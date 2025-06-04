#!/usr/bin/env python3
"""
Fast Hybrid Evidence Linking Test

Optimized version using faster gemini-flash model and reduced test scope
for rapid iteration and validation of the hybrid approach.

Usage:
    python test_hybrid_evidence_linking_fast.py --parliament_session_id 44 --limit 2
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
import csv

# Load environment variables
load_dotenv()

# Add parent directories to path to import modules
sys.path.append(str(Path(__file__).parent.parent.parent))
sys.path.append(str(Path(__file__).parent.parent.parent / 'lib'))

# Logger setup
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(filename)s:%(lineno)d - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger("hybrid_fast_test")

# Import our components
try:
    from pipeline.stages.linking.semantic_evidence_linker import SemanticEvidenceLinker
    from pipeline.stages.linking.llm_evidence_validator import LLMEvidenceValidator, MatchEvaluation
    logger.info("Successfully imported hybrid linking components")
except ImportError as e:
    logger.error(f"Failed to import components: {e}")
    sys.exit(1)

class FastHybridTester:
    """Fast hybrid evidence linking tester with optimizations."""
    
    def __init__(self, parliament_session_id: int, use_test_collections: bool = True):
        self.parliament_session_id = parliament_session_id
        self.use_test_collections = use_test_collections
        
        # Initialize Firebase
        self._init_firebase()
        
        # Collection names
        if use_test_collections:
            self.promises_collection = "promises_test"
            self.evidence_collection = "evidence_items_test"
            logger.info("Using TEST collections for safe testing")
        else:
            self.promises_collection = "promises"
            self.evidence_collection = "evidence_items"
            logger.info("Using PRODUCTION collections")
    
    def _init_firebase(self) -> None:
        """Initialize Firebase connection using project credentials."""
        try:
            if not firebase_admin._apps:
                firebase_admin.initialize_app()
            
            self.db = firestore.client()
            logger.info(f"Connected to CLOUD Firestore (Project: {os.getenv('FIREBASE_PROJECT_ID')}) using default credentials.")
            
        except Exception as e:
            logger.error(f"Failed to connect to Firebase: {e}")
            sys.exit(1)
    
    def _init_components(self) -> None:
        """Initialize semantic linker and LLM validator."""
        logger.info("Initializing semantic evidence linker...")
        self.semantic_linker = SemanticEvidenceLinker(
            similarity_threshold=0.45,  # Lower threshold for more candidates
            max_links_per_evidence=20  # Limit candidates for LLM
        )
        # Initialize the semantic linker
        self.semantic_linker.initialize()
        
        logger.info("Initializing LLM evidence validator...")
        self.llm_validator = LLMEvidenceValidator()
        logger.info("All components initialized successfully")
    
    def _fetch_sample_evidence(self, limit: int) -> List[Dict[str, Any]]:
        """Fetch sample evidence items for testing."""
        logger.info(f"Fetching {limit} evidence items from {self.evidence_collection}")
        
        # For test collections, fetch items with pending status when possible
        if self.use_test_collections:
            # Try to get pending items first
            query = (self.db.collection(self.evidence_collection)
                    .where(filter=firestore.FieldFilter('promise_linking_status', '==', 'pending'))
                    .limit(limit))
            
            evidence_items = []
            for doc in query.stream():
                evidence_data = doc.to_dict()
                evidence_data['id'] = doc.id
                evidence_items.append(evidence_data)
            
            # If not enough pending items, get additional items
            if len(evidence_items) < limit:
                remaining_limit = limit - len(evidence_items)
                logger.info(f"Found {len(evidence_items)} pending items, fetching {remaining_limit} additional items")
                
                existing_ids = {item['id'] for item in evidence_items}
                query = self.db.collection(self.evidence_collection).limit(limit * 2)  # Get more to filter out existing
                
                for doc in query.stream():
                    if len(evidence_items) >= limit:
                        break
                    if doc.id not in existing_ids:
                        evidence_data = doc.to_dict()
                        evidence_data['id'] = doc.id
                        evidence_items.append(evidence_data)
        else:
            # Production - filter by session and pending status
            query = (self.db.collection(self.evidence_collection)
                    .where(filter=firestore.FieldFilter('parliament_session', '==', self.parliament_session_id))
                    .where(filter=firestore.FieldFilter('promise_linking_status', '==', 'pending'))
                    .limit(limit))
            
            evidence_items = []
            for doc in query.stream():
                evidence_data = doc.to_dict()
                evidence_data['id'] = doc.id
                evidence_items.append(evidence_data)
        
        logger.info(f"Fetched {len(evidence_items)} evidence items")
        return evidence_items
    
    async def run_fast_test(self, evidence_limit: int = 2, validation_threshold: float = 0.7, update_database: bool = False) -> Dict[str, Any]:
        """
        Run fast hybrid test with optimizations.
        
        Args:
            evidence_limit: Number of evidence items to test
            validation_threshold: Minimum confidence for final recommendations
            update_database: Whether to update the database with linked evidence items
            
        Returns:
            Test results with performance metrics and match quality
        """
        start_time = time.time()
        results = {
            'test_config': {
                'parliament_session': self.parliament_session_id,
                'evidence_limit': evidence_limit,
                'validation_threshold': validation_threshold,
                'collections': {
                    'promises': self.promises_collection,
                    'evidence': self.evidence_collection
                }
            },
            'performance_metrics': {},
            'evidence_results': [],
            'summary': {}
        }
        
        logger.info("=== Starting Fast Hybrid Evidence Linking Test ===")
        logger.info(f"Parliament Session: {self.parliament_session_id}")
        logger.info(f"Evidence Items to Test: {evidence_limit}")
        logger.info(f"Validation Threshold: {validation_threshold}")
        logger.info(f"Collections: {self.promises_collection}, {self.evidence_collection}")
        
        # Initialize components
        self._init_components()
        
        # Fetch sample evidence
        evidence_items = self._fetch_sample_evidence(evidence_limit)
        
        if not evidence_items:
            logger.error("No evidence items found")
            return results
        
        # Pre-load promises for semantic matching (one-time setup)
        logger.info("Pre-loading promises for semantic matching...")
        setup_start = time.time()
        
        # Fetch promises using the semantic linker's method
        promise_docs, promise_ids = await asyncio.to_thread(
            self.semantic_linker.fetch_promises,
            str(self.parliament_session_id),
            self.promises_collection
        )
        
        if not promise_docs:
            logger.error("No promises found for session")
            return results
        
        # Generate promise embeddings
        promise_texts = [self.semantic_linker.create_promise_text(promise) for promise in promise_docs]
        promise_embeddings = await asyncio.to_thread(
            self.semantic_linker.generate_embeddings,
            promise_texts
        )
        
        setup_time = time.time() - setup_start
        logger.info(f"Promise setup completed in {setup_time:.2f} seconds ({len(promise_docs)} promises)")
        
        # Process each evidence item
        total_semantic_matches = 0
        total_validated_matches = 0
        total_high_confidence = 0
        
        for i, evidence_item in enumerate(evidence_items, 1):
            logger.info(f"Processing evidence {i}/{len(evidence_items)}: {evidence_item['id']}")
            
            evidence_start = time.time()
            
            # OPTIMIZATION 1: Check bill linking bypass
            bill_bypass_promise_ids = self._check_bill_linking_bypass(evidence_item)
            if bill_bypass_promise_ids:
                logger.info(f"🚀 BILL BYPASS: Auto-linking to {len(bill_bypass_promise_ids)} promises without semantic/LLM validation")
                
                # Create high-confidence evaluations for bill bypass
                bill_bypass_matches = []
                for promise_id in bill_bypass_promise_ids:
                    # Find promise data for this ID
                    promise_data = next((p for p in promise_docs if p.get('promise_id') == promise_id), None)
                    if promise_data:
                        bypass_evaluation = MatchEvaluation(
                            confidence_score=0.95,  # Very high confidence for bill linking
                            reasoning="Same LEGISinfo source document already linked to this promise in other evidence items. Auto-linked for consistency using evidence_source_document_raw_id matching.",
                            category="Direct Implementation",
                            thematic_alignment=1.0,
                            department_overlap=True,
                            timeline_relevance="Contemporary",
                            implementation_type="Legislative Implementation",
                            semantic_quality_assessment="Bill linking bypass - high confidence based on source document ID",
                            progress_indicator="Legislative progress",
                            promise_id=promise_id,
                            semantic_similarity_score=1.0  # Perfect match through bill linking
                        )
                        bill_bypass_matches.append(bypass_evaluation)
                
                # Store results for bill bypass
                evidence_result = {
                    'evidence_id': evidence_item['id'],
                    'evidence_title': evidence_item.get('title_or_summary', 'No title'),
                    'semantic_matches_found': 0,  # Bypassed semantic matching
                    'validated_matches': len(bill_bypass_matches),
                    'high_confidence_matches': len(bill_bypass_matches),
                    'optimization_used': 'bill_linking_bypass',
                    'processing_time': {
                        'semantic_matching': 0,  # Bypassed
                        'llm_validation': 0,     # Bypassed
                        'total': time.time() - evidence_start
                    },
                    'top_matches': [
                        {
                            'promise_id': match.promise_id,
                            'promise_text': next(
                                (p.get('text', 'Promise text not found') for p in promise_docs 
                                 if p.get('promise_id') == match.promise_id), 'Promise text not found'
                            ),
                            'confidence_score': match.confidence_score,
                            'category': match.category,
                            'semantic_similarity': match.semantic_similarity_score,
                            'reasoning_preview': match.reasoning[:200] + "..." if len(match.reasoning) > 200 else match.reasoning,
                            'full_reasoning': match.reasoning,
                            'validation_method': 'bill_linking_bypass'
                        }
                        for match in bill_bypass_matches[:3]
                    ]
                }
                
                # Update database if requested
                if update_database:
                    promise_ids = [match.promise_id for match in bill_bypass_matches]
                    confidence_scores = [match.confidence_score for match in bill_bypass_matches]
                    self._update_evidence_with_promise_links(
                        evidence_item['id'],
                        promise_ids,
                        'bill_linking_bypass',
                        confidence_scores
                    )
                
                total_semantic_matches += 0  # Bypassed
                total_validated_matches += len(bill_bypass_matches)
                total_high_confidence += len(bill_bypass_matches)
                
                results['evidence_results'].append(evidence_result)
                continue
            
            # OPTIMIZATION 2: Semantic matching with high similarity bypass
            evidence_text = self.semantic_linker.create_evidence_text(evidence_item)
            evidence_embeddings = await asyncio.to_thread(
                self.semantic_linker.generate_embeddings,
                [evidence_text]
            )
            
            semantic_matches = await asyncio.to_thread(
                self.semantic_linker.find_semantic_matches,
                evidence_embeddings[0],
                promise_embeddings,
                promise_docs
            )
            
            semantic_time = time.time() - evidence_start
            logger.info(f"Found {len(semantic_matches)} semantic matches (threshold: 0.45)")
            
            if semantic_matches:
                # OPTIMIZATION 2: Separate high similarity matches from those needing LLM validation
                high_similarity_matches = []
                llm_validation_matches = []
                
                for match in semantic_matches:
                    if match['similarity_score'] >= 0.50:  # Back to production threshold
                        high_similarity_matches.append(match)
                    else:
                        llm_validation_matches.append(match)
                
                # Limit LLM validation to top candidates for performance
                max_llm_candidates = 5
                if len(llm_validation_matches) > max_llm_candidates:
                    llm_validation_matches = sorted(
                        llm_validation_matches, 
                        key=lambda x: x['similarity_score'], 
                        reverse=True
                    )[:max_llm_candidates]
                    logger.info(f"🔧 LIMITED: Reduced LLM validation to top {max_llm_candidates} candidates")
                
                logger.info(f"🚀 HIGH SIMILARITY BYPASS: {len(high_similarity_matches)} matches ≥0.50 will skip LLM validation")
                logger.info(f"🔍 LLM VALIDATION: {len(llm_validation_matches)} matches <0.50 need LLM validation")
                
                validation_start = time.time()
                validated_matches = []
                
                # Add high-confidence matches without LLM validation
                for match in high_similarity_matches:
                    high_conf_eval = self._create_high_confidence_evaluation(match)
                    validated_matches.append(high_conf_eval)
                
                # LLM validate the remaining matches
                if llm_validation_matches:
                    llm_validated = self.llm_validator.batch_validate_matches(
                        evidence_item,
                        llm_validation_matches,
                        validation_threshold=validation_threshold
                    )
                    validated_matches.extend(llm_validated)
                
                validation_time = time.time() - validation_start
                logger.info(f"LLM validated {len(validated_matches)} total matches")
                
                # Filter for high confidence recommendations
                high_confidence_matches = [
                    match for match in validated_matches 
                    if match.confidence_score >= validation_threshold
                ]
                
                logger.info(f"Final recommendations: {len(high_confidence_matches)} high-confidence matches")
                
                # Store results
                evidence_result = {
                    'evidence_id': evidence_item['id'],
                    'evidence_title': evidence_item.get('title_or_summary', 'No title'),
                    'semantic_matches_found': len(semantic_matches),
                    'validated_matches': len(validated_matches),
                    'high_confidence_matches': len(high_confidence_matches),
                    'optimization_used': f'high_similarity_bypass_{len(high_similarity_matches)}_of_{len(semantic_matches)}',
                    'processing_time': {
                        'semantic_matching': semantic_time,
                        'llm_validation': validation_time,
                        'total': semantic_time + validation_time
                    },
                    'top_matches': [
                        {
                            'promise_id': match.promise_id,
                            'promise_text': next(
                                (sm['promise_text'] for sm in semantic_matches 
                                 if sm['promise_id'] == match.promise_id), 'Promise text not found'
                            ),
                            'confidence_score': match.confidence_score,
                            'category': match.category,
                            'semantic_similarity': next(
                                (sm['similarity_score'] for sm in semantic_matches 
                                 if sm['promise_id'] == match.promise_id), 0.0
                            ),
                            'reasoning_preview': match.reasoning[:200] + "..." if len(match.reasoning) > 200 else match.reasoning,
                            'full_reasoning': match.reasoning,  # Store complete LLM reasoning
                            'thematic_alignment': match.thematic_alignment,
                            'department_overlap': match.department_overlap,
                            'timeline_relevance': match.timeline_relevance,
                            'implementation_type': match.implementation_type,
                            'semantic_quality_assessment': match.semantic_quality_assessment,
                            'progress_indicator': match.progress_indicator,
                            'validation_method': 'batch_llm_validation' if len(llm_validation_matches) > 0 else 'high_similarity_bypass'
                        }
                        for match in high_confidence_matches[:5]  # Top 5 with detailed info
                    ]
                }
                
                # Update database if requested
                if update_database and high_confidence_matches:
                    promise_ids = [match.promise_id for match in high_confidence_matches]
                    confidence_scores = [match.confidence_score for match in high_confidence_matches]
                    optimization_method = f'hybrid_validation_{len(high_similarity_matches)}_bypass_{len(llm_validation_matches)}_llm'
                    self._update_evidence_with_promise_links(
                        evidence_item['id'],
                        promise_ids,
                        optimization_method,
                        confidence_scores
                    )
                elif update_database:
                    # Update status even if no matches found
                    evidence_ref = self.db.collection(self.evidence_collection).document(evidence_item['id'])
                    evidence_ref.update({
                        'promise_linking_status': 'processed',
                        'promise_linking_processed_at': firestore.SERVER_TIMESTAMP,
                        'promise_links_found': 0,
                        'hybrid_linking_method': 'no_matches_found',
                        'hybrid_linking_timestamp': firestore.SERVER_TIMESTAMP
                    })
                    logger.info(f"✅ Updated evidence {evidence_item['id']}: No matches found, marked as processed")
                
                total_semantic_matches += len(semantic_matches)
                total_validated_matches += len(validated_matches)
                total_high_confidence += len(high_confidence_matches)
                
            else:
                evidence_result = {
                    'evidence_id': evidence_item['id'],
                    'evidence_title': evidence_item.get('title_or_summary', 'No title'),
                    'semantic_matches_found': 0,
                    'validated_matches': 0,
                    'high_confidence_matches': 0,
                    'optimization_used': 'none_needed',
                    'processing_time': {'semantic_matching': semantic_time, 'llm_validation': 0, 'total': semantic_time},
                    'top_matches': []
                }
            
            results['evidence_results'].append(evidence_result)
        
        # Calculate summary metrics
        total_time = time.time() - start_time
        
        results['performance_metrics'] = {
            'total_test_time': total_time,
            'setup_time': setup_time,
            'avg_processing_time_per_evidence': (total_time - setup_time) / len(evidence_items),
            'semantic_linker_stats': self.semantic_linker.stats,
            'llm_validator_stats': self.llm_validator.stats
        }
        
        results['summary'] = {
            'evidence_items_processed': len(evidence_items),
            'total_semantic_matches': total_semantic_matches,
            'total_validated_matches': total_validated_matches,
            'total_high_confidence_matches': total_high_confidence,
            'avg_semantic_matches_per_evidence': total_semantic_matches / len(evidence_items),
            'avg_validated_matches_per_evidence': total_validated_matches / len(evidence_items),
            'validation_success_rate': (total_validated_matches / total_semantic_matches) * 100 if total_semantic_matches > 0 else 0,
            'high_confidence_rate': (total_high_confidence / total_validated_matches) * 100 if total_validated_matches > 0 else 0
        }
        
        logger.info("=== Fast Hybrid Test Complete ===")
        logger.info(f"Total time: {total_time:.2f}s")
        logger.info(f"Semantic matches found: {total_semantic_matches}")
        logger.info(f"LLM validated matches: {total_validated_matches}")
        logger.info(f"High confidence recommendations: {total_high_confidence}")
        
        return results

    def _check_bill_linking_bypass(self, evidence_item: Dict[str, Any]) -> List[str]:
        """
        Check if this evidence item can bypass semantic/LLM validation through bill linking.
        
        If this is a LEGISinfo Bill Event with pending status and other evidence items 
        from the same source document are already linked to promises, automatically 
        link this evidence to those same promises.
        
        Returns:
            List of promise IDs to auto-link, empty list if no bypass possible
        """
        try:
            # Check if this is a LEGISinfo Bill Event
            evidence_source_type = evidence_item.get('evidence_source_type', '')
            if evidence_source_type != 'Bill Event (LEGISinfo)':
                return []
            
            # Check if this evidence item has pending promise linking status
            promise_linking_status = evidence_item.get('promise_linking_status', '')
            if promise_linking_status != 'pending':
                return []
            
            # Get the source document raw ID for matching
            source_document_raw_id = evidence_item.get('evidence_source_document_raw_id', '')
            if not source_document_raw_id:
                logger.debug("No evidence_source_document_raw_id found for bill linking bypass")
                return []
            
            logger.info(f"Checking bill linking bypass for LEGISinfo document: {source_document_raw_id}")
            
            # Query for other evidence items with the same source document ID that are already linked
            if self.use_test_collections:
                query = self.db.collection(self.evidence_collection)
            else:
                query = (self.db.collection(self.evidence_collection)
                        .where(filter=firestore.FieldFilter('parliament_session', '==', self.parliament_session_id)))
            
            linked_promise_ids = set()
            matching_evidence_count = 0
            
            for doc in query.stream():
                doc_data = doc.to_dict()
                doc_source_id = doc_data.get('evidence_source_document_raw_id', '')
                doc_evidence_id = doc_data.get('evidence_id', '')
                
                # Skip the current evidence item
                if doc_evidence_id == evidence_item.get('evidence_id', ''):
                    continue
                
                # Check if this document has the same source document raw ID
                if doc_source_id == source_document_raw_id:
                    matching_evidence_count += 1
                    
                    # Get promise IDs this evidence is linked to
                    promise_ids = doc_data.get('promise_ids', [])
                    if isinstance(promise_ids, list) and promise_ids:
                        linked_promise_ids.update(promise_ids)
                        logger.debug(f"Found {len(promise_ids)} promise links in evidence {doc_evidence_id}")
            
            if linked_promise_ids:
                logger.info(f"🔗 BILL LINKING BYPASS: Found {len(linked_promise_ids)} existing promise links for document {source_document_raw_id} across {matching_evidence_count} evidence items")
                return list(linked_promise_ids)
            
            logger.debug(f"No existing promise links found for document {source_document_raw_id} (found {matching_evidence_count} matching evidence items)")
            return []
            
        except Exception as e:
            logger.error(f"Error in bill linking bypass check: {e}")
            return []
    
    def _create_high_confidence_evaluation(self, semantic_match: Dict[str, Any]) -> MatchEvaluation:
        """
        Create a high-confidence MatchEvaluation for semantic scores >= 0.50 without LLM validation.
        
        Args:
            semantic_match: Semantic match dictionary with promise data and similarity score
            
        Returns:
            MatchEvaluation with high confidence
        """
        similarity_score = semantic_match.get('similarity_score', 0.0)
        promise_data = semantic_match.get('promise_full', {})
        
        # Determine category based on similarity score
        if similarity_score >= 0.65:
            category = "Direct Implementation"
            confidence = 0.9
        elif similarity_score >= 0.55:
            category = "Supporting Action"
            confidence = 0.8
        else:  # >= 0.50
            category = "Related Policy"
            confidence = 0.7
        
        return MatchEvaluation(
            confidence_score=confidence,
            reasoning=f"High semantic similarity ({similarity_score:.3f}) indicates strong relationship. Auto-validated without LLM to improve performance.",
            category=category,
            thematic_alignment=similarity_score,
            department_overlap=True,  # Assume true for high similarity
            timeline_relevance="Contemporary",
            implementation_type="Policy Implementation",
            semantic_quality_assessment="High quality semantic match",
            progress_indicator="Evidence of policy progress",
            promise_id=promise_data.get('promise_id', ''),
            semantic_similarity_score=similarity_score
        )

    def _update_evidence_with_promise_links(
        self,
        evidence_id: str,
        promise_ids: List[str],
        optimization_method: str,
        confidence_scores: List[float]
    ) -> bool:
        """
        Update evidence item in database with promise links.
        
        Args:
            evidence_id: Evidence item ID to update
            promise_ids: List of promise IDs to link
            optimization_method: Method used for linking (for tracking)
            confidence_scores: Confidence scores for each promise link
            
        Returns:
            True if successful, False otherwise
        """
        try:
            evidence_ref = self.db.collection(self.evidence_collection).document(evidence_id)
            evidence_doc = evidence_ref.get()
            
            if not evidence_doc.exists:
                logger.error(f"Evidence document {evidence_id} not found for update")
                return False
            
            evidence_data = evidence_doc.to_dict()
            
            # Get existing promise IDs to merge with new ones
            existing_promise_ids = evidence_data.get('promise_ids', [])
            if not isinstance(existing_promise_ids, list):
                existing_promise_ids = []
            
            # Merge promise IDs (avoid duplicates)
            all_promise_ids = list(set(existing_promise_ids + promise_ids))
            
            # Calculate average confidence for logging
            avg_confidence = sum(confidence_scores) / len(confidence_scores) if confidence_scores else 0.0
            
            # Update the evidence document
            update_data = {
                'promise_ids': all_promise_ids,
                'promise_linking_status': 'processed',
                'promise_linking_processed_at': firestore.SERVER_TIMESTAMP,
                'promise_links_found': len(promise_ids),
                'hybrid_linking_method': optimization_method,
                'hybrid_linking_avg_confidence': avg_confidence,
                'hybrid_linking_timestamp': firestore.SERVER_TIMESTAMP
            }
            
            evidence_ref.update(update_data)
            
            logger.info(f"✅ Updated evidence {evidence_id}: Added {len(promise_ids)} new links (method: {optimization_method}, avg confidence: {avg_confidence:.3f})")
            return True
            
        except Exception as e:
            logger.error(f"Failed to update evidence {evidence_id}: {e}")
            return False

def save_results(results: Dict[str, Any], parliament_session_id: int, evidence_limit: int) -> str:
    """Save test results to debug output."""
    timestamp = int(time.time())
    filename = f"fast_hybrid_test_session_{parliament_session_id}_limit_{evidence_limit}_{timestamp}.json"
    output_path = Path("debug_output") / filename
    
    # Ensure debug directory exists
    output_path.parent.mkdir(exist_ok=True)
    
    with open(output_path, 'w') as f:
        json.dump(results, f, indent=2, default=str)
    
    logger.info(f"Results saved to: {output_path}")
    return str(output_path)

def save_results_csv(results: Dict[str, Any], parliament_session_id: int, evidence_limit: int) -> str:
    """Save detailed test results to CSV format for inspection."""
    timestamp = int(time.time())
    filename = f"hybrid_test_detailed_session_{parliament_session_id}_limit_{evidence_limit}_{timestamp}.csv"
    output_path = Path("debug_output") / filename
    
    # Ensure debug directory exists
    output_path.parent.mkdir(exist_ok=True)
    
    # Prepare CSV data
    csv_rows = []
    
    for evidence_result in results.get('evidence_results', []):
        evidence_id = evidence_result.get('evidence_id', '')
        evidence_title = evidence_result.get('evidence_title', '')
        optimization_used = evidence_result.get('optimization_used', '')
        semantic_matches_count = evidence_result.get('semantic_matches_found', 0)
        
        processing_time = evidence_result.get('processing_time', {})
        total_time = processing_time.get('total', 0)
        semantic_time = processing_time.get('semantic_matching', 0)
        llm_time = processing_time.get('llm_validation', 0)
        
        # If there are matches, create a row for each match
        top_matches = evidence_result.get('top_matches', [])
        
        if top_matches:
            for i, match in enumerate(top_matches, 1):
                csv_rows.append({
                    'evidence_id': evidence_id,
                    'evidence_title': evidence_title[:100] + "..." if len(evidence_title) > 100 else evidence_title,
                    'match_rank': i,
                    'promise_id': match.get('promise_id', ''),
                    'promise_text': match.get('promise_text', 'Promise text not available')[:150] + "..." if len(match.get('promise_text', '')) > 150 else match.get('promise_text', 'Promise text not available'),
                    'confidence_score': match.get('confidence_score', 0),
                    'category': match.get('category', ''),
                    'semantic_similarity': match.get('semantic_similarity', 0),
                    'reasoning_preview': match.get('reasoning_preview', ''),
                    'full_reasoning': match.get('full_reasoning', ''),
                    'validation_method': match.get('validation_method', 'unknown'),
                    'optimization_used': optimization_used,
                    'semantic_matches_found': semantic_matches_count,
                    'total_processing_time': f"{total_time:.2f}s",
                    'semantic_processing_time': f"{semantic_time:.2f}s",
                    'llm_processing_time': f"{llm_time:.2f}s"
                })
        else:
            # No matches - create a single row
            csv_rows.append({
                'evidence_id': evidence_id,
                'evidence_title': evidence_title[:100] + "..." if len(evidence_title) > 100 else evidence_title,
                'match_rank': 0,
                'promise_id': 'NO_MATCHES',
                'promise_text': 'No matching promises found',
                'confidence_score': 0,
                'category': 'No Matches Found',
                'semantic_similarity': 0,
                'reasoning_preview': 'No semantic matches above threshold',
                'full_reasoning': 'No semantic matches found above the 0.45 threshold',
                'validation_method': 'none_needed',
                'optimization_used': optimization_used,
                'semantic_matches_found': semantic_matches_count,
                'total_processing_time': f"{total_time:.2f}s",
                'semantic_processing_time': f"{semantic_time:.2f}s",
                'llm_processing_time': f"{llm_time:.2f}s"
            })
    
    # Write CSV file
    fieldnames = [
        'evidence_id', 'evidence_title', 'match_rank', 'promise_id', 
        'promise_text', 'confidence_score', 'category', 'semantic_similarity', 'reasoning_preview', 'full_reasoning',
        'validation_method', 'optimization_used', 'semantic_matches_found', 'total_processing_time',
        'semantic_processing_time', 'llm_processing_time'
    ]
    
    with open(output_path, 'w', newline='', encoding='utf-8') as csvfile:
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(csv_rows)
    
    logger.info(f"Detailed CSV results saved to: {output_path}")
    return str(output_path)

async def main():
    """Main test execution."""
    parser = argparse.ArgumentParser(description="Fast Hybrid Evidence Linking Test")
    parser.add_argument("--parliament_session_id", type=int, default=44, help="Parliament session ID")
    parser.add_argument("--limit", type=int, default=2, help="Number of evidence items to test")
    parser.add_argument("--validation_threshold", type=float, default=0.7, help="LLM validation threshold")
    parser.add_argument("--use_production", action="store_true", help="Use production collections (default: test)")
    parser.add_argument("--update_database", action="store_true", help="Update database with linked evidence items")
    
    args = parser.parse_args()
    
    try:
        # Create tester
        tester = FastHybridTester(
            parliament_session_id=args.parliament_session_id,
            use_test_collections=not args.use_production
        )
        
        # Run test
        results = await tester.run_fast_test(
            evidence_limit=args.limit,
            validation_threshold=args.validation_threshold,
            update_database=args.update_database
        )
        
        # Save results
        output_file = save_results(results, args.parliament_session_id, args.limit)
        output_csv = save_results_csv(results, args.parliament_session_id, args.limit)
        
        # Print summary
        summary = results.get('summary', {})
        print("\n" + "="*50)
        print("🚀 FAST HYBRID TEST SUMMARY")
        print("="*50)
        print(f"Evidence Items: {summary.get('evidence_items_processed', 0)}")
        print(f"Semantic Matches: {summary.get('total_semantic_matches', 0)}")
        print(f"LLM Validated: {summary.get('total_validated_matches', 0)}")
        print(f"High Confidence: {summary.get('total_high_confidence_matches', 0)}")
        print(f"Validation Success Rate: {summary.get('validation_success_rate', 0):.1f}%")
        print(f"High Confidence Rate: {summary.get('high_confidence_rate', 0):.1f}%")
        print(f"Total Time: {results.get('performance_metrics', {}).get('total_test_time', 0):.2f}s")
        print(f"Results: {output_file}")
        print(f"Detailed CSV Results: {output_csv}")
        print("="*50)
        
    except KeyboardInterrupt:
        logger.info("Test interrupted by user")
    except Exception as e:
        logger.error(f"Test failed: {e}")
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(main()) 