"""
Ingests raw notice information from Canada Gazette Part II into Firestore.
Fetches an RSS feed of Gazette issues, scrapes each issue's table of contents
to find individual regulations, and stores their metadata.

CLI arguments:
--start_date: The start date to ingest from. Format: YYYY-MM-DD. Default: 2025-01-01
--end_date: The end date to ingest to. Format: YYYY-MM-DD. Default: today
--dry_run: If True, will not write to Firestore. Default: False
--JSON: If True, will write to a JSON file. Default: False
--JSON_output_dir: The directory to write the JSON file to. Default: ./JSON_outputs

Next steps to make ready for production:
- add check for last run date in Firestore and only ingest items that are newer than that
- add any changes or config to run with docker
"""
import os
import logging
import feedparser
import hashlib
from datetime import datetime, timezone, date
from dotenv import load_dotenv
import firebase_admin
from firebase_admin import credentials, firestore
import argparse
import time # For unique app name fallback
from dateutil import parser as dateutil_parser # For parsing date strings flexibly
import json
import requests
from bs4 import BeautifulSoup
import re # <--- Import the 're' module

# --- Configuration ---
load_dotenv()

# --- Logger Setup ---
logging.basicConfig(level=logging.INFO,
                    format='%(asctime)s - %(levelname)s - %(filename)s:%(lineno)d - %(message)s',
                    datefmt='%Y-%m-%d %H:%M:%S')
logger = logging.getLogger("ingest_canada_gazette_p2")
# --- End Logger Setup ---

# --- Constants ---
GAZETTE_P2_RSS_URL = "https://gazette.gc.ca/rss/p2-eng.xml"
RAW_GAZETTE_P2_NOTICES_COLLECTION = "raw_gazette_p2_notices"
DEFAULT_START_DATE_STR = "2025-01-01" # Sensible default for Gazette
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
JSON_OUTPUT_DIR_DEFAULT = os.path.join(SCRIPT_DIR, "..", "JSON_outputs", "gazette_p2")

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
                app_name = 'ingest_gazette_p2_app'
                try:
                    firebase_admin.initialize_app(cred, name=app_name)
                except ValueError: # App already exists
                    app_name_unique = f"{app_name}_{str(time.time())}"
                    firebase_admin.initialize_app(cred, name=app_name_unique)
                    app_name = app_name_unique
                project_id_sa_env = os.getenv('FIREBASE_PROJECT_ID', '[Not Set - Using Service Account]')
                logger.info(f"Connected to CLOUD Firestore (Project: {project_id_sa_env}) via service account.")
                db = firestore.client(app=firebase_admin.get_app(name=app_name))
            except Exception as e_sa:
                logger.critical(f"Firebase init with service account key from {cred_path} failed: {e_sa}", exc_info=True)
        else:
            logger.warning("FIREBASE_SERVICE_ACCOUNT_KEY_PATH environment variable not set, and default creds failed.")

# Global cache for parliament sessions to avoid repeated Firestore queries within a single run
_parliament_sessions_cache = None

if db is None:
    logger.critical("CRITICAL: Failed to obtain Firestore client. Exiting.")
    # exit("Exiting: Firestore client not available.") # Allow script to run for local JSON generation if needed
# --- End Firebase Configuration ---

# --- Helper Functions ---

