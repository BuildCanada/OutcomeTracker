#!/usr/bin/env python3
"""
Consolidated Promise Enrichment Pipeline

This script combines the functionality of multiple enrichment scripts:
- enrich_promises_with_explanation.py (explanations, descriptions, background)
- enrich_tag_new_promise.py (history rationale, keywords, action types)
- rank_promise_priority.py (BC priority rankings)

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
logger = logging.getLogger("consolidated_enrichment")

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
                app_name = 'consolidated_enrichment_app'
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
TARGET_SOURCE_TYPES = ["2021 LPC Mandate Letters", "2025 LPC Platform"]
RATE_LIMIT_DELAY_SECONDS = 2

class ConsolidatedPromiseEnricher:
    """Handles all promise enrichment operations using Langchain framework."""
    
    def __init__(self):
        """Initialize the enricher with Langchain instance."""
        self.langchain = get_langchain_instance()
        self.stats = {
            'total_processed': 0,
            'explanations_generated': 0,
            'keywords_extracted': 0,
            'action_types_classified': 0,
            'history_generated': 0,
            'priorities_ranked': 0,
            'errors': 0
        }
    
    async def query_promises_for_enrichment(self, parliament_session_id: str, source_type: str = None, 
                                          limit: int = None, force_reprocessing: bool = False) -> list[dict]:
        """Query promises that need enrichment."""
        logger.info(f"Querying promises for enrichment: session '{parliament_session_id}', source_type: '{source_type}', limit: {limit}, force: {force_reprocessing}")
        
        try:
            # Build query for LPC promises
            query = db.collection(PROMISES_COLLECTION_ROOT).where(
                filter=firestore.FieldFilter("party_code", "==", "LPC")
            ).where(
                filter=firestore.FieldFilter("parliament_session_id", "==", parliament_session_id)
            )
            
            if source_type:
                query = query.where(filter=firestore.FieldFilter("source_type", "==", source_type))
            else:
                query = query.where(filter=firestore.FieldFilter("source_type", "in", TARGET_SOURCE_TYPES))
            
            # Filter for promises needing enrichment (unless force reprocessing)
            if not force_reprocessing:
                # Check if any enrichment fields are missing
                # For simplicity, check one key field as proxy
                query = query.where(filter=firestore.FieldFilter("what_it_means_for_canadians", "==", None))
            
            if limit:
                query = query.limit(limit)
            
            # Execute query
            promise_docs = list(await asyncio.to_thread(query.stream))
            
            promises = []
            for doc in promise_docs:
                data = doc.to_dict()
                if data and data.get("text"):
                    promises.append({
                        "id": doc.id,
                        "text": data["text"],
                        "responsible_department_lead": data.get("responsible_department_lead"),
                        "source_type": data.get("source_type"),
                        "party_code": data.get("party_code"),
                        "doc_ref": doc.reference,
                        "data": data
                    })
                else:
                    logger.warning(f"Promise {doc.id} missing 'text' field, skipping.")
            
            logger.info(f"Retrieved {len(promises)} promises for enrichment")
            return promises
            
        except Exception as e:
            logger.error(f"Error querying promises: {e}", exc_info=True)
            return []
    
    async def enrich_promise_explanation(self, promise: dict) -> dict:
        """Generate explanation fields for a promise."""
        try:
            logger.debug(f"Generating explanation for promise {promise['id']}")
            
            result = self.langchain.enrich_promise_explanation(
                promise_text=promise['text'],
                department=promise.get('responsible_department_lead', ''),
                party=promise.get('party_code', 'LPC'),
                context=f"Source: {promise.get('source_type', '')}"
            )
            
            if 'error' not in result:
                self.stats['explanations_generated'] += 1
                return {
                    "what_it_means_for_canadians": result.get("what_it_means"),
                    "background_and_context": result.get("background_and_context"),
                    "description": result.get("key_components", []),
                    "concise_title": result.get("potential_impact", "")[:100],  # Use first part as title
                    "explanation_enriched_at": firestore.SERVER_TIMESTAMP,
                    "explanation_enrichment_model": self.langchain.model_name,
                    "explanation_enrichment_status": "processed"
                }
            else:
                logger.error(f"Error in explanation generation: {result['error']}")
                return {"explanation_enrichment_status": "failed"}
                
        except Exception as e:
            logger.error(f"Error enriching explanation for promise {promise['id']}: {e}")
            return {"explanation_enrichment_status": "failed"}
    
    async def extract_promise_keywords(self, promise: dict) -> dict:
        """Extract keywords and concepts from a promise."""
        try:
            logger.debug(f"Extracting keywords for promise {promise['id']}")
            
            result = self.langchain.extract_promise_keywords(
                promise_text=promise['text'],
                department=promise.get('responsible_department_lead', '')
            )
            
            if 'error' not in result:
                self.stats['keywords_extracted'] += 1
                
                # Flatten all keywords into a single list
                all_keywords = []
                all_keywords.extend(result.get("policy_areas", []))
                all_keywords.extend(result.get("actions", []))
                all_keywords.extend(result.get("target_groups", []))
                all_keywords.extend(result.get("key_concepts", []))
                
                return {
                    "extracted_keywords_concepts": all_keywords,
                    "policy_areas": result.get("policy_areas", []),
                    "target_groups": result.get("target_groups", []),
                    "keywords_extracted_at": firestore.SERVER_TIMESTAMP
                }
            else:
                logger.error(f"Error in keyword extraction: {result['error']}")
                return {}
                
        except Exception as e:
            logger.error(f"Error extracting keywords for promise {promise['id']}: {e}")
            return {}
    
    async def classify_action_type(self, promise: dict) -> dict:
        """Classify the action type required for a promise."""
        try:
            logger.debug(f"Classifying action type for promise {promise['id']}")
            
            result = self.langchain.classify_promise_action_type(promise['text'])
            
            if 'error' not in result:
                self.stats['action_types_classified'] += 1
                return {
                    "implied_action_type": result.get("action_type"),
                    "action_type_confidence": result.get("confidence", 0.0),
                    "action_type_rationale": result.get("rationale"),
                    "action_type_classified_at": firestore.SERVER_TIMESTAMP
                }
            else:
                logger.error(f"Error in action type classification: {result['error']}")
                return {}
                
        except Exception as e:
            logger.error(f"Error classifying action type for promise {promise['id']}: {e}")
            return {}
    
    async def generate_commitment_history(self, promise: dict) -> dict:
        """Generate commitment history for a promise."""
        try:
            logger.debug(f"Generating history for promise {promise['id']}")
            
            # Extract year from source type or use current year
            year = "2021" if "2021" in promise.get('source_type', '') else "2025"
            
            result = self.langchain.generate_promise_history(
                promise_text=promise['text'],
                party=promise.get('party_code', 'LPC'),
                year=year,
                department=promise.get('responsible_department_lead', '')
            )
            
            if 'error' not in result:
                self.stats['history_generated'] += 1
                return {
                    "commitment_history_rationale": result.get("historical_context"),
                    "political_significance": result.get("political_significance"),
                    "implementation_notes": result.get("implementation_notes"),
                    "history_generated_at": firestore.SERVER_TIMESTAMP
                }
            else:
                logger.error(f"Error in history generation: {result['error']}")
                return {}
                
        except Exception as e:
            logger.error(f"Error generating history for promise {promise['id']}: {e}")
            return {}
    
    async def enrich_single_promise(self, promise: dict, enrichment_types: list, dry_run: bool = False) -> bool:
        """Enrich a single promise with specified enrichment types."""
        try:
            update_data = {}
            
            # Generate each type of enrichment
            if 'explanation' in enrichment_types:
                explanation_data = await self.enrich_promise_explanation(promise)
                update_data.update(explanation_data)
            
            if 'keywords' in enrichment_types:
                keywords_data = await self.extract_promise_keywords(promise)
                update_data.update(keywords_data)
            
            if 'action_type' in enrichment_types:
                action_data = await self.classify_action_type(promise)
                update_data.update(action_data)
            
            if 'history' in enrichment_types:
                history_data = await self.generate_commitment_history(promise)
                update_data.update(history_data)
            
            # Add processing timestamp
            update_data["last_enrichment_at"] = firestore.SERVER_TIMESTAMP
            
            # Update promise in Firestore
            if update_data and not dry_run:
                await asyncio.to_thread(promise['doc_ref'].update, update_data)
                logger.info(f"Successfully enriched promise {promise['id']} with {len(update_data)} fields")
            elif update_data and dry_run:
                logger.info(f"[DRY RUN] Would update promise {promise['id']} with {len(update_data)} fields")
            
            self.stats['total_processed'] += 1
            return True
            
        except Exception as e:
            logger.error(f"Error enriching promise {promise['id']}: {e}", exc_info=True)
            self.stats['errors'] += 1
            return False
    
    async def run_enrichment_pipeline(self, parliament_session_id: str, enrichment_types: list,
                                    source_type: str = None, limit: int = None, 
                                    force_reprocessing: bool = False, dry_run: bool = False) -> dict:
        """Run the complete enrichment pipeline."""
        logger.info("=== Starting Consolidated Promise Enrichment Pipeline ===")
        logger.info(f"Parliament Session: {parliament_session_id}")
        logger.info(f"Enrichment Types: {enrichment_types}")
        logger.info(f"Source Type: {source_type or 'All TARGET_SOURCE_TYPES'}")
        logger.info(f"Limit: {limit or 'None'}")
        logger.info(f"Force Reprocessing: {force_reprocessing}")
        logger.info(f"Dry Run: {dry_run}")
        
        if dry_run:
            logger.warning("*** DRY RUN MODE: No changes will be written to Firestore ***")
        
        # Query promises needing enrichment
        promises = await self.query_promises_for_enrichment(
            parliament_session_id=parliament_session_id,
            source_type=source_type,
            limit=limit,
            force_reprocessing=force_reprocessing
        )
        
        if not promises:
            logger.info("No promises found for enrichment. Exiting.")
            return self.stats
        
        logger.info(f"Processing {len(promises)} promises...")
        
        # Process each promise
        for i, promise in enumerate(promises):
            logger.info(f"--- Processing promise {i+1}/{len(promises)}: {promise['id']} ---")
            logger.debug(f"Promise text: {promise['text'][:100]}...")
            
            success = await self.enrich_single_promise(promise, enrichment_types, dry_run)
            
            if not success:
                logger.warning(f"Failed to enrich promise {promise['id']}")
            
            # Rate limiting between promises
            if i < len(promises) - 1:
                await asyncio.sleep(RATE_LIMIT_DELAY_SECONDS)
        
        # Log final statistics
        logger.info("=== Enrichment Pipeline Complete ===")
        logger.info(f"Total promises processed: {self.stats['total_processed']}")
        logger.info(f"Explanations generated: {self.stats['explanations_generated']}")
        logger.info(f"Keywords extracted: {self.stats['keywords_extracted']}")
        logger.info(f"Action types classified: {self.stats['action_types_classified']}")
        logger.info(f"History generated: {self.stats['history_generated']}")
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
    parser = argparse.ArgumentParser(description='Consolidated Promise Enrichment Pipeline')
    parser.add_argument(
        '--parliament_session_id',
        type=str,
        required=True,
        help='Parliament session ID (e.g., "44")'
    )
    parser.add_argument(
        '--enrichment_types',
        nargs='+',
        choices=['explanation', 'keywords', 'action_type', 'history', 'all'],
        default=['all'],
        help='Types of enrichment to perform'
    )
    parser.add_argument(
        '--source_type',
        type=str,
        help='Optional source type filter'
    )
    parser.add_argument(
        '--limit',
        type=int,
        help='Limit number of promises to process'
    )
    parser.add_argument(
        '--force_reprocessing',
        action='store_true',
        help='Force reprocessing even if enrichment already exists'
    )
    parser.add_argument(
        '--dry_run',
        action='store_true',
        help='Run without making changes to Firestore'
    )
    
    args = parser.parse_args()
    
    # Handle 'all' enrichment type
    if 'all' in args.enrichment_types:
        enrichment_types = ['explanation', 'keywords', 'action_type', 'history']
    else:
        enrichment_types = args.enrichment_types
    
    # Run enrichment pipeline
    enricher = ConsolidatedPromiseEnricher()
    stats = await enricher.run_enrichment_pipeline(
        parliament_session_id=args.parliament_session_id,
        enrichment_types=enrichment_types,
        source_type=args.source_type,
        limit=args.limit,
        force_reprocessing=args.force_reprocessing,
        dry_run=args.dry_run
    )
    
    logger.info("Enrichment pipeline completed successfully!")

if __name__ == "__main__":
    asyncio.run(main()) 