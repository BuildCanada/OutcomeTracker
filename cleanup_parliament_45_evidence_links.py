#!/usr/bin/env python3
"""
Cleanup Parliament 45 Evidence Links

This script removes orphaned references to old Parliament 45 evidence items
from promises' evidence_item_ids arrays. This is necessary because we deleted
the old single-stage evidence items and created new stage-based ones.
"""

import logging
import sys
from pathlib import Path
from datetime import datetime, timezone

# Add core directory to path
core_dir = Path(__file__).parent / "pipeline" / "core"
sys.path.insert(0, str(core_dir))

from base_job import BaseJob

class Parliament45LinkCleanupJob(BaseJob):
    """Clean up orphaned Parliament 45 evidence item links"""
    
    def __init__(self):
        super().__init__(job_name="parliament_45_link_cleanup")
        
    def _execute_job(self):
        """Execute the cleanup process"""
        try:
            self.logger.info("Starting Parliament 45 evidence link cleanup")
            
            # Step 1: Get all current Parliament 45 evidence item IDs
            current_evidence_ids = self._get_current_parliament_45_evidence_ids()
            self.logger.info(f"Found {len(current_evidence_ids)} current Parliament 45 evidence items")
            
            # Step 2: Find all promises with evidence_item_ids that might contain orphaned refs
            promises_to_check = self._get_promises_with_evidence_links()
            self.logger.info(f"Found {len(promises_to_check)} promises with evidence links to check")
            
            # Step 3: Clean up orphaned references
            cleaned_promises = self._clean_orphaned_references(promises_to_check, current_evidence_ids)
            
            self.logger.info(f"Cleanup completed successfully")
            return {
                'status': 'success',
                'current_evidence_items': len(current_evidence_ids),
                'promises_checked': len(promises_to_check),
                'promises_cleaned': cleaned_promises,
                'timestamp': datetime.now(timezone.utc).isoformat()
            }
            
        except Exception as e:
            self.logger.error(f"Error during cleanup: {e}")
            return {
                'status': 'error',
                'error': str(e),
                'timestamp': datetime.now(timezone.utc).isoformat()
            }
    
    def _get_current_parliament_45_evidence_ids(self) -> set:
        """Get all current Parliament 45 evidence item IDs"""
        try:
            from google.cloud import firestore
            
            query = (
                self.db.collection('evidence_items')
                .where(filter=firestore.FieldFilter('parliament_session_id', '==', '45'))
                .where(filter=firestore.FieldFilter('evidence_source_type', '==', 'Bill Event (LEGISinfo)'))
            )
            
            evidence_ids = set()
            for doc in query.stream():
                evidence_ids.add(doc.id)
            
            return evidence_ids
            
        except Exception as e:
            self.logger.error(f"Error getting current evidence IDs: {e}")
            return set()
    
    def _get_promises_with_evidence_links(self) -> list:
        """Get all promises that have evidence_item_ids arrays"""
        try:
            from google.cloud import firestore
            
            # Get all promises that have non-empty evidence_item_ids arrays
            query = (
                self.db.collection('promises')
                .where(filter=firestore.FieldFilter('evidence_item_ids', '>', []))
            )
            
            promises = []
            for doc in query.stream():
                promise_data = doc.to_dict()
                promise_data['_doc_id'] = doc.id
                promises.append(promise_data)
            
            return promises
            
        except Exception as e:
            self.logger.error(f"Error getting promises with evidence links: {e}")
            return []
    
    def _clean_orphaned_references(self, promises: list, valid_evidence_ids: set) -> int:
        """Clean orphaned evidence item references from promises"""
        cleaned_count = 0
        
        try:
            from google.cloud import firestore
            
            for promise in promises:
                doc_id = promise.get('_doc_id')
                evidence_item_ids = promise.get('evidence_item_ids', [])
                
                if not evidence_item_ids:
                    continue
                
                # Filter to keep only valid evidence item IDs
                valid_ids = [eid for eid in evidence_item_ids if eid in valid_evidence_ids]
                
                # Check if we found any orphaned references
                orphaned_ids = [eid for eid in evidence_item_ids if eid not in valid_evidence_ids]
                
                if orphaned_ids:
                    # Check if any are Parliament 45 related (contain parliament session in ID)
                    parl45_orphaned = [eid for eid in orphaned_ids if '45' in str(eid)]
                    
                    if parl45_orphaned:
                        self.logger.info(f"Promise {promise.get('promise_id', doc_id)}: removing {len(parl45_orphaned)} orphaned Parliament 45 evidence links")
                        self.logger.debug(f"  Orphaned IDs: {parl45_orphaned}")
                        
                        # Update the promise with cleaned evidence_item_ids
                        update_data = {
                            'evidence_item_ids': valid_ids,
                            'last_evidence_link_cleanup': firestore.SERVER_TIMESTAMP,
                            'cleanup_removed_orphaned_count': len(parl45_orphaned)
                        }
                        
                        doc_ref = self.db.collection('promises').document(doc_id)
                        doc_ref.update(update_data)
                        
                        cleaned_count += 1
            
            self.logger.info(f"Successfully cleaned {cleaned_count} promises")
            return cleaned_count
            
        except Exception as e:
            self.logger.error(f"Error cleaning orphaned references: {e}")
            return cleaned_count

def main():
    """Main execution function"""
    print("🧹 PARLIAMENT 45 EVIDENCE LINK CLEANUP")
    print("=" * 50)
    print("This script removes orphaned references to old Parliament 45")
    print("evidence items from promises' evidence_item_ids arrays.")
    print()
    
    job = Parliament45LinkCleanupJob()
    result = job.execute()
    
    print("✅ CLEANUP COMPLETED")
    print("=" * 30)
    print(f"📊 Status: {result.status.value}")
    print(f"⏰ Completed at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    if result.metadata:
        metadata = result.metadata
        print(f"📈 Results:")
        print(f"   - Current Parliament 45 evidence items: {metadata.get('current_evidence_items', 0)}")
        print(f"   - Promises checked: {metadata.get('promises_checked', 0)}")
        print(f"   - Promises cleaned: {metadata.get('promises_cleaned', 0)}")
    
    if result.status.value == 'success':
        print()
        print("🎉 Link cleanup successful!")
        print("   You can now run the evidence linker on Parliament 45 bills")
        print("   without worrying about orphaned link data.")
    else:
        print()
        print("⚠️  Cleanup completed with issues. Check logs for details.")

if __name__ == "__main__":
    main() 