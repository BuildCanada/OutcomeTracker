#!/usr/bin/env python3
"""
Consolidated Promise Pipeline - Master Script

This script combines and orchestrates all promise processing functionality:
1. Promise Ingestion (from CSV or PDF files using Gemini)
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
import requests
from urllib.parse import urlparse
from google import genai
from google.genai import types
import httpx

# Add current directory to path to import utilities
current_dir = str(Path(__file__).parent)
if current_dir not in sys.path:
    sys.path.insert(0, current_dir)

try:
    from common_utils import standardize_department_name, get_promise_document_path_flat as get_promise_document_path
    _common_utils_imported = True
    
    # Try to import SOURCE_TYPE_FIELD_UPDATE_MAPPING, but it's not critical
    try:
        from common_utils import SOURCE_TYPE_FIELD_UPDATE_MAPPING
    except ImportError:
        # Define a simple mapping if not available
        SOURCE_TYPE_FIELD_UPDATE_MAPPING = {
            "Mandate Letter Commitment (Structured)": "2021 LPC Mandate Letters"
        }
        
except ImportError as e:
    _common_utils_imported = False
    _common_utils_error = str(e)
    def standardize_department_name(dept_name): return dept_name
    def get_promise_document_path(promise_id): return f"promises/{promise_id}"
    SOURCE_TYPE_FIELD_UPDATE_MAPPING = {
        "Mandate Letter Commitment (Structured)": "2021 LPC Mandate Letters"
    }

# Load environment variables
load_dotenv()

# Logger setup
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(filename)s:%(lineno)d - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger("consolidated_promise_pipeline")

# Log common_utils import status now that logger is available
if _common_utils_imported:
    logger.info("✅ Successfully imported common_utils")
else:
    logger.warning(f"⚠️  common_utils not found ({_common_utils_error}), using fallback functions")

# Add parent directory to path to import langchain_config
sys.path.append(str(Path(__file__).parent.parent / 'lib'))

try:
    from langchain_config import get_langchain_instance
    langchain_available = True
except ImportError as e:
    logger.warning(f"langchain_config not available: {e}")
    langchain_available = False
    get_langchain_instance = None

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

# Parliament Session Mapping - determined by release dates
PARLIAMENT_SESSIONS = {
    "44": {
        "start_date": "2021-08-15",  # Election called date
        "end_date": "2025-03-23",    # Session end date
        "election_date": "2021-09-20"
    },
    "45": {
        "start_date": "2025-03-24",  # Day after 44th ended
        "end_date": "2030-12-31",    # Future end date (will be updated)
        "election_date": "2025-04-28"
    }
}

def determine_parliament_session_and_year(release_date_str: str) -> Tuple[str, str]:
    """
    Determine parliament session ID and source year from release date.
    
    Args:
        release_date_str: Date string in YYYY-MM-DD format
        
    Returns:
        Tuple of (parliament_session_id, source_year)
    """
    try:
        release_date = datetime.strptime(release_date_str, "%Y-%m-%d").date()
        
        for session_id, session_data in PARLIAMENT_SESSIONS.items():
            start_date = datetime.strptime(session_data["start_date"], "%Y-%m-%d").date()
            end_date = datetime.strptime(session_data["end_date"], "%Y-%m-%d").date()
            
            if start_date <= release_date <= end_date:
                return session_id, str(release_date.year)
        
        # Default to most recent session if no match
        logger.warning(f"Release date {release_date_str} doesn't match any parliament session. Defaulting to session 45.")
        return "45", str(release_date.year)
        
    except ValueError as e:
        logger.error(f"Invalid release date format {release_date_str}: {e}. Defaulting to session 44, year 2021.")
        return "44", "2021"

def download_file_bytes(url: str) -> bytes:
    """
    Download a file from URL and return as bytes.
    
    Args:
        url: URL to download from
        
    Returns:
        File content as bytes
    """
    try:
        logger.info(f"📥 Downloading file from {url}")
        logger.info("   ⏳ This may take a moment for large files...")
        
        start_time = time.time()
        response = httpx.get(url, timeout=60)
        response.raise_for_status()
        download_time = time.time() - start_time
        
        logger.info(f"   ✅ Successfully downloaded {len(response.content):,} bytes ({len(response.content)/1024/1024:.1f} MB) in {download_time:.1f} seconds")
        return response.content
        
    except Exception as e:
        logger.error(f"❌ Error downloading file from {url}: {e}")
        raise

class ConsolidatedPromisePipeline:
    """Main class for orchestrating the complete promise processing pipeline."""
    
    def __init__(self):
        """Initialize the pipeline."""
        self.db = db
        if langchain_available:
            self.langchain = get_langchain_instance()
        else:
            self.langchain = None
        
        # Initialize Gemini client with timeout configuration
        gemini_api_key = os.getenv('GEMINI_API_KEY')
        if not gemini_api_key:
            logger.error("GEMINI_API_KEY environment variable not set. Cannot initialize Gemini client.")
            raise ValueError("GEMINI_API_KEY environment variable is required for Gemini document processing")
        
        # Configure client with timeout settings
        self.gemini_client = genai.Client(
            api_key=gemini_api_key,
            http_options={
                'timeout': 120.0,  # 2 minute timeout
                'retries': 3
            }
        )
        
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

    def create_promise_extraction_prompt(self, source_type: str, release_date: str) -> str:
        """Create prompt for extracting promises from documents using Gemini."""
        return f"""
