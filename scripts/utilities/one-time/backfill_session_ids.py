import firebase_admin
from firebase_admin import credentials, firestore
import os
import logging
from dotenv import load_dotenv
import argparse
from datetime import datetime, date

# --- Load Environment Variables ---
load_dotenv()
# --- End Load Environment Variables ---

# --- Logger Setup ---
logging.basicConfig(level=logging.INFO,
                    format='%(asctime)s - %(levelname)s - %(filename)s:%(lineno)d - %(message)s',
                    datefmt='%Y-%m-%d %H:%M:%S')
logger = logging.getLogger(__name__)
# --- End Logger Setup ---

# --- Constants ---
TARGET_PARLIAMENT_SESSION_ID = "44"
# Inclusive start date (election_called_date for 44th)
SESSION_44_START_DATE_STR = "2021-08-15"
# Exclusive end date (end_date for 44th / election_called_date for 45th)
SESSION_44_END_DATE_STR = "2025-03-23"

SESSION_44_START_DATE = datetime.strptime(SESSION_44_START_DATE_STR, "%Y-%m-%d").date()
SESSION_44_END_DATE = datetime.strptime(SESSION_44_END_DATE_STR, "%Y-%m-%d").date()

FIRESTORE_BATCH_SIZE = 250
# --- End Constants ---

def initialize_firestore():
    """Initializes Firebase Admin SDK and returns a Firestore client instance."""
    # (Reusing the robust initialization logic from populate_department_config.py)
    db_client = None
    if not firebase_admin._apps:
        try:
            firebase_admin.initialize_app()
            project_id = os.getenv('FIREBASE_PROJECT_ID', '[Not Set - Using Default]')
            logger.info(f"Successfully connected to CLOUD Firestore (Project: {project_id}) using default credentials.")
            db_client = firestore.client()
        except Exception as e_default:
            logger.warning(f"Cloud Firestore init with default creds failed: {e_default}")
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
            else:
                logger.warning("FIREBASE_SERVICE_ACCOUNT_KEY_PATH environment variable not set.")
    else:
        logger.info("Firebase Admin SDK already initialized. Getting Firestore client.")
        db_client = firestore.client()
    return db_client

def parse_date_value(date_val) -> date | None:
    """Parses various date string formats or Firestore Timestamps into a date object."""
    if date_val is None:
        return None
    if isinstance(date_val, datetime):
        return date_val.date() # If it's a datetime object (e.g. Firestore Timestamp)
    if isinstance(date_val, date):
        return date_val # If it's already a date object
    
    if isinstance(date_val, str):
        date_str = date_val.strip()
        try:
            # Try YYYY-MM-DDTHH:MM:SS format first (split T)
            return datetime.strptime(date_str.split('T')[0], "%Y-%m-%d").date()
        except ValueError:
            pass # Continue to next format
        try:
            # Try YYYY-MM-DD format
            return datetime.strptime(date_str, "%Y-%m-%d").date()
        except ValueError:
            pass # Continue to next format
        try:
            # Try YYYYMMDD format
            return datetime.strptime(date_str, "%Y%m%d").date()
        except ValueError:
            logger.debug(f"Could not parse date string: '{date_str}' with known formats.")
            return None
    logger.debug(f"Unsupported date type for parsing: {type(date_val)}")
    return None

def is_in_44th_parliament_window(doc_date_obj: date | None) -> bool:
    """Checks if the given date object falls within the 44th Parliament window."""
    if doc_date_obj is None:
        return False
    return SESSION_44_START_DATE <= doc_date_obj < SESSION_44_END_DATE

