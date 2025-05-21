import firebase_admin
from firebase_admin import credentials, firestore
import os
import logging

# --- Logger Setup ---
# Simplified logger setup
logging.basicConfig(level=logging.INFO,
                    format='%(asctime)s - %(levelname)s - %(filename)s:%(lineno)d - %(message)s',
                    datefmt='%Y-%m-%d %H:%M:%S')
logger = logging.getLogger(__name__)
# --- End Logger Setup ---

# --- Firebase Configuration ---
db = None
if not firebase_admin._apps:
    try:
        cred_path = os.getenv('GOOGLE_APPLICATION_CREDENTIALS')
        if cred_path:
            logger.info(f"Attempting to use GOOGLE_APPLICATION_CREDENTIALS from: {cred_path}")
            cred = credentials.Certificate(cred_path)
            firebase_admin.initialize_app(cred)
            logger.info("Firebase Admin SDK initialized using GOOGLE_APPLICATION_CREDENTIALS.")
        else:
            logger.info("GOOGLE_APPLICATION_CREDENTIALS not set. Attempting to use default credentials (e.g., from gcloud ADC).")
            # Fallback for environments where GOOGLE_APPLICATION_CREDENTIALS might not be set
            # but default service account might be available (e.g. Cloud Functions, Cloud Run, or local gcloud auth)
            firebase_admin.initialize_app()
            logger.info("Firebase Admin SDK initialized with default or environment-provided credentials.")
        
        db = firestore.client()
        project_id = firebase_admin.get_app().project_id
        logger.info(f"Successfully connected to Firestore. Project ID: {project_id}")

    except Exception as e:
        logger.critical(f"Firebase initialization failed: {e}", exc_info=True)
        exit("Exiting: Firebase connection failed.")
else:
    # App already initialized, just get the client
    db = firestore.client()
    project_id = firebase_admin.get_app().project_id
    logger.info(f"Firebase Admin SDK already initialized. Connected to Firestore. Project ID: {project_id}")

if db is None:
    # This case should ideally be caught by the exit calls above, but as a safeguard:
    logger.critical("Firestore client (db) is None after initialization attempts.")
    exit("Exiting: Firestore client not available.")
# --- End Firebase Configuration ---

# --- Constants ---
EVIDENCE_ITEMS_COLLECTION = 'evidence_items'
# --- End Constants ---

def test_query():
    logger.info(f"--- Starting Data Overview for '{EVIDENCE_ITEMS_COLLECTION}' ---")

    total_records = 0
    parliament_session_counts = {}
    evidence_source_type_counts = {} # Stores {"type": {"total": X, "linked_to_promise": Y}}

    try:
        docs_stream = db.collection(EVIDENCE_ITEMS_COLLECTION).stream()

        for doc in docs_stream:
            total_records += 1
            doc_data = doc.to_dict()

            # 2. Count by parliament_session_id
            session_id = doc_data.get('parliament_session_id', '##FIELD_MISSING##')
            parliament_session_counts[session_id] = parliament_session_counts.get(session_id, 0) + 1

            # 3. Count by evidence_source_type and linked promises
            source_type = doc_data.get('evidence_source_type', '##FIELD_MISSING##')
            promise_ids = doc_data.get('promise_ids', []) # Assume list, default to empty

            if source_type not in evidence_source_type_counts:
                evidence_source_type_counts[source_type] = {"total": 0, "linked_to_promise": 0}
            
            evidence_source_type_counts[source_type]["total"] += 1
            
            # Check if promise_ids is a list and is not empty
            if isinstance(promise_ids, list) and len(promise_ids) > 0:
                evidence_source_type_counts[source_type]["linked_to_promise"] += 1
            
            # Commented out individual record logging as requested
            # if total_records <= 20: # Log details for the first few
            #      dev_linking_status_value = doc_data.get('dev_linking_status', '##FIELD_MISSING_IN_PYTHON##')
            #      has_field = 'dev_linking_status' in doc_data
            #      logger.info(f"  Fetched doc ID: {doc.id}, Has 'dev_linking_status' field: {has_field}, Value (or default): '{dev_linking_status_value}'")
        
        logger.info("--- Aggregated Data ---")
        logger.info(f"1. Total records in '{EVIDENCE_ITEMS_COLLECTION}': {total_records}")
        
        logger.info("2. Records by 'parliament_session_id':")
        if parliament_session_counts:
            for session, count in parliament_session_counts.items():
                logger.info(f"  - {session}: {count}")
        else:
            logger.info("  No data found for 'parliament_session_id' or field is largely missing.")

        logger.info("3. Records by 'evidence_source_type' (and linked promises via 'promise_ids'):")
        if evidence_source_type_counts:
            for source_type, counts in evidence_source_type_counts.items():
                logger.info(f"  - Type: {source_type}")
                logger.info(f"    - Total Occurrences: {counts['total']}")
                logger.info(f"    - With Linked Promises: {counts['linked_to_promise']}")
        else:
            logger.info("  No data found for 'evidence_source_type' or field is largely missing.")

    except Exception as e:
        logger.error(f"Error during Firestore query or processing: {e}", exc_info=True)

    logger.info(f"--- Data Overview Finished ---")

if __name__ == "__main__":
    from dotenv import load_dotenv
    load_dotenv() # Load .env file for GOOGLE_APPLICATION_CREDENTIALS if not set globally
    test_query() 