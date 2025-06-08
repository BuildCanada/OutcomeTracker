"""
Hybrid Evidence Linker Job for Promise Tracker Pipeline

Production-ready evidence linking that combines semantic similarity with LLM validation
for high-precision promise-evidence relationships. Includes performance optimizations:
- Bill linking bypass for same-document evidence
- High similarity bypass for confident semantic matches  
- Batch LLM validation for efficiency
- Configurable thresholds and limits

This replaces the existing keyword-based evidence linking with a sophisticated
hybrid approach while maintaining the same BaseJob interface.
"""

import logging
import sys
import asyncio
import time
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional
from pathlib import Path
import numpy as np
import os

# Handle imports for both module execution and testing
try:
    from ...core.base_job import BaseJob
    from .semantic_evidence_linker import SemanticEvidenceLinker
    from .llm_evidence_validator import LLMEvidenceValidator, MatchEvaluation
except ImportError:
    # Add pipeline directory to path for testing
    pipeline_dir = Path(__file__).parent.parent.parent
    sys.path.insert(0, str(pipeline_dir))
    from core.base_job import BaseJob
    
    # Add the linking directory for semantic components
    sys.path.append(str(Path(__file__).parent))
    from semantic_evidence_linker import SemanticEvidenceLinker
    from llm_evidence_validator import LLMEvidenceValidator, MatchEvaluation

from google.cloud import firestore


