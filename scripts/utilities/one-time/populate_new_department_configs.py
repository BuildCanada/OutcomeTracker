# PromiseTracker/scripts/utilities/one-time/populate_new_department_configs.py
import firebase_admin
from firebase_admin import credentials, firestore
import os
import logging
from dotenv import load_dotenv
import argparse
import csv
import io # Required to read string data as CSV
import re # For slugifying

# --- Load Environment Variables ---
load_dotenv()
# --- End Load Environment Variables ---

# --- Logger Setup ---
logging.basicConfig(level=logging.INFO,
                    format='%(asctime)s - %(levelname)s - %(filename)s:%(lineno)d - %(message)s',
                    datefmt='%Y-%m-%d %H:%M:%S')
logger = logging.getLogger(__name__)
# --- End Logger Setup ---

# Data provided by the user
CSV_DATA = """variant_text_raw,variant_text_normalized,trudeau_minister,department_official_name,display_short_name
"Minister of International Trade","minister of international trade","Minister of International Trade","Global Affairs Canada","International Trade"
"Minister responsible for Canada Economic Development for Quebec Regions","minister responsible for canada economic development for quebec regions","Minister responsible for Canada Economic Development for Quebec Regions","Canada Economic Development for Quebec Regions","CED Quebec"
"Minister responsible for the Atlantic Canada Opportunities Agency","minister responsible for the atlantic canada opportunities agency","Minister responsible for the Atlantic Canada Opportunities Agency","Atlantic Canada Opportunities Agency","ACOA"
"President of the King's Privy Council for Canada and Minister responsible for Canada-U.S. Trade, Intergovernmental Affairs and One Canadian Economy","president of the king's privy council for canada and minister responsible for canada-u.s. trade, intergovernmental affairs and one canadian economy","President of the King's Privy Council for Canada and Minister responsible for Canada-U.S. Trade, Intergovernmental Affairs and One Canadian Economy","Privy Council Office / Intergovernmental Affairs Secretariat","Privy Council / IGA"
"Secretary of State (Children and Youth)","secretary of state (children and youth)","Secretary of State (Children and Youth)","Employment and Social Development Canada","Children/Youth (ESDC)"
"Secretary of State (International Development)","secretary of state (international development)","Secretary of State (International Development)","Global Affairs Canada","Global Affairs"
"Secretary of State (Rural Development)","secretary of state (rural development)","Secretary of State (Rural Development)","Innovation, Science and Economic Development Canada / Infrastructure Canada","Rural Development"
"Secretary of State (Small Business and Tourism)","secretary of state (small business and tourism)","Secretary of State (Small Business and Tourism)","Innovation, Science and Economic Development Canada","ISED"
"""

def initialize_firestore():
    """Initializes Firebase Admin SDK and returns a Firestore client instance."""
    db_client = None
    if not firebase_admin._apps:
        try:
            firebase_admin.initialize_app()
            project_id = os.getenv('FIREBASE_PROJECT_ID', '[Not Set - Using Default]')
            logger.info(f"Successfully connected to CLOUD Firestore (Project: {project_id}) using default credentials.")
            db_client = firestore.client()
        except Exception as e_default:
            logger.warning(f"Cloud Firestore init with default creds failed: {e_default}")
            cred_path = os.getenv('FIREBASE_SERVICE_ACCOUNT_KEY_PATH')
            if cred_path:
                try:
                    logger.info(f"Attempting Firebase init with service account key from env var: {cred_path}")
                    cred = credentials.Certificate(cred_path)
                    firebase_admin.initialize_app(cred)
                    project_id_sa = os.getenv('FIREBASE_PROJECT_ID', '[Not Set - Using Service Account]')
                    logger.info(f"Successfully connected to CLOUD Firestore (Project: {project_id_sa}) via service account.")
                    db_client = firestore.client()
                except Exception as e_sa:
                    logger.critical(f"Firebase init with service account key from {cred_path} failed: {e_sa}", exc_info=True)
            else:
                logger.warning("FIREBASE_SERVICE_ACCOUNT_KEY_PATH environment variable not set.")
    else:
        logger.info("Firebase Admin SDK already initialized. Getting Firestore client.")
        db_client = firestore.client()
    return db_client

