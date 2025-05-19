#!/usr/bin/env python
# PromiseTracker/scripts/utilities/migrate_promises_structure.py
# This script migrates promise documents from a flat collection structure
# to a hierarchical structure: promises/{country}/{party_code}/{YYYYMMDD_SOURCETYPE_CONTENTHASH}

import firebase_admin
from firebase_admin import firestore, credentials
import hashlib
import os
from dotenv import load_dotenv
import logging
import time
import asyncio # Required for async operations

# --- Load Environment Variables ---
load_dotenv()
# --- End Load Environment Variables ---

# --- Logger Setup ---
logging.basicConfig(level=logging.INFO,
                    format='%(asctime)s - %(levelname)s - %(filename)s:%(lineno)d - %(message)s',
                    datefmt='%Y-%m-%d %H:%M:%S')
logger = logging.getLogger("migrate_promises_structure")
# --- End Logger Setup ---

# --- Firebase Configuration ---
db = None
# Adapted from enrich_tag_new_promise.py
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
                app_name = 'migrate_promises_app' # Unique app name for this script
                # Ensure app_name is unique if other scripts might run concurrently or if default exists
                if firebase_admin.get_app(firebase_admin.DEFAULT_APP_NAME, raise_exceptions=False):
                     app_name = app_name + str(time.time())

                firebase_admin.initialize_app(cred, name=app_name)
                project_id_sa = os.getenv('FIREBASE_PROJECT_ID', '[Not Set - Using Service Account]')
                logger.info(f"Connected to CLOUD Firestore (Project: {project_id_sa}) via service account using app '{app_name}'.")
                db = firestore.client(app=firebase_admin.get_app(name=app_name))

            except Exception as e_sa:
                logger.critical(f"Firebase init with service account key from {cred_path} failed: {e_sa}", exc_info=True)
        else:
            logger.warning("FIREBASE_SERVICE_ACCOUNT_KEY_PATH environment variable not set, and default creds failed.")

if db is None:
    logger.critical("CRITICAL: Failed to obtain Firestore client. Exiting.")
    exit("Exiting: Firestore client not available.")
# --- End Firebase Configuration ---

# --- Mappings ---
PARTY_NAME_TO_CODE_MAPPING = {
    "Liberal Party of Canada": "LPC",
    "Conservative Party of Canada": "CPC",
    "New Democratic Party": "NDP",
    "Bloc Québécois": "BQ",
    # Ensure these keys EXACTLY match the values in your 'party' field
    # Add variations if they exist, e.g. "Liberal Party of Canada (2025 Platform)": "LPC",
}

SOURCE_TYPE_TO_ID_CODE_MAPPING = {
    "Video Transcript (YouTube)": "YTVID",
    "Mandate Letter Commitment (Structured)": "MANDL", # Original maps to MANDL for ID code
    "2021 LPC Mandate Letters": "MANDL",             # New value also maps to MANDL for ID code
    "2025 LPC Platform": "PLTFM",
    # Add more as needed, and consider a fallback
    "DEFAULT_SOURCE_ID_CODE": "OTHER" # Fallback code
}

# Rule for updating the source_type field itself
SOURCE_TYPE_FIELD_UPDATE_MAPPING = {
    "Mandate Letter Commitment (Structured)": "2021 LPC Mandate Letters"
}

REGION_CODE = "Canada" # Default for this migration

# --- Helper Functions ---
def generate_content_hash(text: str, length: int = 10) -> str:
    if not text:
        logger.warning("generate_content_hash received empty text, returning 'nohash'.")
        return "nohash" + str(int(time.time())) # Add timestamp to ensure uniqueness for empty texts if multiple
        
    normalized_text = text.lower().strip()
    # Consider more normalization: remove punctuation, multiple spaces for better deduplication.
    # For example:
    # import re
    # normalized_text = re.sub(r'\s+', ' ', normalized_text) # Replace multiple spaces with one
    # normalized_text = re.sub(r'[^a-z0-9\s-]', '', normalized_text) # Keep alphanumeric, spaces, hyphens

    hasher = hashlib.sha256()
    hasher.update(normalized_text.encode('utf-8'))
    return hasher.hexdigest()[:length]

