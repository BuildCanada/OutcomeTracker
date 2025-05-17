from dotenv import load_dotenv
load_dotenv()

import firebase_admin
from firebase_admin import credentials
from firebase_admin import firestore
import pandas as pd
import os
import csv
import logging

# Import the common utility for department standardization
from common_utils import standardize_department_name # Assuming common_utils.py is in PYTHONPATH or same directory

# --- Logger Setup ---
logging.basicConfig(level=logging.INFO,
                    format='%(asctime)s - %(levelname)s - %(filename)s:%(lineno)d - %(message)s',
                    datefmt='%Y-%m-%d %H:%M:%S')
logger = logging.getLogger(__name__)
# --- End Logger Setup ---


# --- Firebase Configuration ---
db = None # Initialize db to None
if not firebase_admin._apps: # Check if app is already initialized
    # Check for emulator host first
    if os.getenv('FIRESTORE_EMULATOR_HOST'):
        options = {'projectId': os.getenv('FIREBASE_PROJECT_ID', 'promisetrackerapp')}
        try:
            firebase_admin.initialize_app(options=options)
            logger.info(f"Python (2025 Platform Ingest): Connected to Firestore Emulator at {os.getenv('FIRESTORE_EMULATOR_HOST')} using project ID '{options['projectId']}'")
            db = firestore.client()
        except Exception as e:
            logger.critical(f"Python (2025 Platform Ingest): Firebase emulator initialization failed: {e}", exc_info=True)
            exit("Exiting: Firebase emulator connection failed.")
    else:
        # Connect to Cloud Firestore
        if not os.getenv('GOOGLE_APPLICATION_CREDENTIALS'):
            logger.critical("CRITICAL: GOOGLE_APPLICATION_CREDENTIALS environment variable not set.")
            logger.critical("CRITICAL: This is required for authentication with Google Cloud Firestore.")
            exit("Exiting: GOOGLE_APPLICATION_CREDENTIALS not set.")
        try:
            firebase_admin.initialize_app()
            project_id = os.getenv('FIREBASE_PROJECT_ID', '[Not Set]')
            logger.info(f"Python (2025 Platform Ingest): Connected to CLOUD Firestore using Application Default Credentials (Project: {project_id}).")
            db = firestore.client()
        except Exception as e:
            logger.critical(f"Python (2025 Platform Ingest): Firebase initialization failed for Google Cloud Firestore: {e}", exc_info=True)
            exit("Exiting: Firebase connection failed.")
else:
    logger.info("Python (2025 Platform Ingest): Firebase app already initialized. Getting client.")
    db = firestore.client()


# Final check if db is assigned
if db is None:
    logger.critical("CRITICAL: Python (2025 Platform Ingest): Failed to obtain Firestore client. Exiting.")
    exit("Exiting: Firestore client not available.")
# --- End Firestore Configuration ---

