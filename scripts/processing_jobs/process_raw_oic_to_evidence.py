"""
Processes raw Orders in Council (OICs) from Firestore, uses a Gemini LLM for analysis,
and creates structured evidence_items.

CLI arguments:
--dry_run: If True, do not write to Firestore but still call Gemini and log/store outputs. Default: False
--log_level: Set the logging level. Default: INFO
--

Next steps to make ready for production:
- add check for last run date in Firestore and only process items that are newer than that
- update firestore collection to write to evidence_items instead of evidence_items_test
- add any changes or config to run with docker
- schedule cron job run hourly after the ingestion job runs
"""
import os
import logging
import json
from datetime import datetime, timezone, date
from dotenv import load_dotenv
import firebase_admin
from firebase_admin import credentials, firestore
import asyncio
import time
import argparse
from google import genai
import traceback
import hashlib
import re

# --- Configuration ---
load_dotenv()

# --- Logger Setup ---
logging.basicConfig(level=logging.INFO,
                    format='%(asctime)s - %(levelname)s - %(filename)s:%(lineno)d - %(message)s',
                    datefmt='%Y-%m-%d %H:%M:%S')
logger = logging.getLogger("process_raw_oic_to_evidence")
# --- End Logger Setup ---

# --- Constants ---
RAW_OIC_COLLECTION = "raw_orders_in_council"
EVIDENCE_ITEMS_COLLECTION = "evidence_items_test" # Target evidence collection
DEPARTMENT_CONFIG_COLLECTION = "department_config"
DEFAULT_JSON_OUTPUT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'JSON_outputs', 'oic_processing')
PROMPT_FILE_PATH = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', 'prompts', 'prompt_oic_evidence.md'))
DEFAULT_START_DATE_STR = "2024-01-01" # Sensible default for OICs
# --- End Constants ---

# --- Firebase Configuration ---
db = None
if not firebase_admin._apps:
    try:
        firebase_admin.initialize_app()
        db = firestore.client()
        logger.info(f"Connected to CLOUD Firestore (Project: {os.getenv('FIREBASE_PROJECT_ID', 'Default')}) using default credentials.")
    except Exception as e_default:
        logger.warning(f"Cloud Firestore init with default creds failed: {e_default}. Attempting service account.")
        cred_path = os.getenv('FIREBASE_SERVICE_ACCOUNT_KEY_PATH')
        if cred_path:
            try:
                cred = credentials.Certificate(cred_path)
                app_name = f'process_oic_app_{int(time.time())}'
                firebase_admin.initialize_app(cred, name=app_name)
                db = firestore.client(app=firebase_admin.get_app(name=app_name))
                logger.info(f"Connected to CLOUD Firestore (Project: {os.getenv('FIREBASE_PROJECT_ID', 'Default')}) via service account.")
            except Exception as e_sa:
                logger.critical(f"Firebase init with service account key from {cred_path} failed: {e_sa}", exc_info=True)
        else:
            logger.warning("FIREBASE_SERVICE_ACCOUNT_KEY_PATH environment variable not set, and default creds failed.")
if db is None:
    logger.critical("CRITICAL: Failed to obtain Firestore client. Exiting.")
    exit("Exiting: Firestore client not available.")
# --- End Firebase Configuration ---

# --- Gemini Configuration ---
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
if not GEMINI_API_KEY:
    logger.critical("GEMINI_API_KEY not found in environment variables or .env file.")
    exit("Exiting: Missing GEMINI_API_KEY.")

if "GOOGLE_API_KEY" not in os.environ and GEMINI_API_KEY:
    os.environ["GOOGLE_API_KEY"] = GEMINI_API_KEY
    logger.info("Set GOOGLE_API_KEY environment variable from GEMINI_API_KEY.")

LLM_MODEL_NAME = os.getenv("GEMINI_MODEL_NAME_OIC_PROCESSING", "models/gemini-2.5-flash-preview-05-20") # Changed from gemini-pro

GENERATION_CONFIG_DICT = {
    "temperature": 0.3,
    "top_p": 0.95,
    "top_k": 64,
    "max_output_tokens": 8192, # Adjusted based on typical model limits, was 65536, flash might be 8k
    "response_mime_type": "application/json",
}

client = None
try:
    client = genai.Client() # Using the unified client
    logger.info(f"Successfully initialized Gemini Client. Model {LLM_MODEL_NAME} will be used at call time.")
