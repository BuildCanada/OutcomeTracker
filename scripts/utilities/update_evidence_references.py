#!/usr/bin/env python
# PromiseTracker/scripts/utilities/update_evidence_references.py
# This script updates evidence items to ensure they correctly reference associated promises by their full path.
# It will clear the existing 'promise_ids' array in evidence_items and replace it with the new, correct full paths.

import firebase_admin
from firebase_admin import credentials, firestore
import os
import logging
import traceback
from dotenv import load_dotenv
import argparse
import time # For potential unique app names if needed
from collections import defaultdict # For building the map

# --- Load Environment Variables ---
load_dotenv(dotenv_path=os.path.join(os.path.dirname(__file__), '..', '..', '.env'))
# --- End Load Environment Variables ---

# --- Logger Setup ---
logging.basicConfig(level=logging.INFO,
                    format='%(asctime)s - %(levelname)s - %(filename)s:%(lineno)d - %(message)s',
                    datefmt='%Y-%m-%d %H:%M:%S')
logger = logging.getLogger("update_evidence_references")
# --- End Logger Setup ---

# --- Firebase Configuration ---
db = None
try:
    if not firebase_admin._apps:
        # Attempt to initialize with default credentials first
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
                    app_name = 'update_evidence_references_app'
                    try:
                        firebase_admin.initialize_app(cred, name=app_name)
                    except ValueError: # App with this name already exists
                         app_name = app_name + str(time.time()) # Make name unique
                         firebase_admin.initialize_app(cred, name=app_name)
                    
                    project_id_sa = os.getenv('FIREBASE_PROJECT_ID', '[Not Set - Using Service Account]')
                    logger.info(f"Connected to CLOUD Firestore (Project: {project_id_sa}) via service account using app '{app_name}'.")
                    db = firestore.client(app=firebase_admin.get_app(name=app_name))

                except Exception as e_sa:
                    logger.critical(f"Firebase init with service account key from {cred_path} failed: {e_sa}", exc_info=True)
            else:
                logger.warning("FIREBASE_SERVICE_ACCOUNT_KEY_PATH environment variable not set, and default creds failed.")
    else:
        # If apps exist, try to get the default client, or one specific to this script if re-running
        try:
            db = firestore.client() # Try default app's client
            logger.info("Re-using existing Firebase default app's Firestore client.")
        except Exception as e_reuse:
            logger.warning(f"Could not get default Firestore client: {e_reuse}. This might happen if default app changed.")


    if db is None and firebase_admin._apps: 
        logger.warning("db is None but firebase_admin._apps exist. This script expects db to be set during init.")


except Exception as e_outer_init:
    logger.critical(f"Outer Firebase initialization block failed: {e_outer_init}", exc_info=True)

if db is None:
    logger.critical("CRITICAL: Failed to obtain Firestore client. Exiting.")
    exit("Exiting: Firestore client not available.")
# --- End Firebase Configuration ---

# --- Constants ---
TARGET_PROMISES_COLLECTION_ROOT = os.getenv("TARGET_PROMISES_COLLECTION", "promises")
EVIDENCE_ITEMS_COLLECTION = "evidence_items"

DEFAULT_REGION_CODE = "Canada" 
KNOWN_PARTY_CODES = ["LPC", "CPC", "NDP", "BQ", "GP"] 
# --- End Constants ---

class BatchManager:
    def __init__(self, db_client, dry_run=True, max_batch_size=490):
        self.db = db_client
        self.dry_run = dry_run
        self.max_batch_size = max_batch_size
        self.batch = db_client.batch()
        self.operations_in_batch = 0
        self.total_operations_committed = 0

    def add_set_operation(self, doc_ref, payload_to_set): # Changed from add_update to add_set_operation
        if self.dry_run:
            # Logging for set operation will be handled by caller
            pass
        else:
            self.batch.set(doc_ref, payload_to_set, merge=False) # Using set with merge=False to overwrite
            self.operations_in_batch += 1
    
    async def commit_if_needed(self):
        if self.operations_in_batch >= self.max_batch_size:
            await self.commit_batch()

    async def commit_batch(self):
        if self.operations_in_batch > 0:
            logger.info(f"Committing batch of {self.operations_in_batch} operations...")
            if not self.dry_run:
                try:
                    self.batch.commit()
                    logger.info("Batch committed successfully.")
                    self.total_operations_committed += self.operations_in_batch
                except Exception as e:
                    logger.error(f"Error committing batch: {e}", exc_info=True)
            else:
                logger.info("[Dry Run] Would have committed batch.")
                self.total_operations_committed += self.operations_in_batch 

            self.batch = self.db.batch() 
            self.operations_in_batch = 0
        else:
            logger.debug("No operations in current batch to commit.")


