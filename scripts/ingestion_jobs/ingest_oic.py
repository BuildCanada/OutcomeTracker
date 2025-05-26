"""
Ingests raw Order in Council (OIC) data from orders-in-council.canada.ca.
Iteratively scrapes OIC attachment pages based on an attachment ID.
Stores raw OIC data into the 'raw_orders_in_council' Firestore collection.

CLI arguments:
--dry_run: If True, will not write to Firestore. Default: False
--log_level: Set the logging level. Default: INFO
--JSON: If True, output raw OIC data to a JSON file instead of Firestore. Default: False
--json_output_dir: The directory to write the JSON file to. Default: ./JSON_outputs
--force_reprocessing: If True, reprocess all items up to the limit, ignoring current status. Default: False
--start_attach_id: The attach_id to start processing from. Overrides persisted state. Default: None

Next steps to make ready for production:
- add check for last run date in Firestore and only ingest items that are newer than that
- add any changes or config to run with docker
- schedule cron job run daily
"""
import os
import logging
import hashlib
from datetime import datetime, timezone, date
from dotenv import load_dotenv
import firebase_admin
from firebase_admin import credentials, firestore
import argparse
import time
import requests
from bs4 import BeautifulSoup
import re
import json

# --- Configuration ---
load_dotenv()

# --- Logger Setup ---
logging.basicConfig(level=logging.INFO,
                    format='%(asctime)s - %(levelname)s - %(filename)s:%(lineno)d - %(message)s',
                    datefmt='%Y-%m-%d %H:%M:%S')
logger = logging.getLogger("ingest_raw_oic")
# --- End Logger Setup ---

# --- Constants ---
RAW_OIC_COLLECTION = "raw_orders_in_council"
CONFIG_COLLECTION = "script_config"  # For storing last_successfully_scraped_attach_id
CONFIG_DOC_ID = "ingest_raw_oic_config"
DEFAULT_START_ATTACH_ID = 47204  # Fallback if no persisted state, adjust as needed. 46560 was the first OIC of 2025 = PC2025-0001. 47204 was first OIC of Carney's tenure (pre-election)
DEFAULT_MAX_CONSECUTIVE_MISSES = 50
DEFAULT_ID_ITERATION_DELAY_SECONDS = 2
OIC_BASE_URL = "https://orders-in-council.canada.ca/attachment.php"
USER_AGENT = "CanadaOICIngestionBot/1.0 (https://buildcanada.com)" # Replace with actual project URL/contact if available

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
JSON_OUTPUT_DIR_DEFAULT = os.path.join(SCRIPT_DIR, "..", "JSON_outputs", "oic_ingestion")
# --- End Constants ---

# --- Firebase Configuration ---
db = None
if not firebase_admin._apps:
    try:
        firebase_admin.initialize_app()
        project_id_env = os.getenv('FIREBASE_PROJECT_ID', '[Not Set - Using Default]')
        logger.info(f"Connected to CLOUD Firestore (Project: {project_id_env}) using default credentials.")
        db = firestore.client()
    except Exception as e_default:
        logger.warning(f"Cloud Firestore init with default creds failed: {e_default}. Attempting service account.")
        cred_path = os.getenv('FIREBASE_SERVICE_ACCOUNT_KEY_PATH')
        if cred_path:
            try:
                logger.info(f"Attempting Firebase init with service account key from env var: {cred_path}")
                cred = credentials.Certificate(cred_path)
                app_name = f'ingest_oic_app_{int(time.time())}'
                firebase_admin.initialize_app(cred, name=app_name)
                project_id_sa_env = os.getenv('FIREBASE_PROJECT_ID', '[Not Set - Using Service Account]')
                logger.info(f"Connected to CLOUD Firestore (Project: {project_id_sa_env}) via service account.")
                db = firestore.client(app=firebase_admin.get_app(name=app_name))
            except Exception as e_sa:
                logger.critical(f"Firebase init with service account key from {cred_path} failed: {e_sa}", exc_info=True)
        else:
            logger.warning("FIREBASE_SERVICE_ACCOUNT_KEY_PATH environment variable not set, and default creds failed.")

