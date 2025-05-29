#!/usr/bin/env python3
"""
Bulk Promise Ingestion Script

Simple, reliable bulk ingestion for structured promise data from CSV files.
Based on the proven approach from ingest_2025_LPC_platform.py but made generic.

Usage:
    python bulk_ingest_promises.py --csv_file path/to/promises.csv --source_type "2025 LPC Platform" --release_date "2025-04-19"
"""

import os
import sys
import csv
import logging
import argparse
from datetime import datetime
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
logger = logging.getLogger("bulk_ingest_promises")

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
                firebase_admin.initialize_app(cred, name='bulk_ingest_promises')
                project_id_sa = os.getenv('FIREBASE_PROJECT_ID', '[Not Set - Using Service Account]')
                logger.info(f"Connected to CLOUD Firestore (Project: {project_id_sa}) via service account.")
                db = firestore.client(app=firebase_admin.get_app(name='bulk_ingest_promises'))
            except Exception as e_sa:
                logger.critical(f"Firebase init with service account key from {cred_path} failed: {e_sa}", exc_info=True)
        else:
            logger.warning("FIREBASE_SERVICE_ACCOUNT_KEY_PATH environment variable not set, and default creds failed.")

if db is None:
    logger.critical("CRITICAL: Failed to obtain Firestore client. Exiting.")
    exit("Exiting: Firestore client not available.")

# Parliament Session Mapping
PARLIAMENT_SESSIONS = {
    "44": {"start_date": "2021-08-15", "end_date": "2025-03-23"},
    "45": {"start_date": "2025-03-24", "end_date": "2030-12-31"}
}

def determine_parliament_session(release_date_str):
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