def get_parliament_session_id(db_client, publication_date_dt):
    """
    Determines parliament session ID based on publication date by querying the 'parliament_session' collection.
    Uses a global cache to minimize Firestore reads during a single script run.
    Assumes publication_date_dt is a timezone-aware datetime object (e.g., UTC).
    """
    global _parliament_sessions_cache

    if not db_client:
        logger.warning("get_parliament_session_id: db_client is None. Cannot fetch sessions. Returning None.")
        return None

    if _parliament_sessions_cache is None:
        logger.info("Populating parliament sessions cache from Firestore...")
        _parliament_sessions_cache = []
        try:
            sessions_ref = db_client.collection('parliament_session').stream()
            for session_doc in sessions_ref:
                session_data = session_doc.to_dict()
                session_data['id'] = session_doc.id # Store document ID as session_id
                # Ensure election_called_date is a datetime object (and timezone-aware, assume UTC if naive)
                if 'election_called_date' in session_data and isinstance(session_data['election_called_date'], datetime):
                    if session_data['election_called_date'].tzinfo is None:
                        session_data['election_called_date'] = session_data['election_called_date'].replace(tzinfo=timezone.utc)
                else:
                    logger.warning(f"Session {session_doc.id} missing or has invalid election_called_date. Skipping.")
                    continue # Skip this session if essential date is missing
                
                # Ensure session_end_date is a datetime object if it exists (and timezone-aware)
                if 'session_end_date' in session_data and isinstance(session_data['session_end_date'], datetime):
                    if session_data['session_end_date'].tzinfo is None:
                        session_data['session_end_date'] = session_data['session_end_date'].replace(tzinfo=timezone.utc)
                elif 'session_end_date' in session_data and session_data['session_end_date'] is not None: # It exists but isn't datetime
                    logger.warning(f"Session {session_doc.id} has non-datetime session_end_date. Treating as None for now.")
                    session_data['session_end_date'] = None
                else: # Does not exist or is None
                    session_data['session_end_date'] = None

                _parliament_sessions_cache.append(session_data)
            # Sort sessions by election_called_date just in case they aren't ordered in DB
            _parliament_sessions_cache.sort(key=lambda s: s['election_called_date'], reverse=True)
            logger.info(f"Parliament sessions cache populated with {len(_parliament_sessions_cache)} sessions.")
        except Exception as e:
            logger.error(f"Error fetching parliament sessions: {e}", exc_info=True)
            _parliament_sessions_cache = [] # Reset cache on error to allow retry on next call if appropriate
            return None # Cannot determine session if fetch fails

    if not _parliament_sessions_cache:
        logger.warning("Parliament sessions cache is empty. Cannot determine session ID.")
        return None

    # Ensure publication_date_dt is timezone-aware (assume UTC if naive, consistent with Firestore)
    if publication_date_dt.tzinfo is None:
        publication_date_dt_utc = publication_date_dt.replace(tzinfo=timezone.utc)
    else:
        publication_date_dt_utc = publication_date_dt.astimezone(timezone.utc)

    for session in _parliament_sessions_cache:
        election_called_dt_utc = session['election_called_date'] # Already UTC from caching logic
        session_end_dt_utc = session['session_end_date'] # Already UTC or None

        if election_called_dt_utc <= publication_date_dt_utc:
            if session_end_dt_utc is None: # Current or ongoing session
                logger.debug(f"Matched to current/ongoing session {session['id']} for date {publication_date_dt_utc}")
                return session['id']
            elif publication_date_dt_utc < session_end_dt_utc:
                logger.debug(f"Matched to session {session['id']} for date {publication_date_dt_utc}")
                return session['id']
    
    logger.warning(f"No matching parliament session found for publication date: {publication_date_dt_utc}. Cached sessions: {_parliament_sessions_cache}")
    return None

def parse_rss_publication_date(entry):
    """
    Parses the publication date from an RSS entry for Gazette.
    Gazette RSS uses 'published_parsed' (struct_time) or 'published' (string).
    Returns a timezone-aware datetime object or None.
    """
    pub_date_dt = None
    if hasattr(entry, 'published_parsed') and entry.published_parsed:
        try:
            pub_date_dt = datetime(*entry.published_parsed[:6], tzinfo=timezone.utc)
        except Exception as e:
            logger.warning(f"Could not parse 'published_parsed' struct_time {entry.published_parsed}: {e}")
    elif hasattr(entry, 'published') and entry.published:
        try:
            pub_date_dt = dateutil_parser.parse(entry.published)
            if pub_date_dt.tzinfo is None:
                 pub_date_dt = pub_date_dt.replace(tzinfo=timezone.utc)
        except Exception as e:
            logger.warning(f"Could not parse 'published' string '{entry.published}': {e}")
    
    if not pub_date_dt:
        logger.warning(f"Failed to parse date for RSS entry with link: {entry.get('link', 'N/A')}")
    return pub_date_dt

