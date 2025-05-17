import firebase_admin
from firebase_admin import credentials, firestore
import os
import requests
import xml.etree.ElementTree as ET
import logging
import time
import argparse
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# --- Logger Setup ---
logging.basicConfig(level=logging.INFO,
                    format='%(asctime)s - %(levelname)s - %(filename)s:%(lineno)d - %(message)s',
                    datefmt='%Y-%m-%d %H:%M:%S')
logger = logging.getLogger(__name__)
# --- End Logger Setup ---

# --- common_utils import --- 
# Assuming common_utils.py is in the same directory or Python path correctly configured
try:
    from common_utils import standardize_department_name
except ImportError:
    logger.critical("common_utils.py not found or standardize_department_name cannot be imported.")
    # Define a basic placeholder if common_utils is missing, to allow script to run with warnings
    def standardize_department_name(title_or_name): 
        logger.warning(f"Using PLACEHOLDER standardize_department_name for '{title_or_name}'")
        if title_or_name:
            if "minister of " in title_or_name.lower():
                dept_part = title_or_name.lower().split("minister of ")[-1]
                return f"Dept for {dept_part.title()}" # Simple extraction
            return f"Dept from {title_or_name.split()[-1] if title_or_name.split() else 'Unknown'}"
        return None
# --- End common_utils import ---

# --- Firebase Configuration ---
db = None
if not firebase_admin._apps:
    try:
        cred_path = os.getenv('GOOGLE_APPLICATION_CREDENTIALS')
        if cred_path:
            cred = credentials.Certificate(cred_path)
            firebase_admin.initialize_app(cred)
            logger.info("Firebase Admin SDK initialized using Application Credentials.")
        else:
            firebase_admin.initialize_app()
            logger.info("Firebase Admin SDK initialized with default or environment-provided credentials.")
        
        project_id = os.getenv('FIREBASE_PROJECT_ID', firebase_admin.get_app().project_id if firebase_admin.get_app() else '[Cloud Project ID Not Set]')
        logger.info(f"Python (UpdateSponsorDepts): Connected to CLOUD Firestore (Project: {project_id}).")
        db = firestore.client()
    except Exception as e:
        logger.critical(f"Firebase init failed: {e}", exc_info=True)
        exit("Exiting: Firebase connection failed.")
else:
    db = firestore.client()
    logger.info("Firebase Admin SDK already initialized.")

if db is None:
    exit("Exiting: Firestore client not available.")
# --- End Firebase Configuration ---

# --- Constants ---
BILLS_DATA_COLLECTION = 'bills_data'
HEADERS = {'User-Agent': 'PromiseTrackerBot-UpdateSponsorDept/1.0'}
# --- End Constants ---

def fetch_xml_from_url(xml_url):
    """Fetches and parses XML from a given URL."""
    if not xml_url:
        logger.warning("XML URL is missing. Cannot fetch.")
        return None
    try:
        logger.debug(f"Fetching XML from: {xml_url}")
        response = requests.get(xml_url, headers=HEADERS, timeout=30)
        response.raise_for_status()
        return ET.fromstring(response.content)
    except requests.exceptions.RequestException as e:
        logger.error(f"Error fetching XML from {xml_url}: {e}")
    except ET.ParseError as e:
        logger.error(f"Error parsing XML from {xml_url}: {e}")
    except Exception as e:
        logger.error(f"An unexpected error occurred fetching/parsing {xml_url}: {e}")
    return None