def create_promise_record(promise_id, commitment_text, source_type, release_date, 
                         parliament_session_id, responsible_department=None, 
                         relevant_departments=None, source_document_url=""):
    """Create a standardized promise record."""
    
    if relevant_departments is None:
        relevant_departments = []
    
    return {
        'promise_id': promise_id,
        'text': commitment_text,
        'source_type': source_type,
        'source_document_url': source_document_url,
        'date_issued': release_date,
        'parliament_session_id': parliament_session_id,
        'candidate_or_government': f'Liberal Party of Canada ({release_date[:4]} Platform)',
        'party': 'Liberal Party of Canada',
        'category': None,
        'responsible_department_lead': responsible_department,
        'relevant_departments': relevant_departments,
        
        # Flat structure fields
        'region_code': DEFAULT_REGION_CODE,
        'party_code': PARTY_NAME_TO_CODE_MAPPING.get('Liberal Party of Canada', 'LPC'),
        
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

def process_csv_file(csv_file_path, source_type, release_date, collection_name="promises", dry_run=False):
    """Process a CSV file containing promise data."""
    
    parliament_session_id = determine_parliament_session(release_date)
    logger.info(f"Determined parliament session: {parliament_session_id} for date: {release_date}")
    
    processed_count = 0
    skipped_count = 0
    updated_count = 0
    added_count = 0
    
    logger.info(f"🔄 Starting processing of {csv_file_path}")
    logger.info(f"📄 Source Type: {source_type}")
    logger.info(f"📅 Release Date: {release_date}")
    logger.info(f"🏛️  Parliament Session: {parliament_session_id}")
    
    if dry_run:
        logger.warning("⚠️  *** DRY RUN MODE: No changes will be written to Firestore ***")
    
    try:
        with open(csv_file_path, mode='r', encoding='utf-8') as infile:
            reader = csv.DictReader(infile)
            
            # Detect CSV format based on headers
            headers = reader.fieldnames
            logger.info(f"📋 CSV Headers: {headers}")
            
            for index, row in enumerate(reader):
                try:
                    # Extract promise ID - flexible field names
                    promise_id_str = None
                    for id_field in ['ID', 'id', 'Promise_ID', 'promise_id', 'MLC ID', 'mlc_id']:
                        if id_field in row and row[id_field].strip():
                            promise_id_str = str(row[id_field]).strip()
                            break
                    
                    if not promise_id_str:
                        logger.warning(f"Skipping row {index+2} due to missing or invalid ID field.")
                        skipped_count += 1
                        continue
                    
                    # Extract commitment text - flexible field names
                    commitment_text = None
                    for text_field in ['Commitment', 'commitment', 'Text', 'text', 'Promise_Text']:
                        if text_field in row and row[text_field].strip():
                            commitment_text = str(row[text_field]).strip()
                            break
                    
                    if not commitment_text:
                        logger.warning(f"Skipping row {index+2} (ID: {promise_id_str}) due to missing commitment text.")
                        skipped_count += 1
                        continue
                    
                    # Extract and standardize departments
                    responsible_department = None
                    for dept_field in ['Reporting Lead', 'reporting_lead', 'Department', 'department']:
                        if dept_field in row and row[dept_field].strip():
                            dept_raw = str(row[dept_field]).strip()
                            if dept_raw.lower() != 'nan':
                                responsible_department = standardize_department_name(dept_raw)
                            break
                    
                    # Extract relevant departments
                    relevant_departments = []
                    for depts_field in ['All ministers', 'all_ministers', 'Relevant_Departments', 'relevant_departments']:
                        if depts_field in row and row[depts_field].strip():
                            depts_raw = str(row[depts_field]).strip()
                            if depts_raw.lower() != 'nan':
                                dept_list = depts_raw.split(';')
                                for dept in dept_list:
                                    dept_stripped = dept.strip()
                                    if dept_stripped:
                                        std_name = standardize_department_name(dept_stripped)
                                        if std_name and std_name not in relevant_departments:
                                            relevant_departments.append(std_name)
                            break
                    
                    # Create promise document
                    promise_doc = create_promise_record(
                        promise_id=promise_id_str,
                        commitment_text=commitment_text,
                        source_type=source_type,
                        release_date=release_date,
                        parliament_session_id=parliament_session_id,
                        responsible_department=responsible_department,
                        relevant_departments=relevant_departments
                    )
                    
                    # Generate document path
                    doc_full_path = get_promise_document_path_flat(
                        party_name_str=promise_doc['party'],
                        date_issued_str=promise_doc['date_issued'],
                        source_type_str=promise_doc['source_type'],
                        promise_text=promise_doc['text'],
                        region_code=DEFAULT_REGION_CODE
                    )
                    
                    # Debug logging to understand document path generation
                    logger.debug(f"Debug path generation for {promise_id_str}:")
                    logger.debug(f"  - party: {promise_doc['party']}")
                    logger.debug(f"  - date_issued: {promise_doc['date_issued']}")
                    logger.debug(f"  - source_type: {promise_doc['source_type']}")
                    logger.debug(f"  - promise_text[:50]: {promise_doc['text'][:50]}...")
                    logger.debug(f"  - generated doc_full_path: {doc_full_path}")
                    
                    # Replace collection name if different from default
                    if collection_name != "promises":
                        doc_full_path = doc_full_path.replace("promises/", f"{collection_name}/", 1)
                        logger.debug(f"  - updated doc_full_path: {doc_full_path}")
                    
                    if not doc_full_path:
                        logger.warning(f"Could not generate document path for row {index+2} (ID: {promise_id_str}). Skipping.")
                        skipped_count += 1
                        continue
                    
                    # Insert or update promise
                    if not dry_run:
                        doc_ref = db.document(doc_full_path)
                        doc_snapshot = doc_ref.get()
                        doc_ref.set(promise_doc, merge=True)
                        
                        if doc_snapshot.exists:
                            updated_count += 1
                            logger.debug(f"✅ [{index+1}] Updated: {promise_id_str}")
                        else:
                            added_count += 1
                            logger.debug(f"🆕 [{index+1}] Added: {promise_id_str}")
                    else:
                        logger.info(f"🔄 [{index+1}] [DRY RUN] Would process: {promise_id_str}")
                        added_count += 1  # Count as "would add" for dry run
                    
                    processed_count += 1
                    
                    # Log progress every 10 items
                    if processed_count % 10 == 0:
                        logger.info(f"📊 Progress: {processed_count} processed, {skipped_count} skipped")
                        
                except Exception as e_row:
                    logger.error(f"Error processing row {index+2} (ID: {row.get('ID', 'N/A')}): {e_row}", exc_info=True)
                    skipped_count += 1
                    
    except FileNotFoundError:
        logger.error(f"CSV file not found at: {csv_file_path}")
        return None
    except Exception as e_file:
        logger.error(f"Error reading or processing CSV file {csv_file_path}: {e_file}", exc_info=True)
        return None
    
    # Final summary
    logger.info("🎉 " + "="*50)
    logger.info("🎉 BULK PROMISE INGESTION COMPLETE!")
    logger.info("🎉 " + "="*50)
    logger.info(f"📊 Total processed: {processed_count}")
    logger.info(f"🆕 Added: {added_count}")
    logger.info(f"✅ Updated: {updated_count}")
    logger.info(f"⏭️  Skipped: {skipped_count}")
    logger.info("=" * 60)
    
    return {
        'processed': processed_count,
        'added': added_count,
        'updated': updated_count,
        'skipped': skipped_count,
        'parliament_session_id': parliament_session_id
    }

def main():
    parser = argparse.ArgumentParser(description='Bulk ingest promises from structured CSV file')
    parser.add_argument('--csv_file', required=True, help='Path to CSV file containing promise data')
    parser.add_argument('--source_type', required=True, help='Source type (e.g., "2025 LPC Platform")')
    parser.add_argument('--release_date', required=True, help='Release date in YYYY-MM-DD format')
    parser.add_argument('--collection_name', default='promises', help='Firestore collection name (default: promises)')
    parser.add_argument('--dry_run', action='store_true', help='Run without making changes to Firestore')
    
    args = parser.parse_args()
    
    if not os.path.exists(args.csv_file):
        logger.error(f"CSV file not found: {args.csv_file}")
        return
    
    results = process_csv_file(
        csv_file_path=args.csv_file,
        source_type=args.source_type,
        release_date=args.release_date,
        collection_name=args.collection_name,
        dry_run=args.dry_run
    )
    
    if results:
        logger.info(f"✅ Bulk ingestion completed successfully!")
        logger.info(f"📋 Results summary: {results}")
    else:
        logger.error("❌ Bulk ingestion failed")

if __name__ == "__main__":
    main() 