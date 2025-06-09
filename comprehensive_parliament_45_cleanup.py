#!/usr/bin/env python3
"""
Comprehensive Parliament 45 Evidence Link Cleanup

This script completely removes ALL Parliament 45 evidence item links from:
1. All promises' evidence_item_ids arrays 
2. Resets ALL Parliament 45 evidence items to pending linking status

This creates a clean slate for re-linking with higher standards.
"""

import logging
import sys
from pathlib import Path
from datetime import datetime, timezone

# Add core directory to path
core_dir = Path(__file__).parent / "pipeline" / "core"
sys.path.insert(0, str(core_dir))

from base_job import BaseJob

class ComprehensiveParliament45CleanupJob(BaseJob):
    """Comprehensive cleanup of ALL Parliament 45 evidence links"""
    
    def __init__(self):
        super().__init__(job_name="comprehensive_parliament_45_cleanup")
        
    def _execute_job(self):
        """Execute the comprehensive cleanup process"""
        try:
            self.logger.info("Starting comprehensive Parliament 45 evidence link cleanup")
            
            # Step 1: Get all Parliament 45 evidence item IDs
            all_p45_evidence_ids = self._get_all_parliament_45_evidence_ids()
            self.logger.info(f"Found {len(all_p45_evidence_ids)} Parliament 45 evidence items total")
            
            # Step 2: Remove these evidence IDs from ALL promises
            cleaned_promises = self._remove_evidence_ids_from_all_promises(all_p45_evidence_ids)
            
            # Step 3: Reset ALL Parliament 45 evidence items to pending status
            reset_evidence_count = self._reset_all_parliament_45_evidence_status()
            
            self.logger.info(f"Comprehensive cleanup completed successfully")
            return {
                'status': 'success',
                'parliament_45_evidence_items': len(all_p45_evidence_ids),
                'promises_cleaned': cleaned_promises,
                'evidence_items_reset': reset_evidence_count,
                'timestamp': datetime.now(timezone.utc).isoformat()
            }
            
        except Exception as e:
            self.logger.error(f"Error during comprehensive cleanup: {e}")
            return {
                'status': 'error',
                'error': str(e),
                'timestamp': datetime.now(timezone.utc).isoformat()
            }
    
    def _get_all_parliament_45_evidence_ids(self) -> set:
        """Get ALL Parliament 45 evidence item IDs (all source types)"""
        try:
            from google.cloud import firestore
            
            # Get ALL Parliament 45 evidence items regardless of source type
            query = (
                self.db.collection('evidence_items')
                .where(filter=firestore.FieldFilter('parliament_session_id', '==', '45'))
            )
            
            evidence_ids = set()
            for doc in query.stream():
                evidence_ids.add(doc.id)
            
            self.logger.info(f"Found {len(evidence_ids)} total Parliament 45 evidence items")
            return evidence_ids
            
        except Exception as e:
            self.logger.error(f"Error getting Parliament 45 evidence IDs: {e}")
            return set()
    
    def _remove_evidence_ids_from_all_promises(self, evidence_ids_to_remove: set) -> int:
        """Remove Parliament 45 evidence IDs from ALL promises' evidence_item_ids arrays"""
        cleaned_count = 0
        
        try:
            from google.cloud import firestore
            
            self.logger.info(f"Scanning ALL promises for Parliament 45 evidence links to remove...")
            
            # Get ALL promises (no filtering) - we need to check every promise
            query = self.db.collection('promises')
            
            batch_size = 100
            batch = self.db.batch()
            batch_count = 0
            
            for doc in query.stream():
                doc_data = doc.to_dict()
                evidence_item_ids = doc_data.get('evidence_item_ids', [])
                
                if not evidence_item_ids:
                    continue
                
                # Filter out Parliament 45 evidence IDs
                original_count = len(evidence_item_ids)
                cleaned_evidence_ids = [eid for eid in evidence_item_ids if eid not in evidence_ids_to_remove]
                removed_count = original_count - len(cleaned_evidence_ids)
                
                if removed_count > 0:
                    self.logger.info(f"Promise {doc.id}: removing {removed_count} Parliament 45 evidence links")
                    
                    # Add update to batch
                    batch.update(doc.reference, {
                        'evidence_item_ids': cleaned_evidence_ids,
                        'last_comprehensive_cleanup': firestore.SERVER_TIMESTAMP,
                        'parliament_45_links_removed': removed_count
                    })
                    
                    cleaned_count += 1
                    batch_count += 1
                    
                    # Commit batch when it reaches batch_size
                    if batch_count >= batch_size:
                        batch.commit()
                        self.logger.info(f"Committed batch of {batch_count} promise updates")
                        batch = self.db.batch()
                        batch_count = 0
            
            # Commit any remaining updates
            if batch_count > 0:
                batch.commit()
                self.logger.info(f"Committed final batch of {batch_count} promise updates")
            
            self.logger.info(f"Successfully cleaned {cleaned_count} promises")
            return cleaned_count
            
        except Exception as e:
            self.logger.error(f"Error removing evidence IDs from promises: {e}")
            return cleaned_count
    
    def _reset_all_parliament_45_evidence_status(self) -> int:
        """Reset ALL Parliament 45 evidence items to pending linking status"""
        reset_count = 0
        
        try:
            from google.cloud import firestore
            
            self.logger.info("Resetting ALL Parliament 45 evidence items to pending status...")
            
            # Get ALL Parliament 45 evidence items
            query = (
                self.db.collection('evidence_items')
                .where(filter=firestore.FieldFilter('parliament_session_id', '==', '45'))
            )
            
            batch_size = 100
            batch = self.db.batch()
            batch_count = 0
            
            for doc in query.stream():
                # Reset linking status and clear existing links
                update_data = {
                    'promise_linking_status': 'pending',
                    'promise_ids': [],  # Clear existing promise links
                    'linked_evidence_ids': [],  # Clear any reverse links
                    'promise_links_found': 0,
                    'comprehensive_cleanup_reset_at': firestore.SERVER_TIMESTAMP,
                    'reset_reason': 'Comprehensive Parliament 45 cleanup for higher linking standards'
                }
                
                batch.update(doc.reference, update_data)
                reset_count += 1
                batch_count += 1
                
                # Commit batch when it reaches batch_size
                if batch_count >= batch_size:
                    batch.commit()
                    self.logger.info(f"Reset batch of {batch_count} evidence items")
                    batch = self.db.batch()
                    batch_count = 0
            
            # Commit any remaining updates
            if batch_count > 0:
                batch.commit()
                self.logger.info(f"Reset final batch of {batch_count} evidence items")
            
            self.logger.info(f"Successfully reset {reset_count} Parliament 45 evidence items")
            return reset_count
            
        except Exception as e:
            self.logger.error(f"Error resetting evidence items: {e}")
            return reset_count

