#!/usr/bin/env python3
"""
Reset Parliament 45 Bills for Stage-Based Processing

This script prepares Parliament 45 bills for the new stage-based evidence processing
by clearing existing single-stage evidence items and resetting processing status.
"""

import logging
import sys
from pathlib import Path
from datetime import datetime, timezone

# Add core directory to path
core_dir = Path(__file__).parent / "pipeline" / "core"
sys.path.insert(0, str(core_dir))

from base_job import BaseJob

class Parliament45StageResetJob(BaseJob):
    """Reset Parliament 45 bills for stage-based processing"""
    
    def __init__(self):
        super().__init__(job_name="parliament_45_stage_reset")
    
    def _execute_job(self):
        """Execute the reset process (required by BaseJob)"""
        try:
            self.logger.info("Starting Parliament 45 stage-based reset process")
            
            # Step 1: Find all Parliament 45 bill evidence items
            evidence_items = self._find_parliament_45_evidence_items()
            self.logger.info(f"Found {len(evidence_items)} Parliament 45 evidence items")
            
            # Step 2: Delete existing evidence items
            deleted_count = self._delete_evidence_items(evidence_items)
            self.logger.info(f"Deleted {deleted_count} evidence items")
            
            # Step 3: Find and reset any raw data items
            raw_items = self._find_parliament_45_raw_items()
            reset_count = self._reset_raw_items(raw_items)
            self.logger.info(f"Reset {reset_count} raw data items")
            
            # Summary
            self.logger.info(f"""
=== PARLIAMENT 45 STAGE RESET COMPLETE ===
Evidence items deleted: {deleted_count}
Raw items reset: {reset_count}
Ready for stage-based re-ingestion and processing
""")
            
            return {
                'items_processed': len(evidence_items) + len(raw_items),
                'items_created': 0,
                'items_updated': reset_count,
                'items_skipped': 0,
                'errors': 0,
                'metadata': {
                    'evidence_items_deleted': deleted_count,
                    'raw_items_reset': reset_count
                }
            }
            
        except Exception as e:
            self.logger.error(f"Reset process failed: {e}")
            raise
        
    def run(self):
        """Execute the reset process"""
        try:
            self.logger.info("Starting Parliament 45 stage-based reset process")
            
            # Step 1: Find all Parliament 45 bill evidence items
            evidence_items = self._find_parliament_45_evidence_items()
            self.logger.info(f"Found {len(evidence_items)} Parliament 45 evidence items")
            
            # Step 2: Delete existing evidence items
            deleted_count = self._delete_evidence_items(evidence_items)
            self.logger.info(f"Deleted {deleted_count} evidence items")
            
            # Step 3: Find and reset any raw data items
            raw_items = self._find_parliament_45_raw_items()
            reset_count = self._reset_raw_items(raw_items)
            self.logger.info(f"Reset {reset_count} raw data items")
            
            # Summary
            self.logger.info(f"""
=== PARLIAMENT 45 STAGE RESET COMPLETE ===
Evidence items deleted: {deleted_count}
Raw items reset: {reset_count}
Ready for stage-based re-ingestion and processing
""")
            
        except Exception as e:
            self.logger.error(f"Reset process failed: {e}")
            raise
            
    def _find_parliament_45_evidence_items(self):
        """Find all Parliament 45 bill evidence items"""
        try:
            # Query for Parliament 45 bill evidence items
            from google.cloud import firestore
            evidence_query = (
                self.db.collection('evidence_items')
                .where(filter=firestore.FieldFilter('parliament_session_id', '==', '45'))
                .where(filter=firestore.FieldFilter('evidence_source_type', '==', 'Bill Event (LEGISinfo)'))
            )
            
            evidence_items = []
            for doc in evidence_query.stream():
                evidence_data = doc.to_dict()
                evidence_data['doc_id'] = doc.id
                evidence_items.append(evidence_data)
                
            return evidence_items
            
        except Exception as e:
            self.logger.error(f"Error finding Parliament 45 evidence items: {e}")
            return []
            
    def _delete_evidence_items(self, evidence_items):
        """Delete evidence items and unlink promises"""
        deleted_count = 0
        
        for item in evidence_items:
            try:
                evidence_id = item.get('evidence_id')
                doc_id = item.get('doc_id')
                promise_ids = item.get('promise_ids', [])
                
                # Unlink from promises first
                if promise_ids:
                    self._unlink_from_promises(evidence_id, promise_ids)
                
                # Delete the evidence item
                self.db.collection('evidence_items').document(doc_id).delete()
                deleted_count += 1
                
                self.logger.info(f"Deleted evidence item: {evidence_id}")
                
            except Exception as e:
                self.logger.error(f"Error deleting evidence item {item.get('evidence_id', 'unknown')}: {e}")
                
        return deleted_count
        
    def _unlink_from_promises(self, evidence_id, promise_ids):
        """Remove evidence item from linked promises"""
        for promise_id in promise_ids:
            try:
                promise_ref = self.db.collection('promises').document(promise_id)
                promise_doc = promise_ref.get()
                
                if promise_doc.exists:
                    promise_data = promise_doc.to_dict()
                    evidence_ids = promise_data.get('evidence_ids', [])
                    
                    if evidence_id in evidence_ids:
                        evidence_ids.remove(evidence_id)
                        promise_ref.update({'evidence_ids': evidence_ids})
                        self.logger.debug(f"Unlinked {evidence_id} from promise {promise_id}")
                        
            except Exception as e:
                self.logger.error(f"Error unlinking from promise {promise_id}: {e}")
                
    def _find_parliament_45_raw_items(self):
        """Find raw bill data items for Parliament 45"""
        try:
            # Query for Parliament 45 raw bill items
            from google.cloud import firestore
            raw_query = (
                self.db.collection('raw_legisinfo_bill_details')
                .where(filter=firestore.FieldFilter('parliament_session', '==', '45-1'))
            )
            
            raw_items = []
            for doc in raw_query.stream():
                raw_data = doc.to_dict()
                raw_data['doc_id'] = doc.id
                raw_items.append(raw_data)
                
            return raw_items
            
        except Exception as e:
            self.logger.error(f"Error finding Parliament 45 raw items: {e}")
            return []
            
    def _reset_raw_items(self, raw_items):
        """Reset processing status of raw items"""
        reset_count = 0
        
        for item in raw_items:
            try:
                doc_id = item.get('doc_id')
                bill_code = item.get('bill_code', 'unknown')
                
                # Reset processing status
                from google.cloud import firestore
                update_data = {
                    'processing_status': 'pending',
                    'reset_for_stage_processing_at': firestore.SERVER_TIMESTAMP,
                    'reset_reason': 'Parliament 45 stage-based processing implementation'
                }
                
                self.db.collection('raw_legisinfo_bill_details').document(doc_id).update(update_data)
                reset_count += 1
                
                self.logger.info(f"Reset raw item for bill: {bill_code}")
                
            except Exception as e:
                self.logger.error(f"Error resetting raw item {item.get('bill_code', 'unknown')}: {e}")
                
        return reset_count

def main():
    """Main execution function"""
    job = Parliament45StageResetJob()
    result = job.execute()
    print(f"Reset completed with status: {result.status.value}")
    if result.metadata:
        print(f"Evidence items deleted: {result.metadata.get('evidence_items_deleted', 0)}")
        print(f"Raw items reset: {result.metadata.get('raw_items_reset', 0)}")

if __name__ == "__main__":
    main() 