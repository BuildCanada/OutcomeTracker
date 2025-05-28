"""
Optimized cleanup script to delete news items from before the 44th Parliament (2021-11-21).
Uses batch deletions for much faster performance.

CLI arguments:
--dry_run: If True, will not delete from Firestore but show what would be deleted. Default: False
--log_level: Set the logging level. Default: INFO
--batch_size: Number of items to delete in each batch. Default: 500
"""

import os
import sys
import logging
from datetime import datetime, timezone, date
from dotenv import load_dotenv
import firebase_admin
from firebase_admin import credentials, firestore
import argparse
import time

# --- Configuration ---
load_dotenv()

# --- Logger Setup ---
logging.basicConfig(level=logging.INFO,
                    format='%(asctime)s - %(levelname)s - %(filename)s:%(lineno)d - %(message)s',
                    datefmt='%Y-%m-%d %H:%M:%S')
logger = logging.getLogger("cleanup_pre_44th_parliament_news_batch")
# --- End Logger Setup ---

# --- Constants ---
RAW_NEWS_RELEASES_COLLECTION = "raw_news_releases"
EVIDENCE_ITEMS_COLLECTION = "evidence_items"
PARLIAMENT_44TH_START_DATE = date(2021, 11, 21)  # Start of 44th Parliament
DEFAULT_BATCH_SIZE = 500
# --- End Constants ---

# --- Firebase Configuration ---
db = None
if not firebase_admin._apps:
    try:
        firebase_admin.initialize_app()
        project_id_env = os.getenv('FIREBASE_PROJECT_ID', '[Not Set - Using Default]')
        logger.info(f"Connected to CLOUD Firestore (Project: {project_id_env}) using default credentials.")
        db = firestore.client()
    except Exception as e_default:
        logger.warning(f"Cloud Firestore init with default creds failed: {e_default}. Attempting service account.")
        cred_path = os.getenv('FIREBASE_SERVICE_ACCOUNT_KEY_PATH')
        if cred_path:
            try:
                logger.info(f"Attempting Firebase init with service account key from env var: {cred_path}")
                cred = credentials.Certificate(cred_path)
                app_name = f'cleanup_news_batch_app_{int(time.time())}'
                firebase_admin.initialize_app(cred, name=app_name)
                db = firestore.client(app=firebase_admin.get_app(name=app_name))
                logger.info(f"Connected to CLOUD Firestore (Project: {project_id_env}) via service account.")
            except Exception as e_sa:
                logger.critical(f"Firebase init with service account key from {cred_path} failed: {e_sa}", exc_info=True)
        else:
            logger.warning("FIREBASE_SERVICE_ACCOUNT_KEY_PATH environment variable not set, and default creds failed.")

if db is None:
    logger.critical("CRITICAL: Failed to obtain Firestore client. Exiting.")
    exit("Exiting: Firestore client not available.")
# --- End Firebase Configuration ---

