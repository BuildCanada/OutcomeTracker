#!/usr/bin/env python3
"""
Reset No Matches Status Script

Resets all evidence items with 'no_matches' status back to 'pending' 
so they can be reprocessed by the updated evidence_linker logic.

The updated evidence_linker no longer assigns 'no_matches' - it assigns
'processed' with empty promise_ids arrays when no matches are found.

Usage:
    python reset_no_matches_status.py [--dry-run]
"""

import sys
import logging
import argparse
from pathlib import Path
from typing import Dict, Any

# Add project root to path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from pipeline.core.base_job import BaseJob
from google.cloud import firestore

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

logger = logging.getLogger(__name__)

class NoMatchesResetter(BaseJob):
    """Reset evidence items from 'no_matches' status to 'pending'."""
    
    def __init__(self):
        super().__init__("no_matches_resetter", {})
        self.evidence_collection = 'evidence_items'
    
    def _execute_job(self, **kwargs):
        """Required abstract method - not used in this script."""
        return {}
    
    def reset_no_matches_items(self, dry_run: bool = False) -> Dict[str, Any]:
        """
        Reset all evidence items with 'no_matches' status to 'pending'.
        
        Args:
            dry_run: If True, don't actually update the database
            
        Returns:
            Statistics about the reset operation
        """
        stats = {
            'items_found': 0,
            'items_reset': 0,
            'errors': 0,
            'dry_run': dry_run
        }
        
        try:
            # Query for all evidence items with 'no_matches' status
            logger.info("Querying for evidence items with 'no_matches' status...")
            
            query = self.db.collection(self.evidence_collection).where(
                filter=firestore.FieldFilter('promise_linking_status', '==', 'no_matches')
            )
            
            items_to_reset = []
            for doc in query.stream():
                doc_data = doc.to_dict()
                items_to_reset.append({
                    'doc_id': doc.id,
                    'evidence_id': doc_data.get('evidence_id', doc.id),
                    'parliament_session': doc_data.get('parliament_session_id', 'unknown'),
                    'source_type': doc_data.get('evidence_source_type', 'unknown'),
                    'existing_promise_ids': doc_data.get('promise_ids', [])
                })
            
            stats['items_found'] = len(items_to_reset)
            logger.info(f"Found {len(items_to_reset)} evidence items with 'no_matches' status")
            
            if not items_to_reset:
                logger.info("No items to reset - all good!")
                return stats
            
            # Show sample of items to be reset
            logger.info("Sample items to be reset:")
            for i, item in enumerate(items_to_reset[:5]):
                existing_links = len(item['existing_promise_ids'])
                logger.info(f"  {i+1}. {item['evidence_id']} (session: {item['parliament_session']}, "
                           f"type: {item['source_type']}, existing links: {existing_links})")
            
            if len(items_to_reset) > 5:
                logger.info(f"  ... and {len(items_to_reset) - 5} more items")
            
            if dry_run:
                logger.info("🔍 DRY RUN MODE - No changes will be made")
                return stats
            
            # Confirm reset operation
            logger.warning(f"About to reset {len(items_to_reset)} evidence items from 'no_matches' to 'pending'")
            
            # Reset items in batches
            batch_size = 50
            for i in range(0, len(items_to_reset), batch_size):
                batch = items_to_reset[i:i + batch_size]
                
                for item in batch:
                    try:
                        doc_ref = self.db.collection(self.evidence_collection).document(item['doc_id'])
                        
                        # Reset to pending status, preserve existing promise_ids
                        update_data = {
                            'promise_linking_status': 'pending',
                            'promise_linking_processed_at': firestore.DELETE_FIELD,
                            'hybrid_linking_timestamp': firestore.DELETE_FIELD,
                            'hybrid_linking_method': firestore.DELETE_FIELD,
                            'hybrid_linking_avg_confidence': firestore.DELETE_FIELD,
                            'promise_links_found': firestore.DELETE_FIELD
                        }
                        
                        doc_ref.update(update_data)
                        stats['items_reset'] += 1
                        
                        if stats['items_reset'] % 10 == 0:
                            logger.info(f"Reset {stats['items_reset']}/{len(items_to_reset)} items...")
                        
                    except Exception as e:
                        logger.error(f"Error resetting item {item['doc_id']}: {e}")
                        stats['errors'] += 1
            
            logger.info(f"✅ Reset complete: {stats['items_reset']} items reset, {stats['errors']} errors")
            
        except Exception as e:
            logger.error(f"Fatal error in reset operation: {e}")
            stats['errors'] += 1
            raise
        
        return stats

def main():
    parser = argparse.ArgumentParser(description='Reset evidence items from no_matches to pending status')
    parser.add_argument('--dry-run', action='store_true',
                        help='Show what would be reset without making changes')
    
    args = parser.parse_args()
    
    print("🔄 Evidence Items No-Matches Status Resetter")
    print("=" * 60)
    
    if args.dry_run:
        print("🔍 DRY RUN MODE - No changes will be made")
    
    try:
        resetter = NoMatchesResetter()
        stats = resetter.reset_no_matches_items(dry_run=args.dry_run)
        
        print("\n" + "=" * 60)
        print("📊 Reset Summary:")
        print(f"Items Found: {stats['items_found']}")
        print(f"Items Reset: {stats['items_reset']}")
        print(f"Errors: {stats['errors']}")
        print(f"Dry Run: {stats['dry_run']}")
        
        if not args.dry_run and stats['items_reset'] > 0:
            print("\n✨ These items will now be reprocessed by the evidence_linker")
            print("   and marked as 'processed' with appropriate promise_ids arrays")
        
    except KeyboardInterrupt:
        print("\n🛑 Interrupted by user")
    except Exception as e:
        print(f"\n❌ Error: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main() 