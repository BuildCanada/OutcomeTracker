#!/usr/bin/env python3
"""
Semantic vs Existing Matching Comparison Script

Compare existing promise links with new semantic matches for evidence items.
Outputs results to CSV for manual inspection and quality assessment.

Usage:
    python semantic_comparison_analysis.py --parliament_session_id 44 --limit 100 --similarity_threshold 0.4
"""

import firebase_admin
from firebase_admin import firestore, credentials
import os
import sys
import asyncio
import logging
import traceback
from dotenv import load_dotenv
import csv
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
logger = logging.getLogger("semantic_comparison")

# Try to import sentence transformers
try:
    from sentence_transformers import SentenceTransformer
    from sklearn.metrics.pairwise import cosine_similarity
    logger.info("Successfully imported sentence transformers and sklearn")
except ImportError as e:
    logger.error(f"Failed to import required packages: {e}")
    logger.error("Please install: pip install sentence-transformers scikit-learn")
    sys.exit(1)

# Firebase Configuration (same as other scripts)
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
                app_name = 'semantic_comparison_app'
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

# Constants
DEFAULT_MODEL_NAME = 'all-MiniLM-L6-v2'
DEFAULT_SIMILARITY_THRESHOLD = 0.55  # Updated based on analysis results

class SemanticComparisonAnalyzer:
    """Compares existing vs semantic evidence-promise linking for analysis."""
    
    def __init__(self, use_test_collections: bool = True, model_name: str = DEFAULT_MODEL_NAME):
        """Initialize the analyzer."""
        
        # Load sentence transformer model
        logger.info(f"Loading sentence transformer model: {model_name}")
        start_time = time.time()
        self.model = SentenceTransformer(model_name)
        load_time = time.time() - start_time
        logger.info(f"Model loaded in {load_time:.2f} seconds")
        
        self.use_test_collections = use_test_collections
        
        # Set collection names
        if use_test_collections:
            self.promises_collection = 'promises_test'
            self.evidence_items_collection = 'evidence_items_test'
            logger.info("Using TEST collections for safe analysis")
        else:
            self.promises_collection = 'promises'
            self.evidence_items_collection = 'evidence_items'
            logger.warning("Using PRODUCTION collections")
        
        self.similarity_threshold = DEFAULT_SIMILARITY_THRESHOLD
    
    def extract_text_for_embedding(self, item: Dict[str, Any], item_type: str = 'evidence') -> str:
        """Extract text for embedding generation with simplified field selection."""
        text_parts = []
        
        if item_type == 'evidence':
            # Primary content fields (corrected based on processing scripts)
            value = item.get('title_or_summary', '')
            if value and isinstance(value, str) and value.strip():
                text_parts.append(value.strip())
            
            value = item.get('description_or_details', '')
            if value and isinstance(value, str) and value.strip():
                text_parts.append(value.strip())
            
            # Key concepts for better semantic matching
            key_concepts = item.get('key_concepts', [])
            if isinstance(key_concepts, list):
                for concept in key_concepts:
                    if isinstance(concept, str) and concept.strip():
                        text_parts.append(concept.strip())
            
            # Linked departments for context
            linked_depts = item.get('linked_departments', [])
            if isinstance(linked_depts, list):
                for dept in linked_depts:
                    if isinstance(dept, str) and dept.strip():
                        text_parts.append(f"Department: {dept.strip()}")
        
        elif item_type == 'promise':
            # Primary content fields
            value = item.get('text', '')
            if value and isinstance(value, str) and value.strip():
                text_parts.append(value.strip())
            
            value = item.get('description', '')
            if value and isinstance(value, str) and value.strip():
                text_parts.append(value.strip())
            
            value = item.get('background_and_context', '')
            if value and isinstance(value, str) and value.strip():
                text_parts.append(value.strip())
            
            # Impact and objectives for better semantic matching
            impacts = item.get('intended_impact_and_objectives', [])
            if isinstance(impacts, list):
                for impact in impacts:
                    if isinstance(impact, str) and impact.strip():
                        text_parts.append(impact.strip())
            
            # Responsible department for context
            dept_lead = item.get('responsible_department_lead', '')
            if dept_lead and isinstance(dept_lead, str) and dept_lead.strip():
                text_parts.append(f"Department lead: {dept_lead.strip()}")
        
        # Combine all text parts
        combined_text = ' '.join(text_parts)
        combined_text = ' '.join(combined_text.split())  # Remove extra whitespace
        
        return combined_text[:1000]  # Keep reasonable limit
    
    async def fetch_evidence_items_for_comparison(self, parliament_session_id: str, limit: int) -> List[Dict[str, Any]]:
        """Fetch evidence items that have existing promise links for comparison."""
        try:
            logger.info(f"Fetching {limit} evidence items for comparison from {self.evidence_items_collection}")
            
            # Query evidence items that have promise_ids (existing links)
            query = db.collection(self.evidence_items_collection).where(
                filter=firestore.FieldFilter("parliament_session_id", "==", parliament_session_id)
            ).limit(limit * 2)  # Get more to filter for ones with existing links
            
            evidence_docs = await asyncio.to_thread(list, query.stream())
            
            evidence_items = []
            for doc in evidence_docs:
                data = doc.to_dict()
                if data and data.get('promise_ids') and len(data.get('promise_ids', [])) > 0:
                    data['_doc_id'] = doc.id
                    evidence_items.append(data)
                    
                    if len(evidence_items) >= limit:
                        break
            
            logger.info(f"Found {len(evidence_items)} evidence items with existing promise links")
            return evidence_items
            
        except Exception as e:
            logger.error(f"Error fetching evidence items: {e}", exc_info=True)
            return []
    
    async def fetch_all_promises(self, parliament_session_id: str) -> Dict[str, Dict[str, Any]]:
        """Fetch all promises and return as a lookup dictionary keyed by document ID."""
        try:
            logger.info(f"Fetching all promises for session {parliament_session_id}")
            
            query = db.collection(self.promises_collection).where(
                filter=firestore.FieldFilter("parliament_session_id", "==", parliament_session_id)
            )
            
            promise_docs = await asyncio.to_thread(list, query.stream())
            
            promises_lookup = {}
            for doc in promise_docs:
                data = doc.to_dict()
                if data:
                    # Use document ID as key, not the promise_id field
                    doc_id = doc.id
                    data['_doc_id'] = doc_id  # Store doc ID in the data for reference
                    promises_lookup[doc_id] = data
            
            logger.info(f"Successfully fetched {len(promises_lookup)} promises")
            return promises_lookup
            
        except Exception as e:
            logger.error(f"Error fetching promises: {e}", exc_info=True)
            return {}
    
    def generate_embeddings(self, texts: List[str]) -> np.ndarray:
        """Generate embeddings for texts with validation."""
        try:
            if not texts:
                return np.array([])
            
            # Filter out empty texts and replace with minimal content
            processed_texts = []
            for text in texts:
                if text and text.strip():
                    processed_texts.append(text.strip())
                else:
                    # Use minimal placeholder for empty texts to avoid zero embeddings
                    processed_texts.append("no content available")
            
            embeddings = self.model.encode(processed_texts, batch_size=32, show_progress_bar=False)
            
            # Validate embeddings and handle edge cases
            if embeddings.size > 0:
                # Check for NaN or infinity values
                if np.any(np.isnan(embeddings)) or np.any(np.isinf(embeddings)):
                    logger.warning("Found NaN or infinity values in embeddings, replacing with zeros")
                    embeddings = np.nan_to_num(embeddings, nan=0.0, posinf=0.0, neginf=0.0)
                
                # Check for zero magnitude vectors
                norms = np.linalg.norm(embeddings, axis=1)
                zero_norm_indices = np.where(norms == 0)[0]
                if len(zero_norm_indices) > 0:
                    logger.warning(f"Found {len(zero_norm_indices)} zero magnitude vectors, adding small random values")
                    # Add small random values to prevent zero magnitude
                    for idx in zero_norm_indices:
                        embeddings[idx] = np.random.normal(0, 1e-8, embeddings.shape[1])
            
            return embeddings
            
        except Exception as e:
            logger.error(f"Error generating embeddings: {e}")
            return np.array([])
    
    def safe_cosine_similarity(self, vec1: np.ndarray, vec2: np.ndarray) -> float:
        """Calculate cosine similarity with proper error handling."""
        try:
            # Ensure vectors are not zero magnitude
            norm1 = np.linalg.norm(vec1)
            norm2 = np.linalg.norm(vec2)
            
            if norm1 == 0 or norm2 == 0:
                return 0.0
            
            # Calculate dot product
            dot_product = np.dot(vec1, vec2)
            
            # Check for overflow/underflow
            if np.isnan(dot_product) or np.isinf(dot_product):
                return 0.0
            
            # Calculate cosine similarity
            similarity = dot_product / (norm1 * norm2)
            
            # Ensure result is valid and within expected range
            if np.isnan(similarity) or np.isinf(similarity):
                return 0.0
            
            # Clamp to valid range [-1, 1]
            return float(np.clip(similarity, -1.0, 1.0))
            
        except Exception as e:
            logger.warning(f"Error in cosine similarity calculation: {e}")
            return 0.0
    
    def find_semantic_matches(self, evidence_embedding: np.ndarray, promise_embeddings: np.ndarray, 
                             promise_list: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Find semantic matches for evidence with safe similarity calculations."""
        try:
            if evidence_embedding.size == 0 or promise_embeddings.size == 0:
                return []
            
            # Validate evidence embedding
            if np.linalg.norm(evidence_embedding) == 0:
                logger.warning("Evidence embedding has zero magnitude, skipping")
                return []
            
            matches = []
            
            # Calculate similarities one by one to handle errors gracefully
            for i, promise_embedding in enumerate(promise_embeddings):
                try:
                    similarity = self.safe_cosine_similarity(evidence_embedding, promise_embedding)
                    
                    if similarity >= self.similarity_threshold:
                        promise = promise_list[i]
                        # Use document ID instead of promise_id field
                        doc_id = promise.get('_doc_id', '')
                        promise_text = promise.get('text', promise.get('canonical_commitment_text', ''))
                        
                        matches.append({
                            'promise_id': doc_id,  # This is actually the document ID
                            'promise_text': promise_text,
                            'similarity_score': similarity
                        })
                        
                except Exception as e:
                    logger.warning(f"Error calculating similarity for promise {i}: {e}")
                    continue
            
            # Sort by similarity score (highest first)
            matches.sort(key=lambda x: x['similarity_score'], reverse=True)
            
            return matches
            
        except Exception as e:
            logger.error(f"Error finding semantic matches: {e}")
            return []
    
    def extract_promise_ids_and_text(self, promise_ids_field: List, promises_lookup: Dict[str, Dict[str, Any]]) -> List[Dict[str, str]]:
        """Extract promise IDs and text from the promise_ids field."""
        results = []
        
        if not promise_ids_field:
            return results
        
        for item in promise_ids_field:
            promise_id = None
            
            # Handle different formats of promise_ids field
            if isinstance(item, dict):
                # If it's a dict, look for promise_id key
                promise_id = item.get('promise_id')
            elif isinstance(item, str):
                # If it's a string, it's directly the promise_id
                promise_id = item
            else:
                continue
            
            # Look up the promise data
            if promise_id and promise_id in promises_lookup:
                promise_data = promises_lookup[promise_id]
                promise_text = promise_data.get('text', promise_data.get('canonical_commitment_text', ''))
                results.append({
                    'promise_id': promise_id,
                    'promise_text': promise_text
                })
            elif promise_id:
                # Promise ID exists but not found in lookup - add with placeholder
                results.append({
                    'promise_id': promise_id,
                    'promise_text': '[Promise not found in lookup]'
                })
        
        return results
    
    async def run_comparison_analysis(self, parliament_session_id: str, limit: int, similarity_threshold: float) -> str:
        """Run the complete comparison analysis and return CSV file path."""
        
        self.similarity_threshold = similarity_threshold
        
        logger.info("=== Starting Semantic vs Existing Comparison Analysis ===")
        logger.info(f"Parliament Session: {parliament_session_id}")
        logger.info(f"Evidence Items to Analyze: {limit}")
        logger.info(f"Similarity Threshold: {similarity_threshold}")
        logger.info(f"Collections: {self.promises_collection}, {self.evidence_items_collection}")
        
        try:
            # Step 1: Fetch evidence items with existing links
            evidence_items = await self.fetch_evidence_items_for_comparison(parliament_session_id, limit)
            if not evidence_items:
                raise Exception("No evidence items with existing links found")
            
            # Step 2: Fetch all promises
            promises_lookup = await self.fetch_all_promises(parliament_session_id)
            if not promises_lookup:
                raise Exception("No promises found")
            
            # Step 3: Prepare promise data for semantic analysis
            promise_list = list(promises_lookup.values())
            promise_texts = [self.extract_text_for_embedding(promise, 'promise') for promise in promise_list]
            promise_embeddings = self.generate_embeddings(promise_texts)
            
            logger.info(f"Generated embeddings for {len(promise_list)} promises")
            
            # Step 4: Process each evidence item
            comparison_results = []
            
            for i, evidence_item in enumerate(evidence_items, 1):
                evidence_id = evidence_item.get('_doc_id')
                logger.info(f"Processing evidence {i}/{len(evidence_items)}: {evidence_id}")
                
                try:
                    # Get existing promise links
                    existing_promise_ids = evidence_item.get('promise_ids', [])
                    existing_promises = self.extract_promise_ids_and_text(existing_promise_ids, promises_lookup)
                    
                    # Generate semantic matches
                    evidence_text = self.extract_text_for_embedding(evidence_item, 'evidence')
                    if evidence_text.strip():
                        evidence_embedding = self.generate_embeddings([evidence_text])
                        if evidence_embedding.size > 0:
                            semantic_matches = self.find_semantic_matches(
                                evidence_embedding[0], promise_embeddings, promise_list
                            )
                        else:
                            semantic_matches = []
                    else:
                        semantic_matches = []
                    
                    # Prepare row data
                    row_data = {
                        'evidence_id': evidence_id,
                        'evidence_title': evidence_item.get('title_or_summary', 'No title')[:200],
                        'evidence_source': evidence_item.get('evidence_source_type', 'Unknown'),
                        'evidence_date': str(evidence_item.get('evidence_date', 'Unknown')),
                        
                        # Existing matches
                        'existing_count': len(existing_promises),
                        'existing_promise_ids': ' | '.join([p['promise_id'] for p in existing_promises]),
                        'existing_promise_texts': ' | '.join([p['promise_text'][:100] + '...' if len(p['promise_text']) > 100 else p['promise_text'] for p in existing_promises]),
                        
                        # Semantic matches
                        'semantic_count': len(semantic_matches),
                        'semantic_promise_ids': ' | '.join([m['promise_id'] for m in semantic_matches[:10]]),  # Top 10
                        'semantic_promise_texts': ' | '.join([m['promise_text'][:100] + '...' if len(m['promise_text']) > 100 else m['promise_text'] for m in semantic_matches[:10]]),
                        'semantic_scores': ' | '.join([f"{m['similarity_score']:.3f}" for m in semantic_matches[:10]]),
                        
                        # Overlap analysis
                        'overlap_count': len(set([p['promise_id'] for p in existing_promises]) & 
                                            set([m['promise_id'] for m in semantic_matches])),
                        'new_semantic_count': len(set([m['promise_id'] for m in semantic_matches]) - 
                                                 set([p['promise_id'] for p in existing_promises])),
                        'lost_existing_count': len(set([p['promise_id'] for p in existing_promises]) - 
                                                  set([m['promise_id'] for m in semantic_matches]))
                    }
                    
                    comparison_results.append(row_data)
                    
                except Exception as e:
                    logger.error(f"Error processing evidence {evidence_id}: {e}")
                    continue
            
            # Step 5: Write to CSV
            timestamp = int(time.time())
            csv_filename = f"semantic_comparison_session_{parliament_session_id}_limit_{limit}_threshold_{similarity_threshold}_{timestamp}.csv"
            csv_filepath = Path("debug_output") / csv_filename
            csv_filepath.parent.mkdir(exist_ok=True)
            
            fieldnames = [
                'evidence_id', 'evidence_title', 'evidence_source', 'evidence_date',
                'existing_count', 'existing_promise_ids', 'existing_promise_texts',
                'semantic_count', 'semantic_promise_ids', 'semantic_promise_texts', 'semantic_scores',
                'overlap_count', 'new_semantic_count', 'lost_existing_count'
            ]
            
            with open(csv_filepath, 'w', newline='', encoding='utf-8') as csvfile:
                writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
                writer.writeheader()
                writer.writerows(comparison_results)
            
            logger.info(f"Comparison analysis complete! Results saved to: {csv_filepath}")
            
            # Log summary statistics
            total_existing = sum(row['existing_count'] for row in comparison_results)
            total_semantic = sum(row['semantic_count'] for row in comparison_results)
            total_overlap = sum(row['overlap_count'] for row in comparison_results)
            total_new = sum(row['new_semantic_count'] for row in comparison_results)
            total_lost = sum(row['lost_existing_count'] for row in comparison_results)
            
            logger.info("=== SUMMARY STATISTICS ===")
            logger.info(f"Evidence items analyzed: {len(comparison_results)}")
            logger.info(f"Total existing links: {total_existing}")
            logger.info(f"Total semantic links: {total_semantic}")
            logger.info(f"Total overlapping links: {total_overlap}")
            logger.info(f"New semantic links: {total_new}")
            logger.info(f"Lost existing links: {total_lost}")
            logger.info(f"Overlap rate: {(total_overlap / max(total_existing, 1)):.1%}")
            
            return str(csv_filepath)
            
        except Exception as e:
            logger.error(f"Error in comparison analysis: {e}", exc_info=True)
            raise


async def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(description='Semantic vs Existing Matching Comparison Analysis')
    parser.add_argument(
        '--parliament_session_id',
        type=str,
        required=True,
        help='Parliament session ID (e.g., "44")'
    )
    parser.add_argument(
        '--limit',
        type=int,
        default=100,
        help='Number of evidence items to analyze (default: 100)'
    )
    parser.add_argument(
        '--similarity_threshold',
        type=float,
        default=DEFAULT_SIMILARITY_THRESHOLD,
        help=f'Similarity threshold for semantic matching (default: {DEFAULT_SIMILARITY_THRESHOLD})'
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
    
    # Initialize analyzer
    analyzer = SemanticComparisonAnalyzer(
        use_test_collections=not args.use_production
    )
    
    try:
        # Run comparison analysis
        csv_file = await analyzer.run_comparison_analysis(
            parliament_session_id=args.parliament_session_id,
            limit=args.limit,
            similarity_threshold=args.similarity_threshold
        )
        
        print(f"\n✅ SUCCESS! Comparison analysis complete!")
        print(f"📊 Results saved to: {csv_file}")
        print(f"\nOpen the CSV file to inspect the comparison between existing and semantic matches.")
        
    except Exception as e:
        logger.error(f"Analysis failed: {e}")
        print(f"\n❌ FAILED: {e}")


if __name__ == "__main__":
    asyncio.run(main()) 