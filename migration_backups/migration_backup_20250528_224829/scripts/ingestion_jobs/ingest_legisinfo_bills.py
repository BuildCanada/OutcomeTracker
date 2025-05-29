"""
Ingests raw bill JSON data from LEGISinfo into Firestore.
Fetches the main bill list from LEGISinfo JSON API, then fetches detailed JSON for each bill
and stores the raw content for later processing.

CLI arguments:
--limit: Limit the number of bills to process. Default: None (process all)
--dry_run: If True, will not write to Firestore. Default: False
--parliament_session_target: Target parliament session (e.g., "45-1"). Default: None (process all)
--force_reprocessing: Force re-fetch even if LatestActivityDateTime hasn't changed. Default: False
--min_parliament: Minimum parliament number to process (default: 44). Filters out older parliaments for efficiency.
--log_level: Set the logging level. Default: INFO
--JSON: If True, output raw bill data to a JSON file instead of Firestore. Default: False
--json_output_dir: Directory to write JSON output files. Default: ./scripts/JSON_outputs/legisinfo_raw

For daily scheduled runs, use default settings which will:
1. Process bills from Parliament 44 onwards (--min_parliament 44)
2. Use idempotency to only fetch bills with changed LatestActivityDateTime
3. Automatically detect and ingest new bills

Stage 1 of LEGISinfo two-stage ingestion. Feeds into process_raw_legisinfo_to_evidence.py.
"""

import os
import logging
import json
import requests
import hashlib
from datetime import datetime, timezone
from dotenv import load_dotenv
import firebase_admin
from firebase_admin import credentials, firestore
import argparse
import time
from dateutil import parser as dateutil_parser

# --- Configuration ---
load_dotenv()

# --- Logger Setup ---
logging.basicConfig(level=logging.INFO,
                    format='%(asctime)s - %(levelname)s - %(filename)s:%(lineno)d - %(message)s',
                    datefmt='%Y-%m-%d %H:%M:%S')
logger = logging.getLogger("ingest_legisinfo_raw_bills")
# --- End Logger Setup ---

# --- Constants ---
BILL_LIST_JSON_URL = "https://www.parl.ca/legisinfo/en/bills/json"
RAW_LEGISINFO_BILLS_COLLECTION = "raw_legisinfo_bill_details"
HEADERS = {'User-Agent': 'BuildCanadaPromiseTrackerBot/1.0'}
# Define JSON_OUTPUT_DIR relative to the script's location
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
JSON_OUTPUT_DIR = os.path.join(SCRIPT_DIR, "..", "JSON_outputs", "legisinfo_raw")
# Default minimum parliament number for daily ingestion (start from Parliament 44)
DEFAULT_MIN_PARLIAMENT = 44
# --- End Constants ---

# --- Firebase Configuration ---
db = None
if not firebase_admin._apps:
    try:
        firebase_admin.initialize_app()
        db = firestore.client()
        project_id = os.getenv('FIREBASE_PROJECT_ID', firebase_admin.get_app().project_id if firebase_admin.get_app() else '[Cloud Project ID Not Set]')
        logger.info(f"Connected to CLOUD Firestore (Project: {project_id}).")
    except Exception as e:
        logger.critical(f"Firebase init failed for Cloud: {e}", exc_info=True)
        exit("Exiting: Cloud Firebase connection failed.")
else:
    db = firestore.client()

if db is None:
    exit("Exiting: Firestore client not available.")
# --- End Firebase Configuration ---

def parse_legisinfo_datetime(date_str):
    """Parse datetime string from LEGISinfo JSON API"""
    if not date_str:
        return None
    try:
        return datetime.fromisoformat(date_str).astimezone(timezone.utc)
    except ValueError:
        logger.warning(f"Could not parse LEGISinfo date string: {date_str}")
        return None

def fetch_bill_list_json():
    """Fetch the main bill list from LEGISinfo JSON API"""
    logger.info(f"Fetching bill list from: {BILL_LIST_JSON_URL}")
    try:
        response = requests.get(BILL_LIST_JSON_URL, headers=HEADERS, timeout=60)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        logger.error(f"Error fetching bill list JSON: {e}")
        return None
    except json.JSONDecodeError as e:
        logger.error(f"Error parsing bill list JSON: {e}")
        return None

def fetch_bill_details_json(parliament_num, session_num, bill_code):
    """Fetch detailed JSON for a specific bill"""
    url = f"https://www.parl.ca/legisinfo/en/bill/{parliament_num}-{session_num}/{bill_code}/json?view=details"
    logger.info(f"Fetching details for Bill {bill_code} from {url}")
    try:
        response = requests.get(url, headers=HEADERS, timeout=45)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        logger.error(f"Error fetching details for Bill {bill_code}: {e}")
        return None
    except json.JSONDecodeError as e:
        logger.error(f"Error parsing JSON for Bill {bill_code}: {e}")
        return None

