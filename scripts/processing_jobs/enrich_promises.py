#!/usr/bin/env python3
"""
Promise Enrichment Script

Enriches promises with AI-generated content including explanations, keywords, 
action types, and historical context using LangChain.

Usage:
    python enrich_promises.py --parliament_session 45 --limit 10
    python enrich_promises.py --promise_ids "LPC-001,LPC-002,LPC-003"
    python enrich_promises.py --enrichment_types explanation,keywords --force_reprocessing
"""

import os
import sys
import logging
import argparse
import asyncio
from datetime import datetime
from typing import List, Optional, Dict
from dotenv import load_dotenv
import firebase_admin
from firebase_admin import credentials, firestore

# Add parent directory to path for imports
scripts_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
project_dir = os.path.dirname(scripts_dir)
lib_dir = os.path.join(project_dir, 'lib')

sys.path.append(scripts_dir)
sys.path.append(project_dir)
sys.path.append(lib_dir)

# Fix logger initialization order
load_dotenv()

# Logger setup
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(filename)s:%(lineno)d - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger("enrich_promises")

try:
    from langchain_config import get_langchain_instance
    langchain_available = True
    logger.info("✅ Successfully imported langchain_config")
except ImportError as e:
    logger.warning(f"langchain_config not available: {e}")
    langchain_available = False
    get_langchain_instance = None

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
                firebase_admin.initialize_app(cred, name='enrich_promises')
                project_id_sa = os.getenv('FIREBASE_PROJECT_ID', '[Not Set - Using Service Account]')
                logger.info(f"Connected to CLOUD Firestore (Project: {project_id_sa}) via service account.")
                db = firestore.client(app=firebase_admin.get_app(name='enrich_promises'))
            except Exception as e_sa:
                logger.critical(f"Firebase init with service account key from {cred_path} failed: {e_sa}", exc_info=True)
        else:
            logger.warning("FIREBASE_SERVICE_ACCOUNT_KEY_PATH environment variable not set, and default creds failed.")

if db is None:
    logger.critical("CRITICAL: Failed to obtain Firestore client. Exiting.")
    exit("Exiting: Firestore client not available.")

# Default constants (can be overridden by command line args)
DEFAULT_PROMISES_COLLECTION = 'promises'
RATE_LIMIT_DELAY_SECONDS = 2

