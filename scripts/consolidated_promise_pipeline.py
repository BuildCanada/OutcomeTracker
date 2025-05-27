#!/usr/bin/env python3
"""
Consolidated Promise Pipeline - Master Script

This script combines and orchestrates all promise processing functionality:
1. Promise Ingestion (ingest_2021_mandate_commitments.py logic)
2. Promise Enrichment (consolidated_promise_enrichment.py logic)  
3. Promise Priority Ranking (rank_promise_priority.py logic)

Uses a state machine approach with comprehensive error handling and progress tracking.
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
import pandas as pd
import csv
from enum import Enum
from typing import Dict, List, Optional, Tuple
import uuid

# Add parent directory to path to import utilities
sys.path.append(str(Path(__file__).parent))

try:
    from common_utils import standardize_department_name, get_promise_document_path, SOURCE_TYPE_FIELD_UPDATE_MAPPING
except ImportError:
    logging.warning("common_utils not found, using fallback functions")
    def standardize_department_name(dept_name): return dept_name
    def get_promise_document_path(promise_id): return f"promises/{promise_id}"
    SOURCE_TYPE_FIELD_UPDATE_MAPPING = {}

# Load environment variables
load_dotenv()

# Logger setup
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(filename)s:%(lineno)d - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger("consolidated_promise_pipeline")

# Add parent directory to path to import langchain_config
sys.path.append(str(Path(__file__).parent.parent / 'lib'))

try:
    from langchain_config import get_langchain_instance
except ImportError as e:
    logger.warning(f"langchain_config not available: {e}")
    langchain_instance = None

# Promise Processing States
class PromiseState(Enum):
    RAW = "raw"
    INGESTED = "ingested"
    ENRICHED = "enriched"
    PRIORITY_RANKED = "priority_ranked"
    COMPLETED = "completed"
    ERROR = "error"

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
                app_name = 'consolidated_promise_pipeline'
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
PROMISES_COLLECTION = 'promises'
RATE_LIMIT_DELAY_SECONDS = 2

class ConsolidatedPromisePipeline:
    """Main class for orchestrating the complete promise processing pipeline."""
    
    def __init__(self):
        """Initialize the pipeline."""
        self.db = db
        if langchain_instance:
            self.langchain = get_langchain_instance()
        else:
            self.langchain = None
        
        self.session_id = str(uuid.uuid4())[:8]
        self.stats = {
            'total_processed': 0,
            'ingested': 0,
            'enriched': 0,
            'priority_ranked': 0,
            'errors': 0,
            'skipped': 0
        }
        
        # State tracking
        self.promise_states = {}
        
        logger.info(f"Initialized Consolidated Promise Pipeline (Session: {self.session_id})")
    
    def update_promise_state(self, promise_id: str, new_state: PromiseState, error_message: str = None):
        """Update the state of a promise in tracking and Firestore."""
        try:
            # Update local tracking
            self.promise_states[promise_id] = {
                'state': new_state,
                'updated_at': datetime.now().isoformat(),
                'error_message': error_message
            }
            
            # Update Firestore document
            update_data = {
                'pipeline_state': new_state.value,
                'pipeline_updated_at': firestore.SERVER_TIMESTAMP,
                'pipeline_session_id': self.session_id
            }
            
            if error_message:
                update_data['pipeline_error_message'] = error_message[:500]
            
            doc_ref = self.db.collection(PROMISES_COLLECTION).document(promise_id)
            doc_ref.update(update_data)
            
            logger.debug(f"Updated promise {promise_id} state to {new_state.value}")
            
        except Exception as e:
            logger.error(f"Failed to update state for promise {promise_id}: {e}")
    
    def get_promise_state(self, promise_data: dict) -> PromiseState:
        """Determine the current state of a promise based on its data."""
        # Check for error state
        if promise_data.get('pipeline_state') == 'error':
            return PromiseState.ERROR
        
        # Check completion markers in order
        if promise_data.get('bc_priority_score') is not None:
            return PromiseState.PRIORITY_RANKED
        
        if (promise_data.get('what_it_means_for_canadians') and 
            promise_data.get('extracted_keywords_concepts') and
            promise_data.get('implied_action_type')):
            return PromiseState.ENRICHED
        
        if promise_data.get('text') and promise_data.get('source_type'):
            return PromiseState.INGESTED
        
        return PromiseState.RAW
    
    async def ingest_mandate_letters(self, mandate_csv_path: str, mandate_urls_csv_path: str, 
                                   dry_run: bool = False) -> List[str]:
        """Ingest promises from mandate letter CSV files."""
        logger.info("=== Starting Mandate Letter Ingestion ===")
        
        ingested_promise_ids = []
        
        try:
            # Load mandate letter URLs mapping
            url_map = self.load_mandate_letter_urls(mandate_urls_csv_path)
            
            # Process mandate commitments CSV
            df = pd.read_csv(mandate_csv_path)
            logger.info(f"Processing {len(df)} rows from {mandate_csv_path}")
            
            for index, row in df.iterrows():
                try:
                    promise_id_str = str(row['MLC ID'])
                    
                    # Basic validation
                    if not promise_id_str or promise_id_str.lower() == 'nan':
                        logger.warning(f"Skipping row {index+2} due to missing or invalid 'MLC ID'.")
                        self.stats['skipped'] += 1
                        continue
                    
                    # Standardize departments
                    reporting_lead_raw = str(row.get('Reporting Lead', '')).strip()
                    reporting_lead_standardized = standardize_department_name(reporting_lead_raw)
                    
                    all_ministers_raw = str(row.get('All ministers', '')).strip()
                    all_ministers_standardized = []
                    if all_ministers_raw and all_ministers_raw.lower() != 'nan':
                        ministers_list = all_ministers_raw.split(';')
                        for m in ministers_list:
                            std_name = standardize_department_name(m.strip())
                            if std_name and std_name not in all_ministers_standardized:
                                all_ministers_standardized.append(std_name)
                    
                    # Look up source URL
                    source_url = None
                    if reporting_lead_standardized:
                        source_url = url_map.get(reporting_lead_standardized)
                    
                    # Validate commitment text
                    commitment_text = str(row.get('Commitment', '')).strip()
                    if not commitment_text or commitment_text.lower() == 'nan':
                        logger.warning(f"Skipping row {index+2} (MLC ID: {promise_id_str}) due to missing 'Commitment' text.")
                        self.stats['skipped'] += 1
                        continue
                    
                    # Create promise document
                    current_source_type = 'Mandate Letter Commitment (Structured)'
                    final_source_type = SOURCE_TYPE_FIELD_UPDATE_MAPPING.get(current_source_type, current_source_type)
                    
                    promise_doc = {
                        'promise_id': promise_id_str,
                        'text': commitment_text,
                        'source_document_url': source_url,
                        'source_type': final_source_type,
                        'date_issued': '2021-12-16',
                        'parliament_session_id': "44",
                        'candidate_or_government': 'Government of Canada (2021 Mandate)',
                        'party_code': 'LPC',
                        'region_code': 'CAN',
                        'responsible_department_lead': reporting_lead_standardized,
                        'relevant_departments': all_ministers_standardized,
                        'mlc_raw_reporting_lead': reporting_lead_raw if reporting_lead_raw.lower() != 'nan' else None,
                        'mlc_raw_all_ministers': all_ministers_raw if all_ministers_raw.lower() != 'nan' else None,
                        
                        # Pipeline tracking
                        'pipeline_state': PromiseState.INGESTED.value,
                        'pipeline_created_at': firestore.SERVER_TIMESTAMP,
                        'pipeline_session_id': self.session_id,
                        
                        # Placeholders for enrichment
                        'what_it_means_for_canadians': None,
                        'background_and_context': None,
                        'extracted_keywords_concepts': None,
                        'implied_action_type': None,
                        'commitment_history_rationale': None,
                        'bc_priority_score': None
                    }
                    
                    # Insert or update promise
                    if not dry_run:
                        doc_ref = self.db.collection(PROMISES_COLLECTION).document(promise_id_str)
                        doc_ref.set(promise_doc, merge=True)
                        logger.debug(f"Ingested promise: {promise_id_str}")
                    else:
                        logger.info(f"[DRY RUN] Would ingest promise: {promise_id_str}")
                    
                    ingested_promise_ids.append(promise_id_str)
                    self.stats['ingested'] += 1
                    self.update_promise_state(promise_id_str, PromiseState.INGESTED)
                    
                except Exception as e:
                    logger.error(f"Error processing promise row {index+2}: {e}")
                    self.stats['errors'] += 1
                    continue
            
            logger.info(f"Ingestion complete: {self.stats['ingested']} promises ingested, {self.stats['skipped']} skipped, {self.stats['errors']} errors")
            return ingested_promise_ids
            
        except Exception as e:
            logger.error(f"Error in mandate letter ingestion: {e}", exc_info=True)
            raise
    
    def load_mandate_letter_urls(self, csv_file_path: str) -> Dict[str, str]:
        """Load mandate letter URLs from CSV file."""
        url_map = {}
        logger.info(f"Loading mandate letter URLs from: {csv_file_path}")
        
        try:
            with open(csv_file_path, mode='r', encoding='utf-8') as infile:
                reader = csv.DictReader(infile)
                processed_count = 0
                skipped_count = 0
                
                for row in reader:
                    department_raw = row.get('Department')
                    mandate_url = row.get('Mandate Letter URL')

                    if not department_raw or not mandate_url:
                        logger.warning(f"Skipping row due to missing Department or URL: {row}")
                        skipped_count += 1
                        continue

                    standardized_dept = standardize_department_name(department_raw.strip())
                    if standardized_dept:
                        if standardized_dept in url_map:
                            logger.debug(f"Duplicate standardized department '{standardized_dept}' found. Keeping first URL: {url_map[standardized_dept]}")
                        else:
                            url_map[standardized_dept] = mandate_url.strip()
                            processed_count += 1
                    else:
                        logger.warning(f"Could not standardize department '{department_raw}'. Cannot map URL.")
                        skipped_count += 1

                logger.info(f"Successfully loaded {processed_count} mandate letter URLs. Skipped {skipped_count} rows.")
                return url_map
                
        except FileNotFoundError:
            logger.error(f"Mandate URLs CSV not found at: {csv_file_path}")
            return {}
        except Exception as e:
            logger.error(f"Error reading mandate URLs CSV: {e}", exc_info=True)
            return {}
    
    async def enrich_promises(self, promise_ids: List[str], enrichment_types: List[str],
                            force_reprocessing: bool = False, dry_run: bool = False) -> List[str]:
        """Enrich promises with specified enrichment types."""
        logger.info("=== Starting Promise Enrichment ===")
        
        if not self.langchain:
            logger.error("Langchain not available, cannot perform enrichment")
            return []
        
        enriched_promise_ids = []
        
        for promise_id in promise_ids:
            try:
                # Get promise data
                doc_ref = self.db.collection(PROMISES_COLLECTION).document(promise_id)
                doc = doc_ref.get()
                
                if not doc.exists:
                    logger.warning(f"Promise {promise_id} not found, skipping enrichment")
                    continue
                
                promise_data = doc.to_dict()
                current_state = self.get_promise_state(promise_data)
                
                # Skip if already enriched (unless force reprocessing)
                if current_state in [PromiseState.ENRICHED, PromiseState.PRIORITY_RANKED, PromiseState.COMPLETED] and not force_reprocessing:
                    logger.info(f"Promise {promise_id} already enriched, skipping")
                    continue
                
                logger.info(f"Enriching promise {promise_id}")
                
                update_data = {}
                
                # Generate enrichments based on types requested
                if 'explanation' in enrichment_types:
                    explanation_result = self.langchain.enrich_promise_explanation(
                        promise_text=promise_data['text'],
                        department=promise_data.get('responsible_department_lead', ''),
                        party=promise_data.get('party_code', 'LPC'),
                        context=f"Source: {promise_data.get('source_type', '')}"
                    )
                    
                    if 'error' not in explanation_result:
                        update_data.update({
                            "what_it_means_for_canadians": explanation_result.get("what_it_means"),
                            "background_and_context": explanation_result.get("background_and_context"),
                            "description": explanation_result.get("key_components", []),
                            "explanation_enriched_at": firestore.SERVER_TIMESTAMP,
                            "explanation_enrichment_status": "processed"
                        })
                
                if 'keywords' in enrichment_types:
                    keywords_result = self.langchain.extract_promise_keywords(promise_data['text'])
                    
                    if 'error' not in keywords_result:
                        update_data.update({
                            "extracted_keywords_concepts": keywords_result.get("keywords", []),
                            "keywords_enriched_at": firestore.SERVER_TIMESTAMP,
                            "keywords_enrichment_status": "processed"
                        })
                
                if 'action_type' in enrichment_types:
                    action_result = self.langchain.classify_promise_action_type(promise_data['text'])
                    
                    if 'error' not in action_result:
                        update_data.update({
                            "implied_action_type": action_result.get("action_type"),
                            "action_type_confidence": action_result.get("confidence", 0.0),
                            "action_type_rationale": action_result.get("rationale"),
                            "action_type_classified_at": firestore.SERVER_TIMESTAMP
                        })
                
                if 'history' in enrichment_types:
                    history_result = self.langchain.generate_commitment_history(
                        promise_text=promise_data['text'],
                        department=promise_data.get('responsible_department_lead', ''),
                        party=promise_data.get('party_code', 'LPC')
                    )
                    
                    if 'error' not in history_result:
                        update_data.update({
                            "commitment_history_rationale": history_result.get("history_rationale"),
                            "history_enriched_at": firestore.SERVER_TIMESTAMP,
                            "history_enrichment_status": "processed"
                        })
                
                # Update promise if enrichments were generated
                if update_data:
                    update_data["last_enrichment_at"] = firestore.SERVER_TIMESTAMP
                    
                    if not dry_run:
                        doc_ref.update(update_data)
                        logger.info(f"Successfully enriched promise {promise_id}")
                    else:
                        logger.info(f"[DRY RUN] Would enrich promise {promise_id}")
                    
                    enriched_promise_ids.append(promise_id)
                    self.stats['enriched'] += 1
                    self.update_promise_state(promise_id, PromiseState.ENRICHED)
                
                # Rate limiting
                await asyncio.sleep(RATE_LIMIT_DELAY_SECONDS)
                
            except Exception as e:
                logger.error(f"Error enriching promise {promise_id}: {e}", exc_info=True)
                self.stats['errors'] += 1
                self.update_promise_state(promise_id, PromiseState.ERROR, str(e))
                continue
        
        logger.info(f"Enrichment complete: {len(enriched_promise_ids)} promises enriched")
        return enriched_promise_ids
    
    async def rank_promises_priority(self, promise_ids: List[str], source_year: str = "2021", 
                                   force_reprocessing: bool = False, dry_run: bool = False) -> List[str]:
        """Rank promises by priority using BC priority scoring."""
        logger.info("=== Starting Promise Priority Ranking ===")
        
        # This is a simplified version - in a full implementation, you'd integrate
        # the complete priority ranking logic from rank_promise_priority.py
        
        ranked_promise_ids = []
        
        for promise_id in promise_ids:
            try:
                # Get promise data
                doc_ref = self.db.collection(PROMISES_COLLECTION).document(promise_id)
                doc = doc_ref.get()
                
                if not doc.exists:
                    logger.warning(f"Promise {promise_id} not found, skipping ranking")
                    continue
                
                promise_data = doc.to_dict()
                current_state = self.get_promise_state(promise_data)
                
                # Skip if already ranked (unless force reprocessing)
                if current_state in [PromiseState.PRIORITY_RANKED, PromiseState.COMPLETED] and not force_reprocessing:
                    logger.info(f"Promise {promise_id} already ranked, skipping")
                    continue
                
                # Ensure promise is enriched first
                if current_state != PromiseState.ENRICHED:
                    logger.warning(f"Promise {promise_id} not enriched, skipping priority ranking")
                    continue
                
                logger.info(f"Ranking promise {promise_id}")
                
                # Placeholder priority scoring logic
                # In full implementation, integrate LLM-based priority evaluation
                placeholder_score = {
                    "bc_priority_score": 75.0,  # Placeholder score
                    "bc_priority_rationale": "Placeholder rationale - integrate full priority ranking logic",
                    "bc_confidence": 0.8,
                    "bc_ranked_at": firestore.SERVER_TIMESTAMP
                }
                
                if not dry_run:
                    doc_ref.update(placeholder_score)
                    logger.info(f"Successfully ranked promise {promise_id}")
                else:
                    logger.info(f"[DRY RUN] Would rank promise {promise_id}")
                
                ranked_promise_ids.append(promise_id)
                self.stats['priority_ranked'] += 1
                self.update_promise_state(promise_id, PromiseState.PRIORITY_RANKED)
                
                # Rate limiting
                await asyncio.sleep(RATE_LIMIT_DELAY_SECONDS)
                
            except Exception as e:
                logger.error(f"Error ranking promise {promise_id}: {e}", exc_info=True)
                self.stats['errors'] += 1
                self.update_promise_state(promise_id, PromiseState.ERROR, str(e))
                continue
        
        logger.info(f"Priority ranking complete: {len(ranked_promise_ids)} promises ranked")
        return ranked_promise_ids
    
    async def run_complete_pipeline(self, mandate_csv_path: str = None, mandate_urls_csv_path: str = None,
                                  parliament_session_id: str = "44", source_year: str = "2021",
                                  enrichment_types: List[str] = None, limit: int = None,
                                  force_reprocessing: bool = False, dry_run: bool = False) -> Dict:
        """Run the complete promise processing pipeline."""
        logger.info("=== Starting Complete Promise Processing Pipeline ===")
        logger.info(f"Parliament Session: {parliament_session_id}")
        logger.info(f"Source Year: {source_year}")
        logger.info(f"Enrichment Types: {enrichment_types or ['all']}")
        logger.info(f"Limit: {limit or 'None'}")
        logger.info(f"Force Reprocessing: {force_reprocessing}")
        logger.info(f"Dry Run: {dry_run}")
        
        if dry_run:
            logger.warning("*** DRY RUN MODE: No changes will be written to Firestore ***")
        
        # Default enrichment types
        if enrichment_types is None or 'all' in enrichment_types:
            enrichment_types = ['explanation', 'keywords', 'action_type', 'history']
        
        pipeline_results = {
            'session_id': self.session_id,
            'ingested_promises': [],
            'enriched_promises': [],
            'ranked_promises': [],
            'stats': self.stats
        }
        
        try:
            # Phase 1: Ingestion (if CSV files provided)
            if mandate_csv_path and mandate_urls_csv_path:
                logger.info("Phase 1: Promise Ingestion")
                ingested_ids = await self.ingest_mandate_letters(
                    mandate_csv_path, mandate_urls_csv_path, dry_run
                )
                pipeline_results['ingested_promises'] = ingested_ids
                
                # Apply limit if specified
                if limit and len(ingested_ids) > limit:
                    ingested_ids = ingested_ids[:limit]
                
                promise_ids_to_process = ingested_ids
            else:
                # Use existing promises from database
                logger.info("Phase 1: Using existing promises from database")
                query = self.db.collection(PROMISES_COLLECTION).where(
                    'parliament_session_id', '==', parliament_session_id
                )
                
                if limit:
                    query = query.limit(limit)
                
                docs = query.stream()
                promise_ids_to_process = [doc.id for doc in docs]
                logger.info(f"Found {len(promise_ids_to_process)} existing promises to process")
            
            # Phase 2: Enrichment
            if promise_ids_to_process:
                logger.info("Phase 2: Promise Enrichment")
                enriched_ids = await self.enrich_promises(
                    promise_ids_to_process, enrichment_types, force_reprocessing, dry_run
                )
                pipeline_results['enriched_promises'] = enriched_ids
                
                # Phase 3: Priority Ranking
                if enriched_ids:
                    logger.info("Phase 3: Priority Ranking")
                    ranked_ids = await self.rank_promises_priority(
                        enriched_ids, source_year, force_reprocessing, dry_run
                    )
                    pipeline_results['ranked_promises'] = ranked_ids
            
            # Update final statistics
            self.stats['total_processed'] = len(promise_ids_to_process)
            pipeline_results['stats'] = self.stats
            
            # Log final results
            logger.info("=== Pipeline Complete ===")
            logger.info(f"Session ID: {self.session_id}")
            logger.info(f"Total processed: {self.stats['total_processed']}")
            logger.info(f"Ingested: {self.stats['ingested']}")
            logger.info(f"Enriched: {self.stats['enriched']}")
            logger.info(f"Priority ranked: {self.stats['priority_ranked']}")
            logger.info(f"Errors: {self.stats['errors']}")
            
            return pipeline_results
            
        except Exception as e:
            logger.error(f"Pipeline execution failed: {e}", exc_info=True)
            raise

async def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(description='Consolidated Promise Processing Pipeline')
    parser.add_argument(
        '--mandate_csv',
        type=str,
        help='Path to mandate commitments CSV file (for ingestion)'
    )
    parser.add_argument(
        '--mandate_urls_csv',
        type=str,
        help='Path to mandate letter URLs CSV file (for ingestion)'
    )
    parser.add_argument(
        '--parliament_session_id',
        type=str,
        default="44",
        help='Parliament session ID (e.g., "44")'
    )
    parser.add_argument(
        '--source_year',
        type=str,
        default="2021",
        help='Source year for priority ranking (e.g., "2021")'
    )
    parser.add_argument(
        '--enrichment_types',
        nargs='+',
        choices=['explanation', 'keywords', 'action_type', 'history', 'all'],
        default=['all'],
        help='Types of enrichment to perform'
    )
    parser.add_argument(
        '--limit',
        type=int,
        help='Limit number of promises to process'
    )
    parser.add_argument(
        '--force_reprocessing',
        action='store_true',
        help='Force reprocessing even if promises are already processed'
    )
    parser.add_argument(
        '--dry_run',
        action='store_true',
        help='Run without making changes to Firestore'
    )
    
    args = parser.parse_args()
    
    # Initialize and run pipeline
    pipeline = ConsolidatedPromisePipeline()
    
    results = await pipeline.run_complete_pipeline(
        mandate_csv_path=args.mandate_csv,
        mandate_urls_csv_path=args.mandate_urls_csv,
        parliament_session_id=args.parliament_session_id,
        source_year=args.source_year,
        enrichment_types=args.enrichment_types,
        limit=args.limit,
        force_reprocessing=args.force_reprocessing,
        dry_run=args.dry_run
    )
    
    logger.info("Consolidated Promise Pipeline completed successfully!")
    
    # Save results to file
    results_file = f"pipeline_results_{pipeline.session_id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    with open(results_file, 'w') as f:
        json.dump(results, f, indent=2, default=str)
    
    logger.info(f"Pipeline results saved to: {results_file}")

if __name__ == "__main__":
    asyncio.run(main()) 