from dotenv import load_dotenv
load_dotenv()

import firebase_admin
from firebase_admin import credentials
from firebase_admin import firestore
import pandas as pd
import os
import csv # Add csv import
import logging # Add logging import

# Import the new common utility for department standardization
from common_utils import standardize_department_name

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
        # Connect to Emulator
        # Note: Emulator often doesn't need explicit credentials or project ID unless configured
        options = {'projectId': os.getenv('FIREBASE_PROJECT_ID', 'promisetrackerapp')} # Use a default project ID for emulator if needed
        try:
            firebase_admin.initialize_app(options=options)
            logger.info(f"Python (Mandate Process): Connected to Firestore Emulator at {os.getenv('FIRESTORE_EMULATOR_HOST')} using project ID '{options['projectId']}'")
            db = firestore.client()
        except Exception as e:
            logger.critical(f"Python (Mandate Process): Firebase emulator initialization failed: {e}", exc_info=True)
            exit("Exiting: Firebase emulator connection failed.")
    else:
        # Connect to Cloud Firestore
        # GOOGLE_APPLICATION_CREDENTIALS environment variable must be set
        if not os.getenv('GOOGLE_APPLICATION_CREDENTIALS'):
            logger.critical("CRITICAL: GOOGLE_APPLICATION_CREDENTIALS environment variable not set.")
            logger.critical("CRITICAL: This is required for authentication with Google Cloud Firestore.")
            exit("Exiting: GOOGLE_APPLICATION_CREDENTIALS not set.")
        try:
            firebase_admin.initialize_app() # Default initialization uses GOOGLE_APPLICATION_CREDENTIALS
            project_id = os.getenv('FIREBASE_PROJECT_ID', '[Not Set]') # Get project ID if available for logging
            logger.info(f"Python (Mandate Process): Connected to CLOUD Firestore using Application Default Credentials (Project: {project_id}).")
            db = firestore.client()
        except Exception as e:
            logger.critical(f"Python (Mandate Process): Firebase initialization failed for Google Cloud Firestore: {e}", exc_info=True)
            exit("Exiting: Firebase connection failed.")
else:
    # If the app is already initialized (e.g., by another module), get the client
    # Assume it was initialized correctly (either cloud or emulator)
    logger.info("Python (Mandate Process): Firebase app already initialized. Getting client.")
    db = firestore.client()


# Final check if db is assigned
if db is None:
    logger.critical("CRITICAL: Python (Mandate Process): Failed to obtain Firestore client. Exiting.")
    exit("Exiting: Firestore client not available.")
# --- End Firestore Configuration ---

# --- Helper Function to Load Mandate Letter URLs ---
def load_mandate_letter_urls(csv_file_path):
    """
    Reads 2021MandateLetters.csv and creates a map from standardized department name
    to mandate letter URL. Uses the 'Department' column for standardization key.
    """
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
                    logger.warning(f"Skipping row in 2021MandateLetters.csv due to missing Department or URL: {row}")
                    skipped_count += 1
                    continue

                # Standardize using the 'Department' column as the key
                standardized_dept = standardize_department_name(department_raw.strip())
                if standardized_dept:
                    if standardized_dept in url_map:
                         # This might happen if multiple titles map to the same dept, like Finance
                         logger.debug(f"Duplicate standardized department '{standardized_dept}' found. Keeping first URL: {url_map[standardized_dept]}")
                    else:
                        url_map[standardized_dept] = mandate_url.strip()
                        processed_count += 1
                else:
                    logger.warning(f"Could not standardize department '{department_raw}' from 2021MandateLetters.csv. Cannot map URL.")
                    skipped_count += 1

        logger.info(f"Successfully loaded {processed_count} mandate letter URLs. Skipped {skipped_count} rows.")
        return url_map
    except FileNotFoundError:
        logger.error(f"2021MandateLetters.csv not found at: {csv_file_path}")
        return {}
    except Exception as e:
        logger.error(f"Error reading or processing 2021MandateLetters.csv: {e}", exc_info=True)
        return {}
# --- End Helper Function ---


