#!/usr/bin/env python3
"""
Promise Processing Pipeline

This script provides a comprehensive pipeline for:
1. Raw document ingestion with LLM extraction
2. Promise creation and storage 
3. Complete enrichment using tested prompts
4. Priority ranking
5. Testing with promises_test collection

Uses Langchain orchestration with gemini-2.5-flash-preview-05-20
"""

import os
import sys
import logging
import asyncio
import json
import argparse
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, asdict
import uuid

import firebase_admin
from firebase_admin import firestore, credentials
from dotenv import load_dotenv

# Add lib directory to path for imports
sys.path.append(str(Path(__file__).parent.parent / 'lib'))

from langchain_config import get_langchain_instance, PromiseTrackerLangchain
from priority_ranking import PromisePriorityRanker
from common_utils import get_promise_document_path_flat, PARTY_NAME_TO_CODE_MAPPING, generate_content_hash
import hashlib
from datetime import datetime

# Load environment variables
load_dotenv()

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(filename)s:%(lineno)d - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)

def generate_human_readable_doc_id(date_issued: str, source_type: str, promise_text: str) -> str:
    """
    Generate a human-readable document ID in format: YYYYMMDD_{source}_{short_hash}
    
    Args:
        date_issued: Date in YYYY-MM-DD format
        source_type: Source type string
        promise_text: Promise text for hash generation
    
    Returns:
        Document ID string
    """
    # Convert date to YYYYMMDD format
    try:
        if '-' in date_issued:
            date_obj = datetime.strptime(date_issued, "%Y-%m-%d")
            yyyymmdd = date_obj.strftime("%Y%m%d")
        else:
            # Already in YYYYMMDD format
            yyyymmdd = date_issued
    except ValueError:
        # Fallback to current date if parsing fails
        yyyymmdd = datetime.now().strftime("%Y%m%d")
    
    # Create source code from source type
    source_clean = source_type.lower().replace(' ', '_').replace('-', '_')
    # Take first few meaningful parts
    source_parts = source_clean.split('_')[:2]  # e.g., "2025_lpc" from "2025 LPC Platform"
    source_code = '_'.join(source_parts)
    
    # Generate short hash from promise text
    short_hash = generate_content_hash(promise_text, 6)  # 6 character hash
    
    return f"{yyyymmdd}_{source_code}_{short_hash}"

@dataclass
class PromiseData:
    """Data structure for a promise."""
    # Core fields
    promise_id: str
    text: str
    source_document_url: str
    source_type: str
    
    # Metadata
    date_issued: str
    parliament_session_id: str
    candidate_or_government: str
    party_code: str
    region_code: str = "Canada"
    
    # Department info
    responsible_department_lead: Optional[str] = None
    relevant_departments: List[str] = None
    
    # Enrichment fields
    concise_title: Optional[str] = None
    what_it_means_for_canadians: Optional[List[str]] = None
    description: Optional[str] = None
    background_and_context: Optional[str] = None
    
    # Preprocessing fields
    extracted_keywords_concepts: Optional[List[str]] = None
    implied_action_type: Optional[str] = None
    commitment_history_rationale: Optional[List[Dict]] = None
    
    # Priority ranking
    bc_promise_rank: Optional[str] = None  # 'strong', 'medium', 'weak'
    bc_promise_direction: Optional[str] = None  # 'positive', 'negative', 'neutral'
    bc_promise_rank_rationale: Optional[str] = None
    
    # Timestamps
    ingested_at: Optional[datetime] = None
    explanation_enriched_at: Optional[datetime] = None
    linking_preprocessing_done_at: Optional[datetime] = None
    
    def __post_init__(self):
        if self.relevant_departments is None:
            self.relevant_departments = []
        if self.ingested_at is None:
            self.ingested_at = datetime.now(timezone.utc)

