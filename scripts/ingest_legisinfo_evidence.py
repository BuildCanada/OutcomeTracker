# scripts/ingest_legisinfo_evidence.py

import firebase_admin
from firebase_admin import firestore
import os
import requests
import xml.etree.ElementTree as ET # For parsing XML
from datetime import datetime, timezone
import time
import uuid # For fallback unique IDs
import logging
from dotenv import load_dotenv

# --- Load Environment Variables ---
load_dotenv()
# --- End Load Environment Variables ---

# --- Logger Setup --- 
logging.basicConfig(level=logging.INFO, 
                    format='%(asctime)s - %(levelname)s - %(filename)s:%(lineno)d - %(message)s',
                    datefmt='%Y-%m-%d %H:%M:%S')
logger = logging.getLogger(__name__)
# --- End Logger Setup ---

# --- Firebase Configuration ---
# (Standard Cloud Firestore connection logic - relies on GOOGLE_APPLICATION_CREDENTIALS)
db = None 
if not firebase_admin._apps:
    try:
        firebase_admin.initialize_app() 
        project_id = os.getenv('FIREBASE_PROJECT_ID', '[Not Set]')
        logger.info(f"Python (LEGISinfo Ingest): Connected to CLOUD Firestore (Project: {project_id}).")
        db = firestore.client()
    except Exception as e:
        logger.critical(f"Firebase init failed for Cloud: {e}", exc_info=True)
        logger.critical("Ensure GOOGLE_APPLICATION_CREDENTIALS env var is set correctly.")
        exit("Exiting: Cloud Firebase connection failed.")
else:
    logger.info("Firebase app already initialized. Getting client.")
    db = firestore.client()

if db is None:
     logger.critical("Failed to obtain Firestore client. Exiting.")
     exit("Exiting: Firestore client not available.")
# --- End Firebase Configuration ---

# --- Constants ---
# LEGISINFO_BILLS_FEED_URL = "https://www.parl.ca/legisinfo/RSS/LegisInfoRSS.aspx?Language=E&Mode=1&ParliamentSession=" 
# The RSS feed might not be ideal for historical batch processing.
# Let's assume we can get a more comprehensive XML export or will use their search + XML for individual bills.
# For initial setup, let's use a direct XML feed if available for all bills in a session.
# If not, the strategy would need to be:
# 1. Get list of bills for the target period (e.g., via search or a broader feed).
# 2. For each bill, fetch its detailed XML.
# For this first version, let's simulate fetching a feed that contains multiple bills and their events.
# A common source: https://www.parl.ca/legisinfo/en/bills/xml (provides a list of current session bills)
# From there, you can get individual bill XMLs like: https://www.parl.ca/LegisInfo/BillXML.aspx?Language=E&billId=12000 (example)
# This script will focus on processing the XML structure of a *single bill's detailed activity*.
# A wrapper script would iterate over bill IDs for the target period.

FIRESTORE_EVIDENCE_COLLECTION = 'evidence_items'
TARGET_START_DATE = datetime(2022, 1, 1, tzinfo=timezone.utc)
TARGET_END_DATE = datetime(2022, 6, 30, 23, 59, 59, tzinfo=timezone.utc)
# --- End Constants ---

def parse_legisinfo_datetime(date_str):
    """Parses LEGISinfo date strings (e.g., '2022-01-20T10:00:00-05:00') into aware UTC datetimes."""
    if not date_str:
        return None
    try:
        # Python 3.7+ handles timezone offsets like -05:00 directly.
        # For older Pythons, you might need to parse manually or use dateutil.parser
        dt = datetime.fromisoformat(date_str)
        return dt.astimezone(timezone.utc) # Convert to UTC
    except ValueError:
        logger.warning(f"Could not parse LEGISinfo date string: {date_str}")
        return None

def fetch_bill_details_xml(bill_id_parl):
    """
    Fetches the detailed XML for a specific bill from LEGISinfo.
    bill_id_parl is the internal ID used by LEGISinfo (e.g., 12000 for a specific bill).
    This function is a placeholder/example; actual fetching of all bills for 
    the period would need a preceding step to get all relevant bill_id_parls.
    """
    # Example URL structure, adjust if LEGISinfo API changes
    url = f"https://www.parl.ca/LegisInfo/BillXML.aspx?Language=E&billId={bill_id_parl}"
    logger.info(f"Fetching XML for Bill ID (Parl): {bill_id_parl} from {url}")
    try:
        response = requests.get(url, timeout=30)
        response.raise_for_status()
        return response.text # Return XML content as string
    except requests.exceptions.RequestException as e:
        logger.error(f"Error fetching XML for Bill ID {bill_id_parl}: {e}")
        return None

