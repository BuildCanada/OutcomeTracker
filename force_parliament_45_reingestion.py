#!/usr/bin/env python3
"""
Force Parliament 45 Bill Re-ingestion

This script forces re-ingestion of Parliament 45 bills by deleting existing
raw data items so they can be re-ingested with the updated stage detection logic.
"""

import logging
import sys
from pathlib import Path
from datetime import datetime, timezone

# Add core directory to path
core_dir = Path(__file__).parent / "pipeline" / "core"
sys.path.insert(0, str(core_dir))

from base_job import BaseJob

class ForceParliament45ReingestionJob(BaseJob):
    """Force re-ingestion of Parliament 45 bills"""
    
    def __init__(self):
        super().__init__(job_name="force_parliament_45_reingestion")
    
    def _execute_job(self):
        """Execute the forced re-ingestion process"""
        try:
            self.logger.info("Starting forced re-ingestion of Parliament 45 bills")
            
            # Step 1: Find all Parliament 45 raw bill items
            raw_items = self._find_parliament_45_raw_items()
            self.logger.info(f"Found {len(raw_items)} Parliament 45 raw bill items")
            
            # Step 2: Delete existing raw items to force re-ingestion
            deleted_count = self._delete_raw_items(raw_items)
            self.logger.info(f"Deleted {deleted_count} raw bill items")
            
            # Step 3: Run the ingestion
            ingestion_result = self._run_ingestion()
            
            return {
                'status': 'success',
                'raw_items_deleted': deleted_count,
                'ingestion_result': ingestion_result
            }
            
        except Exception as e:
            self.logger.error(f"Error in forced re-ingestion: {e}")
            return {
                'status': 'error',
                'error': str(e)
            }
    
    def _find_parliament_45_raw_items(self):
        """Find all Parliament 45 raw bill items"""
        from google.cloud import firestore
        
        # Try different possible field names and values
        possible_queries = [
            ('parliament_session', '45-1'),
            ('parliament_session', '45'),
            ('parliament_session_id', '45-1'),
            ('parliament_session_id', '45'),
        ]
        
        all_items = []
        
        for field_name, field_value in possible_queries:
            try:
                query = (
                    self.db.collection('raw_legisinfo_bill_details')
                    .where(filter=firestore.FieldFilter(field_name, '==', field_value))
                )
                
                items = list(query.stream())
                if items:
                    self.logger.info(f"Found {len(items)} items with {field_name}={field_value}")
                    all_items.extend(items)
                    break  # Use the first successful query
                    
            except Exception as e:
                self.logger.debug(f"Query with {field_name}={field_value} failed: {e}")
                continue
        
        # Also try to find any recent bill items
        if not all_items:
            try:
                # Get all raw bill items and filter manually
                query = self.db.collection('raw_legisinfo_bill_details').limit(100)
                all_raw_items = list(query.stream())
                
                for item in all_raw_items:
                    data = item.to_dict()
                    # Check if this looks like a Parliament 45 bill
                    bill_code = data.get('bill_code', '')
                    if bill_code and any(code in bill_code for code in ['C-', 'S-']):
                        # Check raw JSON content for Parliament 45
                        raw_content = data.get('raw_json_content', '')
                        if '45-1' in str(raw_content) or '"ParliamentNumber": 45' in str(raw_content):
                            all_items.append(item)
                            
            except Exception as e:
                self.logger.error(f"Error finding raw items manually: {e}")
        
        return all_items
    
    def _delete_raw_items(self, raw_items):
        """Delete raw bill items"""
        deleted_count = 0
        
        for item in raw_items:
            try:
                item.reference.delete()
                deleted_count += 1
                self.logger.debug(f"Deleted raw item: {item.id}")
                
            except Exception as e:
                self.logger.error(f"Error deleting raw item {item.id}: {e}")
        
        return deleted_count
    
    def _run_ingestion(self):
        """Run the Parliament 45 ingestion"""
        try:
            # Import and run the ingestion
            pipeline_dir = Path(__file__).parent / "pipeline"
            sys.path.insert(0, str(pipeline_dir))
            
            from stages.ingestion.legisinfo_bills import LegisInfoBillsIngestion
            
            # Configuration for Parliament 45 ingestion
            config = {
                'min_parliament': 45,
                'max_parliament': 45,
                'include_xml': True,
                'batch_size': 10
            }
            
            ingestion_job = LegisInfoBillsIngestion(config)
            
            # Force re-ingestion with large since_hours
            result = ingestion_job.execute(since_hours=8760)  # 1 year
            
            return {
                'status': result.status.value,
                'metadata': result.metadata
            }
            
        except Exception as e:
            self.logger.error(f"Error running ingestion: {e}")
            return {
                'status': 'error',
                'error': str(e)
            }

def main():
    """Main execution function"""
    job = ForceParliament45ReingestionJob()
    result = job.execute()
    
    print(f"Forced re-ingestion completed with status: {result.status.value}")
    if result.metadata:
        print(f"Raw items deleted: {result.metadata.get('raw_items_deleted', 0)}")
        ingestion_result = result.metadata.get('ingestion_result', {})
        print(f"Ingestion status: {ingestion_result.get('status', 'unknown')}")

if __name__ == "__main__":
    main() 