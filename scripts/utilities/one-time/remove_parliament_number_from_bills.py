import firebase_admin
from firebase_admin import credentials, firestore
import os
import logging
from dotenv import load_dotenv
import argparse

# --- Load Environment Variables ---
load_dotenv()
# --- End Load Environment Variables ---

# --- Logger Setup ---
logging.basicConfig(level=logging.INFO,
                    format='%(asctime)s - %(levelname)s - %(filename)s:%(lineno)d - %(message)s',
                    datefmt='%Y-%m-%d %H:%M:%S')
logger = logging.getLogger(__name__)
# --- End Logger Setup ---

# --- Firebase Initialization ---
db = None
def initialize_firestore():
    """Initializes the Firestore client, trying default and then service account key."""
    global db
    if firebase_admin._apps:
        logger.info("Firebase app already initialized.")
        db = firestore.client()
        return

    try:
        # Try to initialize with application default credentials (useful in GCP environments)
        firebase_admin.initialize_app()
        project_id = os.getenv('FIREBASE_PROJECT_ID', firebase_admin.get_app().project_id if firebase_admin.get_app() else '[Cloud Project ID Not Set]')
        logger.info(f"Successfully initialized Firebase with Application Default Credentials (Project: {project_id}).")
        db = firestore.client()
    except Exception as e_default:
        logger.warning(f"Firebase init with Application Default Credentials failed: {e_default}")
        # Fallback to service account key if default credentials fail
        service_account_key_path = os.getenv('FIREBASE_SERVICE_ACCOUNT_KEY_PATH')
        if service_account_key_path:
            logger.info(f"Attempting Firebase init with service account key: {service_account_key_path}")
            try:
                cred = credentials.Certificate(service_account_key_path)
                firebase_admin.initialize_app(cred)
                project_id = os.getenv('FIREBASE_PROJECT_ID', firebase_admin.get_app().project_id if firebase_admin.get_app() else '[Cloud Project ID Not Set]')
                logger.info(f"Successfully initialized Firebase with Service Account Key (Project: {project_id}).")
                db = firestore.client()
            except Exception as e_sa:
                logger.critical(f"Firebase init with Service Account Key failed: {e_sa}", exc_info=True)
                db = None # Ensure db is None if SA key also fails
        else:
            logger.warning("FIREBASE_SERVICE_ACCOUNT_KEY_PATH not set. Cannot initialize Firebase with service account key.")
            db = None

    if db is None:
        logger.critical("Failed to initialize Firestore client. Exiting.")
        exit("Exiting: Firestore client could not be initialized.")

# --- End Firebase Initialization ---

COLLECTION_NAME = 'bills_data'
FIELD_TO_REMOVE = 'parliament_number'

def remove_field_from_bills(dry_run=False):
    """
    Iterates through all documents in the 'bills_data' collection
    and removes the 'parliament_number' field.
    """
    initialize_firestore()
    if db is None:
        logger.error("Firestore client not available. Aborting.")
        return

    logger.info(f"Starting removal of field '{FIELD_TO_REMOVE}' from collection '{COLLECTION_NAME}'. Dry run: {dry_run}")

    bills_ref = db.collection(COLLECTION_NAME)
    docs_processed = 0
    docs_updated = 0
    batch_size = 200  # Firestore batch limit is 500 operations, update is 1 operation.
    batch = db.batch()
    operations_in_batch = 0

    try:
        for doc_snapshot in bills_ref.stream():
            docs_processed += 1
            doc_id = doc_snapshot.id
            bill_data = doc_snapshot.to_dict()

            if FIELD_TO_REMOVE in bill_data:
                logger.info(f"Document '{doc_id}' contains field '{FIELD_TO_REMOVE}'. Value: {bill_data.get(FIELD_TO_REMOVE)}")
                if not dry_run:
                    doc_ref = bills_ref.document(doc_id)
                    batch.update(doc_ref, {FIELD_TO_REMOVE: firestore.DELETE_FIELD})
                    operations_in_batch += 1
                    docs_updated += 1
                    logger.info(f"  Scheduled removal of '{FIELD_TO_REMOVE}' for document '{doc_id}'.")

                    if operations_in_batch >= batch_size:
                        logger.info(f"Committing batch of {operations_in_batch} updates...")
                        batch.commit()
                        logger.info("Batch committed.")
                        batch = db.batch() # Start a new batch
                        operations_in_batch = 0
                else:
                    logger.info(f"  [DRY RUN] Would remove '{FIELD_TO_REMOVE}' from document '{doc_id}'.")
            else:
                logger.info(f"Document '{doc_id}' does not contain field '{FIELD_TO_REMOVE}'. Skipping.")

        if operations_in_batch > 0 and not dry_run:
            logger.info(f"Committing final batch of {operations_in_batch} updates...")
            batch.commit()
            logger.info("Final batch committed.")

        logger.info(f"Script finished. Processed {docs_processed} documents.")
        if not dry_run:
            logger.info(f"Updated {docs_updated} documents by removing field '{FIELD_TO_REMOVE}'.")
        else:
            logger.info(f"[DRY RUN] Would have updated {docs_updated} documents (if they contained the field).")

    except Exception as e:
        logger.error(f"An error occurred during processing: {e}", exc_info=True)

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=f"Remove the '{FIELD_TO_REMOVE}' field from all documents in the '{COLLECTION_NAME}' Firestore collection.")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Simulate the removal process without actually modifying Firestore data."
    )
    args = parser.parse_args()

    remove_field_from_bills(dry_run=args.dry_run) 