def filter_bills_by_session(bills_data, target_session):
    """Filter bills by parliament session if specified"""
    if not target_session:
        return bills_data
    
    try:
        target_parl, target_sess = target_session.split('-')
        filtered_bills = []
        for bill in bills_data:
            if (str(bill.get('ParliamentNumber')) == target_parl and 
                str(bill.get('SessionNumber')) == target_sess):
                filtered_bills.append(bill)
        logger.info(f"Filtered to {len(filtered_bills)} bills matching session {target_session}")
        return filtered_bills
    except ValueError:
        logger.error(f"Invalid parliament session format: {target_session}. Use format like '45-1'")
        return bills_data

def filter_bills_by_min_parliament(bills_data, min_parliament=None):
    """Filter out bills from parliaments older than min_parliament"""
    if min_parliament is None:
        min_parliament = DEFAULT_MIN_PARLIAMENT
    
    filtered_bills = []
    excluded_count = 0
    
    for bill in bills_data:
        parliament_num = bill.get('ParliamentNumber')
        if parliament_num and int(parliament_num) >= min_parliament:
            filtered_bills.append(bill)
        else:
            excluded_count += 1
    
    if excluded_count > 0:
        logger.info(f"Excluded {excluded_count} bills from parliaments < {min_parliament}")
    
    logger.info(f"Filtered to {len(filtered_bills)} bills from parliament {min_parliament}+")
    return filtered_bills

def load_rss_filter_list(rss_filter_file):
    """Load list of bills to process from RSS filter file"""
    if not rss_filter_file or not os.path.exists(rss_filter_file):
        return None
    
    try:
        with open(rss_filter_file, 'r', encoding='utf-8') as f:
            rss_data = json.load(f)
        
        if not isinstance(rss_data, list):
            logger.error(f"RSS filter file should contain a JSON array, got {type(rss_data)}")
            return None
        
        # Extract human-readable IDs for filtering
        bill_ids = set()
        for item in rss_data:
            if isinstance(item, dict) and 'human_readable_id' in item:
                bill_ids.add(item['human_readable_id'])
            elif isinstance(item, str):
                # If it's just a list of strings
                bill_ids.add(item)
        
        logger.info(f"Loaded RSS filter with {len(bill_ids)} bills: {rss_filter_file}")
        return bill_ids
        
    except Exception as e:
        logger.error(f"Error loading RSS filter file {rss_filter_file}: {e}")
        return None

def filter_bills_by_rss_list(bills_data, rss_bill_ids):
    """Filter bills to only those in the RSS update list"""
    if not rss_bill_ids:
        return bills_data
    
    filtered_bills = []
    
    for bill in bills_data:
        parliament_num = str(bill.get('ParliamentNumber'))
        session_num = str(bill.get('SessionNumber'))
        bill_code = bill.get('BillNumberFormatted', '')
        
        # Create human-readable ID to match RSS format
        human_readable_id = f"{parliament_num}-{session_num}_{bill_code}"
        
        if human_readable_id in rss_bill_ids:
            filtered_bills.append(bill)
    
    logger.info(f"RSS filter: Found {len(filtered_bills)} bills from RSS update list out of {len(bills_data)} total bills")
    return filtered_bills

def should_update_bill(bill_data, force_reprocessing):
    """Check if bill should be updated based on LatestActivityDateTime"""
    bill_id = str(bill_data.get('BillId'))
    parliament_num = str(bill_data.get('ParliamentNumber'))
    session_num = str(bill_data.get('SessionNumber'))
    bill_code = bill_data.get('BillNumberFormatted', '')
    latest_activity_str = bill_data.get('LatestActivityDateTime')
    
    # Create human-readable document ID
    human_readable_doc_id = f"{parliament_num}-{session_num}_{bill_code}"
    
    if force_reprocessing:
        logger.debug(f"Force reprocessing enabled for Bill {bill_code} ({human_readable_doc_id})")
        return True
    
    try:
        # Check existing document using new document ID format
        doc_ref = db.collection(RAW_LEGISINFO_BILLS_COLLECTION).document(human_readable_doc_id)
        existing_doc = doc_ref.get()
        
        if not existing_doc.exists:
            logger.debug(f"Bill {bill_code} ({human_readable_doc_id}) not found in database, will fetch")
            return True
        
        stored_data = existing_doc.to_dict()
        stored_last_activity = stored_data.get('feed_last_major_activity_date')
        
        # Parse current activity date
        current_activity_date = parse_legisinfo_datetime(latest_activity_str)
        
        # Compare dates
        if isinstance(stored_last_activity, datetime) and current_activity_date:
            if current_activity_date > stored_last_activity:
                logger.info(f"Bill {bill_code} ({human_readable_doc_id}) has newer activity date, will update")
                return True
            else:
                logger.debug(f"Bill {bill_code} ({human_readable_doc_id}) is up to date")
                return False
        else:
            # If we can't compare, err on side of updating
            logger.debug(f"Bill {bill_code} ({human_readable_doc_id}) missing date comparison data, will update")
            return True
            
    except Exception as e:
        logger.error(f"Error checking update status for Bill {bill_code} ({human_readable_doc_id}): {e}")
        return True  # Default to updating on error

