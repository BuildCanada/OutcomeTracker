#!/usr/bin/env python3
"""
Prepare News Documents for Evidence Processing

This script updates raw_news_releases documents to prepare them for evidence processing by:
1. Adding the required evidence_processing_status field
2. Mapping field names to what the process_news_to_evidence.py script expects
3. Filtering by date range to only process recent documents

CLI arguments:
--dry_run: If True, will not write to Firestore. Default: False
--limit: Maximum number of documents to process. Default: 1000
--start_date: Start date for processing (YYYY-MM-DD). Default: 2025-03-01
--end_date: End date for processing (YYYY-MM-DD). Default: today
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
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(filename)s:%(lineno)d - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger("prepare_news_for_evidence_processing")

# --- Constants ---
RAW_NEWS_RELEASES_COLLECTION = "raw_news_releases"

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
                app_name = 'prepare_news_app'
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

def prepare_document_for_processing(doc_snapshot, dry_run: bool = False) -> dict:
    """
    Prepare a single document for evidence processing.
    Returns a result dictionary with status information.
    """
    result = {
        'doc_id': doc_snapshot.id,
        'status': 'error',
        'message': '',
        'updated': False
    }
    
    try:
        doc_data = doc_snapshot.to_dict()
        
        # Check if already has correct status
        current_status = doc_data.get('evidence_processing_status')
        if current_status == 'pending_evidence_creation':
            result['status'] = 'already_ready'
            result['message'] = 'Document already has pending_evidence_creation status'
            return result
        
        # Prepare update data
        update_data = {}
        
        # Map field names if needed
        if 'title' in doc_data and 'title_raw' not in doc_data:
            update_data['title_raw'] = doc_data['title']
            
        if 'description' in doc_data and 'summary_or_snippet_raw' not in doc_data:
            update_data['summary_or_snippet_raw'] = doc_data['description']
        
        # Set evidence processing status
        update_data['evidence_processing_status'] = 'pending_evidence_creation'
        update_data['prepared_for_evidence_processing_at'] = firestore.SERVER_TIMESTAMP
        
        if not update_data:
            result['status'] = 'no_updates_needed'
            result['message'] = 'Document already has all required fields'
            return result
        
        if dry_run:
            result['status'] = 'would_update'
            result['message'] = f'Would update with: {list(update_data.keys())}'
            result['updated'] = True
            return result
        
        # Perform the update
        doc_snapshot.reference.update(update_data)
        
        result['status'] = 'success'
        result['message'] = f'Updated with: {list(update_data.keys())}'
        result['updated'] = True
        
        return result
        
    except Exception as e:
        result['message'] = f'Update error: {str(e)}'
        logger.error(f"Error preparing document {doc_snapshot.id}: {e}", exc_info=True)
        return result

def get_documents_to_prepare(start_date_dt: date, end_date_dt: date, limit: int = 1000):
    """
    Get documents that need preparation for evidence processing.
    """
    logger.info(f"Scanning for documents from {start_date_dt} to {end_date_dt} (limit: {limit})...")
    
    # Convert dates to datetime objects for Firestore query
    start_datetime_utc = datetime.combine(start_date_dt, datetime.min.time(), tzinfo=timezone.utc)
    end_datetime_utc = datetime.combine(end_date_dt, datetime.max.time(), tzinfo=timezone.utc)
    
    # Query documents in date range
    query = db.collection(RAW_NEWS_RELEASES_COLLECTION)
    query = query.where(filter=firestore.FieldFilter("publication_date", ">=", start_datetime_utc))
    query = query.where(filter=firestore.FieldFilter("publication_date", "<=", end_datetime_utc))
    query = query.limit(limit)
    
    docs = list(query.stream())
    
    logger.info(f"Found {len(docs)} documents in date range")
    
    return docs

def prepare_documents_batch(docs_to_prepare, batch_size: int = 25, dry_run: bool = False):
    """
    Prepare documents in batches with progress tracking.
    """
    total_docs = len(docs_to_prepare)
    logger.info(f"Starting preparation of {total_docs} documents in batches of {batch_size}")
    
    if dry_run:
        logger.warning("*** DRY RUN MODE: No changes will be made to Firestore ***")
    
    stats = {
        'total': total_docs,
        'success': 0,
        'already_ready': 0,
        'no_updates_needed': 0,
        'errors': 0,
        'would_update': 0
    }
    
    # Process in batches
    for i in range(0, total_docs, batch_size):
        batch = docs_to_prepare[i:i + batch_size]
        batch_num = (i // batch_size) + 1
        total_batches = (total_docs + batch_size - 1) // batch_size
        
        logger.info(f"🔄 Processing batch {batch_num}/{total_batches} ({len(batch)} documents)")
        
        for j, doc in enumerate(batch):
            doc_num = i + j + 1
            doc_data = doc.to_dict()
            title = doc_data.get('title', doc_data.get('title_raw', 'No title'))[:50]
            logger.info(f"  📄 [{doc_num}/{total_docs}] Preparing: {title}...")
            
            result = prepare_document_for_processing(doc, dry_run)
            
            if result['status'] == 'success':
                stats['success'] += 1
                logger.info(f"     ✅ Success: {result['message']}")
            elif result['status'] == 'would_update':
                stats['would_update'] += 1
                logger.info(f"     🔄 [DRY RUN] {result['message']}")
            elif result['status'] == 'already_ready':
                stats['already_ready'] += 1
                logger.info(f"     ✅ Already ready: {result['message']}")
            elif result['status'] == 'no_updates_needed':
                stats['no_updates_needed'] += 1
                logger.info(f"     ✅ No updates: {result['message']}")
            else:
                stats['errors'] += 1
                logger.error(f"     ❌ Error: {result['message']}")
        
        # Small delay between batches
        if batch_num < total_batches:
            time.sleep(0.5)
    
    return stats

def main():
    parser = argparse.ArgumentParser(description="Prepare raw_news_releases documents for evidence processing.")
    parser.add_argument("--dry_run", action="store_true", help="Perform a dry run without making changes to Firestore.")
    parser.add_argument("--limit", type=int, default=1000, help="Maximum number of documents to process (default: 1000).")
    parser.add_argument("--batch_size", type=int, default=25, help="Number of documents to process in each batch (default: 25).")
    parser.add_argument("--start_date", type=str, default="2025-03-01", help="Start date for processing (YYYY-MM-DD, default: 2025-03-01).")
    parser.add_argument("--end_date", type=str, help="End date for processing (YYYY-MM-DD, default: today).")
    parser.add_argument("--log_level", type=str, default="INFO", choices=["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"], help="Set the logging level.")

    args = parser.parse_args()
    logger.setLevel(getattr(logging, args.log_level.upper()))

    if db is None:
        logger.critical("Firestore client not initialized. Check Firebase configuration.")
        return

    # Parse dates
    try:
        start_date_dt = datetime.strptime(args.start_date, "%Y-%m-%d").date()
    except ValueError:
        logger.error(f"Invalid start_date: {args.start_date}. Use YYYY-MM-DD format.")
        return
    
    end_date_dt = datetime.strptime(args.end_date, "%Y-%m-%d").date() if args.end_date else date.today()
    
    if start_date_dt > end_date_dt:
        logger.error(f"Start date {start_date_dt} is after end date {end_date_dt}.")
        return

    logger.info("🚀 " + "=" * 60)
    logger.info("🚀 PREPARING NEWS DOCUMENTS FOR EVIDENCE PROCESSING")
    logger.info("🚀 " + "=" * 60)
    logger.info(f"📅 Date range: {start_date_dt} to {end_date_dt}")
    logger.info(f"📊 Limit: {args.limit}")
    logger.info(f"📦 Batch size: {args.batch_size}")
    logger.info(f"🧪 Dry run: {args.dry_run}")
    logger.info("=" * 70)

    start_time = time.time()
    
    try:
        # Get documents to prepare
        docs_to_prepare = get_documents_to_prepare(start_date_dt, end_date_dt, args.limit)
        
        if not docs_to_prepare:
            logger.info("🎉 No documents found in the specified date range!")
            return
        
        # Show some examples
        logger.info("📋 Examples of documents to prepare:")
        for i, doc in enumerate(docs_to_prepare[:3]):
            doc_data = doc.to_dict()
            pub_date = doc_data.get('publication_date', 'N/A')
            title = doc_data.get('title', doc_data.get('title_raw', 'N/A'))
            status = doc_data.get('evidence_processing_status', 'NOT_SET')
            logger.info(f"  {i+1}. ID: {doc.id[:20]}...")
            logger.info(f"     Title: {title[:60]}...")
            logger.info(f"     Date: {pub_date}")
            logger.info(f"     Status: {status}")
        
        if len(docs_to_prepare) > 3:
            logger.info(f"  ... and {len(docs_to_prepare) - 3} more documents")
        
        # Perform preparation
        stats = prepare_documents_batch(docs_to_prepare, args.batch_size, args.dry_run)
        
        # Final summary
        total_time = time.time() - start_time
        logger.info("🎉 " + "=" * 60)
        logger.info("🎉 PREPARATION COMPLETE!")
        logger.info("🎉 " + "=" * 60)
        logger.info(f"⏱️  Total runtime: {total_time:.2f} seconds")
        logger.info(f"📊 Documents processed: {stats['total']}")
        
        if args.dry_run:
            logger.info(f"🔄 Would update: {stats['would_update']}")
        else:
            logger.info(f"✅ Successfully updated: {stats['success']}")
            logger.info(f"✅ Already ready: {stats['already_ready']}")
            logger.info(f"✅ No updates needed: {stats['no_updates_needed']}")
        
        logger.info(f"❌ Errors: {stats['errors']}")
        
        if not args.dry_run and stats['success'] > 0:
            logger.info("✨ Documents are now ready for evidence processing!")
            logger.info("   Run: python process_news_to_evidence.py")
        
    except Exception as e:
        logger.error(f"Preparation failed with error: {e}", exc_info=True)
        raise

if __name__ == "__main__":
    main() 