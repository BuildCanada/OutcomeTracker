"""
Processes raw news items from Firestore, uses an LLM for analysis,
and creates structured evidence items.
"""
import os
import logging
import uuid
import json
from datetime import datetime, timezone
from dotenv import load_dotenv
import firebase_admin # For Firestore connection
from firebase_admin import credentials, firestore # For Firestore connection
import asyncio # For potential async LLM calls
import time # For unique app name fallback in Firebase init

# It's good practice to import your LLM library here
# For example, if using Google's Generative AI SDK:
# import google.generativeai as genai

# --- Configuration ---
load_dotenv()
# --- Logger Setup ---
logging.basicConfig(level=logging.INFO,
                    format='%(asctime)s - %(levelname)s - %(filename)s:%(lineno)d - %(message)s',
                    datefmt='%Y-%m-%d %H:%M:%S')
logger = logging.getLogger("process_raw_news_to_evidence")
# --- End Logger Setup ---

FIRESTORE_PROJECT_ID = os.getenv("FIRESTORE_PROJECT_ID") # Used for logging clarity
RAW_NEWS_RELEASES_COLLECTION = "raw_news_releases"
EVIDENCE_ITEMS_COLLECTION = "evidence_items"
SESSIONS_CONFIG_COLLECTION = "sessions_config" # Needed for context if not in raw item
DEPARTMENT_CONFIG_COLLECTION = "department_config" # For standardizing department names

# Configure your LLM API key if needed (example for Google GenAI)
# GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")
# if GOOGLE_API_KEY:
#     genai.configure(api_key=GOOGLE_API_KEY)
# else:
#     logger.warning("GOOGLE_API_KEY not found in .env. LLM calls will likely fail.")

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
                app_name = 'process_news_to_evidence_app'
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

if db is None:
    logger.critical("CRITICAL: Failed to obtain Firestore client. Exiting.")
    exit("Exiting: Firestore client not available.")
# --- End Firebase Configuration ---


# --- LLM Interaction (Placeholder) ---
async def get_llm_analysis(raw_title, raw_summary, publication_date_str, parliament_session_id):
    """
    Sends data to an LLM for analysis and returns structured output.
    This is a placeholder. You will need to implement the actual LLM call.
    """
    raw_summary_short = (raw_summary[:100] + '...') if raw_summary and len(raw_summary) > 100 else raw_summary
    logger.debug(f"Sending to LLM: Title: '{raw_title}', Summary: '{raw_summary_short}...'")

    # --- LLM Prompt --- (as defined in the user query)
    prompt = f"""
    CONTEXT: You are analyzing Canadian federal government news releases. Your goal is to create a concise, factual summary suitable for a timeline tracking government actions and determine if this news is significant enough to warrant further linking to specific government commitments.

    NEWS RELEASE DATA:
    - Title: "{raw_title}"
    - Summary/Snippet: "{raw_summary}"
    - Publication Date: "{publication_date_str}"
    - Assigned Parliamentary Session: "{parliament_session_id}"

    INSTRUCTIONS:
    1. Generate a concise `timeline_summary` (max 30 words, active voice, e.g., "Government announces $X for Y initiative.", "Minister Z tables new legislation on A.") based on the provided news data.
    2. Assign a `potential_relevance_score` (choose one: "High", "Medium", "Low") indicating if this news item likely represents a tangible action, policy change, funding announcement, or legislative step, rather than routine administrative updates, minor staff announcements, or general public awareness campaigns.
    3. Extract up to 5 `key_concepts` (keywords or short phrases) from the news item.
    4. Output as a single JSON object:
       {{ "timeline_summary": "...", "potential_relevance_score": "...", "key_concepts": ["...", "..."] }}
    """

    try:
        # Replace with your actual LLM call, e.g.:
        # model = genai.GenerativeModel('gemini-pro') # Or your chosen model
        # response = await model.generate_content_async(prompt) # Use async if available and preferred
        # llm_output_text = response.text

        # --- Placeholder Response --- (Remove once LLM is integrated)
        logger.warning("Using PLACEHOLDER LLM response. Integrate your LLM.")
        await asyncio.sleep(0.1) # Simulate async call
        placeholder_json = {
            "timeline_summary": f"Placeholder: Gov action on {raw_title[:20]}...",
            "potential_relevance_score": "Medium", # Default to medium to allow processing
            "key_concepts": ["placeholder concept 1", "placeholder concept 2"]
        }
        llm_output_text = json.dumps(placeholder_json)
        # --- End Placeholder --- 

        # Attempt to parse the LLM output as JSON
        llm_data = json.loads(llm_output_text)
        logger.info(f"LLM analysis received for '{raw_title}': Score: {llm_data.get('potential_relevance_score')}")
        return llm_data

    except json.JSONDecodeError as e:
        logger.error(f"LLM output was not valid JSON: {llm_output_text}. Error: {e}")
        return None
    except Exception as e:
        logger.error(f"Error during LLM call for title '{raw_title}': {e}", exc_info=True)
        return None

# --- Helper Functions ---

