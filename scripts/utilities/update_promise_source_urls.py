#!/usr/bin/env python3
"""
Update Promise Source URLs Script

Updates the source_url field in the promises collection based on the appears_in field
and date_issued for 2025 LPC promises.

Logic:
- For "Both" or "SFT Only" or date_issued="2025-05-27": Use Throne Speech URL
- For "Platform Only" or date_issued="2025-04-19": Use Platform URL

Usage:
    python update_promise_source_urls.py --dry_run  # Preview changes
    python update_promise_source_urls.py            # Apply changes
"""

import os
import sys
import logging
import argparse
from datetime import datetime
from dotenv import load_dotenv
import firebase_admin
from firebase_admin import credentials, firestore

load_dotenv()

# Logger setup
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(filename)s:%(lineno)d - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger("update_promise_source_urls")

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
                firebase_admin.initialize_app(cred, name='update_source_urls')
                project_id_sa = os.getenv('FIREBASE_PROJECT_ID', '[Not Set - Using Service Account]')
                logger.info(f"Connected to CLOUD Firestore (Project: {project_id_sa}) via service account.")
                db = firestore.client(app=firebase_admin.get_app(name='update_source_urls'))
            except Exception as e_sa:
                logger.critical(f"Firebase init with service account key from {cred_path} failed: {e_sa}", exc_info=True)
        else:
            logger.warning("FIREBASE_SERVICE_ACCOUNT_KEY_PATH environment variable not set, and default creds failed.")

if db is None:
    logger.critical("CRITICAL: Failed to obtain Firestore client. Exiting.")
    exit("Exiting: Firestore client not available.")

# Source URLs
PLATFORM_URL = "https://liberal.ca/wp-content/uploads/sites/292/2025/04/Canada-Strong.pdf"
THRONE_SPEECH_URL = "https://www.canada.ca/en/privy-council/campaigns/speech-throne/2025/building-canada-strong.html"

def determine_source_url(promise_data):
    """Determine the appropriate source URL based on promise data."""
    appears_in = promise_data.get('appears_in', '')
    date_issued = promise_data.get('date_issued', '')
    
    # Check if this is a 2025 LPC promise
    source_type = promise_data.get('source_type', '')
    is_2025_lpc = ('2025' in source_type or 
                   date_issued == '2025-04-19' or 
                   date_issued == '2025-05-27')
    
    if not is_2025_lpc:
        return None  # Don't update non-2025 promises
    
    # Determine URL based on appears_in field or date
    if appears_in in ['Both', 'SFT Only'] or date_issued == '2025-05-27':
        return THRONE_SPEECH_URL
    elif appears_in == 'Platform Only' or date_issued == '2025-04-19':
        return PLATFORM_URL
    
    # Default for 2025 LPC promises without clear source indication
    return PLATFORM_URL

def update_promise_source_urls(collection_name="promises", dry_run=False):
    """Update source_url field for promises in the collection."""
    
    logger.info(f"🔄 Starting source URL update for collection: {collection_name}")
    if dry_run:
        logger.warning("⚠️  *** DRY RUN MODE: No changes will be written to Firestore ***")
    
    updated_count = 0
    skipped_count = 0
    error_count = 0
    
    try:
        # Get all promises from the collection
        promises_ref = db.collection(collection_name)
        promises = promises_ref.stream()
        
        for promise_doc in promises:
            try:
                promise_data = promise_doc.to_dict()
                promise_id = promise_doc.id
                
                # Determine the appropriate source URL
                new_source_url = determine_source_url(promise_data)
                
                if new_source_url is None:
                    logger.debug(f"⏭️  Skipping {promise_id}: Not a 2025 LPC promise")
                    skipped_count += 1
                    continue
                
                current_source_url = promise_data.get('source_url', '')
                
                # Check if update is needed
                if current_source_url == new_source_url:
                    logger.debug(f"⏭️  Skipping {promise_id}: source_url already correct")
                    skipped_count += 1
                    continue
                
                # Log the update
                appears_in = promise_data.get('appears_in', 'Unknown')
                date_issued = promise_data.get('date_issued', 'Unknown')
                
                if dry_run:
                    logger.info(f"🔄 [DRY RUN] Would update {promise_id}:")
                    logger.info(f"    appears_in: {appears_in}")
                    logger.info(f"    date_issued: {date_issued}")
                    logger.info(f"    current_source_url: {current_source_url}")
                    logger.info(f"    new_source_url: {new_source_url}")
                else:
                    # Update the document
                    promise_doc.reference.update({
                        'source_url': new_source_url,
                        'last_updated_at': firestore.SERVER_TIMESTAMP
                    })
                    
                    logger.info(f"✅ Updated {promise_id}: {appears_in} -> {new_source_url}")
                
                updated_count += 1
                
                # Log progress every 50 updates
                if updated_count % 50 == 0:
                    logger.info(f"📊 Progress: {updated_count} updated, {skipped_count} skipped")
                
            except Exception as e:
                logger.error(f"❌ Error processing promise {promise_doc.id}: {e}", exc_info=True)
                error_count += 1
                continue
    
    except Exception as e:
        logger.error(f"❌ Error accessing collection {collection_name}: {e}", exc_info=True)
        return None
    
    # Final summary
    logger.info("🎉 " + "="*60)
    logger.info("🎉 SOURCE URL UPDATE COMPLETE!")
    logger.info("🎉 " + "="*60)
    logger.info(f"📊 Total updated: {updated_count}")
    logger.info(f"⏭️  Total skipped: {skipped_count}")
    logger.info(f"❌ Total errors: {error_count}")
    logger.info(f"🗃️  Collection: {collection_name}")
    if dry_run:
        logger.info("⚠️  DRY RUN: No actual changes were made")
    logger.info("=" * 70)
    
    return {
        'updated': updated_count,
        'skipped': skipped_count,
        'errors': error_count,
        'collection_name': collection_name,
        'dry_run': dry_run
    }

def main():
    parser = argparse.ArgumentParser(description='Update source_url field for 2025 LPC promises')
    parser.add_argument('--collection_name', default='promises', help='Firestore collection name (default: promises)')
    parser.add_argument('--dry_run', action='store_true', help='Run without making changes to Firestore')
    
    args = parser.parse_args()
    
    results = update_promise_source_urls(
        collection_name=args.collection_name,
        dry_run=args.dry_run
    )
    
    if results:
        logger.info(f"✅ Source URL update completed successfully!")
        logger.info(f"📋 Results summary: {results}")
    else:
        logger.error("❌ Source URL update failed")

if __name__ == "__main__":
    main() 