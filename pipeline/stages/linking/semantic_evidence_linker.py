#!/usr/bin/env python3
"""
Semantic Evidence Linking Module

Production-ready semantic similarity-based evidence linking using sentence transformers.
Replaces keyword-based approach with embedding-based cosine similarity matching.

This module provides semantic evidence linking functionality that:
- Uses sentence transformers to generate embeddings for evidence and promises
- Calculates cosine similarity for matching
- Provides configurable similarity thresholds
- Integrates with existing pipeline infrastructure
"""

import logging
import time
from typing import List, Dict, Any, Tuple, Optional
import numpy as np
from sklearn.metrics.pairwise import cosine_similarity
from sentence_transformers import SentenceTransformer
import firebase_admin
from firebase_admin import firestore
from google.cloud import firestore as firestore_client
from datetime import datetime, timezone
import json
from pathlib import Path

# Set up logging
logger = logging.getLogger(__name__)

class SemanticEvidenceLinker:
    """
    Semantic evidence linking using sentence transformers and cosine similarity.
    
    This class provides semantic matching between evidence items and promises by:
    1. Generating embeddings using sentence transformers
    2. Computing cosine similarity between evidence and promise embeddings
    3. Linking evidence to promises above a configurable similarity threshold
    """
    
    def __init__(
        self,
        model_name: str = "all-MiniLM-L6-v2",
        similarity_threshold: float = 0.55,
        max_links_per_evidence: int = 50,
        batch_size: int = 32
    ):
        """
        Initialize the semantic evidence linker.
        
        Args:
            model_name: Name of the sentence transformer model to use
            similarity_threshold: Minimum cosine similarity score for linking (0.0-1.0)
            max_links_per_evidence: Maximum number of links to create per evidence item
            batch_size: Batch size for embedding generation
        """
        self.model_name = model_name
        self.similarity_threshold = similarity_threshold
        self.max_links_per_evidence = max_links_per_evidence
        self.batch_size = batch_size
        
        self.model = None
        self.db = None
        
        # Performance tracking
        self.stats = {
            'embeddings_generated': 0,
            'similarities_calculated': 0,
            'links_created': 0,
            'processing_time': 0.0
        }
    
    def initialize(self) -> None:
        """
        Initialize the model and database connection.
        
        Raises:
            Exception: If model loading or database connection fails
        """
        try:
            # Load sentence transformer model
            logger.info(f"Loading sentence transformer model: {self.model_name}")
            start_time = time.time()
            self.model = SentenceTransformer(self.model_name)
            load_time = time.time() - start_time
            logger.info(f"Model loaded in {load_time:.2f} seconds")
            
            # Initialize Firestore connection
            if not firebase_admin._apps:
                firebase_admin.initialize_app()
            self.db = firestore.client()
            logger.info("Connected to Firestore database")
            
        except Exception as e:
            logger.error(f"Failed to initialize semantic evidence linker: {e}")
            raise
    
    def generate_embeddings(self, texts: List[str]) -> np.ndarray:
        """
        Generate embeddings for a list of texts.
        
        Args:
            texts: List of texts to generate embeddings for
            
        Returns:
            numpy array of embeddings (shape: [len(texts), embedding_dim])
            
        Raises:
            Exception: If embedding generation fails
        """
        if not self.model:
            raise Exception("Model not initialized. Call initialize() first.")
        
        if not texts:
            return np.array([])
        
        try:
            logger.info(f"Generating embeddings for {len(texts)} texts")
            start_time = time.time()
            
            # Generate embeddings in batches
            embeddings = self.model.encode(texts, batch_size=self.batch_size, show_progress_bar=False)
            
            generation_time = time.time() - start_time
            logger.info(f"Generated {len(embeddings)} embeddings in {generation_time:.2f} seconds")
            
            self.stats['embeddings_generated'] += len(embeddings)
            
            return embeddings
            
        except Exception as e:
            logger.error(f"Failed to generate embeddings: {e}")
            raise
    
    def create_evidence_text(self, evidence_item: Dict[str, Any]) -> str:
        """
        Create a unified text representation of an evidence item for embedding.
        
        Args:
            evidence_item: Evidence item document from Firestore
            
        Returns:
            Combined text string for embedding generation
        """
        text_parts = []
        
        # Core evidence content
        if evidence_item.get('title_or_summary'):
            text_parts.append(evidence_item['title_or_summary'])
        
        if evidence_item.get('description_or_details'):
            text_parts.append(evidence_item['description_or_details'])
        
        # LLM analysis content if available
        llm_analysis = evidence_item.get('llm_analysis_raw', {})
        if isinstance(llm_analysis, dict):
            if llm_analysis.get('one_sentence_description'):
                text_parts.append(llm_analysis['one_sentence_description'])
            
            # Add key concepts
            key_concepts = llm_analysis.get('key_concepts', [])
            if isinstance(key_concepts, list) and key_concepts:
                text_parts.append(', '.join(key_concepts))
        
        # Fallback to top-level key_concepts if no LLM analysis
        if not text_parts and evidence_item.get('key_concepts'):
            key_concepts = evidence_item['key_concepts']
            if isinstance(key_concepts, list):
                text_parts.append(', '.join(key_concepts))
        
        # Join all parts
        combined_text = ' '.join(text_parts).strip()
        
        # Fallback if no text available
        if not combined_text:
            combined_text = evidence_item.get('evidence_id', 'Unknown evidence')
        
        return combined_text
    
    def create_promise_text(self, promise_item: Dict[str, Any]) -> str:
        """
        Create a unified text representation of a promise item for embedding.
        
        Args:
            promise_item: Promise document from Firestore
            
        Returns:
            Combined text string for embedding generation
        """
        text_parts = []
        
        # Primary promise content
        if promise_item.get('text'):
            text_parts.append(promise_item['text'])
        
        if promise_item.get('description'):
            text_parts.append(promise_item['description'])
        
        if promise_item.get('background_and_context'):
            text_parts.append(promise_item['background_and_context'])
        
        # Additional context
        if promise_item.get('reporting_lead_title'):
            text_parts.append(f"Lead: {promise_item['reporting_lead_title']}")
        
        # Join all parts
        combined_text = ' '.join(text_parts).strip()
        
        # Fallback if no text available
        if not combined_text:
            combined_text = promise_item.get('promise_id', 'Unknown promise')
        
        return combined_text
    
    def find_semantic_matches(
        self,
        evidence_embedding: np.ndarray,
        promise_embeddings: np.ndarray,
        promise_docs: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """
        Find semantic matches between evidence and promises using cosine similarity.
        
        Args:
            evidence_embedding: Embedding vector for the evidence item
            promise_embeddings: Embedding matrix for all promises
            promise_docs: List of promise documents with full data
            
        Returns:
            List of match dictionaries with promise details and similarity scores
        """
        if evidence_embedding.size == 0 or promise_embeddings.size == 0:
            return []
        
        # Calculate cosine similarities with better error handling
        logger.debug(f"Computing similarities between evidence and {len(promise_embeddings)} promises")
        
        # Validate embeddings before similarity calculation
        evidence_embedding = evidence_embedding.reshape(1, -1)
        
        # Check for zero magnitude vectors or NaN/infinite values
        evidence_norm = np.linalg.norm(evidence_embedding)
        if evidence_norm == 0 or np.isnan(evidence_norm) or np.isinf(evidence_norm):
            logger.warning("Evidence embedding has zero magnitude, NaN, or infinite values - skipping similarity calculation")
            return []
        
        # Check promise embeddings for issues and filter out problematic ones
        promise_norms = np.linalg.norm(promise_embeddings, axis=1)
        valid_indices = (promise_norms > 1e-10) & (~np.isnan(promise_norms)) & (~np.isinf(promise_norms))
        
        if not np.any(valid_indices):
            logger.warning("No valid promise embeddings found")
            return []
        
        valid_count = np.sum(valid_indices)
        if valid_count < len(promise_embeddings):
            logger.debug(f"Filtered out {len(promise_embeddings) - valid_count} invalid promise embeddings")
        
        # Filter to valid embeddings and corresponding promises
        valid_promise_embeddings = promise_embeddings[valid_indices]
        valid_promises = [promise_docs[i] for i in range(len(promise_docs)) if valid_indices[i]]
        
        # Normalize embeddings to prevent overflow
        evidence_embedding_norm = evidence_embedding / evidence_norm
        promise_norms_valid = promise_norms[valid_indices].reshape(-1, 1)
        valid_promise_embeddings_norm = valid_promise_embeddings / promise_norms_valid
        
        # Safe cosine similarity calculation using normalized embeddings
        try:
            # Use normalized dot product which is equivalent to cosine similarity
            similarities = np.dot(evidence_embedding_norm, valid_promise_embeddings_norm.T).flatten()
            
            # Clamp similarities to valid range [-1, 1] to handle any numerical precision issues
            similarities = np.clip(similarities, -1.0, 1.0)
            
            # Handle any remaining NaN values
            similarities = np.nan_to_num(similarities, nan=0.0, posinf=1.0, neginf=-1.0)
            
            self.stats['similarities_calculated'] += len(similarities)
            
        except Exception as e:
            logger.error(f"Error calculating cosine similarities: {e}")
            return []
        
        # Filter by threshold and create detailed match objects
        matches = []
        for i, similarity in enumerate(similarities):
            if similarity >= self.similarity_threshold:
                promise = valid_promises[i]
                matches.append({
                    'promise_id': promise.get('promise_id'),
                    'promise_text': promise.get('text', promise.get('canonical_commitment_text', '')),
                    'promise_description': promise.get('description', ''),
                    'similarity_score': float(similarity),
                    'confidence': float(similarity),
                    'match_type': 'semantic_similarity',
                    'promise_full': promise  # Keep full promise object for compatibility
                })
        
        # Sort by similarity score (descending) and limit results
        matches.sort(key=lambda x: x['similarity_score'], reverse=True)
        if self.max_links_per_evidence > 0:
            matches = matches[:self.max_links_per_evidence]
        
        # Log top matches for debugging
        logger.info(f"Found {len(matches)} semantic matches above threshold {self.similarity_threshold}")
        for i, match in enumerate(matches[:5]):  # Top 5 matches
            promise_text = match['promise_text'][:100]
            logger.info(f"  Match {i+1}: {match['similarity_score']:.3f} - {promise_text}...")
        
        return matches
    
    def fetch_promises(
        self,
        parliament_session_id: str,
        collection_name: str = "promises"
    ) -> Tuple[List[Dict[str, Any]], List[str]]:
        """
        Fetch all promises for a given parliament session.
        
        Args:
            parliament_session_id: Parliament session to fetch promises for
            collection_name: Name of the promises collection
            
        Returns:
            Tuple of (promise_documents, promise_ids)
        """
        logger.info(f"Fetching all promises for session {parliament_session_id} from {collection_name}")
        
        try:
            query = self.db.collection(collection_name).where(
                filter=firestore_client.FieldFilter('parliament_session_id', '==', parliament_session_id)
            )
            
            promise_docs = []
            promise_ids = []
            
            for doc in query.stream():
                promise_data = doc.to_dict()
                promise_data['__path__'] = doc.reference.path
                promise_docs.append(promise_data)
                promise_ids.append(promise_data.get('promise_id', doc.id))
            
            logger.info(f"Successfully fetched {len(promise_docs)} promises for session {parliament_session_id}")
            return promise_docs, promise_ids
            
        except Exception as e:
            logger.error(f"Failed to fetch promises: {e}")
            raise
    
    def update_evidence_links(
        self,
        evidence_id: str,
        new_promise_ids: List[str],
        collection_name: str = "evidence_items",
        dry_run: bool = False
    ) -> bool:
        """
        Update evidence item with new semantic links.
        
        Args:
            evidence_id: ID of the evidence item to update
            new_promise_ids: List of promise IDs to link
            collection_name: Name of the evidence collection
            dry_run: If True, don't actually update the database
            
        Returns:
            True if update successful, False otherwise
        """
        if dry_run:
            logger.info(f"[DRY RUN] Would update evidence {evidence_id} with {len(new_promise_ids)} semantic links")
            return True
        
        try:
            # Get current evidence document
            evidence_ref = self.db.collection(collection_name).document(evidence_id)
            evidence_doc = evidence_ref.get()
            
            if not evidence_doc.exists:
                logger.error(f"Evidence document {evidence_id} not found")
                return False
            
            evidence_data = evidence_doc.to_dict()
            
            # Get existing promise IDs
            existing_promise_ids = evidence_data.get('promise_ids', [])
            if not isinstance(existing_promise_ids, list):
                existing_promise_ids = []
            
            # Merge with new semantic links (avoid duplicates)
            all_promise_ids = list(set(existing_promise_ids + new_promise_ids))
            
            # Update document
            update_data = {
                'promise_ids': all_promise_ids,
                'promise_linking_status': 'processed',
                'promise_linking_processed_at': firestore.SERVER_TIMESTAMP,
                'promise_links_found': len([pid for pid in new_promise_ids if pid not in existing_promise_ids])
            }
            
            evidence_ref.update(update_data)
            
            logger.info(f"Updated evidence {evidence_id}: {len(existing_promise_ids)} -> {len(all_promise_ids)} total links")
            return True
            
        except Exception as e:
            logger.error(f"Failed to update evidence {evidence_id}: {e}")
            return False
    
    def process_evidence_item(
        self,
        evidence_item: Dict[str, Any],
        promise_embeddings: np.ndarray,
        promise_docs: List[Dict[str, Any]],
        collection_name: str = "evidence_items",
        dry_run: bool = False
    ) -> int:
        """
        Process a single evidence item for semantic linking.
        
        Args:
            evidence_item: Evidence item document
            promise_embeddings: Pre-computed promise embeddings
            promise_docs: List of promise documents corresponding to embeddings
            collection_name: Name of the evidence collection
            dry_run: If True, don't actually update the database
            
        Returns:
            Number of semantic links created
        """
        evidence_id = evidence_item.get('evidence_id')
        if not evidence_id:
            logger.warning("Evidence item missing evidence_id")
            return 0
        
        try:
            # Create evidence text and generate embedding
            evidence_text = self.create_evidence_text(evidence_item)
            evidence_embedding = self.generate_embeddings([evidence_text])
            
            if evidence_embedding.size == 0:
                logger.warning(f"Failed to generate embedding for evidence {evidence_id}")
                return 0
            
            # Find semantic matches
            semantic_matches = self.find_semantic_matches(
                evidence_embedding[0], promise_embeddings, promise_docs
            )
            
            if not semantic_matches:
                logger.info(f"No semantic matches found for evidence {evidence_id}")
                return 0
            
            # Extract promise IDs and log matches
            new_promise_ids = [match['promise_id'] for match in semantic_matches]
            
            logger.info(f"Found {len(semantic_matches)} semantic matches for evidence {evidence_id}")
            for match in semantic_matches[:5]:  # Log top 5
                logger.info(f"  -> {match['promise_id']} (Similarity: {match['similarity_score']:.3f})")
            
            # Update evidence with semantic links
            success = self.update_evidence_links(
                evidence_id, new_promise_ids, collection_name, dry_run
            )
            
            if success:
                self.stats['links_created'] += len(new_promise_ids)
                return len(new_promise_ids)
            else:
                return 0
                
        except Exception as e:
            logger.error(f"Failed to process evidence {evidence_id}: {e}")
            return 0
    
    def process_evidence_batch(
        self,
        parliament_session_id: str,
        evidence_collection: str = "evidence_items",
        promise_collection: str = "promises",
        limit: Optional[int] = None,
        dry_run: bool = False,
        generate_debug_files: bool = False
    ) -> Dict[str, Any]:
        """
        Process a batch of evidence items for semantic linking.
        
        Args:
            parliament_session_id: Parliament session to process
            evidence_collection: Name of the evidence collection
            promise_collection: Name of the promise collection
            limit: Maximum number of evidence items to process (None for all)
            dry_run: If True, don't actually update the database
            generate_debug_files: If True, generate JSON debug files
            
        Returns:
            Dictionary with processing statistics and detailed results
        """
        if not self.model or not self.db:
            raise Exception("Linker not initialized. Call initialize() first.")
        
        start_time = time.time()
        
        try:
            # Fetch promises and generate embeddings
            logger.info(f"Fetching promises for session {parliament_session_id}")
            promise_docs, promise_ids = self.fetch_promises(parliament_session_id, promise_collection)
            
            if not promise_docs:
                logger.warning(f"No promises found for session {parliament_session_id}")
                return {'success': False, 'error': 'No promises found'}
            
            # Generate promise embeddings
            logger.info("Generating promise embeddings...")
            promise_texts = [self.create_promise_text(promise) for promise in promise_docs]
            promise_embeddings = self.generate_embeddings(promise_texts)
            
            # Fetch evidence items to process
            logger.info(f"Fetching evidence items from {evidence_collection}")
            evidence_query = self.db.collection(evidence_collection).where(
                filter=firestore_client.FieldFilter('parliament_session_id', '==', parliament_session_id)
            ).where(
                filter=firestore_client.FieldFilter('promise_linking_status', '==', 'pending')
            )
            
            if limit:
                evidence_query = evidence_query.limit(limit)
            
            evidence_items = []
            for doc in evidence_query.stream():
                evidence_data = doc.to_dict()
                evidence_data['__path__'] = doc.reference.path
                evidence_items.append(evidence_data)
            
            logger.info(f"Found {len(evidence_items)} evidence items ready for processing")
            
            if not evidence_items:
                return {
                    'success': True,
                    'evidence_processed': 0,
                    'promises_loaded': len(promise_docs),
                    'total_links_created': 0,
                    'processing_time': time.time() - start_time
                }
            
            # Process each evidence item and collect detailed results
            total_links_created = 0
            processed_count = 0
            detailed_results = []
            
            for i, evidence_item in enumerate(evidence_items, 1):
                evidence_id = evidence_item.get('evidence_id')
                logger.info(f"Processing evidence item {i}/{len(evidence_items)}: {evidence_id}")
                
                # Initialize result for this evidence item (for debug output)
                evidence_result = {
                    "evidence_id": evidence_id,
                    "evidence_title": evidence_item.get('title_or_summary', 'No title'),
                    "evidence_source_type": evidence_item.get('evidence_source_type', 'Unknown'),
                    "evidence_date": evidence_item.get('evidence_date', 'Unknown'),
                    "before_promise_ids": evidence_item.get('promise_ids', []),
                    "semantic_matches": [],
                    "links_created": 0,
                    "processing_success": False,
                    "error": None
                } if generate_debug_files else None
                
                try:
                    # Create evidence text and generate embedding
                    evidence_text = self.create_evidence_text(evidence_item)
                    evidence_embedding = self.generate_embeddings([evidence_text])
                    
                    if evidence_embedding.size == 0:
                        logger.warning(f"Failed to generate embedding for evidence {evidence_id}")
                        if evidence_result:
                            evidence_result["error"] = "Failed to generate embedding"
                        continue
                    
                    # Find semantic matches
                    semantic_matches = self.find_semantic_matches(
                        evidence_embedding[0], promise_embeddings, promise_docs
                    )
                    
                    if evidence_result:
                        evidence_result["semantic_matches"] = semantic_matches
                    
                    if not semantic_matches:
                        logger.info(f"No semantic matches found for evidence {evidence_id}")
                        if evidence_result:
                            evidence_result["processing_success"] = True
                        processed_count += 1
                        continue
                    
                    # Extract promise IDs and log matches
                    new_promise_ids = [match['promise_id'] for match in semantic_matches]
                    
                    logger.info(f"Found {len(semantic_matches)} semantic matches for evidence {evidence_id}")
                    for match in semantic_matches[:5]:  # Log top 5
                        logger.info(f"  -> {match['promise_id']} (Similarity: {match['similarity_score']:.3f})")
                    
                    # Update evidence with semantic links
                    success = self.update_evidence_links(
                        evidence_id, new_promise_ids, evidence_collection, dry_run
                    )
                    
                    if success:
                        links_created = len(new_promise_ids)
                        total_links_created += links_created
                        self.stats['links_created'] += links_created
                        if evidence_result:
                            evidence_result["links_created"] = links_created
                            evidence_result["processing_success"] = True
                    
                    processed_count += 1
                    
                except Exception as e:
                    logger.error(f"Failed to process evidence {evidence_id}: {e}")
                    if evidence_result:
                        evidence_result["error"] = str(e)
                
                if evidence_result:
                    detailed_results.append(evidence_result)
            
            processing_time = time.time() - start_time
            self.stats['processing_time'] += processing_time
            
            # Prepare return data
            result = {
                'success': True,
                'evidence_processed': processed_count,
                'promises_loaded': len(promise_docs),
                'total_links_created': total_links_created,
                'processing_time': processing_time,
                'stats': self.stats.copy()
            }
            
            # Generate debug files if requested
            if generate_debug_files:
                timestamp = int(time.time())
                
                # Create comprehensive batch results
                batch_results = {
                    "success": True,
                    "parliament_session_id": parliament_session_id,
                    "processing_metadata": {
                        "evidence_collection": evidence_collection,
                        "promise_collection": promise_collection,
                        "limit": limit,
                        "dry_run": dry_run,
                        "similarity_threshold": self.similarity_threshold,
                        "total_processing_time": processing_time,
                        "model_name": self.model_name,
                        "timestamp": datetime.now(timezone.utc).isoformat()
                    },
                    "summary": {
                        "evidence_items_processed": processed_count,
                        "promises_fetched": len(promise_docs),
                        "total_semantic_links_created": total_links_created,
                        "embeddings_generated": self.stats['embeddings_generated'],
                        "similarities_calculated": self.stats['similarities_calculated'],
                        "errors": self.stats.get('errors', 0)
                    },
                    "detailed_results": detailed_results,
                    "stats": self.stats.copy()
                }
                
                # Save comprehensive batch results to JSON files
                debug_dir = Path("debug_output")
                debug_dir.mkdir(exist_ok=True)
                
                # Main results file
                batch_result_filename = f"production_semantic_linking_session_{parliament_session_id}_limit_{limit or 'all'}_{timestamp}.json"
                batch_result_filepath = debug_dir / batch_result_filename
                
                with open(batch_result_filepath, 'w') as f:
                    json.dump(batch_results, f, indent=2, default=str)
                
                logger.info(f"Production batch results saved to: {batch_result_filepath}")
                
                # Add file paths to return data
                result["debug_files"] = {
                    "batch_results": str(batch_result_filepath)
                }
            
            return result
            
        except Exception as e:
            logger.error(f"Failed to process evidence batch: {e}")
            return {
                'success': False,
                'error': str(e),
                'processing_time': time.time() - start_time
            }
    
    def get_stats(self) -> Dict[str, Any]:
        """
        Get current processing statistics.
        
        Returns:
            Dictionary with current statistics
        """
        return self.stats.copy()
    
    def reset_stats(self) -> None:
        """Reset processing statistics."""
        self.stats = {
            'embeddings_generated': 0,
            'similarities_calculated': 0,
            'links_created': 0,
            'processing_time': 0.0
        }


# Convenience function for direct usage
def link_evidence_semantically(
    parliament_session_id: str,
    evidence_collection: str = "evidence_items",
    promise_collection: str = "promises",
    similarity_threshold: float = 0.55,
    max_links_per_evidence: int = 50,
    limit: Optional[int] = None,
    dry_run: bool = False,
    generate_debug_files: bool = False
) -> Dict[str, Any]:
    """
    Convenience function to perform semantic evidence linking.
    
    Args:
        parliament_session_id: Parliament session to process
        evidence_collection: Name of the evidence collection
        promise_collection: Name of the promise collection
        similarity_threshold: Minimum similarity score for linking (0.0-1.0)
        max_links_per_evidence: Maximum links per evidence item
        limit: Maximum number of evidence items to process
        dry_run: If True, don't actually update the database
        generate_debug_files: If True, generate JSON debug files with detailed results
        
    Returns:
        Dictionary with processing results
    """
    linker = SemanticEvidenceLinker(
        similarity_threshold=similarity_threshold,
        max_links_per_evidence=max_links_per_evidence
    )
    
    try:
        linker.initialize()
        return linker.process_evidence_batch(
            parliament_session_id=parliament_session_id,
            evidence_collection=evidence_collection,
            promise_collection=promise_collection,
            limit=limit,
            dry_run=dry_run,
            generate_debug_files=generate_debug_files
        )
    except Exception as e:
        logger.error(f"Semantic evidence linking failed: {e}")
        return {'success': False, 'error': str(e)} 