except Exception as e:
    logger.critical(f"Failed to initialize Gemini client: {e}", exc_info=True)
    exit("Exiting: Gemini client initialization failed.")
# --- End Gemini Configuration ---

_department_configs_cache = None
_parliament_sessions_cache = None

# --- Helper Functions ---
def clean_json_from_markdown(text_blob: str) -> str:
    regex_pattern = r"```(?:json)?\s*([\s\S]+?)\s*```"
    match = re.search(regex_pattern, text_blob)
    if match:
        return match.group(1).strip()
    return text_blob.strip()

async def call_gemini_llm(prompt_text):
    if not client:
        logger.critical("Gemini client not initialized. Cannot call LLM.")
        return None, LLM_MODEL_NAME
    try:
        # Corrected to use the client.generate_content_async for the unified client
        # Assuming client.generate_content_async is the correct async method for the unified client.
        # If using an older specific `GenerativeModel` instance, it would be `model.generate_content_async`.
        response = await client.aio.models.generate_content( # Changed to use .models.generate_content
            model=LLM_MODEL_NAME, # Pass model name here
            contents=[prompt_text],
            # generation_config=GENERATION_CONFIG_DICT # Temporarily commenting out as client.aio.models.generate_content might not take it directly
        )
        raw_response_text = response.text
        json_str = clean_json_from_markdown(raw_response_text)
        parsed_result = json.loads(json_str)
        return parsed_result, LLM_MODEL_NAME
    except json.JSONDecodeError as json_err:
        logger.error(f"LLM response was not valid JSON. Error: {json_err}. Raw: {raw_response_text[:500] if 'raw_response_text' in locals() else ''}", exc_info=True)
        return None, LLM_MODEL_NAME
    except Exception as e:
        # Check if the error is related to candidate.text access
        if "text not found" in str(e).lower() or (hasattr(e, 'message') and "text not found" in e.message.lower()):
             logger.error(f"Error calling Gemini LLM ({LLM_MODEL_NAME}): Content has no text. Possible safety block or empty response. Full response: {response if 'response' in locals() else 'N/A'}", exc_info=True)
        else:
            logger.error(f"Error calling Gemini LLM ({LLM_MODEL_NAME}): {e}\n{traceback.format_exc()}", exc_info=True)
        return None, LLM_MODEL_NAME

def load_gemini_prompt_template(prompt_file: str) -> str:
    try:
        with open(prompt_file, 'r', encoding='utf-8') as f:
            return f.read()
    except Exception as e:
        logger.critical(f"Could not load Gemini prompt template from {prompt_file}: {e}")
        raise

def build_oic_gemini_prompt(raw_oic_data, prompt_template: str) -> str:
    oic_date_obj = raw_oic_data.get('oic_date')
    oic_date_str = oic_date_obj.isoformat() if isinstance(oic_date_obj, datetime) else str(oic_date_obj or '')
    
    full_text = raw_oic_data.get('full_text_scraped', '')
    # Simple truncation for the prompt if text is too long
    # A more sophisticated approach might summarize it first if consistently very large.
    MAX_FULL_TEXT_LEN_FOR_PROMPT = 30000 # Adjust as needed based on typical OIC sizes and model context window
    if len(full_text) > MAX_FULL_TEXT_LEN_FOR_PROMPT:
        full_text_snippet = full_text[:MAX_FULL_TEXT_LEN_FOR_PROMPT] + "... [TRUNCATED]"
    else:
        full_text_snippet = full_text

    return prompt_template.format(
        oic_number_full_raw=raw_oic_data.get('oic_number_full_raw', ''),
        oic_date=oic_date_str,
        title_or_summary_raw=raw_oic_data.get('title_or_summary_raw', '')[:2000], # Snippet for safety
        responsible_department_raw=raw_oic_data.get('responsible_department_raw', ''),
        act_citation_raw=raw_oic_data.get('act_citation_raw', ''),
        full_text_scraped=full_text_snippet, # Pass potentially truncated full text
        parliament_session_id=raw_oic_data.get('parliament_session_id_assigned', '')
    )

