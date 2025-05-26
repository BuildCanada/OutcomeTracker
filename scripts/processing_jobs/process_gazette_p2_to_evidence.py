"""
Processes raw Canada Gazette Part II notices into standardized evidence_items using Gemini LLM.
Queries raw_gazette_p2_notices with evidence_processing_status == 'pending_evidence_creation',
extracts key sections (RIAS, main text), sends to Gemini, and writes to evidence_items or updates status.

CLI arguments:
--dry_run: If True, do not write to Firestore but still call Gemini and log/store outputs. Default: False
--log_level: Set the logging level. Default: INFO
--JSON: If True, output processed evidence docs to a JSON file instead of Firestore. Default: False
--json_output_dir: The directory to write the JSON file to. Default: ./JSON_outputs
--force_reprocessing: If True, reprocess all items up to the limit, ignoring current status. Default: False
--start_date: The start date to process from. Format: YYYY-MM-DD. Default: 2025-03-23
--end_date: The end date to process to. Format: YYYY-MM-DD. Default: today

Next steps to make ready for production:
- add check for last run date in Firestore and only process items that are newer than that
- add any changes or config to run with docker
- schedule cron job to daily at 9:30am ET
"""
import os
import logging
import json
import asyncio
from datetime import datetime, timezone, date
from dotenv import load_dotenv
import firebase_admin
from firebase_admin import credentials, firestore
import argparse
import time
import re
from bs4 import BeautifulSoup
import hashlib
from google import genai
import traceback

# --- Configuration ---
load_dotenv()

# --- Logger Setup ---
logging.basicConfig(level=logging.INFO,
                    format='%(asctime)s - %(levelname)s - %(filename)s:%(lineno)d - %(message)s',
                    datefmt='%Y-%m-%d %H:%M:%S')
logger = logging.getLogger("process_raw_gazette_to_evidence")
# --- End Logger Setup ---

# --- Constants ---
RAW_GAZETTE_P2_NOTICES_COLLECTION = "raw_gazette_p2_notices"
EVIDENCE_ITEMS_COLLECTION = "evidence_items_test"
DEFAULT_PROCESS_LIMIT = 10
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
DEFAULT_JSON_OUTPUT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'JSON_outputs', 'gazette_p2_processing')
PROMPT_FILE_PATH = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', 'prompts', 'prompt_gazette2_evidence.md'))
DEFAULT_START_DATE_STR = "2025-03-23"


# --- Gemini Configuration ---
if not GEMINI_API_KEY:
    logger.critical("GEMINI_API_KEY not found in environment variables or .env file.")
    exit("Exiting: Missing GEMINI_API_KEY.")

# Set GOOGLE_API_KEY environment variable if not already set, for the client to pick up
if "GOOGLE_API_KEY" not in os.environ and GEMINI_API_KEY:
    os.environ["GOOGLE_API_KEY"] = GEMINI_API_KEY
    logger.info("Set GOOGLE_API_KEY environment variable from GEMINI_API_KEY.")

LLM_MODEL_NAME = os.getenv("GEMINI_MODEL_NAME_GAZETTE_PROCESSING", "models/gemini-2.5-flash-preview-05-20")

# GENERATION_CONFIG_DICT can be used with model.generate_content if needed, 
# but is often passed directly or relies on model defaults for simpler calls.
GENERATION_CONFIG_DICT = { 
    "temperature": 0.3, 
    "top_p": 0.95,
    "top_k": 64,
    "max_output_tokens": 65536, 
    "response_mime_type": "application/json", # Ensure your prompt asks for JSON
}

# Initialize the model directly
client = None
try:
    client = genai.Client()
    logger.info(f"Successfully initialized Gemini Client. Model {LLM_MODEL_NAME} will be used at call time.")
except Exception as e:
    logger.critical(f"Failed to initialize Gemini client: {e}", exc_info=True)
    exit("Exiting: Gemini client initialization failed.")
# --- End Gemini Configuration ---

