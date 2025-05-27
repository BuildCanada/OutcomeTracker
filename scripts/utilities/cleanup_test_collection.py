#!/usr/bin/env python3
"""
Cleanup Test Collection Utility

Removes inconsistent document IDs from the promises_test collection 
to prepare for proper document ID format testing.

Usage:
    python cleanup_test_collection.py --collection promises_test --dry_run
    python cleanup_test_collection.py --collection promises_test
"""

import os
import sys
import logging
import argparse
import re
from dotenv import load_dotenv
import firebase_admin
from firebase_admin import credentials, firestore

# Add parent directory to path for imports
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

load_dotenv()

# Logger setup
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(filename)s:%(lineno)d - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger("cleanup_test_collection")

# Firebase Configuration
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
                firebase_admin.initialize_app(cred, name='cleanup_test_collection')
                project_id_sa = os.getenv('FIREBASE_PROJECT_ID', '[Not Set - Using Service Account]')
                logger.info(f"Connected to CLOUD Firestore (Project: {project_id_sa}) via service account.")
                db = firestore.client(app=firebase_admin.get_app(name='cleanup_test_collection'))
            except Exception as e_sa:
                logger.critical(f"Firebase init with service account key from {cred_path} failed: {e_sa}", exc_info=True)
        else:
            logger.warning("FIREBASE_SERVICE_ACCOUNT_KEY_PATH environment variable not set, and default creds failed.")

if db is None:
    logger.critical("CRITICAL: Failed to obtain Firestore client. Exiting.")
    exit("Exiting: Firestore client not available.")

# Define patterns for proper vs inconsistent document IDs
PROPER_ID_PATTERN = re.compile(r'^[A-Z]{2,5}_\d{8}_[A-Z]{3,6}_[a-f0-9]{6,10}$')
INCONSISTENT_PATTERNS = [
    re.compile(r'^\d{8}_\d{4}_[a-z]+_[a-f0-9]{6}$'),  # 20250101_2025_lpc_104556
    re.compile(r'^[A-Za-z0-9]{20,}$'),  # Long random strings
]

def is_inconsistent_id(doc_id):
    """Check if a document ID uses an inconsistent format."""
    
    # Check if it matches the proper format first
    if PROPER_ID_PATTERN.match(doc_id):
        return False
    
    # Check if it matches any inconsistent patterns
    for pattern in INCONSISTENT_PATTERNS:
        if pattern.match(doc_id):
            return True
    
    # If it doesn't match proper format and doesn't match known inconsistent patterns,
    # consider it inconsistent for safety
    return True

def cleanup_collection(collection_name, dry_run=False):
    """Clean up inconsistent document IDs from the specified collection."""
    
    logger.info(f"🔄 Scanning collection '{collection_name}' for inconsistent document IDs...")
    
    if dry_run:
        logger.warning("⚠️  *** DRY RUN MODE: No deletions will be performed ***")
    
    try:
        collection_ref = db.collection(collection_name)
        docs = collection_ref.stream()
        
        total_docs = 0
        inconsistent_docs = []
        proper_docs = []
        
        for doc in docs:
            total_docs += 1
            doc_id = doc.id
            doc_data = doc.to_dict()
            
            if is_inconsistent_id(doc_id):
                inconsistent_docs.append({
                    'id': doc_id,
                    'source_type': doc_data.get('source_type', 'Unknown'),
                    'date_issued': doc_data.get('date_issued', 'Unknown'),
                    'text_preview': doc_data.get('text', 'No text')[:60] + '...'
                })
            else:
                proper_docs.append({
                    'id': doc_id,
                    'source_type': doc_data.get('source_type', 'Unknown'),
                    'date_issued': doc_data.get('date_issued', 'Unknown')
                })
        
        logger.info(f"📊 Scan results for '{collection_name}':")
        logger.info(f"   📋 Total documents: {total_docs}")
        logger.info(f"   ✅ Proper format: {len(proper_docs)}")
        logger.info(f"   ❌ Inconsistent format: {len(inconsistent_docs)}")
        
        if inconsistent_docs:
            logger.info(f"📝 Inconsistent documents found:")
            for i, doc_info in enumerate(inconsistent_docs[:10]):  # Show first 10
                logger.info(f"   {i+1}. {doc_info['id']} - {doc_info['source_type']} ({doc_info['date_issued']})")
                logger.info(f"      Text: {doc_info['text_preview']}")
            
            if len(inconsistent_docs) > 10:
                logger.info(f"   ... and {len(inconsistent_docs) - 10} more")
            
            if not dry_run:
                # Delete inconsistent documents
                logger.info(f"🗑️  Deleting {len(inconsistent_docs)} inconsistent documents...")
                
                batch = db.batch()
                batch_count = 0
                deleted_count = 0
                
                for doc_info in inconsistent_docs:
                    doc_ref = collection_ref.document(doc_info['id'])
                    batch.delete(doc_ref)
                    batch_count += 1
                    
                    # Commit in batches of 500 (Firestore limit)
                    if batch_count >= 500:
                        batch.commit()
                        deleted_count += batch_count
                        logger.info(f"   ✅ Deleted batch of {batch_count} documents ({deleted_count} total)")
                        batch = db.batch()
                        batch_count = 0
                
                # Commit remaining documents
                if batch_count > 0:
                    batch.commit()
                    deleted_count += batch_count
                    logger.info(f"   ✅ Deleted final batch of {batch_count} documents")
                
                logger.info(f"🎉 Successfully deleted {deleted_count} inconsistent documents!")
            else:
                logger.info(f"🔄 [DRY RUN] Would delete {len(inconsistent_docs)} inconsistent documents")
        else:
            logger.info(f"✅ No inconsistent documents found in '{collection_name}'!")
        
        if proper_docs:
            logger.info(f"📝 Proper format documents (keeping these):")
            for i, doc_info in enumerate(proper_docs[:5]):  # Show first 5
                logger.info(f"   {i+1}. {doc_info['id']} - {doc_info['source_type']} ({doc_info['date_issued']})")
            if len(proper_docs) > 5:
                logger.info(f"   ... and {len(proper_docs) - 5} more proper documents")
        
        return {
            'total_docs': total_docs,
            'proper_docs': len(proper_docs),
            'inconsistent_docs': len(inconsistent_docs),
            'deleted': len(inconsistent_docs) if not dry_run else 0
        }
        
    except Exception as e:
        logger.error(f"Error during cleanup: {e}", exc_info=True)
        return None

def main():
    parser = argparse.ArgumentParser(description='Clean up inconsistent document IDs from test collection')
    parser.add_argument('--collection', required=True, help='Collection name to clean up (e.g., promises_test)')
    parser.add_argument('--dry_run', action='store_true', help='Run without making changes')
    
    args = parser.parse_args()
    
    logger.info("🧹 Starting collection cleanup...")
    logger.info(f"📄 Target collection: {args.collection}")
    
    results = cleanup_collection(args.collection, dry_run=args.dry_run)
    
    if results:
        logger.info("🎉 " + "="*50)
        logger.info("🎉 CLEANUP COMPLETE!")
        logger.info("🎉 " + "="*50)
        logger.info(f"📊 Results summary: {results}")
        logger.info("=" * 60)
    else:
        logger.error("❌ Cleanup failed")

if __name__ == "__main__":
    main() 