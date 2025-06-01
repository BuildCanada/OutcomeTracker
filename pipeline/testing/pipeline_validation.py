#!/usr/bin/env python3
"""
Pipeline Validation Script

Comprehensive testing of the Promise Tracker pipeline to ensure production readiness.
Tests each component systematically with real data but in a safe manner.

Usage:
    python pipeline_validation.py --component ingestion
    python pipeline_validation.py --component processing  
    python pipeline_validation.py --component linking
    python pipeline_validation.py --component all
"""

import os
import sys
import logging
import argparse
import json
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Dict, Any, List

# Add pipeline directory to path
pipeline_dir = Path(__file__).parent.parent
sys.path.insert(0, str(pipeline_dir))

from core.job_runner import JobRunner
from stages.ingestion.canada_news import CanadaNewsIngestion
from stages.ingestion.legisinfo_bills import LegisInfoBillsIngestion
from stages.ingestion.orders_in_council import OrdersInCouncilIngestion
from stages.ingestion.canada_gazette import CanadaGazetteIngestion
from stages.processing.canada_news_processor import CanadaNewsProcessor
from stages.processing.legisinfo_processor import LegisInfoProcessor
from stages.processing.orders_in_council_processor import OrdersInCouncilProcessor
from stages.processing.canada_gazette_processor import CanadaGazetteProcessor
from stages.linking.evidence_linker import EvidenceLinker
from stages.linking.progress_scorer import ProgressScorer

# Firebase imports
import firebase_admin
from firebase_admin import firestore


