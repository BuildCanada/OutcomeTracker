#!/usr/bin/env python3
"""
Semantic Evidence Linking Test Script

Test script for evaluating semantic similarity-based approach to linking evidence items to promises.
Uses sentence transformers to generate embeddings and calculate cosine similarity for matching.

Usage:
    python test_semantic_evidence_linking.py --parliament_session_id 44 --evidence_id_to_test <evidence_id> [options]
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
import numpy as np

# Add parent directory to path to import modules
sys.path.append(str(Path(__file__).parent.parent.parent / 'lib'))

# Load environment variables
load_dotenv()

# Logger setup
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(filename)s:%(lineno)d - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger("semantic_evidence_linking")

# Try to import sentence transformers
try:
    from sentence_transformers import SentenceTransformer
    from sklearn.metrics.pairwise import cosine_similarity
    logger.info("Successfully imported sentence transformers and sklearn")
except ImportError as e:
    logger.error(f"Failed to import required packages: {e}")
    logger.error("Please install: pip install sentence-transformers scikit-learn")
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
                app_name = 'semantic_evidence_linking_app'
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
        else:
            logger.warning("FIREBASE_SERVICE_ACCOUNT_KEY_PATH environment variable not set, and default creds failed.")

if db is None:
    logger.critical("CRITICAL: Failed to obtain Firestore client. Exiting.")
    exit("Exiting: Firestore client not available.")

# Constants
PROMISES_COLLECTION_TEST = 'promises_test'
PROMISES_COLLECTION_PROD = 'promises'
EVIDENCE_ITEMS_COLLECTION_TEST = 'evidence_items_test'
EVIDENCE_ITEMS_COLLECTION_PROD = 'evidence_items'

# Semantic similarity settings
DEFAULT_MODEL_NAME = 'all-MiniLM-L6-v2'  # Fast, good quality model
DEFAULT_SIMILARITY_THRESHOLD = 0.4  # Minimum similarity score for linking
RATE_LIMIT_DELAY_SECONDS = 1


class SemanticEvidenceLinkingTester:
    """Handles semantic similarity-based evidence linking testing and evaluation."""
    
    def __init__(self, use_test_collections: bool = True, model_name: str = DEFAULT_MODEL_NAME):
        """Initialize the tester with semantic model and collection settings."""
        
        # Load sentence transformer model
        logger.info(f"Loading sentence transformer model: {model_name}")
        start_time = time.time()
        self.model = SentenceTransformer(model_name)
        load_time = time.time() - start_time
        logger.info(f"Model loaded in {load_time:.2f} seconds")
        
        self.use_test_collections = use_test_collections
        
        # Set collection names based on mode
        if use_test_collections:
            self.promises_collection = PROMISES_COLLECTION_TEST
            self.evidence_items_collection = EVIDENCE_ITEMS_COLLECTION_TEST
            logger.info("Using TEST collections for safe testing")
        else:
            self.promises_collection = PROMISES_COLLECTION_PROD
            self.evidence_items_collection = EVIDENCE_ITEMS_COLLECTION_PROD
            logger.warning("Using PRODUCTION collections - changes will affect live data")
        
        # Settings
        self.similarity_threshold = DEFAULT_SIMILARITY_THRESHOLD
        
        self.stats = {
            'evidence_items_processed': 0,
            'promises_fetched': 0,
            'embeddings_generated': 0,
            'similarities_calculated': 0,
            'links_created': 0,
            'errors': 0
        }
    
    def extract_text_for_embedding(self, item: Dict[str, Any], item_type: str = 'evidence') -> str:
        """
        Extract meaningful text from evidence or promise for embedding generation.
        
        Args:
            item: Evidence item or promise document
            item_type: 'evidence' or 'promise'
            
        Returns:
            Combined text string for embedding
        """
        text_parts = []
        
        if item_type == 'evidence':
            # Extract evidence text fields
            fields = ['title_or_summary', 'title', 'description_or_details', 'description', 'summary']
            for field in fields:
                value = item.get(field, '')
                if value and isinstance(value, str) and value.strip():
                    text_parts.append(value.strip())
        
        elif item_type == 'promise':
            # Extract promise text fields
            fields = ['text', 'canonical_commitment_text', 'description', 'background_and_context']
            for field in fields:
                value = item.get(field, '')
                if value and isinstance(value, str) and value.strip():
                    text_parts.append(value.strip())
        
        # Combine all text parts
        combined_text = ' '.join(text_parts)
        
        # Clean up the text
        combined_text = ' '.join(combined_text.split())  # Remove extra whitespace
        
        return combined_text[:1000]  # Limit to 1000 chars to avoid token limits
    
    async def fetch_target_evidence_item(self, evidence_id: str) -> Optional[Dict[str, Any]]:
        """
        Fetch the specific evidence item to test linking for.
        
        Args:
            evidence_id: The specific evidence ID to fetch
            
        Returns:
            Evidence item data or None if not found
        """
        try:
            logger.info(f"Fetching evidence item: {evidence_id} from {self.evidence_items_collection}")
            
            doc_ref = db.collection(self.evidence_items_collection).document(evidence_id)
            doc = await asyncio.to_thread(doc_ref.get)
            
            if not doc.exists:
                logger.error(f"Evidence item {evidence_id} not found in {self.evidence_items_collection}")
                return None
            
            evidence_data = doc.to_dict()
            evidence_data['_doc_id'] = doc.id
            
            logger.info(f"Successfully fetched evidence item: {evidence_id}")
            return evidence_data
            
        except Exception as e:
            logger.error(f"Error fetching evidence item {evidence_id}: {e}", exc_info=True)
            return None
    
    async def fetch_evidence_items_for_processing(self, parliament_session_id: str, limit: Optional[int] = None) -> List[Dict[str, Any]]:
        """
        Fetch evidence items that need semantic linking processing.
        
        Args:
            parliament_session_id: Parliament session to fetch evidence for
            limit: Maximum number of evidence items to fetch
            
        Returns:
            List of evidence items ready for processing
        """
        try:
            logger.info(f"Fetching evidence items for processing from {self.evidence_items_collection}")
            
            # Query evidence items for the session
            query = db.collection(self.evidence_items_collection).where(
                filter=firestore.FieldFilter("parliament_session_id", "==", parliament_session_id)
            ).where(
                filter=firestore.FieldFilter("promise_linking_status", "==", "pending")
            )
            
            # Apply limit if specified
            if limit:
                query = query.limit(limit)
                logger.info(f"Limiting to {limit} evidence items")
            
            evidence_docs = await asyncio.to_thread(list, query.stream())
            
            evidence_items = []
            for doc in evidence_docs:
                data = doc.to_dict()
                if data:
                    data['_doc_id'] = doc.id
                    evidence_items.append(data)
                else:
                    logger.warning(f"Evidence item {doc.id} has no data, skipping")
            
            logger.info(f"Found {len(evidence_items)} evidence items ready for processing")
            return evidence_items
            
        except Exception as e:
            logger.error(f"Error fetching evidence items for processing: {e}", exc_info=True)
            return []
    
    async def fetch_promises_for_session(self, parliament_session_id: str) -> List[Dict[str, Any]]:
        """
        Fetch all promises for the specified parliament session.
        
        Args:
            parliament_session_id: Parliament session to fetch promises for
            
        Returns:
            List of promise data with required fields
        """
        try:
            logger.info(f"Fetching all promises for session {parliament_session_id} from {self.promises_collection}")
            
            # Query promises for the session
            query = db.collection(self.promises_collection).where(
                filter=firestore.FieldFilter("parliament_session_id", "==", parliament_session_id)
            )
            
            promise_docs = await asyncio.to_thread(list, query.stream())
            
            promises = []
            for doc in promise_docs:
                data = doc.to_dict()
                if data:
                    promise_summary = {
                        'promise_id': doc.id,
                        'text': data.get('text', data.get('canonical_commitment_text', '')),
                        'description': data.get('description', ''),
                        'background_and_context': data.get('background_and_context', ''),
                        'reporting_lead_title': data.get('reporting_lead_title', ''),
                        'relevant_departments': data.get('relevant_departments', []),
                        'extracted_keywords_concepts': data.get('extracted_keywords_concepts', [])
                    }
                    promises.append(promise_summary)
                else:
                    logger.warning(f"Promise {doc.id} has no data, skipping")
            
            self.stats['promises_fetched'] = len(promises)
            logger.info(f"Successfully fetched {len(promises)} promises for session {parliament_session_id}")
            
            return promises
            
        except Exception as e:
            logger.error(f"Error fetching promises for session {parliament_session_id}: {e}", exc_info=True)
            return []
    
    def generate_embeddings(self, texts: List[str], batch_size: int = 32) -> np.ndarray:
        """
        Generate embeddings for a list of texts.
        
        Args:
            texts: List of text strings
            batch_size: Batch size for processing
            
        Returns:
            Array of embeddings
        """
        try:
            logger.info(f"Generating embeddings for {len(texts)} texts")
            start_time = time.time()
            
            # Generate embeddings in batches
            embeddings = self.model.encode(texts, batch_size=batch_size, show_progress_bar=False)
            
            generation_time = time.time() - start_time
            self.stats['embeddings_generated'] += len(texts)
            
            logger.info(f"Generated {len(embeddings)} embeddings in {generation_time:.2f} seconds")
            return embeddings
            
        except Exception as e:
            logger.error(f"Error generating embeddings: {e}")
            return np.array([])
    
    def find_semantic_matches(self, evidence_embedding: np.ndarray, promise_embeddings: np.ndarray, 
                             promises: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Find promises that semantically match the evidence using cosine similarity.
        
        Args:
            evidence_embedding: Embedding for the evidence item
            promise_embeddings: Embeddings for all promises
            promises: List of promise documents
            
        Returns:
            List of matches with similarity scores
        """
        try:
            # Calculate cosine similarities
            similarities = cosine_similarity([evidence_embedding], promise_embeddings)[0]
            self.stats['similarities_calculated'] += len(similarities)
            
            # Find matches above threshold
            matches = []
            for i, similarity in enumerate(similarities):
                if similarity >= self.similarity_threshold:
                    promise = promises[i]
                    matches.append({
                        'promise_id': promise.get('promise_id'),
                        'promise_text': promise.get('text', promise.get('canonical_commitment_text', '')),
                        'promise_description': promise.get('description', ''),
                        'similarity_score': float(similarity),
                        'confidence': float(similarity),  # Use similarity as confidence
                        'match_type': 'semantic_similarity',
                        'promise': promise  # Keep full promise object for compatibility
                    })
            
            # Sort by similarity score (highest first)
            matches.sort(key=lambda x: x['similarity_score'], reverse=True)
            
            logger.info(f"Found {len(matches)} semantic matches above threshold {self.similarity_threshold}")
            
            # Log top matches for debugging
            for i, match in enumerate(matches[:5]):  # Top 5 matches
                promise_text = match['promise_text'][:100]
                logger.debug(f"Match {i+1}: {match['similarity_score']:.3f} - {promise_text}...")
            
            return matches
            
        except Exception as e:
            logger.error(f"Error finding semantic matches: {e}")
            return []
    
    async def create_evidence_promise_links(self, evidence_item: Dict[str, Any], 
                                          matches: List[Dict[str, Any]], dry_run: bool = False) -> int:
        """
        Create the actual evidence-promise links in the database.
        
        Args:
            evidence_item: The evidence item
            matches: List of match objects from semantic analysis
            dry_run: If True, don't write to database
            
        Returns:
            Number of links created
        """
        links_created = 0
        evidence_id = evidence_item.get('_doc_id')
        
        try:
            for match in matches:
                promise_id = match.get('promise_id')
                
                if not promise_id:
                    logger.warning("Match missing promise_id, skipping")
                    continue
                
                # Create link data structure
                link_data = {
                    'evidence_id': evidence_id,
                    'promise_id': promise_id,
                    'similarity_score': match['similarity_score'],
                    'confidence_score': match['confidence'],
                    'match_type': match['match_type'],
                    'linking_method': 'semantic_similarity',
                    'created_at': datetime.now(timezone.utc),
                    'parliament_session_id': evidence_item.get('parliament_session_id')
                }
                
                if dry_run:
                    logger.info(f"[DRY RUN] Would create semantic link: {evidence_id} -> {promise_id} "
                              f"(Similarity: {link_data['similarity_score']:.3f})")
                    links_created += 1
                else:
                    # Update promises collection: add evidence reference
                    promise_ref = db.collection(self.promises_collection).document(promise_id)
                    await asyncio.to_thread(
                        promise_ref.update,
                        {
                            'linked_evidence': firestore.ArrayUnion([{
                                'evidence_id': evidence_id,
                                'link_confidence': link_data['similarity_score'],
                                'link_type': 'semantic',
                                'linked_at': link_data['created_at']
                            }])
                        }
                    )
                    
                    # Update evidence_items collection: add promise reference
                    evidence_ref = db.collection(self.evidence_items_collection).document(evidence_id)
                    await asyncio.to_thread(
                        evidence_ref.update,
                        {
                            'promise_ids': firestore.ArrayUnion([{
                                'promise_id': promise_id,
                                'link_confidence': link_data['similarity_score'],
                                'link_type': 'semantic',
                                'linked_at': link_data['created_at']
                            }])
                        }
                    )
                    
                    logger.info(f"Created semantic link: {evidence_id} -> {promise_id} "
                              f"(Similarity: {link_data['similarity_score']:.3f})")
                    links_created += 1
        
        except Exception as e:
            logger.error(f"Error creating semantic links: {e}", exc_info=True)
            self.stats['errors'] += 1
        
        return links_created
    
    async def update_evidence_linking_status(self, evidence_id: str, links_count: int, dry_run: bool = False):
        """
        Update the evidence item's linking status.
        
        Args:
            evidence_id: Evidence item ID
            links_count: Number of links created
            dry_run: If True, don't write to database
        """
        try:
            status_data = {
                'promise_linking_status': 'processed',
                'promise_linking_processed_at': datetime.now(timezone.utc),
                'promise_links_found': links_count,
                'semantic_linking_method': 'sentence_transformers'
            }
            
            if dry_run:
                logger.info(f"[DRY RUN] Would update evidence {evidence_id} status: {links_count} semantic links found")
            else:
                evidence_ref = db.collection(self.evidence_items_collection).document(evidence_id)
                await asyncio.to_thread(evidence_ref.update, status_data)
                logger.info(f"Updated evidence {evidence_id} linking status: {links_count} semantic links found")
                
        except Exception as e:
            logger.error(f"Error updating evidence linking status: {e}")
    
    async def run_semantic_linking_test(self, parliament_session_id: str, evidence_id: str, 
                                      dry_run: bool = False) -> Dict[str, Any]:
        """
        Run the complete semantic evidence linking test.
        
        Args:
            parliament_session_id: Parliament session ID
            evidence_id: Evidence item ID to test
            dry_run: If True, don't write to database
            
        Returns:
            Test results and statistics including before/after state
        """
        start_time = time.time()
        
        logger.info("=== Starting Semantic Evidence Linking Test ===")
        logger.info(f"Parliament Session: {parliament_session_id}")
        logger.info(f"Evidence ID: {evidence_id}")
        logger.info(f"Dry Run: {dry_run}")
        logger.info(f"Collections: {self.promises_collection}, {self.evidence_items_collection}")
        logger.info(f"Similarity Threshold: {self.similarity_threshold}")
        
        if dry_run:
            logger.warning("*** DRY RUN MODE: No changes will be written to Firestore ***")
        
        try:
            # Step 1: Fetch target evidence item
            evidence_item = await self.fetch_target_evidence_item(evidence_id)
            if not evidence_item:
                return {
                    "error": "Evidence item not found", 
                    "stats": self.stats,
                    "processing_time_seconds": time.time() - start_time
                }
            
            # Capture before state
            before_promise_ids = evidence_item.get('promise_ids', [])
            before_linking_status = evidence_item.get('promise_linking_status', 'unknown')
            
            logger.info(f"Evidence Title: '{evidence_item.get('title_or_summary', 'No title')}'")
            logger.info(f"Evidence Source: {evidence_item.get('evidence_source_type', 'Unknown')}")
            logger.info(f"Evidence Date: {evidence_item.get('evidence_date', 'Unknown')}")
            logger.info(f"Before state - Promise IDs: {len(before_promise_ids)} links")
            logger.info(f"Before state - Linking Status: {before_linking_status}")
            
            # Step 2: Fetch all promises for the session
            promises = await self.fetch_promises_for_session(parliament_session_id)
            if not promises:
                return {
                    "error": "No promises found for session", 
                    "stats": self.stats,
                    "processing_time_seconds": time.time() - start_time
                }
            
            # Step 3: Generate embeddings
            logger.info("Generating semantic embeddings...")
            embedding_start_time = time.time()
            
            # Extract text for embeddings
            evidence_text = self.extract_text_for_embedding(evidence_item, 'evidence')
            promise_texts = [self.extract_text_for_embedding(promise, 'promise') for promise in promises]
            
            if not evidence_text.strip():
                return {
                    "error": "No extractable text from evidence item", 
                    "stats": self.stats,
                    "processing_time_seconds": time.time() - start_time
                }
            
            # Generate embeddings
            evidence_embedding = self.generate_embeddings([evidence_text])[0]
            promise_embeddings = self.generate_embeddings(promise_texts)
            
            embedding_time = time.time() - embedding_start_time
            logger.info(f"Embedding generation completed in {embedding_time:.2f} seconds")
            
            # Step 4: Find semantic matches
            logger.info("Finding semantic matches...")
            matches = self.find_semantic_matches(evidence_embedding, promise_embeddings, promises)
            
            # Calculate after state
            after_promise_ids = before_promise_ids.copy()
            new_promise_ids = []
            database_updates = []
            
            for match in matches:
                promise_id = match.get('promise_id')
                # Check if this promise is already linked (basic check)
                existing_ids = [link.get('promise_id', '') if isinstance(link, dict) else link 
                               for link in before_promise_ids]
                if promise_id not in existing_ids:
                    after_promise_ids.append(promise_id)
                    new_promise_ids.append(promise_id)
                    database_updates.append({
                        'promise_id': promise_id,
                        'action': 'added_to_evidence',
                        'similarity_score': match['similarity_score'],
                        'match_type': 'semantic'
                    })
            
            after_linking_status = 'processed'
            
            # Step 5: Create database links
            links_created = 0
            if matches:
                links_created = await self.create_evidence_promise_links(evidence_item, matches, dry_run)
                self.stats['links_created'] = links_created
                
                # Step 6: Update evidence linking status
                await self.update_evidence_linking_status(evidence_item['_doc_id'], links_created, dry_run)
            else:
                logger.info("No semantic matches found - updating evidence status with zero links")
                await self.update_evidence_linking_status(evidence_item['_doc_id'], 0, dry_run)
            
            self.stats['evidence_items_processed'] += 1
            
            processing_time = time.time() - start_time
            
            logger.info(f"After state - Promise IDs: {len(after_promise_ids)} links (+{len(new_promise_ids)} new)")
            logger.info(f"After state - Linking Status: {after_linking_status}")
            
            # Create debug output
            debug_data = {
                "input_evidence": evidence_item,
                "input_promises_sample": promises[:5],  # First 5 promises for debugging
                "total_promises_count": len(promises),
                "evidence_text_extracted": evidence_text,
                "semantic_matches": matches,
                "similarity_threshold": self.similarity_threshold,
                "processing_metadata": {
                    "embedding_generation_time": embedding_time,
                    "total_processing_time": processing_time,
                    "model_name": self.model.get_sentence_embedding_dimension(),
                    "timestamp": datetime.now(timezone.utc).isoformat()
                }
            }
            
            # Save debug data to JSON file
            debug_filename = f"debug_semantic_linking_{evidence_id}_{int(time.time())}.json"
            debug_filepath = Path("debug_output") / debug_filename
            debug_filepath.parent.mkdir(exist_ok=True)
            
            with open(debug_filepath, 'w') as f:
                json.dump(debug_data, f, indent=2, default=str)
            
            logger.info(f"Debug data saved to: {debug_filepath}")
            
            # Log final results
            logger.info("=== Semantic Evidence Linking Test Complete ===")
            logger.info(f"Evidence items processed: {self.stats['evidence_items_processed']}")
            logger.info(f"Promises fetched: {self.stats['promises_fetched']}")
            logger.info(f"Embeddings generated: {self.stats['embeddings_generated']}")
            logger.info(f"Similarities calculated: {self.stats['similarities_calculated']}")
            logger.info(f"Links created: {self.stats['links_created']}")
            logger.info(f"Errors: {self.stats['errors']}")
            logger.info(f"Total processing time: {processing_time:.2f} seconds")
            
            result = {
                "success": True, 
                "evidence_id": evidence_id,
                "evidence_title": evidence_item.get('title_or_summary', 'No title'),
                "evidence_source_type": evidence_item.get('evidence_source_type', 'Unknown'),
                "evidence_date": evidence_item.get('evidence_date', 'Unknown'),
                "before_state": {
                    "promise_ids": before_promise_ids,
                    "promise_count": len(before_promise_ids),
                    "linking_status": before_linking_status
                },
                "after_state": {
                    "promise_ids": after_promise_ids,
                    "promise_count": len(after_promise_ids),
                    "linking_status": after_linking_status
                },
                "changes": {
                    "new_promise_ids": new_promise_ids,
                    "new_links_count": len(new_promise_ids),
                    "database_updates": database_updates
                },
                "semantic_analysis": {
                    "matches_found": matches,
                    "matches_count": len(matches),
                    "similarity_threshold": self.similarity_threshold,
                    "embedding_generation_time": embedding_time
                },
                "stats": self.stats, 
                "links_created": links_created,
                "processing_time_seconds": processing_time,
                "dry_run": dry_run,
                "debug_file": str(debug_filepath)
            }
            
            # Also save the main result
            result_filename = f"result_semantic_linking_{evidence_id}_{int(time.time())}.json"
            result_filepath = Path("debug_output") / result_filename
            
            with open(result_filepath, 'w') as f:
                json.dump(result, f, indent=2, default=str)
            
            logger.info(f"Results saved to: {result_filepath}")
            
            return result
            
        except Exception as e:
            logger.error(f"Error in semantic linking test: {e}", exc_info=True)
            self.stats['errors'] += 1
            return {
                "error": str(e), 
                "stats": self.stats,
                "processing_time_seconds": time.time() - start_time
            }
    
    async def run_batch_semantic_linking_test(self, parliament_session_id: str, limit: Optional[int] = None, 
                                            dry_run: bool = False) -> Dict[str, Any]:
        """
        Run semantic evidence linking test on multiple evidence items.
        
        Args:
            parliament_session_id: Parliament session ID
            limit: Maximum number of evidence items to process
            dry_run: If True, don't write to database
            
        Returns:
            Test results and statistics
        """
        start_time = time.time()
        
        logger.info("=== Starting Batch Semantic Evidence Linking Test ===")
        logger.info(f"Parliament Session: {parliament_session_id}")
        logger.info(f"Limit: {limit or 'No limit'}")
        logger.info(f"Dry Run: {dry_run}")
        logger.info(f"Collections: {self.promises_collection}, {self.evidence_items_collection}")
        logger.info(f"Similarity Threshold: {self.similarity_threshold}")
        
        if dry_run:
            logger.warning("*** DRY RUN MODE: No changes will be written to Firestore ***")
        
        try:
            # Step 1: Fetch evidence items for processing
            evidence_items = await self.fetch_evidence_items_for_processing(parliament_session_id, limit)
            if not evidence_items:
                return {"error": "No evidence items found for processing", "stats": self.stats}
            
            # Step 2: Fetch all promises for the session (once)
            promises = await self.fetch_promises_for_session(parliament_session_id)
            if not promises:
                return {"error": "No promises found for session", "stats": self.stats}
            
            # Step 3: Pre-generate promise embeddings (efficiency optimization)
            logger.info("Pre-generating promise embeddings for batch processing...")
            promise_texts = [self.extract_text_for_embedding(promise, 'promise') for promise in promises]
            promise_embeddings = self.generate_embeddings(promise_texts)
            
            logger.info(f"Processing {len(evidence_items)} evidence items against {len(promises)} promises")
            
            # Step 4: Process each evidence item and collect detailed results
            total_links_created = 0
            detailed_results = []
            
            for i, evidence_item in enumerate(evidence_items, 1):
                evidence_id = evidence_item.get('_doc_id')
                logger.info(f"Processing evidence item {i}/{len(evidence_items)}: {evidence_id}")
                
                # Initialize result for this evidence item
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
                }
                
                try:
                    # Extract evidence text and generate embedding
                    evidence_text = self.extract_text_for_embedding(evidence_item, 'evidence')
                    if not evidence_text.strip():
                        logger.warning(f"No extractable text from evidence {evidence_id}, skipping")
                        evidence_result["error"] = "No extractable text"
                        detailed_results.append(evidence_result)
                        continue
                    
                    evidence_embedding = self.generate_embeddings([evidence_text])[0]
                    
                    # Find semantic matches
                    matches = self.find_semantic_matches(evidence_embedding, promise_embeddings, promises)
                    evidence_result["semantic_matches"] = matches
                    logger.info(f"Found {len(matches)} semantic matches for evidence {evidence_id}")
                    
                    # Create database links
                    if matches:
                        links_created = await self.create_evidence_promise_links(evidence_item, matches, dry_run)
                        evidence_result["links_created"] = links_created
                        total_links_created += links_created
                        
                        # Update evidence linking status
                        await self.update_evidence_linking_status(evidence_id, links_created, dry_run)
                    else:
                        logger.info(f"No semantic matches found for evidence {evidence_id} - updating status with zero links")
                        await self.update_evidence_linking_status(evidence_id, 0, dry_run)
                    
                    evidence_result["processing_success"] = True
                    self.stats['evidence_items_processed'] += 1
                    
                    # Rate limiting
                    if i < len(evidence_items):  # Don't sleep after the last item
                        await asyncio.sleep(RATE_LIMIT_DELAY_SECONDS)
                        
                except Exception as e:
                    logger.error(f"Error processing evidence item {evidence_id}: {e}", exc_info=True)
                    evidence_result["error"] = str(e)
                    self.stats['errors'] += 1
                
                detailed_results.append(evidence_result)
            
            self.stats['links_created'] = total_links_created
            processing_time = time.time() - start_time
            
            # Create comprehensive batch results
            batch_results = {
                "success": True,
                "parliament_session_id": parliament_session_id,
                "processing_metadata": {
                    "limit": limit,
                    "dry_run": dry_run,
                    "similarity_threshold": self.similarity_threshold,
                    "total_processing_time": processing_time,
                    "model_name": self.model.get_sentence_embedding_dimension(),
                    "timestamp": datetime.now(timezone.utc).isoformat()
                },
                "summary": {
                    "evidence_items_processed": self.stats['evidence_items_processed'],
                    "promises_fetched": self.stats['promises_fetched'],
                    "total_semantic_links_created": self.stats['links_created'],
                    "embeddings_generated": self.stats['embeddings_generated'],
                    "similarities_calculated": self.stats['similarities_calculated'],
                    "errors": self.stats['errors']
                },
                "detailed_results": detailed_results,
                "stats": self.stats
            }
            
            # Save comprehensive batch results to JSON files
            timestamp = int(time.time())
            
            # Main results file
            batch_result_filename = f"batch_semantic_linking_session_{parliament_session_id}_limit_{limit or 'all'}_{timestamp}.json"
            batch_result_filepath = Path("debug_output") / batch_result_filename
            batch_result_filepath.parent.mkdir(exist_ok=True)
            
            with open(batch_result_filepath, 'w') as f:
                json.dump(batch_results, f, indent=2, default=str)
            
            logger.info(f"Batch results saved to: {batch_result_filepath}")
            
            # Also create a summary-only file for quick overview
            summary_filename = f"batch_summary_session_{parliament_session_id}_limit_{limit or 'all'}_{timestamp}.json"
            summary_filepath = Path("debug_output") / summary_filename
            
            summary_data = {
                "processing_summary": batch_results["summary"],
                "processing_metadata": batch_results["processing_metadata"],
                "evidence_overview": [
                    {
                        "evidence_id": result["evidence_id"],
                        "evidence_title": result["evidence_title"],
                        "matches_found": len(result["semantic_matches"]),
                        "links_created": result["links_created"],
                        "processing_success": result["processing_success"],
                        "top_match": result["semantic_matches"][0] if result["semantic_matches"] else None
                    }
                    for result in detailed_results
                ]
            }
            
            with open(summary_filepath, 'w') as f:
                json.dump(summary_data, f, indent=2, default=str)
            
            logger.info(f"Batch summary saved to: {summary_filepath}")
            
            # Log final results
            logger.info("=== Batch Semantic Evidence Linking Test Complete ===")
            logger.info(f"Evidence items processed: {self.stats['evidence_items_processed']}")
            logger.info(f"Promises fetched: {self.stats['promises_fetched']}")
            logger.info(f"Total semantic links created: {self.stats['links_created']}")
            logger.info(f"Embeddings generated: {self.stats['embeddings_generated']}")
            logger.info(f"Similarities calculated: {self.stats['similarities_calculated']}")
            logger.info(f"Errors: {self.stats['errors']}")
            logger.info(f"Total processing time: {processing_time:.2f} seconds")
            
            # Add file paths to return data
            batch_results["debug_files"] = {
                "batch_results": str(batch_result_filepath),
                "batch_summary": str(summary_filepath)
            }
            
            return batch_results
            
        except Exception as e:
            logger.error(f"Error in batch semantic linking test: {e}", exc_info=True)
            self.stats['errors'] += 1
            return {"error": str(e), "stats": self.stats}


