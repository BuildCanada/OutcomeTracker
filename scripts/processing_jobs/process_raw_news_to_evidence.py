"""
Processes raw news items from Firestore, uses an LLM for analysis,
and creates structured evidence items.
"""
import os
import logging
import uuid
import json
from datetime import datetime, timezone, date # Added date
from dotenv import load_dotenv
import firebase_admin # For Firestore connection
from firebase_admin import credentials, firestore # For Firestore connection
import asyncio # For potential async LLM calls
import time # For unique app name fallback in Firebase init
import argparse # For CLI arguments
import google.generativeai as genai # For Gemini LLM
import traceback # For detailed error logging
import hashlib # For generating deterministic IDs
import re # For cleaning LLM output


# --- Configuration ---
load_dotenv()
# --- Logger Setup ---
logging.basicConfig(level=logging.INFO,
                    format='%(asctime)s - %(levelname)s - %(filename)s:%(lineno)d - %(message)s',
                    datefmt='%Y-%m-%d %H:%M:%S')
logger = logging.getLogger("process_raw_news_to_evidence")
# --- End Logger Setup ---

# --- Constants ---
RAW_NEWS_RELEASES_COLLECTION = "raw_news_releases"
EVIDENCE_ITEMS_COLLECTION = "evidence_items_test" # Using test collection
DEPARTMENT_CONFIG_COLLECTION = "department_config" # For standardizing department names
DEFAULT_JSON_OUTPUT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'JSON_outputs', 'news_processing')
PROMPT_FILE_PATH = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', 'prompts', 'prompt_news_evidence.md'))
DEFAULT_START_DATE_STR = "2025-03-23" # Default start date for processing
# --- End Constants ---


# --- Gemini Configuration ---
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
if not GEMINI_API_KEY:
    logger.critical("GEMINI_API_KEY not found in environment variables or .env file.")
    exit("Exiting: Missing GEMINI_API_KEY.")

genai.configure(api_key=GEMINI_API_KEY)
LLM_MODEL_NAME = os.getenv("GEMINI_MODEL_NAME_NEWS_PROCESSING", "models/gemini-1.5-flash-latest")
GENERATION_CONFIG_DICT = {
    "temperature": 0.3,
    "top_p": 0.95,
    "top_k": 64,
    "max_output_tokens": 8192,
    "response_mime_type": "application/json",
}
llm_model = None
try:
    llm_model = genai.GenerativeModel(LLM_MODEL_NAME)
    logger.info(f"Successfully initialized Gemini Model: {LLM_MODEL_NAME}.")
except Exception as e:
    logger.critical(f"Failed to initialize Gemini model '{LLM_MODEL_NAME}': {e}", exc_info=True)
    exit(f"Exiting: Gemini model '{LLM_MODEL_NAME}' initialization failed.")
# --- End Gemini Configuration ---


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
                app_name = f'process_news_app_{int(time.time())}'
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

_department_configs_cache = None # For standardizing department names
_parliament_sessions_cache = None # For parliament session ID lookups

# --- Helper Functions ---
def clean_json_from_markdown(text_blob: str) -> str:
    regex_pattern = r"```(?:json)?\s*([\s\S]+?)\s*```"
    match = re.search(regex_pattern, text_blob)
    if match:
        return match.group(1).strip()
    return text_blob.strip()

async def call_gemini_llm(prompt_text, model_to_call=None):
    current_model = model_to_call or llm_model
    model_name_for_return = "unknown_model"

    if not current_model:
        logger.critical("Gemini model not initialized. Cannot call LLM.")
        return None, None # Return None for result and model name
    
    model_name_for_return = current_model.model_name if hasattr(current_model, 'model_name') else "unknown_model_instance"

    try:
        response = await current_model.generate_content_async(
            contents=[prompt_text],
            generation_config=genai.types.GenerationConfig(**GENERATION_CONFIG_DICT)
        )
        raw_response_text = response.text
        json_str = clean_json_from_markdown(raw_response_text)
        parsed_result = json.loads(json_str)
        # No need to add model_name_used here; it's returned separately
        return parsed_result, model_name_for_return
    except json.JSONDecodeError as json_err:
        logger.error(f"LLM response was not valid JSON. Error: {json_err}. Raw: {raw_response_text[:500] if 'raw_response_text' in locals() else ''}", exc_info=True)
        return None, model_name_for_return
    except Exception as e:
        logger.error(f"Error calling Gemini LLM ({model_name_for_return}): {e}\n{traceback.format_exc()}", exc_info=True)
        return None, model_name_for_return

