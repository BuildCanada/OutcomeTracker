#!/usr/bin/env python3
"""
Migrate News Document IDs - One-time migration script

This script migrates raw_news_releases documents that have the old long hex ID format 
(created by the bulk ingestion script) to the new standardized format: YYYYMMDD_CANADANEWS_[hash]

The script will:
1. Identify documents with old hex-only IDs (64 characters, no underscores)
2. Generate new proper IDs using publication_date and source_url
3. Create new documents with proper IDs
4. Copy all data from old to new documents
5. Delete old documents (with safety checks)

CLI arguments:
--dry_run: If True, will not write to Firestore or delete documents. Default: False
--limit: Maximum number of documents to process in one run. Default: 100
--batch_size: Number of documents to process in each batch. Default: 10
"""

import os
import sys
import logging
import hashlib
from datetime import datetime, timezone
from dotenv import load_dotenv
import firebase_admin
from firebase_admin import credentials, firestore
import argparse
import time
import re

# --- Configuration ---
load_dotenv()

# --- Logger Setup ---
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(filename)s:%(lineno)d - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger("migrate_news_document_ids")

# --- Constants ---
RAW_NEWS_RELEASES_COLLECTION = "raw_news_releases"
OLD_ID_PATTERN = re.compile(r'^[a-f0-9]{64}$')  # 64-character hex string
NEW_ID_PATTERN = re.compile(r'^\d{8}_CANADANEWS_[a-f0-9]{12}$')  # YYYYMMDD_CANADANEWS_hash

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
                app_name = 'migrate_news_ids_app'
                try:
                    firebase_admin.initialize_app(cred, name=app_name)
                except ValueError:
                    app_name_unique = f"{app_name}_{str(time.time())}"
                    firebase_admin.initialize_app(cred, name=app_name_unique)
                    app_name = app_name_unique

                project_id_sa_env = os.getenv('FIREBASE_PROJECT_ID', '[Not Set - Using Service Account]')
                logger.info(f"Connected to CLOUD Firestore (Project: {project_id_sa_env}) via service account.")
                db = firestore.client(app=firebase_admin.get_app(name=app_name))
            except Exception as e_sa:
                logger.critical(f"Firebase init with service account key from {cred_path} failed: {e_sa}", exc_info=True)
        else:
            logger.warning("FIREBASE_SERVICE_ACCOUNT_KEY_PATH environment variable not set, and default creds failed.")

if db is None:
    logger.critical("CRITICAL: Failed to obtain Firestore client. Exiting.")
    exit("Exiting: Firestore client not available.")

# --- Helper Functions ---

def is_old_format_id(doc_id: str) -> bool:
    """Check if a document ID uses the old long hex format."""
    return bool(OLD_ID_PATTERN.match(doc_id))

def is_new_format_id(doc_id: str) -> bool:
    """Check if a document ID uses the new standardized format."""
    return bool(NEW_ID_PATTERN.match(doc_id))

def generate_new_id(publication_date_dt: datetime, source_url: str) -> str:
    """Generate a new standardized ID using the same logic as the fixed scripts."""
    date_yyyymmdd_str = publication_date_dt.strftime('%Y%m%d')
    original_hash_input = f"{source_url}_{publication_date_dt.isoformat()}"
    full_hash = hashlib.sha256(original_hash_input.encode('utf-8')).hexdigest()
    short_hash = full_hash[:12]
    return f"{date_yyyymmdd_str}_CANADANEWS_{short_hash}"

def get_documents_to_migrate(limit: int = 100):
    """
    Get documents that need migration (old hex format IDs).
    Returns a list of document snapshots.
    """
    logger.info(f"Scanning for documents with old format IDs (limit: {limit})...")
    
    # Get all documents and filter by ID pattern
    collection_ref = db.collection(RAW_NEWS_RELEASES_COLLECTION)
    
    # We can't filter by document ID pattern in Firestore query, so we need to get all and filter
    all_docs = list(collection_ref.limit(limit * 2).stream())  # Get more than limit to account for filtering
    
    old_format_docs = []
    new_format_count = 0
    
    for doc in all_docs:
        if is_old_format_id(doc.id):
            old_format_docs.append(doc)
            if len(old_format_docs) >= limit:
                break
        elif is_new_format_id(doc.id):
            new_format_count += 1
    
    logger.info(f"Found {len(old_format_docs)} documents with old format IDs")
    logger.info(f"Found {new_format_count} documents with new format IDs")
    
    return old_format_docs

