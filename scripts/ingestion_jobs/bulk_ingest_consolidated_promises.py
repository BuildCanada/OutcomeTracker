#!/usr/bin/env python3
"""
Bulk Consolidated Promise Ingestion Script

Ingests the JSON output from the promise consolidation process into Firestore.
Preserves all field names and types from the consolidation output exactly as they are.

Usage:
    python bulk_ingest_consolidated_promises.py --json_file consolidated_2025_LPC_promises_final.json --source_type "2025 LPC Consolidated" --release_date "2025-04-19"
"""

import os
import sys
import json
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
logger = logging.getLogger("bulk_ingest_consolidated_promises")

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
                firebase_admin.initialize_app(cred, name='bulk_ingest_consolidated')
                project_id_sa = os.getenv('FIREBASE_PROJECT_ID', '[Not Set - Using Service Account]')
                logger.info(f"Connected to CLOUD Firestore (Project: {project_id_sa}) via service account.")
                db = firestore.client(app=firebase_admin.get_app(name='bulk_ingest_consolidated'))
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
        logger.error(f"Invalid release date format {release_date_str}: {e}. Defaulting to session 45.")
        return "45"

def create_consolidated_promise_record(promise_data, source_type, base_release_date, parliament_session_id):
    """Create a standardized promise record from consolidated JSON data."""
    
    # Extract the consolidated fields (preserve exact names and types)
    commitment_id = promise_data.get('commitment_id', '')
    canonical_commitment_text = promise_data.get('canonical_commitment_text', '')
    appears_in = promise_data.get('appears_in', '')
    reporting_lead_title = promise_data.get('reporting_lead_title', '')
    all_other_ministers_involved = promise_data.get('all_other_ministers_involved', '')
    notes_and_differences = promise_data.get('notes_and_differences', '')
    
    # Determine if this is an SFT-only promise
    is_sft_only = commitment_id.startswith('SFT_ONLY_')
    
    # Set release date based on source
    if appears_in == "SFT Only":
        # Speech from the Throne date
        actual_release_date = "2025-05-27"
    else:
        # Platform Only or Both - use platform date
        actual_release_date = "2025-04-19"
    
    # Base promise record
    promise_record = {
        # === CONSOLIDATED FIELDS (PRESERVED EXACTLY) ===
        'commitment_id': commitment_id,
        'canonical_commitment_text': canonical_commitment_text,
        'appears_in': appears_in,
        'reporting_lead_title': reporting_lead_title,
        'all_other_ministers_involved': all_other_ministers_involved,
        'notes_and_differences': notes_and_differences,
        
        # === STANDARD PROMISE TRACKER FIELDS ===
        'promise_id': commitment_id,  # Alias for compatibility
        'text': canonical_commitment_text,  # Alias for compatibility
        'source_type': source_type,
        'source_document_url': '',
        'date_issued': actual_release_date,
        'parliament_session_id': parliament_session_id,
        'party': 'Liberal Party of Canada',
        'category': None,
        
        # Handle departments - clean up "N/A" values
        'responsible_department_lead': None if reporting_lead_title in ['N/A', 'N/A (SFT Specific)', ''] else reporting_lead_title,
        'relevant_departments': [] if all_other_ministers_involved in ['N/A', 'N/A (SFT Specific)', ''] else [dept.strip() for dept in all_other_ministers_involved.split(';') if dept.strip()],
        
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
    
    # Adjust candidate_or_government based on source
    if is_sft_only:
        promise_record['candidate_or_government'] = f'Liberal Party of Canada ({actual_release_date[:4]} Speech from the Throne)'
    elif appears_in == 'Both':
        promise_record['candidate_or_government'] = f'Liberal Party of Canada ({actual_release_date[:4]} Platform & Speech from the Throne)'
    else:
        promise_record['candidate_or_government'] = f'Liberal Party of Canada ({actual_release_date[:4]} Platform)'
    
    return promise_record

def process_csv_file(csv_file_path, source_type, base_release_date, collection_name="promises_test", dry_run=False):
    """Process a CSV file containing consolidated promise data."""
    
    # Note: Parliament session will be determined per promise based on actual release date
    logger.info(f"Base release date: {base_release_date} (will be adjusted per promise based on source)")
    
    processed_count = 0
    skipped_count = 0
    updated_count = 0
    added_count = 0
    
    logger.info(f"🔄 Starting processing of {csv_file_path}")
    logger.info(f"📄 Source Type: {source_type}")
    logger.info(f"📅 Base Release Date: {base_release_date}")
    logger.info(f"🗃️  Target Collection: {collection_name}")
    
    if dry_run:
        logger.warning("⚠️  *** DRY RUN MODE: No changes will be written to Firestore ***")
    
    try:
        import csv
        with open(csv_file_path, 'r', encoding='utf-8') as infile:
            csv_reader = csv.DictReader(infile)
            promises_data = list(csv_reader)
            
        if not isinstance(promises_data, list) or len(promises_data) == 0:
            logger.error(f"No data found in CSV file or invalid format")
            return None
            
        logger.info(f"📋 Loaded {len(promises_data)} consolidated promises from CSV")
        
        for index, promise_data in enumerate(promises_data):
            try:
                # Validate required fields
                commitment_id = promise_data.get('commitment_id', '').strip()
                canonical_text = promise_data.get('canonical_commitment_text', '').strip()
                
                if not commitment_id:
                    logger.warning(f"Skipping promise {index+1} due to missing commitment_id.")
                    skipped_count += 1
                    continue
                
                if not canonical_text:
                    logger.warning(f"Skipping promise {index+1} (ID: {commitment_id}) due to missing canonical_commitment_text.")
                    skipped_count += 1
                    continue
                
                # Determine the actual release date and parliament session for this specific promise
                appears_in = promise_data.get('appears_in', '')
                if appears_in == "SFT Only":
                    actual_release_date = "2025-05-27"
                else:
                    actual_release_date = "2025-04-19"
                
                parliament_session_id = determine_parliament_session(actual_release_date)
                
                # Create promise document
                promise_doc = create_consolidated_promise_record(
                    promise_data=promise_data,
                    source_type=source_type,
                    base_release_date=base_release_date,
                    parliament_session_id=parliament_session_id
                )
                
                # Generate document path
                doc_full_path = get_promise_document_path_flat(
                    party_name_str=promise_doc['party'],
                    date_issued_str=promise_doc['date_issued'],
                    source_type_str=promise_doc['source_type'],
                    promise_text=promise_doc['text'],
                    region_code=DEFAULT_REGION_CODE
                )
                
                # Replace collection name
                if collection_name != "promises":
                    doc_full_path = doc_full_path.replace("promises/", f"{collection_name}/", 1)
                
                if not doc_full_path:
                    logger.warning(f"Could not generate document path for promise {index+1} (ID: {commitment_id}). Skipping.")
                    skipped_count += 1
                    continue
                
                # Insert or update promise
                if not dry_run:
                    doc_ref = db.document(doc_full_path)
                    doc_snapshot = doc_ref.get()
                    doc_ref.set(promise_doc, merge=True)
                    
                    if doc_snapshot.exists:
                        updated_count += 1
                        logger.debug(f"✅ [{index+1}] Updated: {commitment_id}")
                    else:
                        added_count += 1
                        logger.debug(f"🆕 [{index+1}] Added: {commitment_id}")
                else:
                    logger.info(f"🔄 [{index+1}] [DRY RUN] Would process: {commitment_id} ({promise_data.get('appears_in', 'Unknown')})")
                    added_count += 1  # Count as "would add" for dry run
                
                processed_count += 1
                
                # Log progress every 25 items
                if processed_count % 25 == 0:
                    logger.info(f"📊 Progress: {processed_count} processed, {skipped_count} skipped")
                    
            except Exception as e_row:
                logger.error(f"Error processing promise {index+1} (ID: {promise_data.get('commitment_id', 'N/A')}): {e_row}", exc_info=True)
                skipped_count += 1
                
    except FileNotFoundError:
        logger.error(f"CSV file not found at: {csv_file_path}")
        return None
    except Exception as e_file:
        logger.error(f"Error reading or processing CSV file {csv_file_path}: {e_file}", exc_info=True)
        return None
    
    # Final summary
    logger.info("🎉 " + "="*60)
    logger.info("🎉 CONSOLIDATED PROMISE INGESTION COMPLETE!")
    logger.info("🎉 " + "="*60)
    logger.info(f"📊 Total processed: {processed_count}")
    logger.info(f"🆕 Added: {added_count}")
    logger.info(f"✅ Updated: {updated_count}")
    logger.info(f"⏭️  Skipped: {skipped_count}")
    logger.info(f"🗃️  Collection: {collection_name}")
    logger.info("=" * 70)
    
    return {
        'processed': processed_count,
        'added': added_count,
        'updated': updated_count,
        'skipped': skipped_count,
        'collection_name': collection_name
    }

def main():
    parser = argparse.ArgumentParser(description='Bulk ingest consolidated promises from JSON file')
    parser.add_argument('--csv_file', required=True, help='Path to CSV file containing consolidated promise data')
    parser.add_argument('--source_type', required=True, help='Source type (e.g., "2025 LPC Consolidated")')
    parser.add_argument('--release_date', required=True, help='Release date in YYYY-MM-DD format')
    parser.add_argument('--collection_name', default='promises_test', help='Firestore collection name (default: promises_test)')
    parser.add_argument('--dry_run', action='store_true', help='Run without making changes to Firestore')
    
    args = parser.parse_args()
    
    if not os.path.exists(args.csv_file):
        logger.error(f"CSV file not found: {args.csv_file}")
        return
    
    results = process_csv_file(
        csv_file_path=args.csv_file,
        source_type=args.source_type,
        base_release_date=args.release_date,
        collection_name=args.collection_name,
        dry_run=args.dry_run
    )
    
    if results:
        logger.info(f"✅ Consolidated promise ingestion completed successfully!")
        logger.info(f"📋 Results summary: {results}")
    else:
        logger.error("❌ Consolidated promise ingestion failed")

if __name__ == "__main__":
    main() 