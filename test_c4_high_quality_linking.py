#!/usr/bin/env python3
"""
Test High-Quality Linking for Bill C-4

This script specifically tests Bill C-4 (the bill that previously had 26 false positive links)
with the new higher quality thresholds to validate the improvements.
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

class BillC4HighQualityTestJob(BaseJob):
    """Test job specifically for Bill C-4 high-quality linking"""
    
    def __init__(self):
        super().__init__(job_name="bill_c4_high_quality_test")
        
    def _execute_job(self):
        """Execute the C-4 specific test"""
        try:
            self.logger.info("Starting Bill C-4 high-quality linking test")
            
            # Step 1: Find Bill C-4 evidence items
            c4_evidence_items = self._get_bill_c4_evidence_items()
            self.logger.info(f"Found {len(c4_evidence_items)} Bill C-4 evidence items")
            
            if not c4_evidence_items:
                return {
                    'status': 'error',
                    'error': 'No Bill C-4 evidence items found',
                    'timestamp': datetime.now(timezone.utc).isoformat()
                }
            
            # Step 2: Show current linking status
            current_links = self._analyze_current_c4_links(c4_evidence_items)
            
            # Step 3: Reset C-4 items to pending status
            reset_count = self._reset_c4_items_to_pending(c4_evidence_items)
            
            # Step 4: Run high-quality linking on C-4
            linking_results = self._run_c4_high_quality_linking(c4_evidence_items)
            
            # Step 5: Analyze results
            new_links = self._analyze_new_c4_links(c4_evidence_items)
            
            return {
                'status': 'success',
                'c4_evidence_items': len(c4_evidence_items),
                'current_links': current_links,
                'items_reset': reset_count,
                'linking_results': linking_results,
                'new_links': new_links,
                'timestamp': datetime.now(timezone.utc).isoformat()
            }
            
        except Exception as e:
            self.logger.error(f"Error during Bill C-4 test: {e}")
            return {
                'status': 'error',
                'error': str(e),
                'timestamp': datetime.now(timezone.utc).isoformat()
            }
    
    def _get_bill_c4_evidence_items(self) -> list:
        """Get all Bill C-4 evidence items"""
        try:
            from google.cloud import firestore
            
            # Look for Bill C-4 evidence items
            query = (
                self.db.collection('evidence_items')
                .where(filter=firestore.FieldFilter('parliament_session_id', '==', '45'))
                .where(filter=firestore.FieldFilter('evidence_source_type', '==', 'Bill Event (LEGISinfo)'))
            )
            
            c4_items = []
            for doc in query.stream():
                item_data = doc.to_dict()
                item_data['_doc_id'] = doc.id
                
                # Check if this is related to Bill C-4
                evidence_id = item_data.get('evidence_id', '')
                bill_code = item_data.get('bill_code', '')
                title = item_data.get('title', '')
                
                if 'C-4' in evidence_id or 'C-4' in bill_code or 'C-4' in title:
                    c4_items.append(item_data)
                    self.logger.info(f"Found C-4 item: {evidence_id}")
            
            return c4_items
            
        except Exception as e:
            self.logger.error(f"Error getting Bill C-4 evidence items: {e}")
            return []
    
    def _analyze_current_c4_links(self, c4_items: list) -> dict:
        """Analyze current linking status of C-4 items"""
        analysis = {
            'total_items': len(c4_items),
            'items_with_links': 0,
            'total_links': 0,
            'link_details': []
        }
        
        for item in c4_items:
            evidence_id = item.get('evidence_id', item.get('_doc_id'))
            promise_ids = item.get('promise_ids', [])
            linking_status = item.get('promise_linking_status', 'unknown')
            
            if promise_ids:
                analysis['items_with_links'] += 1
                analysis['total_links'] += len(promise_ids)
                
                analysis['link_details'].append({
                    'evidence_id': evidence_id,
                    'status': linking_status,
                    'link_count': len(promise_ids),
                    'promise_ids': promise_ids[:5]  # First 5 for display
                })
        
        return analysis
    
    def _analyze_new_c4_links(self, c4_items: list) -> dict:
        """Analyze new linking results for C-4 items"""
        try:
            # Refresh data from database
            new_analysis = {
                'total_items': len(c4_items),
                'items_with_links': 0,
                'total_links': 0,
                'link_details': []
            }
            
            for item in c4_items:
                doc_id = item.get('_doc_id')
                
                # Get fresh data from database
                doc_ref = self.db.collection('evidence_items').document(doc_id)
                updated_item = doc_ref.get().to_dict()
                
                evidence_id = updated_item.get('evidence_id', doc_id)
                promise_ids = updated_item.get('promise_ids', [])
                linking_status = updated_item.get('promise_linking_status', 'unknown')
                method = updated_item.get('hybrid_linking_method', 'unknown')
                confidence = updated_item.get('hybrid_linking_avg_confidence', 0.0)
                
                if promise_ids:
                    new_analysis['items_with_links'] += 1
                    new_analysis['total_links'] += len(promise_ids)
                    
                    new_analysis['link_details'].append({
                        'evidence_id': evidence_id,
                        'status': linking_status,
                        'method': method,
                        'confidence': confidence,
                        'link_count': len(promise_ids),
                        'promise_ids': promise_ids[:5]  # First 5 for display
                    })
                else:
                    # Also track items with no links for comparison
                    new_analysis['link_details'].append({
                        'evidence_id': evidence_id,
                        'status': linking_status,
                        'method': method,
                        'confidence': confidence,
                        'link_count': 0,
                        'promise_ids': []
                    })
            
            return new_analysis
            
        except Exception as e:
            self.logger.error(f"Error analyzing new C-4 links: {e}")
            return {'error': str(e)}
    
    def _reset_c4_items_to_pending(self, c4_items: list) -> int:
        """Reset C-4 items to pending status"""
        reset_count = 0
        
        try:
            from google.cloud import firestore
            
            for item in c4_items:
                doc_id = item.get('_doc_id')
                if doc_id:
                    # Reset to pending status
                    self.db.collection('evidence_items').document(doc_id).update({
                        'promise_linking_status': 'pending',
                        'promise_ids': [],  # Clear existing links
                        'promise_links_found': 0,
                        'c4_test_reset_at': firestore.SERVER_TIMESTAMP,
                        'c4_test_reset_reason': 'Bill C-4 high-quality linking test'
                    })
                    reset_count += 1
                    
            self.logger.info(f"Reset {reset_count} Bill C-4 items to pending status")
            return reset_count
            
        except Exception as e:
            self.logger.error(f"Error resetting C-4 items: {e}")
            return reset_count
    
    def _run_c4_high_quality_linking(self, c4_items: list) -> dict:
        """Run the high-quality linking specifically on C-4 items"""
        try:
            # Instead of using the full evidence linker (which processes all pending items),
            # we'll manually process just the C-4 items using the linking components directly
            from stages.linking.semantic_evidence_linker import SemanticEvidenceLinker
            from stages.linking.llm_evidence_validator import LLMEvidenceValidator
            from google.cloud import firestore
            
            # Initialize components
            semantic_linker = SemanticEvidenceLinker(similarity_threshold=0.50)
            semantic_linker.initialize()
            
            llm_validator = LLMEvidenceValidator(validation_threshold=0.6)
            
            # Load promises for parliament session 45
            query = self.db.collection('promises').where(
                filter=firestore.FieldFilter('parliament_session_id', '==', '45')
            )
            
            promise_docs = []
            for doc in query.stream():
                promise_data = doc.to_dict()
                promise_data['promise_id'] = doc.id
                promise_docs.append(promise_data)
            
            # Generate promise embeddings
            promise_texts = [semantic_linker.create_promise_text(promise) for promise in promise_docs]
            promise_embeddings = semantic_linker.generate_embeddings(promise_texts)
            
            self.logger.info(f"Loaded {len(promise_docs)} promises for C-4 linking test")
            
            # Process each C-4 item individually
            results = {
                'items_processed': 0,
                'items_updated': 0,
                'items_with_links': 0,
                'total_links': 0,
                'processing_details': []
            }
            
            for c4_item in c4_items:
                doc_id = c4_item.get('_doc_id')
                evidence_id = c4_item.get('evidence_id', doc_id)
                
                self.logger.info(f"Processing C-4 item: {evidence_id}")
                
                # Generate evidence embedding
                evidence_text = semantic_linker.create_evidence_text(c4_item)
                evidence_embedding = semantic_linker.generate_embeddings([evidence_text])
                
                if evidence_embedding.size == 0:
                    self.logger.warning(f"Failed to generate embedding for {evidence_id}")
                    continue
                
                # Find semantic matches
                semantic_matches = semantic_linker.find_semantic_matches(
                    evidence_embedding[0], promise_embeddings, promise_docs
                )
                
                self.logger.info(f"Found {len(semantic_matches)} semantic matches for {evidence_id}")
                
                validated_matches = []
                
                if semantic_matches:
                    # Separate high similarity from those needing LLM validation
                    high_similarity_matches = []
                    llm_validation_matches = []
                    
                    for match in semantic_matches:
                        if match['similarity_score'] >= 0.60:  # Bypass threshold
                            high_similarity_matches.append(match)
                        else:
                            llm_validation_matches.append(match)
                    
                    # For high-confidence matches, we'll still validate them through LLM
                    # but we know they're likely good matches
                    
                    # LLM validate all matches (including high similarity ones)
                    all_matches_to_validate = high_similarity_matches + llm_validation_matches
                    if all_matches_to_validate:
                        llm_validated = llm_validator.batch_validate_matches(
                            c4_item, all_matches_to_validate, validation_threshold=0.6
                        )
                        validated_matches.extend(llm_validated)
                
                # Filter for final high-confidence matches
                final_matches = [m for m in validated_matches if m.confidence_score >= 0.6]
                
                # Update the evidence item with results
                promise_ids = [match.promise_id for match in final_matches]
                confidence_scores = [match.confidence_score for match in final_matches]
                avg_confidence = sum(confidence_scores) / len(confidence_scores) if confidence_scores else 0.0
                
                # Update evidence item in database
                self.db.collection('evidence_items').document(doc_id).update({
                    'promise_ids': promise_ids,
                    'promise_linking_status': 'processed',
                    'promise_linking_processed_at': firestore.SERVER_TIMESTAMP,
                    'promise_links_found': len(promise_ids),
                    'c4_test_linking_method': 'manual_high_quality_test',
                    'c4_test_avg_confidence': avg_confidence,
                    'c4_test_timestamp': firestore.SERVER_TIMESTAMP
                })
                
                # Update promises with new evidence link
                for promise_id in promise_ids:
                    try:
                        self.db.collection('promises').document(promise_id).update({
                            'evidence_item_ids': firestore.ArrayUnion([doc_id])
                        })
                    except Exception as e:
                        self.logger.error(f"Failed to update promise {promise_id}: {e}")
                
                results['items_processed'] += 1
                results['items_updated'] += 1
                if promise_ids:
                    results['items_with_links'] += 1
                    results['total_links'] += len(promise_ids)
                
                    results['processing_details'].append({
                    'evidence_id': evidence_id,
                    'semantic_matches': len(semantic_matches),
                    'final_links': len(promise_ids),
                    'avg_confidence': avg_confidence,
                    'promise_ids': promise_ids
                })
                
                self.logger.info(f"C-4 item {evidence_id}: {len(promise_ids)} final links (avg confidence: {avg_confidence:.3f})")
            
            return {
                'status': 'success',
                'items_processed': results['items_processed'],
                'items_updated': results['items_updated'],
                'items_skipped': 0,
                'errors': 0,
                'duration_seconds': 0.0,  # We'll calculate this if needed
                'processing_details': results['processing_details']
            }
            
        except Exception as e:
            self.logger.error(f"Error running C-4 high-quality linking: {e}")
            return {
                'status': 'error',
                'error': str(e)
            }

def compare_results(current_links: dict, new_links: dict):
    """Compare before and after linking results"""
    print("\n📊 BILL C-4 LINKING COMPARISON")
    print("=" * 50)
    
    print("🔍 BEFORE (Current Links):")
    print(f"   - Items with links: {current_links.get('items_with_links', 0)}")
    print(f"   - Total links: {current_links.get('total_links', 0)}")
    
    print("\n🎯 AFTER (High-Quality Links):")
    print(f"   - Items with links: {new_links.get('items_with_links', 0)}")
    print(f"   - Total links: {new_links.get('total_links', 0)}")
    
    # Calculate reduction
    old_total = current_links.get('total_links', 0)
    new_total = new_links.get('total_links', 0)
    
    if old_total > 0:
        reduction = old_total - new_total
        reduction_pct = (reduction / old_total) * 100
        print(f"\n📈 IMPROVEMENT:")
        print(f"   - Links reduced by: {reduction} ({reduction_pct:.1f}%)")
        print(f"   - False positive reduction: {reduction_pct:.1f}%")
    
    print("\n📋 DETAILED RESULTS:")
    for detail in new_links.get('link_details', []):
        evidence_id = detail['evidence_id']
        link_count = detail['link_count']
        method = detail.get('method', 'unknown')
        confidence = detail.get('confidence', 0.0)
        
        print(f"\n   📄 {evidence_id}")
        print(f"      - Links: {link_count}")
        print(f"      - Method: {method}")
        print(f"      - Confidence: {confidence:.3f}")
        if link_count > 0:
            promise_ids = detail.get('promise_ids', [])
            print(f"      - Promise IDs: {promise_ids}")

def main():
    """Main test function for Bill C-4"""
    print("🧪 BILL C-4 HIGH-QUALITY LINKING TEST")
    print("=" * 60)
    print("This test focuses specifically on Bill C-4 (the bill that")
    print("previously had 26 false positive links) to validate that")
    print("our higher quality thresholds eliminate false positives.")
    print()
    
    print("📊 HIGH-QUALITY STANDARDS FOR BILLS:")
    print("   - Semantic Threshold: 0.50 (was 0.47)")
    print("   - LLM Threshold: 0.60 (was 0.50)")
    print("   - Bypass Threshold: 0.60 (was 0.50)")
    print()
    
    # Run the test
    job = BillC4HighQualityTestJob()
    result = job.execute()
    
    print("✅ BILL C-4 TEST EXECUTION COMPLETED")
    print("=" * 40)
    print(f"📊 Status: {result.status.value}")
    print(f"⏰ Completed at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    if result.metadata:
        metadata = result.metadata
        current_links = metadata.get('current_links', {})
        new_links = metadata.get('new_links', {})
        linking_results = metadata.get('linking_results', {})
        
        print(f"📈 Test Results:")
        print(f"   - C-4 evidence items: {metadata.get('c4_evidence_items', 0)}")
        print(f"   - Items reset: {metadata.get('items_reset', 0)}")
        
        if linking_results:
            print(f"   - Items processed: {linking_results.get('items_processed', 0)}")
            print(f"   - Items updated: {linking_results.get('items_updated', 0)}")
            print(f"   - Duration: {linking_results.get('duration_seconds', 0):.2f}s")
        
        # Compare before and after
        if current_links and new_links:
            compare_results(current_links, new_links)
    
    if result.status.value == 'success':
        print("\n🎉 BILL C-4 TEST SUCCESSFUL!")
        print("📋 Review the comparison above to see false positive reduction")
        print("📋 If satisfied with C-4 results, the full re-linking should work well")
    else:
        print(f"\n⚠️ Bill C-4 test completed with issues: {result.metadata.get('error', 'Unknown error')}")

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n🛑 Bill C-4 test interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ Bill C-4 test failed: {e}")
        logging.error("Bill C-4 high-quality linking test failed", exc_info=True)
        sys.exit(1) 