# --- Firestore Setup ---
db = None
if not firebase_admin._apps:
    try:
        firebase_admin.initialize_app()
        db = firestore.client()
        logger.info("Connected to Firestore with default credentials.")
    except Exception as e_default:
        logger.warning(f"Default Firebase init failed: {e_default}. Trying service account.")
        cred_path = os.getenv('FIREBASE_SERVICE_ACCOUNT_KEY_PATH')
        if cred_path:
            try:
                cred = credentials.Certificate(cred_path)
                app_name = f'gazette_processing_app_{int(time.time())}' # Ensure unique app name
                firebase_admin.initialize_app(cred, name=app_name)
                db = firestore.client(app=firebase_admin.get_app(name=app_name))
                logger.info("Connected to Firestore with service account.")
            except Exception as e_sa:
                logger.critical(f"Service account Firebase init failed: {e_sa}", exc_info=True)
        else:
            logger.critical("No FIREBASE_SERVICE_ACCOUNT_KEY_PATH set and default creds failed.")

if db is None:
    logger.critical("CRITICAL: Firestore client not available. Exiting.")
    exit(1)
# --- End Firestore Setup ---

# --- Helper Functions ---
def extract_rias_from_text(full_text):
    if not full_text:
        return None
    rias_patterns = [
        r"REGULATORY IMPACT ANALYSIS STATEMENT[\s\n]*([\s\S]+?)(?:\n[A-Z][A-Z\s]+:|$)",
        r"Regulatory Impact Analysis Statement[\s\n]*([\s\S]+?)(?:\n[A-Z][A-Z\s]+:|$)",
        r"Impact Analysis Statement[\s\n]*([\s\S]+?)(?:\n[A-Z][A-Z\s]+:|$)"
    ]
    for pattern in rias_patterns:
        match = re.search(pattern, full_text, re.IGNORECASE)
        if match:
            return match.group(1).strip()
    return None

def extract_coming_into_force(full_text):
    if not full_text:
        return None
    match = re.search(r"coming into force[\s\S]{0,200}", full_text, re.IGNORECASE)
    if match:
        return match.group(0).strip()
    return None

def clean_json_from_markdown(text_blob: str) -> str:
    regex_pattern = r"```(?:json)?\s*([\s\S]+?)\s*```"
    match = re.search(regex_pattern, text_blob)
    if match:
        return match.group(1).strip()
    else:
        return text_blob.strip()

async def call_gemini_llm(prompt_text):
    if not client:
        logger.critical("Gemini client not initialized. Cannot call LLM.")
        return None, LLM_MODEL_NAME

    max_retries = 3
    for attempt in range(max_retries):
        try:
            response = await client.aio.models.generate_content(
                model=LLM_MODEL_NAME,
                contents=[prompt_text]
            )
            raw_response_text = response.text
            
            # Log truncated responses to help debug
            if len(raw_response_text) > 1000 and not raw_response_text.strip().endswith('}'):
                logger.warning(f"LLM response appears to be truncated (length: {len(raw_response_text)}, ends with: '{raw_response_text[-50:]}'). Attempt {attempt + 1}/{max_retries}")
                if attempt < max_retries - 1:
                    continue  # Retry if not the last attempt
            
            json_str = clean_json_from_markdown(raw_response_text)
            parsed_result = json.loads(json_str)
            return parsed_result, LLM_MODEL_NAME
            
        except json.JSONDecodeError as json_err:
            logger.error(f"LLM response was not valid JSON on attempt {attempt + 1}. Error: {json_err}")
            logger.error(f"Raw Response (first 800 chars): {raw_response_text[:800] if 'raw_response_text' in locals() else 'N/A'}")
            logger.error(f"Raw Response (last 200 chars): {raw_response_text[-200:] if 'raw_response_text' in locals() else 'N/A'}")
            
            if attempt < max_retries - 1:
                logger.info(f"Retrying LLM call ({attempt + 2}/{max_retries})...")
                continue
            else:
                logger.error("Failed to get valid JSON after all retry attempts")
                return None, LLM_MODEL_NAME
                
        except Exception as e:
            logger.error(f"Error calling Gemini LLM ({LLM_MODEL_NAME}) on attempt {attempt + 1}: {e}")
            if attempt < max_retries - 1:
                logger.info(f"Retrying LLM call ({attempt + 2}/{max_retries})...")
                continue
            else:
                logger.error("Failed after all retry attempts", exc_info=True)
                return None, LLM_MODEL_NAME
    
    return None, LLM_MODEL_NAME

def load_gemini_prompt_template(prompt_file: str) -> str:
    try:
        with open(prompt_file, 'r') as f:
            return f.read()
    except Exception as e:
        logger.critical(f"Could not load Gemini prompt template from {prompt_file}: {e}")
        raise