class EvidenceLinker(BaseJob):
    """
    Production-ready hybrid evidence linking job.
    
    Combines semantic similarity analysis with LLM validation to create
    high-quality evidence-promise relationships. Includes performance 
    optimizations for production scale processing.
    """
    
    def __init__(self, job_name: str, config: Dict[str, Any] = None):
        """Initialize the Hybrid Evidence Linker job"""
        super().__init__(job_name, config)
        
        # Processing settings
        self.batch_size = self.config.get('batch_size', 10)
        self.max_items_per_run = self.config.get('max_items_per_run', 500)
        self.default_parliament_session = self.config.get('default_parliament_session', '45')
        
        # Hybrid approach configuration
        self.semantic_threshold = self.config.get('semantic_threshold', 0.45)
        self.high_similarity_bypass_threshold = self.config.get('high_similarity_bypass_threshold', 0.50)
        self.llm_validation_threshold = self.config.get('llm_validation_threshold', 0.5)
        self.max_llm_candidates = self.config.get('max_llm_candidates', 5)
        
        # Collections
        self.evidence_collection = self.config.get('evidence_collection', 'evidence_items')
        self.promises_collection = self.config.get('promises_collection', 'promises')
        
        # Initialize components (will be done in _execute_job)
        self.semantic_linker = None
        self.llm_validator = None
        
        # Cache for promises to avoid repeated queries
        self._promises_cache = None
        self._promise_embeddings_cache = None
    
    def _execute_job(self, **kwargs) -> Dict[str, Any]:
        """
        Execute the hybrid evidence linking job.
        
        Args:
            **kwargs: Additional job arguments including:
                limit: Max evidence items to process 
                validation_threshold: LLM confidence threshold
                
        Returns:
            Job execution statistics
        """
        self.logger.info("Starting hybrid evidence linking process")
        
        # Extract parameters
        limit = kwargs.get('limit', self.max_items_per_run)
        validation_threshold = kwargs.get('validation_threshold', self.llm_validation_threshold)
        parliament_session_id = kwargs.get('parliament_session_id', self.default_parliament_session)
        
        stats = {
            'items_processed': 0,
            'items_created': 0,
            'items_updated': 0,
            'items_skipped': 0,
            'errors': 0,
            'metadata': {
                'evidence_collection': self.evidence_collection,
                'promises_collection': self.promises_collection,
                'semantic_threshold': self.semantic_threshold,
                'validation_threshold': validation_threshold,
                'affected_promise_ids': set(),  # Track which promises need rescoring
                'optimizations': {
                    'bill_linking_bypasses': 0,
                    'high_similarity_bypasses': 0,
                    'batch_llm_validations': 0
                }
            }
        }
        
        try:
            # Initialize components
            self._init_components()
            
            # Load and cache promises for the specified parliament session
            self._load_promises_cache(parliament_session_id)
            
            if not self._promises_cache:
                self.logger.warning("No promises found")
                return stats
            
            # Get evidence items to process (pending items for specified parliament session)
            evidence_items = self._get_pending_evidence_items(limit, parliament_session_id)
            
            if not evidence_items:
                self.logger.info("No evidence items found for linking")
                return stats
            
            self.logger.info(f"Processing {len(evidence_items)} evidence items against {len(self._promises_cache)} promises")
            
            # Process evidence items in batches
            for i in range(0, len(evidence_items), self.batch_size):
                batch = evidence_items[i:i + self.batch_size]
                batch_stats = self._process_evidence_batch(batch, validation_threshold)
                
                # Update overall stats
                for key in ['items_processed', 'items_created', 'items_updated', 'items_skipped', 'errors']:
                    stats[key] += batch_stats.get(key, 0)
                
                # Update optimization stats
                for opt_key in ['bill_linking_bypasses', 'high_similarity_bypasses', 'batch_llm_validations']:
                    stats['metadata']['optimizations'][opt_key] += batch_stats.get('optimizations', {}).get(opt_key, 0)
                
                # Update affected promise IDs
                stats['metadata']['affected_promise_ids'].update(batch_stats.get('affected_promise_ids', set()))
                
                self.logger.info(f"Processed batch {i//self.batch_size + 1}: "
                               f"{batch_stats['items_updated']} evidence items updated, "
                               f"{batch_stats['items_skipped']} skipped, "
                               f"{batch_stats['errors']} errors")
            
            # Add component stats
            if self.semantic_linker:
                stats['metadata']['semantic_stats'] = self.semantic_linker.get_stats()
            if self.llm_validator:
                stats['metadata']['llm_stats'] = self.llm_validator.get_stats()
            
            self.logger.info(f"Hybrid evidence linking completed: {stats['items_updated']} evidence items updated, "
                           f"{stats['items_skipped']} skipped, {stats['errors']} errors")
            
        except Exception as e:
            self.logger.error(f"Fatal error in hybrid evidence linking: {e}", exc_info=True)
            stats['errors'] += 1
            raise
        
        return stats
    
    def _init_components(self):
        """Initialize semantic linker and LLM validator components."""
        try:
            self.logger.info("Initializing hybrid evidence linking components")
            
            # Check for required environment variables first
            gemini_api_key = os.getenv('GEMINI_API_KEY') or os.getenv('GOOGLE_API_KEY')
            if not gemini_api_key:
                raise EnvironmentError(
                    "Missing required environment variable: GEMINI_API_KEY or GOOGLE_API_KEY. "
                    "Please ensure the API key is properly configured in the Cloud Run environment."
                )
            
            # Initialize semantic evidence linker
            self.semantic_linker = SemanticEvidenceLinker(
                similarity_threshold=self.semantic_threshold,
                max_links_per_evidence=50  # Higher limit for pre-filtering
            )
            self.semantic_linker.initialize()
            
            # Initialize LLM evidence validator  
            self.llm_validator = LLMEvidenceValidator(
                validation_threshold=self.llm_validation_threshold
            )
            
            self.logger.info("Hybrid components initialized successfully")
            
        except EnvironmentError as e:
            self.logger.error(f"Environment configuration error: {e}")
            raise
        except Exception as e:
            self.logger.error(f"Failed to initialize hybrid components: {e}")
            raise
    
    def _load_promises_cache(self, parliament_session_id: str):
        """Load promises for a specific parliament session and their embeddings into memory for efficient processing."""
        try:
            self.logger.info(f"Loading promises for parliament session {parliament_session_id}")
            
            # Fetch promises from the promises collection for the specified parliament session
            query = self.db.collection(self.promises_collection).where(
                filter=firestore.FieldFilter('parliament_session_id', '==', parliament_session_id)
            )
            
            promise_docs = []
            for doc in query.stream():
                promise_data = doc.to_dict()
                promise_data['promise_id'] = doc.id
                promise_docs.append(promise_data)
            
            if promise_docs:
                # Generate embeddings for all promises
                promise_texts = [self.semantic_linker.create_promise_text(promise) for promise in promise_docs]
                promise_embeddings = self.semantic_linker.generate_embeddings(promise_texts)
                
                self._promises_cache = promise_docs
                self._promise_embeddings_cache = promise_embeddings
                
                self.logger.info(f"Cached {len(promise_docs)} promises with embeddings for parliament session {parliament_session_id}")
            else:
                self._promises_cache = []
                self._promise_embeddings_cache = None
                self.logger.warning(f"No promises found for parliament session {parliament_session_id}")
                
        except Exception as e:
            self.logger.error(f"Error loading promises cache for parliament session {parliament_session_id}: {e}")
            self._promises_cache = []
            self._promise_embeddings_cache = None
    
    def _get_pending_evidence_items(self, limit: int, parliament_session_id: str = None) -> List[Dict[str, Any]]:
        """Get evidence items that need hybrid linking for a specific parliament session."""
        try:
            # Query for evidence items with pending promise linking status
            query = self.db.collection(self.evidence_collection).where(
                filter=firestore.FieldFilter('promise_linking_status', '==', 'pending')
            )
            
            # Filter by parliament session if specified
            if parliament_session_id:
                query = query.where(
                    filter=firestore.FieldFilter('parliament_session_id', '==', parliament_session_id)
                )
            
            query = query.limit(limit)
            
            items = []
            for doc in query.stream():
                item_data = doc.to_dict()
                item_data['_doc_id'] = doc.id
                items.append(item_data)
            
            if parliament_session_id:
                self.logger.info(f"Found {len(items)} evidence items for hybrid linking (parliament session {parliament_session_id})")
            else:
                self.logger.info(f"Found {len(items)} evidence items for hybrid linking (all sessions)")
            return items
            
        except Exception as e:
            self.logger.error(f"Error querying evidence items: {e}")
            return []
    
    def _process_evidence_batch(self, batch: List[Dict[str, Any]], validation_threshold: float) -> Dict[str, Any]:
        """Process a batch of evidence items using the hybrid approach."""
        batch_stats = {
            'items_processed': 0,
            'items_created': 0,
            'items_updated': 0,
            'items_skipped': 0,
            'errors': 0,
            'affected_promise_ids': set(),  # Track promises affected in this batch
            'optimizations': {
                'bill_linking_bypasses': 0,
                'high_similarity_bypasses': 0,
                'batch_llm_validations': 0
            }
        }
        
        for evidence_item in batch:
            try:
                batch_stats['items_processed'] += 1
                # Use the actual Firestore document ID, not the evidence_id field
                doc_id = evidence_item.get('_doc_id')
                evidence_id = evidence_item.get('evidence_id', doc_id)  # For logging only
                
                if not doc_id:
                    self.logger.error(f"Evidence item missing _doc_id: {evidence_id}")
                    batch_stats['errors'] += 1
                    continue
                
                self.logger.debug(f"Processing evidence item: {evidence_id} (doc_id: {doc_id})")
                
                # OPTIMIZATION 1: Check bill linking bypass
                bill_bypass_promise_ids = self._check_bill_linking_bypass(evidence_item)
                if bill_bypass_promise_ids:
                    self.logger.info(f"🚀 BILL BYPASS: Auto-linking {evidence_id} to {len(bill_bypass_promise_ids)} promises")
                    
                    success = self._update_evidence_with_promise_links(
                        doc_id,  # Use actual document ID
                        bill_bypass_promise_ids,
                        'bill_linking_bypass',
                        [0.95] * len(bill_bypass_promise_ids)  # High confidence for bill links
                    )
                    
                    if success:
                        batch_stats['items_updated'] += 1
                        batch_stats['optimizations']['bill_linking_bypasses'] += 1
                        batch_stats['affected_promise_ids'].update(bill_bypass_promise_ids)  # Track affected promises
                    else:
                        batch_stats['errors'] += 1
                    
                    continue
                
                # OPTIMIZATION 2: Semantic matching with LLM validation
                validated_matches = self._hybrid_evidence_linking(evidence_item, validation_threshold, batch_stats)
                
                if validated_matches:
                    # Update evidence with validated links
                    promise_ids = [match.promise_id for match in validated_matches]
                    confidence_scores = [match.confidence_score for match in validated_matches]
                    
                    success = self._update_evidence_with_promise_links(
                        doc_id,  # Use actual document ID
                        promise_ids,
                        'hybrid_semantic_llm',
                        confidence_scores
                    )
                    
                    if success:
                        batch_stats['items_updated'] += 1
                        batch_stats['affected_promise_ids'].update(promise_ids)  # Track affected promises
                    else:
                        batch_stats['errors'] += 1
                else:
                    # No matches found - still mark as processed with empty promise_ids
                    success = self._update_evidence_with_promise_links(
                        doc_id,  # Use actual document ID
                        [],  # Empty promise_ids array
                        'no_semantic_matches',
                        []  # Empty confidence scores
                    )
                    
                    if success:
                        batch_stats['items_updated'] += 1
                    else:
                        batch_stats['errors'] += 1
                    
            except Exception as e:
                self.logger.error(f"Error processing evidence item {evidence_item.get('evidence_id', 'unknown')}: {e}")
                batch_stats['errors'] += 1
                
                # Mark as linking error
                try:
                    doc_id = evidence_item.get('_doc_id')
                    if doc_id:
                        self.db.collection(self.evidence_collection).document(doc_id).update({
                            'promise_linking_status': 'error',
                            'promise_linking_processed_at': firestore.SERVER_TIMESTAMP,
                            'hybrid_linking_timestamp': firestore.SERVER_TIMESTAMP,
                            'error_message': str(e)
                        })
                except Exception:
                    pass
        
        return batch_stats
    
    def _check_bill_linking_bypass(self, evidence_item: Dict[str, Any]) -> List[str]:
        """
        Check if evidence can bypass semantic/LLM validation through bill linking.
        Uses evidence_source_document_raw_id for robust document matching.
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
                return []
            
            # Query for other evidence items with the same source document ID that are already linked
            query = (self.db.collection(self.evidence_collection)
                    .where(filter=firestore.FieldFilter('evidence_source_document_raw_id', '==', source_document_raw_id))
                    .where(filter=firestore.FieldFilter('promise_linking_status', '==', 'processed')))
            
            linked_promise_ids = set()
            
            for doc in query.stream():
                doc_data = doc.to_dict()
                promise_ids = doc_data.get('promise_ids', [])
                if isinstance(promise_ids, list) and promise_ids:
                    linked_promise_ids.update(promise_ids)
            
            return list(linked_promise_ids)
            
        except Exception as e:
            self.logger.error(f"Error in bill linking bypass check: {e}")
            return []
    
    def _hybrid_evidence_linking(
        self, 
        evidence_item: Dict[str, Any], 
        validation_threshold: float,
        batch_stats: Dict[str, Any]
    ) -> List[MatchEvaluation]:
        """
        Perform hybrid evidence linking: semantic pre-filtering + LLM validation.
        """
        try:
            # Generate evidence embedding
            evidence_text = self.semantic_linker.create_evidence_text(evidence_item)
            evidence_embedding = self.semantic_linker.generate_embeddings([evidence_text])
            
            if evidence_embedding.size == 0:
                self.logger.warning(f"Failed to generate embedding for evidence {evidence_item.get('evidence_id')}")
                return []
            
            # Find semantic matches
            semantic_matches = self.semantic_linker.find_semantic_matches(
                evidence_embedding[0], self._promise_embeddings_cache, self._promises_cache
            )
            
            if not semantic_matches:
                self.logger.debug(f"No semantic matches found above threshold {self.semantic_threshold}")
                return []
            
            # OPTIMIZATION 3: Separate high similarity matches from those needing LLM validation
            high_similarity_matches = []
            llm_validation_matches = []
            
            for match in semantic_matches:
                if match['similarity_score'] >= self.high_similarity_bypass_threshold:
                    high_similarity_matches.append(match)
                else:
                    llm_validation_matches.append(match)
            
            # Limit LLM validation candidates for performance
            if len(llm_validation_matches) > self.max_llm_candidates:
                llm_validation_matches = sorted(
                    llm_validation_matches, 
                    key=lambda x: x['similarity_score'], 
                    reverse=True
                )[:self.max_llm_candidates]
            
            validated_matches = []
            
            # Add high-confidence matches without LLM validation
            for match in high_similarity_matches:
                high_conf_eval = self._create_high_confidence_evaluation(match)
                validated_matches.append(high_conf_eval)
            
            if high_similarity_matches:
                batch_stats['optimizations']['high_similarity_bypasses'] += len(high_similarity_matches)
                self.logger.debug(f"🚀 HIGH SIMILARITY BYPASS: {len(high_similarity_matches)} matches ≥{self.high_similarity_bypass_threshold}")
            
            # LLM validate the remaining matches
            if llm_validation_matches:
                self.logger.debug(f"🔍 LLM VALIDATION: {len(llm_validation_matches)} matches need validation")
                
                llm_validated = self.llm_validator.batch_validate_matches(
                    evidence_item,
                    llm_validation_matches,
                    validation_threshold=validation_threshold
                )
                validated_matches.extend(llm_validated)
                batch_stats['optimizations']['batch_llm_validations'] += 1
            
            # Filter for high confidence matches
            final_matches = [
                match for match in validated_matches 
                if match.confidence_score >= validation_threshold
            ]
            
            self.logger.info(f"Hybrid linking result: {len(final_matches)} final matches from {len(semantic_matches)} semantic candidates")
            
            return final_matches
            
        except Exception as e:
            self.logger.error(f"Error in hybrid evidence linking: {e}")
            return []
    
    def _create_high_confidence_evaluation(self, semantic_match: Dict[str, Any]) -> MatchEvaluation:
        """Create high-confidence evaluation for semantic scores above bypass threshold."""
        similarity_score = semantic_match.get('similarity_score', 0.0)
        promise_data = semantic_match.get('promise_full', {})
        
        # Determine category based on similarity score
        if similarity_score >= 0.65:
            category = "Direct Implementation"
            confidence = 0.9
        elif similarity_score >= 0.55:
            category = "Supporting Action"
            confidence = 0.8
        else:  # >= bypass threshold
            category = "Related Policy"
            confidence = 0.7
        
        return MatchEvaluation(
            confidence_score=confidence,
            reasoning=f"High semantic similarity ({similarity_score:.3f}) indicates strong relationship. Auto-validated without LLM to improve performance.",
            category=category,
            thematic_alignment=similarity_score,
            department_overlap=True,
            timeline_relevance="Contemporary",
            implementation_type="Policy Implementation",
            semantic_quality_assessment="High quality semantic match",
            progress_indicator="Evidence of policy progress",
            promise_id=promise_data.get('promise_id', ''),
            semantic_similarity_score=similarity_score
        )
    
    def _update_evidence_with_promise_links(
        self,
        doc_id: str,
        promise_ids: List[str],
        optimization_method: str,
        confidence_scores: List[float]
    ) -> bool:
        """Update evidence item with promise links and hybrid linking metadata."""
        try:
            evidence_ref = self.db.collection(self.evidence_collection).document(doc_id)
            evidence_doc = evidence_ref.get()
            
            if not evidence_doc.exists:
                self.logger.error(f"Evidence document {doc_id} not found for update")
                return False
            
            evidence_data = evidence_doc.to_dict()
            evidence_id = evidence_data.get('evidence_id', doc_id)  # For logging
            
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
                'promise_links_found': len(all_promise_ids),  # Count total links, not just new ones
                'hybrid_linking_method': optimization_method,
                'hybrid_linking_avg_confidence': avg_confidence,
                'hybrid_linking_timestamp': firestore.SERVER_TIMESTAMP
            }
            
            evidence_ref.update(update_data)
            
            self.logger.info(f"✅ Updated evidence {evidence_id} (doc: {doc_id}): Added {len(promise_ids)} new links (method: {optimization_method}, avg confidence: {avg_confidence:.3f})")
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to update evidence {doc_id}: {e}")
            return False
    
    def _update_evidence_linking_status(self, doc_id: str, status: str, links_count: int):
        """Update the linking status of an evidence item."""
        try:
            self.db.collection(self.evidence_collection).document(doc_id).update({
                'promise_linking_status': status,
                'promise_linking_processed_at': firestore.SERVER_TIMESTAMP,
                'promise_links_found': links_count,
                'hybrid_linking_timestamp': firestore.SERVER_TIMESTAMP
            })
        except Exception as e:
            self.logger.warning(f"Failed to update linking status for {doc_id}: {e}")
    
    def should_trigger_downstream(self, result) -> bool:
        """
        Trigger downstream progress scoring if evidence items were updated.
        
        Args:
            result: Job execution result
            
        Returns:
            True if downstream jobs should be triggered
        """
        return result and result.items_updated > 0
    
    def get_trigger_metadata(self, result) -> Dict[str, Any]:
        """
        Get metadata for downstream progress scoring jobs.
        
        Args:
            result: Job execution result
            
        Returns:
            Metadata for downstream jobs
        """
        metadata = result.metadata if result else {}
        affected_promise_ids = metadata.get('affected_promise_ids', set())
        
        return {
            'triggered_by': self.job_name,
            'evidence_updated': result.items_updated if result else 0,
            'evidence_processed': result.items_processed if result else 0,
            'affected_promise_ids': list(affected_promise_ids),  # Convert set to list for JSON serialization
            'affected_promise_count': len(affected_promise_ids),
            'trigger_time': datetime.now(timezone.utc).isoformat(),
            'linking_method': 'hybrid_semantic_llm',
            'optimizations_used': metadata.get('optimizations', {})
        }

if __name__ == "__main__":
    import argparse
    import logging
    
    # Optionally load environment variables for local development
    # This won't break Cloud Run if python-dotenv isn't available
    try:
        from dotenv import load_dotenv
        # Go up to the PromiseTracker directory (4 levels from pipeline/stages/linking/)
        env_path = Path(__file__).resolve().parent.parent.parent.parent / '.env'
        load_dotenv(env_path)
        print(f"📋 Loaded environment from: {env_path}")
    except ImportError:
        print("📋 python-dotenv not available, skipping .env file loading")
    except Exception as e:
        print(f"📋 Could not load .env file: {e}")
    
    # Setup logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(name)s - %(message)s'
    )
    
    # Parse command line arguments
    parser = argparse.ArgumentParser(description='Hybrid Evidence Linker for Promise Tracker')
    parser.add_argument('--limit', type=int, default=100,
                        help='Maximum number of evidence items to process (default: 100)')
    parser.add_argument('--parliament_session_id', type=str, default='45',
                        help='Parliament session ID to process (default: 45)')
    parser.add_argument('--all_sessions', action='store_true',
                        help='Process all parliament sessions instead of default session')
    parser.add_argument('--validation_threshold', type=float, default=0.5,
                        help='LLM validation confidence threshold (default: 0.5)')
    parser.add_argument('--semantic_threshold', type=float, default=0.45,
                        help='Semantic similarity threshold (default: 0.45)')
    parser.add_argument('--batch_size', type=int, default=10,
                        help='Batch size for processing (default: 10)')
    parser.add_argument('--dry_run', action='store_true',
                        help='Run without making database updates')
    
    args = parser.parse_args()
    
    # Determine parliament session to process
    parliament_session_id = None if args.all_sessions else args.parliament_session_id
    
    print(f"🔗 Starting Hybrid Evidence Linker")
    print(f"Max Items: {args.limit}")
    if parliament_session_id:
        print(f"Parliament Session: {parliament_session_id}")
    else:
        print(f"Parliament Session: ALL")
    print(f"Validation Threshold: {args.validation_threshold}")
    print(f"Semantic Threshold: {args.semantic_threshold}")
    print(f"Batch Size: {args.batch_size}")
    print(f"Dry Run: {args.dry_run}")
    print("-" * 60)
    
    try:
        # Create job configuration
        config = {
            'batch_size': args.batch_size,
            'max_items_per_run': args.limit,
            'semantic_threshold': args.semantic_threshold,
            'llm_validation_threshold': args.validation_threshold,
            'default_parliament_session': args.parliament_session_id,
            'dry_run': args.dry_run
        }
        
        # Initialize and run the evidence linker
        linker = EvidenceLinker("hybrid_evidence_linker", config)
        
        # Execute the job
        result = linker.execute(
            limit=args.limit,
            validation_threshold=args.validation_threshold,
            parliament_session_id=parliament_session_id
        )
        
        # Print results
        print("\n" + "=" * 60)
        print("🎉 Evidence Linking Complete!")
        print(f"Status: {result.status.value}")
        print(f"Duration: {result.duration_seconds:.2f} seconds")
        print(f"Items Processed: {result.items_processed}")
        print(f"Items Updated: {result.items_updated}")
        print(f"Items Skipped: {result.items_skipped}")
        print(f"Errors: {result.errors}")
        
        if result.metadata:
            optimizations = result.metadata.get('optimizations', {})
            print(f"\nOptimizations:")
            print(f"  Bill Linking Bypasses: {optimizations.get('bill_linking_bypasses', 0)}")
            print(f"  High Similarity Bypasses: {optimizations.get('high_similarity_bypasses', 0)}")
            print(f"  Batch LLM Validations: {optimizations.get('batch_llm_validations', 0)}")
        
        if result.error_message:
            print(f"\nError: {result.error_message}")
            
    except KeyboardInterrupt:
        print("\n🛑 Interrupted by user")
    except Exception as e:
        print(f"\n❌ Error: {e}")
        logging.error("Evidence linker failed", exc_info=True) 