#!/usr/bin/env python3
"""
Quick Test Script for Hybrid Evidence Linking

Tests the LLM validation component with a small sample of evidence items
to validate the hybrid approach before full implementation.

Usage:
    python test_hybrid_evidence_linking.py --parliament_session_id 44 --limit 5
"""

import firebase_admin
from firebase_admin import firestore, credentials
import os
import sys
import asyncio
import logging
import traceback
from dotenv import load_dotenv
import json
import argparse
from datetime import datetime, timezone
import time
from pathlib import Path
from typing import Dict, List, Any, Optional

# Add parent directories to path to import modules
sys.path.append(str(Path(__file__).parent.parent.parent))
sys.path.append(str(Path(__file__).parent.parent.parent / 'lib'))

# Load environment variables
load_dotenv()

# Logger setup
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(filename)s:%(lineno)d - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger("hybrid_test")

# Import our components
try:
    from pipeline.stages.linking.semantic_evidence_linker import SemanticEvidenceLinker
    from pipeline.stages.linking.llm_evidence_validator import LLMEvidenceValidator, MatchEvaluation
    logger.info("Successfully imported hybrid linking components")
except ImportError as e:
    logger.error(f"Failed to import components: {e}")
    sys.exit(1)

# Firebase Configuration
db = None
if not firebase_admin._apps:
    try:
        firebase_admin.initialize_app()
        project_id = os.getenv('FIREBASE_PROJECT_ID', '[Not Set - Using Default]')
        logger.info(f"Connected to CLOUD Firestore (Project: {project_id}) using default credentials.")
        db = firestore.client()
    except Exception as e_default:
        logger.warning(f"Cloud Firestore init with default creds failed: {e_default}. Attempting service account.")
        cred_path = os.getenv('FIREBASE_SERVICE_ACCOUNT_KEY_PATH')
        if cred_path:
            try:
                logger.info(f"Attempting Firebase init with service account key from env var: {cred_path}")
                cred = credentials.Certificate(cred_path)
                app_name = 'hybrid_test_app'
                try:
                    firebase_admin.initialize_app(cred, name=app_name)
                except ValueError:
                    app_name_unique = f"{app_name}_{str(time.time())}"
                    firebase_admin.initialize_app(cred, name=app_name_unique)
                    app_name = app_name_unique

                project_id_sa = os.getenv('FIREBASE_PROJECT_ID', '[Not Set - Using Service Account]')
                logger.info(f"Connected to CLOUD Firestore (Project: {project_id_sa}) via service account.")
                db = firestore.client(app=firebase_admin.get_app(name=app_name))
            except Exception as e_sa:
                logger.critical(f"Firebase init with service account key from {cred_path} failed: {e_sa}", exc_info=True)

if db is None:
    logger.critical("CRITICAL: Failed to obtain Firestore client. Exiting.")
    exit("Exiting: Firestore client not available.")