def standardize_department_name(raw_dept_name, db_client_for_cache):
    global _department_configs_cache
    if not raw_dept_name: return None
    if _department_configs_cache is None:
        _department_configs_cache = {}
        if db_client_for_cache:
            try:
                logger.info("Populating department_config cache for standardization...")
                for doc in db_client_for_cache.collection(DEPARTMENT_CONFIG_COLLECTION).stream():
                    _department_configs_cache[doc.id] = doc.to_dict()
                if not _department_configs_cache: logger.warning("Department configs cache is empty after fetch attempt.")
                else: logger.info(f"Cached {len(_department_configs_cache)} department configurations.")
            except Exception as e:
                logger.error(f"Error fetching department_config for caching: {e}", exc_info=True)
                # Proceed without cache, will return raw_dept_name
        else:
            logger.warning("DB client not available for department_config caching.")
            return raw_dept_name # Cannot standardize without DB access for cache
            
    for config_id, config_data in _department_configs_cache.items():
        # Ensure keys exist and are of expected types before lowercasing or comparing
        config_name = config_data.get("name")
        if isinstance(config_name, str) and raw_dept_name.lower() == config_name.lower():
            return config_name
        
        name_variations = config_data.get("name_variations_all")
        if isinstance(name_variations, list):
            if any(isinstance(var, str) and raw_dept_name.lower() == var.lower() for var in name_variations):
                return config_name # Return the standardized name from 'name' field
                
    logger.debug(f"Could not standardize department: '{raw_dept_name}'. Using raw name.")
    return raw_dept_name

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
                elif sed is not None:
                    logger.warning(f"Session {session_doc.id} has non-datetime session_end_date. Treating as None.")
                    session_data['session_end_date'] = None
                else:
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
# --- End Helper Functions ---

