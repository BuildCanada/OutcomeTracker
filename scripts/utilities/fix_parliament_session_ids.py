#!/usr/bin/env python3
"""
Fix Parliament Session IDs

This script updates all evidence items that have parliament_session_id in the
format '45-1' to use just the parliament number '45', which is the standard
format used throughout the promise tracker system.
"""

import sys
import logging
from pathlib import Path
from datetime import datetime, timezone

# Add the PromiseTracker directory to the path
promise_tracker_dir = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(promise_tracker_dir))

import firebase_admin
from firebase_admin import credentials, firestore

def setup_logging():
    """Setup logging configuration"""
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s',
        handlers=[
            logging.StreamHandler(sys.stdout),
            logging.FileHandler('fix_parliament_session_ids.log')
        ]
    )

def initialize_firebase():
    """Initialize Firebase Admin SDK"""
    try:
        # Check if already initialized
        firebase_admin.get_app()
        logging.info("Firebase already initialized")
    except ValueError:
        # Initialize Firebase
        cred = credentials.ApplicationDefault()
        firebase_admin.initialize_app(cred)
        logging.info("Firebase initialized successfully")
    
    return firestore.client()

def get_evidence_items_to_fix(db, batch_size=100):
    """Get evidence items that need parliament_session_id fixes"""
    try:
        # Query for evidence items with parliament_session_id ending in '-1' or similar patterns
        # We'll check for common patterns like '45-1', '44-1', etc.
        patterns_to_fix = ['44-1', '45-1', '46-1']  # Add more as needed
        
        all_items = []
        for pattern in patterns_to_fix:
            logging.info(f"Querying for evidence items with parliament_session_id: {pattern}")
            
            query = (db.collection('evidence_items')
                    .where(filter=firestore.FieldFilter('parliament_session_id', '==', pattern)))
            
            items = []
            for doc in query.stream():
                item_data = doc.to_dict()
                item_data['_doc_id'] = doc.id
                items.append(item_data)
            
            logging.info(f"Found {len(items)} evidence items with parliament_session_id: {pattern}")
            all_items.extend(items)
        
        return all_items
        
    except Exception as e:
        logging.error(f"Error querying evidence items: {e}")
        return []

def fix_parliament_session_id(parliament_session_id):
    """Convert parliament session ID from '45-1' format to '45' format"""
    if '-' in parliament_session_id:
        return parliament_session_id.split('-')[0]
    return parliament_session_id

def update_evidence_items(db, evidence_items, dry_run=True):
    """Update evidence items with corrected parliament_session_id"""
    updated_count = 0
    error_count = 0
    
    for item in evidence_items:
        try:
            doc_id = item['_doc_id']
            current_session_id = item.get('parliament_session_id', '')
            new_session_id = fix_parliament_session_id(current_session_id)
            
            if current_session_id == new_session_id:
                logging.debug(f"No change needed for {doc_id}: {current_session_id}")
                continue
            
            logging.info(f"Updating {doc_id}: {current_session_id} -> {new_session_id}")
            
            if not dry_run:
                # Update the document
                doc_ref = db.collection('evidence_items').document(doc_id)
                doc_ref.update({
                    'parliament_session_id': new_session_id,
                    'parliament_session_id_fixed_at': datetime.now(timezone.utc),
                    'parliament_session_id_previous': current_session_id
                })
                
            updated_count += 1
            
        except Exception as e:
            logging.error(f"Error updating evidence item {item.get('_doc_id', 'unknown')}: {e}")
            error_count += 1
    
    return updated_count, error_count

def main():
    """Main function"""
    import argparse
    
    parser = argparse.ArgumentParser(description='Fix parliament session IDs in evidence items')
    parser.add_argument('--dry-run', action='store_true', default=True,
                        help='Run in dry-run mode (no actual updates)')
    parser.add_argument('--execute', action='store_true',
                        help='Actually execute the updates (overrides dry-run)')
    
    args = parser.parse_args()
    
    # Determine if this is a dry run
    dry_run = not args.execute
    
    setup_logging()
    
    logging.info("=" * 60)
    logging.info("Parliament Session ID Fix Script")
    logging.info(f"Mode: {'DRY RUN' if dry_run else 'EXECUTE'}")
    logging.info("=" * 60)
    
    try:
        # Initialize Firebase
        db = initialize_firebase()
        
        # Get evidence items to fix
        logging.info("Finding evidence items with incorrect parliament_session_id format...")
        evidence_items = get_evidence_items_to_fix(db)
        
        if not evidence_items:
            logging.info("No evidence items found that need fixing.")
            return
        
        logging.info(f"Found {len(evidence_items)} evidence items to fix")
        
        # Show summary of what will be changed
        session_id_changes = {}
        for item in evidence_items:
            current = item.get('parliament_session_id', '')
            new = fix_parliament_session_id(current)
            if current != new:
                session_id_changes[current] = session_id_changes.get(current, 0) + 1
        
        logging.info("Summary of changes:")
        for old_id, count in session_id_changes.items():
            new_id = fix_parliament_session_id(old_id)
            logging.info(f"  {old_id} -> {new_id}: {count} items")
        
        if dry_run:
            logging.info("\nThis is a DRY RUN. No changes will be made.")
            logging.info("To execute the changes, run with --execute flag")
        else:
            # Confirm before proceeding
            response = input("\nProceed with updates? (yes/no): ")
            if response.lower() != 'yes':
                logging.info("Update cancelled by user")
                return
        
        # Update evidence items
        logging.info(f"\n{'Simulating' if dry_run else 'Executing'} updates...")
        updated_count, error_count = update_evidence_items(db, evidence_items, dry_run)
        
        # Summary
        logging.info("\n" + "=" * 60)
        logging.info("SUMMARY")
        logging.info("=" * 60)
        logging.info(f"Items processed: {len(evidence_items)}")
        logging.info(f"Items {'would be ' if dry_run else ''}updated: {updated_count}")
        logging.info(f"Errors: {error_count}")
        
        if dry_run:
            logging.info("\nNo actual changes were made (dry run mode)")
        else:
            logging.info("\nAll updates completed successfully!")
        
    except KeyboardInterrupt:
        logging.info("\nScript interrupted by user")
    except Exception as e:
        logging.error(f"Script failed with error: {e}", exc_info=True)

if __name__ == "__main__":
    main() 