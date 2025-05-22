#!/usr/bin/env python
# PromiseTracker/scripts/delete_session_data.py
# This script deletes evidence items for a specified parliament session
# and cleans up linked promises.

import firebase_admin
from firebase_admin import firestore, credentials
import os
import asyncio
import logging
from dotenv import load_dotenv
import argparse
from typing import List, Dict, Any

# --- Load Environment Variables ---
load_dotenv()
# --- End Load Environment Variables ---

# --- Logger Setup ---
logging.basicConfig(level=logging.INFO,
                    format='%(asctime)s - %(levelname)s - %(filename)s:%(lineno)d - %(message)s',
                    datefmt='%Y-%m-%d %H:%M:%S')
logger = logging.getLogger("delete_session_data")
# --- End Logger Setup ---

# --- Firebase Configuration ---
db = None
if not firebase_admin._apps:
    try:
        firebase_admin.initialize_app()
        project_id = os.getenv('FIREBASE_PROJECT_ID', '[Not Set - Using Default]')
        logger.info(f"Connected to CLOUD Firestore (Project: {project_id}) using default credentials.")
        db = firestore.client()
    except Exception as e_default:
        logger.warning(f"Cloud Firestore init with default creds failed: {e_default}. Attempting service account.")
        cred_path = os.getenv('FIREBASE_SERVICE_ACCOUNT_KEY_PATH')
        if cred_path:
            try:
                logger.info(f"Attempting Firebase init with service account key from env var: {cred_path}")
                cred = credentials.Certificate(cred_path)
                app_name = 'delete_session_data_app'
                # Ensure unique app name if script is run multiple times in same process (unlikely for CLI)
                if app_name not in firebase_admin._apps:
                    firebase_admin.initialize_app(cred, name=app_name)
                else: # App already exists, get it
                    firebase_admin.get_app(name=app_name)
                
                project_id_sa = os.getenv('FIREBASE_PROJECT_ID', '[Not Set - Using Service Account]')
                logger.info(f"Connected to CLOUD Firestore (Project: {project_id_sa}) via service account.")
                db = firestore.client(app=firebase_admin.get_app(name=app_name))
            except Exception as e_sa:
                logger.critical(f"Firebase init with service account key from {cred_path} failed: {e_sa}", exc_info=True)
                exit(f"Exiting: Firebase service account init failed: {e_sa}")
        else:
            logger.warning("FIREBASE_SERVICE_ACCOUNT_KEY_PATH environment variable not set, and default creds failed.")

if db is None:
    logger.critical("CRITICAL: Failed to obtain Firestore client. Exiting.")
    exit("Exiting: Firestore client not available.")
# --- End Firebase Configuration ---

# --- Constants ---
PROMISES_COLLECTION_ROOT = os.getenv("TARGET_PROMISES_COLLECTION", "promises")
EVIDENCE_COLLECTION_NAME = "evidence_items"
DEFAULT_REGION_CODE = "Canada"
FIRESTORE_BATCH_LIMIT = 499 # Firestore batch limit is 500 operations
# --- End Constants ---

async def fetch_evidence_items_for_session(session_id_to_delete: str) -> List[Dict[str, Any]]:
    """Fetches evidence items for the specified parliament session."""
    logger.info(f"Fetching evidence items for parliament_session_id: '{session_id_to_delete}'")
    evidence_items = []
    try:
        evidence_query = db.collection(EVIDENCE_COLLECTION_NAME).where(
            filter=firestore.FieldFilter("parliament_session_id", "==", session_id_to_delete)
        )
        evidence_docs_stream = evidence_query.stream()
        
        # Convert synchronous stream to list asynchronously
        for doc_snapshot in await asyncio.to_thread(list, evidence_docs_stream):
            evidence_data = doc_snapshot.to_dict()
            if evidence_data:
                evidence_items.append({
                    "id": doc_snapshot.id,
                    "promise_ids": evidence_data.get("promise_ids", []),
                    "doc_ref": doc_snapshot.reference
                })
            else:
                logger.warning(f"Evidence item {doc_snapshot.id} has no data. Skipping.")
        logger.info(f"Found {len(evidence_items)} evidence items for session '{session_id_to_delete}'.")
        return evidence_items
    except Exception as e:
        logger.error(f"Error querying evidence items for session '{session_id_to_delete}': {e}", exc_info=True)
        return []