class FirebaseManager:
    """Manages Firebase connections and operations."""
    
    def __init__(self, use_test_collection: bool = False):
        self.use_test_collection = use_test_collection
        self.collection_name = "promises_test" if use_test_collection else "promises"
        self.db = self._init_firebase()
        
    def _init_firebase(self):
        """Initialize Firebase connection."""
        if not firebase_admin._apps:
            try:
                firebase_admin.initialize_app()
                project_id = os.getenv('FIREBASE_PROJECT_ID', '[Not Set - Using Default]')
                logger.info(f"Connected to Cloud Firestore (Project: {project_id}) using default credentials.")
            except Exception as e_default:
                logger.warning(f"Cloud Firestore init with default creds failed: {e_default}. Attempting service account.")
                cred_path = os.getenv('FIREBASE_SERVICE_ACCOUNT_KEY_PATH')
                if cred_path:
                    try:
                        logger.info(f"Attempting Firebase init with service account key from env var: {cred_path}")
                        cred = credentials.Certificate(cred_path)
                        firebase_admin.initialize_app(cred)
                        project_id_sa = os.getenv('FIREBASE_PROJECT_ID', '[Not Set - Using Service Account]')
                        logger.info(f"Connected to Cloud Firestore (Project: {project_id_sa}) via service account.")
                    except Exception as e_sa:
                        logger.critical(f"Firebase init with service account key from {cred_path} failed: {e_sa}")
                        raise
                else:
                    logger.critical("FIREBASE_SERVICE_ACCOUNT_KEY_PATH environment variable not set, and default creds failed.")
                    raise e_default
        
        return firestore.client()
    
    async def store_promise(self, promise_data: PromiseData) -> str:
        """Store a promise in Firestore using proper document naming."""
        try:
            # Convert to dict and handle special types
            data = asdict(promise_data)
            
            # Convert datetime objects to Firestore timestamps
            for key, value in data.items():
                if isinstance(value, datetime):
                    data[key] = value
                elif value is None:
                    data[key] = None
            
            # Add flat structure fields
            party_code = PARTY_NAME_TO_CODE_MAPPING.get(promise_data.candidate_or_government, promise_data.party_code)
            data['party_code'] = party_code
            data['region_code'] = promise_data.region_code
            
            # Generate human-readable document ID
            if self.use_test_collection:
                # For test collection, use human-readable naming too
                doc_id = generate_human_readable_doc_id(
                    promise_data.date_issued,
                    promise_data.source_type,
                    promise_data.text
                )
                doc_ref = self.db.collection(self.collection_name).document(doc_id)
            else:
                # Use human-readable naming for production as well
                doc_id = generate_human_readable_doc_id(
                    promise_data.date_issued,
                    promise_data.source_type,
                    promise_data.text
                )
                doc_ref = self.db.collection(self.collection_name).document(doc_id)
            
            await asyncio.to_thread(doc_ref.set, data)
            
            logger.info(f"Stored promise with ID: {doc_id} in collection: {self.collection_name}")
            return doc_id
            
        except Exception as e:
            logger.error(f"Error storing promise: {e}")
            raise
    
    async def get_promise(self, doc_id: str) -> Optional[PromiseData]:
        """Get a promise from Firestore."""
        try:
            doc_ref = self.db.collection(self.collection_name).document(doc_id)
            doc = await asyncio.to_thread(doc_ref.get)
            
            if doc.exists:
                data = doc.to_dict()
                # Handle potential missing fields that PromiseData expects
                expected_fields = {
                    'promise_id', 'text', 'source_document_url', 'source_type',
                    'date_issued', 'parliament_session_id', 'candidate_or_government', 'party_code'
                }
                for field in expected_fields:
                    if field not in data:
                        logger.warning(f"Missing required field '{field}' in promise {doc_id}")
                        return None
                
                return PromiseData(**data)
            return None
            
        except Exception as e:
            logger.error(f"Error getting promise {doc_id}: {e}")
            return None
    
    async def update_promise(self, doc_id: str, updates: Dict[str, Any]):
        """Update a promise in Firestore."""
        try:
            doc_ref = self.db.collection(self.collection_name).document(doc_id)
            await asyncio.to_thread(doc_ref.update, updates)
            logger.info(f"Updated promise {doc_id} with fields: {list(updates.keys())}")
            
        except Exception as e:
            logger.error(f"Error updating promise {doc_id}: {e}")
            raise

