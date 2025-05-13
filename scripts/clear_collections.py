# scripts/clear_collection.py

import firebase_admin
from firebase_admin import firestore
import os
import argparse
import sys
import logging 
import traceback
from dotenv import load_dotenv

load_dotenv()

# --- Logger Setup --- 
logging.basicConfig(level=logging.INFO, 
                    format='%(asctime)s - %(levelname)s - %(filename)s:%(lineno)d - %(message)s',
                    datefmt='%Y-%m-%d %H:%M:%S')
logger = logging.getLogger(__name__)
# --- End Logger Setup ---

# --- Firebase Configuration ---
# Initialize db variable to None initially
db = None 
if not firebase_admin._apps:
    # Cloud Firestore initialization
    # GOOGLE_APPLICATION_CREDENTIALS environment variable must be set
    if not os.getenv('GOOGLE_APPLICATION_CREDENTIALS'):
        logger.critical("GOOGLE_APPLICATION_CREDENTIALS environment variable not set.")
        logger.critical("This is required for authentication with Google Cloud Firestore.")
        exit("Exiting: GOOGLE_APPLICATION_CREDENTIALS not set.")
    try:
        firebase_admin.initialize_app() # Default initialization for cloud
        logger.info("Successfully connected to Google Cloud Firestore.")
        db = firestore.client() # Assign the client to db
    except Exception as e:
        logger.critical(f"Firebase initialization failed for Google Cloud Firestore: {e}", exc_info=True)
        exit("Exiting: Firebase connection failed.")
else:
    logger.info("Firebase app already initialized. Getting client for Google Cloud Firestore.")
    db = firestore.client() # Get client if already initialized

# Final check if db is assigned
if db is None:
     logger.critical("Failed to obtain Firestore client after attempting cloud connection. Exiting.")
     exit("Exiting: Firestore client not available.")
# --- End Firebase Configuration ---

# --- Constants ---
BATCH_SIZE = 499 # Firestore batch limit is 500, stay slightly under
# --- End Constants ---


def delete_collection(collection_ref, batch_size):
    """
    Deletes all documents in a Firestore collection in batches.
    """
    docs = collection_ref.limit(batch_size).stream()
    deleted_count = 0
    batch_count = 0
    total_deleted = 0

    while True:
        batch = db.batch()
        docs_in_batch = 0
        
        # Consume the stream generator for the current batch
        try:
            for doc in docs:
                logger.debug(f"Adding doc {doc.id} to delete batch.")
                batch.delete(doc.reference)
                docs_in_batch += 1
            
            if docs_in_batch == 0:
                logger.info("No more documents found to delete.")
                break # Exit the loop if no documents were found in this iteration

            logger.info(f"Committing batch {batch_count + 1} with {docs_in_batch} documents...")
            batch.commit()
            deleted_count += docs_in_batch
            batch_count += 1
            total_deleted += docs_in_batch
            logger.info(f"Batch {batch_count} committed. {deleted_count} documents deleted in this batch.")
            
            # After committing, prepare for the next potential batch
            # Re-fetch the next batch of documents
            docs = collection_ref.limit(batch_size).stream()
            deleted_count = 0 # Reset counter for the next potential batch status message

        except Exception as e:
            logger.error(f"Error during batch deletion (Batch {batch_count + 1}): {e}", exc_info=True)
            logger.error("Aborting further deletions for safety.")
            break

    logger.info(f"Finished deleting collection. Total documents deleted: {total_deleted}")
    return total_deleted


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Clear all documents from a specific Firestore collection (use with emulator!).")
    parser.add_argument("collection_name", help="The name of the Firestore collection to clear.")
    
    args = parser.parse_args()
    collection_name = args.collection_name

    logger.warning(f"--- WARNING ---")
    logger.warning(f"You are about to delete ALL documents from the collection named '{collection_name}'.")
    logger.warning(f"This script will target your CLOUD FIRESTORE INSTANCE if GOOGLE_APPLICATION_CREDENTIALS is set.")
    logger.warning(f"Ensure GOOGLE_APPLICATION_CREDENTIALS points to the correct project or is not set if you intend to use an emulator (which is no longer the default).")
    # logger.warning(f"Targeting Firestore at: {os.getenv('FIRESTORE_EMULATOR_HOST', 'NOT SET - DANGER!')}") # Commented out emulator specific log
    
    # Confirmation Prompt
    confirmation = input("Type the collection name exactly to confirm deletion: ")
    
    if confirmation != collection_name:
        logger.info("Confirmation mismatch. Aborting deletion.")
        sys.exit()
        
    logger.info(f"Proceeding with deletion of collection '{collection_name}'...")
    
    try:
        collection_ref = db.collection(collection_name)
        # Check if collection exists by trying to get one document (optional but good practice)
        # Note: This adds one read operation
        check_docs = collection_ref.limit(1).stream()
        if not list(check_docs):
             logger.info(f"Collection '{collection_name}' appears to be empty already or does not exist.")
        else:
             logger.info(f"Collection '{collection_name}' found. Starting deletion process...")
             # Reset reference before passing to delete function
             collection_ref = db.collection(collection_name) 
             delete_collection(collection_ref, BATCH_SIZE)
             
    except Exception as e:
        logger.error(f"An unexpected error occurred: {e}", exc_info=True)

    logger.info("Script finished.")