async def delete_data_for_session(
    evidence_items_to_delete: List[Dict[str, Any]],
    party_code_for_promises: str,
    dry_run: bool
):
    """Deletes evidence items and updates linked promises."""
    if not evidence_items_to_delete:
        logger.info("No evidence items to delete.")
        return

    total_evidence_deleted = 0
    total_promises_updated = 0
    
    firestore_batch = db.batch()
    operations_in_batch = 0

    # Keep track of promise IDs that have been processed in the current batch to avoid redundant updates
    promises_updated_in_current_batch = set()

    for evidence_item in evidence_items_to_delete:
        evidence_id = evidence_item["id"]
        evidence_doc_ref = evidence_item["doc_ref"]
        promise_ids_linked_to_evidence = evidence_item.get("promise_ids", [])

        logger.info(f"Processing evidence item ID: {evidence_id} for deletion.")
        if not dry_run:
            firestore_batch.delete(evidence_doc_ref)
            operations_in_batch += 1
            total_evidence_deleted +=1
        else:
            logger.info(f"[DRY RUN] Would delete evidence item: {evidence_id}")

        if promise_ids_linked_to_evidence:
            for promise_id in promise_ids_linked_to_evidence:
                if not promise_id:
                    logger.warning(f"Found empty or null promise_id in evidence item {evidence_id}. Skipping.")
                    continue

                promise_doc_path = f"{PROMISES_COLLECTION_ROOT}/{DEFAULT_REGION_CODE}/{party_code_for_promises}/{promise_id}"
                promise_doc_ref = db.document(promise_doc_path)
                
                update_payload = {
                    "linked_evidence_ids": firestore.ArrayRemove([evidence_id]),
                    "progress_score": 0,
                    "progress_summary": "Progress reset due to data cleanup for parliament session.",
                    "last_evidence_linking_at": firestore.SERVER_TIMESTAMP 
                }
                
                # Log before adding to batch, regardless of dry_run
                log_message_promise = f"Updating promise ID: {promise_id} (Path: {promise_doc_path}). Removing link to evidence {evidence_id}, resetting progress."
                if dry_run:
                     logger.info(f"[DRY RUN] {log_message_promise} with payload: {update_payload}")
                else:
                    logger.info(log_message_promise)
                    firestore_batch.update(promise_doc_ref, update_payload)
                    operations_in_batch += 1
                    # We count an update attempt here. If the promise doesn't exist, it won't fail the batch,
                    # but it also won't create it.
                    if promise_id not in promises_updated_in_current_batch:
                        total_promises_updated +=1 # Count unique promises intended for update in this run
                        promises_updated_in_current_batch.add(promise_id)


                if operations_in_batch >= FIRESTORE_BATCH_LIMIT and not dry_run:
                    logger.info(f"Committing batch of {operations_in_batch} Firestore operations...")
                    await asyncio.to_thread(firestore_batch.commit)
                    logger.info("Batch committed.")
                    firestore_batch = db.batch() # Start a new batch
                    operations_in_batch = 0
                    promises_updated_in_current_batch.clear()


    # Commit any remaining operations in the last batch
    if operations_in_batch > 0 and not dry_run:
        logger.info(f"Committing final batch of {operations_in_batch} Firestore operations...")
        await asyncio.to_thread(firestore_batch.commit)
        logger.info("Final batch committed.")
    elif operations_in_batch > 0 and dry_run:
        logger.info(f"[DRY RUN] Would commit final batch of {operations_in_batch} Firestore operations.")

    logger.info(f"Script finished. Processed {len(evidence_items_to_delete)} evidence items.")
    if dry_run:
        logger.info(f"[DRY RUN] Would have deleted {len(evidence_items_to_delete)} evidence items.")
        logger.info(f"[DRY RUN] Would have attempted updates on approximately {len(set(pid for evi in evidence_items_to_delete for pid in evi.get('promise_ids',[])))} unique promises.")
    else:
        logger.info(f"Actually deleted {total_evidence_deleted} evidence items.")
        logger.info(f"Attempted updates on {total_promises_updated} unique promises (some may have been updated multiple times if linked to multiple deleted evidence items across batches).")


async def main():
    parser = argparse.ArgumentParser(description='Deletes evidence items for a specific parliament session and cleans up linked promises.')
    parser.add_argument(
        '--parliament_session_id_to_delete',
        type=str,
        default="45",
        help='The parliament_session_id for which to delete evidence (e.g., "45"). Default is "45".'
    )
    parser.add_argument(
        '--party_code_for_promises',
        type=str,
        required=True,
        help='The party code (e.g., "LPC", "CPC") under which the promises are stored. This is crucial for constructing the correct promise document path for updates.'
    )
    parser.add_argument(
        '--dry_run',
        action='store_true',
        help='Perform a dry run without making any changes to Firestore. Highly recommended for the first run.'
    )
    args = parser.parse_args()

    logger.info("--- Starting Session Data Deletion Script ---")
    if args.dry_run:
        logger.info("*** DRY RUN MODE ENABLED: No changes will be written to Firestore. ***")
    
    logger.info(f"Target Parliament Session ID for deletion: {args.parliament_session_id_to_delete}")
    logger.info(f"Party Code for locating promises: {args.party_code_for_promises}")


    evidence_to_process = await fetch_evidence_items_for_session(args.parliament_session_id_to_delete)

    if not evidence_to_process:
        logger.info(f"No evidence items found for session '{args.parliament_session_id_to_delete}'. Nothing to do.")
    else:
        await delete_data_for_session(evidence_to_process, args.party_code_for_promises, args.dry_run)

    logger.info("--- Session Data Deletion Script Finished ---")

if __name__ == "__main__":
    asyncio.run(main()) 