class DocumentIngestionManager:
    """Manages document ingestion and promise extraction."""
    
    def __init__(self, langchain_instance: PromiseTrackerLangchain):
        # Use the more powerful model for document ingestion
        from langchain_google_genai import ChatGoogleGenerativeAI
        self.llm = ChatGoogleGenerativeAI(
            model="models/gemini-2.5-pro-preview-05-06",
            google_api_key=langchain_instance.api_key,
            temperature=0.1,
            max_output_tokens=65536
        )
        
    def _create_extraction_prompt(self) -> str:
        """Create prompt for extracting promises from raw documents."""
        return """You are an expert analyst specializing in extracting government commitments from official documents.

Your task is to analyze the following document and extract all specific, actionable commitments made by the government or political party.

**Document Content:**
{document_content}

**Document Metadata:**
- Source Type: {source_type}
- Date: {date_issued}
- Source URL: {source_url}
- Party/Government: {entity}

**Instructions:**
1. Extract ONLY specific, actionable commitments (promises of future action)
2. Ignore general statements, descriptions of current policies, or historical information
3. Each commitment should be a distinct, measurable promise
4. Keep commitment text concise but complete (1-2 sentences max)

**Output Requirements:**
Return a JSON array of commitment objects. Each object must contain:
- "text": The commitment text (concise but complete)
- "implied_department": Best guess at responsible department (or null if unclear)
- "confidence": Confidence level (0.0-1.0) that this is a genuine commitment
- "context": Brief context explaining why this is a commitment

Example Output:
[
  {{
    "text": "Increase child care funding by $10 billion over 5 years",
    "implied_department": "Employment and Social Development Canada",
    "confidence": 0.95,
    "context": "Specific funding commitment with timeline"
  }},
  {{
    "text": "Introduce legislation to ban single-use plastics by 2025",
    "implied_department": "Environment and Climate Change Canada", 
    "confidence": 0.90,
    "context": "Legislative commitment with specific deadline"
  }}
]

If no commitments are found, return an empty array: []

Analyze the document now:"""
    
    async def extract_promises_from_document(
        self,
        document_content: str,
        source_type: str,
        source_url: str,
        date_issued: str,
        entity: str,
        parliament_session_id: str,
        party_code: str
    ) -> List[PromiseData]:
        """Extract promises from a raw document using LLM."""
        try:
            prompt = self._create_extraction_prompt()
            
            # Format the prompt with document data
            formatted_prompt = prompt.format(
                document_content=document_content,
                source_type=source_type,
                date_issued=date_issued,
                source_url=source_url,
                entity=entity
            )
            
            # Call LLM
            response = await self.llm.ainvoke(formatted_prompt)
            
            # Parse JSON response
            try:
                extracted_commitments = json.loads(response.content)
            except json.JSONDecodeError:
                # Try to extract JSON from markdown code blocks
                import re
                json_match = re.search(r'```(?:json)?\s*(\[.*?\])\s*```', response.content, re.DOTALL)
                if json_match:
                    extracted_commitments = json.loads(json_match.group(1))
                else:
                    logger.error(f"Could not parse LLM response as JSON: {response.content}")
                    return []
            
            # Convert to PromiseData objects
            promises = []
            for commitment in extracted_commitments:
                if commitment.get('confidence', 0) >= 0.7:  # Filter by confidence
                    promise_data = PromiseData(
                        promise_id=str(uuid.uuid4()),
                        text=commitment['text'],
                        source_document_url=source_url,
                        source_type=source_type,
                        date_issued=date_issued,
                        parliament_session_id=parliament_session_id,
                        candidate_or_government=entity,
                        party_code=party_code,
                        responsible_department_lead=commitment.get('implied_department'),
                        ingested_at=datetime.now(timezone.utc)
                    )
                    promises.append(promise_data)
                    
            logger.info(f"Extracted {len(promises)} high-confidence promises from document")
            return promises
            
        except Exception as e:
            logger.error(f"Error extracting promises from document: {e}")
            return []

