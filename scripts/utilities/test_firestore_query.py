import firebase_admin
from firebase_admin import credentials, firestore
import os
import logging

# --- Logger Setup ---
logging.basicConfig(level=logging.INFO,
                    format='%(asctime)s - %(levelname)s - %(filename)s:%(lineno)d - %(message)s',
                    datefmt='%Y-%m-%d %H:%M:%S')
logger = logging.getLogger(__name__)
# --- End Logger Setup ---

# --- Firebase Configuration ---
db = None
if not firebase_admin._apps:
    try:
        # Attempt to use GOOGLE_APPLICATION_CREDENTIALS first
        cred_path = os.getenv('GOOGLE_APPLICATION_CREDENTIALS')
        if cred_path:
            cred = credentials.Certificate(cred_path)
            firebase_admin.initialize_app(cred)
            logger.info("Firebase Admin SDK initialized using Application Credentials.")
        else:
            # Fallback for environments where GOOGLE_APPLICATION_CREDENTIALS might not be set
            # but default service account might be available (e.g. Cloud Functions, Cloud Run)
            firebase_admin.initialize_app()
            logger.info("Firebase Admin SDK initialized with default or environment-provided credentials.")
        
        project_id_env = os.getenv('FIREBASE_PROJECT_ID')
        actual_project_id = firebase_admin.get_app().project_id if firebase_admin.get_app() else None
        
        if project_id_env and actual_project_id and project_id_env != actual_project_id:
            logger.warning(f"Mismatch between FIREBASE_PROJECT_ID env var ('{project_id_env}') and actual project_id from SDK ('{actual_project_id}'). Using SDK's project_id.")
        
        project_id_to_log = actual_project_id or project_id_env or '[Cloud Project ID Not Set]'
        logger.info(f"Python (TestQuery): Connected to CLOUD Firestore (Project: {project_id_to_log}).")
        db = firestore.client()
    except Exception as e:
        logger.critical(f"Firebase init failed: {e}", exc_info=True)
        exit("Exiting: Firebase connection failed.")
else:
    db = firestore.client()
    logger.info("Firebase Admin SDK already initialized.")

if db is None:
    exit("Exiting: Firestore client not available.")
# --- End Firebase Configuration ---

# --- Constants ---
EVIDENCE_ITEMS_COLLECTION = 'evidence_items'
# --- End Constants ---

def test_query():
    logger.info(f"--- Starting Test Query on '{EVIDENCE_ITEMS_COLLECTION}' ---")

    query_count = 0
    documents_found_details = []

    try:
        logger.info("DEBUG: Fetching documents based on 'evidence_source_type' only and checking 'dev_linking_status' in client.")
        
        evidence_query = (db.collection(EVIDENCE_ITEMS_COLLECTION)
                           .where(filter=firestore.FieldFilter('evidence_source_type', '==', "Bill Event (LEGISinfo)"))
                           .limit(50)) # Fetch a decent number to check

        docs_stream = evidence_query.stream()
        
        processed_in_test = 0
        actually_missing_status_count = 0
        found_with_status_count = 0

        for doc in docs_stream:
            processed_in_test += 1
            doc_data = doc.to_dict()
            
            dev_linking_status_value = doc_data.get('dev_linking_status', '##FIELD_MISSING_IN_PYTHON##')
            has_field = 'dev_linking_status' in doc_data

            if dev_linking_status_value == '##FIELD_MISSING_IN_PYTHON##':
                actually_missing_status_count += 1
            else:
                found_with_status_count +=1

            if processed_in_test <= 20: # Log details for the first few
                 logger.info(f"  Fetched doc ID: {doc.id}, Has 'dev_linking_status' field: {has_field}, Value (or default): '{dev_linking_status_value}'")
        
        logger.info(f"DEBUG: Total documents fetched by source_type: {processed_in_test}")
        logger.info(f"DEBUG: Documents where get() indicated field was missing: {actually_missing_status_count}")
        logger.info(f"DEBUG: Documents where get() found the field: {found_with_status_count}")

    except Exception as e:
        logger.error(f"Error during Firestore query or processing: {e}", exc_info=True)

    logger.info(f"--- Test Query Finished ---")
    # Combined logging for overall script execution might be confusing now with two tests.
    # Let individual test logs be the primary source of counts for now.
    # logger.info(f"Total documents found by the query: {query_count}") 
    # if query_count > 10:
    #     logger.info(f"Details for first 10 shown above. Total {query_count - 10} more documents found but not logged in detail.")
    # elif query_count == 0:
    #     logger.info("No documents matched the query.")

if __name__ == "__main__":
    from dotenv import load_dotenv
    load_dotenv() # Load .env file for GOOGLE_APPLICATION_CREDENTIALS if not set globally
    test_query() 