def determine_sponsoring_department_from_xml_node(bill_xml_root_node, bill_number_for_logging="N/A"):
    """Determines the sponsoring department from a parsed <Bill> XML node."""
    if bill_xml_root_node is None:
        return None

    bill_node = bill_xml_root_node.find('.//Bill') # Expects root of detailed bill XML to be <Bills><Bill> or just <Bill>
    if bill_node is None and bill_xml_root_node.tag == 'Bill': # If the passed root is already the <Bill> node
        bill_node = bill_xml_root_node
    elif bill_node is None: # Try finding Bill as a direct child if root is <Bills>
        bill_node = bill_xml_root_node.find('Bill')
        if bill_node is None:
            logger.error(f"Could not find <Bill> node in provided XML for bill {bill_number_for_logging}")
            return None

    sponsor_name = bill_node.findtext('SponsorPersonName', default=None)
    sponsor_title = bill_node.findtext('SponsorAffiliationTitleEn', default=None)
    
    calculated_department = None
    if sponsor_title:
        is_senator_by_title = "senator" in sponsor_title.lower()
        is_senator_by_name = sponsor_name and sponsor_name.lower().startswith("sen.")
        if is_senator_by_title or is_senator_by_name:
            calculated_department = None
        else:
            calculated_department = standardize_department_name(sponsor_title)
            if not calculated_department and sponsor_name and not (is_senator_by_name or is_senator_by_title):
                logger.info(f"Attempting department standardization by sponsor_name ('{sponsor_name}') as fallback for bill {bill_number_for_logging} because title '{sponsor_title}' did not yield a department.")
                sponsoring_department_from_name = standardize_department_name(sponsor_name)
                if sponsoring_department_from_name:
                    calculated_department = sponsoring_department_from_name
    elif sponsor_name:
        if not sponsor_name.lower().startswith("sen."):
            logger.info(f"Attempting department standardization by sponsor_name ('{sponsor_name}') for bill {bill_number_for_logging} as no sponsor title was present.")
            calculated_department = standardize_department_name(sponsor_name)
            
    return calculated_department

def update_sponsoring_departments_for_bills(limit=None):
    logger.info("--- Starting Sponsoring Department Update Process ---")
    
    bills_query = db.collection(BILLS_DATA_COLLECTION).stream()
    if limit:
        # Firestore's .limit() applies to the stream directly for server-side limiting is complex with .stream()
        # For simplicity with .stream(), we'll limit client-side after fetching. 
        # This is not ideal for very large collections if limit is small.
        # A more robust solution for large collections would use cursors/pagination.
        logger.info(f"Processing up to {limit} bills (client-side limit after streaming all). Consider pagination for very large datasets.")

    processed_count = 0
    updated_count = 0

    for bill_doc_snap in bills_query:
        if limit and processed_count >= limit:
            logger.info(f"Reached client-side processing limit of {limit} bills.")
            break
        
        processed_count += 1
        bill_id = bill_doc_snap.id
        bill_data = bill_doc_snap.to_dict()
        bill_number_code = bill_data.get('bill_number_code', bill_id) # For logging

        logger.info(f"Checking Bill {bill_number_code} (Parl ID: {bill_id}) - {processed_count}...")

        xml_url = bill_data.get('legisinfo_detail_xml_url')
        current_department = bill_data.get('sponsoring_department')

        if not xml_url:
            logger.warning(f"Skipping Bill {bill_number_code} (Parl ID: {bill_id}): missing 'legisinfo_detail_xml_url'.")
            continue

        xml_root = fetch_xml_from_url(xml_url)
        if not xml_root:
            logger.warning(f"Skipping Bill {bill_number_code} (Parl ID: {bill_id}): failed to fetch or parse XML.")
            continue
        
        new_department = determine_sponsoring_department_from_xml_node(xml_root, bill_number_code)

        if new_department != current_department:
            try:
                db.collection(BILLS_DATA_COLLECTION).document(bill_id).update({'sponsoring_department': new_department})
                logger.info(f"  Updated Bill {bill_number_code} (Parl ID: {bill_id}): sponsoring_department changed from '{current_department}' to '{new_department}'.")
                updated_count += 1
            except Exception as e_update:
                logger.error(f"  Failed to update sponsoring_department for Bill {bill_number_code} (Parl ID: {bill_id}): {e_update}", exc_info=True)
        else:
            logger.info(f"  No change needed for Bill {bill_number_code} (Parl ID: {bill_id}): sponsoring_department is already '{current_department}'.")
        
        time.sleep(0.3) # Be polite to the LEGISinfo server

    logger.info("--- Sponsoring Department Update Process Finished ---")
    logger.info(f"Total bills checked: {processed_count -1 if limit and processed_count > limit else processed_count}") # Adjust if limit was hit mid-process
    logger.info(f"Total bills updated: {updated_count}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Update sponsoring departments for bills in Firestore by re-fetching and re-parsing their LEGISinfo XML.")
    parser.add_argument("--limit", type=int, default=None, help="Limit the number of bills to process.")
    args = parser.parse_args()

    update_sponsoring_departments_for_bills(limit=args.limit) 