if db is None:
    logger.critical("CRITICAL: Failed to obtain Firestore client. Exiting if not in JSON output mode.")
    # Allow script to run for JSON output even if DB connection fails, will be checked later.
# --- End Firebase Configuration ---

# --- Parliament Session Cache & Helper ---
_parliament_sessions_cache = None

def get_parliament_session_id(db_client, publication_date_dt):
    global _parliament_sessions_cache
    if not db_client:
        logger.warning("get_parliament_session_id: db_client is None. Cannot fetch sessions. Returning None.")
        return None
    if publication_date_dt is None:
        logger.warning("get_parliament_session_id: publication_date_dt is None. Cannot determine session. Returning None.")
        return None

    if publication_date_dt.tzinfo is None:
        publication_date_dt_utc = publication_date_dt.replace(tzinfo=timezone.utc)
    else:
        publication_date_dt_utc = publication_date_dt.astimezone(timezone.utc)

    if _parliament_sessions_cache is None:
        logger.info("Populating parliament sessions cache from Firestore...")
        _parliament_sessions_cache = []
        try:
            sessions_ref = db_client.collection('parliament_session').stream()
            for session_doc in sessions_ref:
                session_data = session_doc.to_dict()
                session_data['id'] = session_doc.id
                ecd = session_data.get('election_called_date')
                if isinstance(ecd, datetime):
                    session_data['election_called_date'] = ecd.replace(tzinfo=timezone.utc) if ecd.tzinfo is None else ecd.astimezone(timezone.utc)
                else:
                    logger.warning(f"Session {session_doc.id} missing or invalid election_called_date. Skipping.")
                    continue
                sed = session_data.get('session_end_date')
                if isinstance(sed, datetime):
                    session_data['session_end_date'] = sed.replace(tzinfo=timezone.utc) if sed.tzinfo is None else sed.astimezone(timezone.utc)
                elif sed is not None: # Exists but not datetime
                    logger.warning(f"Session {session_doc.id} has non-datetime session_end_date. Treating as None.")
                    session_data['session_end_date'] = None
                else: # Does not exist or is None
                    session_data['session_end_date'] = None
                _parliament_sessions_cache.append(session_data)
            _parliament_sessions_cache.sort(key=lambda s: s['election_called_date'], reverse=True)
            logger.info(f"Parliament sessions cache populated with {len(_parliament_sessions_cache)} sessions.")
        except Exception as e:
            logger.error(f"Error fetching parliament sessions: {e}", exc_info=True)
            _parliament_sessions_cache = []
            return None

    if not _parliament_sessions_cache:
        logger.warning("Parliament sessions cache is empty. Cannot determine session ID.")
        return None

    for session in _parliament_sessions_cache:
        election_called_dt_utc = session['election_called_date']
        session_end_dt_utc = session['session_end_date']
        if election_called_dt_utc <= publication_date_dt_utc:
            if session_end_dt_utc is None or publication_date_dt_utc < session_end_dt_utc:
                logger.debug(f"Matched to session {session['id']} for date {publication_date_dt_utc.strftime('%Y-%m-%d')}")
                return session['id']
    logger.warning(f"No matching parliament session found for OIC date: {publication_date_dt_utc.strftime('%Y-%m-%d')}.")
    return None
# --- End Parliament Session Helper ---

def get_last_scraped_attach_id(db_client):
    if not db_client:
        logger.warning("DB client not available, cannot get last scraped attach_id. Returning default.")
        return DEFAULT_START_ATTACH_ID
    try:
        doc_ref = db_client.collection(CONFIG_COLLECTION).document(CONFIG_DOC_ID)
        doc = doc_ref.get()
        if doc.exists:
            return doc.to_dict().get("last_successfully_scraped_attach_id", DEFAULT_START_ATTACH_ID)
        else:
            logger.info(f"Config doc {CONFIG_DOC_ID} not found. Using default start attach_id: {DEFAULT_START_ATTACH_ID}")
            return DEFAULT_START_ATTACH_ID
    except Exception as e:
        logger.error(f"Error getting last scraped attach_id: {e}. Using default.", exc_info=True)
        return DEFAULT_START_ATTACH_ID

