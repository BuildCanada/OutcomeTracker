#!/usr/bin/env python3
"""
Test High-Quality Evidence Linking

This script tests the new higher quality evidence linking approach on a small
subset of Parliament 45 evidence items to validate the improvements before
running the full comprehensive re-linking.
"""

import logging
import sys
import time
from pathlib import Path
from datetime import datetime, timezone

# Load environment variables before importing other modules
try:
    from dotenv import load_dotenv
    env_path = Path(__file__).parent / '.env'
    load_dotenv(env_path)
    print(f"📋 Loaded environment from: {env_path}")
except ImportError:
    print("📋 python-dotenv not available, skipping .env file loading")
except Exception as e:
    print(f"📋 Could not load .env file: {e}")

# Add pipeline directory to path
pipeline_dir = Path(__file__).parent / "pipeline"
sys.path.insert(0, str(pipeline_dir))

from stages.linking.evidence_linker import EvidenceLinker

# Add core directory for database access
core_dir = Path(__file__).parent / "pipeline" / "core"
sys.path.insert(0, str(core_dir))

from base_job import BaseJob

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(name)s - %(message)s'
)

class HighQualityLinkingTestJob(BaseJob):
    """Test job for high-quality evidence linking"""
    
    def __init__(self):
        super().__init__(job_name="high_quality_linking_test")
        
    def _execute_job(self):
        """Execute the test"""
        try:
            self.logger.info("Starting high-quality linking test")
            
            # Step 1: Find a small subset of Parliament 45 evidence items for testing
            test_evidence_items = self._get_test_evidence_items()
            self.logger.info(f"Found {len(test_evidence_items)} evidence items for testing")
            
            if not test_evidence_items:
                return {
                    'status': 'error',
                    'error': 'No test evidence items found',
                    'timestamp': datetime.now(timezone.utc).isoformat()
                }
            
            # Step 2: Reset these specific items to pending status
            reset_count = self._reset_test_items_to_pending(test_evidence_items)
            
            # Step 3: Run high-quality linking on the test subset
            linking_results = self._run_test_linking(test_evidence_items)
            
            return {
                'status': 'success',
                'test_evidence_items': len(test_evidence_items),
                'items_reset': reset_count,
                'linking_results': linking_results,
                'timestamp': datetime.now(timezone.utc).isoformat()
            }
            
        except Exception as e:
            self.logger.error(f"Error during test: {e}")
            return {
                'status': 'error',
                'error': str(e),
                'timestamp': datetime.now(timezone.utc).isoformat()
            }
    
    def _get_test_evidence_items(self) -> list:
        """Get a small subset of Parliament 45 evidence items for testing"""
        try:
            from google.cloud import firestore
            
            # Get a mix of different source types for testing
            test_items = []
            
            # Test different source types
            source_types_to_test = [
                'Bill Event (LEGISinfo)',
                'News Article', 
                'Order in Council',
                'Canada Gazette'
            ]
            
            for source_type in source_types_to_test:
                query = (
                    self.db.collection('evidence_items')
                    .where(filter=firestore.FieldFilter('parliament_session_id', '==', '45'))
                    .where(filter=firestore.FieldFilter('evidence_source_type', '==', source_type))
                    .limit(2)  # Just 2 items per source type
                )
                
                for doc in query.stream():
                    item_data = doc.to_dict()
                    item_data['_doc_id'] = doc.id
                    test_items.append(item_data)
                    
                self.logger.info(f"Found {len([i for i in test_items if i.get('evidence_source_type') == source_type])} {source_type} items")
            
            return test_items
            
        except Exception as e:
            self.logger.error(f"Error getting test evidence items: {e}")
            return []
    
    def _reset_test_items_to_pending(self, test_items: list) -> int:
        """Reset test items to pending status"""
        reset_count = 0
        
        try:
            from google.cloud import firestore
            
            for item in test_items:
                doc_id = item.get('_doc_id')
                if doc_id:
                    # Reset to pending status
                    self.db.collection('evidence_items').document(doc_id).update({
                        'promise_linking_status': 'pending',
                        'promise_ids': [],  # Clear existing links
                        'promise_links_found': 0,
                        'test_reset_at': firestore.SERVER_TIMESTAMP,
                        'test_reset_reason': 'High-quality linking test'
                    })
                    reset_count += 1
                    
            self.logger.info(f"Reset {reset_count} test items to pending status")
            return reset_count
            
        except Exception as e:
            self.logger.error(f"Error resetting test items: {e}")
            return reset_count
    
    def _run_test_linking(self, test_items: list) -> dict:
        """Run the high-quality linking on test items"""
        try:
            # Configuration with higher standards
            config = {
                'batch_size': 5,
                'max_items_per_run': len(test_items),
                'semantic_threshold': 0.55,  # Higher base threshold
                'llm_validation_threshold': 0.7,  # Much higher LLM threshold
                'high_similarity_bypass_threshold': 0.65,  # Higher bypass threshold
                'max_llm_candidates': 3,  # Fewer candidates for quality
                'default_parliament_session': '45',
                
                # Source-specific thresholds for quality control
                'source_type_thresholds': {
                    'Bill Event (LEGISinfo)': {
                        'semantic_threshold': 0.50,
                        'llm_threshold': 0.6,
                        'bypass_threshold': 0.60
                    },
                    'News Article': {
                        'semantic_threshold': 0.60,
                        'llm_threshold': 0.75,
                        'bypass_threshold': 0.70
                    },
                    'Order in Council': {
                        'semantic_threshold': 0.58,
                        'llm_threshold': 0.72,
                        'bypass_threshold': 0.68
                    },
                    'Canada Gazette': {
                        'semantic_threshold': 0.58,
                        'llm_threshold': 0.72,
                        'bypass_threshold': 0.68
                    }
                }
            }
            
            # Create and run the evidence linker
            linker = EvidenceLinker("high_quality_linking_test", config)
            
            result = linker.execute(
                limit=len(test_items),
                parliament_session_id='45'
            )
            
            return {
                'status': result.status.value,
                'items_processed': result.items_processed,
                'items_updated': result.items_updated,
                'items_skipped': result.items_skipped,
                'errors': result.errors,
                'duration_seconds': result.duration_seconds,
                'metadata': result.metadata
            }
            
        except Exception as e:
            self.logger.error(f"Error running test linking: {e}")
            return {
                'status': 'error',
                'error': str(e)
            }