class PromiseEnricher:
    """Handles promise enrichment using LangChain."""
    
    def __init__(self, collection_name: str = DEFAULT_PROMISES_COLLECTION):
        """Initialize the enricher."""
        self.db = db
        self.collection_name = collection_name
        self.langchain = None
        
        if langchain_available:
            try:
                self.langchain = get_langchain_instance()
                logger.info("✅ LangChain initialized successfully")
            except Exception as e:
                logger.error(f"❌ Failed to initialize LangChain: {e}")
                self.langchain = None
        
        if not self.langchain:
            logger.error("❌ LangChain not available - enrichment will not work")
        
        self.stats = {
            'total_processed': 0,
            'enriched': 0,
            'skipped': 0,
            'errors': 0
        }
    
    def get_promises_to_enrich(self, parliament_session: Optional[str] = None, 
                             promise_ids: Optional[List[str]] = None, 
                             limit: Optional[int] = None) -> List[Dict]:
        """Get promises that need enrichment."""
        
        promises = []
        
        if promise_ids:
            # Get specific promises by ID
            logger.info(f"🔍 Fetching {len(promise_ids)} specific promises...")
            for promise_id in promise_ids:
                try:
                    doc_ref = self.db.collection(self.collection_name).document(promise_id)
                    doc = doc_ref.get()
                    if doc.exists:
                        promise_data = doc.to_dict()
                        promise_data['doc_id'] = doc.id
                        promises.append(promise_data)
                    else:
                        logger.warning(f"⚠️  Promise {promise_id} not found")
                except Exception as e:
                    logger.error(f"❌ Error fetching promise {promise_id}: {e}")
        else:
            # Query promises by parliament session
            logger.info(f"🔍 Querying promises for parliament session: {parliament_session or 'all'}")
            
            query = self.db.collection(self.collection_name)
            if parliament_session:
                query = query.where('parliament_session_id', '==', parliament_session)
            
            if limit:
                query = query.limit(limit)
            
            docs = query.stream()
            for doc in docs:
                promise_data = doc.to_dict()
                promise_data['doc_id'] = doc.id
                promises.append(promise_data)
        
        logger.info(f"📋 Found {len(promises)} promises to process")
        return promises
    
    def is_enrichment_needed(self, promise_data: Dict, enrichment_types: List[str], 
                           force_reprocessing: bool = False) -> bool:
        """Check if a promise needs enrichment."""
        
        if force_reprocessing:
            return True
        
        # Check each enrichment type
        for enrichment_type in enrichment_types:
            if enrichment_type == 'explanation':
                if not promise_data.get('what_it_means_for_canadians'):
                    return True
            elif enrichment_type == 'keywords':
                if not promise_data.get('extracted_keywords_concepts'):
                    return True
            elif enrichment_type == 'action_type':
                if not promise_data.get('implied_action_type'):
                    return True
            elif enrichment_type == 'history':
                if not promise_data.get('commitment_history_rationale'):
                    return True
        
        return False
    
    async def enrich_single_promise(self, promise_data: Dict, enrichment_types: List[str], 
                                  force_reprocessing: bool = False, dry_run: bool = False) -> Dict:
        """Enrich a single promise."""
        
        promise_id = promise_data.get('promise_id', promise_data.get('doc_id', 'unknown'))
        
        try:
            if not self.langchain:
                raise Exception("LangChain not available")
            
            # Check if enrichment is needed
            if not self.is_enrichment_needed(promise_data, enrichment_types, force_reprocessing):
                logger.info(f"   ⏭️  {promise_id}: Already enriched, skipping")
                return {'success': True, 'skipped': True}
            
            logger.info(f"   🔧 {promise_id}: Starting enrichment...")
            
            update_data = {}
            
            # Generate enrichments based on types requested
            if 'explanation' in enrichment_types:
                try:
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
                        logger.info(f"     ✅ Explanation generated")
                    else:
                        logger.warning(f"     ⚠️  Explanation failed: {explanation_result.get('error')}")
                except Exception as e:
                    logger.error(f"     ❌ Explanation error: {e}")
            
            if 'keywords' in enrichment_types:
                try:
                    keywords_result = self.langchain.extract_promise_keywords(
                        promise_text=promise_data['text'],
                        department=promise_data.get('responsible_department_lead', '')
                    )
                    
                    # Handle both list and dict responses from keywords extraction
                    if isinstance(keywords_result, list):
                        # Direct list response
                        keywords_list = keywords_result
                        error = None
                    elif isinstance(keywords_result, dict) and 'error' not in keywords_result:
                        # Dict response with keywords key
                        keywords_list = keywords_result.get("keywords", keywords_result.get("concepts", []))
                        error = None
                    else:
                        # Error response
                        keywords_list = []
                        error = keywords_result.get('error', 'Unknown error') if isinstance(keywords_result, dict) else 'Invalid response format'
                    
                    if not error:
                        update_data.update({
                            "extracted_keywords_concepts": keywords_list,
                            "keywords_enriched_at": firestore.SERVER_TIMESTAMP,
                            "keywords_enrichment_status": "processed"
                        })
                        logger.info(f"     ✅ Keywords extracted: {len(keywords_list)}")
                    else:
                        logger.warning(f"     ⚠️  Keywords failed: {error}")
                except Exception as e:
                    logger.error(f"     ❌ Keywords error: {e}")
            
            if 'action_type' in enrichment_types:
                try:
                    action_result = self.langchain.classify_promise_action_type(promise_data['text'])
                    
                    if 'error' not in action_result:
                        update_data.update({
                            "implied_action_type": action_result.get("action_type"),
                            "action_type_confidence": action_result.get("confidence", 0.0),
                            "action_type_rationale": action_result.get("rationale"),
                            "action_type_classified_at": firestore.SERVER_TIMESTAMP
                        })
                        logger.info(f"     ✅ Action type: {action_result.get('action_type')}")
                    else:
                        logger.warning(f"     ⚠️  Action type failed: {action_result.get('error')}")
                except Exception as e:
                    logger.error(f"     ❌ Action type error: {e}")
            
            if 'history' in enrichment_types:
                try:
                    history_result = self.langchain.generate_promise_history(
                        promise_text=promise_data['text'],
                        source_type=promise_data.get('source_type', ''),
                        entity=promise_data.get('party', 'Liberal Party of Canada'),
                        date_issued=promise_data.get('date_issued', '')
                    )
                    
                    if 'error' not in history_result:
                        update_data.update({
                            "commitment_history_rationale": history_result.get("history_rationale"),
                            "history_enriched_at": firestore.SERVER_TIMESTAMP,
                            "history_enrichment_status": "processed"
                        })
                        logger.info(f"     ✅ History generated")
                    else:
                        logger.warning(f"     ⚠️  History failed: {history_result.get('error')}")
                except Exception as e:
                    logger.error(f"     ❌ History error: {e}")
            
            # Update promise if enrichments were generated
            if update_data:
                update_data["last_enrichment_at"] = firestore.SERVER_TIMESTAMP
                
                if not dry_run:
                    doc_ref = self.db.collection(self.collection_name).document(promise_data['doc_id'])
                    doc_ref.update(update_data)
                    logger.info(f"   ✅ {promise_id}: Successfully enriched with {len(update_data)} fields")
                else:
                    logger.info(f"   🔄 {promise_id}: [DRY RUN] Would update {len(update_data)} fields")
                
                return {'success': True, 'enriched': True, 'fields_updated': len(update_data)}
            else:
                logger.warning(f"   ⚠️  {promise_id}: No enrichments generated")
                return {'success': False, 'error': 'No enrichments generated'}
            
        except Exception as e:
            logger.error(f"   ❌ {promise_id}: Error during enrichment: {e}", exc_info=True)
            return {'success': False, 'error': str(e)}
    
    async def enrich_promises(self, parliament_session: Optional[str] = None,
                            promise_ids: Optional[List[str]] = None,
                            enrichment_types: List[str] = None,
                            limit: Optional[int] = None,
                            force_reprocessing: bool = False,
                            dry_run: bool = False) -> Dict:
        """Enrich multiple promises."""
        
        if enrichment_types is None:
            enrichment_types = ['explanation', 'keywords', 'action_type', 'history']
        
        logger.info("🚀 " + "="*50)
        logger.info("🚀 STARTING PROMISE ENRICHMENT")
        logger.info("🚀 " + "="*50)
        logger.info(f"🏛️  Parliament Session: {parliament_session or 'All'}")
        logger.info(f"🆔 Promise IDs: {promise_ids or 'Query-based'}")
        logger.info(f"🔧 Enrichment Types: {enrichment_types}")
        logger.info(f"🔢 Limit: {limit or 'None'}")
        logger.info(f"🔄 Force Reprocessing: {force_reprocessing}")
        logger.info(f"🧪 Dry Run: {dry_run}")
        logger.info("=" * 60)
        
        if dry_run:
            logger.warning("⚠️  *** DRY RUN MODE: No changes will be written to Firestore ***")
        
        # Get promises to enrich
        promises = self.get_promises_to_enrich(parliament_session, promise_ids, limit)
        
        if not promises:
            logger.warning("⚠️  No promises found to enrich")
            return {'success': False, 'message': 'No promises found'}
        
        # Process each promise
        enriched_promises = []
        for i, promise_data in enumerate(promises, 1):
            logger.info(f"🔄 [{i}/{len(promises)}] Processing promise...")
            
            result = await self.enrich_single_promise(
                promise_data, enrichment_types, force_reprocessing, dry_run
            )
            
            if result['success']:
                if result.get('skipped'):
                    self.stats['skipped'] += 1
                elif result.get('enriched'):
                    self.stats['enriched'] += 1
                    enriched_promises.append(promise_data.get('promise_id', promise_data.get('doc_id')))
            else:
                self.stats['errors'] += 1
            
            self.stats['total_processed'] += 1
            
            # Rate limiting
            await asyncio.sleep(RATE_LIMIT_DELAY_SECONDS)
        
        # Final summary
        logger.info("🎉 " + "="*50)
        logger.info("🎉 PROMISE ENRICHMENT COMPLETE!")
        logger.info("🎉 " + "="*50)
        logger.info(f"📊 Total processed: {self.stats['total_processed']}")
        logger.info(f"🔧 Enriched: {self.stats['enriched']}")
        logger.info(f"⏭️  Skipped: {self.stats['skipped']}")
        logger.info(f"❌ Errors: {self.stats['errors']}")
        logger.info("=" * 60)
        
        return {
            'success': True,
            'stats': self.stats,
            'enriched_promises': enriched_promises
        }