def scrape_gazette_issue_page(issue_url, logger_instance):
    """
    Scrapes a Canada Gazette Part II issue page (table of contents)
    to find individual regulations.
    Returns a list of dictionaries, each representing a regulation.
    """
    regulations_found = []
    try:
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        }
        response = requests.get(issue_url, headers=headers, timeout=30)
        response.raise_for_status()
        soup = BeautifulSoup(response.content, 'html.parser')

        # Find the main content area for Part II issues
        # Example: <main property="mainContentOfPage" typeof="WebPageElement">
        # Within this, regulations are often in a <ul> with class "lst-noneวนtype" or similar.
        # Or look for <div id="gazetteContent">
        main_content = soup.find('main', attrs={'property': 'mainContentOfPage'})
        if not main_content:
            main_content = soup.find('div', id='gazetteContent') # Fallback

        if main_content:
            # Regulations are typically in list items. Look for <li> elements.
            # The exact selectors might need adjustment based on Gazette website structure.
            # Common pattern: <li> contains <a> for HTML, another <a> for PDF, title text, and SOR/SI number.
            
            # Try finding a common list structure first
            regulation_list_items = main_content.select('ul.lst-noneวนtype > li') # Note: class might change
            if not regulation_list_items:
                 # Fallback: Look for any <li> inside a prominent div like 'cn-toc' or directly in main_content
                regulation_list_items = main_content.select('div.cn-toc > ul > li') 
            if not regulation_list_items:
                regulation_list_items = main_content.find_all('li')


            logger_instance.debug(f"Found {len(regulation_list_items)} potential list items for regulations on {issue_url}")

            for item in regulation_list_items:
                reg_data = {
                    "regulation_title": None,
                    "source_url_regulation_html": None,
                    "source_url_regulation_pdf": None,
                    "registration_sor_si_number": None,
                    "summary_snippet_from_gazette": None # Usually not available on TOC, but placeholder
                }

                # Extract HTML link and title
                html_link_tag = item.find('a', href=lambda href: href and href.endswith('.html'))
                if html_link_tag and html_link_tag.get('href'):
                    reg_data["source_url_regulation_html"] = requests.compat.urljoin(issue_url, html_link_tag['href'])
                    reg_data["regulation_title"] = html_link_tag.get_text(strip=True)
                else:
                    # If no HTML link, this might not be a regulation entry we're interested in, or structure is different
                    # Try to get title from a strong tag or similar if no link
                    strong_title = item.find('strong')
                    if strong_title:
                         reg_data["regulation_title"] = strong_title.get_text(strip=True)
                    else: # last resort, grab all text and hope for the best, may require cleaning
                         all_text = item.get_text(" ", strip=True)
                         # A very basic heuristic: if it contains "SOR/" or "SI/" it might be a title line
                         if "SOR/" in all_text or "SI/" in all_text:
                              reg_data["regulation_title"] = all_text.splitlines()[0] if all_text else None


                # Extract PDF link
                pdf_link_tag = item.find('a', href=lambda href: href and href.endswith('.pdf'))
                if pdf_link_tag and pdf_link_tag.get('href'):
                    reg_data["source_url_regulation_pdf"] = requests.compat.urljoin(issue_url, pdf_link_tag['href'])

                # Attempt to parse SOR/SI number (often part of the title or nearby text)
                item_text = item.get_text(" ", strip=True)
                sor_si_match = re.search(r'(SOR/\d{4}-\d+|SI/\d{4}-\d+)', item_text)
                if sor_si_match:
                    reg_data["registration_sor_si_number"] = sor_si_match.group(0)
                
                # If we have at least an HTML URL and a title, consider it a valid find
                if reg_data["source_url_regulation_html"] and reg_data["regulation_title"]:
                    # Clean up title if SOR/SI number is also in it
                    if reg_data["registration_sor_si_number"] and reg_data["registration_sor_si_number"] in reg_data["regulation_title"]:
                        reg_data["regulation_title"] = reg_data["regulation_title"].replace(reg_data["registration_sor_si_number"], "").strip()
                        # Remove extra spaces or leading/trailing hyphens/colons if any
                        reg_data["regulation_title"] = re.sub(r'^[\s:-]+|[\s:-]+$', '', reg_data["regulation_title"]).strip()


                    regulations_found.append(reg_data)
                    logger_instance.debug(f"Found regulation: {reg_data['regulation_title']} - HTML: {reg_data['source_url_regulation_html']}")
                elif reg_data["regulation_title"] and not reg_data["source_url_regulation_html"]:
                     logger_instance.debug(f"Found item with title '{reg_data['regulation_title']}' but no .html link. Inspecting: {item_text[:100]}")


        else:
            logger_instance.warning(f"Could not find main content area on {issue_url}. No regulations extracted.")

    except requests.exceptions.RequestException as e:
        logger_instance.error(f"Error fetching URL {issue_url} for scraping: {e}")
    except Exception as e:
        logger_instance.error(f"Error scraping Gazette issue page {issue_url}: {e}", exc_info=True)
    
    return regulations_found

