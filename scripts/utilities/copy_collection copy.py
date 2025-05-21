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
        cred_path_env = os.getenv('GOOGLE_APPLICATION_CREDENTIALS')
        if cred_path_env:
            logger.info(f"Attempting Firebase init with GOOGLE_APPLICATION_CREDENTIALS: {cred_path_env}")
            cred = credentials.Certificate(cred_path_env)
            firebase_admin.initialize_app(cred)
        else:
            logger.info("GOOGLE_APPLICATION_CREDENTIALS not set. Attempting init with default app credentials (ADC or service account implicitly).")
            firebase_admin.initialize_app() # For ADC or implicit service account in GCP environment
        
        project_id = firebase_admin.get_app().project_id if firebase_admin.get_app() else os.getenv('FIREBASE_PROJECT_ID', '[Project ID Not Detected]')
        logger.info(f"Python (Copy Collection): Connected to CLOUD Firestore (Project: {project_id}).")
        db = firestore.client()
    except Exception as e_init:
        logger.warning(f"Initial Firebase init attempt failed: {e_init}")
        # Fallback to explicit service account key path if primary methods fail
        cred_path_sa = os.getenv('FIREBASE_SERVICE_ACCOUNT_KEY_PATH')
        if cred_path_sa:
            try:
                logger.info(f"Attempting Firebase init with explicit service account key: {cred_path_sa}")
                cred = credentials.Certificate(cred_path_sa)
                # Check if default app already exists from a failed attempt
                if not firebase_admin._apps: 
                    firebase_admin.initialize_app(cred)
                else: # Re-initialize with specific creds if default app exists but didn't work
                    firebase_admin.initialize_app(cred, name='explicit_sa_app')
                db = firestore.client(app=firebase_admin.get_app(name='explicit_sa_app') if 'explicit_sa_app' in firebase_admin._apps else None)
                project_id = firebase_admin.get_app(name='explicit_sa_app').project_id if 'explicit_sa_app' in firebase_admin._apps else os.getenv('FIREBASE_PROJECT_ID', '[Project ID Not Detected]')
                logger.info(f"Python (Copy Collection): Connected to CLOUD Firestore (Project: {project_id}) via explicit service account.")
            except Exception as e_sa_init:
                logger.critical(f"Firebase init with explicit service account key also failed: {e_sa_init}", exc_info=True)
                db = None
        else:
            logger.warning("FIREBASE_SERVICE_ACCOUNT_KEY_PATH not set, cannot fallback to explicit SA key.")
            db = None
else:
    # App already initialized, assume db client is available or can be re-fetched
    db = firestore.client()
    project_id = firebase_admin.get_app().project_id if firebase_admin.get_app() else os.getenv('FIREBASE_PROJECT_ID', '[Project ID Not Detected]')
    logger.info(f"Firebase Admin SDK already initialized. Connected to Firestore (Project: {project_id}).")

if db is None:
    logger.critical("Failed to obtain Firestore client after all attempts. Exiting.")
    exit("Exiting: Firestore client not available.")
# --- End Firebase Configuration ---

def _recursive_copy_logic(source_coll_ref: firestore.CollectionReference, 
                            dest_coll_ref: firestore.CollectionReference):
    """
    Recursively copies documents from source_coll_ref to dest_coll_ref,
    and all their subcollections.
    Based on user-provided logic.
    """
    current_source_path_for_logging = source_coll_ref.parent.path + "/" + source_coll_ref.id if source_coll_ref.parent else source_coll_ref.id
    logger.info(f"Processing documents in source collection: {current_source_path_for_logging}")
    
    docs_processed_at_this_level = 0
    for doc_snap in source_coll_ref.stream():
        # 1) Copy this document's data
        document_data = doc_snap.to_dict()
        dest_doc_ref = dest_coll_ref.document(doc_snap.id)
        
        # Perform the set operation (equivalent to a single batch item)
        dest_doc_ref.set(document_data)
        logger.debug(f"Copied document: {doc_snap.reference.path} to {dest_doc_ref.path}")
        docs_processed_at_this_level += 1

        # 2) For each subcollection under this doc, recurse
        for subcollection_ref in doc_snap.reference.collections():
            logger.info(f"Found subcollection: {subcollection_ref.id} under {doc_snap.reference.path}. Starting recursion.")
            dest_subcollection_ref = dest_doc_ref.collection(subcollection_ref.id)
            _recursive_copy_logic(subcollection_ref, dest_subcollection_ref)
    
    if docs_processed_at_this_level > 0:
        logger.info(f"Finished processing {docs_processed_at_this_level} documents in source collection: {current_source_path_for_logging}")
    else:
        logger.info(f"No documents found directly in source collection: {current_source_path_for_logging}")

def copy_collection(source_collection_name, destination_collection_name):
    logger.info(f"Starting recursive copy from '{source_collection_name}' to '{destination_collection_name}'.")

    source_top_ref = db.collection(source_collection_name)
    destination_top_ref = db.collection(destination_collection_name)

    # Check if destination collection has documents at the top level
    docs_in_dest = list(destination_top_ref.limit(1).stream())
    if docs_in_dest:
        confirm = input(f"WARNING: Destination collection '{destination_collection_name}' appears to have data at its top level. "
                        f"Continuing will add/overwrite documents. Proceed? (yes/no): ")
        if confirm.lower() != 'yes':
            logger.info("Copy operation aborted by user.")
            return
    
    total_docs_copied_this_run = 0 # Simple counter, can be enhanced if needed

    try:
        # We need a way to count total documents if we want to log it.
        # The pure recursive function doesn't return counts. We can wrap it or pass a mutable counter.
        # For now, let's just call it. The internal logging will show progress.
        _recursive_copy_logic(source_top_ref, destination_top_ref)
        
        # Since the recursive function doesn't return a count, we can't easily log a total here
        # without re-querying or passing a mutable object (like a list [0]) into the recursion.
        # The user's example also just prints "Done copying".
        logger.info(f"Recursive copy process from '{source_collection_name}' to '{destination_collection_name}' initiated and ran.")
        logger.info("Check logs above for details on processed collections and documents.")

    except Exception as e:
        logger.error(f"Error during recursive collection copy: {e}", exc_info=True)
        logger.error(f"Operation may be incomplete. Check Firestore and logs.")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Recursively copy a Firestore collection and its subcollections.")
    parser.add_argument("source_collection_name", help="Name of the source Firestore collection.")
    parser.add_argument("destination_collection_name", help="Name of the destination Firestore collection.")
    
    args = parser.parse_args()

    logger.info(f"--- Starting Firestore Recursive Collection Copy Utility ---")
    logger.info(f"Source Collection Path: {args.source_collection_name}")
    logger.info(f"Destination Collection Path: {args.destination_collection_name}")

    copy_collection(args.source_collection_name, args.destination_collection_name)

    logger.info(f"--- Firestore Recursive Collection Copy Utility Finished ---") 