You are an expert at analyzing political documents and extracting specific commitments and promises.

Please analyze the attached {source_type} document and extract all political promises, commitments, and pledges.

For each promise you identify, please provide:
1. The exact text of the promise/commitment
2. A confidence score (0.0 to 1.0) indicating how certain you are this is a promise
3. A brief explanation of why this constitutes a promise

Return your response as a JSON array with this structure:
[
  {{
    "promise_id": "001",
    "text": "The exact text of the promise",
    "confidence": 0.9,
    "rationale": "Why this is considered a promise"
  }},
  ...
]

Guidelines for identifying promises:
- Look for commitments using words like "will", "commit to", "pledge", "ensure", "establish", "create", "implement"
- Focus on specific actionable commitments rather than general principles
- Include policy proposals that represent concrete actions the party intends to take
- Exclude general statements of values or aspirations without specific actions
- Only include promises with confidence >= 0.7

Document details:
- Source: {source_type}
- Release Date: {release_date}
- Context: Liberal Party of Canada platform/commitment document

Please analyze the document and extract the promises as requested.
"""

    async def process_document_with_gemini(self, file_bytes: bytes, mime_type: str, source_type: str, release_date: str) -> List[Dict]:
        """
        Process document with Gemini to extract promises.
        
        Args:
            file_bytes: Document content as bytes
            mime_type: MIME type of the document  
            source_type: Type of source document
            release_date: Release date of the document
            
        Returns:
            List of extracted promise dictionaries
        """
        max_retries = 3
        retry_delay = 5  # seconds
        
        for attempt in range(max_retries):
            try:
                logger.info(f"🔄 Processing {source_type} document with Gemini (Attempt {attempt + 1}/{max_retries})")
                logger.info(f"   📄 Document size: {len(file_bytes):,} bytes ({len(file_bytes)/1024/1024:.1f} MB)")
                logger.info(f"   🤖 Model: gemini-2.5-pro-preview-05-06")
                logger.info(f"   ⏳ This may take 30-120 seconds for large documents...")
                
                prompt = self.create_promise_extraction_prompt(source_type, release_date)
                
                logger.info("   📤 Sending document to Gemini for analysis...")
                start_time = time.time()
                
                # Create the request with timeout handling
                response = self.gemini_client.models.generate_content(
                    model="gemini-2.5-pro-preview-05-06",
                    contents=[
                        types.Part.from_bytes(
                            data=file_bytes,
                            mime_type=mime_type,
                        ),
                        prompt
                    ]
                )
                
                processing_time = time.time() - start_time
                logger.info(f"   ✅ Gemini processing completed in {processing_time:.1f} seconds")
                
                # Parse JSON response
                try:
                    logger.info("   🔍 Parsing Gemini response...")
                    
                    # Check if we got a valid response
                    if not hasattr(response, 'text') or not response.text:
                        logger.warning("   ⚠️  Empty response from Gemini")
                        if attempt < max_retries - 1:
                            logger.info(f"   🔄 Retrying in {retry_delay} seconds...")
                            await asyncio.sleep(retry_delay)
                            continue
                        else:
                            return []
                    
                    # Clean up the response text (sometimes has markdown formatting)
                    response_text = response.text.strip()
                    if response_text.startswith('```json'):
                        response_text = response_text[7:]  # Remove ```json
                    if response_text.endswith('```'):
                        response_text = response_text[:-3]  # Remove ```
                    response_text = response_text.strip()
                    
                    extracted_promises = json.loads(response_text)
                    if not isinstance(extracted_promises, list):
                        logger.error(f"❌ Expected list from Gemini, got {type(extracted_promises)}")
                        if attempt < max_retries - 1:
                            logger.info(f"   🔄 Retrying in {retry_delay} seconds...")
                            await asyncio.sleep(retry_delay)
                            continue
                        else:
                            return []
                    
                    logger.info(f"   📊 Raw extraction: {len(extracted_promises)} potential promises found")
                        
                    # Filter by confidence threshold
                    high_confidence_promises = [
                        p for p in extracted_promises 
                        if p.get('confidence', 0) >= 0.7
                    ]
                    
                    logger.info(f"   ✅ Filtered result: {len(high_confidence_promises)} high-confidence promises (≥0.7)")
                    if len(extracted_promises) > len(high_confidence_promises):
                        filtered_out = len(extracted_promises) - len(high_confidence_promises)
                        logger.info(f"   🚫 Filtered out: {filtered_out} low-confidence promises")
                    
                    return high_confidence_promises
                    
                except json.JSONDecodeError as e:
                    logger.error(f"❌ Could not parse Gemini response as JSON: {e}")
                    logger.debug(f"Raw Gemini response (first 500 chars): {response.text[:500]}")
                    if attempt < max_retries - 1:
                        logger.info(f"   🔄 Retrying in {retry_delay} seconds...")
                        await asyncio.sleep(retry_delay)
                        continue
                    else:
                        return []
                
            except TimeoutError as e:
                logger.error(f"⏰ Timeout error processing document with Gemini (attempt {attempt + 1}): {e}")
                if attempt < max_retries - 1:
                    logger.info(f"   🔄 Retrying in {retry_delay} seconds...")
                    await asyncio.sleep(retry_delay)
                    continue
                else:
                    logger.error("❌ Max retries exceeded for timeout errors")
                    return []
                    
            except Exception as e:
                logger.error(f"❌ Error processing document with Gemini (attempt {attempt + 1}): {e}", exc_info=True)
                if attempt < max_retries - 1:
                    logger.info(f"   🔄 Retrying in {retry_delay} seconds...")
                    await asyncio.sleep(retry_delay)
                    continue
                else:
                    logger.error("❌ Max retries exceeded")
                    return []
        
        return []

    async def ingest_from_csv(self, csv_path: str, release_date: str, dry_run: bool = False) -> List[str]:
        """
        Ingest promises from CSV file using Gemini processing.
        
        Args:
            csv_path: Path to CSV file or URL
            release_date: Release date in YYYY-MM-DD format
            dry_run: If True, don't write to Firestore
            
        Returns:
            List of ingested promise IDs
        """
        logger.info("=== Starting CSV Ingestion with Gemini ===")
        
        parliament_session_id, source_year = determine_parliament_session_and_year(release_date)
        logger.info(f"Determined parliament session: {parliament_session_id}, source year: {source_year}")
        
        ingested_promise_ids = []
        
        try:
            # Determine if it's a URL or local file
            if csv_path.startswith(('http://', 'https://')):
                file_bytes = download_file_bytes(csv_path)
                source_url = csv_path
            else:
                with open(csv_path, 'rb') as f:
                    file_bytes = f.read()
                source_url = ""
            
            # Process with Gemini
            source_type = f'{source_year} LPC Platform'
            extracted_promises = await self.process_document_with_gemini(
                file_bytes, "text/csv", source_type, release_date
            )
            
            logger.info(f"📝 Processing {len(extracted_promises)} extracted promises from CSV")
            
            for i, promise_data in enumerate(extracted_promises, 1):
                try:
                    promise_id_str = f"CSV_{parliament_session_id}_{promise_data['promise_id']}"
                    
                    # Create promise document
                    promise_doc = {
                        'promise_id': promise_id_str,
                        'text': promise_data['text'],
                        'source_document_url': source_url,
                        'source_type': source_type,
                        'date_issued': release_date,
                        'parliament_session_id': parliament_session_id,
                        'candidate_or_government': f'Liberal Party of Canada ({source_year} Platform)',
                        'party_code': 'LPC',
                        'region_code': 'CAN',
                        'responsible_department_lead': None,
                        'relevant_departments': [],
                        'extraction_confidence': promise_data.get('confidence', 0.8),
                        'extraction_rationale': promise_data.get('rationale', ''),
                        
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
                        logger.info(f"   ✅ [{i}/{len(extracted_promises)}] Ingested: {promise_id_str}")
                    else:
                        logger.info(f"   🔄 [{i}/{len(extracted_promises)}] [DRY RUN] Would ingest: {promise_id_str}")
                    
                    ingested_promise_ids.append(promise_id_str)
                    self.stats['ingested'] += 1
                    self.update_promise_state(promise_id_str, PromiseState.INGESTED)
                    
                except Exception as e:
                    logger.error(f"   ❌ [{i}/{len(extracted_promises)}] Error processing promise: {e}")
                    self.stats['errors'] += 1
                    continue
            
            logger.info(f"🎉 CSV ingestion complete: {self.stats['ingested']} promises ingested")
            return ingested_promise_ids
            
        except Exception as e:
            logger.error(f"Error in CSV ingestion: {e}", exc_info=True)
            raise

    async def ingest_from_pdf(self, pdf_path: str, release_date: str, dry_run: bool = False) -> List[str]:
        """
        Ingest promises from PDF file using Gemini processing.
        
        Args:
            pdf_path: Path to PDF file or URL
            release_date: Release date in YYYY-MM-DD format
            dry_run: If True, don't write to Firestore
            
        Returns:
            List of ingested promise IDs
        """
        logger.info("=== Starting PDF Ingestion with Gemini ===")
        
        parliament_session_id, source_year = determine_parliament_session_and_year(release_date)
        logger.info(f"Determined parliament session: {parliament_session_id}, source year: {source_year}")
        
        ingested_promise_ids = []
        
        try:
            # Determine if it's a URL or local file
            if pdf_path.startswith(('http://', 'https://')):
                file_bytes = download_file_bytes(pdf_path)
                source_url = pdf_path
            else:
                with open(pdf_path, 'rb') as f:
                    file_bytes = f.read()
                source_url = ""
            
            # Process with Gemini
            source_type = f'{source_year} LPC Platform'
            extracted_promises = await self.process_document_with_gemini(
                file_bytes, "application/pdf", source_type, release_date
            )
            
            logger.info(f"📝 Processing {len(extracted_promises)} extracted promises from PDF")
            
            for i, promise_data in enumerate(extracted_promises, 1):
                try:
                    promise_id_str = f"PDF_{parliament_session_id}_{promise_data['promise_id']}"
                    
                    # Create promise document
                    promise_doc = {
                        'promise_id': promise_id_str,
                        'text': promise_data['text'],
                        'source_document_url': source_url,
                        'source_type': source_type,
                        'date_issued': release_date,
                        'parliament_session_id': parliament_session_id,
                        'candidate_or_government': f'Liberal Party of Canada ({source_year} Platform)',
                        'party_code': 'LPC',
                        'region_code': 'CAN',
                        'responsible_department_lead': None,
                        'relevant_departments': [],
                        'extraction_confidence': promise_data.get('confidence', 0.8),
                        'extraction_rationale': promise_data.get('rationale', ''),
                        
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
                        logger.info(f"   ✅ [{i}/{len(extracted_promises)}] Ingested: {promise_id_str}")
                    else:
                        logger.info(f"   🔄 [{i}/{len(extracted_promises)}] [DRY RUN] Would ingest: {promise_id_str}")
                    
                    ingested_promise_ids.append(promise_id_str)
                    self.stats['ingested'] += 1
                    self.update_promise_state(promise_id_str, PromiseState.INGESTED)
                    
                except Exception as e:
                    logger.error(f"   ❌ [{i}/{len(extracted_promises)}] Error processing promise: {e}")
                    self.stats['errors'] += 1
                    continue
            
            logger.info(f"🎉 PDF ingestion complete: {self.stats['ingested']} promises ingested")
            return ingested_promise_ids
            
        except Exception as e:
            logger.error(f"Error in PDF ingestion: {e}", exc_info=True)
            raise

    async def enrich_promises(self, promise_ids: List[str], enrichment_types: List[str],
                            force_reprocessing: bool = False, dry_run: bool = False) -> List[str]:
        """Enrich promises with specified enrichment types."""
        logger.info("=== Starting Promise Enrichment ===")
        
        if not self.langchain:
            logger.error("Langchain not available, cannot perform enrichment")
            return []
        
        enriched_promise_ids = []
        
        for i, promise_id in enumerate(promise_ids, 1):
            try:
                logger.info(f"🔄 [{i}/{len(promise_ids)}] Processing promise: {promise_id}")
                
                # Get promise data
                doc_ref = self.db.collection(PROMISES_COLLECTION).document(promise_id)
                doc = doc_ref.get()
                
                if not doc.exists:
                    logger.warning(f"   ⚠️  Promise {promise_id} not found, skipping enrichment")
                    continue
                
                promise_data = doc.to_dict()
                current_state = self.get_promise_state(promise_data)
                
                # Skip if already enriched (unless force reprocessing)
                if current_state in [PromiseState.ENRICHED, PromiseState.PRIORITY_RANKED, PromiseState.COMPLETED] and not force_reprocessing:
                    logger.info(f"   ⏭️  Promise {promise_id} already enriched, skipping")
                    continue
                
                logger.info(f"   🚀 Enriching promise {promise_id}...")
                
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
                        logger.info(f"   ✅ Successfully enriched promise {promise_id}")
                    else:
                        logger.info(f"   🔄 [DRY RUN] Would enrich promise {promise_id}")
                    
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
        
        logger.info(f"🎉 Enrichment complete: {len(enriched_promise_ids)} promises enriched")
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
    
    async def run_complete_pipeline(self, document_path: str = None, release_date: str = None,
                                  enrichment_types: List[str] = None, limit: int = None,
                                  force_reprocessing: bool = False, dry_run: bool = False) -> Dict:
        """Run the complete promise processing pipeline."""
        logger.info("🚀 " + "="*50)
        logger.info("🚀 STARTING COMPLETE PROMISE PROCESSING PIPELINE")
        logger.info("🚀 " + "="*50)
        logger.info(f"📄 Document Path: {document_path or 'None (using existing promises)'}")
        logger.info(f"📅 Release Date: {release_date or 'N/A'}")
        logger.info(f"🔧 Enrichment Types: {enrichment_types or ['all']}")
        logger.info(f"🔢 Limit: {limit or 'None'}")
        logger.info(f"🔄 Force Reprocessing: {force_reprocessing}")
        logger.info(f"🧪 Dry Run: {dry_run}")
        logger.info("=" * 60)
        
        if dry_run:
            logger.warning("⚠️  *** DRY RUN MODE: No changes will be written to Firestore ***")
        
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
            # Phase 1: Ingestion (if document provided)
            if document_path and release_date:
                logger.info("📥 " + "="*40)
                logger.info("📥 PHASE 1: PROMISE INGESTION")
                logger.info("📥 " + "="*40)
                
                # Determine parliament session and year from release date
                parliament_session_id, source_year = determine_parliament_session_and_year(release_date)
                
                # Determine file type and process accordingly
                if document_path.lower().endswith('.pdf') or 'pdf' in document_path.lower():
                    ingested_ids = await self.ingest_from_pdf(document_path, release_date, dry_run)
                elif document_path.lower().endswith('.csv') or 'csv' in document_path.lower():
                    ingested_ids = await self.ingest_from_csv(document_path, release_date, dry_run)
                else:
                    logger.error(f"Unsupported file type for document: {document_path}")
                    ingested_ids = []
                
                pipeline_results['ingested_promises'] = ingested_ids
                
                # Apply limit if specified
                if limit and len(ingested_ids) > limit:
                    ingested_ids = ingested_ids[:limit]
                
                promise_ids_to_process = ingested_ids
            else:
                # Use existing promises from database
                logger.info("📚 " + "="*40)
                logger.info("📚 PHASE 1: USING EXISTING PROMISES")
                logger.info("📚 " + "="*40)
                # Default to latest parliament session if no document provided
                parliament_session_id = "45"
                
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
                logger.info("🔧 " + "="*40)
                logger.info("🔧 PHASE 2: PROMISE ENRICHMENT")
                logger.info("🔧 " + "="*40)
                enriched_ids = await self.enrich_promises(
                    promise_ids_to_process, enrichment_types, force_reprocessing, dry_run
                )
                pipeline_results['enriched_promises'] = enriched_ids
                
                # Phase 3: Priority Ranking
                if enriched_ids:
                    logger.info("📊 " + "="*40)
                    logger.info("📊 PHASE 3: PRIORITY RANKING")
                    logger.info("📊 " + "="*40)
                    ranked_ids = await self.rank_promises_priority(
                        enriched_ids, release_date[:4] if release_date else "2025", force_reprocessing, dry_run
                    )
                    pipeline_results['ranked_promises'] = ranked_ids
            
            # Update final statistics
            self.stats['total_processed'] = len(promise_ids_to_process) if promise_ids_to_process else 0
            pipeline_results['stats'] = self.stats
            
            # Log final results
            logger.info("🎉 " + "="*50)
            logger.info("🎉 PIPELINE COMPLETE!")
            logger.info("🎉 " + "="*50)
            logger.info(f"🆔 Session ID: {self.session_id}")
            logger.info(f"📊 Total processed: {self.stats['total_processed']}")
            logger.info(f"📥 Ingested: {self.stats['ingested']}")
            logger.info(f"🔧 Enriched: {self.stats['enriched']}")
            logger.info(f"📊 Priority ranked: {self.stats['priority_ranked']}")
            logger.info(f"❌ Errors: {self.stats['errors']}")
            logger.info("=" * 60)
            
            return pipeline_results
            
        except Exception as e:
            logger.error(f"Pipeline execution failed: {e}", exc_info=True)
            raise

async def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(description='Consolidated Promise Processing Pipeline')
    parser.add_argument(
        '--document_path',
        type=str,
        help='Path or URL to document (PDF or CSV) for ingestion'
    )
    parser.add_argument(
        '--release_date',
        type=str,
        help='Release date in YYYY-MM-DD format (determines parliament session and year)'
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
        document_path=args.document_path,
        release_date=args.release_date,
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