def scrape_regulation_full_text(regulation_html_url, logger_instance):
    """
    Scrapes the main textual content from a Canada Gazette Part II regulation HTML page.
    Returns the cleaned text or None if an error occurs or content isn't found.
    """
    try:
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        }
        response = requests.get(regulation_html_url, headers=headers, timeout=20) # Increased timeout slightly
        response.raise_for_status()
        soup = BeautifulSoup(response.content, 'html.parser')

        # Common content containers for regulations (often on laws-lois.justice.gc.ca or similar)
        # Order of preference can be adjusted
        main_content_selectors = [
            {'tag': 'main', 'attrs': {'property': 'mainContentOfPage'}}, # Primary target for justice.gc.ca
            {'tag': 'article', 'attrs': {}}, # General article tag
            {'tag': 'div', 'attrs': {'id': 'wb-main-in'}}, # Common on GC sites
            {'tag': 'div', 'attrs': {'class': 'content'}}, # Generic content class
            {'tag': 'body', 'attrs': {}} # Fallback to whole body
        ]

        text_content = None

        for selector_config in main_content_selectors:
            content_area = soup.find(selector_config['tag'], attrs=selector_config.get('attrs', {}))
            if content_area:
                logger_instance.debug(f"Found content area with {selector_config} on {regulation_html_url}")
                # Remove known non-content sections if necessary (e.g., share buttons, breadcrumbs, footers within main)
                # Example: for el in content_area.select('.wb-share, nav[aria-label="breadcrumb"], footer'): el.decompose()
                
                # Remove script and style tags explicitly before getting text
                for s in content_area.select('script, style'):
                    s.decompose()
                
                text_content = content_area.get_text(separator='\n', strip=True)
                break # Use the first successful selector
        
        if text_content:
            logger_instance.debug(f"Successfully scraped full text from {regulation_html_url} (length: {len(text_content)}).")
            # Basic clean up: reduce multiple newlines to a single one, for example
            cleaned_text = re.sub(r'\n{3,}', '\n\n', text_content).strip()
            if len(cleaned_text) > 200000: # Arbitrary limit to avoid excessively large text fields
                logger_instance.warning(f"Truncating scraped text from {regulation_html_url} as it exceeds 200,000 characters.")
                return cleaned_text[:200000] + "... [truncated]"
            return cleaned_text
        else:
            logger_instance.warning(f"Could not find a suitable main content container on {regulation_html_url}. No full text scraped.")
            return None

    except requests.exceptions.RequestException as e:
        logger_instance.error(f"Error fetching URL {regulation_html_url} for full text scraping: {e}")
        return None
    except Exception as e:
        logger_instance.error(f"Error scraping full text from {regulation_html_url}: {e}", exc_info=True)
        return None

