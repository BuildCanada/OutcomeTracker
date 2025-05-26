#!/usr/bin/env python3
"""
Consolidated Evidence Processing Pipeline

This script combines the functionality of multiple evidence processing scripts:
- process_oic_to_evidence.py (Orders in Council)
- process_gazette_p2_to_evidence.py (Canada Gazette Part II)
- process_legisinfo_to_evidence.py (LegisInfo Bills)
- process_news_to_evidence.py (News Articles)

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
logger = logging.getLogger("consolidated_evidence")

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
                app_name = 'consolidated_evidence_app'
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
EVIDENCE_COLLECTION_ROOT = os.getenv("TARGET_EVIDENCE_COLLECTION", "evidence")
RATE_LIMIT_DELAY_SECONDS = 1

# Source type mappings
SOURCE_TYPE_MAPPING = {
    'oic': {
        'collection': 'raw_oic',
        'evidence_type': 'OIC',
        'display_name': 'Orders in Council'
    },
    'gazette': {
        'collection': 'raw_gazette_p2',
        'evidence_type': 'Canada Gazette Part II',
        'display_name': 'Canada Gazette Part II'
    },
    'bills': {
        'collection': 'raw_legisinfo_bills',
        'evidence_type': 'Bill',
        'display_name': 'LegisInfo Bills'
    },
    'news': {
        'collection': 'raw_news',
        'evidence_type': 'News',
        'display_name': 'News Articles'
    }
}

class ConsolidatedEvidenceProcessor:
    """Handles all evidence processing operations using Langchain framework."""
    
    def __init__(self):
        """Initialize the processor with Langchain instance."""
        self.langchain = get_langchain_instance()
        self.stats = {
            'total_processed': 0,
            'oic_processed': 0,
            'gazette_processed': 0,
            'bills_processed': 0,
            'news_processed': 0,
            'errors': 0,
            'skipped': 0
        }
    
    async def query_raw_items_for_processing(self, source_type: str, limit: int = None, 
                                           force_reprocessing: bool = False) -> List[Dict[str, Any]]:
        """Query raw items that need processing."""
        logger.info(f"Querying {source_type} items for processing: limit={limit}, force={force_reprocessing}")
        
        if source_type not in SOURCE_TYPE_MAPPING:
            logger.error(f"Unknown source type: {source_type}")
            return []
        
        source_config = SOURCE_TYPE_MAPPING[source_type]
        collection_name = source_config['collection']
        
        try:
            # Build query for unprocessed items
            query = db.collection(collection_name)
            
            # Filter for items that haven't been processed (unless force reprocessing)
            if not force_reprocessing:
                query = query.where(filter=firestore.FieldFilter("evidence_processing_status", "==", None))
            
            if limit:
                query = query.limit(limit)
            
            # Execute query
            raw_docs = list(await asyncio.to_thread(query.stream))
            
            items = []
            for doc in raw_docs:
                data = doc.to_dict()
                if data:
                    items.append({
                        "id": doc.id,
                        "doc_ref": doc.reference,
                        "data": data,
                        "source_type": source_type
                    })
                else:
                    logger.warning(f"Empty data for {source_type} item {doc.id}, skipping.")
            
            logger.info(f"Retrieved {len(items)} {source_type} items for processing")
            return items
            
        except Exception as e:
            logger.error(f"Error querying {source_type} items: {e}", exc_info=True)
            return []
    
    def prepare_evidence_data_oic(self, raw_item: Dict[str, Any]) -> Dict[str, Any]:
        """Prepare OIC data for evidence processing."""
        data = raw_item['data']
        return {
            'document_id': raw_item['id'],
            'title': data.get('title', ''),
            'content': data.get('full_text', ''),
            'date': data.get('registration_date'),
            'pc_number': data.get('pc_number'),
            'enabling_authority': data.get('enabling_authority'),
            'source_url': data.get('source_url'),
            'source_type': 'OIC'
        }
    
    def prepare_evidence_data_gazette(self, raw_item: Dict[str, Any]) -> Dict[str, Any]:
        """Prepare Gazette data for evidence processing."""
        data = raw_item['data']
        return {
            'document_id': raw_item['id'],
            'title': data.get('title', ''),
            'content': data.get('full_text', ''),
            'date': data.get('registration_date'),
            'department': data.get('department'),
            'regulation_type': data.get('regulation_type'),
            'source_url': data.get('source_url'),
            'source_type': 'Canada Gazette Part II'
        }
    
    def prepare_evidence_data_bills(self, raw_item: Dict[str, Any]) -> Dict[str, Any]:
        """Prepare Bills data for evidence processing."""
        data = raw_item['data']
        return {
            'document_id': raw_item['id'],
            'title': data.get('long_title', ''),
            'short_title': data.get('short_title', ''),
            'content': data.get('summary', ''),
            'bill_number': data.get('bill_number'),
            'parliament_session': data.get('parliament_session'),
            'sponsor': data.get('sponsor'),
            'status': data.get('status'),
            'source_url': data.get('source_url'),
            'source_type': 'Bill'
        }
    
    def prepare_evidence_data_news(self, raw_item: Dict[str, Any]) -> Dict[str, Any]:
        """Prepare News data for evidence processing."""
        data = raw_item['data']
        return {
            'document_id': raw_item['id'],
            'title': data.get('title', ''),
            'content': data.get('content', ''),
            'date': data.get('published_date'),
            'source': data.get('source'),
            'author': data.get('author'),
            'category': data.get('category'),
            'source_url': data.get('url'),
            'source_type': 'News'
        }
    
    async def process_single_evidence_item(self, raw_item: Dict[str, Any], dry_run: bool = False) -> bool:
        """Process a single evidence item through LLM analysis."""
        try:
            source_type = raw_item['source_type']
            item_id = raw_item['id']
            
            logger.debug(f"Processing {source_type} item {item_id}")
            
            # Prepare data based on source type
            if source_type == 'oic':
                evidence_data = self.prepare_evidence_data_oic(raw_item)
            elif source_type == 'gazette':
                evidence_data = self.prepare_evidence_data_gazette(raw_item)
            elif source_type == 'bills':
                evidence_data = self.prepare_evidence_data_bills(raw_item)
            elif source_type == 'news':
                evidence_data = self.prepare_evidence_data_news(raw_item)
            else:
                logger.error(f"Unknown source type: {source_type}")
                return False
            
            # Skip if no content
            if not evidence_data.get('content') and not evidence_data.get('title'):
                logger.warning(f"No content or title for {source_type} item {item_id}, skipping")
                self.stats['skipped'] += 1
                return True
            
            # Process through LLM
            result = self.langchain.process_evidence_item(source_type, evidence_data)
            
            if 'error' in result:
                logger.error(f"Error processing {source_type} item {item_id}: {result['error']}")
                self.stats['errors'] += 1
                
                # Update raw item with error status
                if not dry_run:
                    await asyncio.to_thread(raw_item['doc_ref'].update, {
                        "evidence_processing_status": "failed",
                        "evidence_processing_error": result['error'],
                        "evidence_processed_at": firestore.SERVER_TIMESTAMP
                    })
                return False
            
            # Create evidence document
            evidence_doc = {
                **evidence_data,
                **result,
                "raw_item_id": item_id,
                "evidence_type": SOURCE_TYPE_MAPPING[source_type]['evidence_type'],
                "parliament_session_id": "44",  # Default for now
                "processing_model": self.langchain.model_name,
                "processed_at": firestore.SERVER_TIMESTAMP,
                "evidence_linking_status": "unprocessed"
            }
            
            # Save evidence document and update raw item
            if not dry_run:
                # Create evidence document
                evidence_ref = db.collection(EVIDENCE_COLLECTION_ROOT).document()
                await asyncio.to_thread(evidence_ref.set, evidence_doc)
                
                # Update raw item status
                await asyncio.to_thread(raw_item['doc_ref'].update, {
                    "evidence_processing_status": "processed",
                    "evidence_id": evidence_ref.id,
                    "evidence_processed_at": firestore.SERVER_TIMESTAMP
                })
                
                logger.info(f"Successfully processed {source_type} item {item_id} -> evidence {evidence_ref.id}")
            else:
                logger.info(f"[DRY RUN] Would create evidence document for {source_type} item {item_id}")
            
            # Update stats
            self.stats['total_processed'] += 1
            self.stats[f'{source_type}_processed'] += 1
            
            return True
            
        except Exception as e:
            logger.error(f"Error processing evidence item {raw_item['id']}: {e}", exc_info=True)
            self.stats['errors'] += 1
            return False
    
    async def run_evidence_processing_pipeline(self, source_types: List[str], limit: int = None,
                                             force_reprocessing: bool = False, dry_run: bool = False) -> Dict[str, Any]:
        """Run the complete evidence processing pipeline."""
        logger.info("=== Starting Consolidated Evidence Processing Pipeline ===")
        logger.info(f"Source Types: {source_types}")
        logger.info(f"Limit per type: {limit or 'None'}")
        logger.info(f"Force Reprocessing: {force_reprocessing}")
        logger.info(f"Dry Run: {dry_run}")
        
        if dry_run:
            logger.warning("*** DRY RUN MODE: No changes will be written to Firestore ***")
        
        total_items = 0
        
        # Process each source type
        for source_type in source_types:
            logger.info(f"\n--- Processing {SOURCE_TYPE_MAPPING[source_type]['display_name']} ---")
            
            # Query raw items
            raw_items = await self.query_raw_items_for_processing(
                source_type=source_type,
                limit=limit,
                force_reprocessing=force_reprocessing
            )
            
            if not raw_items:
                logger.info(f"No {source_type} items found for processing")
                continue
            
            total_items += len(raw_items)
            logger.info(f"Processing {len(raw_items)} {source_type} items...")
            
            # Process each item
            for i, raw_item in enumerate(raw_items):
                logger.info(f"Processing {source_type} {i+1}/{len(raw_items)}: {raw_item['id']}")
                
                success = await self.process_single_evidence_item(raw_item, dry_run)
                
                if not success:
                    logger.warning(f"Failed to process {source_type} item {raw_item['id']}")
                
                # Rate limiting between items
                if i < len(raw_items) - 1:
                    await asyncio.sleep(RATE_LIMIT_DELAY_SECONDS)
        
        # Log final statistics
        logger.info("\n=== Evidence Processing Pipeline Complete ===")
        logger.info(f"Total items processed: {self.stats['total_processed']}")
        logger.info(f"OIC processed: {self.stats['oic_processed']}")
        logger.info(f"Gazette processed: {self.stats['gazette_processed']}")
        logger.info(f"Bills processed: {self.stats['bills_processed']}")
        logger.info(f"News processed: {self.stats['news_processed']}")
        logger.info(f"Items skipped: {self.stats['skipped']}")
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
    parser = argparse.ArgumentParser(description='Consolidated Evidence Processing Pipeline')
    parser.add_argument(
        '--source_types',
        nargs='+',
        choices=['oic', 'gazette', 'bills', 'news', 'all'],
        default=['all'],
        help='Types of evidence sources to process'
    )
    parser.add_argument(
        '--limit',
        type=int,
        help='Limit number of items per source type to process'
    )
    parser.add_argument(
        '--force_reprocessing',
        action='store_true',
        help='Force reprocessing even if evidence already exists'
    )
    parser.add_argument(
        '--dry_run',
        action='store_true',
        help='Run without making changes to Firestore'
    )
    
    args = parser.parse_args()
    
    # Handle 'all' source type
    if 'all' in args.source_types:
        source_types = ['oic', 'gazette', 'bills', 'news']
    else:
        source_types = args.source_types
    
    # Run evidence processing pipeline
    processor = ConsolidatedEvidenceProcessor()
    stats = await processor.run_evidence_processing_pipeline(
        source_types=source_types,
        limit=args.limit,
        force_reprocessing=args.force_reprocessing,
        dry_run=args.dry_run
    )
    
    logger.info("Evidence processing pipeline completed successfully!")

if __name__ == "__main__":
    asyncio.run(main()) 