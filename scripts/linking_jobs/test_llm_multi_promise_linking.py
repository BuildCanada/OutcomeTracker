#!/usr/bin/env python3
"""
LLM Multi-Promise Evidence Linking Test Script

Test script for evaluating LLM-first approach to linking evidence items to promises.
Uses large-context LLM calls to identify semantic relationships between a single evidence
item and multiple promises simultaneously.

Usage:
    python test_llm_multi_promise_linking.py --parliament_session_id 44 --evidence_id_to_test <evidence_id> [options]
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

# Add parent directory to path to import langchain_config
sys.path.append(str(Path(__file__).parent.parent.parent / 'lib'))

try:
    from langchain_config import get_langchain_instance
except ImportError as e:
    logging.error(f"Failed to import langchain_config: {e}")
    sys.exit("Please ensure langchain_config.py is available in the lib directory")

# Load environment variables
load_dotenv()

# Logger setup
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(filename)s:%(lineno)d - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger("llm_evidence_linking")

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
                app_name = 'llm_evidence_linking_app'
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
# Collection names - test vs production mode
PROMISES_COLLECTION_TEST = 'promises_test'
PROMISES_COLLECTION_PROD = 'promises'
EVIDENCE_ITEMS_COLLECTION_TEST = 'evidence_items_test'
EVIDENCE_ITEMS_COLLECTION_PROD = 'evidence_items'

# Rate limiting
RATE_LIMIT_DELAY_SECONDS = 2


class LLMEvidenceLinkingTester:
    """Handles LLM-based evidence linking testing and evaluation."""
    
    def __init__(self, use_test_collections: bool = True):
        """Initialize the tester with Langchain instance and collection settings."""
        self.langchain = get_langchain_instance()
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
        
        self.stats = {
            'evidence_items_processed': 0,
            'promises_fetched': 0,
            'links_created': 0,
            'llm_calls_made': 0,
            'errors': 0
        }
    
    async def update_test_evidence_linking_status(self, parliament_session_id: str) -> bool:
        """
        Update all evidence items in test collection to have promise_linking_status = 'pending'.
        
        Args:
            parliament_session_id: Parliament session to update evidence for
            
        Returns:
            True if successful, False otherwise
        """
        try:
            logger.info(f"Updating all evidence items in {self.evidence_items_collection} to promise_linking_status = 'pending'")
            
            # Query all evidence items for the session
            query = db.collection(self.evidence_items_collection).where(
                filter=firestore.FieldFilter("parliament_session_id", "==", parliament_session_id)
            )
            
            evidence_docs = await asyncio.to_thread(list, query.stream())
            
            update_count = 0
            for doc in evidence_docs:
                try:
                    await asyncio.to_thread(
                        doc.reference.update,
                        {
                            'promise_linking_status': 'pending',
                            'promise_linking_status_updated_at': datetime.now(timezone.utc)
                        }
                    )
                    update_count += 1
                except Exception as e:
                    logger.warning(f"Failed to update evidence item {doc.id}: {e}")
            
            logger.info(f"Updated {update_count} evidence items to promise_linking_status = 'pending'")
            return True
            
        except Exception as e:
            logger.error(f"Error updating evidence linking status: {e}", exc_info=True)
            return False
    
    async def fetch_evidence_items_for_processing(self, parliament_session_id: str, limit: Optional[int] = None) -> List[Dict[str, Any]]:
        """
        Fetch evidence items that need promise linking processing.
        
        Args:
            parliament_session_id: Parliament session to fetch evidence for
            limit: Maximum number of evidence items to fetch
            
        Returns:
            List of evidence items ready for processing
        """
        try:
            logger.info(f"Fetching evidence items for processing from {self.evidence_items_collection}")
            
            # Query evidence items that need processing
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
            
            # Extract required fields
            required_fields = ['evidence_source_type', 'parliament_session_id']
            for field in required_fields:
                if field not in evidence_data:
                    logger.warning(f"Evidence item {evidence_id} missing required field: {field}")
            
            logger.info(f"Successfully fetched evidence item: {evidence_id}")
            logger.debug(f"Evidence type: {evidence_data.get('evidence_source_type', 'Unknown')}")
            logger.debug(f"Parliament session: {evidence_data.get('parliament_session_id', 'Unknown')}")
            
            return evidence_data
            
        except Exception as e:
            logger.error(f"Error fetching evidence item {evidence_id}: {e}", exc_info=True)
            return None
    
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
                    # Extract required fields for linking
                    promise_summary = {
                        'promise_id': doc.id,
                        'text': data.get('text', data.get('canonical_commitment_text', '')),
                        'description': data.get('description', ''),
                        'background_and_context': data.get('background_and_context', ''),
                        'reporting_lead_title': data.get('reporting_lead_title', ''),
                        'relevant_departments': data.get('relevant_departments', []),
                        'commitment_history_rationale': data.get('commitment_history_rationale', []),
                        'what_it_means_for_canadians': data.get('what_it_means_for_canadians', []),
                        'extracted_keywords_concepts': data.get('extracted_keywords_concepts', []),
                        'policy_areas': data.get('policy_areas', [])
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
    
    async def create_test_collections(self, parliament_session_id: str) -> bool:
        """
        Create test collections by copying from production collections.
        
        Args:
            parliament_session_id: Session to copy data for
            
        Returns:
            True if successful, False otherwise
        """
        try:
            logger.info(f"Creating test collections for session {parliament_session_id}")
            
            # Copy promises
            logger.info("Copying promises to test collection...")
            promises_query = db.collection(PROMISES_COLLECTION_PROD).where(
                filter=firestore.FieldFilter("parliament_session_id", "==", parliament_session_id)
            )
            
            promise_count = 0
            for doc in promises_query.stream():
                await asyncio.to_thread(
                    db.collection(PROMISES_COLLECTION_TEST).document(doc.id).set,
                    doc.to_dict()
                )
                promise_count += 1
            
            logger.info(f"Copied {promise_count} promises to {PROMISES_COLLECTION_TEST}")
            
            # Copy evidence items
            logger.info("Copying evidence items to test collection...")
            evidence_query = db.collection(EVIDENCE_ITEMS_COLLECTION_PROD).where(
                filter=firestore.FieldFilter("parliament_session_id", "==", parliament_session_id)
            )
            
            evidence_count = 0
            for doc in evidence_query.stream():
                await asyncio.to_thread(
                    db.collection(EVIDENCE_ITEMS_COLLECTION_TEST).document(doc.id).set,
                    doc.to_dict()
                )
                evidence_count += 1
            
            logger.info(f"Copied {evidence_count} evidence items to {EVIDENCE_ITEMS_COLLECTION_TEST}")
            logger.info("Test collections created successfully")
            
            return True
            
        except Exception as e:
            logger.error(f"Error creating test collections: {e}", exc_info=True)
            return False
    
    def construct_llm_prompt(self, evidence_item: Dict[str, Any], promises: List[Dict[str, Any]]) -> str:
        """
        Construct the large context LLM prompt for evidence-promise linking.
        
        Args:
            evidence_item: The evidence item to link
            promises: List of all promises for the session
            
        Returns:
            Complete prompt string
        """
        # This method is now deprecated in favor of langchain integration
        # The langchain framework handles prompt construction automatically
        logger.debug("Using langchain framework for prompt construction")
        return "Prompt construction handled by langchain framework"
    
    async def call_llm_for_linking(self, evidence_item: Dict[str, Any], promises: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Call the LLM to perform evidence-promise linking analysis.
        
        Args:
            evidence_item: The evidence item to analyze
            promises: List of all promises to evaluate against
            
        Returns:
            LLM response with links found
        """
        try:
            logger.info(f"Calling LLM for evidence {evidence_item.get('_doc_id')} against {len(promises)} promises")
            
            # Create mapping of promise text to promise ID for validation and conversion
            text_to_id_mapping = {promise.get('text', ''): promise.get('promise_id') for promise in promises}
            valid_promise_texts = set(text_to_id_mapping.keys())
            logger.info(f"Valid promise texts count: {len(valid_promise_texts)}")
            
            # Use langchain framework for the LLM call
            result = self.langchain.link_evidence_to_multiple_promises(evidence_item, promises)
            
            self.stats['llm_calls_made'] += 1
            
            if 'error' in result:
                logger.error(f"LLM call failed: {result['error']}")
                return {"error": result['error'], "links": []}
            
            # Parse and validate the response
            if isinstance(result, list):
                links = result
            elif isinstance(result, dict) and 'links' in result:
                links = result['links']
            else:
                # Assume the result is the direct JSON array response
                links = result if isinstance(result, list) else []
            
            # Validate promise texts and convert to promise IDs
            valid_links = []
            invalid_links = []
            
            for link in links:
                promise_text = link.get('promise_text', '')
                if promise_text in valid_promise_texts:
                    # Convert promise text back to promise ID for database operations
                    promise_id = text_to_id_mapping[promise_text]
                    # Update the link to use promise_id for compatibility with existing database code
                    link['promise_id'] = promise_id
                    link['original_promise_text'] = promise_text  # Keep original for debugging
                    valid_links.append(link)
                else:
                    invalid_links.append({
                        'invalid_promise_text': promise_text,
                        'explanation': link.get('llm_explanation', 'No explanation'),
                        'score': link.get('llm_relevance_score', 0)
                    })
                    logger.warning(f"LLM returned invalid promise text: {promise_text[:100]}...")
            
            if invalid_links:
                logger.error(f"LLM returned {len(invalid_links)} invalid promise texts out of {len(links)} total")
                for i, invalid in enumerate(invalid_links[:3]):  # Show first 3 invalid texts
                    logger.error(f"Invalid text {i+1}: {invalid['invalid_promise_text'][:100]}...")
                
                # Log sample of valid texts for comparison
                sample_valid_texts = list(valid_promise_texts)[:5]
                for i, text in enumerate(sample_valid_texts):
                    logger.info(f"Sample valid text {i+1}: {text[:100]}...")
            
            logger.info(f"LLM found {len(valid_links)} valid links ({len(invalid_links)} invalid filtered out)")
            
            # Log each valid link for debugging
            for i, link in enumerate(valid_links):
                logger.debug(f"Valid Link {i+1}: Promise {link.get('promise_id')} "
                           f"(Score: {link.get('llm_relevance_score')}/10, "
                           f"Ranking: {link.get('llm_ranking_score')})")
                logger.debug(f"  Text: {link.get('original_promise_text', '')[:100]}...")
                logger.debug(f"  Explanation: {link.get('llm_explanation', 'No explanation')}")
            
            return {
                "links": valid_links, 
                "success": True,
                "validation_results": {
                    "total_links_returned": len(links),
                    "valid_links": len(valid_links),
                    "invalid_links": len(invalid_links),
                    "invalid_link_details": invalid_links
                }
            }
            
        except Exception as e:
            logger.error(f"Error in LLM call: {e}", exc_info=True)
            self.stats['errors'] += 1
            return {"error": str(e), "links": []}
    
    async def create_evidence_promise_links(self, evidence_item: Dict[str, Any], 
                                          links: List[Dict[str, Any]], dry_run: bool = False) -> int:
        """
        Create the actual evidence-promise links in the database.
        
        Args:
            evidence_item: The evidence item
            links: List of link objects from LLM
            dry_run: If True, don't write to database
            
        Returns:
            Number of links created
        """
        links_created = 0
        evidence_id = evidence_item.get('_doc_id')
        
        try:
            for link in links:
                promise_id = link.get('promise_id')
                if not promise_id:
                    logger.warning("Link missing promise_id, skipping")
                    continue
                
                # Create link data structure
                link_data = {
                    'evidence_id': evidence_id,
                    'promise_id': promise_id,
                    'llm_relevance_score': link.get('llm_relevance_score', 0),
                    'llm_ranking_score': link.get('llm_ranking_score', 'Unknown'),
                    'llm_explanation': link.get('llm_explanation', ''),
                    'llm_link_type_suggestion': link.get('llm_link_type_suggestion', ''),
                    'llm_status_impact_suggestion': link.get('llm_status_impact_suggestion', ''),
                    'linking_method': 'llm_multi_promise',
                    'created_at': datetime.now(timezone.utc),
                    'parliament_session_id': evidence_item.get('parliament_session_id')
                }
                
                if dry_run:
                    logger.info(f"[DRY RUN] Would create link: {evidence_id} -> {promise_id} "
                              f"(Score: {link_data['llm_relevance_score']}/10)")
                    links_created += 1
                else:
                    # Update promises collection: add evidence reference
                    promise_ref = db.collection(self.promises_collection).document(promise_id)
                    await asyncio.to_thread(
                        promise_ref.update,
                        {
                            'linked_evidence': firestore.ArrayUnion([{
                                'evidence_id': evidence_id,
                                'link_confidence': link_data['llm_relevance_score'],
                                'link_explanation': link_data['llm_explanation'],
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
                                'link_confidence': link_data['llm_relevance_score'],
                                'link_explanation': link_data['llm_explanation'],
                                'linked_at': link_data['created_at']
                            }])
                        }
                    )
                    
                    logger.info(f"Created link: {evidence_id} -> {promise_id} "
                              f"(Score: {link_data['llm_relevance_score']}/10)")
                    links_created += 1
        
        except Exception as e:
            logger.error(f"Error creating links: {e}", exc_info=True)
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
                'promise_links_found': links_count
            }
            
            if dry_run:
                logger.info(f"[DRY RUN] Would update evidence {evidence_id} status: {links_count} links found")
            else:
                evidence_ref = db.collection(self.evidence_items_collection).document(evidence_id)
                await asyncio.to_thread(evidence_ref.update, status_data)
                logger.info(f"Updated evidence {evidence_id} linking status: {links_count} links found")
                
        except Exception as e:
            logger.error(f"Error updating evidence linking status: {e}")

    async def run_linking_test(self, parliament_session_id: str, evidence_id: str, 
                             dry_run: bool = False) -> Dict[str, Any]:
        """
        Run the complete LLM evidence linking test.
        
        Args:
            parliament_session_id: Parliament session ID
            evidence_id: Evidence item ID to test
            dry_run: If True, don't write to database
            
        Returns:
            Test results and statistics including before/after state
        """
        start_time = time.time()
        
        logger.info("=== Starting LLM Evidence Linking Test ===")
        logger.info(f"Parliament Session: {parliament_session_id}")
        logger.info(f"Evidence ID: {evidence_id}")
        logger.info(f"Dry Run: {dry_run}")
        logger.info(f"Collections: {self.promises_collection}, {self.evidence_items_collection}")
        
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
            logger.info(f"Evidence Source: {evidence_item.get('source_type', 'Unknown')}")
            logger.info(f"Evidence Date: {evidence_item.get('date', 'Unknown')}")
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
            
            # Step 3: Call LLM for linking analysis
            logger.info("Calling LLM for multi-promise linking analysis...")
            llm_start_time = time.time()
            llm_result = await self.call_llm_for_linking(evidence_item, promises)
            llm_processing_time = time.time() - llm_start_time
            
            if "error" in llm_result:
                return {
                    "error": f"LLM analysis failed: {llm_result['error']}", 
                    "stats": self.stats,
                    "processing_time_seconds": time.time() - start_time
                }
            
            links_found = llm_result.get("links", [])
            logger.info(f"LLM analysis complete in {llm_processing_time:.2f}s. Found {len(links_found)} potential links")
            
            # Calculate after state
            after_promise_ids = before_promise_ids.copy()
            new_promise_ids = []
            database_updates = []
            
            for link in links_found:
                promise_id = link['promise_id']
                if promise_id not in after_promise_ids:
                    after_promise_ids.append(promise_id)
                    new_promise_ids.append(promise_id)
                    database_updates.append({
                        'promise_id': promise_id,
                        'action': 'added_to_evidence',
                        'llm_score': link.get('llm_relevance_score', 0),
                        'llm_explanation': link.get('llm_explanation', '')
                    })
            
            after_linking_status = 'processed'
            
            # Step 4: Create database links
            links_created = 0
            if links_found:
                links_created = await self.create_evidence_promise_links(evidence_item, links_found, dry_run)
                self.stats['links_created'] = links_created
                
                # Step 5: Update evidence linking status
                await self.update_evidence_linking_status(evidence_item['_doc_id'], links_created, dry_run)
            else:
                logger.info("No links found - updating evidence status with zero links")
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
                "llm_response": llm_result,
                "processing_metadata": {
                    "llm_processing_time": llm_processing_time,
                    "total_processing_time": processing_time,
                    "timestamp": datetime.now(timezone.utc).isoformat()
                }
            }
            
            # Save debug data to JSON file
            debug_filename = f"debug_linking_{evidence_id}_{int(time.time())}.json"
            debug_filepath = Path("debug_output") / debug_filename
            debug_filepath.parent.mkdir(exist_ok=True)
            
            with open(debug_filepath, 'w') as f:
                json.dump(debug_data, f, indent=2, default=str)
            
            logger.info(f"Debug data saved to: {debug_filepath}")
            
            # Log final results
            logger.info("=== LLM Evidence Linking Test Complete ===")
            logger.info(f"Evidence items processed: {self.stats['evidence_items_processed']}")
            logger.info(f"Promises fetched: {self.stats['promises_fetched']}")
            logger.info(f"Links created: {self.stats['links_created']}")
            logger.info(f"LLM calls made: {self.stats['llm_calls_made']}")
            logger.info(f"Errors: {self.stats['errors']}")
            logger.info(f"Total processing time: {processing_time:.2f} seconds")
            
            # Get cost summary from langchain
            cost_summary = self.langchain.get_cost_summary()
            logger.info(f"LLM Usage Summary:")
            logger.info(f"  Estimated cost: ${cost_summary['total_cost_usd']:.4f}")
            logger.info(f"  Total tokens: {cost_summary['total_tokens']}")
            logger.info(f"  Model: {cost_summary['model_name']}")
            
            result = {
                "success": True, 
                "evidence_id": evidence_id,
                "evidence_title": evidence_item.get('title_or_summary', 'No title'),
                "evidence_source_type": evidence_item.get('source_type', 'Unknown'),
                "evidence_date": evidence_item.get('date', 'Unknown'),
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
                "llm_analysis": {
                    "links_found": links_found,
                    "links_count": len(links_found),
                    "processing_time_seconds": llm_processing_time
                },
                "stats": self.stats, 
                "links_created": links_created,
                "cost_summary": cost_summary,
                "processing_time_seconds": processing_time,
                "dry_run": dry_run,
                "debug_file": str(debug_filepath)
            }
            
            # Also save the main result
            result_filename = f"result_linking_{evidence_id}_{int(time.time())}.json"
            result_filepath = Path("debug_output") / result_filename
            
            with open(result_filepath, 'w') as f:
                json.dump(result, f, indent=2, default=str)
            
            logger.info(f"Results saved to: {result_filepath}")
            
            return result
            
        except Exception as e:
            logger.error(f"Error in linking test: {e}", exc_info=True)
            self.stats['errors'] += 1
            return {
                "error": str(e), 
                "stats": self.stats,
                "processing_time_seconds": time.time() - start_time
            }
    
    async def run_batch_linking_test(self, parliament_session_id: str, limit: Optional[int] = None, 
                                   dry_run: bool = False) -> Dict[str, Any]:
        """
        Run LLM evidence linking test on multiple evidence items.
        
        Args:
            parliament_session_id: Parliament session ID
            limit: Maximum number of evidence items to process
            dry_run: If True, don't write to database
            
        Returns:
            Test results and statistics
        """
        logger.info("=== Starting Batch LLM Evidence Linking Test ===")
        logger.info(f"Parliament Session: {parliament_session_id}")
        logger.info(f"Limit: {limit or 'No limit'}")
        logger.info(f"Dry Run: {dry_run}")
        logger.info(f"Collections: {self.promises_collection}, {self.evidence_items_collection}")
        
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
            
            logger.info(f"Processing {len(evidence_items)} evidence items against {len(promises)} promises")
            
            # Step 3: Process each evidence item
            total_links_created = 0
            for i, evidence_item in enumerate(evidence_items, 1):
                evidence_id = evidence_item.get('_doc_id')
                logger.info(f"Processing evidence item {i}/{len(evidence_items)}: {evidence_id}")
                
                try:
                    # Call LLM for linking analysis
                    llm_result = await self.call_llm_for_linking(evidence_item, promises)
                    
                    if "error" in llm_result:
                        logger.error(f"LLM analysis failed for {evidence_id}: {llm_result['error']}")
                        self.stats['errors'] += 1
                        continue
                    
                    links_found = llm_result.get("links", [])
                    logger.info(f"Found {len(links_found)} potential links for evidence {evidence_id}")
                    
                    # Create database links
                    if links_found:
                        links_created = await self.create_evidence_promise_links(evidence_item, links_found, dry_run)
                        total_links_created += links_created
                        
                        # Update evidence linking status
                        await self.update_evidence_linking_status(evidence_id, links_created, dry_run)
                    else:
                        logger.info(f"No links found for evidence {evidence_id} - updating status with zero links")
                        await self.update_evidence_linking_status(evidence_id, 0, dry_run)
                    
                    self.stats['evidence_items_processed'] += 1
                    
                    # Rate limiting
                    if i < len(evidence_items):  # Don't sleep after the last item
                        await asyncio.sleep(RATE_LIMIT_DELAY_SECONDS)
                        
                except Exception as e:
                    logger.error(f"Error processing evidence item {evidence_id}: {e}", exc_info=True)
                    self.stats['errors'] += 1
                    continue
            
            self.stats['links_created'] = total_links_created
            
            # Log final results
            logger.info("=== Batch LLM Evidence Linking Test Complete ===")
            logger.info(f"Evidence items processed: {self.stats['evidence_items_processed']}")
            logger.info(f"Promises fetched: {self.stats['promises_fetched']}")
            logger.info(f"Total links created: {self.stats['links_created']}")
            logger.info(f"LLM calls made: {self.stats['llm_calls_made']}")
            logger.info(f"Errors: {self.stats['errors']}")
            
            # Get cost summary from langchain
            cost_summary = self.langchain.get_cost_summary()
            logger.info(f"LLM Usage Summary:")
            logger.info(f"  Estimated cost: ${cost_summary['total_cost_usd']:.4f}")
            logger.info(f"  Total tokens: {cost_summary['total_tokens']}")
            logger.info(f"  Model: {cost_summary['model_name']}")
            
            return {
                "success": True, 
                "stats": self.stats, 
                "cost_summary": cost_summary
            }
            
        except Exception as e:
            logger.error(f"Error in batch linking test: {e}", exc_info=True)
            self.stats['errors'] += 1
            return {"error": str(e), "stats": self.stats}


