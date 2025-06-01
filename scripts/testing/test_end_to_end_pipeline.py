#!/usr/bin/env python3
"""
End-to-End Pipeline Validation Test

Tests the complete pipeline flow:
1. Ingestion: Raw news items → raw_news_releases collection
2. Processing: raw_news_releases → evidence_items collection
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
from pipeline.stages.ingestion.canada_news import CanadaNewsIngestion
from pipeline.stages.processing.canada_news_processor import CanadaNewsProcessor


class EndToEndPipelineTest(BaseJob):
    """End-to-end pipeline validation test"""
    
    def __init__(self):
        super().__init__("end_to_end_pipeline_test")
        self.test_results = {
            'ingestion': {'passed': False, 'details': []},
            'processing': {'passed': False, 'details': []},
            'validation': {'passed': False, 'details': []},
            'overall': {'passed': False, 'summary': ''}
        }
    
    def _execute_job(self, **kwargs) -> Dict[str, Any]:
        """Execute the end-to-end pipeline test"""
        try:
            self.logger.info("="*60)
            self.logger.info("STARTING END-TO-END PIPELINE VALIDATION")
            self.logger.info("="*60)
            
            # Step 1: Test Ingestion
            self.logger.info("\n🔄 STEP 1: Testing Raw News Ingestion...")
            ingestion_success = self._test_ingestion()
            
            if not ingestion_success:
                self.logger.error("❌ Ingestion test failed. Stopping pipeline test.")
                return self._compile_results()
            
            # Step 2: Test Processing
            self.logger.info("\n🔄 STEP 2: Testing News Processing...")
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
                self.logger.info("\n✅ END-TO-END PIPELINE VALIDATION SUCCESSFUL!")
                self.test_results['overall']['summary'] = "All pipeline stages working correctly"
            else:
                self.logger.error("\n❌ END-TO-END PIPELINE VALIDATION FAILED!")
                self.test_results['overall']['summary'] = "Pipeline issues detected"
            
            return self._compile_results()
            
        except Exception as e:
            self.logger.error(f"End-to-end test failed with exception: {e}")
            self.test_results['overall']['summary'] = f"Test failed with exception: {e}"
            return self._compile_results()
    
    def _test_ingestion(self) -> bool:
        """Test the ingestion pipeline"""
        try:
            self.logger.info("  🔍 Running Canada News ingestion...")
            
            # Configure ingestion job
            config = {
                'recent_only': True,
                'limit': 3,  # Test with small number
                'feeds': ['backgrounders']  # Focus on one feed type
            }
            
            ingestion_job = CanadaNewsIngestion("test_ingestion", config)
            result = ingestion_job.execute()
            
            # Check ingestion results
            if result.status.value == 'success':
                items_created = result.items_created
                self.logger.info(f"  ✅ Ingestion completed: {items_created} items created")
                
                # Validate field structure of newly created items
                if items_created > 0:
                    recent_items = self._get_recent_raw_items(limit=2)
                    field_validation = self._validate_raw_item_fields(recent_items)
                    
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
                    self.logger.info("  ⚠️  No new items created (may be expected if feeds are up to date)")
                    # Still consider this a success if no errors occurred
                    self.test_results['ingestion']['passed'] = True
                    self.test_results['ingestion']['details'] = ["No new items created (feeds up to date)"]
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
        """Test the processing pipeline"""
        try:
            self.logger.info("  🔍 Running news processing...")
            
            # Configure processing job
            config = {
                'use_llm_analysis': False,  # Disable LLM for faster testing
                'limit': 5,  # Process small batch
                'status_filter': 'pending_evidence_creation'
            }
            
            processing_job = CanadaNewsProcessor("test_processing", config)
            result = processing_job.execute()
            
            # Check processing results
            if result.status.value == 'success':
                items_processed = result.items_processed
                items_created = result.items_created
                self.logger.info(f"  ✅ Processing completed: {items_processed} processed, {items_created} evidence items created")
                
                # Validate evidence items structure
                if items_created > 0:
                    recent_evidence = self._get_recent_evidence_items(limit=2)
                    evidence_validation = self._validate_evidence_item_fields(recent_evidence)
                    
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
        """Validate the complete pipeline flow"""
        try:
            self.logger.info("  🔍 Validating pipeline data flow...")
            
            # Get sample of recent items from both collections
            raw_items = self._get_recent_raw_items(limit=3)
            evidence_items = self._get_recent_evidence_items(limit=3)
            
            validation_results = []
            
            # Check that raw items have correct field names
            if raw_items:
                self.logger.info(f"    📋 Checking {len(raw_items)} raw items...")
                for item in raw_items:
                    # Check for production field names
                    required_fields = ['title_raw', 'summary_or_snippet_raw', 'full_text_scraped', 
                                     'source_feed_name', 'rss_feed_url_used', 'categories_rss']
                    missing_fields = [field for field in required_fields if field not in item]
                    
                    if missing_fields:
                        validation_results.append(f"Raw item missing fields: {missing_fields}")
                    else:
                        validation_results.append("Raw item field structure correct")
            
            # Check evidence items structure
            if evidence_items:
                self.logger.info(f"    📋 Checking {len(evidence_items)} evidence items...")
                for item in evidence_items:
                    required_fields = ['title_or_summary', 'description_or_details', 'evidence_source_type', 
                                     'publication_date', 'source_url']
                    missing_fields = [field for field in required_fields if field not in item]
                    
                    if missing_fields:
                        validation_results.append(f"Evidence item missing fields: {missing_fields}")
                    else:
                        validation_results.append("Evidence item structure correct")
            
            # Check data flow consistency
            if raw_items and evidence_items:
                # Find evidence items that reference raw items
                raw_ids = {item.get('raw_item_id') for item in raw_items}
                evidence_refs = {item.get('additional_metadata', {}).get('raw_news_release_id') for item in evidence_items}
                
                if raw_ids.intersection(evidence_refs):
                    validation_results.append("Data flow linkage verified")
                else:
                    validation_results.append("No linkage found between raw and evidence items")
            
            # Determine overall validation result
            failed_validations = [result for result in validation_results if "missing" in result or "No linkage" in result]
            
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
    
    def _get_recent_raw_items(self, limit: int = 5) -> List[Dict[str, Any]]:
        """Get recent raw news items"""
        try:
            collection = self.db.collection('raw_news_releases')
            docs = collection.order_by('ingested_at', direction='DESCENDING').limit(limit).stream()
            return [doc.to_dict() for doc in docs]
        except Exception as e:
            self.logger.error(f"Error fetching recent raw items: {e}")
            return []
    
    def _get_recent_evidence_items(self, limit: int = 5) -> List[Dict[str, Any]]:
        """Get recent evidence items"""
        try:
            collection = self.db.collection('evidence_items')
            docs = collection.order_by('created_at', direction='DESCENDING').limit(limit).stream()
            return [doc.to_dict() for doc in docs]
        except Exception as e:
            self.logger.error(f"Error fetching recent evidence items: {e}")
            return []
    
    def _validate_raw_item_fields(self, items: List[Dict[str, Any]]) -> bool:
        """Validate that raw items have correct production field names"""
        if not items:
            return True
        
        required_production_fields = [
            'title_raw', 'summary_or_snippet_raw', 'full_text_scraped',
            'source_feed_name', 'rss_feed_url_used', 'categories_rss'
        ]
        
        old_fields = ['title', 'description', 'full_content', 'feed_name', 'feed_url', 'tags']
        
        for item in items:
            # Check that production fields exist
            missing_fields = [field for field in required_production_fields if field not in item]
            if missing_fields:
                self.logger.error(f"Raw item missing production fields: {missing_fields}")
                return False
            
            # Check that old fields don't exist (except if migrated)
            present_old_fields = [field for field in old_fields if field in item]
            if present_old_fields:
                self.logger.error(f"Raw item still has old field names: {present_old_fields}")
                return False
        
        return True
    
    def _validate_evidence_item_fields(self, items: List[Dict[str, Any]]) -> bool:
        """Validate evidence item structure"""
        if not items:
            return True
        
        required_fields = [
            'title_or_summary', 'description_or_details', 'evidence_source_type',
            'publication_date', 'source_url', 'created_at'
        ]
        
        for item in items:
            missing_fields = [field for field in required_fields if field not in item]
            if missing_fields:
                self.logger.error(f"Evidence item missing fields: {missing_fields}")
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
                'test_type': 'end_to_end_pipeline',
                'results': self.test_results,
                'summary': f"{passed_tests}/{total_tests} tests passed"
            }
        }


def main():
    """Run the end-to-end pipeline test"""
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    test = EndToEndPipelineTest()
    result = test.execute()
    
    print("\n" + "="*60)
    print("END-TO-END PIPELINE TEST RESULTS")
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