async def migrate_document(old_doc_ref, old_doc_data, target_collection_prefix="promises_migrated"):
    try:
        logger.debug(f"Processing old document ID: {old_doc_ref.id}. Target root: {target_collection_prefix}")

        # --- Pre-migration data correction ---
        if old_doc_data.get("source_type") == "2025 LPC Platform":
            corrected_date = "2025-04-19"
            original_date_for_log = old_doc_data.get("date_issued") # Get value for logging
            if original_date_for_log != corrected_date:
                logger.info(f"  CORRECTION: Updating date_issued for '{old_doc_ref.id}' from '{original_date_for_log}' to '{corrected_date}' because source_type is '2025 LPC Platform'.")
                old_doc_data["date_issued"] = corrected_date # Modify the data in memory
            else:
                logger.debug(f"  Date for '{old_doc_ref.id}' is already '{corrected_date}' for source_type '2025 LPC Platform'. No change needed for date.")
        # --- End pre-migration data correction ---

        # 1. Extract Party Code
        party_name = old_doc_data.get("party")
        party_code = PARTY_NAME_TO_CODE_MAPPING.get(party_name)
        
        # Fallback for party if direct match fails (e.g. "Liberal Party of Canada (2025 Platform)")
        if not party_code:
            for key, value in PARTY_NAME_TO_CODE_MAPPING.items():
                if party_name and key in party_name: # Check if known party name is substring
                    party_code = value
                    logger.debug(f"Found party code '{party_code}' using substring match for '{party_name}'.")
                    break
        
        if not party_code:
            logger.warning(f"No party code mapping for '{party_name}' in doc {old_doc_ref.id}. Skipping.")
            return False, "no_party_code"

        # 2. Extract and Format Date (Expects YYYY-MM-DD from 'date_issued')
        date_issued_str = old_doc_data.get("date_issued")
        if not date_issued_str or not isinstance(date_issued_str, str) or len(date_issued_str.split('-')) != 3:
            logger.warning(f"Invalid or missing 'date_issued' ({date_issued_str}) in doc {old_doc_ref.id}. Using 'nodate'.")
            yyyymmdd = "nodate" + str(int(time.time()))[-4:] # Add part of timestamp for uniqueness
        else:
            try:
                # Attempt to parse and reformat to ensure YYYYMMDD
                dt_obj = datetime.strptime(date_issued_str, "%Y-%m-%d")
                yyyymmdd = dt_obj.strftime("%Y%m%d")
            except ValueError:
                logger.warning(f"Malformed 'date_issued' ({date_issued_str}) in doc {old_doc_ref.id}, attempting direct replace. Using 'baddate'.")
                yyyymmdd = date_issued_str.replace("-", "")
                if len(yyyymmdd) != 8 or not yyyymmdd.isdigit():
                     yyyymmdd = "baddate" + str(int(time.time()))[-4:]


        # 3. Handle Source Type (Field Update and ID Code)
        original_source_type = old_doc_data.get("source_type", "Unknown") # Default if missing

        # Apply field update rule first
        new_source_type_field_value = SOURCE_TYPE_FIELD_UPDATE_MAPPING.get(original_source_type, original_source_type)
        
        # Use the (potentially updated) field value to get the ID code
        source_id_code = SOURCE_TYPE_TO_ID_CODE_MAPPING.get(new_source_type_field_value, SOURCE_TYPE_TO_ID_CODE_MAPPING["DEFAULT_SOURCE_ID_CODE"])
        
        migrated_doc_data = old_doc_data.copy()
        migrated_doc_data["source_type"] = new_source_type_field_value # Store the updated/original source_type

        # 4. Generate Content Hash
        promise_text = old_doc_data.get("text")
        content_hash = generate_content_hash(promise_text)

        # 5. Construct New Document ID (leaf ID)
        new_doc_leaf_id = f"{yyyymmdd}_{source_id_code}_{content_hash}"

        # 6. Construct New Full Path
        new_doc_full_path = f"{target_collection_prefix}/{REGION_CODE}/{party_code}/{new_doc_leaf_id}"
        new_doc_ref = db.document(new_doc_full_path)
        
        logger.info(f"  Old ID: {old_doc_ref.id} -> New Path will be: {new_doc_full_path}")
        logger.debug(f"  Old source_type: '{original_source_type}', New source_type field: '{new_source_type_field_value}', ID Code: '{source_id_code}'")

        # 7. Write New Document
        # For safety during testing, you might check if it exists first,
        # or decide on an overwrite policy (current is overwrite).
        # if (await asyncio.to_thread(new_doc_ref.get)).exists:
        #     logger.warning(f"  Target document {new_doc_full_path} already exists. Skipping write.")
        #     return False, "target_exists"

        await asyncio.to_thread(new_doc_ref.set, migrated_doc_data)
        logger.info(f"  Successfully wrote to new path: {new_doc_full_path}")

        # 8. Delete Old Document (IMPORTANT: Keep commented out during testing)
        # await asyncio.to_thread(old_doc_ref.delete)
        # logger.info(f"  Successfully deleted old document: {old_doc_ref.id}")
        
        return True, "success"

    except Exception as e:
        potential_path_str = "unknown_path"
        if 'new_doc_full_path' in locals() and new_doc_full_path:
            potential_path_str = new_doc_full_path
        else:
            leaf_id_str = new_doc_leaf_id if 'new_doc_leaf_id' in locals() and new_doc_leaf_id else 'unknown_leaf_id'
            party_code_str = party_code if 'party_code' in locals() and party_code else 'unknown_party'
            # Construct a simplified fallback path string without nested f-strings for the error message
            potential_path_str = f"{target_collection_prefix}/{REGION_CODE}/{party_code_str}/.../{leaf_id_str}"
        
        logger.error(f"Error migrating document {old_doc_ref.id} to potential path {potential_path_str}: {e}", exc_info=True)
        return False, str(e)