def update_last_scraped_attach_id(db_client, attach_id):
    if not db_client:
        logger.warning("DB client not available, cannot update last scraped attach_id.")
        return
    try:
        doc_ref = db_client.collection(CONFIG_COLLECTION).document(CONFIG_DOC_ID)
        doc_ref.set({"last_successfully_scraped_attach_id": attach_id, "updated_at": firestore.SERVER_TIMESTAMP}, merge=True)
        logger.info(f"Updated last_successfully_scraped_attach_id to: {attach_id}")
    except Exception as e:
        logger.error(f"Error updating last_successfully_scraped_attach_id to {attach_id}: {e}", exc_info=True)

def normalize_oic_number(raw_oic_number_str):
    if not raw_oic_number_str:
        return None
    # Remove "P.C. " prefix and strip whitespace
    normalized = re.sub(r"P\.C\.\s*", "", raw_oic_number_str, flags=re.IGNORECASE).strip()
    # Basic validation for YYYY-NNNN or YYYY-NNN format
    if re.match(r"^\d{4}-\d{3,4}$", normalized):
        return normalized
    logger.warning(f"Could not normalize OIC number: '{raw_oic_number_str}'. Original kept if pattern mismatch.")
    return raw_oic_number_str.strip() # Fallback to stripped original if complex

def parse_oic_date(date_str):
    if not date_str:
        return None
    try:
        # Example date format on page: "2023-12-15"
        dt_naive = datetime.strptime(date_str, "%Y-%m-%d")
        dt_aware_utc = dt_naive.replace(tzinfo=timezone.utc)
        return dt_aware_utc
    except ValueError as e:
        logger.warning(f"Could not parse OIC date string '{date_str}': {e}")
        return None