def backfill_collection(db, collection_name: str, dry_run: bool):
    logger.info(f"--- Starting backfill for collection: '{collection_name}' ---")
    collection_ref = db.collection(collection_name)
    docs_processed = 0
    docs_updated = 0
    docs_skipped_no_date = 0
    docs_skipped_outside_window = 0
    docs_error = 0

    batch = db.batch()
    current_batch_count = 0

    for doc_snapshot in collection_ref.stream():
        docs_processed += 1
        doc_data = doc_snapshot.to_dict()
        doc_id = doc_snapshot.id
        parliament_session_id_to_set = None
        log_reason = ""

        try:
            if collection_name == "mandate_letters_fulltext":
                parliament_session_id_to_set = TARGET_PARLIAMENT_SESSION_ID
                log_reason = "Direct assignment for mandate_letters_fulltext."

            elif collection_name == "bills_data":
                if doc_data.get("parliament_number") == TARGET_PARLIAMENT_SESSION_ID:
                    parliament_session_id_to_set = TARGET_PARLIAMENT_SESSION_ID
                    log_reason = f"Matched by existing parliament_number field."
                else:
                    intro_date_val = doc_data.get("introduction_date")
                    if not intro_date_val:
                        logger.error(f"[{collection_name}/{doc_id}] Missing 'introduction_date'. Skipping.")
                        docs_error +=1
                        continue
                    parsed_date = parse_date_value(intro_date_val)
                    if parsed_date:
                        if is_in_44th_parliament_window(parsed_date):
                            parliament_session_id_to_set = TARGET_PARLIAMENT_SESSION_ID
                            log_reason = f"introduction_date ({parsed_date}) in 44th window."
                        else:
                            log_reason = f"introduction_date ({parsed_date}) outside 44th window."
                            docs_skipped_outside_window +=1
                    else:
                        logger.error(f"[{collection_name}/{doc_id}] Unparseable 'introduction_date': '{intro_date_val}'. Skipping.")
                        docs_error +=1
                        continue
            
            elif collection_name == "promises":
                source_type = doc_data.get("source_type")
                relevant_date_val = None
                date_field_used = ""
                apply_other_cases_rule = False

                if source_type == "Video Transcript (YouTube)":
                    relevant_date_val = doc_data.get("video_upload_date")
                    date_field_used = "video_upload_date"
                    if not relevant_date_val:
                        logger.warning(f"[{collection_name}/{doc_id}] '{source_type}' missing '{date_field_used}'. Applying 'Other Cases' rule.")
                        apply_other_cases_rule = True
                elif source_type == "Mandate Letter Commitment (Structured)":
                    relevant_date_val = doc_data.get("date_issued")
                    date_field_used = "date_issued"
                    if not relevant_date_val:
                        logger.warning(f"[{collection_name}/{doc_id}] '{source_type}' missing '{date_field_used}'. Applying 'Other Cases' rule.")
                        apply_other_cases_rule = True
                else:
                    apply_other_cases_rule = True
                    log_reason = "Applying 'Other Cases' rule (default)."

                if apply_other_cases_rule:
                    parliament_session_id_to_set = TARGET_PARLIAMENT_SESSION_ID
                    if not log_reason: log_reason = "Assigned by 'Other Cases' rule for promises."
                elif relevant_date_val:
                    parsed_date = parse_date_value(relevant_date_val)
                    if parsed_date:
                        if is_in_44th_parliament_window(parsed_date):
                            parliament_session_id_to_set = TARGET_PARLIAMENT_SESSION_ID
                            log_reason = f"{date_field_used} ({parsed_date}) in 44th window."
                        else:
                            log_reason = f"{date_field_used} ({parsed_date}) outside 44th window. Applying 'Other Cases' rule."
                            parliament_session_id_to_set = TARGET_PARLIAMENT_SESSION_ID # Fallback to Other Cases rule
                    else:
                        logger.warning(f"[{collection_name}/{doc_id}] Unparseable '{date_field_used}': '{relevant_date_val}'. Applying 'Other Cases' rule.")
                        parliament_session_id_to_set = TARGET_PARLIAMENT_SESSION_ID # Fallback to Other Cases rule
                        log_reason = f"Unparseable '{date_field_used}', assigned by 'Other Cases' rule."
            
            elif collection_name == "evidence_items":
                evidence_date_val = doc_data.get("evidence_date")
                if not evidence_date_val:
                    logger.warning(f"[{collection_name}/{doc_id}] Missing 'evidence_date'. Skipping.")
                    docs_skipped_no_date +=1
                    continue
                parsed_date = parse_date_value(evidence_date_val)
                if parsed_date:
                    if is_in_44th_parliament_window(parsed_date):
                        parliament_session_id_to_set = TARGET_PARLIAMENT_SESSION_ID
                        log_reason = f"evidence_date ({parsed_date}) in 44th window."
                    else:
                        log_reason = f"evidence_date ({parsed_date}) outside 44th window."
                        docs_skipped_outside_window += 1
                else:
                    logger.warning(f"[{collection_name}/{doc_id}] Unparseable 'evidence_date': '{evidence_date_val}'. Skipping.")
                    docs_skipped_no_date +=1
                    continue

            elif collection_name == "youtube_video_data":
                upload_date_val = doc_data.get("upload_date")
                if not upload_date_val:
                    logger.error(f"[{collection_name}/{doc_id}] Missing 'upload_date'. Skipping.")
                    docs_error +=1
                    continue
                parsed_date = parse_date_value(upload_date_val)
                if parsed_date:
                    if is_in_44th_parliament_window(parsed_date):
                        parliament_session_id_to_set = TARGET_PARLIAMENT_SESSION_ID
                        log_reason = f"upload_date ({parsed_date}) in 44th window."
                    else:
                        log_reason = f"upload_date ({parsed_date}) outside 44th window."
                        docs_skipped_outside_window += 1
                else:
                    logger.error(f"[{collection_name}/{doc_id}] Unparseable 'upload_date': '{upload_date_val}'. Skipping.")
                    docs_error +=1
                    continue

            # Perform update if parliament_session_id_to_set is determined
            if parliament_session_id_to_set:
                # Only update if the field is new or different
                if doc_data.get("parliament_session_id") != parliament_session_id_to_set:
                    logger.info(f"[{collection_name}/{doc_id}] Will be updated. Reason: {log_reason} Field value: {parliament_session_id_to_set}")
                    if not dry_run:
                        doc_ref = collection_ref.document(doc_id)
                        batch.update(doc_ref, {"parliament_session_id": parliament_session_id_to_set})
                        current_batch_count += 1
                    docs_updated += 1
                else:
                    logger.debug(f"[{collection_name}/{doc_id}] Already has correct parliament_session_id '{parliament_session_id_to_set}'. Skipping update. Reason: {log_reason}")
            elif log_reason: # Log if no ID set but there was a reason (e.g. outside window)
                 logger.info(f"[{collection_name}/{doc_id}] No update needed. Reason: {log_reason}")

            if current_batch_count >= FIRESTORE_BATCH_SIZE:
                if not dry_run:
                    logger.info(f"Committing batch of {current_batch_count} updates for {collection_name}...")
                    batch.commit()
                    batch = db.batch() # Start new batch
                current_batch_count = 0
        
        except Exception as e:
            logger.error(f"[{collection_name}/{doc_id}] Unexpected error processing document: {e}", exc_info=True)
            docs_error += 1
            # Optionally, re-raise or handle more gracefully depending on desired script behavior for critical errors.

    # Commit any remaining items in the last batch
    if current_batch_count > 0 and not dry_run:
        logger.info(f"Committing final batch of {current_batch_count} updates for {collection_name}...")
        batch.commit()
    
    logger.info(f"--- Finished backfill for collection: '{collection_name}' ---")
    logger.info(f"Summary for '{collection_name}':")
    logger.info(f"  Documents processed: {docs_processed}")
    logger.info(f"  Documents updated (or would be updated): {docs_updated}")
    logger.info(f"  Documents skipped (missing/unparseable date): {docs_skipped_no_date}")
    logger.info(f"  Documents skipped (date outside 44th window): {docs_skipped_outside_window}")
    logger.info(f"  Documents with errors: {docs_error}")
    logger.info("---------------------------------------------------")


def main():
    parser = argparse.ArgumentParser(description="Backfill parliament_session_id for specified Firestore collections.")
    parser.add_argument("--dry-run", action="store_true", help="Log changes without writing to Firestore.")
    parser.add_argument("--collections", nargs='+', 
                        default=["mandate_letters_fulltext", "bills_data", "promises", "evidence_items", "youtube_video_data"],
                        help="List of collections to process (e.g., promises evidence_items). Processes all by default.")
    args = parser.parse_args()

    if args.dry_run:
        logger.info("DRY RUN mode enabled. No actual writes to Firestore will occur.")

    db = initialize_firestore()
    if not db:
        logger.critical("Failed to initialize Firestore. Exiting.")
        return

    collections_to_process = args.collections
    logger.info(f"Target collections for backfill: {collections_to_process}")

    for collection_name in collections_to_process:
        backfill_collection(db, collection_name, args.dry_run)
    
    logger.info("Backfill process completed for all specified collections.")

if __name__ == "__main__":
    main() 