#!/usr/bin/env python
# scripts/copy_collection.py

import firebase_admin
from firebase_admin import firestore, credentials
import os
import argparse
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

# --- Firebase Configuration ---
db = None
if not firebase_admin._apps:
    try:
        # Attempt to initialize with application default credentials
        firebase_admin.initialize_app()
        project_id = os.getenv('FIREBASE_PROJECT_ID', '[Not Set - Using Default]')
        logger.info(f"Python (Copy Collection): Connected to CLOUD Firestore (Project: {project_id}).")
        db = firestore.client()
    except Exception as e_default:
        logger.warning(f"Cloud Firestore init with default creds failed: {e_default}")
        logger.warning("Ensure GOOGLE_APPLICATION_CREDENTIALS env var is set for default auth.")
        logger.warning("Or, set FIREBASE_SERVICE_ACCOUNT_KEY_PATH for service account key file auth.")
        
        # Fallback to service account key if path is provided
        cred_path = os.getenv('FIREBASE_SERVICE_ACCOUNT_KEY_PATH')
        if cred_path:
            try:
                logger.info(f"Attempting Firebase init with service account key: {cred_path}")
                cred = credentials.Certificate(cred_path)
                firebase_admin.initialize_app(cred)
                project_id = os.getenv('FIREBASE_PROJECT_ID', '[Not Set - Using Service Account]')
                logger.info(f"Python (Copy Collection): Connected to CLOUD Firestore (Project: {project_id}) via service account.")
                db = firestore.client()
            except Exception as e_sa:
                logger.critical(f"Firebase init with service account key failed: {e_sa}", exc_info=True)
                db = None # Ensure db is None if all attempts fail
        else:
            db = None # Ensure db is None if no cred_path

if db is None:
    logger.critical("Failed to obtain Firestore client after all attempts. Exiting.")
    exit("Exiting: Firestore client not available.")
# --- End Firebase Configuration ---

def copy_collection(source_collection_name, destination_collection_name):
    """
    Copies all documents from a source Firestore collection to a destination collection.
    """
    logger.info(f"Starting copy from '{source_collection_name}' to '{destination_collection_name}'.")

    source_ref = db.collection(source_collection_name)
    destination_ref = db.collection(destination_collection_name)

    # Check if destination collection has documents
    docs_in_dest = list(destination_ref.limit(1).stream())
    if docs_in_dest:
        confirm = input(f"WARNING: Destination collection '{destination_collection_name}' is not empty. "
                        f"Continuing will add/overwrite documents. Proceed? (yes/no): ")
        if confirm.lower() != 'yes':
            logger.info("Copy operation aborted by user.")
            return

    docs_copied_count = 0
    batch = db.batch()
    docs_in_batch = 0

    try:
        source_docs = source_ref.stream()
        for doc in source_docs:
            destination_doc_ref = destination_ref.document(doc.id)
            batch.set(destination_doc_ref, doc.to_dict())
            docs_in_batch += 1
            docs_copied_count +=1

            if docs_in_batch >= 400: # Firestore batch limit is 500
                logger.info(f"Committing batch of {docs_in_batch} documents...")
                batch.commit()
                batch = db.batch() # Start a new batch
                docs_in_batch = 0
                logger.info(f"So far, {docs_copied_count} documents processed.")

        if docs_in_batch > 0: # Commit any remaining documents in the last batch
            logger.info(f"Committing final batch of {docs_in_batch} documents...")
            batch.commit()
        
        logger.info(f"Successfully copied {docs_copied_count} documents from "
                    f"'{source_collection_name}' to '{destination_collection_name}'.")

    except Exception as e:
        logger.error(f"Error during collection copy: {e}", exc_info=True)
        logger.error(f"Operation may be incomplete. {docs_copied_count} documents were processed before error.")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Copy a Firestore collection to another.")
    parser.add_argument("source_collection_name", help="Name of the source Firestore collection.")
    parser.add_argument("destination_collection_name", help="Name of the destination Firestore collection.")
    
    args = parser.parse_args()

    logger.info(f"--- Starting Firestore Collection Copy Utility ---")
    logger.info(f"Source Collection: {args.source_collection_name}")
    logger.info(f"Destination Collection: {args.destination_collection_name}")

    copy_collection(args.source_collection_name, args.destination_collection_name)

    logger.info(f"--- Firestore Collection Copy Utility Finished ---") 