def process_bill_xml(xml_content, bill_id_parl):
    """
    Parses the XML content of a single bill and extracts key events 
    within the target timeframe to store as evidence items.
    """
    if not xml_content:
        return []

    try:
        root = ET.fromstring(xml_content)
    except ET.ParseError as e:
        logger.error(f"Error parsing XML for Bill ID {bill_id_parl}: {e}")
        return []

    evidence_list = []
    
    bill_number_element = root.find('.//Bill/BillNumber')
    bill_number = bill_number_element.text if bill_number_element is not None else f"UnknownBillParlID-{bill_id_parl}"
    
    bill_title_element = root.find('.//Bill/LongTitle[@Language="English"]') # Or ShortTitle
    bill_title = bill_title_element.text if bill_title_element is not None else "N/A"

    sponsoring_minister_element = root.find('.//Bill/PrimeMinisterSponsor/Person/FullName') # Or other sponsor types
    sponsoring_minister = sponsoring_minister_element.text if sponsoring_minister_element is not None else None

    # Find all legislative events
    events = root.findall('.//Bill/Events/LegislativeEvents/Event')
    logger.info(f"Found {len(events)} legislative events for Bill {bill_number} (Parl ID: {bill_id_parl})")

    for event in events:
        event_date_str = event.find('Date')
        event_date_dt = parse_legisinfo_datetime(event_date_str.text) if event_date_str is not None else None

        if not event_date_dt or not (TARGET_START_DATE <= event_date_dt <= TARGET_END_DATE):
            # logger.debug(f"Skipping event outside target date range: {event_date_dt}")
            continue

        chamber_element = event.find('Chamber')
        chamber = chamber_element.text if chamber_element is not None else "N/A"
        
        meeting_number_element = event.find('MeetingNumber') # Useful for context
        meeting_number = meeting_number_element.text if meeting_number_element is not None else ""


        publication_element = event.find('Publications/Publication[@PublicationType="Public"]/Title[@Language="English"]')
        event_title_from_pub = publication_element.text if publication_element is not None else None

        # Try to get a more descriptive title for the event
        description_elements = event.findall('Description/Description[@Language="English"]/Para')
        event_description = " ".join([para.text for para in description_elements if para.text]).strip() \
                            if description_elements else "N/A"
        
        # Use Publication Title if available, otherwise craft one from description
        event_title = event_title_from_pub if event_title_from_pub else f"{event_description[:70]}..."
        if event_title == "N/A" and chamber != "N/A": # Fallback if description also bad
            event_title = f"Legislative Event in {chamber} for Bill {bill_number}"


        # Generate a unique ID for this specific evidence item (bill event)
        # Combining bill number, chamber, date, and a snippet of title for uniqueness
        # Or use event ID if LEGISinfo XML provides a stable one for each event
        event_id_xml = event.get('Id') # Check if 'Id' attribute exists on Event tag
        if event_id_xml:
            evidence_id_str = f"legisinfo_bill_{bill_number}_event_{event_id_xml}"
        else:
            # Fallback if no event ID in XML
            date_slug = event_date_dt.strftime('%Y%m%d')
            title_slug = re.sub(r'\W+', '', event_title.lower())[:20]
            evidence_id_str = f"legisinfo_bill_{bill_number}_{chamber.lower()}_{date_slug}_{title_slug}_{str(uuid.uuid4())[:8]}"
        
        evidence_item = {
            'evidence_id': evidence_id_str,
            'promise_ids': [], # To be populated by a separate linking script
            'evidence_source_type': "Bill Event (LEGISinfo)",
            'evidence_date': event_date_dt, # Firestore Timestamp (aware UTC datetime)
            'title_or_summary': f"Bill {bill_number}: {event_title}",
            'description_or_details': f"Chamber: {chamber}. Event: {event_description}. Meeting: {meeting_number}." ,
            'source_url': f"https://www.parl.ca/legisinfo/en/bill/{bill_id_parl}/{bill_number.lower().replace('-', '')}", # Generic link to bill page
            'source_document_raw_id': bill_number, # e.g., "C-12"
            'linked_departments': [sponsoring_minister] if sponsoring_minister else [], # Initial thought, department better
            'status_impact_on_promise': None, # To be determined by linking logic
            'ingested_at': firestore.SERVER_TIMESTAMP,
            'additional_metadata': {
                'bill_title_long': bill_title,
                'bill_parliament_id': bill_id_parl,
                'event_chamber': chamber,
                'event_meeting_number': meeting_number,
                'event_xml_id': event_id_xml # Store LEGISinfo's event ID if it exists
            }
        }
        evidence_list.append(evidence_item)
        logger.info(f"  Extracted event: '{event_title}' for Bill {bill_number} on {event_date_dt.strftime('%Y-%m-%d')}")

    return evidence_list