def scrape_oic_page(attach_id, session, logger_instance):
    oic_data = {"attach_id": attach_id}
    target_url = f"{OIC_BASE_URL}?attach={attach_id}&lang=en"
    oic_data["source_url_oic_detail_page"] = target_url
    max_retries = 3
    backoff_factor = 2 # seconds

    for attempt in range(max_retries):
        try:
            response = session.get(target_url, timeout=15)
            logger_instance.debug(f"Attempt {attempt+1} for attach_id {attach_id}: Status {response.status_code}, URL: {target_url}")

            if response.status_code == 200:
                soup = BeautifulSoup(response.content, 'html.parser')
                main_content = soup.find('main', id='wb-cont')

                if not main_content:
                    logger_instance.warning(f"Content validation failed for attach_id {attach_id}: 'main#wb-cont' element not found. URL: {target_url}")
                    return None

                pc_number_raw = None
                oic_date_str = None
                full_text_content = None

                # --- PC Number and Date Extraction ---
                # Try finding <strong> tags first
                pc_strong_tag = main_content.find('strong', string=re.compile(r"^\s*PC Number:\s*$", re.IGNORECASE))
                if pc_strong_tag:
                    if pc_strong_tag.next_sibling and isinstance(pc_strong_tag.next_sibling, str) and pc_strong_tag.next_sibling.strip():
                        pc_number_raw = pc_strong_tag.next_sibling.strip()
                    elif pc_strong_tag.parent:
                        parent_text = pc_strong_tag.parent.get_text(separator=' ', strip=True)
                        match = re.search(r"PC Number:\s*([\w-]+)", parent_text, re.IGNORECASE)
                        if match: pc_number_raw = match.group(1)
                
                date_strong_tag = main_content.find('strong', string=re.compile(r"^\s*Date:\s*$", re.IGNORECASE))
                if date_strong_tag:
                    if date_strong_tag.next_sibling and isinstance(date_strong_tag.next_sibling, str) and date_strong_tag.next_sibling.strip():
                        date_str_candidate = date_strong_tag.next_sibling.strip()
                        match = re.match(r"(\d{4}-\d{2}-\d{2})", date_str_candidate)
                        if match: oic_date_str = match.group(1)
                    elif date_strong_tag.parent:
                        parent_text = date_strong_tag.parent.get_text(separator=' ', strip=True)
                        match = re.search(r"Date:\s*(\d{4}-\d{2}-\d{2})", parent_text, re.IGNORECASE)
                        if match: oic_date_str = match.group(1)

                # Fallback using the <p> tag sequence if strong tags didn't work well
                if not pc_number_raw or not oic_date_str:
                    all_p_tags_in_main = main_content.find_all('p', recursive=False)
                    if not pc_number_raw and len(all_p_tags_in_main) > 0:
                        p_pc_text = all_p_tags_in_main[0].get_text(strip=True)
                        match = re.search(r"PC Number:\s*([\w-]+)", p_pc_text, re.IGNORECASE)
                        if match: pc_number_raw = match.group(1)
                    
                    if not oic_date_str and len(all_p_tags_in_main) > 1:
                        p_date_text = all_p_tags_in_main[1].get_text(strip=True)
                        match = re.search(r"Date:\s*(\d{4}-\d{2}-\d{2})", p_date_text, re.IGNORECASE)
                        if match: oic_date_str = match.group(1)
                
                oic_data["oic_number_full_raw"] = pc_number_raw
                oic_data["oic_date"] = parse_oic_date(oic_date_str)

                if not oic_data.get("oic_number_full_raw") or not oic_data.get("oic_date"):
                    logger_instance.warning(f"Crucial fields (OIC Number or Date) are missing after parsing attach_id {attach_id}. "
                                            f"Raw PC#: '{pc_number_raw}', Raw Date: '{oic_date_str}'. Treating as unprocessable. URL: {target_url}")
                    return None

                # --- Full Text ---
                # Remove "Back to Form" button from main_content before processing further for text
                overall_form = main_content.find('form', action='index.php')
                if overall_form:
                    overall_form.decompose()

                hr_tag = main_content.find('hr')
                if hr_tag:
                    content_node = hr_tag.find_next_sibling()
                    if content_node:
                        target_text_element = None
                        if content_node.name == 'p':
                            section_div = content_node.find('div', class_=re.compile(r"Section\d*$", re.IGNORECASE))
                            if not section_div:
                                section_div = content_node.find('div', style=re.compile(r"line-height", re.IGNORECASE))
                            target_text_element = section_div if section_div else content_node
                        elif content_node.name == 'div' and \
                             (re.search(r"Section\d*$", " ".join(content_node.get('class', [])), re.IGNORECASE) or \
                              re.search(r"line-height", content_node.get('style',''), re.IGNORECASE)):
                            target_text_element = content_node
                        else:
                            logger_instance.debug(f"Content node after HR for attach_id {attach_id} is '{content_node.name}'. Using it directly.")
                            target_text_element = content_node
                        
                        if target_text_element:
                            for s in target_text_element.select('script, style, noscript, header, footer, nav, form'): s.decompose()
                            full_text_content = target_text_element.get_text(separator='\n', strip=True)
                        else:
                            logger_instance.warning(f"Target text element was None for attach_id {attach_id} after HR.")
                    else:
                        logger_instance.warning(f"Could not find content node (sibling) after <hr> for attach_id {attach_id}")
                else:
                    logger_instance.warning(f"No <hr> tag found in main_content for attach_id {attach_id}. Full text extraction may be unreliable.")
                    # Fallback: Try to find content in <p> tags after the ones for PC#/Date
                    all_p_tags = main_content.find_all('p', recursive=False) # Re-fetch Ps as form was decomposed from main_content
                    
                    potential_content_p = None
                    start_index_for_content = 0 
                    if pc_number_raw and oic_date_str : start_index_for_content = 2 
                    
                    if len(all_p_tags) > start_index_for_content:
                        potential_content_p = all_p_tags[start_index_for_content]
                    
                    if potential_content_p:
                         section_div = potential_content_p.find('div', class_=re.compile(r"Section\d*$", re.IGNORECASE))
                         if not section_div: section_div = potential_content_p.find('div', style=re.compile(r"line-height", re.IGNORECASE))
                         
                         target_text_element = section_div if section_div else potential_content_p
                         for s in target_text_element.select('script, style, noscript, header, footer, nav, form'): s.decompose()
                         full_text_content = target_text_element.get_text(separator='\n', strip=True)
                         logger_instance.info(f"Used fallback for full text (no HR) for attach_id {attach_id}")
                
                oic_data["full_text_scraped"] = full_text_content

                # --- Title/Summary Raw ---
                title_summary_raw = None
                if oic_data["full_text_scraped"]:
                    for line in oic_data["full_text_scraped"].split('\n'):
                        stripped_line = line.strip()
                        if stripped_line: # Take the first non-empty line
                            title_summary_raw = stripped_line
                            break
                oic_data["title_or_summary_raw"] = title_summary_raw

                # --- Other fields (Department, Minister, Act Citation) ---
                # These are expected to be extracted by the LLM from the full_text_scraped.
                oic_data["responsible_department_raw"] = None
                oic_data["responsible_minister_raw"] = None
                oic_data["act_citation_raw"] = None
                
                return oic_data

            elif response.status_code == 404:
                logger_instance.info(f"Attach_id {attach_id} not found (404). URL: {target_url}")
                return "404_miss" # Special marker for a 404 miss
            elif response.status_code in [403, 429]:
                logger_instance.warning(f"Rate limited or forbidden for attach_id {attach_id} (Status: {response.status_code}). Retrying after backoff... URL: {target_url}")
                time.sleep(backoff_factor * (2 ** attempt)) # Exponential backoff
                continue
            elif response.status_code >= 500:
                logger_instance.error(f"Server error ({response.status_code}) for attach_id {attach_id}. Retrying after backoff... URL: {target_url}")
                time.sleep(backoff_factor * (2 ** attempt))
                continue
            else:
                logger_instance.error(f"Unexpected HTTP status {response.status_code} for attach_id {attach_id}. URL: {target_url}")
                return None # Treat as a general error for this ID
        
        except requests.exceptions.Timeout:
            logger_instance.warning(f"Request timed out for attach_id {attach_id} on attempt {attempt+1}. Retrying... URL: {target_url}")
            time.sleep(backoff_factor * (2 ** attempt))
        except requests.exceptions.RequestException as e:
            logger_instance.error(f"Request exception for attach_id {attach_id} on attempt {attempt+1}: {e}. URL: {target_url}", exc_info=True)
            time.sleep(backoff_factor * (2 ** attempt)) # Retry on general request errors too
            
    logger_instance.error(f"Failed to fetch attach_id {attach_id} after {max_retries} retries. URL: {target_url}")
    return None # Failed after retries