def load_gemini_prompt_template(prompt_file: str) -> str:
    try:
        with open(prompt_file, 'r') as f:
            return f.read()
    except Exception as e:
        logger.critical(f"Could not load Gemini prompt template from {prompt_file}: {e}")
        raise

def build_news_gemini_prompt(raw_item_data, prompt_template: str) -> str:
    pub_date = raw_item_data.get('publication_date')
    pub_date_str = pub_date.isoformat() if isinstance(pub_date, datetime) else str(pub_date or '')
    return prompt_template.format(
        news_title=raw_item_data.get('title_raw', ''),
        news_summary_snippet=raw_item_data.get('summary_or_snippet_raw', '')[:2000],
        publication_date=pub_date_str,
        parliament_session_id=raw_item_data.get('parliament_session_id_assigned', '')
    )

def standardize_department_name(raw_dept_name):
    global _department_configs_cache
    if not raw_dept_name: return None
    if _department_configs_cache is None:
        _department_configs_cache = {}
        try:
            for doc in db.collection(DEPARTMENT_CONFIG_COLLECTION).stream():
                _department_configs_cache[doc.id] = doc.to_dict()
            if not _department_configs_cache: logger.warning("Dept configs cache empty.")
        except Exception as e:
            logger.error(f"Error fetching department_config for caching: {e}", exc_info=True)
            return raw_dept_name
    for config in _department_configs_cache.values():
        if isinstance(config.get("name"), str) and raw_dept_name.lower() == config["name"].lower(): return config["name"]
        if isinstance(config.get("name_variations_all"), list):
            if any(isinstance(var, str) and raw_dept_name.lower() == var.lower() for var in config["name_variations_all"]):
                return config["name"]
    logger.debug(f"Could not standardize department: '{raw_dept_name}'. Using raw.")
    return raw_dept_name

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
    
    if publication_date_dt is None:
        logger.warning("get_parliament_session_id: publication_date_dt is None. Cannot determine session. Returning None.")
        return None

    # Ensure publication_date_dt is timezone-aware (assume UTC if naive, consistent with Firestore)
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
                session_data['id'] = session_doc.id # Store document ID as session_id
                
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
                    session_data['session_end_date'] = None # Explicitly set to None if missing or None

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
    
    logger.warning(f"No matching parliament session found for publication date: {publication_date_dt_utc.strftime('%Y-%m-%d')}. Review cache and date.")
    return None

# --- End Helper Functions ---