def process_lpc_platform_csv(file_path):
    """Processes the 2025-LPC-platform.csv and adds/updates docs in Firestore."""
    promises_collection = db.collection('promises')
    
    processed_count = 0
    skipped_count = 0
    updated_count = 0
    added_count = 0

    logger.info(f"Starting processing of {file_path}")

    try:
        with open(file_path, mode='r', encoding='utf-8') as infile:
            reader = csv.DictReader(infile)
            for index, row in enumerate(reader):
                try:
                    promise_id_str = str(row.get('ID', '')).strip()
                    if not promise_id_str:
                        logger.warning(f"Skipping row {index+2} due to missing or invalid 'ID'.")
                        skipped_count += 1
                        continue

                    commitment_text = str(row.get('Commitment', '')).strip()
                    if not commitment_text:
                        logger.warning(f"Skipping row {index+2} (ID: {promise_id_str}) due to missing 'Commitment' text.")
                        skipped_count += 1
                        continue

                    # Standardize lead department
                    reporting_lead_raw = str(row.get('Reporting Lead', '')).strip()
                    reporting_lead_standardized = None
                    if reporting_lead_raw and reporting_lead_raw.lower() != 'nan':
                        reporting_lead_standardized = standardize_department_name(reporting_lead_raw)
                        if not reporting_lead_standardized:
                            logger.warning(f"Could not standardize Reporting Lead '{reporting_lead_raw}' for ID {promise_id_str}. Will store None.")
                    
                    # Parse and standardize 'All ministers'
                    all_ministers_raw = str(row.get('All ministers', '')).strip()
                    all_ministers_standardized = []
                    if all_ministers_raw and all_ministers_raw.lower() != 'nan':
                        ministers_list = all_ministers_raw.split(';')
                        for m in ministers_list:
                            m_stripped = m.strip()
                            if not m_stripped: # Skip empty strings that might result from trailing semicolons
                                continue
                            std_name = standardize_department_name(m_stripped)
                            if std_name and std_name not in all_ministers_standardized:
                                all_ministers_standardized.append(std_name)
                            elif not std_name:
                                logger.debug(f"Could not standardize minister '{m_stripped}' in 'All ministers' for ID {promise_id_str}.")
                    
                    promise_doc_data = {
                        'promise_id': promise_id_str,
                        'text': commitment_text,
                        'source_type': '2025 LPC Platform',
                        'source_document_url': 'https://liberal.ca/wp-content/uploads/sites/292/2024/04/Canada-Strong.pdf',
                        'date_issued': '2024-04-19', 
                        'parliament_session_id': "45", 
                        'candidate_or_government': 'Liberal Party of Canada (2025 Platform)',
                        'party': 'Liberal Party of Canada',
                        'category': None, # To be filled later
                        'responsible_department_lead': reporting_lead_standardized,
                        'relevant_departments': all_ministers_standardized,
                        
                        # Fields for subsequent processing
                        'key_points': [],
                        'commitment_history_rationale': None,
                        'linked_evidence_ids': [],
                        'extracted_keywords_concepts': [],
                        'implied_action_type': None,
                        'linking_preprocessing_done_at': None,
                        
                        # Metadata
                        'ingested_at': firestore.SERVER_TIMESTAMP,
                        'last_updated_at': firestore.SERVER_TIMESTAMP,
                    }

                    doc_ref = promises_collection.document(promise_doc_data['promise_id'])
                    doc_snapshot = doc_ref.get()

                    doc_ref.set(promise_doc_data, merge=True) 

                    if doc_snapshot.exists:
                        updated_count += 1
                        logger.debug(f"Updated promise document for ID: {promise_doc_data['promise_id']}")
                    else:
                        added_count += 1
                        logger.debug(f"Added new promise document for ID: {promise_doc_data['promise_id']}")
                    
                    processed_count +=1

                except Exception as e_row:
                    logger.error(f"Error processing row {index+2} (ID: {row.get('ID', 'N/A')}): {e_row}", exc_info=True)
                    skipped_count += 1
        
    except FileNotFoundError:
        logger.error(f"CSV file not found at: {file_path}")
        return
    except Exception as e_file:
        logger.error(f"Error reading or processing CSV file {file_path}: {e_file}", exc_info=True)
        return

    logger.info(f"Finished processing 2025 LPC Platform CSV.")
    logger.info(f"  - Rows processed successfully: {processed_count}")
    logger.info(f"  - Added: {added_count} new promise documents.")
    logger.info(f"  - Updated: {updated_count} existing promise documents.")
    logger.info(f"  - Skipped: {skipped_count} rows due to errors or missing data.")

# --- Main execution ---
if __name__ == "__main__":
    logger.info("Starting 2025 LPC Platform Ingestion Script...")
    
    script_dir = os.path.dirname(os.path.abspath(__file__))
    base_dir = os.path.dirname(script_dir) # Moves up from 'scripts' to 'PromiseTracker'

    # --- Path to 2025-LPC-platform.csv ---
    platform_csv_path = os.path.join(base_dir, 'raw-data', '2025-LPC-platform.csv')
    if not os.path.exists(platform_csv_path):
        logger.error(f"ERROR: 2025-LPC-platform.csv not found at: {platform_csv_path}")
        exit("Exiting: 2025-LPC-platform.csv file missing.")

    logger.info(f"Processing 2025 LPC Platform CSV file from: {platform_csv_path}")
    process_lpc_platform_csv(platform_csv_path)

    logger.info("2025 LPC Platform ingestion script finished.") 