def build_gemini_prompt(raw_doc, rias_text_snippet, coming_into_force, parliament_session_id, prompt_template: str) -> str:
    return prompt_template.format(
        regulation_title=raw_doc.get('regulation_title', ''),
        registration_sor_si_number=raw_doc.get('registration_sor_si_number', ''),
        publication_date=raw_doc.get('publication_date', ''),
        act_sponsoring=raw_doc.get('act_sponsoring', ''),
        rias_text=(rias_text_snippet or '')[:2000], # Pass only a snippet to the main prompt
        coming_into_force=coming_into_force or '',
        parliament_session_id=parliament_session_id or ''
    )

# --- Main Processing Logic ---
async def process_pending_gazette_notices(db_client, dry_run=False, output_to_json=False, json_output_dir=None, force_reprocessing=False, start_date_filter_dt=None, end_date_filter_dt=None):
    main_prompt_template = load_gemini_prompt_template(PROMPT_FILE_PATH)
    logger.info(f"Processing Gazette notices. Dry run: {dry_run}, JSON: {output_to_json}, Force reprocess: {force_reprocessing}")
    logger.info(f"Date filter: From {start_date_filter_dt.strftime('%Y-%m-%d')} to {end_date_filter_dt.strftime('%Y-%m-%d')}")

    query = db_client.collection(RAW_GAZETTE_P2_NOTICES_COLLECTION)

    # Apply date filters
    # Ensure comparison is with datetime objects at midnight UTC for date part
    start_datetime_utc = datetime.combine(start_date_filter_dt, datetime.min.time(), tzinfo=timezone.utc)
    end_datetime_utc = datetime.combine(end_date_filter_dt, datetime.max.time(), tzinfo=timezone.utc) # up to end of day

    query = query.where(filter=firestore.FieldFilter("publication_date", ">=", start_datetime_utc))
    query = query.where(filter=firestore.FieldFilter("publication_date", "<=", end_datetime_utc))

    if force_reprocessing:
        logger.info("Force reprocessing is ENABLED. Will attempt to reprocess all items in date range regardless of current status.")
        # No further status filter needed
    else:
        logger.info("Querying for items in date range with status 'pending_evidence_creation'.")
        query = query.where(filter=firestore.FieldFilter("evidence_processing_status", "==", "pending_evidence_creation"))
    
    # The .limit() is removed here to process ALL matching documents
    docs_snapshot = query.stream() # Use stream for potentially large results
    docs = list(docs_snapshot) # Convert to list to get a count and iterate
    
    logger.info(f"Found {len(docs)} notices matching criteria to process.")

    all_outputs_for_json = []
    if output_to_json:
        os.makedirs(json_output_dir, exist_ok=True)

    for doc in docs:
        raw_doc_data = doc.to_dict()
        doc_id = doc.id
        logger.info(f"Processing Gazette notice: {doc_id} - {raw_doc_data.get('regulation_title', '')}")
        try:
            full_scraped_text = raw_doc_data.get('full_text_scraped')
            full_rias_text = extract_rias_from_text(full_scraped_text)
            coming_into_force_text = extract_coming_into_force(full_scraped_text)
            parliament_session_id = raw_doc_data.get('parliament_session_id_assigned')

            # Single LLM call for all structured data including RIAS summary
            main_llm_prompt = build_gemini_prompt(raw_doc_data, full_rias_text, coming_into_force_text, parliament_session_id, main_prompt_template)
            logger.debug(f"Main Gemini prompt for {doc_id}:\n{main_llm_prompt}")
            gemini_result_dict, model_used_for_call = await call_gemini_llm(main_llm_prompt)

            if not gemini_result_dict:
                logger.error(f"Gemini LLM processing failed for doc {doc_id} (Model: {model_used_for_call}). Skipping.")
                if not dry_run:
                    doc.reference.update({
                        'evidence_processing_status': 'llm_processing_failed',
                        'processed_at': firestore.SERVER_TIMESTAMP,
                        'llm_model_name_last_attempt': model_used_for_call
                        })
                continue

            # The RIAS summary is now part of gemini_result_dict
            rias_summary = gemini_result_dict.get('rias_summary', '')
            # Safe slicing to handle None or empty strings
            rias_preview = (rias_summary[:100] + "...") if rias_summary else "No RIAS summary available"
            logger.debug(f"RIAS summary (from main LLM call) for {doc_id}: {rias_preview}")

            # Evidence ID: YYYYMMDD_sessionID_Gazette2_{short hash}
            pub_date_obj = raw_doc_data.get('publication_date')
            if isinstance(pub_date_obj, str):
                try:
                    pub_date_obj = datetime.fromisoformat(pub_date_obj.replace('Z', '+00:00'))
                except ValueError:
                     try: # Attempt to parse if it's just YYYY-MM-DD
                        pub_date_obj = datetime.strptime(pub_date_obj, "%Y-%m-%d")
                     except ValueError:
                        pub_date_obj = None
            pub_date_str = pub_date_obj.strftime('%Y%m%d') if pub_date_obj else 'unknown'
            
            session_id_str = parliament_session_id or 'unknown'
            hash_input = f"{raw_doc_data.get('source_url_regulation_html', '')}_{pub_date_str}"
            short_hash = hashlib.sha256(hash_input.encode('utf-8')).hexdigest()[:10]
            evidence_id = f"{pub_date_str}_{session_id_str}_Gazette2_{short_hash}"

            # Extract LLM results directly to top-level and specific locations
            # Use safe extraction with fallbacks for None values
            timeline_summary = gemini_result_dict.get('timeline_summary') or ''
            potential_relevance_score = gemini_result_dict.get('potential_relevance_score') or 'Low'  # Default to Low if missing
            key_concepts = gemini_result_dict.get('key_concepts') or []
            sponsoring_department_standardized = gemini_result_dict.get('sponsoring_department_standardized') or ''
            rias_summary_llm = gemini_result_dict.get('rias_summary') or ''
            one_sentence_description_llm = gemini_result_dict.get('one_sentence_description') or '' 

            evidence_doc = {
                'evidence_id': evidence_id,
                'promise_ids': [],
                'parliament_session_id': parliament_session_id,
                'evidence_source_type': 'Regulation (Canada Gazette P2)',
                'evidence_date': pub_date_obj, 
                'title_or_summary': timeline_summary, # From LLM, no date preface
                'description_or_details': one_sentence_description_llm, # Populated by LLM
                'source_url': raw_doc_data.get('source_url_regulation_html'),
                'source_document_raw_id': raw_doc_data.get('registration_sor_si_number'),
                'linked_departments': [sponsoring_department_standardized] if sponsoring_department_standardized else [],
                'ingested_at': datetime.now(timezone.utc),
                'potential_relevance_score': potential_relevance_score, # Top-level from LLM
                'key_concepts': key_concepts, # Top-level from LLM
                'additional_metadata': {
                    'raw_gazette_notice_id': doc_id,
                    'rias_summary': rias_summary_llm # LLM-generated RIAS summary here
                },
                'promise_linking_status': 'pending',
                'llm_analysis_raw': gemini_result_dict, # Keep this for the evidence item itself for now
            }

            if output_to_json:
                json_compatible_doc = evidence_doc.copy()
                for key, value in json_compatible_doc.items():
                    if isinstance(value, datetime):
                        json_compatible_doc[key] = value.isoformat()
                if 'additional_metadata' in json_compatible_doc and isinstance(json_compatible_doc['additional_metadata'], dict):
                    for key_am, value_am in json_compatible_doc['additional_metadata'].items():
                         if isinstance(value_am, datetime):
                            json_compatible_doc['additional_metadata'][key_am] = value_am.isoformat()
                all_outputs_for_json.append(json_compatible_doc)
                logger.info(f"Prepared evidence doc for JSON output (ID: {evidence_id}) for Gazette doc {doc_id}.")

            if dry_run:
                logger.info(f"[DRY RUN] Would create evidence_item for Gazette doc {doc_id}. Evidence ID: {evidence_id}")
                logger.debug(f"[DRY RUN] Evidence doc data: {json.dumps(evidence_doc, default=str, indent=2)}")
                continue # Skip Firestore writes in dry_run

            # Actual Firestore write for non-dry_run
            relevance = potential_relevance_score.lower() # Use the top-level field
            if relevance == 'low':
                logger.info(f"Regulation {doc_id} (Evidence ID: {evidence_id}) scored 'Low' relevance. Marking raw notice as skipped.")
                update_data = {
                    'evidence_processing_status': 'skipped_low_relevance_score',
                    'processed_at': firestore.SERVER_TIMESTAMP,
                    'llm_model_name_last_attempt': model_used_for_call
                }
                doc.reference.update(update_data)
            else:
                db_client.collection(EVIDENCE_ITEMS_COLLECTION).document(evidence_id).set(evidence_doc)
                logger.info(f"Created evidence_item {evidence_id} for Gazette doc {doc_id}.")
                update_data = {
                    'evidence_processing_status': 'evidence_created',
                    'related_evidence_item_id': evidence_id,
                    'processed_at': firestore.SERVER_TIMESTAMP,
                    'llm_model_name_last_attempt': model_used_for_call
                }
                doc.reference.update(update_data)
        except Exception as e_proc:
            logger.error(f"Error processing Gazette doc {doc_id}: {e_proc}", exc_info=True)
            model_name_at_error = model_used_for_call if 'model_used_for_call' in locals() else LLM_MODEL_NAME
            if not dry_run:
                update_data = {
                    'evidence_processing_status': 'processing_error',
                    'processing_error_message': str(e_proc),
                    'processed_at': firestore.SERVER_TIMESTAMP,
                    'llm_model_name_last_attempt': model_name_at_error
                }
                doc.reference.update(update_data)
            continue

    if output_to_json and all_outputs_for_json:
        try:
            timestamp_str = datetime.now().strftime("%Y%m%d_%H%M%S")
            json_filename = os.path.join(json_output_dir, f"processed_gazette_evidence_{timestamp_str}.json")
            with open(json_filename, 'w', encoding='utf-8') as f:
                json.dump(all_outputs_for_json, f, indent=4, ensure_ascii=False, default=str)
            logger.info(f"Successfully wrote {len(all_outputs_for_json)} processed evidence docs to JSON file: {json_filename}")
        except Exception as e_json:
            logger.error(f"Error writing processed evidence docs to JSON file: {e_json}", exc_info=True)