async def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(description='Enrich promises with AI-generated content')
    parser.add_argument(
        '--collection_name',
        type=str,
        default=DEFAULT_PROMISES_COLLECTION,
        help=f'Firestore collection name (default: {DEFAULT_PROMISES_COLLECTION})'
    )
    parser.add_argument(
        '--parliament_session',
        type=str,
        help='Parliament session ID (e.g., "44", "45")'
    )
    parser.add_argument(
        '--promise_ids',
        type=str,
        help='Comma-separated list of specific promise IDs to enrich'
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
        help='Force reprocessing even if promises are already enriched'
    )
    parser.add_argument(
        '--dry_run',
        action='store_true',
        help='Run without making changes to Firestore'
    )
    
    args = parser.parse_args()
    
    # Parse promise IDs if provided
    promise_ids = None
    if args.promise_ids:
        promise_ids = [pid.strip() for pid in args.promise_ids.split(',')]
    
    # Handle 'all' enrichment types
    enrichment_types = args.enrichment_types
    if 'all' in enrichment_types:
        enrichment_types = ['explanation', 'keywords', 'action_type', 'history']
    
    # Initialize and run enricher
    enricher = PromiseEnricher(collection_name=args.collection_name)
    
    results = await enricher.enrich_promises(
        parliament_session=args.parliament_session,
        promise_ids=promise_ids,
        enrichment_types=enrichment_types,
        limit=args.limit,
        force_reprocessing=args.force_reprocessing,
        dry_run=args.dry_run
    )
    
    if results['success']:
        logger.info("✅ Promise enrichment completed successfully!")
    else:
        logger.error("❌ Promise enrichment failed")

if __name__ == "__main__":
    asyncio.run(main()) 