class PromiseEnrichmentManager:
    """Manages promise enrichment using tested prompts."""
    
    def __init__(self, langchain_instance: PromiseTrackerLangchain):
        self.lc = langchain_instance
        
    async def enrich_promise_explanation(self, promise_data: PromiseData) -> Dict[str, Any]:
        """Enrich promise with explanation fields."""
        try:
            result = await asyncio.to_thread(
                self.lc.enrich_promise_explanation,
                promise_data.text,
                promise_data.responsible_department_lead or "Unknown",
                promise_data.party_code,
                f"Source: {promise_data.source_type}, Date: {promise_data.date_issued}"
            )
            
            if 'error' not in result:
                return {
                    'concise_title': result.get('concise_title'),
                    'what_it_means_for_canadians': result.get('what_it_means_for_canadians'),
                    'description': result.get('description'),
                    'background_and_context': result.get('background_and_context'),
                    'explanation_enriched_at': firestore.SERVER_TIMESTAMP
                }
            else:
                logger.error(f"Error in explanation enrichment: {result['error']}")
                return {}
                
        except Exception as e:
            logger.error(f"Error enriching promise explanation: {e}")
            return {}
    
    async def enrich_promise_preprocessing(self, promise_data: PromiseData) -> Dict[str, Any]:
        """Enrich promise with preprocessing fields (keywords, action type, history)."""
        try:
            updates = {}
            
            # Extract keywords
            keywords_result = await asyncio.to_thread(
                self.lc.extract_promise_keywords,
                promise_data.text,
                promise_data.responsible_department_lead or "Unknown"
            )
            if 'error' not in keywords_result and isinstance(keywords_result, list):
                updates['extracted_keywords_concepts'] = keywords_result
            
            # Classify action type
            action_type_result = await asyncio.to_thread(
                self.lc.classify_promise_action_type,
                promise_data.text
            )
            if 'error' not in action_type_result:
                updates['implied_action_type'] = action_type_result.get('action_type', 'other')
            
            # Generate commitment history
            history_result = await asyncio.to_thread(
                self.lc.generate_promise_history,
                promise_data.text,
                promise_data.source_type,
                promise_data.candidate_or_government,
                promise_data.date_issued
            )
            if 'error' not in history_result and isinstance(history_result, list):
                updates['commitment_history_rationale'] = history_result
            
            updates['linking_preprocessing_done_at'] = firestore.SERVER_TIMESTAMP
            
            return updates
            
        except Exception as e:
            logger.error(f"Error enriching promise preprocessing: {e}")
            return {}