def migrate_document(old_doc, dry_run: bool = False) -> dict:
    """
    Migrate a single document from old to new format.
    Returns a result dictionary with status information.
    """
    result = {
        'old_id': old_doc.id,
        'new_id': None,
        'status': 'error',
        'message': '',
        'migrated': False
    }
    
    try:
        doc_data = old_doc.to_dict()
        
        # Validate required fields
        if not doc_data.get('publication_date'):
            result['message'] = 'Missing publication_date field'
            return result
        
        if not doc_data.get('source_url'):
            result['message'] = 'Missing source_url field'
            return result
        
        # Extract publication date
        publication_date = doc_data['publication_date']
        if isinstance(publication_date, str):
            # Try to parse string date
            try:
                publication_date_dt = datetime.fromisoformat(publication_date.replace('Z', '+00:00'))
            except:
                result['message'] = f'Could not parse publication_date: {publication_date}'
                return result
        elif hasattr(publication_date, 'timestamp'):
            # Firestore timestamp
            publication_date_dt = publication_date
        else:
            result['message'] = f'Invalid publication_date type: {type(publication_date)}'
            return result
        
        # Generate new ID
        source_url = doc_data['source_url']
        new_id = generate_new_id(publication_date_dt, source_url)
        result['new_id'] = new_id
        
        # Check if new document already exists
        new_doc_ref = db.collection(RAW_NEWS_RELEASES_COLLECTION).document(new_id)
        
        if not dry_run:
            existing_new_doc = new_doc_ref.get()
            if existing_new_doc.exists:
                result['status'] = 'skipped'
                result['message'] = f'Document with new ID {new_id} already exists'
                return result
        
        # Prepare new document data
        new_doc_data = doc_data.copy()
        new_doc_data['raw_item_id'] = new_id  # Update the raw_item_id field to match
        new_doc_data['migrated_from_old_id'] = old_doc.id  # Add migration tracking
        new_doc_data['migration_timestamp'] = firestore.SERVER_TIMESTAMP
        
        if dry_run:
            result['status'] = 'would_migrate'
            result['message'] = f'Would migrate {old_doc.id} -> {new_id}'
            result['migrated'] = True
            return result
        
        # Perform the migration
        # 1. Create new document
        new_doc_ref.set(new_doc_data)
        logger.debug(f"Created new document: {new_id}")
        
        # 2. Delete old document
        old_doc.reference.delete()
        logger.debug(f"Deleted old document: {old_doc.id}")
        
        result['status'] = 'success'
        result['message'] = f'Successfully migrated {old_doc.id} -> {new_id}'
        result['migrated'] = True
        
        return result
        
    except Exception as e:
        result['message'] = f'Migration error: {str(e)}'
        logger.error(f"Error migrating document {old_doc.id}: {e}", exc_info=True)
        return result