async def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(description='LLM Multi-Promise Evidence Linking Test')
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
        '--create_test_collections',
        action='store_true',
        help='Create/update test collections before running'
    )
    parser.add_argument(
        '--update_evidence_status',
        action='store_true',
        help='Update all evidence items in test collection to promise_linking_status = pending'
    )
    
    args = parser.parse_args()
    
    # Set logging level
    logging.getLogger().setLevel(getattr(logging, args.log_level))
    
    # Initialize tester
    tester = LLMEvidenceLinkingTester(use_test_collections=not args.use_production)
    
    # Create test collections if requested
    if args.create_test_collections and not args.use_production:
        logger.info("Creating/updating test collections...")
        success = await tester.create_test_collections(args.parliament_session_id)
        if not success:
            logger.error("Failed to create test collections")
            return
    
    # Update evidence status if requested
    if args.update_evidence_status and not args.use_production:
        logger.info("Updating evidence items to promise_linking_status = 'pending'...")
        success = await tester.update_test_evidence_linking_status(args.parliament_session_id)
        if not success:
            logger.error("Failed to update evidence linking status")
            return
    
    # Run the linking test
    if args.evidence_id_to_test:
        # Single evidence item mode
        result = await tester.run_linking_test(
            parliament_session_id=args.parliament_session_id,
            evidence_id=args.evidence_id_to_test,
            dry_run=args.dry_run
        )
    else:
        # Batch processing mode
        result = await tester.run_batch_linking_test(
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