class HybridLinkingTester:
    """Test hybrid evidence linking approach with a small sample."""
    
    def __init__(self, use_test_collections: bool = True):
        """Initialize the tester."""
        self.use_test_collections = use_test_collections
        
        # Set collection names
        if use_test_collections:
            self.promises_collection = 'promises_test'
            self.evidence_items_collection = 'evidence_items_test'
            logger.info("Using TEST collections for safe testing")
        else:
            self.promises_collection = 'promises'
            self.evidence_items_collection = 'evidence_items'
            logger.warning("Using PRODUCTION collections")
        
        # Initialize components
        self.semantic_linker = None
        self.llm_validator = None
    
    def initialize_components(self):
        """Initialize semantic linker and LLM validator."""
        try:
            # Initialize semantic linker with lower threshold for more candidates
            logger.info("Initializing semantic evidence linker...")
            self.semantic_linker = SemanticEvidenceLinker(
                similarity_threshold=0.4,  # Lower threshold for LLM validation
                max_links_per_evidence=20  # More candidates for LLM to evaluate
            )
            self.semantic_linker.initialize()
            
            # Initialize LLM validator
            logger.info("Initializing LLM evidence validator...")
            self.llm_validator = LLMEvidenceValidator(
                validation_threshold=0.7  # Higher threshold for final results
            )
            self.llm_validator.initialize()
            
            logger.info("All components initialized successfully")
            
        except Exception as e:
            logger.error(f"Failed to initialize components: {e}")
            raise
    
    async def fetch_sample_evidence(self, parliament_session_id: str, limit: int) -> List[Dict[str, Any]]:
        """Fetch a small sample of evidence items for testing."""
        try:
            logger.info(f"Fetching {limit} evidence items from {self.evidence_items_collection}")
            
            query = db.collection(self.evidence_items_collection).where(
                filter=firestore.FieldFilter("parliament_session_id", "==", parliament_session_id)
            ).limit(limit)
            
            evidence_docs = await asyncio.to_thread(list, query.stream())
            
            evidence_items = []
            for doc in evidence_docs:
                data = doc.to_dict()
                if data:
                    data['_doc_id'] = doc.id
                    evidence_items.append(data)
            
            logger.info(f"Fetched {len(evidence_items)} evidence items")
            return evidence_items
            
        except Exception as e:
            logger.error(f"Error fetching evidence items: {e}", exc_info=True)
            return []
    
    async def run_hybrid_test(self, parliament_session_id: str, limit: int) -> Dict[str, Any]:
        """Run the hybrid linking test and return detailed results."""
        
        logger.info("=== Starting Hybrid Evidence Linking Test ===")
        logger.info(f"Parliament Session: {parliament_session_id}")
        logger.info(f"Evidence Items to Test: {limit}")
        logger.info(f"Collections: {self.promises_collection}, {self.evidence_items_collection}")
        
        start_time = time.time()
        
        try:
            # Initialize components
            self.initialize_components()
            
            # Fetch sample evidence items
            evidence_items = await self.fetch_sample_evidence(parliament_session_id, limit)
            if not evidence_items:
                raise Exception("No evidence items found")
            
            # Fetch promises and generate embeddings (using semantic linker)
            logger.info(f"Fetching promises for session {parliament_session_id}")
            promise_docs, promise_ids = self.semantic_linker.fetch_promises(
                parliament_session_id, self.promises_collection
            )
            
            if not promise_docs:
                raise Exception("No promises found")
            
            # Generate promise embeddings
            logger.info("Generating promise embeddings...")
            promise_texts = [self.semantic_linker.create_promise_text(promise) for promise in promise_docs]
            promise_embeddings = self.semantic_linker.generate_embeddings(promise_texts)
            
            # Process each evidence item through the hybrid pipeline
            test_results = []
            
            for i, evidence_item in enumerate(evidence_items, 1):
                evidence_id = evidence_item.get('evidence_id')
                logger.info(f"Processing evidence {i}/{len(evidence_items)}: {evidence_id}")
                
                # Initialize result tracking
                evidence_result = {
                    "evidence_id": evidence_id,
                    "evidence_title": evidence_item.get('title_or_summary', 'No title'),
                    "evidence_source_type": evidence_item.get('evidence_source_type', 'Unknown'),
                    "evidence_date": str(evidence_item.get('evidence_date', 'Unknown')),
                    "existing_promise_ids": evidence_item.get('promise_ids', []),
                    "semantic_matches": [],
                    "llm_validated_matches": [],
                    "final_recommendations": [],
                    "processing_success": False,
                    "error": None,
                    "performance": {}
                }
                
                try:
                    # Step 1: Semantic matching
                    semantic_start = time.time()
                    evidence_text = self.semantic_linker.create_evidence_text(evidence_item)
                    evidence_embedding = self.semantic_linker.generate_embeddings([evidence_text])
                    
                    if evidence_embedding.size == 0:
                        logger.warning(f"Failed to generate embedding for evidence {evidence_id}")
                        evidence_result["error"] = "Failed to generate embedding"
                        test_results.append(evidence_result)
                        continue
                    
                    semantic_matches = self.semantic_linker.find_semantic_matches(
                        evidence_embedding[0], promise_embeddings, promise_docs
                    )
                    
                    semantic_time = time.time() - semantic_start
                    evidence_result["semantic_matches"] = semantic_matches
                    evidence_result["performance"]["semantic_time"] = semantic_time
                    
                    logger.info(f"Found {len(semantic_matches)} semantic matches (threshold: 0.4)")
                    
                    if not semantic_matches:
                        logger.info(f"No semantic matches found for evidence {evidence_id}")
                        evidence_result["processing_success"] = True
                        test_results.append(evidence_result)
                        continue
                    
                    # Step 2: LLM validation
                    llm_start = time.time()
                    validated_matches = self.llm_validator.validate_semantic_matches(
                        evidence_item, semantic_matches
                    )
                    
                    llm_time = time.time() - llm_start
                    evidence_result["llm_validated_matches"] = [
                        {
                            "promise_id": match.promise_id,
                            "confidence_score": match.confidence_score,
                            "category": match.category,
                            "reasoning": match.reasoning,
                            "semantic_similarity_score": match.semantic_similarity_score,
                            "thematic_alignment": match.thematic_alignment,
                            "department_overlap": match.department_overlap,
                            "implementation_type": match.implementation_type
                        }
                        for match in validated_matches
                    ]
                    evidence_result["performance"]["llm_time"] = llm_time
                    
                    logger.info(f"LLM validated {len(validated_matches)} matches (threshold: 0.7)")
                    
                    # Step 3: Final recommendations (high confidence matches)
                    high_confidence_matches = [match for match in validated_matches if match.is_high_confidence]
                    evidence_result["final_recommendations"] = [
                        {
                            "promise_id": match.promise_id,
                            "confidence_score": match.confidence_score,
                            "category": match.category,
                            "reasoning": match.reasoning[:200] + "..." if len(match.reasoning) > 200 else match.reasoning
                        }
                        for match in high_confidence_matches
                    ]
                    
                    logger.info(f"Final recommendations: {len(high_confidence_matches)} high-confidence matches")
                    
                    evidence_result["processing_success"] = True
                    
                except Exception as e:
                    logger.error(f"Error processing evidence {evidence_id}: {e}")
                    evidence_result["error"] = str(e)
                
                test_results.append(evidence_result)
            
            total_time = time.time() - start_time
            
            # Compile final results
            result = {
                'success': True,
                'parliament_session_id': parliament_session_id,
                'evidence_processed': len(evidence_items),
                'promises_loaded': len(promise_docs),
                'total_processing_time': total_time,
                'test_results': test_results,
                'component_stats': {
                    'semantic_linker': self.semantic_linker.get_stats(),
                    'llm_validator': self.llm_validator.get_stats()
                },
                'summary': self._generate_summary(test_results)
            }
            
            return result
            
        except Exception as e:
            logger.error(f"Error in hybrid test: {e}", exc_info=True)
            return {
                'success': False,
                'error': str(e),
                'processing_time': time.time() - start_time
            }
    
    def _generate_summary(self, test_results: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Generate summary statistics from test results."""
        total_items = len(test_results)
        successful_items = len([r for r in test_results if r['processing_success']])
        
        total_existing_links = sum(len(r.get('existing_promise_ids', [])) for r in test_results)
        total_semantic_matches = sum(len(r.get('semantic_matches', [])) for r in test_results)
        total_llm_validated = sum(len(r.get('llm_validated_matches', [])) for r in test_results)
        total_final_recommendations = sum(len(r.get('final_recommendations', [])) for r in test_results)
        
        # Performance averages
        semantic_times = [r.get('performance', {}).get('semantic_time', 0) for r in test_results if r.get('performance')]
        llm_times = [r.get('performance', {}).get('llm_time', 0) for r in test_results if r.get('performance')]
        
        avg_semantic_time = sum(semantic_times) / len(semantic_times) if semantic_times else 0
        avg_llm_time = sum(llm_times) / len(llm_times) if llm_times else 0
        
        return {
            'evidence_items_tested': total_items,
            'successful_processing': successful_items,
            'success_rate': (successful_items / total_items) if total_items > 0 else 0,
            'total_existing_links': total_existing_links,
            'total_semantic_matches': total_semantic_matches,
            'total_llm_validated_matches': total_llm_validated,
            'total_final_recommendations': total_final_recommendations,
            'semantic_to_llm_filter_rate': (total_llm_validated / total_semantic_matches) if total_semantic_matches > 0 else 0,
            'llm_to_final_filter_rate': (total_final_recommendations / total_llm_validated) if total_llm_validated > 0 else 0,
            'average_semantic_time': avg_semantic_time,
            'average_llm_time': avg_llm_time,
            'pipeline_stages': {
                'semantic_candidates_found': total_semantic_matches,
                'llm_validated_matches': total_llm_validated,
                'high_confidence_recommendations': total_final_recommendations
            }
        }


async def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(description='Test Hybrid Evidence Linking Approach')
    parser.add_argument(
        '--parliament_session_id',
        type=str,
        required=True,
        help='Parliament session ID (e.g., "44")'
    )
    parser.add_argument(
        '--limit',
        type=int,
        default=5,
        help='Number of evidence items to test (default: 5)'
    )
    parser.add_argument(
        '--use_production',
        action='store_true',
        help='Use production collections instead of test collections'
    )
    parser.add_argument(
        '--log_level',
        choices=['DEBUG', 'INFO', 'WARNING', 'ERROR'],
        default='INFO',
        help='Set logging level'
    )
    
    args = parser.parse_args()
    
    # Set logging level
    logging.getLogger().setLevel(getattr(logging, args.log_level))
    
    # Initialize tester
    tester = HybridLinkingTester(
        use_test_collections=not args.use_production
    )
    
    try:
        # Run hybrid test
        result = await tester.run_hybrid_test(
            parliament_session_id=args.parliament_session_id,
            limit=args.limit
        )
        
        if result['success']:
            # Save detailed results to JSON
            timestamp = int(time.time())
            output_filename = f"hybrid_test_session_{args.parliament_session_id}_limit_{args.limit}_{timestamp}.json"
            output_filepath = Path("debug_output") / output_filename
            output_filepath.parent.mkdir(exist_ok=True)
            
            with open(output_filepath, 'w') as f:
                json.dump(result, f, indent=2, default=str)
            
            # Print summary
            summary = result['summary']
            print(f"\n✅ SUCCESS! Hybrid evidence linking test complete!")
            print(f"📊 Results saved to: {output_filepath}")
            print(f"\n📈 SUMMARY STATISTICS:")
            print(f"  Evidence items tested: {summary['evidence_items_tested']}")
            print(f"  Success rate: {summary['success_rate']:.1%}")
            print(f"  Existing links: {summary['total_existing_links']}")
            print(f"  Semantic candidates: {summary['total_semantic_matches']}")
            print(f"  LLM validated: {summary['total_llm_validated_matches']}")
            print(f"  Final recommendations: {summary['total_final_recommendations']}")
            print(f"\n⏱️ PERFORMANCE:")
            print(f"  Avg semantic time: {summary['average_semantic_time']:.2f}s")
            print(f"  Avg LLM time: {summary['average_llm_time']:.2f}s")
            print(f"  Total time: {result['total_processing_time']:.2f}s")
            print(f"\n🔧 FILTER EFFICIENCY:")
            print(f"  Semantic → LLM: {summary['semantic_to_llm_filter_rate']:.1%}")
            print(f"  LLM → Final: {summary['llm_to_final_filter_rate']:.1%}")
            
            # Component stats
            semantic_stats = result['component_stats']['semantic_linker']
            llm_stats = result['component_stats']['llm_validator']
            print(f"\n💰 COST ESTIMATES:")
            print(f"  LLM validations: {llm_stats['validations_performed']}")
            print(f"  Estimated cost: ${llm_stats['total_cost_estimate']:.3f}")
            
        else:
            print(f"\n❌ FAILED: {result.get('error', 'Unknown error')}")
        
    except Exception as e:
        logger.error(f"Test failed: {e}")
        print(f"\n❌ FAILED: {e}")


if __name__ == "__main__":
    asyncio.run(main()) 