def standardize_department_name(raw_dept_name, department_configs):
    """
    Standardizes a department name using the department_config collection data.
    This is a placeholder for your actual common_utils.standardize_department_name function.
    You should ideally import and use your existing utility.
    """
    if not raw_dept_name or not department_configs:
        return None

    # Basic standardization (example - replace with your robust logic)
    for _, config in department_configs.items():
        # Ensure config values are strings before calling .lower()
        config_name = config.get("name", "")
        if isinstance(config_name, str) and raw_dept_name.lower() == config_name.lower():
            return config.get("name")
        
        name_variations = config.get("name_variations_all", [])
        if isinstance(name_variations, list):
            for variation in name_variations:
                if isinstance(variation, str) and raw_dept_name.lower() == variation.lower():
                    return config.get("name")
    logger.warning(f"Could not standardize department: '{raw_dept_name}'. Using raw name.")
    return raw_dept_name # Return raw if no match, or handle as per your policy

# --- Main Processing Logic ---
async def process_pending_raw_news(limit=10, dry_run=False):
    """
    Queries pending raw news items, processes them using LLM, and creates evidence items.
    """
    logger.info(f"Starting raw news processing (limit: {limit}, dry_run: {dry_run})...")
    processed_count = 0
    skipped_low_score_count = 0
    error_count = 0
    evidence_created_count = 0

    # Load department_config once
    department_configs = {}
    try:
        dept_docs = db.collection(DEPARTMENT_CONFIG_COLLECTION).stream()
        for doc in dept_docs:
            department_configs[doc.id] = doc.to_dict()
        if not department_configs:
            logger.warning("No department configurations found. Department standardization might be limited.")
    except Exception as e:
        logger.error(f"Error fetching department_config: {e}", exc_info=True)

    try:
        query = db.collection(RAW_NEWS_RELEASES_COLLECTION)\
                  .where(filter=firestore.FieldFilter("evidence_processing_status", "==", "pending_evidence_creation"))\
                  .limit(limit)
        pending_items_stream = query.stream() # Keep as stream initially

        # Process items one by one if async LLM calls are made individually, 
        # or collect into a list if batching to LLM (and manage cursor timeout risk if list is huge)
        items_to_process_ids = [doc.id for doc in pending_items_stream] # Get IDs first

        if not items_to_process_ids:
            logger.info("No pending raw news items found to process.")
            return

        logger.info(f"Found {len(items_to_process_ids)} pending raw news items to attempt processing.")

        for raw_item_id in items_to_process_ids:
            logger.debug(f"Attempting to fetch and process raw_item_id: {raw_item_id}")
            raw_item_doc = await asyncio.to_thread(db.collection(RAW_NEWS_RELEASES_COLLECTION).document(raw_item_id).get)
            
            if not raw_item_doc.exists:
                logger.warning(f"Raw item {raw_item_id} no longer exists or was processed by another instance. Skipping.")
                continue
            
            raw_item = raw_item_doc.to_dict()
            # Re-check status in case it changed between query and full doc fetch
            if raw_item.get("evidence_processing_status") != "pending_evidence_creation":
                logger.info(f"Raw item {raw_item_id} status changed to '{raw_item.get("evidence_processing_status")}' since initial query. Skipping.")
                continue

            processed_count +=1 # Count as attempted to process now that we have the doc

            try:
                title_raw = raw_item.get("title_raw")
                summary_or_snippet_raw = raw_item.get("summary_or_snippet_raw", "")
                publication_date = raw_item.get("publication_date") # Firestore Timestamp
                parliament_session_id = raw_item.get("parliament_session_id_assigned")
                source_url = raw_item.get("source_url")
                department_rss = raw_item.get("department_rss")

                if not title_raw or not publication_date or not source_url:
                    logger.error(f"Skipping item {raw_item_id} due to missing critical fields (title, pub_date, source_url). Status set to error_processing.")
                    if not dry_run:
                        await asyncio.to_thread(db.collection(RAW_NEWS_RELEASES_COLLECTION).document(raw_item_id).update, {
                            "evidence_processing_status": "error_processing",
                            "last_updated_at": firestore.SERVER_TIMESTAMP
                        })
                    error_count +=1
                    continue

                publication_date_str = publication_date.isoformat() if isinstance(publication_date, datetime) else str(publication_date)

                llm_result = await get_llm_analysis(title_raw, summary_or_snippet_raw, publication_date_str, parliament_session_id)

                if not llm_result:
                    logger.error(f"LLM analysis failed for {raw_item_id}. Status set to error_processing.")
                    if not dry_run:
                        await asyncio.to_thread(db.collection(RAW_NEWS_RELEASES_COLLECTION).document(raw_item_id).update, {
                            "evidence_processing_status": "error_processing",
                            "last_updated_at": firestore.SERVER_TIMESTAMP
                        })
                    error_count +=1
                    continue

                potential_relevance_score = llm_result.get("potential_relevance_score", "Low").lower()
                timeline_summary = llm_result.get("timeline_summary")
                key_concepts = llm_result.get("key_concepts", [])

                if not timeline_summary:
                    logger.error(f"LLM result for {raw_item_id} missing timeline_summary. Status set to error_processing.")
                    if not dry_run:
                        await asyncio.to_thread(db.collection(RAW_NEWS_RELEASES_COLLECTION).document(raw_item_id).update, {
                            "evidence_processing_status": "error_processing",
                            "last_updated_at": firestore.SERVER_TIMESTAMP
                        })
                    error_count += 1
                    continue

                if potential_relevance_score == "low":
                    logger.info(f"Skipping item {raw_item_id} due to low relevance score.")
                    if not dry_run:
                        await asyncio.to_thread(db.collection(RAW_NEWS_RELEASES_COLLECTION).document(raw_item_id).update, {
                            "evidence_processing_status": "skipped_irrelevant_low_score",
                            "last_updated_at": firestore.SERVER_TIMESTAMP
                        })
                    skipped_low_score_count += 1
                    continue

                evidence_id = f"evd_{uuid.uuid4()}"
                linked_departments = []
                if department_rss:
                    std_dept_name = standardize_department_name(department_rss, department_configs)
                    if std_dept_name:
                        linked_departments.append(std_dept_name)
                    # else: Fallback to raw if not standardized is implicitly handled if std_dept_name is None or raw_dept_name
                
                evidence_item_data = {
                    "evidence_id": evidence_id,
                    "promise_ids": [],
                    "evidence_source_type": "News Release (Canada.ca)",
                    "evidence_date": publication_date, 
                    "title_or_summary": timeline_summary,
                    "description_or_details": summary_or_snippet_raw, 
                    "source_url": source_url,
                    "linked_departments": linked_departments if linked_departments else None,
                    "parliament_session_id": parliament_session_id,
                    "ingested_at": firestore.SERVER_TIMESTAMP,
                    "additional_metadata": {
                        "raw_news_release_id": raw_item_id, 
                        "llm_key_concepts": key_concepts
                    },
                    "dev_linking_status": "pending"
                }
                
                if not dry_run:
                    await asyncio.to_thread(db.collection(EVIDENCE_ITEMS_COLLECTION).document(evidence_id).set, evidence_item_data)
                    logger.info(f"Created evidence item {evidence_id} from raw item {raw_item_id}.")
                    await asyncio.to_thread(db.collection(RAW_NEWS_RELEASES_COLLECTION).document(raw_item_id).update, {
                        "evidence_processing_status": "evidence_created",
                        "related_evidence_item_id": evidence_id,
                        "last_updated_at": firestore.SERVER_TIMESTAMP
                    })
                else:
                    logger.info(f"[DRY RUN] Would create evidence item {evidence_id} from raw item {raw_item_id} with data: {json.dumps(evidence_item_data, default=str)}")
                    logger.info(f"[DRY RUN] Would update raw news item {raw_item_id} to status 'evidence_created' and link {evidence_id}.")
                
                evidence_created_count +=1

            except Exception as e_inner:
                logger.error(f"Error processing single raw news item {raw_item_id}: {e_inner}", exc_info=True)
                error_count += 1
                if not dry_run:
                    try:
                        await asyncio.to_thread(db.collection(RAW_NEWS_RELEASES_COLLECTION).document(raw_item_id).update, {
                            "evidence_processing_status": "error_processing",
                            "last_updated_at": firestore.SERVER_TIMESTAMP
                        })
                    except Exception as update_err:
                        logger.error(f"Failed to mark item {raw_item_id} as error_processing after inner error: {update_err}")
                continue # continue to the next item in items_to_process_ids

    except Exception as e_outer:
        logger.error(f"Major error in process_pending_raw_news query or stream setup: {e_outer}", exc_info=True)
        # This indicates an issue with the query itself or Firestore connection during query

    logger.info(f"Raw news processing finished. Attempted: {processed_count}, Evidence Created: {evidence_created_count}, Skipped (Low Score): {skipped_low_score_count}, Errors: {error_count}")

async def main():
    # Setup argparse here if you want command-line arguments for this script too
    # For now, using fixed limit and no dry_run argument passed to process_pending_raw_news
    # You can extend this similarly to ingest_canada_news_rss.py if needed.
    import argparse
    parser = argparse.ArgumentParser(description="Process raw news items into evidence items using LLM analysis.")
    parser.add_argument(
        "--limit", 
        type=int, 
        default=10, 
        help="Number of raw news items to process in this run."
    )
    parser.add_argument(
        "--dry_run",
        action="store_true",
        help="Perform a dry run without making any changes to Firestore."
    )
    args = parser.parse_args()

    logger.info("--- Starting Raw News to Evidence Processing Script ---")
    if args.dry_run:
        logger.info("*** DRY RUN MODE ENABLED: No changes will be written to Firestore. ***")

    await process_pending_raw_news(limit=args.limit, dry_run=args.dry_run)
    logger.info("--- Raw News to Evidence Processing Script Finished ---")

if __name__ == "__main__":
    asyncio.run(main()) 