# --- Main Processing Logic ---
async def process_pending_raw_news(db_client, dry_run=False, output_to_json=False, json_output_dir=None, force_reprocessing=False, start_date_filter_dt=None, end_date_filter_dt=None, limit=None):
    prompt_template = load_gemini_prompt_template(PROMPT_FILE_PATH)
    logger.info(f"Starting raw news processing. Dry run: {dry_run}, JSON: {output_to_json}, Force: {force_reprocessing}, Limit: {limit or 'All'}")
    logger.info(f"Date filter: From {start_date_filter_dt.strftime('%Y-%m-%d')} to {end_date_filter_dt.strftime('%Y-%m-%d')}")
    
    processed_count = 0
    skipped_low_score_count = 0
    error_count = 0
    evidence_created_count = 0
    all_outputs_for_json = []

    if output_to_json:
        os.makedirs(json_output_dir, exist_ok=True)

    try:
        query = db_client.collection(RAW_NEWS_RELEASES_COLLECTION)

        start_datetime_utc = datetime.combine(start_date_filter_dt, datetime.min.time(), tzinfo=timezone.utc)
        end_datetime_utc = datetime.combine(end_date_filter_dt, datetime.max.time(), tzinfo=timezone.utc)
        query = query.where("publication_date", ">=", start_datetime_utc)
        query = query.where("publication_date", "<=", end_datetime_utc)

        if force_reprocessing:
            logger.info("Force reprocessing enabled. Processing all items in date range.")
        else:
            logger.info("Querying for 'pending_evidence_creation' items in date range.")
            query = query.where("evidence_processing_status", "==", "pending_evidence_creation")
        
        if limit:
            query = query.limit(limit)
            logger.info(f"Applying limit of {limit} records to the query.")

        pending_item_docs = list(query.stream())

        if not pending_item_docs:
            logger.info("No pending raw news items found matching criteria.")
            return
        logger.info(f"Found {len(pending_item_docs)} raw news items to process.")

        for raw_item_doc_snapshot in pending_item_docs:
            raw_item_data = raw_item_doc_snapshot.to_dict()
            raw_item_id = raw_item_doc_snapshot.id
            model_used_for_call = llm_model.model_name # Default model, might be updated if LLM call fails early

            # Get publication date for session ID lookup
            pub_date_obj_for_session = raw_item_data.get('publication_date')
            # Ensure pub_date_obj_for_session is a datetime object if it's a string
            if isinstance(pub_date_obj_for_session, str):
                try: 
                    pub_date_obj_for_session = datetime.fromisoformat(pub_date_obj_for_session.replace('Z', '+00:00'))
                except ValueError: 
                    try: pub_date_obj_for_session = datetime.strptime(pub_date_obj_for_session, "%Y-%m-%d")
                    except ValueError: pub_date_obj_for_session = None
            
            # Determine parliament_session_id dynamically
            calculated_parliament_session_id = get_parliament_session_id(db_client, pub_date_obj_for_session)
            if not calculated_parliament_session_id:
                logger.warning(f"Could not determine parliament session ID for item {raw_item_id} with pub date {pub_date_obj_for_session}. Will use existing or None.")
                calculated_parliament_session_id = raw_item_data.get('parliament_session_id_assigned') # Fallback

            if not force_reprocessing and raw_item_data.get("evidence_processing_status") != "pending_evidence_creation":
                logger.info(f"Item {raw_item_id} status is '{raw_item_data.get('evidence_processing_status')}'. Skipping.")
                continue
            logger.info(f"Processing raw news item: {raw_item_id} - {raw_item_data.get('title_raw', '')}")
            processed_count +=1

            try:
                if not raw_item_data.get("title_raw") or not raw_item_data.get("publication_date") or not raw_item_data.get("source_url"):
                    logger.error(f"Skipping item {raw_item_id} due to missing critical fields.")
                    if not dry_run:
                        await asyncio.to_thread(db_client.collection(RAW_NEWS_RELEASES_COLLECTION).document(raw_item_id).update, {
                            "evidence_processing_status": "error_missing_fields", 
                            "last_updated_at": firestore.SERVER_TIMESTAMP,
                            "llm_model_name_last_attempt": model_used_for_call
                        })
                    error_count +=1
                    continue

                llm_prompt = build_news_gemini_prompt(raw_item_data, prompt_template)
                # Modify the prompt build to use the dynamically determined session ID
                # First, create a mutable copy of raw_item_data or ensure build_news_gemini_prompt can take it directly
                prompt_input_data = raw_item_data.copy()
                prompt_input_data['parliament_session_id_assigned'] = calculated_parliament_session_id # Override for prompt
                llm_prompt = build_news_gemini_prompt(prompt_input_data, prompt_template)

                gemini_result_dict, model_used_for_call = await call_gemini_llm(llm_prompt)

                if not gemini_result_dict:
                    logger.error(f"LLM analysis failed for {raw_item_id} (Model: {model_used_for_call}).")
                    if not dry_run:
                         await asyncio.to_thread(db_client.collection(RAW_NEWS_RELEASES_COLLECTION).document(raw_item_id).update, {
                            "evidence_processing_status": "error_llm_processing", 
                            "last_updated_at": firestore.SERVER_TIMESTAMP,
                            "llm_model_name_last_attempt": model_used_for_call
                        })
                    error_count +=1
                    continue

                timeline_summary = gemini_result_dict.get("timeline_summary", "")
                potential_relevance_score = gemini_result_dict.get("potential_relevance_score", "Low")
                key_concepts = gemini_result_dict.get("key_concepts", [])
                sponsoring_department_llm = gemini_result_dict.get("sponsoring_department_standardized", "")

                if not timeline_summary:
                    logger.error(f"LLM result for {raw_item_id} missing timeline_summary (Model: {model_used_for_call}).")
                    if not dry_run:
                        await asyncio.to_thread(db_client.collection(RAW_NEWS_RELEASES_COLLECTION).document(raw_item_id).update, {
                            "evidence_processing_status": "error_llm_missing_summary", 
                            "last_updated_at": firestore.SERVER_TIMESTAMP,
                            "llm_model_name_last_attempt": model_used_for_call
                        })
                    error_count += 1
                    continue

                if potential_relevance_score.lower() == "low":
                    logger.info(f"Skipping item {raw_item_id} due to low relevance score ('{potential_relevance_score}') (Model: {model_used_for_call}).")
                    if not dry_run:
                        await asyncio.to_thread(db_client.collection(RAW_NEWS_RELEASES_COLLECTION).document(raw_item_id).update, {
                            "evidence_processing_status": "skipped_low_relevance_score", 
                            "last_updated_at": firestore.SERVER_TIMESTAMP,
                            "llm_model_name_last_attempt": model_used_for_call 
                            # We are no longer storing the full llm_analysis_raw here
                        })
                    skipped_low_score_count += 1
                    continue
                
                pub_date_obj = raw_item_data.get('publication_date')
                if isinstance(pub_date_obj, str):
                    try: pub_date_obj = datetime.fromisoformat(pub_date_obj.replace('Z', '+00:00'))
                    except ValueError: 
                        try: pub_date_obj = datetime.strptime(pub_date_obj, "%Y-%m-%d")
                        except ValueError: pub_date_obj = None
                pub_date_str = pub_date_obj.strftime('%Y%m%d') if pub_date_obj else 'unknown'
                session_id_str = calculated_parliament_session_id or "unknown" # Use calculated session ID
                hash_input = f"{raw_item_data.get('source_url', '')}_{pub_date_str}"
                short_hash = hashlib.sha256(hash_input.encode('utf-8')).hexdigest()[:10]
                evidence_id = f"{pub_date_str}_{session_id_str}_News_{short_hash}"

                linked_departments = []
                dept_to_standardize = sponsoring_department_llm if sponsoring_department_llm else raw_item_data.get("department_rss")
                if dept_to_standardize:
                    std_dept_name = standardize_department_name(dept_to_standardize)
                    if std_dept_name: linked_departments.append(std_dept_name)
                
                evidence_item_data = {
                    "evidence_id": evidence_id, "promise_ids": [],
                    "evidence_source_type": "News Release (Canada.ca)", 
                    "evidence_date": pub_date_obj, 
                    "title_or_summary": timeline_summary, 
                    "description_or_details": raw_item_data.get("summary_or_snippet_raw", ""), 
                    "source_url": raw_item_data.get("source_url"),
                    "linked_departments": linked_departments or None,
                    "parliament_session_id": calculated_parliament_session_id, # Use calculated session ID
                    "ingested_at": datetime.now(timezone.utc), 
                    "potential_relevance_score": potential_relevance_score, 
                    "key_concepts": key_concepts, 
                    "additional_metadata": {
                        "raw_news_release_id": raw_item_id
                    },
                    "dev_linking_status": "pending"
                }
                
                if output_to_json:
                    json_compatible_doc = {k: (v.isoformat() if isinstance(v, datetime) else v) for k,v in evidence_item_data.items()}
                    if 'additional_metadata' in json_compatible_doc and isinstance(json_compatible_doc['additional_metadata'], dict) : # Ensure datetimes in metadata are also converted
                         for k_am, v_am in json_compatible_doc['additional_metadata'].items():
                            if isinstance(v_am, datetime): json_compatible_doc['additional_metadata'][k_am] = v_am.isoformat()
                    all_outputs_for_json.append(json_compatible_doc)
                    logger.info(f"Prepared for JSON: evidence {evidence_id} from raw {raw_item_id}")

                if not dry_run:
                    await asyncio.to_thread(db_client.collection(EVIDENCE_ITEMS_COLLECTION).document(evidence_id).set, evidence_item_data)
                    logger.info(f"CREATED evidence item {evidence_id} from raw item {raw_item_id}.")
                    await asyncio.to_thread(db_client.collection(RAW_NEWS_RELEASES_COLLECTION).document(raw_item_id).update, {
                        "evidence_processing_status": "evidence_created",
                        "related_evidence_item_id": evidence_id,
                        "last_updated_at": firestore.SERVER_TIMESTAMP,
                        "llm_model_name_last_attempt": model_used_for_call
                    })
                else: 
                    logger.info(f"[DRY RUN] Would create evidence item {evidence_id} from raw item {raw_item_id}.")
                    logger.debug(f"[DRY RUN] Evidence data: {json.dumps(evidence_item_data, default=str, indent=2)}")
                    logger.info(f"[DRY RUN] Would update raw news item {raw_item_id} to 'evidence_created'.")
                evidence_created_count +=1
            except Exception as e_inner:
                logger.error(f"Error processing raw news item {raw_item_id}: {e_inner}", exc_info=True)
                error_count += 1
                # model_used_for_call might not be set if error is very early
                model_name_at_error = model_used_for_call if 'model_used_for_call' in locals() else llm_model.model_name
                if not dry_run:
                    try:
                        await asyncio.to_thread(db_client.collection(RAW_NEWS_RELEASES_COLLECTION).document(raw_item_id).update, {
                            "evidence_processing_status": "error_processing_script",
                            "processing_error_message": str(e_inner),
                            "last_updated_at": firestore.SERVER_TIMESTAMP,
                            "llm_model_name_last_attempt": model_name_at_error
                        })
                    except Exception as update_err:
                        logger.error(f"Failed to mark item {raw_item_id} as error_processing: {update_err}")
                continue 
    except Exception as e_outer:
        logger.error(f"Major error in process_pending_raw_news query or stream setup: {e_outer}", exc_info=True)

    if output_to_json and all_outputs_for_json:
        try:
            ts = datetime.now().strftime("%Y%m%d_%H%M%S")
            fn = os.path.join(json_output_dir, f"processed_news_evidence_{ts}.json")
            with open(fn, 'w', encoding='utf-8') as f:
                json.dump(all_outputs_for_json, f, indent=4, ensure_ascii=False, default=str)
            logger.info(f"Wrote {len(all_outputs_for_json)} processed items to JSON: {fn}")
        except Exception as e_json:
            logger.error(f"Error writing to JSON: {e_json}", exc_info=True)

    logger.info(f"Processing finished. Attempted: {processed_count}, Created: {evidence_created_count}, Skipped (Low Score): {skipped_low_score_count}, Errors: {error_count}")