def analyze_test_results(test_items: list, job: HighQualityLinkingTestJob):
    """Analyze the results of the test linking"""
    print("\n🔍 ANALYZING TEST RESULTS")
    print("=" * 40)
    
    try:
        from google.cloud import firestore
        
        for item in test_items:
            doc_id = item.get('_doc_id')
            evidence_id = item.get('evidence_id', doc_id)
            source_type = item.get('evidence_source_type', 'Unknown')
            
            # Get updated item from database
            doc_ref = job.db.collection('evidence_items').document(doc_id)
            updated_item = doc_ref.get().to_dict()
            
            promise_ids = updated_item.get('promise_ids', [])
            linking_status = updated_item.get('promise_linking_status', 'unknown')
            links_found = updated_item.get('promise_links_found', 0)
            
            print(f"\n📄 {evidence_id}")
            print(f"   Source Type: {source_type}")
            print(f"   Status: {linking_status}")
            print(f"   Links Found: {links_found}")
            if promise_ids:
                print(f"   Promise IDs: {promise_ids[:3]}{'...' if len(promise_ids) > 3 else ''}")
            
    except Exception as e:
        print(f"Error analyzing results: {e}")

def main():
    """Main test function"""
    print("🧪 HIGH-QUALITY EVIDENCE LINKING TEST")
    print("=" * 50)
    print("This test will:")
    print("1. Select a small subset of Parliament 45 evidence items")
    print("2. Reset them to pending status")
    print("3. Run linking with new higher quality thresholds")
    print("4. Analyze the results to validate improvements")
    print()
    
    print("📊 NEW QUALITY STANDARDS:")
    print("   - Base Semantic: 0.55 (was 0.47)")
    print("   - Base LLM: 0.70 (was 0.50)")
    print("   - Base Bypass: 0.65 (was 0.50)")
    print("   - Source-specific thresholds for different evidence types")
    print()
    
    # Run the test
    job = HighQualityLinkingTestJob()
    result = job.execute()
    
    print("✅ TEST EXECUTION COMPLETED")
    print("=" * 30)
    print(f"📊 Status: {result.status.value}")
    print(f"⏰ Completed at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    if result.metadata:
        metadata = result.metadata
        print(f"📈 Test Results:")
        print(f"   - Test evidence items: {metadata.get('test_evidence_items', 0)}")
        print(f"   - Items reset: {metadata.get('items_reset', 0)}")
        
        linking_results = metadata.get('linking_results', {})
        if linking_results:
            print(f"   - Items processed: {linking_results.get('items_processed', 0)}")
            print(f"   - Items updated: {linking_results.get('items_updated', 0)}")
            print(f"   - Duration: {linking_results.get('duration_seconds', 0):.2f}s")
    
    # Get test items for analysis
    test_items = job._get_test_evidence_items()
    if test_items:
        analyze_test_results(test_items, job)
    
    if result.status.value == 'success':
        print("\n🎉 TEST SUCCESSFUL!")
        print("📋 Review the results above to validate quality improvements")
        print("📋 If satisfied, run the full comprehensive re-linking process")
    else:
        print(f"\n⚠️ Test completed with issues: {result.metadata.get('error', 'Unknown error')}")

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n🛑 Test interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ Test failed: {e}")
        logging.error("High-quality linking test failed", exc_info=True)
        sys.exit(1) 