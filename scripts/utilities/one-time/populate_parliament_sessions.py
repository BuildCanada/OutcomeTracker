import json
import firebase_admin
from firebase_admin import credentials, firestore
import os
import logging
from dotenv import load_dotenv

# --- Load Environment Variables ---
load_dotenv()
# --- End Load Environment Variables ---

# --- Logger Setup ---
logging.basicConfig(level=logging.INFO,
                    format='%(asctime)s - %(levelname)s - %(filename)s:%(lineno)d - %(message)s',
                    datefmt='%Y-%m-%d %H:%M:%S')
logger = logging.getLogger(__name__)
# --- End Logger Setup ---

# --- Configuration ---
# Determine the absolute path to the directory where this script is located
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))

# 1. Path to the JSON file containing the parliament session data
JSON_FILE_NAME = 'parliament_sessions_initial_data.json'
JSON_FILE_PATH = os.path.join(SCRIPT_DIR, JSON_FILE_NAME)

# 2. Name of the Firestore collection to populate
COLLECTION_NAME = 'parliament_session' # Updated collection name
# --- End Configuration ---

def initialize_firestore():
    """Initializes Firebase Admin SDK and returns a Firestore client instance."""
    db_client = None
    if not firebase_admin._apps:
        try:
            # Attempt to initialize with application default credentials
            firebase_admin.initialize_app()
            project_id = os.getenv('FIREBASE_PROJECT_ID', '[Not Set - Using Default]')
            logger.info(f"Successfully connected to CLOUD Firestore (Project: {project_id}) using default credentials.")
            db_client = firestore.client()
        except Exception as e_default:
            logger.warning(f"Cloud Firestore init with default creds failed: {e_default}")
            logger.warning("Ensure GOOGLE_APPLICATION_CREDENTIALS env var is set for default auth, or set FIREBASE_SERVICE_ACCOUNT_KEY_PATH.")
            
            # Fallback to service account key if path is provided via environment variable
            cred_path = os.getenv('FIREBASE_SERVICE_ACCOUNT_KEY_PATH')
            if cred_path:
                try:
                    logger.info(f"Attempting Firebase init with service account key from env var: {cred_path}")
                    cred = credentials.Certificate(cred_path)
                    firebase_admin.initialize_app(cred)
                    project_id_sa = os.getenv('FIREBASE_PROJECT_ID', '[Not Set - Using Service Account]')
                    logger.info(f"Successfully connected to CLOUD Firestore (Project: {project_id_sa}) via service account.")
                    db_client = firestore.client()
                except Exception as e_sa:
                    logger.critical(f"Firebase init with service account key from {cred_path} failed: {e_sa}", exc_info=True)
                    db_client = None
            else:
                logger.warning("FIREBASE_SERVICE_ACCOUNT_KEY_PATH environment variable not set. Cannot initialize Firestore.")
                db_client = None
    else:
        # If already initialized, get the default app's Firestore client
        logger.info("Firebase Admin SDK already initialized. Getting Firestore client.")
        db_client = firestore.client()
    
    return db_client

def populate_firestore():
    """Populates the Firestore collection with parliament session data."""
    db = initialize_firestore()
    if not db:
        logger.critical("Failed to initialize Firestore. Exiting population script.")
        return

    logger.info(f"Attempting to load data from: {JSON_FILE_PATH}")
    try:
        with open(JSON_FILE_PATH, 'r') as f:
            session_data_list = json.load(f) # Changed variable name
        logger.info(f"Successfully loaded data from {JSON_FILE_PATH}.")
    except FileNotFoundError:
        logger.error(f"JSON data file not found at {JSON_FILE_PATH}.")
        logger.error(f"Please ensure the file exists in the same directory as the script ({SCRIPT_DIR}).")
        return
    except json.JSONDecodeError as e:
        logger.error(f"Error decoding JSON from {JSON_FILE_PATH}: {e}")
        return
    except Exception as e:
        logger.error(f"An unexpected error occurred while reading {JSON_FILE_PATH}: {e}", exc_info=True)
        return

    if not isinstance(session_data_list, list):
        logger.error("Expected a list of session objects in the JSON file.") # Updated message
        return

    logger.info(f"Starting to populate Firestore collection '{COLLECTION_NAME}'...")
    batch_size = 250 
    batch = db.batch()
    docs_in_batch = 0
    total_docs_processed = 0
    total_docs_successful = 0

    for session_data in session_data_list: # Changed variable name
        if not isinstance(session_data, dict):
            logger.warning(f"Skipping invalid entry (not a dictionary): {session_data}")
            continue

        doc_id = session_data.get("parliament_number") # Use parliament_number for doc ID
        if not doc_id:
            logger.warning(f"Skipping entry due to missing 'parliament_number': {session_data}")
            continue

        # Data to upload is the session_data itself, no server timestamp for last_updated_at needed for this collection
        data_to_upload = session_data.copy()

        doc_ref = db.collection(COLLECTION_NAME).document(doc_id)
        batch.set(doc_ref, data_to_upload)
        docs_in_batch += 1
        total_docs_processed += 1

        if docs_in_batch >= batch_size:
            try:
                batch.commit()
                logger.info(f"Committed batch of {docs_in_batch} documents.")
                total_docs_successful += docs_in_batch
            except Exception as e:
                logger.error(f"Error committing batch of {docs_in_batch} documents: {e}", exc_info=True)
                # logger.error(f"Documents in this failed batch were: {list(batch._writes)}") # Be cautious with logging sensitive data
            finally:
                batch = db.batch() # Start a new batch
                docs_in_batch = 0

    # Commit any remaining documents in the last batch
    if docs_in_batch > 0:
        try:
            batch.commit()
            logger.info(f"Committed final batch of {docs_in_batch} documents.")
            total_docs_successful += docs_in_batch
        except Exception as e:
            logger.error(f"Error committing final batch of {docs_in_batch} documents: {e}", exc_info=True)
            # logger.error(f"Documents in this failed final batch were: {list(batch._writes)}") # Be cautious

    logger.info(f"Firestore population process complete for '{COLLECTION_NAME}'.")
    logger.info(f"Total documents processed: {total_docs_processed}")
    logger.info(f"Total documents successfully committed: {total_docs_successful}")

if __name__ == "__main__":
    populate_firestore() 