import firebase_admin
from firebase_admin import credentials, firestore
import os
from dotenv import load_dotenv
import logging
import time

# Load environment variables from .env file
load_dotenv()

# --- Logger Setup ---
logging.basicConfig(level=logging.INFO,
                    format='%(asctime)s - %(levelname)s - %(filename)s:%(lineno)d - %(message)s',
                    datefmt='%Y-%m-%d %H:%M:%S')
logger = logging.getLogger(__name__) # Use __name__ for logger
# --- End Logger Setup ---

def initialize_firestore():
    """Initializes Firestore connection using environment variables, mirroring enrich_tag_new_promise.py."""
    db_client = None
    try:
        # Attempt to initialize with default credentials first (e.g., for Cloud Functions, local ADC)
        if not firebase_admin._apps:
            firebase_admin.initialize_app()
        project_id = os.getenv('FIREBASE_PROJECT_ID', '[Not Set - Using Default]')
        logger.info(f"Attempting Firestore connection (Project: {project_id}) using default credentials.")
        db_client = firestore.client()
        logger.info(f"Successfully connected to Firestore using default credentials.")
        return db_client
    except Exception as e_default:
        logger.warning(f"Firestore init with default creds failed: {e_default}. Attempting service account.")
        cred_path = os.getenv("FIREBASE_ADMIN_SDK_PATH") # Changed from FIREBASE_SERVICE_ACCOUNT_KEY_PATH for consistency if desired, or keep as is
        if not cred_path:
            logger.critical("FIREBASE_ADMIN_SDK_PATH environment variable not set and default creds failed.")
            raise ValueError("FIREBASE_ADMIN_SDK_PATH environment variable not set.")
        
        if not os.path.exists(cred_path):
            logger.critical(f"Firebase Admin SDK file not found at {cred_path}")
            raise FileNotFoundError(f"Firebase Admin SDK file not found at {cred_path}")

        try:
            logger.info(f"Attempting Firebase init with service account key from: {cred_path}")
            cred = credentials.Certificate(cred_path)
            
            # Ensure app is initialized, potentially with a unique name if default exists
            app_name = 'initialize_promise_fields_app'
            if firebase_admin.DEFAULT_APP_NAME not in firebase_admin._apps:
                 firebase_admin.initialize_app(cred) # Initialize default app
            elif not any(app.name == app_name for app in firebase_admin._apps.values()):
                 firebase_admin.initialize_app(cred, name=app_name)
            
            current_app = firebase_admin.get_app(name=app_name if any(app.name == app_name for app in firebase_admin._apps.values()) else firebase_admin.DEFAULT_APP_NAME)
            project_id_sa = current_app.project_id or os.getenv('FIREBASE_PROJECT_ID', '[Not Set - Using Service Account]')
            logger.info(f"Connected to Firestore (Project: {project_id_sa}) via service account using app: {current_app.name}.")
            db_client = firestore.client(app=current_app)
            return db_client

        except Exception as e_sa:
            logger.critical(f"Firebase init with service account key from {cred_path} failed: {e_sa}", exc_info=True)
            raise

def initialize_promise_fields(db):
    """
    Initializes new fields (bc_promise_rank, bc_promise_direction, bc_promise_rank_rationale)
    to None for all documents in the 'promises/Canada/LPC' collection.
    """
    # Target the specific collection where promises are stored, matching rank_promise_priority.py
    target_collection_path = "promises/Canada/LPC" 
    logger.info(f"Targeting Firestore collection for initialization: {target_collection_path}")
    promises_ref = db.collection(target_collection_path)
    promises = promises_ref.stream()
    updated_count = 0
    batch_size = 100  # Firestore batch limit is 500 operations
    batch = db.batch()
    operations_in_batch = 0

    print("Starting to initialize promise fields...")

    for promise_doc in promises:
        doc_ref = promises_ref.document(promise_doc.id)
        update_data = {
            'bc_promise_rank': None,
            'bc_promise_direction': None,
            'bc_promise_rank_rationale': None
        }
        
        # Check if fields already exist to avoid unnecessary writes (optional, but good practice)
        # For a one-time script, direct update is fine too.
        # if not all(field in promise_doc.to_dict() for field in update_data.keys()):

        batch.update(doc_ref, update_data)
        operations_in_batch += 1
        updated_count += 1

        if operations_in_batch >= batch_size:
            print(f"Committing batch of {operations_in_batch} updates...")
            batch.commit()
            print(f"Batch committed. Total updated so far: {updated_count}")
            batch = db.batch() # Start a new batch
            operations_in_batch = 0
        
        if updated_count % 10 == 0:
            print(f"Processed {updated_count} promises...")
            logger.info(f"Processed {updated_count} promises so far in {target_collection_path}...")


    if operations_in_batch > 0: # Commit any remaining operations in the last batch
        print(f"Committing final batch of {operations_in_batch} updates...")
        batch.commit()
        print(f"Final batch committed.")
        logger.info(f"Final batch of {operations_in_batch} committed for {target_collection_path}.")

    print(f"Initialization complete. {updated_count} promises had fields initialized in {target_collection_path}.")
    logger.info(f"Initialization complete for {target_collection_path}. {updated_count} promises had fields initialized.")

if __name__ == "__main__":
    try:
        db = initialize_firestore()
        if db:
            initialize_promise_fields(db)
        else:
            logger.critical("Failed to initialize Firestore. Aborting.")
    except Exception as e:
        logger.critical(f"An error occurred in main execution: {e}", exc_info=True) 