# --- End Main Processing Logic ---


# --- CLI ---
async def main():
    parser = argparse.ArgumentParser(description="Process raw news items into evidence items using LLM analysis.")
    parser.add_argument("--dry_run", action="store_true", help="Dry run, no Firestore writes.")
    parser.add_argument("--log_level", type=str, default="INFO", choices=['DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL'])
    parser.add_argument("--JSON", dest="output_to_json", action="store_true", help="Output to JSON instead of Firestore.")
    parser.add_argument("--json_output_dir", type=str, default=DEFAULT_JSON_OUTPUT_DIR)
    parser.add_argument("--force_reprocessing", action="store_true", help="Reprocess items in date range, ignoring current status.")
    parser.add_argument("--start_date", type=str, default=DEFAULT_START_DATE_STR, help=f"Start date (YYYY-MM-DD). Default: {DEFAULT_START_DATE_STR}")
    parser.add_argument("--end_date", type=str, help="End date (YYYY-MM-DD). Default: today.")
    parser.add_argument("--limit", type=int, default=None, help="Optional: Max number of items to process. If not set, processes all matching items.")
    args = parser.parse_args()

    logger.setLevel(getattr(logging, args.log_level.upper()))

    try:
        start_date_dt = datetime.strptime(args.start_date, "%Y-%m-%d").date()
    except ValueError:
        logger.error(f"Invalid start_date: {args.start_date}. Use YYYY-MM-DD. Exiting.")
        return
    end_date_dt = datetime.strptime(args.end_date, "%Y-%m-%d").date() if args.end_date else date.today()
    if start_date_dt > end_date_dt:
        logger.error(f"Start date {start_date_dt} after end date {end_date_dt}. Exiting.")
        return

    if args.dry_run: logger.info("*** DRY RUN MODE ENABLED ***")
    if args.output_to_json: logger.info(f"*** JSON OUTPUT to {args.json_output_dir} ***")
    if args.force_reprocessing: logger.info("*** FORCE REPROCESSING ENABLED ***")

    global _department_configs_cache # Ensure cache is loaded before processing
    if _department_configs_cache is None:
        _department_configs_cache = {}
        try:
            logger.info("Pre-caching department configurations...")
            for doc in db.collection(DEPARTMENT_CONFIG_COLLECTION).stream():
                _department_configs_cache[doc.id] = doc.to_dict()
            logger.info(f"Cached {len(_department_configs_cache)} department configurations.")
        except Exception as e: logger.error(f"Error pre-caching depts: {e}", exc_info=True)
    
    global _parliament_sessions_cache # Ensure parliament session cache is loaded
    if _parliament_sessions_cache is None:
        logger.info("Attempting to pre-warm parliament session cache...")
        # Calling get_parliament_session_id with a dummy date to trigger cache population if db is available
        # This relies on the function to handle db_client being None if necessary (e.g. for JSON output only runs)
        if db:
            get_parliament_session_id(db, datetime.now(timezone.utc)) # Use current date to trigger population
        else:
            logger.info("DB client not available, skipping pre-warming of parliament session cache.")

    await process_pending_raw_news(db, 
                                   dry_run=args.dry_run, 
                                   output_to_json=args.output_to_json, 
                                   json_output_dir=args.json_output_dir, 
                                   force_reprocessing=args.force_reprocessing,
                                   start_date_filter_dt=start_date_dt,
                                   end_date_filter_dt=end_date_dt,
                                   limit=args.limit)
    logger.info("--- Raw News to Evidence Processing Script Finished ---")

if __name__ == "__main__":
    asyncio.run(main()) 