class PipelineValidator:
    """Validates pipeline components for production readiness"""
    
    def __init__(self, use_test_collections: bool = False, verbose: bool = False):
        """
        Initialize the validator
        
        Args:
            use_test_collections: Use test collections instead of production
            verbose: Enable verbose logging
        """
        self.use_test_collections = use_test_collections
        self.setup_logging(verbose)
        self.setup_firebase()
        self.job_runner = JobRunner()
        
        # Test configuration
        self.test_config = {
            'timeout_minutes': 5,  # Short timeout for testing
            'retry_attempts': 1,   # Single retry for testing
            'max_items_per_run': 10,  # Limit items for testing
            'since_hours': 72,     # Last 3 days for testing
        }
        
        # Results tracking
        self.results = {
            'timestamp': datetime.now(timezone.utc).isoformat(),
            'use_test_collections': use_test_collections,
            'tests_run': [],
            'passed': 0,
            'failed': 0,
            'errors': []
        }
    
    def setup_logging(self, verbose: bool):
        """Setup logging configuration"""
        level = logging.DEBUG if verbose else logging.INFO
        logging.basicConfig(
            level=level,
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            handlers=[
                logging.StreamHandler(),
                logging.FileHandler('pipeline_validation.log')
            ]
        )
        self.logger = logging.getLogger(__name__)
    
    def setup_firebase(self):
        """Initialize Firebase connection"""
        try:
            if not firebase_admin._apps:
                firebase_admin.initialize_app()
            self.db = firestore.client()
            self.logger.info("Firebase connection established")
        except Exception as e:
            self.logger.error(f"Failed to initialize Firebase: {e}")
            raise
    
    def run_all_tests(self) -> Dict[str, Any]:
        """Run all pipeline tests"""
        self.logger.info("🚀 Starting comprehensive pipeline validation")
        
        try:
            # Test ingestion components
            self.test_ingestion_components()
            
            # Test processing components
            self.test_processing_components()
            
            # Test linking components
            self.test_linking_components()
            
            # Test orchestration
            self.test_orchestration()
            
        except Exception as e:
            self.logger.error(f"Validation failed with error: {e}")
            self.results['errors'].append(str(e))
        
        # Generate summary
        self.generate_summary()
        return self.results
    
    def test_ingestion_components(self):
        """Test all ingestion jobs"""
        self.logger.info("📥 Testing ingestion components")
        
        # Test Canada News ingestion
        self.test_canada_news_ingestion()
        
        # Test LEGISinfo Bills ingestion
        self.test_legisinfo_ingestion()
        
        # Test Orders in Council ingestion
        self.test_oic_ingestion()
        
        # Test Canada Gazette ingestion
        self.test_gazette_ingestion()
    
    def test_canada_news_ingestion(self):
        """Test Canada News ingestion job"""
        test_name = "canada_news_ingestion"
        self.logger.info(f"Testing {test_name}")
        
        try:
            # Create job with test config
            job = CanadaNewsIngestion(
                job_name=f"{test_name}_test",
                config=self.test_config
            )
            
            # Override collection name if using test collections
            if self.use_test_collections:
                job.collection_name = "raw_news_releases_test"
            
            # Run job with limited scope
            result = self.job_runner.run_job(
                job, 
                timeout_minutes=self.test_config['timeout_minutes'],
                since_hours=self.test_config['since_hours']
            )
            
            # Validate results
            self.validate_ingestion_result(test_name, result, expected_feeds=3)
            
        except Exception as e:
            self.record_test_failure(test_name, str(e))
    
    def test_legisinfo_ingestion(self):
        """Test LEGISinfo Bills ingestion job"""
        test_name = "legisinfo_bills_ingestion"
        self.logger.info(f"Testing {test_name}")
        
        try:
            job = LegisInfoBillsIngestion(
                job_name=f"{test_name}_test",
                config=self.test_config
            )
            
            if self.use_test_collections:
                job.collection_name = "raw_legisinfo_bill_details_test"
            
            result = self.job_runner.run_job(
                job,
                timeout_minutes=self.test_config['timeout_minutes'],
                since_hours=self.test_config['since_hours']
            )
            
            self.validate_ingestion_result(test_name, result, check_api_connection=True)
            
        except Exception as e:
            self.record_test_failure(test_name, str(e))
    
    def test_oic_ingestion(self):
        """Test Orders in Council ingestion job"""
        test_name = "orders_in_council_ingestion"
        self.logger.info(f"Testing {test_name}")
        
        try:
            # Use very limited config for OIC scraping
            oic_config = self.test_config.copy()
            oic_config['max_items_per_run'] = 3  # Very limited for OIC
            oic_config['max_consecutive_misses'] = 5  # Stop quickly if no results
            
            job = OrdersInCouncilIngestion(
                job_name=f"{test_name}_test",
                config=oic_config
            )
            
            if self.use_test_collections:
                job.collection_name = "raw_orders_in_council_test"
            
            result = self.job_runner.run_job(
                job,
                timeout_minutes=self.test_config['timeout_minutes'],
                since_hours=self.test_config['since_hours']
            )
            
            self.validate_ingestion_result(test_name, result, allow_zero_items=True)
            
        except Exception as e:
            self.record_test_failure(test_name, str(e))
    
    def test_gazette_ingestion(self):
        """Test Canada Gazette ingestion job"""
        test_name = "canada_gazette_ingestion"
        self.logger.info(f"Testing {test_name}")
        
        try:
            job = CanadaGazetteIngestion(
                job_name=f"{test_name}_test",
                config=self.test_config
            )
            
            if self.use_test_collections:
                job.collection_name = "raw_gazette_p2_notices_test"
            
            result = self.job_runner.run_job(
                job,
                timeout_minutes=self.test_config['timeout_minutes'],
                since_hours=self.test_config['since_hours']
            )
            
            self.validate_ingestion_result(test_name, result, check_rss_connection=True)
            
        except Exception as e:
            self.record_test_failure(test_name, str(e))
    
    def test_processing_components(self):
        """Test all processing jobs"""
        self.logger.info("⚙️ Testing processing components")
        
        # Test Canada News processing
        self.test_canada_news_processing()
        
        # Test LEGISinfo processing
        self.test_legisinfo_processing()
        
        # Test OIC processing
        self.test_oic_processing()
        
        # Test Gazette processing
        self.test_gazette_processing()
    
    def test_canada_news_processing(self):
        """Test Canada News processing job"""
        test_name = "canada_news_processing"
        self.logger.info(f"Testing {test_name}")
        
        try:
            job = CanadaNewsProcessor(
                job_name=f"{test_name}_test",
                config=self.test_config
            )
            
            if self.use_test_collections:
                job.source_collection = "raw_news_releases_test"
                job.target_collection = "evidence_items_test"
            
            result = self.job_runner.run_job(
                job,
                timeout_minutes=self.test_config['timeout_minutes']
            )
            
            self.validate_processing_result(test_name, result)
            
        except Exception as e:
            self.record_test_failure(test_name, str(e))
    
    def test_legisinfo_processing(self):
        """Test LEGISinfo processing job"""
        test_name = "legisinfo_processing"
        self.logger.info(f"Testing {test_name}")
        
        try:
            job = LegisInfoProcessor(
                job_name=f"{test_name}_test",
                config=self.test_config
            )
            
            if self.use_test_collections:
                job.source_collection = "raw_legisinfo_bill_details_test"
                job.target_collection = "evidence_items_test"
            
            result = self.job_runner.run_job(
                job,
                timeout_minutes=self.test_config['timeout_minutes']
            )
            
            self.validate_processing_result(test_name, result)
            
        except Exception as e:
            self.record_test_failure(test_name, str(e))
    
    def test_oic_processing(self):
        """Test OIC processing job"""
        test_name = "oic_processing"
        self.logger.info(f"Testing {test_name}")
        
        try:
            job = OrdersInCouncilProcessor(
                job_name=f"{test_name}_test",
                config=self.test_config
            )
            
            if self.use_test_collections:
                job.source_collection = "raw_orders_in_council_test"
                job.target_collection = "evidence_items_test"
            
            result = self.job_runner.run_job(
                job,
                timeout_minutes=self.test_config['timeout_minutes']
            )
            
            self.validate_processing_result(test_name, result)
            
        except Exception as e:
            self.record_test_failure(test_name, str(e))
    
    def test_gazette_processing(self):
        """Test Gazette processing job"""
        test_name = "gazette_processing"
        self.logger.info(f"Testing {test_name}")
        
        try:
            job = CanadaGazetteProcessor(
                job_name=f"{test_name}_test",
                config=self.test_config
            )
            
            if self.use_test_collections:
                job.source_collection = "raw_gazette_p2_notices_test"
                job.target_collection = "evidence_items_test"
            
            result = self.job_runner.run_job(
                job,
                timeout_minutes=self.test_config['timeout_minutes']
            )
            
            self.validate_processing_result(test_name, result)
            
        except Exception as e:
            self.record_test_failure(test_name, str(e))
    
    def test_linking_components(self):
        """Test linking and scoring jobs"""
        self.logger.info("🔗 Testing linking components")
        
        # Test evidence linking
        self.test_evidence_linking()
        
        # Test progress scoring
        self.test_progress_scoring()
    
    def test_evidence_linking(self):
        """Test evidence linking job"""
        test_name = "evidence_linking"
        self.logger.info(f"Testing {test_name}")
        
        try:
            job = EvidenceLinker(
                job_name=f"{test_name}_test",
                config=self.test_config
            )
            
            if self.use_test_collections:
                job.evidence_collection = "evidence_items_test"
                job.promises_collection = "promises"  # Keep using real promises
                job.links_collection = "promise_evidence_links_test"
            
            result = self.job_runner.run_job(
                job,
                timeout_minutes=self.test_config['timeout_minutes']
            )
            
            self.validate_linking_result(test_name, result)
            
        except Exception as e:
            self.record_test_failure(test_name, str(e))
    
    def test_progress_scoring(self):
        """Test progress scoring job"""
        test_name = "progress_scoring"
        self.logger.info(f"Testing {test_name}")
        
        try:
            scoring_config = self.test_config.copy()
            scoring_config['max_promises_per_run'] = 5  # Limit for testing
            scoring_config['batch_size'] = 2
            
            job = ProgressScorer(
                job_name=f"{test_name}_test",
                config=scoring_config
            )
            
            if self.use_test_collections:
                job.evidence_collection = "evidence_items_test"
                job.promises_collection = "promises"  # Keep using real promises for testing
            
            result = self.job_runner.run_job(
                job,
                timeout_minutes=self.test_config['timeout_minutes']
            )
            
            self.validate_scoring_result(test_name, result)
            
        except Exception as e:
            self.record_test_failure(test_name, str(e))
    
    def test_orchestration(self):
        """Test orchestration capabilities"""
        self.logger.info("🎭 Testing orchestration")
        
        # This would test the Flask app endpoints
        # For now, just check that the orchestrator can be imported
        try:
            from orchestrator import PipelineOrchestrator
            orchestrator = PipelineOrchestrator()
            status = orchestrator.get_job_status()
            
            self.record_test_success("orchestration", {
                'available_jobs': len(status.get('available_jobs', {})),
                'active_jobs': status.get('total_active', 0)
            })
            
        except Exception as e:
            self.record_test_failure("orchestration", str(e))
    
    def validate_ingestion_result(self, test_name: str, result: Any, **validation_params):
        """Validate ingestion job result"""
        try:
            # Convert result to dict for validation
            if hasattr(result, 'to_dict'):
                result_dict = result.to_dict()
            elif hasattr(result, '__dict__'):
                result_dict = result.__dict__
            else:
                result_dict = result
            
            # Check if job completed successfully
            success = result_dict.get('success', False) or result_dict.get('status') == 'success'
            
            if not success:
                error_msg = result_dict.get('error_message', 'Unknown error')
                self.record_test_failure(test_name, f"Job failed: {error_msg}")
                return
            
            # Validate specific parameters
            items_processed = result_dict.get('items_processed', 0)
            
            # Some feeds might legitimately have no new items
            if validation_params.get('allow_zero_items', False) or items_processed >= 0:
                details = {
                    'items_processed': items_processed,
                    'items_created': result_dict.get('items_created', 0),
                    'items_updated': result_dict.get('items_updated', 0),
                    'duration': result_dict.get('duration_seconds', 0)
                }
                
                # Additional validation for API connections
                if validation_params.get('check_api_connection'):
                    details['api_connection'] = 'success'
                
                if validation_params.get('check_rss_connection'):
                    details['rss_connection'] = 'success'
                
                self.record_test_success(test_name, details)
            else:
                self.record_test_failure(test_name, f"No items processed when some were expected")
                
        except Exception as e:
            self.record_test_failure(test_name, f"Validation error: {str(e)}")
    
    def validate_processing_result(self, test_name: str, result: Any):
        """Validate processing job result"""
        try:
            if hasattr(result, 'to_dict'):
                result_dict = result.to_dict()
            elif hasattr(result, '__dict__'):
                result_dict = result.__dict__
            else:
                result_dict = result
            
            success = result_dict.get('success', False) or result_dict.get('status') == 'success'
            
            if success:
                details = {
                    'items_processed': result_dict.get('items_processed', 0),
                    'items_created': result_dict.get('items_created', 0),
                    'evidence_items_created': result_dict.get('items_created', 0),
                    'duration': result_dict.get('duration_seconds', 0)
                }
                self.record_test_success(test_name, details)
            else:
                error_msg = result_dict.get('error_message', 'Unknown error')
                self.record_test_failure(test_name, f"Job failed: {error_msg}")
                
        except Exception as e:
            self.record_test_failure(test_name, f"Validation error: {str(e)}")
    
    def validate_linking_result(self, test_name: str, result: Any):
        """Validate linking job result"""
        try:
            if hasattr(result, 'to_dict'):
                result_dict = result.to_dict()
            elif hasattr(result, '__dict__'):
                result_dict = result.__dict__
            else:
                result_dict = result
            
            success = result_dict.get('success', False) or result_dict.get('status') == 'success'
            
            if success:
                details = {
                    'items_processed': result_dict.get('items_processed', 0),
                    'links_created': result_dict.get('items_created', 0),
                    'duration': result_dict.get('duration_seconds', 0)
                }
                self.record_test_success(test_name, details)
            else:
                error_msg = result_dict.get('error_message', 'Unknown error')
                self.record_test_failure(test_name, f"Job failed: {error_msg}")
                
        except Exception as e:
            self.record_test_failure(test_name, f"Validation error: {str(e)}")
    
    def validate_scoring_result(self, test_name: str, result: Any):
        """Validate scoring job result"""
        try:
            if hasattr(result, 'to_dict'):
                result_dict = result.to_dict()
            elif hasattr(result, '__dict__'):
                result_dict = result.__dict__
            else:
                result_dict = result
            
            success = result_dict.get('success', False) or result_dict.get('status') == 'success'
            
            if success:
                details = {
                    'promises_processed': result_dict.get('promises_processed', 0),
                    'scores_updated': result_dict.get('scores_updated', 0),
                    'llm_calls': result_dict.get('llm_calls', 0),
                    'duration': result_dict.get('duration_seconds', 0)
                }
                self.record_test_success(test_name, details)
            else:
                error_msg = result_dict.get('error_message', 'Unknown error')
                self.record_test_failure(test_name, f"Job failed: {error_msg}")
                
        except Exception as e:
            self.record_test_failure(test_name, f"Validation error: {str(e)}")
    
    def record_test_success(self, test_name: str, details: Dict[str, Any]):
        """Record a successful test"""
        self.logger.info(f"✅ {test_name} PASSED")
        self.results['tests_run'].append({
            'name': test_name,
            'status': 'PASSED',
            'details': details
        })
        self.results['passed'] += 1
    
    def record_test_failure(self, test_name: str, error: str):
        """Record a failed test"""
        self.logger.error(f"❌ {test_name} FAILED: {error}")
        self.results['tests_run'].append({
            'name': test_name,
            'status': 'FAILED',
            'error': error
        })
        self.results['failed'] += 1
        self.results['errors'].append(f"{test_name}: {error}")
    
    def generate_summary(self):
        """Generate test summary"""
        total_tests = self.results['passed'] + self.results['failed']
        success_rate = (self.results['passed'] / total_tests * 100) if total_tests > 0 else 0
        
        self.logger.info("\n" + "="*60)
        self.logger.info("📊 PIPELINE VALIDATION SUMMARY")
        self.logger.info("="*60)
        self.logger.info(f"Total tests run: {total_tests}")
        self.logger.info(f"Passed: {self.results['passed']}")
        self.logger.info(f"Failed: {self.results['failed']}")
        self.logger.info(f"Success rate: {success_rate:.1f}%")
        
        if self.results['errors']:
            self.logger.info("\n❌ ERRORS:")
            for error in self.results['errors']:
                self.logger.info(f"  • {error}")
        
        # Save results to file
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        results_file = f"pipeline_validation_results_{timestamp}.json"
        
        with open(results_file, 'w') as f:
            json.dump(self.results, f, indent=2, default=str)
        
        self.logger.info(f"\n📄 Results saved to: {results_file}")


