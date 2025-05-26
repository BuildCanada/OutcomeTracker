#!/usr/bin/env python3
"""
Consolidated Evidence-Promise Linking Pipeline

This script combines and modernizes the evidence-promise linking functionality:
- link_evidence_to_promises.py (main linking logic)
- linking_jobs/link_evidence_to_promises.py (batch processing)

Uses the centralized Langchain framework for LLM coordination and prompt management.
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
sys.path.append(str(Path(__file__).parent.parent / 'lib'))

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
logger = logging.getLogger("consolidated_linking")

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
                app_name = 'consolidated_linking_app'
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
PROMISES_COLLECTION_ROOT = os.getenv("TARGET_PROMISES_COLLECTION", "promises")
EVIDENCE_COLLECTION_ROOT = os.getenv("TARGET_EVIDENCE_COLLECTION", "evidence")
RATE_LIMIT_DELAY_SECONDS = 1

class ConsolidatedEvidenceLinking:
    """Handles evidence-promise linking using Langchain framework."""
    
    def __init__(self):
        """Initialize the linker with Langchain instance."""
        self.langchain = get_langchain_instance()
        self.stats = {
            'evidence_processed': 0,
            'promises_evaluated': 0,
            'links_created': 0,
            'links_rejected': 0,
            'errors': 0
        }
    
    async def query_evidence_for_linking(self, parliament_session_id: str, evidence_types: List[str] = None,
                                       limit: int = None, force_reprocessing: bool = False) -> List[Dict[str, Any]]:
        """Query evidence items that need linking."""
        logger.info(f"Querying evidence for linking: session='{parliament_session_id}', types={evidence_types}, limit={limit}, force={force_reprocessing}")
        
        try:
            # Build query for unlinked evidence
            query = db.collection(EVIDENCE_COLLECTION_ROOT)
            
            # Filter by parliament session
            if parliament_session_id:
                query = query.where(filter=firestore.FieldFilter("parliament_session_id", "==", parliament_session_id))
            
            # Filter by evidence types
            if evidence_types:
                query = query.where(filter=firestore.FieldFilter("evidence_type", "in", evidence_types))
            
            # Filter for evidence needing linking (unless force reprocessing)
            if not force_reprocessing:
                query = query.where(filter=firestore.FieldFilter("evidence_linking_status", "==", "unprocessed"))
            
            if limit:
                query = query.limit(limit)
            
            # Execute query
            evidence_docs = list(await asyncio.to_thread(query.stream))
            
            evidence_items = []
            for doc in evidence_docs:
                data = doc.to_dict()
                if data:
                    evidence_items.append({
                        "id": doc.id,
                        "doc_ref": doc.reference,
                        "data": data
                    })
                else:
                    logger.warning(f"Empty data for evidence item {doc.id}, skipping.")
            
            logger.info(f"Retrieved {len(evidence_items)} evidence items for linking")
            return evidence_items
            
        except Exception as e:
            logger.error(f"Error querying evidence: {e}", exc_info=True)
            return []
    
    async def query_promises_for_linking(self, parliament_session_id: str, party_codes: List[str] = None) -> List[Dict[str, Any]]:
        """Query promises that could be linked to evidence."""
        logger.info(f"Querying promises for linking: session='{parliament_session_id}', parties={party_codes}")
        
        try:
            # Build query for promises
            query = db.collection(PROMISES_COLLECTION_ROOT)
            
            # Filter by parliament session
            if parliament_session_id:
                query = query.where(filter=firestore.FieldFilter("parliament_session_id", "==", parliament_session_id))
            
            # Filter by party codes
            if party_codes:
                query = query.where(filter=firestore.FieldFilter("party_code", "in", party_codes))
            
            # Execute query
            promise_docs = list(await asyncio.to_thread(query.stream))
            
            promises = []
            for doc in promise_docs:
                data = doc.to_dict()
                if data and data.get("text"):
                    promises.append({
                        "id": doc.id,
                        "doc_ref": doc.reference,
                        "data": data
                    })
                else:
                    logger.warning(f"Promise {doc.id} missing 'text' field, skipping.")
            
            logger.info(f"Retrieved {len(promises)} promises for linking")
            return promises
            
        except Exception as e:
            logger.error(f"Error querying promises: {e}", exc_info=True)
            return []
    
    async def evaluate_evidence_promise_link(self, evidence_item: Dict[str, Any], 
                                           promise_item: Dict[str, Any]) -> Dict[str, Any]:
        """Evaluate if evidence should be linked to a promise using LLM."""
        try:
            evidence_data = evidence_item['data']
            promise_data = promise_item['data']
            
            # Prepare data for LLM evaluation
            linking_data = {
                'evidence': {
                    'title': evidence_data.get('title', ''),
                    'content': evidence_data.get('content', evidence_data.get('summary', '')),
                    'type': evidence_data.get('evidence_type', ''),
                    'date': evidence_data.get('date'),
                    'source': evidence_data.get('source_url', '')
                },
                'promise': {
                    'text': promise_data.get('text', ''),
                    'party': promise_data.get('party_code', ''),
                    'department': promise_data.get('responsible_department_lead', ''),
                    'source_type': promise_data.get('source_type', ''),
                    'keywords': promise_data.get('extracted_keywords_concepts', [])
                }
            }
            
            # Get LLM evaluation
            result = self.langchain.link_evidence_to_promise(
                evidence_data=linking_data['evidence'],
                promise_data=linking_data['promise']
            )
            
            if 'error' in result:
                logger.error(f"Error evaluating link: {result['error']}")
                return {'should_link': False, 'error': result['error']}
            
            return result
            
        except Exception as e:
            logger.error(f"Error evaluating evidence-promise link: {e}")
            return {'should_link': False, 'error': str(e)}
    
    async def create_evidence_link(self, evidence_item: Dict[str, Any], promise_item: Dict[str, Any],
                                 link_rationale: str, confidence_score: float, dry_run: bool = False) -> bool:
        """Create a link between evidence and promise."""
        try:
            evidence_id = evidence_item['id']
            promise_id = promise_item['id']
            
            link_data = {
                'evidence_id': evidence_id,
                'promise_id': promise_id,
                'link_rationale': link_rationale,
                'confidence_score': confidence_score,
                'linking_model': self.langchain.model_name,
                'linked_at': firestore.SERVER_TIMESTAMP,
                'link_type': 'llm_generated'
            }
            
            if not dry_run:
                # Add link to promise's linked_evidence array
                promise_ref = promise_item['doc_ref']
                await asyncio.to_thread(promise_ref.update, {
                    "linked_evidence": firestore.ArrayUnion([link_data])
                })
                
                # Update evidence linking status
                evidence_ref = evidence_item['doc_ref']
                evidence_links = evidence_item['data'].get('linked_promises', [])
                evidence_links.append({
                    'promise_id': promise_id,
                    'link_rationale': link_rationale,
                    'confidence_score': confidence_score,
                    'linked_at': datetime.now(timezone.utc)
                })
                
                await asyncio.to_thread(evidence_ref.update, {
                    "linked_promises": evidence_links,
                    "linking_status": "processed"
                })
                
                logger.info(f"Created link: evidence {evidence_id} -> promise {promise_id} (confidence: {confidence_score:.2f})")
            else:
                logger.info(f"[DRY RUN] Would create link: evidence {evidence_id} -> promise {promise_id} (confidence: {confidence_score:.2f})")
            
            self.stats['links_created'] += 1
            return True
            
        except Exception as e:
            logger.error(f"Error creating evidence link: {e}")
            self.stats['errors'] += 1
            return False
    
    async def process_evidence_linking(self, evidence_item: Dict[str, Any], promises: List[Dict[str, Any]],
                                     min_confidence: float = 0.7, dry_run: bool = False) -> int:
        """Process linking for a single evidence item against all promises."""
        evidence_id = evidence_item['id']
        links_created = 0
        
        logger.debug(f"Processing evidence {evidence_id} against {len(promises)} promises")
        
        try:
            for promise in promises:
                self.stats['promises_evaluated'] += 1
                
                # Evaluate potential link
                evaluation = await self.evaluate_evidence_promise_link(evidence_item, promise)
                
                if evaluation.get('error'):
                    logger.warning(f"Error evaluating evidence {evidence_id} -> promise {promise['id']}: {evaluation['error']}")
                    continue
                
                should_link = evaluation.get('should_link', False)
                confidence = evaluation.get('confidence_score', 0.0)
                rationale = evaluation.get('rationale', '')
                
                if should_link and confidence >= min_confidence:
                    success = await self.create_evidence_link(
                        evidence_item=evidence_item,
                        promise_item=promise,
                        link_rationale=rationale,
                        confidence_score=confidence,
                        dry_run=dry_run
                    )
                    if success:
                        links_created += 1
                else:
                    self.stats['links_rejected'] += 1
                    logger.debug(f"Rejected link: evidence {evidence_id} -> promise {promise['id']} (confidence: {confidence:.2f})")
            
            # Update evidence processing status
            if not dry_run:
                await asyncio.to_thread(evidence_item['doc_ref'].update, {
                    "evidence_linking_status": "processed",
                    "evidence_linking_processed_at": firestore.SERVER_TIMESTAMP
                })
            
            return links_created
            
        except Exception as e:
            logger.error(f"Error processing evidence linking for {evidence_id}: {e}")
            self.stats['errors'] += 1
            return 0
    
    async def run_evidence_linking_pipeline(self, parliament_session_id: str, evidence_types: List[str] = None,
                                          party_codes: List[str] = None, limit: int = None,
                                          min_confidence: float = 0.7, force_reprocessing: bool = False,
                                          dry_run: bool = False) -> Dict[str, Any]:
        """Run the complete evidence-promise linking pipeline."""
        logger.info("=== Starting Consolidated Evidence-Promise Linking Pipeline ===")
        logger.info(f"Parliament Session: {parliament_session_id}")
        logger.info(f"Evidence Types: {evidence_types or 'All'}")
        logger.info(f"Party Codes: {party_codes or 'All'}")
        logger.info(f"Limit: {limit or 'None'}")
        logger.info(f"Min Confidence: {min_confidence}")
        logger.info(f"Force Reprocessing: {force_reprocessing}")
        logger.info(f"Dry Run: {dry_run}")
        
        if dry_run:
            logger.warning("*** DRY RUN MODE: No changes will be written to Firestore ***")
        
        # Query evidence and promises
        evidence_items = await self.query_evidence_for_linking(
            parliament_session_id=parliament_session_id,
            evidence_types=evidence_types,
            limit=limit,
            force_reprocessing=force_reprocessing
        )
        
        if not evidence_items:
            logger.info("No evidence items found for linking. Exiting.")
            return self.stats
        
        promises = await self.query_promises_for_linking(
            parliament_session_id=parliament_session_id,
            party_codes=party_codes
        )
        
        if not promises:
            logger.info("No promises found for linking. Exiting.")
            return self.stats
        
        logger.info(f"Processing {len(evidence_items)} evidence items against {len(promises)} promises...")
        
        # Process each evidence item
        for i, evidence_item in enumerate(evidence_items):
            logger.info(f"--- Processing evidence {i+1}/{len(evidence_items)}: {evidence_item['id']} ---")
            
            links_created = await self.process_evidence_linking(
                evidence_item=evidence_item,
                promises=promises,
                min_confidence=min_confidence,
                dry_run=dry_run
            )
            
            self.stats['evidence_processed'] += 1
            logger.info(f"Evidence {evidence_item['id']} resulted in {links_created} links")
            
            # Rate limiting between evidence items
            if i < len(evidence_items) - 1:
                await asyncio.sleep(RATE_LIMIT_DELAY_SECONDS)
        
        # Log final statistics
        logger.info("=== Evidence-Promise Linking Pipeline Complete ===")
        logger.info(f"Evidence items processed: {self.stats['evidence_processed']}")
        logger.info(f"Promise evaluations: {self.stats['promises_evaluated']}")
        logger.info(f"Links created: {self.stats['links_created']}")
        logger.info(f"Links rejected: {self.stats['links_rejected']}")
        logger.info(f"Errors encountered: {self.stats['errors']}")
        
        # Get cost summary
        cost_summary = self.langchain.get_cost_summary()
        logger.info(f"LLM Usage Summary:")
        logger.info(f"  Total estimated cost: ${cost_summary['total_cost_usd']:.4f}")
        logger.info(f"  Total tokens: {cost_summary['total_tokens']}")
        logger.info(f"  Total LLM calls: {cost_summary['total_calls']}")
        
        return self.stats

async def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(description='Consolidated Evidence-Promise Linking Pipeline')
    parser.add_argument(
        '--parliament_session_id',
        type=str,
        required=True,
        help='Parliament session ID (e.g., "44")'
    )
    parser.add_argument(
        '--evidence_types',
        nargs='+',
        choices=['OIC', 'Canada Gazette Part II', 'Bill', 'News'],
        help='Types of evidence to process'
    )
    parser.add_argument(
        '--party_codes',
        nargs='+',
        choices=['LPC', 'CPC', 'NDP', 'BQ', 'GPC'],
        help='Party codes to process promises for'
    )
    parser.add_argument(
        '--limit',
        type=int,
        help='Limit number of evidence items to process'
    )
    parser.add_argument(
        '--min_confidence',
        type=float,
        default=0.7,
        help='Minimum confidence score for creating links (default: 0.7)'
    )
    parser.add_argument(
        '--force_reprocessing',
        action='store_true',
        help='Force reprocessing even if evidence already processed'
    )
    parser.add_argument(
        '--dry_run',
        action='store_true',
        help='Run without making changes to Firestore'
    )
    
    args = parser.parse_args()
    
    # Run evidence linking pipeline
    linker = ConsolidatedEvidenceLinking()
    stats = await linker.run_evidence_linking_pipeline(
        parliament_session_id=args.parliament_session_id,
        evidence_types=args.evidence_types,
        party_codes=args.party_codes,
        limit=args.limit,
        min_confidence=args.min_confidence,
        force_reprocessing=args.force_reprocessing,
        dry_run=args.dry_run
    )
    
    logger.info("Evidence-promise linking pipeline completed successfully!")

if __name__ == "__main__":
    asyncio.run(main()) 