async def run_migration(source_collection_name="promises", target_collection_name="promises_migrated", dry_run=False):
    logger.info(f"--- Starting Promise Migration from '{source_collection_name}' to target root '{target_collection_name}' (Dry Run: {dry_run}) ---")
    
    old_promises_ref = db.collection(source_collection_name)
    # Use stream() for memory efficiency with large collections
    docs_snapshot_stream = old_promises_ref.stream()

    summary = {"total_considered": 0, "migrated_successfully": 0, "failed_migration": 0, "skipped_no_party_code": 0, "skipped_target_exists": 0, "other_failures": {}}

    # Correctly handle the synchronous stream in an async context
    def get_all_docs_sync():
        return list(docs_snapshot_stream) # Convert synchronous generator to list

    all_docs = await asyncio.to_thread(get_all_docs_sync)
    
    logger.info(f"Found {len(all_docs)} documents in '{source_collection_name}' to consider.")

    for i, doc_snapshot in enumerate(all_docs):
        summary["total_considered"] += 1
        logger.info(f"--- Processing document {i+1} of {len(all_docs)} (ID: {doc_snapshot.id}) ---")
        
        if dry_run:
            logger.info(f"[DRY RUN] Would attempt to migrate doc ID: {doc_snapshot.id}")
            # Simulate path generation for dry run log
            # This is a simplified simulation, actual values depend on doc_snapshot.to_dict()
            # For a more accurate dry run log of the path, we'd need to call parts of migrate_document logic here
            # or pass dry_run into migrate_document and have it stop before the write.
            # For now, focusing on passing target_collection_name correctly.
            success, reason = True, "dry_run_skipped_actual_migration"
        else:
            success, reason = await migrate_document(doc_snapshot.reference, doc_snapshot.to_dict(), target_collection_prefix=target_collection_name)

        if success and reason != "dry_run_skipped_actual_migration":
            summary["migrated_successfully"] += 1
        elif not success:
            summary["failed_migration"] += 1
            if reason == "no_party_code":
                summary["skipped_no_party_code"] +=1
            elif reason == "target_exists": # If you implement the check
                summary["skipped_target_exists"] +=1
            else:
                summary["other_failures"][reason] = summary["other_failures"].get(reason, 0) + 1
        
        # Optional: add a small delay to avoid hitting Firestore rate limits on very large collections
        # if not dry_run and i < len(all_docs) - 1 : await asyncio.sleep(0.01) 

    logger.info("--- Migration Summary ---")
    for key, value in summary.items():
        if key == "other_failures" and value:
            logger.info(f"  Other Failures by reason:")
            for reason, count in value.items():
                logger.info(f"    {reason}: {count}")
        else:
            logger.info(f"  {key.replace('_', ' ').capitalize()}: {value}")
    
    if not dry_run:
        logger.info("--- Migration Complete ---")
        if summary["failed_migration"] > 0:
            logger.warning("Check logs for details on failed migrations.")
        logger.info("REMEMBER TO REVIEW THE NEW STRUCTURE AND MANUALLY DELETE THE OLD COLLECTION "
                    f"'{source_collection_name}' IF EVERYTHING IS OK AND DELETION WASN'T ENABLED IN SCRIPT.")
    else:
        logger.info("--- Dry Run Complete ---")

# Required for parsing date_issued if not already imported
from datetime import datetime

async def main():
    # Global db should be set by Firebase Init block at the top
    if db is None:
        logger.critical("Firestore client not available after init block. Exiting.")
        return

    # --- Script Arguments ---
    import argparse
    parser = argparse.ArgumentParser(description='Migrate Firestore promise documents to a new hierarchical structure.')
    parser.add_argument(
        '--source_collection',
        type=str,
        default="promises", # Default to "promises"
        help='Name of the source collection to migrate (e.g., promises,promises_backup).'
    )
    parser.add_argument(
        '--target_collection',
        type=str,
        default="promises_migrated", # Default to a new distinct name
        help='Name of the new top-level target collection for migrated data (e.g., promises_migrated).'
    )
    parser.add_argument(
        '--dry_run',
        action='store_true',
        help='Perform a dry run without making any actual changes to Firestore.'
    )
    # Potentially add --delete_old_docs flag here later if you want scripted deletion

    args = parser.parse_args()

    logger.info(f"Starting migration script with source: '{args.source_collection}', target: '{args.target_collection}', Dry Run: {args.dry_run}")
    
    await run_migration(source_collection_name=args.source_collection, target_collection_name=args.target_collection, dry_run=args.dry_run)

if __name__ == "__main__":
    asyncio.run(main()) 