class PromisePipeline:
    """Main pipeline orchestrator."""
    
    def __init__(self, use_test_collection: bool = False):
        self.firebase_manager = FirebaseManager(use_test_collection)
        self.langchain_instance = get_langchain_instance()
        self.ingestion_manager = DocumentIngestionManager(self.langchain_instance)
        self.enrichment_manager = PromiseEnrichmentManager(self.langchain_instance)
        self.priority_ranker = PromisePriorityRanker()
        
    async def ingest_document(
        self,
        document_path: str,
        source_type: str,
        source_url: str,
        date_issued: str,
        entity: str,
        parliament_session_id: str,
        party_code: str
    ) -> List[str]:
        """Ingest a document and extract promises."""
        try:
            # Read document content
            with open(document_path, 'r', encoding='utf-8') as f:
                document_content = f.read()
            
            logger.info(f"Ingesting document: {document_path}")
            
            # Extract promises
            promises = await self.ingestion_manager.extract_promises_from_document(
                document_content=document_content,
                source_type=source_type,
                source_url=source_url,
                date_issued=date_issued,
                entity=entity,
                parliament_session_id=parliament_session_id,
                party_code=party_code
            )
            
            # Store promises
            stored_ids = []
            for promise in promises:
                doc_id = await self.firebase_manager.store_promise(promise)
                stored_ids.append(doc_id)
            
            logger.info(f"Successfully ingested {len(stored_ids)} promises from document")
            return stored_ids
            
        except Exception as e:
            logger.error(f"Error in document ingestion: {e}")
            return []
    
    async def enrich_promise(self, doc_id: str, force: bool = False) -> bool:
        """Enrich a single promise with all enrichment fields."""
        try:
            # Get promise data
            promise_data = await self.firebase_manager.get_promise(doc_id)
            if not promise_data:
                logger.error(f"Promise {doc_id} not found")
                return False
            
            logger.info(f"Enriching promise: {doc_id}")
            
            # Check if enrichment needed - be more thorough
            needs_explanation = (force or 
                               promise_data.concise_title is None or 
                               promise_data.what_it_means_for_canadians is None or
                               promise_data.description is None or
                               promise_data.background_and_context is None)
            
            needs_preprocessing = (force or 
                                 promise_data.extracted_keywords_concepts is None or 
                                 promise_data.implied_action_type is None or
                                 promise_data.commitment_history_rationale is None)
                                 
            logger.info(f"Promise {doc_id} enrichment check - explanation needed: {needs_explanation}, preprocessing needed: {needs_preprocessing}")
            
            updates = {}
            
            # Explanation enrichment
            if needs_explanation:
                explanation_updates = await self.enrichment_manager.enrich_promise_explanation(promise_data)
                updates.update(explanation_updates)
                await asyncio.sleep(1)  # Rate limiting
            
            # Preprocessing enrichment
            if needs_preprocessing:
                preprocessing_updates = await self.enrichment_manager.enrich_promise_preprocessing(promise_data)
                updates.update(preprocessing_updates)
                await asyncio.sleep(1)  # Rate limiting
            
            # Priority ranking (if Canada region and LPC)
            if promise_data.region_code == "Canada" and promise_data.party_code == "LPC":
                try:
                    ranking_result = await asyncio.to_thread(
                        self.priority_ranker.rank_promise,
                        promise_data.text,
                        promise_data.responsible_department_lead or "",
                        promise_data.extracted_keywords_concepts or []
                    )
                    if ranking_result:
                        updates.update({
                            'bc_promise_rank': ranking_result.get('bc_promise_rank'),
                            'bc_promise_direction': ranking_result.get('bc_promise_direction'),
                            'bc_promise_rank_rationale': ranking_result.get('bc_promise_rank_rationale')
                        })
                except Exception as e:
                    logger.warning(f"Error in priority ranking: {e}")
            
            # Apply updates
            if updates:
                await self.firebase_manager.update_promise(doc_id, updates)
                logger.info(f"Successfully enriched promise {doc_id}")
                return True
            else:
                logger.info(f"No enrichment needed for promise {doc_id}")
                return False
                
        except Exception as e:
            logger.error(f"Error enriching promise {doc_id}: {e}")
            return False
    
    async def batch_enrich_promises(self, limit: Optional[int] = None, force: bool = False) -> Dict[str, int]:
        """Enrich multiple promises in batch."""
        try:
            # Query promises needing enrichment
            collection_ref = self.firebase_manager.db.collection(self.firebase_manager.collection_name)
            
            # Get all promises first
            query = collection_ref
            if limit:
                query = query.limit(limit)
            
            all_docs = await asyncio.to_thread(list, query.stream())
            logger.info(f"Retrieved {len(all_docs)} total promises from collection")
            
            # Filter for promises that need enrichment if not forcing
            if not force:
                docs_to_process = []
                for doc in all_docs:
                    data = doc.to_dict()
                    doc_id = doc.id
                    
                    # More comprehensive check for enrichment needs
                    needs_explanation = (
                        data.get('concise_title') is None or 
                        data.get('what_it_means_for_canadians') is None or
                        data.get('description') is None or
                        data.get('background_and_context') is None
                    )
                    
                    needs_preprocessing = (
                        data.get('extracted_keywords_concepts') is None or 
                        data.get('implied_action_type') is None or
                        data.get('commitment_history_rationale') is None
                    )
                    
                    if needs_explanation or needs_preprocessing:
                        docs_to_process.append(doc)
                        logger.debug(f"Promise {doc_id} needs enrichment - explanation: {needs_explanation}, preprocessing: {needs_preprocessing}")
                    else:
                        logger.debug(f"Promise {doc_id} appears fully enriched, skipping")
                        
                docs = docs_to_process
            else:
                docs = all_docs
                logger.info("Force mode enabled - will re-enrich all promises")
            
            logger.info(f"Found {len(docs)} promises that need enrichment (out of {len(all_docs)} total)")
            
            if len(docs) == 0:
                logger.info("No promises need enrichment")
                return {'enriched': 0, 'skipped': len(all_docs), 'errors': 0}
            
            # Process each promise
            results = {'enriched': 0, 'skipped': 0, 'errors': 0}
            
            for i, doc in enumerate(docs):
                try:
                    doc_id = doc.id
                    logger.info(f"Processing promise {i+1}/{len(docs)}: {doc_id}")
                    
                    success = await self.enrich_promise(doc_id, force)
                    if success:
                        results['enriched'] += 1
                        logger.info(f"✅ Successfully enriched {doc_id}")
                    else:
                        results['skipped'] += 1
                        logger.warning(f"⚠️ Skipped enriching {doc_id}")
                    
                    # Rate limiting between promises
                    await asyncio.sleep(2)
                    
                except Exception as e:
                    logger.error(f"❌ Error processing promise {doc.id}: {e}")
                    results['errors'] += 1
            
            logger.info(f"Batch enrichment complete: {results}")
            return results
            
        except Exception as e:
            logger.error(f"Error in batch enrichment: {e}")
            return {'enriched': 0, 'skipped': 0, 'errors': 1}
    
    def get_cost_summary(self) -> Dict[str, Any]:
        """Get cost and usage summary."""
        return self.langchain_instance.get_cost_summary()