# --- Main Ingestion Logic ---
def ingest_oics(db_client, dry_run=False, output_to_json=False, json_output_dir=None,
                max_consecutive_misses=DEFAULT_MAX_CONSECUTIVE_MISSES,
                iteration_delay_seconds=DEFAULT_ID_ITERATION_DELAY_SECONDS,
                start_attach_id_override=None):

    if not db_client and not dry_run and not output_to_json:
        logger.critical("Firestore client (db) is not initialized, and not in dry_run or JSON output mode. Cannot proceed with Firestore operations. Exiting.")
        return

    logger.info("Starting OIC ingestion process...")
    if dry_run: logger.info("*** DRY RUN MODE ENABLED ***")
    if output_to_json:
        logger.info(f"*** JSON OUTPUT MODE ENABLED to {json_output_dir} ***")
        os.makedirs(json_output_dir, exist_ok=True)

    current_attach_id = DEFAULT_START_ATTACH_ID # Default in case no override and no DB state
    if start_attach_id_override is not None:
        current_attach_id = start_attach_id_override
        logger.info(f"Using provided --start_attach_id: {current_attach_id}")
    else:
        current_attach_id = get_last_scraped_attach_id(db_client) + 1
        logger.info(f"Starting iteration from attach_id based on persisted state or default: {current_attach_id}")

    consecutive_misses = 0
    new_oics_ingested_this_run = 0
    new_oics_for_json = []
    max_attach_id_processed_this_run = current_attach_id -1 # Initialize to previous
    first_attach_id_successfully_processed_this_run = None

    with requests.Session() as session:
        session.headers.update({"User-Agent": USER_AGENT})

        while consecutive_misses < max_consecutive_misses:
            logger.info(f"Attempting to scrape attach_id: {current_attach_id}")
            scraped_data = scrape_oic_page(current_attach_id, session, logger)

            if scraped_data == "404_miss":
                consecutive_misses += 1
                logger.info(f"Attach_id {current_attach_id} was a 404 miss. Consecutive misses: {consecutive_misses}/{max_consecutive_misses}")
            elif scraped_data: # Successfully scraped data
                consecutive_misses = 0 # Reset miss counter on success
                
                raw_oic_id_normalized = normalize_oic_number(scraped_data.get("oic_number_full_raw"))
                if not raw_oic_id_normalized:
                    logger.warning(f"Could not derive a normalized OIC ID for attach_id {current_attach_id}. Skipping. Data: {scraped_data.get('oic_number_full_raw')}")
                    current_attach_id += 1
                    time.sleep(iteration_delay_seconds)
                    continue

                scraped_data["raw_oic_id"] = raw_oic_id_normalized
                oic_firestore_doc_id = raw_oic_id_normalized # Use normalized as document ID

                # Idempotency Check (if not JSON output or dry run)
                if db_client and not output_to_json and not dry_run:
                    doc_ref = db_client.collection(RAW_OIC_COLLECTION).document(oic_firestore_doc_id)
                    if doc_ref.get().exists:
                        logger.info(f"OIC with ID {oic_firestore_doc_id} (from attach_id {current_attach_id}) already exists. Skipping.")
                        max_attach_id_processed_this_run = max(max_attach_id_processed_this_run, current_attach_id) # Still update if we successfully processed it.
                        current_attach_id += 1
                        time.sleep(iteration_delay_seconds)
                        continue
                
                scraped_data["ingested_at"] = firestore.SERVER_TIMESTAMP
                scraped_data["evidence_processing_status"] = "pending_evidence_creation"
                scraped_data["related_evidence_item_id"] = None
                scraped_data["parliament_session_id_assigned"] = get_parliament_session_id(db_client, scraped_data.get("oic_date"))

                if first_attach_id_successfully_processed_this_run is None:
                    first_attach_id_successfully_processed_this_run = current_attach_id

                if output_to_json:
                    json_compatible_item_data = scraped_data.copy()
                    for key, value in json_compatible_item_data.items():
                        if isinstance(value, datetime): json_compatible_item_data[key] = value.isoformat()
                        elif value == firestore.SERVER_TIMESTAMP: json_compatible_item_data[key] = datetime.now(timezone.utc).isoformat()
                    new_oics_for_json.append(json_compatible_item_data)
                    logger.info(f"Prepared for JSON: OIC {oic_firestore_doc_id} from attach_id {current_attach_id}")
                elif not dry_run:
                    if db_client:
                        db_client.collection(RAW_OIC_COLLECTION).document(oic_firestore_doc_id).set(scraped_data)
                        logger.info(f"Ingested OIC {oic_firestore_doc_id} from attach_id {current_attach_id} into Firestore.")
                    else: # Should have been caught earlier, but safeguard
                        logger.error(f"CRITICAL: db_client is None during Firestore write attempt for OIC {oic_firestore_doc_id}")
                else: # Dry run
                    log_data_dry_run = {k: (v.isoformat() if isinstance(v, datetime) else str(v)) for k,v in scraped_data.items()}
                    logger.info(f"[DRY RUN] Would ingest OIC {oic_firestore_doc_id} (attach_id {current_attach_id}) with data: {log_data_dry_run}")

                new_oics_ingested_this_run += 1
                max_attach_id_processed_this_run = max(max_attach_id_processed_this_run, current_attach_id)

            else: # scrape_oic_page returned None (error other than 404)
                logger.error(f"Failed to scrape or process attach_id {current_attach_id}. Skipping this ID.")
                consecutive_misses += 1 # Treat as a miss
                logger.info(f"Attach_id {current_attach_id} was an unprocessable page (e.g., validation failed, content missing). Consecutive misses: {consecutive_misses}/{max_consecutive_misses}")
                # Optionally, could increment a different error counter or implement more nuanced retry for specific errors here.
                # For now, just moves to the next ID. Could also count as a "miss" if desired.

            current_attach_id += 1
            time.sleep(iteration_delay_seconds) # Wait before next request

        if consecutive_misses >= max_consecutive_misses:
            logger.info(f"Stopping OIC ingestion: Reached max consecutive misses ({max_consecutive_misses}). Assumed caught up.")

    if new_oics_ingested_this_run > 0 and not dry_run and not output_to_json: # Only update state if not dry/JSON and items were processed.
        update_last_scraped_attach_id(db_client, max_attach_id_processed_this_run)
    elif dry_run and new_oics_ingested_this_run > 0:
        logger.info(f"[DRY RUN] Would update last_successfully_scraped_attach_id to: {max_attach_id_processed_this_run}")


    if output_to_json and new_oics_for_json:
        try:
            timestamp_str = datetime.now().strftime("%Y%m%d_%H%M%S")
            json_filename = os.path.join(json_output_dir, f"ingested_oics_{timestamp_str}.json")
            with open(json_filename, 'w', encoding='utf-8') as f:
                json.dump(new_oics_for_json, f, indent=4, ensure_ascii=False)
            logger.info(f"Successfully wrote {len(new_oics_for_json)} OICs to JSON file: {json_filename}")
        except Exception as e:
            logger.error(f"Error writing OICs to JSON file: {e}", exc_info=True)

    logger.info(f"--- OIC Ingestion Summary ---")
    logger.info(f"Total new OICs ingested/prepared for JSON this run: {new_oics_ingested_this_run}")
    logger.info(f"Highest attach_id checked in this run: {current_attach_id -1}") # -1 because it increments before next loop or exit
    logger.info(f"First attach_id successfully processed this run: {first_attach_id_successfully_processed_this_run if first_attach_id_successfully_processed_this_run is not None else 'N/A'}")
    logger.info(f"Highest attach_id successfully processed and stored/prepared this run: {max_attach_id_processed_this_run if new_oics_ingested_this_run > 0 else 'N/A'}")
    logger.info(f"--- End of OIC Ingestion Summary ---")