# --- Main Ingestion Logic ---
def fetch_and_process_gazette_issues(db_client, dry_run=False, start_date_filter=None, end_date_filter=None, output_to_json=False, json_output_dir=None):
    logger.info("Starting Canada Gazette Part II ingestion process...")
    if dry_run:
        logger.info("*** DRY RUN MODE ENABLED - No data will be written to Firestore. ***")
    if start_date_filter:
        logger.info(f"Filtering Gazette issues: Processing issues published on or after {start_date_filter.strftime('%Y-%m-%d')}")
    if end_date_filter:
        logger.info(f"Filtering Gazette issues: Processing issues published on or before {end_date_filter.strftime('%Y-%m-%d')}")
    if output_to_json:
        logger.info(f"*** JSON OUTPUT MODE ENABLED - New items will be written to JSON files in {json_output_dir}. ***")
        os.makedirs(json_output_dir, exist_ok=True)

    issues_processed_count = 0
    regulations_found_total_count = 0
    regulations_ingested_count = 0
    regulations_skipped_duplicate_count = 0
    regulations_skipped_date_filter_count = 0 # For individual regulations if their dates differ from issue
    errors_total_count = 0
    all_regulations_for_json = []

    logger.info(f"Fetching Gazette Part II RSS feed: {GAZETTE_P2_RSS_URL}")
    feed = feedparser.parse(GAZETTE_P2_RSS_URL)

    if feed.bozo:
        logger.error(f"Error parsing RSS feed: {feed.bozo_exception}", exc_info=True)
        # return # Depending on severity, might still try to process entries

    logger.info(f"Found {len(feed.entries)} issues in the RSS feed.")

    for issue_entry in feed.entries:
        issues_processed_count += 1
        issue_url = issue_entry.get("link")
        issue_publication_date_dt = parse_rss_publication_date(issue_entry)

        if not issue_url or not issue_publication_date_dt:
            logger.warning(f"Skipping RSS entry due to missing link or publication date: Title '{issue_entry.get('title', 'N/A')}'")
            errors_total_count +=1
            continue

        logger.info(f"Processing Gazette Issue: {issue_entry.get('title', issue_url)} (Published: {issue_publication_date_dt.strftime('%Y-%m-%d')})")

        # Apply date filter for the ISSUE
        if start_date_filter and issue_publication_date_dt.date() < start_date_filter:
            logger.debug(f"Skipping issue {issue_url} (Pub date: {issue_publication_date_dt.date()}) - before start date {start_date_filter}.")
            continue
        if end_date_filter and issue_publication_date_dt.date() > end_date_filter:
            logger.debug(f"Skipping issue {issue_url} (Pub date: {issue_publication_date_dt.date()}) - after end date {end_date_filter}.")
            continue
        
        regulations_from_issue = scrape_gazette_issue_page(issue_url, logger)
        if not regulations_from_issue:
            logger.info(f"No individual regulations found or extracted from issue: {issue_url}")
            continue
        
        logger.info(f"Found {len(regulations_from_issue)} potential regulations in issue: {issue_url}")
        regulations_found_total_count += len(regulations_from_issue)

        for reg_data in regulations_from_issue:
            try:
                if not reg_data["source_url_regulation_html"] or not reg_data["regulation_title"]:
                    logger.warning(f"Skipping regulation entry with missing HTML URL or title from issue {issue_url}. Data: {reg_data}")
                    errors_total_count += 1
                    continue

                # Use issue's publication date for the regulation itself
                regulation_publication_date_dt = issue_publication_date_dt 

                # Create a unique ID for the raw gazette item
                # Hash of HTML URL and precise publication date to ensure uniqueness
                id_hash_input = f"{reg_data['source_url_regulation_html']}_{regulation_publication_date_dt.isoformat()}"
                full_hash = hashlib.sha256(id_hash_input.encode('utf-8')).hexdigest()
                # Consistent ID format: SOURCETYPE_YYYYMMDD_HASH12
                date_yyyymmdd_str = regulation_publication_date_dt.strftime('%Y%m%d')
                short_hash = full_hash[:12]
                raw_gazette_item_id = f"CGP2_{date_yyyymmdd_str}_{short_hash}"

                # Idempotency Check (based on source_url_regulation_html primarily)
                if db_client and not output_to_json: # Only check Firestore if db is available and not just outputting to JSON
                    doc_ref = db_client.collection(RAW_GAZETTE_P2_NOTICES_COLLECTION).document(raw_gazette_item_id) # Check by intended ID first
                    if doc_ref.get().exists:
                        logger.debug(f"Skipping duplicate regulation (ID: {raw_gazette_item_id} exists): {reg_data['regulation_title']}")
                        regulations_skipped_duplicate_count += 1
                        continue
                    
                    # Secondary check: query by source_url_regulation_html if ID method is new or might change
                    query_by_url = db_client.collection(RAW_GAZETTE_P2_NOTICES_COLLECTION).where("source_url_regulation_html", "==", reg_data["source_url_regulation_html"]).limit(1).stream()
                    if any(query_by_url): # if the generator is not empty
                        logger.debug(f"Skipping duplicate regulation (URL exists): {reg_data['source_url_regulation_html']} for title {reg_data['regulation_title']}")
                        regulations_skipped_duplicate_count += 1
                        continue


                parliament_session_id = get_parliament_session_id(db_client, regulation_publication_date_dt)

                # Act sponsoring is hard to parse from TOC; will be handled in Stage 2
                act_sponsoring = None 

                # Scrape full text of the regulation
                full_text_scraped = None
                if reg_data["source_url_regulation_html"]:
                    logger.debug(f"Attempting to scrape full text for regulation: {reg_data['source_url_regulation_html']}")
                    full_text_scraped = scrape_regulation_full_text(reg_data["source_url_regulation_html"], logger)

                notice_doc_data = {
                    "raw_gazette_item_id": raw_gazette_item_id,
                    "regulation_title": reg_data["regulation_title"],
                    "source_url_regulation_html": reg_data["source_url_regulation_html"],
                    "source_url_regulation_pdf": reg_data["source_url_regulation_pdf"],
                    "gazette_issue_url": issue_url,
                    "publication_date": regulation_publication_date_dt, # Firestore Timestamp
                    "act_sponsoring": act_sponsoring, # Placeholder
                    "registration_sor_si_number": reg_data["registration_sor_si_number"],
                    "summary_snippet_from_gazette": reg_data["summary_snippet_from_gazette"],
                    "full_text_scraped": full_text_scraped, # Added field
                    "ingested_at": firestore.SERVER_TIMESTAMP,
                    "evidence_processing_status": "pending_evidence_creation",
                    "related_evidence_item_id": None,
                    "parliament_session_id_assigned": parliament_session_id
                }

                if output_to_json:
                    json_compatible_item_data = notice_doc_data.copy()
                    for key, value in json_compatible_item_data.items():
                        if isinstance(value, datetime):
                            json_compatible_item_data[key] = value.isoformat()
                        elif isinstance(value, date):
                            json_compatible_item_data[key] = value.isoformat()
                        elif value == firestore.SERVER_TIMESTAMP:
                             json_compatible_item_data[key] = datetime.now(timezone.utc).isoformat()

                    all_regulations_for_json.append(json_compatible_item_data)
                    logger.info(f"Prepared for JSON output (ID: {raw_gazette_item_id}): {reg_data['regulation_title']}")
                    regulations_ingested_count += 1
                elif not dry_run:
                    if db_client:
                        db_client.collection(RAW_GAZETTE_P2_NOTICES_COLLECTION).document(raw_gazette_item_id).set(notice_doc_data)
                        logger.info(f"Successfully ingested regulation (ID: {raw_gazette_item_id}) into Firestore: {reg_data['regulation_title']}")
                        regulations_ingested_count += 1
                    else:
                        logger.error(f"CRITICAL: Attempted to write to Firestore but db_client is None. Item: {raw_gazette_item_id}")
                        errors_total_count += 1
                else: # Dry run, not JSON output
                    log_data_dry_run = {k: (v.isoformat() if isinstance(v, (datetime, date)) else str(v)) for k,v in notice_doc_data.items()}
                    logger.info(f"[DRY RUN] Would ingest regulation (ID: {raw_gazette_item_id}): {reg_data['regulation_title']} with data {log_data_dry_run}")
                    regulations_ingested_count += 1
            
            except Exception as e_reg:
                logger.error(f"Error processing individual regulation '{reg_data.get('regulation_title', 'N/A')}' from issue {issue_url}: {e_reg}", exc_info=True)
                errors_total_count += 1
                continue

    if output_to_json and all_regulations_for_json:
        try:
            timestamp_str = datetime.now().strftime("%Y%m%d_%H%M%S")
            json_filename = os.path.join(json_output_dir, f"ingested_gazette_p2_notices_{timestamp_str}.json")
            with open(json_filename, 'w', encoding='utf-8') as f:
                json.dump(all_regulations_for_json, f, indent=4, ensure_ascii=False)
            logger.info(f"Successfully wrote {len(all_regulations_for_json)} regulations to JSON file: {json_filename}")
        except Exception as e:
            logger.error(f"Error writing regulations to JSON file: {e}", exc_info=True)
            errors_total_count += len(all_regulations_for_json)

    logger.info("--- Gazette Part II Ingestion Summary ---")
    logger.info(f"RSS Issues Iterated: {issues_processed_count}")
    logger.info(f"Total individual regulations found across issues: {regulations_found_total_count}")
    if output_to_json:
        logger.info(f"Regulations prepared for JSON output: {regulations_ingested_count}")
    elif dry_run:
        logger.info(f"Regulations that WOULD BE ingested (Dry Run): {regulations_ingested_count}")
    else:
        logger.info(f"Regulations newly ingested into Firestore: {regulations_ingested_count}")
    logger.info(f"Regulations skipped (already existed in Firestore): {regulations_skipped_duplicate_count}")
    logger.info(f"Errors during processing (issues or regulations): {errors_total_count}")
    logger.info("--- End of Gazette Part II Ingestion Summary ---")