# --- Main Processing Logic ---
async def process_pending_raw_oics(db_client, dry_run=False, output_to_json=False, json_output_dir=None, 
                                 force_reprocessing=False, start_date_filter_dt=None, end_date_filter_dt=None, limit=None):
    prompt_template = load_gemini_prompt_template(PROMPT_FILE_PATH)
    logger.info(f"Starting raw OIC processing. Dry run: {dry_run}, JSON: {output_to_json}, Force: {force_reprocessing}, Limit: {limit or 'All'}")
    if start_date_filter_dt and end_date_filter_dt:
        logger.info(f"Date filter: From {start_date_filter_dt.strftime('%Y-%m-%d')} to {end_date_filter_dt.strftime('%Y-%m-%d')}")
    
    processed_count = 0
    skipped_low_score_count = 0
    error_count = 0
    evidence_created_count = 0
    all_outputs_for_json = []

    if output_to_json:
        os.makedirs(json_output_dir, exist_ok=True)

    try:
        query = db_client.collection(RAW_OIC_COLLECTION)

        if start_date_filter_dt:
            start_datetime_utc = datetime.combine(start_date_filter_dt, datetime.min.time(), tzinfo=timezone.utc)
            query = query.where(filter=firestore.FieldFilter("oic_date", ">=", start_datetime_utc))
        if end_date_filter_dt:
            end_datetime_utc = datetime.combine(end_date_filter_dt, datetime.max.time(), tzinfo=timezone.utc)
            query = query.where(filter=firestore.FieldFilter("oic_date", "<=", end_datetime_utc))

        if force_reprocessing:
            logger.info("Force reprocessing enabled. Processing all items in date range (if specified, else all).")
        else:
            logger.info("Querying for 'pending_evidence_creation' items.")
            query = query.where(filter=firestore.FieldFilter("evidence_processing_status", "==", "pending_evidence_creation"))
        
        if limit:
            query = query.limit(limit)
            logger.info(f"Applying limit of {limit} records to the query.")

        pending_oic_docs = list(query.stream())

        if not pending_oic_docs:
            logger.info("No pending raw OICs found matching criteria.")
            return
        logger.info(f"Found {len(pending_oic_docs)} raw OICs to process.")

        for raw_oic_doc_snapshot in pending_oic_docs:
            raw_oic_data = raw_oic_doc_snapshot.to_dict()
            raw_oic_id = raw_oic_doc_snapshot.id # This is the normalized OIC number

            # Ensure parliament_session_id is determined or confirmed here
            oic_date_for_session = raw_oic_data.get('oic_date')
            if isinstance(oic_date_for_session, str): # Convert if string
                try: oic_date_for_session = datetime.fromisoformat(oic_date_for_session.replace('Z', '+00:00'))
                except ValueError: oic_date_for_session = None
            
            current_parliament_session_id = raw_oic_data.get('parliament_session_id_assigned')
            if not current_parliament_session_id and oic_date_for_session: # If not assigned, try to get it
                current_parliament_session_id = get_parliament_session_id(db_client, oic_date_for_session)
                if current_parliament_session_id: # If found, update raw_oic_data for prompt building
                    raw_oic_data['parliament_session_id_assigned'] = current_parliament_session_id
            # If still no session ID, it will be None or empty in the prompt

            logger.info(f"Processing raw OIC: {raw_oic_id} - Title: {raw_oic_data.get('title_or_summary_raw', '')[:50]}...")
            processed_count += 1

            try:
                if not raw_oic_data.get("title_or_summary_raw") or not raw_oic_data.get("oic_date") or not raw_oic_data.get("source_url_oic_detail_page"):
                    logger.error(f"Skipping OIC {raw_oic_id} due to missing critical fields (title, date, or source URL).")
                    if not dry_run:
                        raw_oic_doc_snapshot.reference.update({
                            "evidence_processing_status": "error_missing_fields", 
                            "processed_at": firestore.SERVER_TIMESTAMP,
                            "llm_model_name_last_attempt": LLM_MODEL_NAME # Generic model name for this type of error
                        })
                    error_count +=1
                    continue

                llm_prompt = build_oic_gemini_prompt(raw_oic_data, prompt_template)
                gemini_result_dict, model_name_from_call = await call_gemini_llm(llm_prompt)

                if not gemini_result_dict:
                    logger.error(f"LLM analysis failed for OIC {raw_oic_id} (Model: {model_name_from_call}).")
                    if not dry_run:
                        raw_oic_doc_snapshot.reference.update({
                            "evidence_processing_status": "error_llm_processing", 
                            "processed_at": firestore.SERVER_TIMESTAMP,
                            "llm_model_name_last_attempt": model_name_from_call
                        })
                    error_count +=1
                    continue

                timeline_summary = gemini_result_dict.get("timeline_summary", "")
                potential_relevance_score = gemini_result_dict.get("potential_relevance_score", "Low")
                key_concepts_llm = gemini_result_dict.get("key_concepts", [])
                sponsoring_dept_llm = gemini_result_dict.get("sponsoring_department_standardized", "")
                one_sentence_desc_llm = gemini_result_dict.get("one_sentence_description", "")

                if not timeline_summary:
                    logger.error(f"LLM result for OIC {raw_oic_id} missing timeline_summary (Model: {model_name_from_call}).")
                    # Handle as error, update status in Firestore
                    if not dry_run:
                        raw_oic_doc_snapshot.reference.update({
                            "evidence_processing_status": "error_llm_missing_summary",
                            "processed_at": firestore.SERVER_TIMESTAMP,
                            "llm_model_name_last_attempt": model_name_from_call
                        })
                    error_count += 1
                    continue
                
                if potential_relevance_score.lower() == "low":
                    logger.info(f"Skipping OIC {raw_oic_id} due to low relevance score ('{potential_relevance_score}') from LLM (Model: {model_name_from_call}).")
                    if not dry_run:
                        raw_oic_doc_snapshot.reference.update({
                            "evidence_processing_status": "skipped_low_relevance_score", # Changed from skipped_irrelevant_low_score
                            "processed_at": firestore.SERVER_TIMESTAMP,
                            "llm_model_name_last_attempt": model_name_from_call
                        })
                    skipped_low_score_count += 1
                    continue
                
                oic_pub_date_obj = raw_oic_data.get('oic_date') # Should be datetime from Firestore or parsed earlier
                if isinstance(oic_pub_date_obj, str): # Double check and parse if still string
                    try: oic_pub_date_obj = datetime.fromisoformat(oic_pub_date_obj.replace('Z', '+00:00'))
                    except ValueError: oic_pub_date_obj = None
                
                pub_date_str_for_id = oic_pub_date_obj.strftime('%Y%m%d') if oic_pub_date_obj else 'unknown'
                session_id_str_for_id = current_parliament_session_id or "unknown" # Use the determined session ID
                
                # Ensure raw_oic_id itself is used for hash if it's the normalized OIC number like '2024-0123'
                # Using source URL for more uniqueness if multiple OICs have same number (unlikely but possible)
                hash_input = f"{raw_oic_data.get('source_url_oic_detail_page', raw_oic_id)}_{pub_date_str_for_id}"
                short_hash = hashlib.sha256(hash_input.encode('utf-8')).hexdigest()[:10]
                evidence_id = f"{pub_date_str_for_id}_{session_id_str_for_id}_OIC_{short_hash}"

                linked_departments = []
                dept_to_standardize = sponsoring_dept_llm if sponsoring_dept_llm else raw_oic_data.get("responsible_department_raw")
                if dept_to_standardize:
                    std_dept_name = standardize_department_name(dept_to_standardize, db_client)
                    if std_dept_name: linked_departments.append(std_dept_name)
                
                evidence_item_data = {
                    "evidence_id": evidence_id,
                    "promise_ids": [], # To be linked later
                    "evidence_source_type": "OrderInCouncil (PCO)", 
                    "evidence_date": oic_pub_date_obj, 
                    "title_or_summary": timeline_summary, # From LLM, summary_generated_by_llm
                    "description_or_details": one_sentence_desc_llm, # From LLM, description_generated_by_llm
                    "source_url": raw_oic_data.get("source_url_oic_detail_page"),
                    "source_document_raw_id": raw_oic_id, # Normalized OIC number
                    "linked_departments": linked_departments or None, # Use standardized name
                    "parliament_session_id": current_parliament_session_id, # Use the determined session ID
                    "ingested_at": datetime.now(timezone.utc), 
                    "potential_relevance_score": potential_relevance_score, # From LLM, relevance_score_generated_by_llm
                    "key_concepts": key_concepts_llm, # From LLM, key_concepts_generated_by_llm
                    "additional_metadata": {
                        "raw_oic_document_id": raw_oic_id, # The ID of the raw OIC doc in its collection
                        "attach_id": raw_oic_data.get("attach_id")
                    },
                    "promise_linking_status": "pending",
                }
                
                if output_to_json:
                    json_compatible_doc = evidence_item_data.copy()
                    for key, value in json_compatible_doc.items():
                        if isinstance(value, datetime): json_compatible_doc[key] = value.isoformat()
                    if 'additional_metadata' in json_compatible_doc and isinstance(json_compatible_doc['additional_metadata'], dict):
                         for k_am, v_am in json_compatible_doc['additional_metadata'].items():
                            if isinstance(v_am, datetime): json_compatible_doc['additional_metadata'][k_am] = v_am.isoformat()
                    all_outputs_for_json.append(json_compatible_doc)
                    logger.info(f"Prepared for JSON: evidence {evidence_id} from raw OIC {raw_oic_id}")

                if not dry_run:
                    db_client.collection(EVIDENCE_ITEMS_COLLECTION).document(evidence_id).set(evidence_item_data)
                    logger.info(f"CREATED evidence item {evidence_id} from raw OIC {raw_oic_id}.")
                    raw_oic_doc_snapshot.reference.update({
                        "evidence_processing_status": "evidence_created",
                        "related_evidence_item_id": evidence_id,
                        "processed_at": firestore.SERVER_TIMESTAMP,
                        "llm_model_name_last_attempt": model_name_from_call,
                        # Update parliament_session_id_assigned if it was newly determined
                        "parliament_session_id_assigned": current_parliament_session_id 
                    })
                else: 
                    logger.info(f"[DRY RUN] Would create evidence item {evidence_id} from raw OIC {raw_oic_id}.")
                    # For dry run, ensure datetimes are serializable for logging if printing the whole dict
                    dry_run_log_data = {k: (v.isoformat() if isinstance(v, datetime) else str(v)) for k, v in evidence_item_data.items()}
                    logger.debug(f"[DRY RUN] Evidence data: {json.dumps(dry_run_log_data, indent=2)}")
                    logger.info(f"[DRY RUN] Would update raw OIC {raw_oic_id} to 'evidence_created' and set related_evidence_item_id.")
                evidence_created_count +=1
            
            except Exception as e_inner:
                logger.error(f"Error processing raw OIC {raw_oic_id}: {e_inner}", exc_info=True)
                error_count += 1
                model_name_at_error = model_name_from_call if 'model_name_from_call' in locals() else LLM_MODEL_NAME
                if not dry_run:
                    try:
                        raw_oic_doc_snapshot.reference.update({
                            "evidence_processing_status": "error_processing_script",
                            "processing_error_message": str(e_inner),
                            "processed_at": firestore.SERVER_TIMESTAMP,
                            "llm_model_name_last_attempt": model_name_at_error
                        })
                    except Exception as update_err:
                        logger.error(f"Failed to mark raw OIC {raw_oic_id} as error_processing_script: {update_err}")
                continue 
    
    except Exception as e_outer:
        logger.error(f"Major error in process_pending_raw_oics query or stream setup: {e_outer}", exc_info=True)
        # This is a more catastrophic error, might indicate issues with Firestore connection or query itself.

    if output_to_json and all_outputs_for_json:
        try:
            ts = datetime.now().strftime("%Y%m%d_%H%M%S")
            fn = os.path.join(json_output_dir, f"processed_oic_evidence_{ts}.json")
            with open(fn, 'w', encoding='utf-8') as f:
                json.dump(all_outputs_for_json, f, indent=4, ensure_ascii=False, default=str) # Add default=str for any unhandled types
            logger.info(f"Wrote {len(all_outputs_for_json)} processed OIC evidence items to JSON: {fn}")
        except Exception as e_json:
            logger.error(f"Error writing OIC evidence items to JSON: {e_json}", exc_info=True)

    logger.info(f"OIC Processing finished. Attempted: {processed_count}, Created: {evidence_created_count}, Skipped (Low Score): {skipped_low_score_count}, Errors: {error_count}")