def save_raw_bill_data(bill_feed_data, detailed_json_data):
    """Save raw bill JSON data to Firestore"""
    try:
        bill_id = str(bill_feed_data.get('BillId'))
        parliament_num = str(bill_feed_data.get('ParliamentNumber'))
        session_num = str(bill_feed_data.get('SessionNumber'))
        bill_code = bill_feed_data.get('BillNumberFormatted', '')
        latest_activity_str = bill_feed_data.get('LatestActivityDateTime')
        
        # Create human-readable document ID: parliament-session_billnumber (e.g., "44-1_C-69")
        human_readable_doc_id = f"{parliament_num}-{session_num}_{bill_code}"
        
        # Construct the detail URL
        detail_url = f"https://www.parl.ca/legisinfo/en/bill/{parliament_num}-{session_num}/{bill_code}/json?view=details"
        
        # Prepare document data
        doc_data = {
            'parl_id': bill_id,  # Keep original LEGISinfo BillId for reference
            'bill_number_code_feed': bill_code,
            'parliament_session_id': f"{parliament_num}-{session_num}",  # Consolidated session info
            'source_detailed_json_url': detail_url,
            'raw_json_content': json.dumps(detailed_json_data),
            'feed_last_major_activity_date': parse_legisinfo_datetime(latest_activity_str),
            'ingested_at': firestore.SERVER_TIMESTAMP,
            'processing_status': 'pending_processing',
            'last_attempted_processing_at': None
        }
        
        # Save to Firestore using human-readable document ID
        doc_ref = db.collection(RAW_LEGISINFO_BILLS_COLLECTION).document(human_readable_doc_id)
        doc_ref.set(doc_data, merge=True)
        
        logger.info(f"Saved raw data for Bill {bill_code} (Doc ID: {human_readable_doc_id})")
        return True
        
    except Exception as e:
        logger.error(f"Error saving raw data for Bill {bill_feed_data.get('BillNumberFormatted', 'Unknown')}: {e}", exc_info=True)
        return False

