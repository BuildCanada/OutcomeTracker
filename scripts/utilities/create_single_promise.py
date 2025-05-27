#!/usr/bin/env python3
"""
Single Promise Creation Utility

Simple function for creating individual promise records.
Designed to be easily called from frontend applications.

Usage:
    from create_single_promise import create_promise
    
    result = create_promise(
        promise_text="Increase healthcare funding by 10%",
        source_type="Campaign Commitment",
        release_date="2025-05-26",
        party="Liberal Party of Canada",
        responsible_department="Minister of Health",
        relevant_departments=["Minister of Finance"],
        source_document_url="https://example.com/doc.pdf"
    )
"""

import os
import sys
import logging
from datetime import datetime
from typing import List, Optional, Dict
from dotenv import load_dotenv
import firebase_admin
from firebase_admin import credentials, firestore

# Add parent directory to path for imports
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

try:
    from common_utils import standardize_department_name, get_promise_document_path_flat, DEFAULT_REGION_CODE, PARTY_NAME_TO_CODE_MAPPING
except ImportError:
    # Fallback definitions if common_utils not available
    def standardize_department_name(dept_name): return dept_name
    def get_promise_document_path_flat(**kwargs): return f"promises/{kwargs.get('promise_text', 'unknown')[:20].replace(' ', '_')}"
    DEFAULT_REGION_CODE = "CAN"
    PARTY_NAME_TO_CODE_MAPPING = {"Liberal Party of Canada": "LPC"}

load_dotenv()

# Logger setup
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(filename)s:%(lineno)d - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger("create_single_promise")

# Firebase Configuration - Initialize once
_db = None

def get_firestore_client():
    """Get or initialize Firestore client."""
    global _db
    
    if _db is not None:
        return _db
    
    if not firebase_admin._apps:
        try:
            firebase_admin.initialize_app()
            project_id = os.getenv('FIREBASE_PROJECT_ID', '[Not Set - Using Default]')
            logger.info(f"Connected to CLOUD Firestore (Project: {project_id}) using default credentials.")
            _db = firestore.client()
        except Exception as e_default:
            logger.warning(f"Cloud Firestore init with default creds failed: {e_default}. Attempting service account.")
            cred_path = os.getenv('FIREBASE_SERVICE_ACCOUNT_KEY_PATH')
            if cred_path:
                try:
                    logger.info(f"Attempting Firebase init with service account key from env var: {cred_path}")
                    cred = credentials.Certificate(cred_path)
                    firebase_admin.initialize_app(cred, name='create_single_promise')
                    project_id_sa = os.getenv('FIREBASE_PROJECT_ID', '[Not Set - Using Service Account]')
                    logger.info(f"Connected to CLOUD Firestore (Project: {project_id_sa}) via service account.")
                    _db = firestore.client(app=firebase_admin.get_app(name='create_single_promise'))
                except Exception as e_sa:
                    logger.error(f"Firebase init with service account key from {cred_path} failed: {e_sa}")
                    raise e_sa
            else:
                logger.error("FIREBASE_SERVICE_ACCOUNT_KEY_PATH environment variable not set, and default creds failed.")
                raise e_default
    else:
        _db = firestore.client()
    
    if _db is None:
        raise Exception("Failed to obtain Firestore client")
    
    return _db

# Parliament Session Mapping
PARLIAMENT_SESSIONS = {
    "44": {"start_date": "2021-08-15", "end_date": "2025-03-23"},
    "45": {"start_date": "2025-03-24", "end_date": "2030-12-31"}
}

def determine_parliament_session(release_date_str: str) -> str:
    """Determine parliament session ID from release date."""
    try:
        release_date = datetime.strptime(release_date_str, "%Y-%m-%d").date()
        
        for session_id, session_data in PARLIAMENT_SESSIONS.items():
            start_date = datetime.strptime(session_data["start_date"], "%Y-%m-%d").date()
            end_date = datetime.strptime(session_data["end_date"], "%Y-%m-%d").date()
            
            if start_date <= release_date <= end_date:
                return session_id
        
        # Default to most recent session
        logger.warning(f"Release date {release_date_str} doesn't match any parliament session. Defaulting to session 45.")
        return "45"
        
    except ValueError as e:
        logger.error(f"Invalid release date format {release_date_str}: {e}. Defaulting to session 44.")
        return "44"