def main():
    parser = argparse.ArgumentParser(description="Ingest Canada Gazette Part II notices into Firestore.")
    parser.add_argument("--dry_run", action="store_true", help="Perform a dry run without writing to Firestore.")
    parser.add_argument("--start_date", type=str, help=f"Start date filter for Gazette issues (YYYY-MM-DD). Overrides default: {DEFAULT_START_DATE_STR}")
    parser.add_argument("--end_date", type=str, help="End date filter for Gazette issues (YYYY-MM-DD). Defaults to today if not specified.")
    parser.add_argument("--log_level", type=str, default="INFO", choices=["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"], help="Set the logging level.")
    parser.add_argument("--JSON", dest="output_to_json", action="store_true", help="Output ingested items to a JSON file instead of Firestore.")
    parser.add_argument("--json_output_dir", type=str, default=JSON_OUTPUT_DIR_DEFAULT, help=f"Directory for JSON output. Default: {JSON_OUTPUT_DIR_DEFAULT}")


    args = parser.parse_args()
    logger.setLevel(getattr(logging, args.log_level.upper()))

    if db is None and not args.output_to_json and not args.dry_run:
        logger.critical("Firestore client (db) is not initialized, and not in JSON output or dry_run mode. Cannot proceed with Firestore writes. Exiting.")
        return

    effective_start_date = None
    if args.start_date:
        try:
            effective_start_date = datetime.strptime(args.start_date, "%Y-%m-%d").date()
        except ValueError:
            logger.error(f"Invalid --start_date format: {args.start_date}. Please use YYYY-MM-DD. Exiting.")
            return
    else:
        effective_start_date = datetime.strptime(DEFAULT_START_DATE_STR, "%Y-%m-%d").date()
    logger.info(f"Using start date for Gazette issues: {effective_start_date.strftime('%Y-%m-%d')}")


    effective_end_date = None
    if args.end_date:
        try:
            effective_end_date = datetime.strptime(args.end_date, "%Y-%m-%d").date()
        except ValueError:
            logger.error(f"Invalid --end_date format: {args.end_date}. Please use YYYY-MM-DD. Exiting.")
            return
    else:
        effective_end_date = date.today()
    logger.info(f"Using end date for Gazette issues: {effective_end_date.strftime('%Y-%m-%d')}")


    if effective_start_date > effective_end_date:
        logger.error(f"Error: Start date ({effective_start_date.strftime('%Y-%m-%d')}) cannot be after end date ({effective_end_date.strftime('%Y-%m-%d')}). Exiting.")
        return

    fetch_and_process_gazette_issues(db, args.dry_run, effective_start_date, effective_end_date, args.output_to_json, args.json_output_dir)

if __name__ == "__main__":
    main() 