def main():
    parser = argparse.ArgumentParser(description="Ingest raw LEGISinfo bill JSON data into Firestore.")
    parser.add_argument("--limit", type=int, help="Limit the number of bills to process")
    parser.add_argument("--dry_run", action="store_true", help="Perform a dry run without writing to Firestore")
    parser.add_argument("--parliament_session_target", type=str, help="Target parliament session (e.g., '45-1')")
    parser.add_argument("--force_reprocessing", action="store_true", help="Force re-fetch even if no changes detected")
    parser.add_argument("--min_parliament", type=int, default=DEFAULT_MIN_PARLIAMENT, 
                       help=f"Minimum parliament number to process (default: {DEFAULT_MIN_PARLIAMENT})")
    parser.add_argument("--log_level", type=str, default="INFO", 
                       choices=["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"],
                       help="Set the logging level")
    parser.add_argument("--JSON", action="store_true", help="Output raw bill data to a JSON file instead of Firestore")
    parser.add_argument("--json_output_dir", type=str, default=JSON_OUTPUT_DIR, help="Directory to write JSON output files")
    parser.add_argument("--rss_filter_file", type=str, help="JSON file with list of bills from RSS updates to process (enables RSS-targeted processing)")
    
    args = parser.parse_args()
    logger.setLevel(getattr(logging, args.log_level.upper()))
    
    if args.dry_run:
        logger.info("*** DRY RUN MODE ENABLED - No data will be written to Firestore ***")
    if args.JSON:
        logger.info(f"*** JSON OUTPUT MODE ENABLED - Raw bill data will be written to {args.json_output_dir} ***")
    if args.rss_filter_file:
        logger.info(f"*** RSS FILTER MODE ENABLED - Processing bills from {args.rss_filter_file} ***")
    
    # Load RSS filter list if specified
    rss_bill_ids = load_rss_filter_list(args.rss_filter_file) if args.rss_filter_file else None
    
    # Fetch bill list
    bills_json_data = fetch_bill_list_json()
    if not bills_json_data:
        logger.critical("Failed to fetch bill list. Exiting.")
        return
    
    # Apply RSS filter first if available (most selective)
    if rss_bill_ids:
        filtered_bills = filter_bills_by_rss_list(bills_json_data, rss_bill_ids)
        if not filtered_bills:
            logger.info("No bills found matching RSS filter. Exiting.")
            return
    else:
        # Apply minimum parliament filter first (unless specific session is targeted)
        if not args.parliament_session_target:
            filtered_bills = filter_bills_by_min_parliament(bills_json_data, args.min_parliament)
        else:
            filtered_bills = bills_json_data
            logger.info(f"Skipping minimum parliament filter due to specific session target: {args.parliament_session_target}")
        
        # Filter by specific session if specified (only if not using RSS filter)
        filtered_bills = filter_bills_by_session(filtered_bills, args.parliament_session_target)
    
    # Apply limit if specified
    if args.limit and args.limit > 0:
        filtered_bills = filtered_bills[:args.limit]
        logger.info(f"Limited to processing {len(filtered_bills)} bills")
    
    logger.info(f"Processing {len(filtered_bills)} bills")
    
    processed_count = 0
    updated_count = 0
    skipped_count = 0
    error_count = 0
    items_for_json_output = []
    
    for bill_data in filtered_bills:
        bill_id = bill_data.get('BillId')
        bill_code = bill_data.get('BillNumberFormatted', 'Unknown')
        parliament_num = bill_data.get('ParliamentNumber')
        session_num = bill_data.get('SessionNumber')
        
        logger.info(f"Processing Bill {bill_code} (ID: {bill_id}, Parliament: {parliament_num}, Session: {session_num})")
        
        # Check if we should update this bill
        if not should_update_bill(bill_data, args.force_reprocessing):
            skipped_count += 1
            logger.info(f"Skipping Bill {bill_code} - no updates detected")
            continue
        
        # Fetch detailed JSON
        detailed_json = fetch_bill_details_json(parliament_num, session_num, bill_code)
        if not detailed_json:
            error_count += 1
            logger.error(f"Failed to fetch details for Bill {bill_code}")
            continue
        
        # Save to Firestore or JSON
        if args.JSON:
            # Create human-readable document ID for JSON output
            human_readable_doc_id = f"{parliament_num}-{session_num}_{bill_code}"
            
            # Prepare data for JSON output
            doc_data = {
                '_document_id': human_readable_doc_id,  # Include the document ID for reference
                'parl_id': str(bill_data.get('BillId')),
                'bill_number_code_feed': bill_code,
                'parliament_session_id': f"{parliament_num}-{session_num}",
                'source_detailed_json_url': f"https://www.parl.ca/legisinfo/en/bill/{parliament_num}-{session_num}/{bill_code}/json?view=details",
                'raw_json_content': json.dumps(detailed_json),
                'feed_last_major_activity_date': bill_data.get('LatestActivityDateTime'),
                'ingested_at': datetime.now(timezone.utc).isoformat(),
                'processing_status': 'pending_processing',
                'last_attempted_processing_at': None
            }
            items_for_json_output.append(doc_data)
            logger.info(f"Prepared for JSON output: Bill {bill_code} (ID: {bill_data.get('BillId')})")
            updated_count += 1
        elif not args.dry_run:
            if save_raw_bill_data(bill_data, detailed_json):
                updated_count += 1
            else:
                error_count += 1
        else:
            logger.info(f"[DRY RUN] Would save raw data for Bill {bill_code}")
            updated_count += 1
        
        processed_count += 1
        
        # Be polite to the API
        time.sleep(1.2)
    
    # Write JSON output if specified
    if args.JSON and items_for_json_output:
        try:
            os.makedirs(args.json_output_dir, exist_ok=True)
            timestamp_str = datetime.now().strftime("%Y%m%d_%H%M%S")
            json_filename = os.path.join(args.json_output_dir, f"raw_legisinfo_bills_{timestamp_str}.json")
            with open(json_filename, 'w', encoding='utf-8') as f:
                json.dump(items_for_json_output, f, indent=4, ensure_ascii=False)
            logger.info(f"Successfully wrote {len(items_for_json_output)} raw bill records to JSON file: {json_filename}")
        except Exception as e:
            logger.error(f"Error writing items to JSON file: {e}", exc_info=True)
            error_count += len(items_for_json_output)
    
    logger.info("--- LEGISinfo Raw Ingestion Summary ---")
    logger.info(f"Bills processed: {processed_count}")
    if args.JSON:
        logger.info(f"Bills prepared for JSON output: {updated_count}")
    elif args.dry_run:
        logger.info(f"Bills that would be updated (Dry Run): {updated_count}")
    else:
        logger.info(f"Bills updated in Firestore: {updated_count}")
    logger.info(f"Bills skipped (no changes): {skipped_count}")
    logger.info(f"Errors: {error_count}")

if __name__ == "__main__":
    main() 