def slugify(text):
    """Convert text to a slug. Lowercase, remove non-word chars, replace spaces with hyphens."""
    if not text:
        return ''
    text = text.lower()
    text = re.sub(r'[^\w\s-]', '', text)  # remove non-word characters
    text = re.sub(r'[\s_]+', '-', text) # replace spaces and underscores with hyphens
    text = text.strip('-') # remove leading/trailing hyphens
    return text

def populate_new_configs(db, dry_run: bool):
    logger.info("--- Starting population of new department_config documents ---")
    
    data_io = io.StringIO(CSV_DATA)
    reader = csv.DictReader(data_io)
    
    added_count = 0
    skipped_count = 0
    error_count = 0

    for row_index, row in enumerate(reader):
        try:
            official_name = row.get('department_official_name', '').strip()
            display_short_name = row.get('display_short_name', '').strip()
            variant_raw = row.get('variant_text_raw', '').strip()
            variant_normalized = row.get('variant_text_normalized', '').strip()

            if not official_name:
                logger.warning(f"Row {row_index + 2}: Skipping due to missing 'department_official_name'.")
                skipped_count += 1
                continue

            department_slug = slugify(official_name)
            if not department_slug:
                logger.warning(f"Row {row_index + 2}: Could not generate slug for '{official_name}'. Skipping.")
                skipped_count +=1
                continue
            
            doc_ref = db.collection('department_config').document(department_slug)

            if not dry_run:
                doc_snapshot = doc_ref.get()
                if doc_snapshot.exists:
                    logger.info(f"Row {row_index + 2}: Document with ID '{department_slug}' for '{official_name}' already exists. Updating variants.")
                    # Add new variants if they don't exist
                    existing_variants = doc_snapshot.to_dict().get('name_variants', [])
                    updated_variants = list(set(existing_variants + [v for v in [variant_raw, variant_normalized] if v]))
                    doc_ref.update({'name_variants': updated_variants, 'updated_at': firestore.SERVER_TIMESTAMP})
                    added_count +=1 # Counting as processed/updated
                else:
                    name_variants = []
                    if variant_raw:
                        name_variants.append(variant_raw)
                    if variant_normalized and variant_normalized != variant_raw:
                        name_variants.append(variant_normalized)
                    if not name_variants and official_name.lower() not in name_variants: # Add official name as a variant if others are missing
                        name_variants.append(official_name.lower())


                    new_doc_data = {
                        'official_full_name': official_name,
                        'display_short_name': display_short_name if display_short_name else official_name,
                        'department_slug': department_slug,
                        'name_variants': list(set(name_variants)), # Ensure uniqueness
                        'bc_priority': 2,
                        'minister_of_state': False, # Default assumption
                        'created_at': firestore.SERVER_TIMESTAMP,
                        'updated_at': firestore.SERVER_TIMESTAMP,
                        'notes': 'Added by populate_new_department_configs.py script'
                    }
                    doc_ref.set(new_doc_data)
                    logger.info(f"Row {row_index + 2}: Added new department_config for '{official_name}' with ID '{department_slug}'.")
                    added_count += 1
            else: # Dry run
                logger.info(f"[DRY RUN] Row {row_index + 2}: Would add/update department_config for '{official_name}' with ID '{department_slug}'.")
                logger.info(f"[DRY RUN]    Variants: {[v for v in [variant_raw, variant_normalized] if v]}")
                added_count += 1


        except Exception as e:
            logger.error(f"Row {row_index + 2}: Error processing row {row}: {e}", exc_info=True)
            error_count += 1

    logger.info("--- Finished populating new department_config documents ---")
    logger.info(f"Summary:")
    logger.info(f"  Documents processed/added/updated (or would be): {added_count}")
    logger.info(f"  Documents skipped: {skipped_count}")
    logger.info(f"  Errors: {error_count}")

def main():
    parser = argparse.ArgumentParser(description="Populate new department_config documents from embedded CSV data.")
    parser.add_argument("--dry-run", action="store_true", help="Log changes without writing to Firestore.")
    args = parser.parse_args()

    if args.dry_run:
        logger.info("DRY RUN mode enabled. No actual writes to Firestore will occur.")

    db = initialize_firestore()
    if not db:
        logger.critical("Failed to initialize Firestore. Exiting.")
        return

    populate_new_configs(db, args.dry_run)
    
    logger.info("Script completed.")

if __name__ == "__main__":
    main() 