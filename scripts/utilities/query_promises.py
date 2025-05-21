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
PROMISES_COLLECTION = 'LPC'  # Changed to target the subcollection ID, e.g., LPC
# --- End Constants ---

def analyze_promises_data(): # Renamed function for clarity
    logger.info(f"--- Starting Data Overview for Collection Group '{PROMISES_COLLECTION}' ---")

    total_records = 0
    candidate_or_gov_counts = {}
    party_counts = {}
    parliament_session_counts = {}
    source_type_counts = {}
    implied_action_type_counts = {}
    bc_promise_rank_counts = {}
    bc_promise_direction_counts = {}
    responsible_dept_counts = {}
    category_counts = {}
    promises_with_evidence_count = 0
    promises_without_evidence_count = 0

    try:
        docs_stream = db.collection_group(PROMISES_COLLECTION).stream()

        for doc in docs_stream:
            total_records += 1
            doc_data = doc.to_dict()

            # Helper function to update counts
            def update_counter(counter_dict, field_value_from_get):
                # Ensure keys are strings for consistent sorting, especially converting None
                key_to_use = field_value_from_get
                if key_to_use is None: # Handles cases where field exists but its value is null
                    key_to_use = '##VALUE_IS_NULL##'
                # The .get() already defaults to '##FIELD_MISSING##' if the key itself is absent
                # So, key_to_use will now be either the actual string value, '##FIELD_MISSING##', or '##VALUE_IS_NULL##'
                counter_dict[key_to_use] = counter_dict.get(key_to_use, 0) + 1

            # Aggregate data
            update_counter(candidate_or_gov_counts, doc_data.get('candidate_or_government', '##FIELD_MISSING##'))
            update_counter(party_counts, doc_data.get('party', '##FIELD_MISSING##'))
            update_counter(parliament_session_counts, doc_data.get('parliament_session_id', '##FIELD_MISSING##'))
            update_counter(source_type_counts, doc_data.get('source_type', '##FIELD_MISSING##'))
            update_counter(implied_action_type_counts, doc_data.get('implied_action_type', '##FIELD_MISSING##'))
            update_counter(bc_promise_rank_counts, doc_data.get('bc_promise_rank', '##FIELD_MISSING##'))
            update_counter(bc_promise_direction_counts, doc_data.get('bc_promise_direction', '##FIELD_MISSING##'))
            update_counter(responsible_dept_counts, doc_data.get('responsible_department_lead', '##FIELD_MISSING##'))
            update_counter(category_counts, doc_data.get('category', '##FIELD_MISSING##'))

            linked_evidence = doc_data.get('linked_evidence_ids', [])
            if isinstance(linked_evidence, list) and len(linked_evidence) > 0:
                promises_with_evidence_count += 1
            else:
                promises_without_evidence_count += 1
        
        logger.info("--- Aggregated Data for Promises Collection ---")
        logger.info(f"1. Total records in Collection Group '{PROMISES_COLLECTION}': {total_records}")

        def log_counts(title, counter_dict):
            logger.info(title)
            if counter_dict:
                for item, count in sorted(counter_dict.items()): # Sorted for consistent output
                    logger.info(f"  - {item}: {count}")
            else:
                logger.info("  No data found or field is largely missing.")

        log_counts("2. Records by 'candidate_or_government':", candidate_or_gov_counts)
        log_counts("3. Records by 'party':", party_counts)
        log_counts("4. Records by 'parliament_session_id':", parliament_session_counts)
        log_counts("5. Records by 'source_type':", source_type_counts)
        log_counts("6. Records by 'implied_action_type':", implied_action_type_counts)
        log_counts("7. Records by 'bc_promise_rank':", bc_promise_rank_counts)
        log_counts("8. Records by 'bc_promise_direction':", bc_promise_direction_counts)
        log_counts("9. Records by 'responsible_department_lead':", responsible_dept_counts)
        log_counts("10. Records by 'category':", category_counts)
        
        logger.info("11. Promises linked to evidence:")
        logger.info(f"  - With linked evidence: {promises_with_evidence_count}")
        logger.info(f"  - Without linked evidence: {promises_without_evidence_count}")


    except Exception as e:
        logger.error(f"Error during Firestore query or processing: {e}", exc_info=True)

    logger.info(f"--- Data Overview Finished for Collection Group '{PROMISES_COLLECTION}' ---")

if __name__ == "__main__":
    from dotenv import load_dotenv
    load_dotenv() # Load .env file for GOOGLE_APPLICATION_CREDENTIALS if not set globally
    analyze_promises_data() # Updated function call 