async def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(description='Semantic Evidence Linking Test')
    parser.add_argument(
        '--parliament_session_id',
        type=str,
        required=True,
        help='Parliament session ID (e.g., "44")'
    )
    parser.add_argument(
        '--evidence_id_to_test',
        type=str,
        help='Specific evidence ID to test linking for (if not provided, will process pending items)'
    )
    parser.add_argument(
        '--limit',
        type=int,
        help='Maximum number of evidence items to process (for batch mode)'
    )
    parser.add_argument(
        '--dry_run',
        action='store_true',
        help='Run without making changes to Firestore'
    )
    parser.add_argument(
        '--log_level',
        choices=['DEBUG', 'INFO', 'WARNING', 'ERROR'],
        default='INFO',
        help='Set logging level'
    )
    parser.add_argument(
        '--use_production',
        action='store_true',
        help='Use production collections instead of test collections'
    )
    parser.add_argument(
        '--similarity_threshold',
        type=float,
        default=DEFAULT_SIMILARITY_THRESHOLD,
        help=f'Minimum similarity score for linking (default: {DEFAULT_SIMILARITY_THRESHOLD})'
    )
    parser.add_argument(
        '--model_name',
        type=str,
        default=DEFAULT_MODEL_NAME,
        help=f'Sentence transformer model name (default: {DEFAULT_MODEL_NAME})'
    )
    
    args = parser.parse_args()
    
    # Set logging level
    logging.getLogger().setLevel(getattr(logging, args.log_level))
    
    # Initialize tester
    tester = SemanticEvidenceLinkingTester(
        use_test_collections=not args.use_production,
        model_name=args.model_name
    )
    
    # Set similarity threshold
    tester.similarity_threshold = args.similarity_threshold
    
    # Run the linking test
    if args.evidence_id_to_test:
        # Single evidence item mode
        result = await tester.run_semantic_linking_test(
            parliament_session_id=args.parliament_session_id,
            evidence_id=args.evidence_id_to_test,
            dry_run=args.dry_run
        )
    else:
        # Batch processing mode
        result = await tester.run_batch_semantic_linking_test(
            parliament_session_id=args.parliament_session_id,
            limit=args.limit,
            dry_run=args.dry_run
        )
    
    if "error" in result:
        logger.error(f"Test failed: {result['error']}")
    else:
        logger.info("Test completed successfully!")


if __name__ == "__main__":
    asyncio.run(main()) 