async def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(description='Promise Processing Pipeline')
    
    subparsers = parser.add_subparsers(dest='command', help='Available commands')
    
    # Ingest command
    ingest_parser = subparsers.add_parser('ingest', help='Ingest a document and extract promises')
    ingest_parser.add_argument('document_path', help='Path to document to ingest')
    ingest_parser.add_argument('--source-type', required=True, help='Type of source document')
    ingest_parser.add_argument('--source-url', required=True, help='URL of source document')
    ingest_parser.add_argument('--date-issued', required=True, help='Date document was issued (YYYY-MM-DD)')
    ingest_parser.add_argument('--entity', required=True, help='Government/candidate that issued document')
    ingest_parser.add_argument('--parliament-session', required=True, help='Parliament session ID')
    ingest_parser.add_argument('--party-code', required=True, help='Party code (e.g., LPC, CPC)')
    ingest_parser.add_argument('--test-collection', action='store_true', help='Use test collection')
    
    # Enrich command
    enrich_parser = subparsers.add_parser('enrich', help='Enrich promises')
    enrich_parser.add_argument('--promise-id', help='Specific promise ID to enrich')
    enrich_parser.add_argument('--batch', action='store_true', help='Enrich multiple promises')
    enrich_parser.add_argument('--limit', type=int, help='Limit number of promises in batch')
    enrich_parser.add_argument('--force', action='store_true', help='Force re-enrichment')
    enrich_parser.add_argument('--test-collection', action='store_true', help='Use test collection')
    
    # Cost command
    cost_parser = subparsers.add_parser('cost', help='Show cost summary')
    
    args = parser.parse_args()
    
    if not args.command:
        parser.print_help()
        return
    
    # Initialize pipeline
    pipeline = PromisePipeline(use_test_collection=getattr(args, 'test_collection', False))
    
    if args.command == 'ingest':
        stored_ids = await pipeline.ingest_document(
            document_path=args.document_path,
            source_type=args.source_type,
            source_url=args.source_url,
            date_issued=args.date_issued,
            entity=args.entity,
            parliament_session_id=args.parliament_session,
            party_code=args.party_code
        )
        
        print(f"Ingested {len(stored_ids)} promises:")
        for doc_id in stored_ids:
            print(f"  - {doc_id}")
    
    elif args.command == 'enrich':
        if args.promise_id:
            success = await pipeline.enrich_promise(args.promise_id, args.force)
            print(f"Promise {args.promise_id} enrichment: {'Success' if success else 'Failed/Skipped'}")
        elif args.batch:
            results = await pipeline.batch_enrich_promises(args.limit, args.force)
            print(f"Batch enrichment results: {results}")
        else:
            print("Must specify either --promise-id or --batch")
    
    elif args.command == 'cost':
        cost_summary = pipeline.get_cost_summary()
        print("Cost Summary:")
        print(json.dumps(cost_summary, indent=2))
    
    # Always show final cost summary
    cost_summary = pipeline.get_cost_summary()
    print(f"\nTotal estimated cost: ${cost_summary['total_cost_usd']:.4f}")

if __name__ == "__main__":
    asyncio.run(main()) 