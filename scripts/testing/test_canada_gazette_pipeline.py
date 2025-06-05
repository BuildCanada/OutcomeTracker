#!/usr/bin/env python3
from firebase_admin import firestore

"""
Canada Gazette Pipeline Validation Test

Tests the complete Canada Gazette pipeline flow:
1. Ingestion: Gazette issues → raw_gazette_p2_notices collection
2. Processing: raw_gazette_p2_notices → evidence_items collection
3. Validation: Check field mappings, data integrity, and pipeline functionality
"""

import sys
import logging
from pathlib import Path
from datetime import datetime, timezone, timedelta
from typing import Dict, Any, List

# Add pipeline directory to path
pipeline_dir = Path(__file__).parent.parent.parent
sys.path.insert(0, str(pipeline_dir))

from pipeline.core.base_job import BaseJob
from pipeline.stages.ingestion.canada_gazette import CanadaGazetteIngestion
from pipeline.stages.processing.canada_gazette_processor import CanadaGazetteProcessor


class CanadaGazettePipelineTest(BaseJob):
    """Canada Gazette pipeline validation test"""
    
    def __init__(self):
        super().__init__("canada_gazette_pipeline_test")
        self.test_results = {
            'ingestion': {'passed': False, 'details': []},
            'processing': {'passed': False, 'details': []},
            'validation': {'passed': False, 'details': []},
            'overall': {'passed': False, 'summary': ''}
        }
    
    def _execute_job(self, **kwargs) -> Dict[str, Any]:
        """Execute the Canada Gazette pipeline test"""
        try:
            self.logger.info("="*60)
            self.logger.info("STARTING CANADA GAZETTE PIPELINE VALIDATION")
            self.logger.info("="*60)
            
            # Step 1: Test Ingestion
            self.logger.info("\n🔄 STEP 1: Testing Canada Gazette Ingestion...")
            ingestion_success = self._test_ingestion()
            
            if not ingestion_success:
                self.logger.error("❌ Ingestion test failed. Stopping pipeline test.")
                return self._compile_results()
            
            # Step 2: Test Processing
            self.logger.info("\n🔄 STEP 2: Testing Gazette Processing...")
            processing_success = self._test_processing()
            
            if not processing_success:
                self.logger.error("❌ Processing test failed. Stopping pipeline test.")
                return self._compile_results()
            
            # Step 3: Validate Results
            self.logger.info("\n🔄 STEP 3: Validating End-to-End Results...")
            validation_success = self._validate_pipeline()
            
            # Compile final results
            overall_success = ingestion_success and processing_success and validation_success
            self.test_results['overall']['passed'] = overall_success
            
            if overall_success:
                self.logger.info("\n✅ CANADA GAZETTE PIPELINE VALIDATION SUCCESSFUL!")
                self.test_results['overall']['summary'] = "All pipeline stages working correctly"
            else:
                self.logger.error("\n❌ CANADA GAZETTE PIPELINE VALIDATION FAILED!")
                self.test_results['overall']['summary'] = "Pipeline issues detected"
            
            return self._compile_results()
            
        except Exception as e:
            self.logger.error(f"Canada Gazette test failed with exception: {e}")
            self.test_results['overall']['summary'] = f"Test failed with exception: {e}"
            return self._compile_results()
    
    def _test_ingestion(self) -> bool:
        """Test the Canada Gazette ingestion pipeline"""
        try:
            self.logger.info("  🔍 Running Canada Gazette ingestion...")
            
            # Configure ingestion job
            config = {
                'max_issues_per_run': 2,  # Test with small number
                'scrape_full_text': True
            }
            
            ingestion_job = CanadaGazetteIngestion("test_gazette_ingestion", config)
            result = ingestion_job.execute()
            
            # Check ingestion results
            if result.status.value == 'success':
                items_created = result.items_created
                self.logger.info(f"  ✅ Ingestion completed: {items_created} items created")
                
                # Validate field structure of newly created items
                if items_created > 0:
                    recent_items = self._get_recent_gazette_items(limit=2)
                    field_validation = self._validate_gazette_item_fields(recent_items)
                    
                    if field_validation:
                        self.test_results['ingestion']['passed'] = True
                        self.test_results['ingestion']['details'] = [
                            f"Successfully created {items_created} items",
                            "Field structure validation passed",
                            f"Tested {len(recent_items)} recent items"
                        ]
                        return True
                    else:
                        self.test_results['ingestion']['details'] = ["Field structure validation failed"]
                        return False
                else:
                    self.logger.info("  ⚠️  No new items created (may be expected if no new regulations)")
                    # Still consider this a success if no errors occurred
                    self.test_results['ingestion']['passed'] = True
                    self.test_results['ingestion']['details'] = ["No new items created (no new regulations)"]
                    return True
            else:
                self.logger.error(f"  ❌ Ingestion failed: {result.error_message}")
                self.test_results['ingestion']['details'] = [f"Ingestion job failed: {result.error_message}"]
                return False
                
        except Exception as e:
            self.logger.error(f"  ❌ Ingestion test exception: {e}")
            self.test_results['ingestion']['details'] = [f"Exception during ingestion: {e}"]
            return False
    
    def _test_processing(self) -> bool:
        """Test the Canada Gazette processing pipeline"""
        try:
            self.logger.info("  🔍 Running gazette processing...")
            
            # Configure processing job
            config = {
                'extract_regulatory_details': True,  # Enable full analysis
                'limit': 3,  # Process small batch
                'status_filter': 'pending_evidence_creation'
            }
            
            processing_job = CanadaGazetteProcessor("test_gazette_processing", config)
            result = processing_job.execute()
            
            # Check processing results
            if result.status.value == 'success':
                items_processed = result.items_processed
                items_created = result.items_created
                self.logger.info(f"  ✅ Processing completed: {items_processed} processed, {items_created} evidence items created")
                
                # Validate evidence items structure
                if items_created > 0:
                    recent_evidence = self._get_recent_gazette_evidence_items(limit=2)
                    evidence_validation = self._validate_gazette_evidence_fields(recent_evidence)
                    
                    if evidence_validation:
                        self.test_results['processing']['passed'] = True
                        self.test_results['processing']['details'] = [
                            f"Successfully processed {items_processed} items",
                            f"Created {items_created} evidence items",
                            "Evidence structure validation passed"
                        ]
                        return True
                    else:
                        self.test_results['processing']['details'] = ["Evidence structure validation failed"]
                        return False
                else:
                    self.logger.info("  ⚠️  No evidence items created (may be expected if no pending items)")
                    # Check if there were items to process
                    if items_processed > 0:
                        self.test_results['processing']['details'] = ["Items processed but no evidence created"]
                        return False
                    else:
                        self.test_results['processing']['passed'] = True
                        self.test_results['processing']['details'] = ["No pending items to process"]
                        return True
            else:
                self.logger.error(f"  ❌ Processing failed: {result.error_message}")
                self.test_results['processing']['details'] = [f"Processing job failed: {result.error_message}"]
                return False
                
        except Exception as e:
            self.logger.error(f"  ❌ Processing test exception: {e}")
            self.test_results['processing']['details'] = [f"Exception during processing: {e}"]
            return False
    
    def _validate_pipeline(self) -> bool:
        """Validate the complete Canada Gazette pipeline flow"""
        try:
            self.logger.info("  🔍 Validating pipeline data flow...")
            
            # Get sample of recent items from both collections
            gazette_items = self._get_recent_gazette_items(limit=3)
            evidence_items = self._get_recent_gazette_evidence_items(limit=3)
            
            validation_results = []
            
            # Check that gazette items have correct field names
            if gazette_items:
                self.logger.info(f"    📋 Checking {len(gazette_items)} gazette items...")
                for item in gazette_items:
                    # Check for production field names
                    required_fields = ['raw_gazette_item_id', 'regulation_title', 'source_url_regulation_html', 
                                     'registration_sor_si_number', 'full_text_scraped', 'gazette_issue_url']
                    missing_fields = [field for field in required_fields if field not in item]
                    
                    if missing_fields:
                        validation_results.append(f"Gazette item missing fields: {missing_fields}")
                    else:
                        validation_results.append("Gazette item field structure correct")
            
            # Check evidence items structure
            if evidence_items:
                self.logger.info(f"    📋 Checking {len(evidence_items)} evidence items...")
                for item in evidence_items:
                    required_fields = ['title_or_summary', 'description_or_details', 'evidence_source_type', 
                                     'publication_date', 'source_url', 'registration_sor_si_number']
                    missing_fields = [field for field in required_fields if field not in item]
                    
                    if missing_fields:
                        validation_results.append(f"Evidence item missing fields: {missing_fields}")
                    else:
                        validation_results.append("Evidence item structure correct")
                        
                    # Check evidence ID pattern (YYYYMMDD_{session}_{source}_{hash})
                    evidence_id = item.get('evidence_id', '')
                    if evidence_id:
                        parts = evidence_id.split('_')
                        if len(parts) >= 4 and parts[2] == 'Gazette2':
                            validation_results.append("Evidence ID pattern matches production")
                        else:
                            validation_results.append(f"Evidence ID pattern incorrect: {evidence_id}")
            
            # Check data flow consistency
            if gazette_items and evidence_items:
                # Find evidence items that reference gazette items
                gazette_ids = {item.get('raw_gazette_item_id') for item in gazette_items}
                evidence_refs = {item.get('additional_metadata', {}).get('raw_gazette_notice_id') for item in evidence_items}
                
                if gazette_ids.intersection(evidence_refs):
                    validation_results.append("Data flow linkage verified")
                else:
                    validation_results.append("No linkage found between gazette and evidence items")
            
            # Determine overall validation result
            failed_validations = [result for result in validation_results if "missing" in result or "No linkage" in result or "incorrect" in result]
            
            if not failed_validations:
                self.test_results['validation']['passed'] = True
                self.test_results['validation']['details'] = validation_results
                self.logger.info("  ✅ Pipeline validation passed")
                return True
            else:
                self.test_results['validation']['details'] = validation_results
                self.logger.error(f"  ❌ Pipeline validation failed: {failed_validations}")
                return False
                
        except Exception as e:
            self.logger.error(f"  ❌ Validation exception: {e}")
            self.test_results['validation']['details'] = [f"Exception during validation: {e}"]
            return False
    
    def _get_recent_gazette_items(self, limit: int = 5) -> List[Dict[str, Any]]:
        """Get recent gazette items"""
        try:
            collection = self.db.collection('raw_gazette_p2_notices')
            docs = collection.order_by('ingested_at', direction='DESCENDING').limit(limit).stream()
            return [doc.to_dict() for doc in docs]
        except Exception as e:
            self.logger.error(f"Error fetching recent gazette items: {e}")
            return []
    
    def _get_recent_gazette_evidence_items(self, limit: int = 5) -> List[Dict[str, Any]]:
        """Get recent gazette evidence items"""
        try:
            collection = self.db.collection('evidence_items')
            # Filter by evidence source type for gazette
            docs = collection.where(filter=firestore.FieldFilter('evidence_source_type', '==', 'Regulation (Canada Gazette P2))').order_by('created_at', direction='DESCENDING').limit(limit).stream()
            return [doc.to_dict() for doc in docs]
        except Exception as e:
            self.logger.error(f"Error fetching recent gazette evidence items: {e}")
            return []
    
    def _validate_gazette_item_fields(self, items: List[Dict[str, Any]]) -> bool:
        """Validate that gazette items have correct production field names"""
        if not items:
            return True
        
        required_production_fields = [
            'raw_gazette_item_id', 'regulation_title', 'source_url_regulation_html',
            'registration_sor_si_number', 'full_text_scraped', 'gazette_issue_url',
            'parliament_session_id_assigned', 'evidence_processing_status'
        ]
        
        for item in items:
            # Check that production fields exist
            missing_fields = [field for field in required_production_fields if field not in item]
            if missing_fields:
                self.logger.error(f"Gazette item missing production fields: {missing_fields}")
                return False
        
        return True
    
    def _validate_gazette_evidence_fields(self, items: List[Dict[str, Any]]) -> bool:
        """Validate gazette evidence item structure"""
        if not items:
            return True
        
        required_fields = [
            'title_or_summary', 'description_or_details', 'evidence_source_type',
            'publication_date', 'source_url', 'created_at', 'registration_sor_si_number',
            'source_url_regulation_html', 'gazette_analysis'
        ]
        
        for item in items:
            missing_fields = [field for field in required_fields if field not in item]
            if missing_fields:
                self.logger.error(f"Gazette evidence item missing fields: {missing_fields}")
                return False
        
        return True
    
    def _compile_results(self) -> Dict[str, Any]:
        """Compile test results for return"""
        total_tests = 3
        passed_tests = sum(1 for stage in ['ingestion', 'processing', 'validation'] 
                          if self.test_results[stage]['passed'])
        
        return {
            'items_processed': total_tests,
            'items_created': 0,
            'items_updated': 0,
            'items_skipped': total_tests - passed_tests,
            'errors': total_tests - passed_tests,
            'metadata': {
                'test_type': 'canada_gazette_pipeline',
                'results': self.test_results,
                'summary': f"{passed_tests}/{total_tests} tests passed"
            }
        }


def main():
    """Run the Canada Gazette pipeline test"""
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    test = CanadaGazettePipelineTest()
    result = test.execute()
    
    print("\n" + "="*60)
    print("CANADA GAZETTE PIPELINE TEST RESULTS")
    print("="*60)
    
    test_results = result.metadata['results']
    
    for stage, data in test_results.items():
        if stage == 'overall':
            continue
        status = "✅ PASSED" if data['passed'] else "❌ FAILED"
        print(f"\n{stage.upper()}: {status}")
        for detail in data['details']:
            print(f"  • {detail}")
    
    overall_status = "✅ PASSED" if test_results['overall']['passed'] else "❌ FAILED"
    print(f"\nOVERALL: {overall_status}")
    print(f"Summary: {test_results['overall']['summary']}")
    print(f"Test Results: {result.metadata['summary']}")
    
    return 0 if test_results['overall']['passed'] else 1


if __name__ == "__main__":
    sys.exit(main()) 