def process_mlc_csv(file_path, mandate_url_map):
    """Processes the 2021-mandate-commitments.csv and adds/updates docs in Firestore."""
    df = pd.read_csv(file_path)
    promises_collection = db.collection('promises') # <<< CHANGED collection name

    processed_count = 0
    skipped_count = 0
    updated_count = 0

    logger.info(f"Starting processing of {len(df)} rows from {file_path}")

    for index, row in df.iterrows():
        try:
            promise_id_str = str(row['MLC ID'])
            # Basic validation
            if not promise_id_str or promise_id_str.lower() == 'nan':
                 logger.warning(f"Skipping row {index+2} due to missing or invalid 'MLC ID'.")
                 skipped_count += 1
                 continue

            # Standardize lead department
            reporting_lead_raw = str(row.get('Reporting Lead', '')).strip()
            reporting_lead_standardized = standardize_department_name(reporting_lead_raw)
            if not reporting_lead_standardized:
                logger.warning(f"Could not standardize Reporting Lead '{reporting_lead_raw}' for MLC ID {promise_id_str}. Will store raw value only.")
                # Store raw if standardization fails but still proceed

            # Parse and standardize 'All ministers'
            all_ministers_raw = str(row.get('All ministers', '')).strip()
            all_ministers_standardized = []
            if all_ministers_raw and all_ministers_raw.lower() != 'nan':
                ministers_list = all_ministers_raw.split(';')
                for m in ministers_list:
                    std_name = standardize_department_name(m.strip())
                    if std_name and std_name not in all_ministers_standardized: # Add if standardized and not duplicate
                        all_ministers_standardized.append(std_name)
                    elif not std_name:
                         logger.debug(f"Could not standardize minister '{m.strip()}' in 'All ministers' for MLC ID {promise_id_str}.")


            # Look up the source document URL using the standardized lead department
            source_url = None
            if reporting_lead_standardized:
                source_url = mandate_url_map.get(reporting_lead_standardized)
                if not source_url:
                    logger.warning(f"No mandate letter URL found in map for standardized lead department '{reporting_lead_standardized}' (MLC ID: {promise_id_str}).")
            else:
                 logger.warning(f"Cannot look up mandate letter URL for MLC ID {promise_id_str} because standardized lead department is missing.")

            # Ensure commitment text is a string
            commitment_text = str(row.get('Commitment', '')).strip()
            if not commitment_text or commitment_text.lower() == 'nan':
                 logger.warning(f"Skipping row {index+2} (MLC ID: {promise_id_str}) due to missing 'Commitment' text.")
                 skipped_count += 1
                 continue


            promise_doc = {
                'promise_id': promise_id_str,
                'text': commitment_text,
                'key_points': [], # Kept empty list for future LLM summary
                'source_document_url': source_url, # Use looked-up URL
                'source_type': 'Mandate Letter Commitment (Structured)',
                'date_issued': '2021-12-16', # Common date for 2021 letters
                'parliament_session_id': "44", # NEW: Added parliament_session_id
                'candidate_or_government': 'Government of Canada (2021 Mandate)',
                'party': 'Liberal Party of Canada',
                'category': None, # To be filled later
                'responsible_department_lead': reporting_lead_standardized if reporting_lead_standardized else None, # Store None if standardization failed
                'relevant_departments': all_ministers_standardized, # Store list of standardized names
                'mlc_raw_reporting_lead': reporting_lead_raw if reporting_lead_raw.lower() != 'nan' else None, # Keep raw for reference, store None if NaN
                'mlc_raw_all_ministers': all_ministers_raw if all_ministers_raw.lower() != 'nan' else None,    # Keep raw for reference, store None if NaN

                # --- New Fields --- (Confirmed Present)
                'commitment_history_rationale': None, # Placeholder for future LLM enrichment
                'linked_evidence_ids': [], # Placeholder for linking to evidence items

                # --- Timeline Placeholders (REMOVED) ---
                # 'timeline_first_mention_date': None,
                # 'timeline_last_mention_date': None,
                # 'timeline_total_mentions': 0,
                # 'timeline_events': [],
                # 'timeline_initial_occurrence_text': None,

                # --- Metadata --- (Confirmed Present)
                'ingested_at': firestore.SERVER_TIMESTAMP, # Track when this record was ingested/updated
                'last_updated_at': firestore.SERVER_TIMESTAMP, # Track updates
            }

            # Use set with merge=True to update existing or create new
            # This requires fetching first to check if it's an update or new creation for logging
            doc_ref = promises_collection.document(promise_doc['promise_id'])
            doc_snapshot = doc_ref.get()

            # Store merge_fields=True to only update specified fields if doc exists
            doc_ref.set(promise_doc, merge=True) 

            if doc_snapshot.exists:
                 updated_count += 1
                 logger.debug(f"Updated promise document for MLC ID: {promise_doc['promise_id']}")
            else:
                 processed_count += 1
                 logger.debug(f"Added new promise document for MLC ID: {promise_doc['promise_id']}")

        except Exception as e:
            logger.error(f"Error processing row {index+2} (MLC ID: {row.get('MLC ID', 'N/A')}): {e}", exc_info=True)
            skipped_count += 1


    logger.info(f"Finished processing MLC CSV.")
    logger.info(f"  - Added: {processed_count} new promise documents.")
    logger.info(f"  - Updated: {updated_count} existing promise documents.")
    logger.info(f"  - Skipped: {skipped_count} rows due to errors or missing data.")

# --- Main execution ---
if __name__ == "__main__":
    # Determine base directory (PromiseTracker)
    script_dir = os.path.dirname(os.path.abspath(__file__))
    base_dir = os.path.dirname(script_dir) # Moves up from 'scripts' to 'PromiseTracker'

    # --- Path to MandateLetters.csv ---
    mandate_letters_csv_path = os.path.join(base_dir, 'raw-data', '2021MandateLetters.csv')
    if not os.path.exists(mandate_letters_csv_path):
        logger.error(f"ERROR: 2021MandateLetters.csv not found at: {mandate_letters_csv_path}")
        exit("Exiting: 2021MandateLetters.csv file missing.")

    # Load the URL map first
    mandate_url_map = load_mandate_letter_urls(mandate_letters_csv_path)
    if not mandate_url_map:
         logger.warning("Mandate letter URL map is empty. Source URLs for commitments will likely be null.")
         # Continue processing even if map is empty, just won't populate URLs


    # --- Path to 2021-mandate-commitments.csv ---
    commitments_csv_path = os.path.join(base_dir, 'raw-data', '2021-mandate-commitments.csv')
    if not os.path.exists(commitments_csv_path):
        logger.error(f"ERROR: 2021-mandate-commitments.csv not found at: {commitments_csv_path}")
        exit("Exiting: Commitments CSV file missing.")


    logger.info(f"Processing Commitments CSV file from: {commitments_csv_path}")
    process_mlc_csv(commitments_csv_path, mandate_url_map) # Pass the map to the function

    logger.info("Mandate processing script finished.")