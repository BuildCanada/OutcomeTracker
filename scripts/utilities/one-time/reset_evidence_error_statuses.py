import firebase_admin
from firebase_admin import credentials, firestore
import os
import logging
from dotenv import load_dotenv

# --- Load Environment Variables ---
load_dotenv(dotenv_path=os.path.join(os.path.dirname(__file__), '..', '..', '.env')) # Look for .env in the project root
# --- End Load Environment Variables ---

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
        cred_path = os.getenv('GOOGLE_APPLICATION_CREDENTIALS')
        if not cred_path:
            logger.critical("GOOGLE_APPLICATION_CREDENTIALS environment variable not set. Exiting.")
            exit("Exiting: GOOGLE_APPLICATION_CREDENTIALS not set.")
        
        # Ensure the path is absolute or correctly relative to the script's execution directory
        if not os.path.isabs(cred_path):
            # This assumes the script is run from the workspace root or GOOGLE_APPLICATION_CREDENTIALS is set absolutely
            # If cred_path is relative, it needs to be relative to where you run the script from,
            # or you should adjust its path.
            pass

        cred = credentials.Certificate(cred_path)
        firebase_admin.initialize_app(cred)
        logger.info("Firebase Admin SDK initialized using Application Credentials.")
        
        project_id = os.getenv('FIREBASE_PROJECT_ID', firebase_admin.get_app().project_id if firebase_admin.get_app() else '[Cloud Project ID Not Set]')
        logger.info(f"Connected to CLOUD Firestore (Project: {project_id}).")
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
EVIDENCE_ITEMS_COLLECTION = 'evidence_items' # Make sure this matches your collection name
ERROR_STATUS_TO_RESET = 'error_processing'   # The status you want to find
NEW_STATUS = 'pending'                       # The status to set
BATCH_SIZE = 50                             # Number of documents to update in a single batch
# --- End Constants ---

def reset_error_statuses():
    """
    Finds evidence items with a specific error status and resets them to 'pending'.
    """
    logger.info(f"--- Starting Reset Process for Evidence Items with status '{ERROR_STATUS_TO_RESET}' ---")

    docs_to_reset_query = (db.collection(EVIDENCE_ITEMS_COLLECTION)
                           .where(filter=firestore.FieldFilter('promise_linking_status', '==', ERROR_STATUS_TO_RESET)))
    
    docs_stream = docs_to_reset_query.stream()
    
    batch = db.batch()
    reset_count = 0
    total_queried_count = 0
    batch_item_count = 0

    for doc in docs_stream:
        total_queried_count += 1
        logger.info(f"Found document {doc.id} with status '{ERROR_STATUS_TO_RESET}'. Adding to batch for update.")
        
        update_data = {
            'promise_linking_status': NEW_STATUS,
            'promise_linking_error_message': None  # Clear the previous error message
            # Optionally, you could set a field like 'promise_linking_reset_at': firestore.SERVER_TIMESTAMP
        }
        batch.update(doc.reference, update_data)
        batch_item_count += 1
        
        if batch_item_count >= BATCH_SIZE:
            logger.info(f"Committing batch of {batch_item_count} updates...")
            try:
                batch.commit()
                logger.info(f"Successfully committed batch.")
                reset_count += batch_item_count
            except Exception as e:
                logger.error(f"Error committing batch: {e}", exc_info=True)
            # Start a new batch
            batch = db.batch()
            batch_item_count = 0

    # Commit any remaining items in the last batch
    if batch_item_count > 0:
        logger.info(f"Committing final batch of {batch_item_count} updates...")
        try:
            batch.commit()
            logger.info(f"Successfully committed final batch.")
            reset_count += batch_item_count
        except Exception as e:
            logger.error(f"Error committing final batch: {e}", exc_info=True)

    logger.info("--- Reset Process Finished ---")
    logger.info(f"Total documents queried with status '{ERROR_STATUS_TO_RESET}': {total_queried_count}")
    logger.info(f"Total documents successfully reset to '{NEW_STATUS}': {reset_count}")

    if total_queried_count != reset_count:
        logger.warning("Warning: Not all queried documents may have been reset due to batch commit errors. Check logs.")

if __name__ == "__main__":
    # Confirm with the user before proceeding
    confirm = input(
        f"This script will find all documents in '{EVIDENCE_ITEMS_COLLECTION}' "
        f"with promise_linking_status = '{ERROR_STATUS_TO_RESET}' "
        f"and update their status to '{NEW_STATUS}', clearing 'promise_linking_error_message'.\n"
        "Are you sure you want to proceed? (yes/no): "
    )
    if confirm.lower() == 'yes':
        reset_error_statuses()
    else:
        logger.info("Operation cancelled by the user.")