def main():
    parser = argparse.ArgumentParser(description="Ingest raw Orders in Council (OICs) by iterating attachment IDs.")
    parser.add_argument('--dry_run', action='store_true', help='If set, do not write to Firestore or update state.')
    parser.add_argument('--JSON', dest='output_to_json', action='store_true', help='Output processed OICs to a JSON file instead of Firestore.')
    parser.add_argument('--json_output_dir', type=str, default=JSON_OUTPUT_DIR_DEFAULT, help=f'Directory for JSON output. Default: {JSON_OUTPUT_DIR_DEFAULT}')
    parser.add_argument('--log_level', type=str, default='INFO', choices=['DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL'], help='Set the logging level.')
    parser.add_argument('--max_consecutive_misses', type=int, default=DEFAULT_MAX_CONSECUTIVE_MISSES, help=f'Max consecutive attach_id misses (404s) before stopping. Default: {DEFAULT_MAX_CONSECUTIVE_MISSES}')
    parser.add_argument('--id_iteration_delay_seconds', type=float, default=DEFAULT_ID_ITERATION_DELAY_SECONDS, help=f'Delay in seconds between fetching attach_ids. Default: {DEFAULT_ID_ITERATION_DELAY_SECONDS}')
    parser.add_argument('--start_attach_id', type=int, default=None, help='Specify the attach_id to start processing from. Overrides persisted state.')
    
    args = parser.parse_args()
    logger.setLevel(getattr(logging, args.log_level.upper()))

    if not db and not args.dry_run and not args.output_to_json:
        logger.critical("Firestore client (db) is not initialized, and not in dry_run or JSON output mode. Cannot proceed. Exiting.")
        return

    ingest_oics(db, args.dry_run, args.output_to_json, args.json_output_dir,
                args.max_consecutive_misses, args.id_iteration_delay_seconds,
                args.start_attach_id)

if __name__ == '__main__':
    main() 