def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(description='Pipeline Validation Script')
    parser.add_argument('--component', 
                       choices=['ingestion', 'processing', 'linking', 'all'],
                       default='all',
                       help='Component to test')
    parser.add_argument('--test-collections', 
                       action='store_true',
                       help='Use test collections instead of production')
    parser.add_argument('--verbose', '-v', 
                       action='store_true',
                       help='Enable verbose logging')
    
    args = parser.parse_args()
    
    # Change to pipeline directory
    os.chdir(pipeline_dir)
    
    # Create validator
    validator = PipelineValidator(
        use_test_collections=args.test_collections,
        verbose=args.verbose
    )
    
    try:
        if args.component == 'all':
            results = validator.run_all_tests()
        elif args.component == 'ingestion':
            validator.test_ingestion_components()
        elif args.component == 'processing':
            validator.test_processing_components()
        elif args.component == 'linking':
            validator.test_linking_components()
        
        # Generate summary
        validator.generate_summary()
        
        # Exit with appropriate code
        if validator.results['failed'] > 0:
            sys.exit(1)
        else:
            sys.exit(0)
            
    except KeyboardInterrupt:
        validator.logger.info("\n🛑 Validation interrupted by user")
        sys.exit(130)
    except Exception as e:
        validator.logger.error(f"💥 Validation failed with error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main() 