def cleanup_old_news_items_batch(db_client, dry_run=False, batch_size=DEFAULT_BATCH_SIZE):
    """
    Delete news items from before the 44th Parliament start date (2021-11-21).
    Uses batch deletions for better performance.
    """
    logger.info(f"Starting batch cleanup of news items before {PARLIAMENT_44TH_START_DATE}")
    logger.info(f"Using batch size: {batch_size}")
    if dry_run:
        logger.info("*** DRY RUN MODE ENABLED - No data will be deleted. ***")
    
    cutoff_datetime = datetime.combine(PARLIAMENT_44TH_START_DATE, datetime.min.time(), tzinfo=timezone.utc)
    
    # Track statistics
    raw_news_found = 0
    raw_news_deleted = 0
    evidence_items_found = 0
    evidence_items_deleted = 0
    errors = 0
    
    try:
        # First, find all raw news items before the cutoff date
        logger.info(f"Querying raw news items with publication_date < {cutoff_datetime}")
        
        query = db_client.collection(RAW_NEWS_RELEASES_COLLECTION).where(
            filter=firestore.FieldFilter("publication_date", "<", cutoff_datetime)
        )
        
        # Collect all documents and related evidence IDs
        old_news_docs = []
        related_evidence_ids = set()
        
        logger.info("Collecting documents to delete...")
        for doc in query.stream():
            old_news_docs.append(doc)
            news_data = doc.to_dict()
            
            # Check for related evidence item
            related_evidence_id = news_data.get('related_evidence_item_id')
            if related_evidence_id:
                related_evidence_ids.add(related_evidence_id)
        
        raw_news_found = len(old_news_docs)
        logger.info(f"Found {raw_news_found} raw news items before {PARLIAMENT_44TH_START_DATE}")
        logger.info(f"Found {len(related_evidence_ids)} related evidence items to check")
        
        if raw_news_found == 0:
            logger.info("No old news items found to clean up.")
            return
        
        # Delete raw news items in batches
        logger.info("Starting batch deletion of raw news items...")
        for i in range(0, len(old_news_docs), batch_size):
            batch_docs = old_news_docs[i:i + batch_size]
            batch_num = (i // batch_size) + 1
            total_batches = (len(old_news_docs) + batch_size - 1) // batch_size
            
            logger.info(f"Processing batch {batch_num}/{total_batches} ({len(batch_docs)} items)")
            
            if not dry_run:
                try:
                    # Create a batch
                    batch = db_client.batch()
                    
                    # Add deletions to batch
                    for doc in batch_docs:
                        batch.delete(doc.reference)
                    
                    # Commit the batch
                    batch.commit()
                    raw_news_deleted += len(batch_docs)
                    logger.info(f"Successfully deleted batch {batch_num} ({len(batch_docs)} items)")
                    
                except Exception as e:
                    logger.error(f"Error deleting batch {batch_num}: {e}")
                    errors += 1
                    # Try individual deletions for this batch
                    logger.info(f"Attempting individual deletions for batch {batch_num}")
                    for doc in batch_docs:
                        try:
                            doc.reference.delete()
                            raw_news_deleted += 1
                        except Exception as e_individual:
                            logger.error(f"Error deleting individual item {doc.id}: {e_individual}")
                            errors += 1
            else:
                raw_news_deleted += len(batch_docs)
                # Log some sample items for dry run
                for j, doc in enumerate(batch_docs[:3]):  # Show first 3 items of each batch
                    news_data = doc.to_dict()
                    pub_date = news_data.get('publication_date')
                    title = news_data.get('title_raw', 'Unknown')[:50]
                    
                    if isinstance(pub_date, datetime):
                        pub_date_str = pub_date.strftime('%Y-%m-%d')
                    else:
                        pub_date_str = str(pub_date)
                    
                    logger.info(f"[DRY RUN] Would delete: {doc.id} - {title} ({pub_date_str})")
                
                if len(batch_docs) > 3:
                    logger.info(f"[DRY RUN] ... and {len(batch_docs) - 3} more items in this batch")
        
        # Handle related evidence items
        if related_evidence_ids:
            logger.info(f"Processing {len(related_evidence_ids)} related evidence items...")
            
            evidence_docs_to_delete = []
            for evidence_id in related_evidence_ids:
                try:
                    evidence_doc_ref = db_client.collection(EVIDENCE_ITEMS_COLLECTION).document(evidence_id)
                    evidence_doc = evidence_doc_ref.get()
                    
                    if evidence_doc.exists:
                        evidence_docs_to_delete.append(evidence_doc_ref)
                        evidence_items_found += 1
                        
                        if dry_run:
                            evidence_data = evidence_doc.to_dict()
                            evidence_date = evidence_data.get('evidence_date')
                            title = evidence_data.get('title_or_summary', 'Unknown')[:50]
                            
                            if isinstance(evidence_date, datetime):
                                evidence_date_str = evidence_date.strftime('%Y-%m-%d')
                            else:
                                evidence_date_str = str(evidence_date)
                            
                            logger.info(f"[DRY RUN] Would delete evidence: {evidence_id} - {title} ({evidence_date_str})")
                    else:
                        logger.debug(f"Evidence item {evidence_id} not found (may have been deleted already)")
                        
                except Exception as e:
                    logger.error(f"Error checking evidence item {evidence_id}: {e}")
                    errors += 1
            
            # Delete evidence items in batches
            if evidence_docs_to_delete and not dry_run:
                logger.info(f"Deleting {len(evidence_docs_to_delete)} evidence items in batches...")
                for i in range(0, len(evidence_docs_to_delete), batch_size):
                    batch_refs = evidence_docs_to_delete[i:i + batch_size]
                    batch_num = (i // batch_size) + 1
                    total_batches = (len(evidence_docs_to_delete) + batch_size - 1) // batch_size
                    
                    logger.info(f"Deleting evidence batch {batch_num}/{total_batches} ({len(batch_refs)} items)")
                    
                    try:
                        # Create a batch
                        batch = db_client.batch()
                        
                        # Add deletions to batch
                        for doc_ref in batch_refs:
                            batch.delete(doc_ref)
                        
                        # Commit the batch
                        batch.commit()
                        evidence_items_deleted += len(batch_refs)
                        logger.info(f"Successfully deleted evidence batch {batch_num}")
                        
                    except Exception as e:
                        logger.error(f"Error deleting evidence batch {batch_num}: {e}")
                        errors += 1
                        # Try individual deletions
                        for doc_ref in batch_refs:
                            try:
                                doc_ref.delete()
                                evidence_items_deleted += 1
                            except Exception as e_individual:
                                logger.error(f"Error deleting individual evidence item: {e_individual}")
                                errors += 1
            elif dry_run:
                evidence_items_deleted = evidence_items_found
        
    except Exception as e:
        logger.error(f"Error during cleanup process: {e}", exc_info=True)
        errors += 1
    
    # Summary
    logger.info("--- Cleanup Summary ---")
    logger.info(f"Raw news items found: {raw_news_found}")
    logger.info(f"Raw news items {'would be deleted' if dry_run else 'deleted'}: {raw_news_deleted}")
    logger.info(f"Evidence items found: {evidence_items_found}")
    logger.info(f"Evidence items {'would be deleted' if dry_run else 'deleted'}: {evidence_items_deleted}")
    logger.info(f"Errors encountered: {errors}")
    logger.info("--- End Cleanup Summary ---")

def main():
    parser = argparse.ArgumentParser(description="Clean up news items from before the 44th Parliament (2021-11-21) using batch deletions.")
    parser.add_argument("--dry_run", action="store_true", help="Perform a dry run without deleting from Firestore.")
    parser.add_argument("--log_level", type=str, default="INFO", choices=["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"], help="Set the logging level.")
    parser.add_argument("--batch_size", type=int, default=DEFAULT_BATCH_SIZE, help=f"Number of items to delete in each batch. Default: {DEFAULT_BATCH_SIZE}")
    
    args = parser.parse_args()
    logger.setLevel(getattr(logging, args.log_level.upper()))
    
    if db is None:
        logger.critical("Firestore client (db) is not initialized. Cannot proceed. Check Firebase configuration and credentials.")
        return
    
    # Confirm with user if not dry run
    if not args.dry_run:
        print(f"\n⚠️  WARNING: This will permanently delete news items from before {PARLIAMENT_44TH_START_DATE}")
        print("This action cannot be undone!")
        print(f"Using batch size: {args.batch_size}")
        response = input("\nAre you sure you want to proceed? Type 'yes' to continue: ")
        if response.lower() != 'yes':
            print("Operation cancelled.")
            return
    
    cleanup_old_news_items_batch(db, args.dry_run, args.batch_size)

if __name__ == "__main__":
    main() 