def save_evidence_to_firestore(evidence_items):
    """Saves a list of evidence items to Firestore, checking for existence."""
    if not evidence_items:
        return 0
    
    # Use a Firestore batch for potentially multiple items from one bill
    batch = db.batch()
    saved_count = 0
    skipped_count = 0

    for item in evidence_items:
        doc_ref = db.collection(FIRESTORE_EVIDENCE_COLLECTION).document(item['evidence_id'])
        
        # Optional: Check if document already exists to avoid overwriting (idempotency)
        # doc_snapshot = doc_ref.get()
        # if doc_snapshot.exists:
        #     logger.info(f"Evidence item {item['evidence_id']} already exists. Skipping.")
        #     skipped_count += 1
        #     continue
            
        batch.set(doc_ref, item) # Use set to create or overwrite
        saved_count += 1
        if saved_count % 400 == 0: # Commit batch periodically if very large
            logger.info(f"Committing intermediate batch of {saved_count} evidence items...")
            batch.commit()
            batch = db.batch() # Start a new batch

    if saved_count > 0 or skipped_count < len(evidence_items): # Commit any remaining items
        try:
            batch.commit()
            logger.info(f"Final batch committed. Total new evidence items saved: {saved_count}. Skipped existing: {skipped_count}.")
        except Exception as e:
            logger.error(f"Error committing final batch of evidence: {e}", exc_info=True)
            return 0 # Or partial count before error
            
    return saved_count

# --- Main Execution ---
if __name__ == "__main__":
    logger.info(f"--- Starting LEGISinfo Evidence Ingestion for Jan-Jun 2022 ---")

    # In a real scenario, you'd get a list of bill_id_parl values for the target period
    # This might involve parsing a broader feed or using LEGISinfo's search capabilities programmatically if possible.
    # For this example, we'll use a few known bill IDs from that period.
    # You would need to find these Parl IDs for bills active in early 2022.
    example_bill_parl_ids_for_early_2022 = [
        # Example: Find some actual bill IDs from that period on LEGISinfo
        # "13651224", # Example: Bill C-8 (Fall Economic Statement Implementation Act, 2021) - Check actual ID
        # "13651004", # Example: Bill C-2 (An Act to provide further support in response to COVID-19) - Check actual ID
        # Add more Parl IDs here.
        # If this list is empty, the script won't do much.
    ]

    if not example_bill_parl_ids_for_early_2022:
        logger.warning("No example Bill Parl IDs provided. Script will not fetch bill details.")
        logger.warning("To run this script effectively, populate 'example_bill_parl_ids_for_early_2022' list.")
        logger.warning("These Parl IDs are internal LEGISinfo IDs for bills, not just 'C-10'.")

    total_evidence_saved_overall = 0

    for bill_parl_id in example_bill_parl_ids_for_early_2022:
        xml_data = fetch_bill_details_xml(bill_parl_id)
        if xml_data:
            evidence_from_bill = process_bill_xml(xml_data, bill_parl_id)
            if evidence_from_bill:
                saved_this_bill = save_evidence_to_firestore(evidence_from_bill)
                total_evidence_saved_overall += saved_this_bill
            else:
                logger.info(f"No relevant evidence items extracted for Bill Parl ID {bill_parl_id} in the target period.")
        else:
            logger.warning(f"Could not fetch or process XML for Bill Parl ID {bill_parl_id}.")
        
        time.sleep(1) # Be polite when fetching multiple bill XMLs

    logger.info(f"--- LEGISinfo Evidence Ingestion Finished ---")
    logger.info(f"Total new evidence items saved across all processed bills: {total_evidence_saved_overall}")