def migrate_documents_batch(docs_to_migrate, batch_size: int = 10, dry_run: bool = False):
    """
    Migrate documents in batches with progress tracking.
    """
    total_docs = len(docs_to_migrate)
    logger.info(f"Starting migration of {total_docs} documents in batches of {batch_size}")
    
    if dry_run:
        logger.warning("*** DRY RUN MODE: No changes will be made to Firestore ***")
    
    stats = {
        'total': total_docs,
        'success': 0,
        'skipped': 0,
        'errors': 0,
        'would_migrate': 0
    }
    
    # Process in batches
    for i in range(0, total_docs, batch_size):
        batch = docs_to_migrate[i:i + batch_size]
        batch_num = (i // batch_size) + 1
        total_batches = (total_docs + batch_size - 1) // batch_size
        
        logger.info(f"🔄 Processing batch {batch_num}/{total_batches} ({len(batch)} documents)")
        
        for j, doc in enumerate(batch):
            doc_num = i + j + 1
            logger.info(f"  📄 [{doc_num}/{total_docs}] Migrating: {doc.id}")
            
            result = migrate_document(doc, dry_run)
            
            if result['status'] == 'success':
                stats['success'] += 1
                logger.info(f"     ✅ Success: {result['message']}")
            elif result['status'] == 'would_migrate':
                stats['would_migrate'] += 1
                logger.info(f"     🔄 [DRY RUN] {result['message']}")
            elif result['status'] == 'skipped':
                stats['skipped'] += 1
                logger.info(f"     ⏭️  Skipped: {result['message']}")
            else:
                stats['errors'] += 1
                logger.error(f"     ❌ Error: {result['message']}")
        
        # Small delay between batches to avoid overwhelming Firestore
        if batch_num < total_batches:
            time.sleep(1)
    
    return stats

def main():
    parser = argparse.ArgumentParser(description="Migrate raw_news_releases document IDs from old hex format to new standardized format.")
    parser.add_argument("--dry_run", action="store_true", help="Perform a dry run without making changes to Firestore.")
    parser.add_argument("--limit", type=int, default=100, help="Maximum number of documents to process in one run (default: 100).")
    parser.add_argument("--batch_size", type=int, default=10, help="Number of documents to process in each batch (default: 10).")
    parser.add_argument("--log_level", type=str, default="INFO", choices=["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"], help="Set the logging level.")

    args = parser.parse_args()
    logger.setLevel(getattr(logging, args.log_level.upper()))

    if db is None:
        logger.critical("Firestore client not initialized. Check Firebase configuration.")
        return

    logger.info("🚀 " + "=" * 60)
    logger.info("🚀 STARTING NEWS DOCUMENT ID MIGRATION")
    logger.info("🚀 " + "=" * 60)
    logger.info(f"📊 Limit: {args.limit}")
    logger.info(f"📦 Batch size: {args.batch_size}")
    logger.info(f"🧪 Dry run: {args.dry_run}")
    logger.info("=" * 70)

    start_time = time.time()
    
    try:
        # Get documents to migrate
        docs_to_migrate = get_documents_to_migrate(args.limit)
        
        if not docs_to_migrate:
            logger.info("🎉 No documents found with old format IDs. Migration not needed!")
            return
        
        # Show some examples
        logger.info("📋 Examples of documents to migrate:")
        for i, doc in enumerate(docs_to_migrate[:3]):
            doc_data = doc.to_dict()
            pub_date = doc_data.get('publication_date', 'N/A')
            title = doc_data.get('title', doc_data.get('title_raw', 'N/A'))
            logger.info(f"  {i+1}. ID: {doc.id}")
            logger.info(f"     Title: {title[:80]}...")
            logger.info(f"     Date: {pub_date}")
        
        if len(docs_to_migrate) > 3:
            logger.info(f"  ... and {len(docs_to_migrate) - 3} more documents")
        
        # Confirm before proceeding (unless dry run)
        if not args.dry_run:
            logger.warning("⚠️  This will DELETE old documents and CREATE new ones!")
            logger.warning("⚠️  Make sure you have a backup of your Firestore data!")
        
        # Perform migration
        stats = migrate_documents_batch(docs_to_migrate, args.batch_size, args.dry_run)
        
        # Final summary
        total_time = time.time() - start_time
        logger.info("🎉 " + "=" * 60)
        logger.info("🎉 MIGRATION COMPLETE!")
        logger.info("🎉 " + "=" * 60)
        logger.info(f"⏱️  Total runtime: {total_time:.2f} seconds")
        logger.info(f"📊 Documents processed: {stats['total']}")
        
        if args.dry_run:
            logger.info(f"🔄 Would migrate: {stats['would_migrate']}")
        else:
            logger.info(f"✅ Successfully migrated: {stats['success']}")
            logger.info(f"⏭️  Skipped (already exist): {stats['skipped']}")
        
        logger.info(f"❌ Errors: {stats['errors']}")
        
        if stats['errors'] > 0:
            logger.warning("⚠️  Some documents had errors. Check the logs above for details.")
        
        if not args.dry_run and stats['success'] > 0:
            logger.info("✨ Migration successful! New documents use the standardized ID format.")
        
    except Exception as e:
        logger.error(f"Migration failed with error: {e}", exc_info=True)
        raise

if __name__ == "__main__":
    main() 