# --- End Main Processing Logic ---


# --- CLI --- 
async def main():
    parser = argparse.ArgumentParser(description="Process raw Orders in Council (OICs) into evidence items using LLM analysis.")
    parser.add_argument("--dry_run", action="store_true", help="Dry run, no Firestore writes.")
    parser.add_argument("--log_level", type=str, default="INFO", choices=['DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL'])
    parser.add_argument("--JSON", dest="output_to_json", action="store_true", help="Output to JSON instead of Firestore.")
    parser.add_argument("--json_output_dir", type=str, default=DEFAULT_JSON_OUTPUT_DIR)
    parser.add_argument("--force_reprocessing", action="store_true", help="Reprocess items in date range, ignoring current status.")
    parser.add_argument("--start_date", type=str, default=DEFAULT_START_DATE_STR, help=f"Start date for OIC oic_date (YYYY-MM-DD). Default: {DEFAULT_START_DATE_STR}")
    parser.add_argument("--end_date", type=str, help="End date for OIC oic_date (YYYY-MM-DD). Default: today.")
    parser.add_argument("--limit", type=int, default=None, help="Optional: Max number of OICs to process. Processes all matching if not set.")
    args = parser.parse_args()

    logger.setLevel(getattr(logging, args.log_level.upper()))

    try:
        start_date_dt = datetime.strptime(args.start_date, "%Y-%m-%d").date()
    except ValueError:
        logger.error(f"Invalid start_date format: {args.start_date}. Please use YYYY-MM-DD. Exiting.")
        return
    end_date_dt = datetime.strptime(args.end_date, "%Y-%m-%d").date() if args.end_date else date.today()
    if start_date_dt > end_date_dt:
        logger.error(f"Start date {start_date_dt.strftime('%Y-%m-%d')} cannot be after end date {end_date_dt.strftime('%Y-%m-%d')}. Exiting.")
        return

    if args.dry_run: logger.info("*** DRY RUN MODE ENABLED ***")
    if args.output_to_json: logger.info(f"*** JSON OUTPUT ENABLED to {args.json_output_dir} ***")
    if args.force_reprocessing: logger.info("*** FORCE REPROCESSING ENABLED ***")

    # Pre-warm caches if db client is available
    if db:
        logger.info("Pre-warming department and parliament session caches...")
        standardize_department_name("Test Department", db) # Call to trigger cache load for departments
        get_parliament_session_id(db, datetime.now(timezone.utc)) # Call to trigger cache load for sessions
        logger.info("Caches pre-warmed (or attempted).")
    else:
        logger.warning("DB client not available, cannot pre-warm caches. Standardization/session ID assignment may be affected if not using JSON mode.")

    await process_pending_raw_oics(db, 
                                   dry_run=args.dry_run, 
                                   output_to_json=args.output_to_json, 
                                   json_output_dir=args.json_output_dir, 
                                   force_reprocessing=args.force_reprocessing,
                                   start_date_filter_dt=start_date_dt,
                                   end_date_filter_dt=end_date_dt,
                                   limit=args.limit)
    logger.info("--- Raw OIC to Evidence Processing Script Finished ---")

if __name__ == "__main__":
    asyncio.run(main()) 