def create_promise(
    promise_text: str,
    source_type: str,
    release_date: str,
    party: str = "Liberal Party of Canada",
    responsible_department: Optional[str] = None,
    relevant_departments: Optional[List[str]] = None,
    source_document_url: str = "",
    promise_id: Optional[str] = None,
    category: Optional[str] = None,
    dry_run: bool = False
) -> Dict:
    """
    Create a single promise record in Firestore.
    
    Args:
        promise_text: The full text of the promise/commitment
        source_type: Type of source (e.g., "Campaign Commitment", "2025 LPC Platform")
        release_date: Date in YYYY-MM-DD format
        party: Political party (defaults to "Liberal Party of Canada")
        responsible_department: Lead department (will be standardized)
        relevant_departments: List of relevant departments (will be standardized)
        source_document_url: URL to source document
        promise_id: Optional custom promise ID (will be generated if not provided)
        category: Optional promise category
        dry_run: If True, don't write to Firestore
        
    Returns:
        Dictionary with creation results
    """
    
    try:
        # Validate required inputs
        if not promise_text or not promise_text.strip():
            raise ValueError("promise_text is required and cannot be empty")
        
        if not source_type or not source_type.strip():
            raise ValueError("source_type is required and cannot be empty")
        
        if not release_date or not release_date.strip():
            raise ValueError("release_date is required and cannot be empty")
        
        # Clean inputs
        promise_text = promise_text.strip()
        source_type = source_type.strip()
        release_date = release_date.strip()
        party = party.strip()
        
        # Determine parliament session
        parliament_session_id = determine_parliament_session(release_date)
        
        # Generate promise ID if not provided
        if not promise_id:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            promise_id = f"MANUAL_{parliament_session_id}_{timestamp}"
        
        # Standardize departments
        standardized_responsible_dept = None
        if responsible_department and responsible_department.strip():
            standardized_responsible_dept = standardize_department_name(responsible_department.strip())
        
        standardized_relevant_depts = []
        if relevant_departments:
            for dept in relevant_departments:
                if dept and dept.strip():
                    std_dept = standardize_department_name(dept.strip())
                    if std_dept and std_dept not in standardized_relevant_depts:
                        standardized_relevant_depts.append(std_dept)
        
        # Create promise document
        promise_doc = {
            'promise_id': promise_id,
            'text': promise_text,
            'source_type': source_type,
            'source_document_url': source_document_url,
            'date_issued': release_date,
            'parliament_session_id': parliament_session_id,
            'candidate_or_government': f'{party} ({release_date[:4]} Platform)',
            'party': party,
            'category': category,
            'responsible_department_lead': standardized_responsible_dept,
            'relevant_departments': standardized_relevant_depts,
            
            # Flat structure fields
            'region_code': DEFAULT_REGION_CODE,
            'party_code': PARTY_NAME_TO_CODE_MAPPING.get(party, 'LPC'),
            
            # Fields for subsequent processing
            'key_points': [],
            'commitment_history_rationale': None,
            'linked_evidence_ids': [],
            'extracted_keywords_concepts': [],
            'implied_action_type': None,
            'linking_preprocessing_done_at': None,
            
            # Enrichment placeholders
            'what_it_means_for_canadians': None,
            'background_and_context': None,
            'bc_priority_score': None,
            
            # Metadata
            'ingested_at': firestore.SERVER_TIMESTAMP,
            'last_updated_at': firestore.SERVER_TIMESTAMP,
        }
        
        # Generate document path
        doc_full_path = get_promise_document_path_flat(
            party_name_str=promise_doc['party'],
            date_issued_str=promise_doc['date_issued'],
            source_type_str=promise_doc['source_type'],
            promise_text=promise_doc['text'],
            region_code=DEFAULT_REGION_CODE
        )
        
        if not doc_full_path:
            raise Exception("Could not generate document path for promise")
        
        # Insert promise into Firestore
        if not dry_run:
            db = get_firestore_client()
            doc_ref = db.document(doc_full_path)
            doc_snapshot = doc_ref.get()
            
            doc_ref.set(promise_doc, merge=True)
            
            operation = "updated" if doc_snapshot.exists else "created"
            logger.info(f"✅ Promise {operation}: {promise_id}")
        else:
            operation = "would_create"
            logger.info(f"🔄 [DRY RUN] Would create promise: {promise_id}")
        
        return {
            'success': True,
            'promise_id': promise_id,
            'document_path': doc_full_path,
            'parliament_session_id': parliament_session_id,
            'operation': operation,
            'message': f"Promise {operation} successfully"
        }
        
    except Exception as e:
        logger.error(f"Error creating promise: {e}", exc_info=True)
        return {
            'success': False,
            'error': str(e),
            'promise_id': promise_id if 'promise_id' in locals() else None
        }

def create_multiple_promises(promises_data: List[Dict], dry_run: bool = False) -> Dict:
    """
    Create multiple promises at once.
    
    Args:
        promises_data: List of dictionaries, each containing promise data
        dry_run: If True, don't write to Firestore
        
    Returns:
        Dictionary with batch creation results
    """
    
    results = {
        'success': True,
        'created': [],
        'updated': [],
        'failed': [],
        'total': len(promises_data)
    }
    
    logger.info(f"🔄 Creating {len(promises_data)} promises...")
    
    for i, promise_data in enumerate(promises_data):
        try:
            result = create_promise(dry_run=dry_run, **promise_data)
            
            if result['success']:
                if result['operation'] == 'created':
                    results['created'].append(result['promise_id'])
                elif result['operation'] == 'updated':
                    results['updated'].append(result['promise_id'])
                
                logger.info(f"✅ [{i+1}/{len(promises_data)}] {result['operation']}: {result['promise_id']}")
            else:
                results['failed'].append({
                    'index': i,
                    'promise_id': result.get('promise_id'),
                    'error': result['error']
                })
                results['success'] = False
                logger.error(f"❌ [{i+1}/{len(promises_data)}] Failed: {result['error']}")
                
        except Exception as e:
            results['failed'].append({
                'index': i,
                'promise_id': promise_data.get('promise_id'),
                'error': str(e)
            })
            results['success'] = False
            logger.error(f"❌ [{i+1}/{len(promises_data)}] Exception: {e}")
    
    logger.info(f"🎉 Batch creation complete: {len(results['created'])} created, {len(results['updated'])} updated, {len(results['failed'])} failed")
    
    return results

# Example usage and testing
if __name__ == "__main__":
    # Test single promise creation
    test_promise = {
        'promise_text': "Increase healthcare funding by 15% over the next four years",
        'source_type': "Campaign Commitment",
        'release_date': "2025-05-26",
        'responsible_department': "Minister of Health",
        'relevant_departments': ["Minister of Finance", "Minister of Treasury"],
        'source_document_url': "https://example.com/healthcare-commitment.pdf",
        'dry_run': True  # Set to False to actually create
    }
    
    result = create_promise(**test_promise)
    print(f"Result: {result}") 