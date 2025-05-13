import firebase_admin
from firebase_admin import credentials
from firebase_admin import firestore
import logging
import re
import os
from dotenv import load_dotenv

load_dotenv()

# Attempt to import DEPARTMENT_MAP from common_utils
# Assuming common_utils.py is in the same directory or Python path
try:
    from common_utils import DEPARTMENT_MAP
except ImportError:
    logging.error("Failed to import DEPARTMENT_MAP from common_utils.py. Ensure the file exists and is accessible.")
    exit(1)

# --- Firebase Configuration ---
# SERVICE_ACCOUNT_KEY_PATH = "promisetrackerapp-firebase-adminsdk-fbsvc-6a44bafc23.json" # No longer directly used for init
# PROJECT_ID = "promisetrackerapp" 

# --- Logging Configuration ---
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(filename)s:%(lineno)d - %(message)s')
logger = logging.getLogger(__name__) # Use a named logger

def sanitize_for_doc_id(name):
    """Converts a string to a Firestore-friendly document ID."""
    s = name.lower()
    s = re.sub(r'\s+', '-', s)  # Replace spaces with hyphens
    s = re.sub(r'[^a-z0-9\-]', '', s)  # Remove disallowed characters
    s = s.strip('-')
    return s if s else None

def get_firestore_db():
    """Initializes Firebase Admin SDK (if not already) and returns a Firestore client."""
    db_client = None
    if not firebase_admin._apps:
        logger.info("Firebase app not initialized. Attempting to initialize...")
        if not os.getenv('GOOGLE_APPLICATION_CREDENTIALS'):
            logger.critical("GOOGLE_APPLICATION_CREDENTIALS environment variable not set.")

            return None # Strict: require env var if not initialized
        try:
            firebase_admin.initialize_app()
            logger.info("Firebase Admin SDK initialized successfully using GOOGLE_APPLICATION_CREDENTIALS.")
            db_client = firestore.client()
        except Exception as e:
            logger.critical(f"Firebase initialization failed: {e}", exc_info=True)
            return None
    else:
        logger.info("Firebase app already initialized. Getting Firestore client.")
        db_client = firestore.client()
    
    if db_client is None:
         logger.critical("Failed to obtain Firestore client.")
    return db_client

def populate_department_config():
    """
    Populates the 'department_config' Firestore collection with unique department
    short names and their full names from DEPARTMENT_MAP.
    """
    db = get_firestore_db()
    if not db:
        logger.error("Firestore client not available. Exiting populate_department_config.")
        return

    logger.info("Firestore client obtained for populate_department_config.")

    departments_to_write = {}  # Using dict to ensure unique shortName-derived doc IDs

    for ministerial_title, dept_info in DEPARTMENT_MAP.items():
        if not isinstance(dept_info, dict) or 'short' not in dept_info or 'full' not in dept_info:
            logger.warning(f"Skipping malformed entry for title '{ministerial_title}': {dept_info}")
            continue

        short_name = dept_info['short']
        full_name = dept_info['full']

        if full_name == "Multiple Departments - Needs Review" or short_name == "Multiple":
            logger.info(f"Skipping special case department: Short='{short_name}', Full='{full_name}'")
            continue
        
        if not short_name or not full_name:
            logger.warning(f"Skipping entry with missing short_name or full_name for title '{ministerial_title}': Short='{short_name}', Full='{full_name}'")
            continue

        doc_id = sanitize_for_doc_id(short_name)
        if not doc_id:
            logger.warning(f"Could not generate valid doc_id for short_name '{short_name}'. Skipping.")
            continue

        if doc_id not in departments_to_write:
            departments_to_write[doc_id] = {
                "shortName": short_name,
                "fullName": full_name
            }
            logger.info(f"Prepared department: ID='{doc_id}', Short='{short_name}', Full='{full_name}'")
        else:
            pass # Prioritizes first encountered mapping

    if not departments_to_write:
        logger.info("No valid department data to write to Firestore.")
        return

    logger.info(f"Starting batch write for {len(departments_to_write)} department configurations...")
    batch = db.batch()
    for doc_id, data in departments_to_write.items():
        try:
            dept_ref = db.collection('department_config').document(doc_id)
            batch.set(dept_ref, data)
            logger.debug(f"Added to batch: {doc_id} -> {data}")
        except Exception as e:
            logger.error(f"Error preparing batch for doc_id '{doc_id}': {e}")
    
    try:
        results = batch.commit()
        # Firestore batch commit returns a list of WriteResults, len(results) would be the count of successful operations
        logger.info(f"Successfully wrote {len(results)} department configurations to Firestore collection 'department_config'.") 
    except Exception as e:
        logger.error(f"Error committing batch to Firestore: {e}")

if __name__ == "__main__":
    if 'DEPARTMENT_MAP' not in globals():
        logger.error("DEPARTMENT_MAP is not available. Exiting.")
    else:
        populate_department_config() 