async def main_async():
    parser = argparse.ArgumentParser(description='Update evidence_items with full promise paths, clearing old paths.')
    parser.add_argument(
        '--dry_run',
        action='store_true', 
        help='Run in dry-run mode (log changes, no writes). If not set, changes will be applied.'
    )
    parser.add_argument(
        '--apply_changes',
        action='store_true',
        help='Actually apply changes to Firestore. If both --dry_run and --apply_changes are omitted, it defaults to a dry run.'
    )

    args = parser.parse_args()
    
    is_dry_run_effective = True 
    if args.apply_changes and not args.dry_run:
        is_dry_run_effective = False
    elif args.dry_run: 
        is_dry_run_effective = True
        if args.apply_changes:
            logger.warning("Both --dry_run and --apply_changes were specified. Defaulting to DRY RUN for safety.")
    else: 
        logger.info("No explicit mode set. Defaulting to DRY RUN. Use --apply_changes to modify data.")
        is_dry_run_effective = True

    logger.info(f"--- Starting Evidence Reference Update Script (Clear & Replace Mode) --- Dry Run: {is_dry_run_effective} ---")

    if db is None:
        logger.critical("Firestore client (db) is not initialized. Cannot proceed.")
        return

    evidence_to_new_promise_paths = defaultdict(set)
    total_promises_scanned = 0
    total_links_found = 0

    # --- Pass 1: Collect all new promise paths for each evidence item ---
    logger.info("--- Pass 1: Collecting new promise paths for evidence items ---")
    for party_code in KNOWN_PARTY_CODES:
        logger.info(f"Scanning flat promises collection for party: {party_code}")
        
        try:
            promise_docs_stream = db.collection(TARGET_PROMISES_COLLECTION_ROOT).where(filter=firestore.FieldFilter('party_code', '==', party_code)).stream()
            party_promises_scanned = 0
            for promise_doc_snap in promise_docs_stream:
                total_promises_scanned += 1
                party_promises_scanned +=1
                promise_full_path = promise_doc_snap.reference.path
                promise_data = promise_doc_snap.to_dict()
                
                if not promise_data:
                    logger.warning(f"Promise at {promise_full_path} has no data. Skipping.")
                    continue
                
                linked_evidence_ids = promise_data.get("linked_evidence_ids")

                if isinstance(linked_evidence_ids, list) and linked_evidence_ids:
                    for evidence_item_id in linked_evidence_ids:
                        if isinstance(evidence_item_id, str) and evidence_item_id.strip():
                            evidence_to_new_promise_paths[evidence_item_id].add(promise_full_path)
                            total_links_found +=1
                            logger.debug(f"Collected link: Evidence '{evidence_item_id}' -> Promise '{promise_full_path}'")
                        else:
                            logger.warning(f"Invalid evidence_item_id '{evidence_item_id}' in promise {promise_full_path}.")
            logger.info(f"Finished scanning party {party_code}. Promises scanned in party: {party_promises_scanned}.")
        except Exception as e:
            logger.error(f"Error scanning party {party_code} in flat collection: {e}", exc_info=True)
    
    logger.info(f"--- Pass 1 Complete: Total promises scanned: {total_promises_scanned}. Total promise-evidence links collected: {total_links_found}. Unique evidence items to update: {len(evidence_to_new_promise_paths)} ---")

    # --- Pass 2: Update evidence items with the collected promise paths ---
    logger.info("--- Pass 2: Updating evidence items (clearing old promise_ids and setting new ones) ---")
    batch_manager = BatchManager(db, dry_run=is_dry_run_effective)
    evidence_items_updated_count = 0

    if not evidence_to_new_promise_paths:
        logger.info("No evidence items found to update based on promise links.")
    else:
        for evidence_item_id, new_promise_paths_set in evidence_to_new_promise_paths.items():
            evidence_item_ref = db.collection(EVIDENCE_ITEMS_COLLECTION).document(evidence_item_id)
            new_promise_ids_list = sorted(list(new_promise_paths_set)) # Sort for consistent ordering, though not strictly necessary for Firestore arrays

            update_op_description = f"Update {EVIDENCE_ITEMS_COLLECTION}/{evidence_item_id}: SET 'promise_ids' to {new_promise_ids_list} (clears old values)."
            
            if is_dry_run_effective:
                logger.info(f"[Dry Run] Would {update_op_description}")
            else:
                logger.debug(f"Queueing: {update_op_description}")
                # Using .set with merge=False to completely overwrite the document's promise_ids field.
                # If evidence_items documents only contain promise_ids and other critical fields,
                # be cautious. This operation using batch.set(..., merge=False) with just one field
                # in the payload effectively overwrites the *entire document* with just this field
                # if the document didn't exist, or replaces this field if it did.
                # A safer approach for just one field is .update()
                # db.collection(...).document(...).update({"promise_ids": new_promise_ids_list})
                # This ensures only the 'promise_ids' field is affected.
                # Let's use batch.update for clarity and safety of other fields.
                batch_manager.batch.update(evidence_item_ref, {"promise_ids": new_promise_ids_list})
                batch_manager.operations_in_batch +=1 # Manually increment as we directly used batch.update

            evidence_items_updated_count += 1
            await batch_manager.commit_if_needed()
    
    await batch_manager.commit_batch() # Commit any remaining operations

    logger.info("--- Script Summary ---")
    logger.info(f"Total promises scanned: {total_promises_scanned}")
    logger.info(f"Total promise-to-evidence links found: {total_links_found}")
    logger.info(f"Unique evidence items targeted for 'promise_ids' update (overwrite): {evidence_items_updated_count}")
    logger.info(f"Total Firestore write operations queued/logged for evidence_items: {evidence_items_updated_count}") # This is item count, not operation count if batching is less fine-grained
    logger.info(f"Total operations actually committed (if not dry run): {batch_manager.total_operations_committed if not is_dry_run_effective else '(Dry Run)'}")
    logger.info(f"Dry Run Mode: {is_dry_run_effective}")
    logger.info("--- Evidence Reference Update Script Finished (Clear & Replace Mode) ---")

if __name__ == "__main__":
    import asyncio
    asyncio.run(main_async()) 