def main():
    """Main execution function"""
    print("🧹 COMPREHENSIVE PARLIAMENT 45 EVIDENCE LINK CLEANUP")
    print("=" * 60)
    print("This script will:")
    print("1. Find ALL Parliament 45 evidence items (all source types)")
    print("2. Remove their IDs from ALL promises' evidence_item_ids arrays")
    print("3. Reset ALL Parliament 45 evidence items to pending status")
    print("4. Clear all existing promise links from evidence items")
    print()
    print("⚠️  This creates a completely clean slate for re-linking!")
    print()
    
    # Ask for confirmation
    response = input("Continue with comprehensive cleanup? (yes/no): ").lower().strip()
    if response != 'yes':
        print("❌ Cleanup cancelled")
        return
    
    print("\n🚀 Starting comprehensive cleanup...")
    
    job = ComprehensiveParliament45CleanupJob()
    result = job.execute()
    
    print("\n✅ COMPREHENSIVE CLEANUP COMPLETED")
    print("=" * 40)
    print(f"📊 Status: {result.status.value}")
    print(f"⏰ Completed at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    if result.metadata:
        metadata = result.metadata
        print(f"📈 Results:")
        print(f"   - Parliament 45 evidence items found: {metadata.get('parliament_45_evidence_items', 0)}")
        print(f"   - Promises cleaned: {metadata.get('promises_cleaned', 0)}")
        print(f"   - Evidence items reset: {metadata.get('evidence_items_reset', 0)}")
    
    if result.status.value == 'success':
        print()
        print("🎉 Comprehensive cleanup successful!")
        print("   ALL Parliament 45 evidence links have been removed.")
        print("   ALL Parliament 45 evidence items are now pending re-linking.")
        print("   Ready for re-linking with higher standards!")
    else:
        print()
        print("⚠️  Cleanup completed with issues. Check logs for details.")

if __name__ == "__main__":
    main() 