# --- CLI ---    
def main():
    parser = argparse.ArgumentParser(description="Process raw Gazette P2 notices into evidence_items using Gemini LLM.")
    parser.add_argument('--dry_run', action='store_true', help='If set, do not write to Firestore but still call Gemini and log/store outputs.')
    parser.add_argument('--log_level', type=str, default='INFO', choices=['DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL'], help='Set the logging level.')
    parser.add_argument('--JSON', dest='output_to_json', action='store_true', help='Output processed evidence docs to a JSON file instead of Firestore.')
    parser.add_argument('--json_output_dir', type=str, default=DEFAULT_JSON_OUTPUT_DIR, help=f'Directory for JSON output. Default: {DEFAULT_JSON_OUTPUT_DIR}')
    parser.add_argument('--force_reprocessing', action='store_true', help='If set, reprocess all items up to the limit, ignoring current status.')
    parser.add_argument("--start_date", type=str, default=DEFAULT_START_DATE_STR, help=f"Start date for processing (YYYY-MM-DD). Default: {DEFAULT_START_DATE_STR}")
    parser.add_argument("--end_date", type=str, help="End date for processing (YYYY-MM-DD). Default: today.")

    args = parser.parse_args()
    logger.setLevel(getattr(logging, args.log_level.upper()))

    # Parse dates
    try:
        start_date_dt = datetime.strptime(args.start_date, "%Y-%m-%d").date()
    except ValueError:
        logger.error(f"Invalid --start_date format: {args.start_date}. Please use YYYY-MM-DD. Exiting.")
        return

    if args.end_date:
        try:
            end_date_dt = datetime.strptime(args.end_date, "%Y-%m-%d").date()
        except ValueError:
            logger.error(f"Invalid --end_date format: {args.end_date}. Please use YYYY-MM-DD. Exiting.")
            return
    else:
        end_date_dt = date.today()

    if start_date_dt > end_date_dt:
        logger.error(f"Error: Start date ({start_date_dt.strftime('%Y-%m-%d')}) cannot be after end date ({end_date_dt.strftime('%Y-%m-%d')}). Exiting.")
        return

    if args.dry_run:
        logger.info("*** DRY RUN MODE ENABLED ***")
    if args.output_to_json:
        logger.info(f"*** JSON OUTPUT ENABLED to {args.json_output_dir} ***")
    if args.force_reprocessing:
        logger.info("*** FORCE REPROCESSING ENABLED ***")

    asyncio.run(process_pending_gazette_notices(db, 
                                                dry_run=args.dry_run, 
                                                output_to_json=args.output_to_json, 
                                                json_output_dir=args.json_output_dir, 
                                                force_reprocessing=args.force_reprocessing,
                                                start_date_filter_dt=start_date_dt,
                                                end_date_filter_dt=end_date_dt))

if __name__ == '__main__':
    main()
