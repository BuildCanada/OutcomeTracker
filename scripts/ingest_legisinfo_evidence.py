# scripts/ingest_legisinfo_evidence.py

import firebase_admin
from firebase_admin import firestore
import os
import requests
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
import time
import uuid
import logging
from dotenv import load_dotenv
import re
import json
import argparse

# --- Load Environment Variables ---
load_dotenv()
# --- End Load Environment Variables ---

# --- Logger Setup --- 
logging.basicConfig(level=logging.INFO, 
                    format='%(asctime)s - %(levelname)s - %(filename)s:%(lineno)d - %(message)s',
                    datefmt='%Y-%m-%d %H:%M:%S')
logger = logging.getLogger(__name__)
# --- End Logger Setup ---

# --- common_utils Placeholder (ensure this file exists and is correct) ---
try:
    from common_utils import standardize_department_name
except ImportError:
    logger.critical("common_utils.py not found or standardize_department_name cannot be imported.")
    # Define a basic placeholder if common_utils is missing, to allow script to run with warnings
    def standardize_department_name(minister_name):
        logger.warning(f"Using PLACEHOLDER standardize_department_name for '{minister_name}'")
        if minister_name: return f"Dept for {minister_name.split()[-1]}"
        return None
# --- End common_utils Placeholder ---


# --- LLM Configuration ---
gemini_model_bill_keywords = None
try:
    import google.generativeai as genai
    GEMINI_API_KEY = os.getenv("GEMINI_API_KEY") 
    if not GEMINI_API_KEY:
        logger.warning("Gemini API key (GEMINI_API_KEY) not set. Bill keyword extraction will be skipped.")
    else:
        genai.configure(api_key=GEMINI_API_KEY)
        llm_model_name_bill = os.getenv("GEMINI_MODEL_BILL_KEYWORDS", "gemini-2.5-flash-preview-04-17") # Use Flash as default
        logger.info(f"Using Gemini model for bill keywords: {llm_model_name_bill}")
        gemini_model_bill_keywords = genai.GenerativeModel(llm_model_name_bill)
except ImportError:
    logger.warning("google.generativeai library not found. Bill keyword extraction will be skipped.")
except Exception as e:
    logger.error(f"Error initializing Gemini model for bill keywords: {e}", exc_info=True)
# --- End LLM Configuration ---

# --- Firebase Configuration ---
db = None 
if not firebase_admin._apps:
    try:
        # GOOGLE_APPLICATION_CREDENTIALS should be set in your environment for cloud
        firebase_admin.initialize_app() 
        project_id = os.getenv('FIREBASE_PROJECT_ID', firebase_admin.get_app().project_id if firebase_admin.get_app() else '[Cloud Project ID Not Set]')
        logger.info(f"Python (LEGISinfo Ingest): Connected to CLOUD Firestore (Project: {project_id}).")
        db = firestore.client()
    except Exception as e:
        logger.critical(f"Firebase init failed for Cloud: {e}", exc_info=True)
        exit("Exiting: Cloud Firebase connection failed.")
else:
    db = firestore.client()

if db is None: exit("Exiting: Firestore client not available.")
# --- End Firebase Configuration ---

# --- Constants ---
FIRESTORE_EVIDENCE_COLLECTION = 'evidence_items'
FIRESTORE_BILLS_DATA_COLLECTION = 'bills_data' # New collection for bill details
# TARGET_START_DATE = datetime(2022, 1, 1, tzinfo=timezone.utc) # No longer strictly needed if processing all events from feed bills
# TARGET_END_DATE = datetime(2022, 6, 30, 23, 59, 59, tzinfo=timezone.utc) # No longer strictly needed
BILL_LIST_XML_FEED_URL = "https://www.parl.ca/legisinfo/en/bills/xml"
HEADERS = {'User-Agent': 'BuildCanadaPromiseTrackerBot/1.0'} # Be a good bot
# --- End Constants ---

def parse_legisinfo_datetime(date_str):
    if not date_str: return None
    try:
        return datetime.fromisoformat(date_str).astimezone(timezone.utc)
    except ValueError:
        logger.warning(f"Could not parse LEGISinfo date string: {date_str}")
        return None

def fetch_bill_details_xml(parliament_num, session_num, bill_code_str):
    # Corrected URL pattern
    url = f"https://www.parl.ca/legisinfo/en/bill/{parliament_num}-{session_num}/{bill_code_str.lower()}/xml"
    logger.info(f"Fetching XML for Bill {bill_code_str} (Parl: {parliament_num}, Session: {session_num}) from {url}")
    try:
        response = requests.get(url, headers=HEADERS, timeout=45)
        response.raise_for_status()
        return response.text
    except requests.exceptions.RequestException as e:
        logger.error(f"Error fetching XML for Bill {bill_code_str} (Parl: {parliament_num}, Session: {session_num}): {e}")
        return None

def fetch_all_bill_parl_ids_from_feed(feed_url):
    """Fetches all Bill Parl IDs, Parliament Number, Session Number, and Bill Number Code from the LEGISinfo XML feed."""
    logger.info(f"Fetching list of all Bill details from: {feed_url}")
    bills_data_from_feed = []
    try:
        response = requests.get(feed_url, headers=HEADERS, timeout=60)
        response.raise_for_status()
        xml_content = response.text
        root = ET.fromstring(xml_content)
        
        for bill_element in root.findall('./Bill'): 
            bill_id = bill_element.findtext('./BillId')
            parliament_num = bill_element.findtext('./ParliamentNumber')
            session_num = bill_element.findtext('./SessionNumber')
            bill_code = bill_element.findtext('./BillNumberFormatted') # e.g., C-2, S-10

            if bill_id and parliament_num and session_num and bill_code:
                bills_data_from_feed.append({
                    'id': bill_id.strip(),
                    'parliament_number': parliament_num.strip(),
                    'session_number': session_num.strip(),
                    'bill_code': bill_code.strip() 
                })
            else:
                logger.warning(f"Found a Bill element in feed with missing core data (ID, Parl, Sess, Code). BillId: '{bill_id}', BillCode: '{bill_code}'. Skipping.")

        if bills_data_from_feed:
            logger.info(f"Successfully fetched details for {len(bills_data_from_feed)} Bills from the feed.")
        else:
            logger.warning("No complete Bill data found in the feed. Check XML structure or feed content.")
        # No need for list(set()) here as we are taking multiple fields; assume feed provides unique bill instances.
        return bills_data_from_feed
    except requests.exceptions.RequestException as e:
        logger.error(f"Error fetching the bill list XML feed from {feed_url}: {e}")
        return []
    except ET.ParseError as e:
        logger.error(f"Error parsing the bill list XML feed: {e}")
        return []
    except Exception as e:
        logger.error(f"An unexpected error occurred while fetching bill data from feed: {e}", exc_info=True)
        return []

def call_gemini_for_bill_keywords(bill_title, bill_short_title="", bill_summary=""):
    if not gemini_model_bill_keywords:
        logger.warning("Gemini model for bill keywords not initialized. Skipping keyword extraction.")
        return []
    
    text_for_llm_parts = []
    if bill_title:
        text_for_llm_parts.append(f"Title: {bill_title}")
    if bill_short_title and bill_short_title != bill_title:
        text_for_llm_parts.append(f"Short Title: {bill_short_title}")
    if bill_summary:
        text_for_llm_parts.append(f"Summary: {bill_summary}")
    
    if not text_for_llm_parts:
        logger.warning(f"No text available (title, short title, or summary) for bill keyword extraction. Skipping.")
        return []
        
    text_for_llm = "\\n".join(text_for_llm_parts)

    # Truncate if too long
    MAX_LLM_INPUT_CHARS = 65536 
    if len(text_for_llm) > MAX_LLM_INPUT_CHARS:
        text_for_llm = text_for_llm[:MAX_LLM_INPUT_CHARS] + "..."
        logger.info(f"Truncated bill text for LLM keyword extraction (Bill: '{bill_title[:50]}...')")

    prompt = f"""From the following Canadian federal bill information:
{text_for_llm}
Extract a list of 5-10 key nouns, specific terms, and short phrases (2-3 words max per phrase) that describe the bill's main subject matter and purpose.
Output ONLY a valid JSON list of strings, with no other text before or after the JSON list. Example: ["term1", "short phrase 2", "concept3"]
"""
    logger.info(f"Attempting to extract keywords for bill: '{bill_title[:70]}...' using combined text.")
    
    try:
        # Add a small delay if making many LLM calls in sequence
        time.sleep(0.5) # To be a good API citizen if processing many bills
        response = gemini_model_bill_keywords.generate_content(prompt)
        
        cleaned_response_text = response.text.strip()
        # Handle potential markdown code block if LLM returns it
        if cleaned_response_text.startswith("```json"):
            cleaned_response_text = cleaned_response_text[7:]
        if cleaned_response_text.endswith("```"):
            cleaned_response_text = cleaned_response_text[:-3]
        
        keywords = json.loads(cleaned_response_text.strip())
        if isinstance(keywords, list) and all(isinstance(k, str) for k in keywords):
            logger.info(f"Extracted bill keywords for '{bill_title[:50]}...': {keywords}")
            return keywords
        else:
            logger.warning(f"Gemini bill keyword extraction for '{bill_title[:50]}...' did not return a valid list of strings. Response: {response.text}")
            return []
    except json.JSONDecodeError:
        logger.error(f"Error decoding JSON from Gemini bill keyword response for '{bill_title[:50]}...'. Response: {response.text if 'response' in locals() else 'N/A'}", exc_info=True)
        return []
    except Exception as e:
        logger.error(f"Error calling Gemini for bill keyword extraction for '{bill_title[:50]}...': {e}", exc_info=True)
        return []

def process_and_save_bill_data(xml_content, bill_parl_id_str, parliament_num_str, session_num_str, bill_number_code_from_feed_str):
    """
    Parses bill XML, saves/updates bill details to 'bills_data', 
    and extracts/saves relevant events to 'evidence_items'.
    Uses parliament_num_str, session_num_str, bill_number_code_from_feed_str for accurate URL construction.
    """
    if not xml_content: return

    try:
        root = ET.fromstring(xml_content)
    except ET.ParseError as e:
        logger.error(f"Error parsing XML for Bill Parl ID {bill_parl_id_str}: {e}")
        return

    bill_node = root.find('.//Bill') # Assuming the detailed XML is wrapped in <Bills><Bill>...</Bill></Bills>
    if bill_node is None:
        # If not wrapped, perhaps the xml_content *is* the <Bill> node already
        if root.tag == 'Bill':
            bill_node = root
        else: # Try finding Bill as a direct child if root is <Bills>
            bill_node = root.find('Bill') 
            if bill_node is None:
                 logger.error(f"Could not find <Bill> node in XML for Parl ID {bill_parl_id_str}")
                 return

    # --- 1. Extract and Save/Update Bill Details to `bills_data` ---
    bill_number_code_from_detail_xml = bill_node.findtext('NumberCode', default=bill_number_code_from_feed_str)
    parl_num_text = bill_node.findtext('ParliamentNumber', default="0")
    sess_num_text = bill_node.findtext('SessionNumber', default="0")
    
    long_title_en = bill_node.findtext('LongTitleEn', default="N/A") # Path updated assuming direct child
    short_title_en = bill_node.findtext('ShortTitleEn', default=None)
    bill_type = bill_node.findtext('BillDocumentTypeNameEn', default="N/A") # Path updated
    status_name = bill_node.findtext('StatusNameEn', default="N/A") # Path updated

    # New Introduction Date Logic
    intro_date_str = None
    originating_chamber_for_intro_date = bill_node.findtext('OriginatingChamberNameEn')
    if originating_chamber_for_intro_date == "House of Commons":
        intro_date_str = bill_node.findtext('PassedHouseFirstReadingDateTime')
    elif originating_chamber_for_intro_date == "Senate":
        intro_date_str = bill_node.findtext('PassedSenateFirstReadingDateTime')
    
    # Fallback if specific first reading dates are not found, try earliest event (less ideal)
    if not intro_date_str:
        first_event_date_house = bill_node.findtext('.//BillStages/HouseBillStages/SignificantEvents/EventDateTime')
        first_event_date_senate = bill_node.findtext('.//BillStages/SenateBillStages/SignificantEvents/EventDateTime')
        if first_event_date_house and first_event_date_senate:
            intro_date_str = min(first_event_date_house, first_event_date_senate)
        elif first_event_date_house:
            intro_date_str = first_event_date_house
        else:
            intro_date_str = first_event_date_senate
        if intro_date_str:
             logger.info(f"Used fallback introduction date for Bill {bill_number_code_from_detail_xml} from earliest significant event: {intro_date_str}")


    introduction_date = parse_legisinfo_datetime(intro_date_str)

    # Sponsor details - paths updated assuming direct children of Bill
    sponsor_name = bill_node.findtext('SponsorPersonName', default=None)
    sponsor_title = bill_node.findtext('SponsorAffiliationTitleEn', default=None)
    
    sponsoring_department = None 
    if sponsor_title:
        # Check if it's a Senator's title first, or if name indicates senator
        is_senator_by_title = "senator" in sponsor_title.lower()
        is_senator_by_name = sponsor_name and sponsor_name.lower().startswith("sen.")

        if is_senator_by_title or is_senator_by_name:
            sponsoring_department = None 
        else:
            # Attempt to standardize based on the title (e.g., "Minister of Health")
            sponsoring_department = standardize_department_name(sponsor_title)
            
            # Fallback: if title didn't yield a department, and we have a non-senator sponsor_name
            if not sponsoring_department and sponsor_name and not (is_senator_by_name or is_senator_by_title):
                logger.info(f"Attempting department standardization by sponsor_name ('{sponsor_name}') as fallback for bill {bill_number_code_from_detail_xml} because title '{sponsor_title}' did not yield a department.")
                sponsoring_department_from_name = standardize_department_name(sponsor_name)
                if sponsoring_department_from_name:
                    sponsoring_department = sponsoring_department_from_name
    
    elif sponsor_name: # Fallback if no sponsor_title, but have sponsor_name
        if not sponsor_name.lower().startswith("sen."):
            # This path is less likely to yield a good department name if standardize_department_name primarily expects titles.
            logger.info(f"Attempting department standardization by sponsor_name ('{sponsor_name}') for bill {bill_number_code_from_detail_xml} as no sponsor title was present.")
            sponsoring_department = standardize_department_name(sponsor_name)

    # Short Legislative Summary
    short_legislative_summary_html = bill_node.findtext('ShortLegislativeSummaryEn', default="")
    short_legislative_summary_cleaned = ""
    if short_legislative_summary_html:
        short_legislative_summary_cleaned = re.sub(r'<br\s*/?>', '\\n', short_legislative_summary_html) # Replace <br> with newline
        short_legislative_summary_cleaned = re.sub(r'<[^>]+>', '', short_legislative_summary_cleaned).strip() # Strip other tags

    text_for_keywords_summary = short_legislative_summary_cleaned if short_legislative_summary_cleaned else (short_title_en or "")
    bill_keywords = call_gemini_for_bill_keywords(long_title_en, short_title_en or "", text_for_keywords_summary)

    # Additional bill details from new XML structure
    latest_completed_major_stage_name_en = bill_node.findtext('LatestCompletedMajorStageNameEn')
    latest_completed_bill_stage_name_en = bill_node.findtext('LatestCompletedBillStageNameEn')
    latest_completed_bill_stage_datetime_str = bill_node.findtext('LatestCompletedBillStageDateTime')
    latest_completed_bill_stage_datetime = parse_legisinfo_datetime(latest_completed_bill_stage_datetime_str)
    
    is_gov_bill_text = bill_node.findtext('IsGovernmentBill')
    is_government_bill = is_gov_bill_text.lower() == 'true' if is_gov_bill_text else None

    originating_chamber_name_en = bill_node.findtext('OriginatingChamberNameEn')
    received_royal_assent_datetime_str = bill_node.findtext('ReceivedRoyalAssentDateTime')
    received_royal_assent_datetime = parse_legisinfo_datetime(received_royal_assent_datetime_str)
    
    statute_year_str = bill_node.findtext('StatuteYear')
    statute_year = int(statute_year_str) if statute_year_str and statute_year_str.isdigit() else None
    statute_chapter_str = bill_node.findtext('StatuteChapter')
    statute_chapter = int(statute_chapter_str) if statute_chapter_str and statute_chapter_str.isdigit() else None

    # Publications Metadata
    publications_metadata = []
    # Simple mapping for known publication types to URL slugs for documentviewer
    publication_type_to_slug = {
        "First Reading": "first-reading",
        "Second Reading": "second-reading", # Less common to link directly, but possible
        "Third Reading": "third-reading",
        "Royal Assent": "royal-assent",
        "As passed by the House of Commons": "third-reading", # Assuming this is a post-third reading version from HoC
        "As passed by the Senate": "third-reading", # Assuming this is a post-third reading version from Senate
        # Add more mappings as needed/discovered
    }

    for pub_node in bill_node.findall('Publications'):
        pub_id = pub_node.findtext('PublicationId')
        pub_type_name_en = pub_node.findtext('PublicationTypeNameEn')
        pub_type_id = pub_node.findtext('PublicationTypeId')
        
        doc_viewer_url = None
        slug = publication_type_to_slug.get(pub_type_name_en)
        if slug:
            doc_viewer_url = f"https://www.parl.ca/documentviewer/en/{parliament_num_str}-{session_num_str}/bill/{bill_number_code_from_feed_str.lower()}/{slug}"
            # Bill code in documentviewer URL often retains original casing, but feed may vary. Using lower for safety from XML feed, adjust if original case is strictly needed.
            # Example S-5 uses S-5 (original case). Let's try to use bill_number_code_from_feed_str directly.
            doc_viewer_url = f"https://www.parl.ca/documentviewer/en/{parliament_num_str}-{session_num_str}/bill/{bill_number_code_from_feed_str}/{slug}"


        if pub_id and pub_type_name_en:
            publications_metadata.append({
                'publication_id': pub_id,
                'type_name_en': pub_type_name_en,
                'type_id': pub_type_id,
                'document_viewer_url_en': doc_viewer_url
            })

    # Web References
    web_references = []
    for ref_node in bill_node.findall('WebReferences'): # Iterates over each <WebReferences> block
        title = ref_node.findtext('TitleEn')
        url = ref_node.findtext('UrlEn')
        type_name = ref_node.findtext('WebReferenceTypeNameEn')
        if title and url:
            web_references.append({
                'title_en': title,
                'url_en': url,
                'type_name_en': type_name
            })

    bill_data_doc = {
        'parl_id': bill_parl_id_str,
        'bill_number_code': bill_number_code_from_detail_xml,
        'parliament_number': int(parl_num_text) if parl_num_text.isdigit() else None,
        'session_number': int(sess_num_text) if sess_num_text.isdigit() else None,
        'long_title_en': long_title_en,
        'short_title_en': short_title_en,
        'short_legislative_summary_en_html': short_legislative_summary_html,
        'short_legislative_summary_en_cleaned': short_legislative_summary_cleaned,
        'bill_document_type_name': bill_type,
        'status_name': status_name,
        'introduction_date': introduction_date,
        'sponsor_name': sponsor_name,
        'sponsor_title': sponsor_title,
        'sponsoring_department': sponsoring_department,
        'extracted_keywords_concepts': bill_keywords,
        'legisinfo_detail_xml_url': f"https://www.parl.ca/legisinfo/en/bill/{parliament_num_str}-{session_num_str}/{bill_number_code_from_feed_str.lower()}/xml",
        'latest_completed_major_stage_name_en': latest_completed_major_stage_name_en,
        'latest_completed_bill_stage_name_en': latest_completed_bill_stage_name_en,
        'latest_completed_bill_stage_datetime': latest_completed_bill_stage_datetime,
        'is_government_bill': is_government_bill,
        'originating_chamber_name_en': originating_chamber_name_en,
        'received_royal_assent_datetime': received_royal_assent_datetime,
        'statute_year': statute_year,
        'statute_chapter': statute_chapter,
        'publications_metadata': publications_metadata,
        'web_references': web_references,
        'last_checked_legisinfo_at': firestore.SERVER_TIMESTAMP
    }
    
    try:
        bill_doc_ref = db.collection(FIRESTORE_BILLS_DATA_COLLECTION).document(bill_parl_id_str)
        bill_doc_ref.set(bill_data_doc, merge=True) 
        logger.info(f"Saved/Updated details for Bill {bill_number_code_from_detail_xml} (Parl ID: {bill_parl_id_str}) in '{FIRESTORE_BILLS_DATA_COLLECTION}'.")
    except Exception as e:
        logger.error(f"Error saving Bill {bill_number_code_from_detail_xml} details to Firestore: {e}", exc_info=True)
        # Continue to process events even if bill detail save fails, but log it.

    # --- 2. Extract and Save Bill Events to `evidence_items` ---
    # New event parsing logic based on BillStages and SignificantEvents
    
    all_significant_event_nodes_with_context = []
    bill_stages_node = bill_node.find('BillStages')

    if bill_stages_node is not None:
        # House Stages
        for stage_node in bill_stages_node.findall('HouseBillStages'):
            chamber_name = stage_node.findtext('ChamberNameEn', default="House of Commons")
            stage_name = stage_node.findtext('BillStageNameEn')
            sittings_nodes = stage_node.findall('Sittings') # Sittings is plural, may contain multiple Sitting
            significant_event_block = stage_node.find('SignificantEvents')
            if significant_event_block is not None:
                all_significant_event_nodes_with_context.append({
                    "node": significant_event_block, 
                    "chamber": chamber_name, 
                    "stage_name": stage_name,
                    "sittings": sittings_nodes
                })

        # Senate Stages
        for stage_node in bill_stages_node.findall('SenateBillStages'):
            chamber_name = stage_node.findtext('ChamberNameEn', default="Senate")
            stage_name = stage_node.findtext('BillStageNameEn')
            sittings_nodes = stage_node.findall('Sittings')
            significant_event_block = stage_node.find('SignificantEvents')
            if significant_event_block is not None:
                all_significant_event_nodes_with_context.append({
                    "node": significant_event_block, 
                    "chamber": chamber_name, 
                    "stage_name": stage_name,
                    "sittings": sittings_nodes
                })
        
        # Royal Assent Stage
        royal_assent_node = bill_stages_node.find('RoyalAssent')
        if royal_assent_node is not None:
            chamber_name = royal_assent_node.findtext('ChamberNameEn', default="Royal Assent") # Or "Senate" as per example
            stage_name = royal_assent_node.findtext('BillStageNameEn', default="Royal Assent")
            sittings_nodes = royal_assent_node.findall('Sittings')
            significant_event_block = royal_assent_node.find('SignificantEvents')
            if significant_event_block is not None:
                all_significant_event_nodes_with_context.append({
                    "node": significant_event_block, 
                    "chamber": chamber_name, 
                    "stage_name": stage_name,
                    "sittings": sittings_nodes
                })
    else:
        logger.warning(f"No <BillStages> node found for Bill {bill_number_code_from_detail_xml} (Parl ID: {bill_parl_id_str}). Cannot process events.")


    logger.info(f"Found {len(all_significant_event_nodes_with_context)} significant event blocks for Bill {bill_number_code_from_detail_xml} (Parl ID: {bill_parl_id_str})")
    
    evidence_batch = db.batch()
    evidence_saved_count = 0

    for event_data in all_significant_event_nodes_with_context:
        event_node = event_data["node"]
        chamber = event_data["chamber"]
        stage_name = event_data["stage_name"] # e.g. "First reading"
        sittings_nodes = event_data["sittings"]

        event_date_str = event_node.findtext('EventDateTime')
        event_date_dt = parse_legisinfo_datetime(event_date_str)

        if not event_date_dt:
            logger.warning(f"Skipping event for Bill {bill_number_code_from_detail_xml} (Stage: {stage_name}) due to unparsable date: {event_date_str}")
            continue

        event_name_en = event_node.findtext('EventNameEn', default=f"Event for {stage_name}")
        additional_info_en = event_node.findtext('AdditionalInformationEn', default="").strip()
        
        # Attempt to get MeetingNumber from the Sittings related to this stage
        meeting_number = ""
        if sittings_nodes:
            # A stage might have multiple sittings. Find the one matching the event date, or take the first.
            # For simplicity, check the first Sittings block's first Sitting's Number.
            # The <Sittings> tag in example is a container for one sitting usually.
            for s_node_container in sittings_nodes: # sittings_nodes is a list of <Sittings> tags
                 # Example shows <Sittings> then <Number>, not <Sittings><Sitting><Number>
                 # So s_node_container is the <Sittings> tag.
                 num_text = s_node_container.findtext('Number')
                 if num_text:
                     meeting_number = num_text
                     break # Take first one found

        event_title_display = f"Bill {bill_number_code_from_detail_xml}: {event_name_en}"
        
        description_parts = [f"Chamber: {chamber}", f"Stage: {stage_name}", f"Event: {event_name_en}"]
        if meeting_number:
            description_parts.append(f"Meeting: {meeting_number}")
        if additional_info_en:
            description_parts.append(f"Details: {additional_info_en}")
        
        event_description_full = ". ".join(description_parts) + "."

        event_type_id = event_node.findtext('EventTypeId') # Use EventTypeId as part of unique ID
        
        # Construct a more unique ID using bill number, date, event type, and chamber to avoid collisions
        date_slug = event_date_dt.strftime('%Y%m%d%H%M%S')
        chamber_slug = re.sub(r'\\W+', '', chamber.lower())[:15]
        event_type_slug = re.sub(r'\\\\W+', '', event_type_id.lower() if event_type_id else 'generic')[:15]

        # evidence_id_str updated for uniqueness with parliament and session
        evidence_id_str = f"legisinfo_bill_{parliament_num_str}_{session_num_str}_{bill_number_code_from_detail_xml}_event_{chamber_slug}_{date_slug}_{event_type_slug}_{str(uuid.uuid4())[:4]}"


        evidence_item = {
            'evidence_id': evidence_id_str,
            'bill_parl_id': bill_parl_id_str, 
            'promise_ids': [], 
            'evidence_source_type': "Bill Event (LEGISinfo)",
            'evidence_date': event_date_dt,
            'title_or_summary': event_title_display,
            'description_or_details': event_description_full,
            'source_url': f"https://www.parl.ca/legisinfo/en/bill/{parliament_num_str}-{session_num_str}/{bill_number_code_from_feed_str}", 
            'source_document_raw_id': bill_number_code_from_detail_xml, 
            'linked_departments': [sponsoring_department] if sponsoring_department else [],
            'status_impact_on_promise': None, 
            'ingested_at': firestore.SERVER_TIMESTAMP,
            'additional_metadata': {
                'bill_long_title': long_title_en, 
                'event_chamber': chamber,
                'event_stage_name': stage_name,
                'event_name_from_xml': event_name_en,
                'event_meeting_number': meeting_number,
                'event_xml_event_type_id': event_type_id # Changed from event_xml_id
            }
        }
        
        doc_ref = db.collection(FIRESTORE_EVIDENCE_COLLECTION).document(evidence_id_str)
        evidence_batch.set(doc_ref, evidence_item)
        evidence_saved_count += 1
        logger.info(f"  Prepared event for batch: '{event_name_en}' for Bill {bill_number_code_from_detail_xml} on {event_date_dt.strftime('%Y-%m-%d')}")

        if evidence_saved_count > 0 and evidence_saved_count % 400 == 0: # Commit if batch size is reached (even if 0, but condition protects)
            logger.info(f"Committing intermediate batch of {evidence_saved_count} evidence items for bill {bill_number_code_from_detail_xml}...")
            try:
                evidence_batch.commit()
                logger.info(f"Successfully committed intermediate batch of {evidence_saved_count} evidence items.")
            except Exception as e:
                logger.error(f"Error committing intermediate evidence batch for bill {bill_number_code_from_detail_xml}: {e}", exc_info=True)
            evidence_batch = db.batch() # Start a new batch
    
    if evidence_saved_count > 0 and (evidence_saved_count % 400 != 0 or evidence_saved_count < 400 and len(all_significant_event_nodes_with_context) == evidence_saved_count): # Commit any remaining items 
        try:
            logger.info(f"Committing final batch of {evidence_saved_count % 400 if evidence_saved_count > 400 else evidence_saved_count} evidence items for bill {bill_number_code_from_detail_xml}...")
            evidence_batch.commit()
            logger.info(f"Successfully committed final batch of evidence items.")
        except Exception as e:
            logger.error(f"Error committing final evidence batch for bill {bill_number_code_from_detail_xml}: {e}", exc_info=True)
    
    logger.info(f"Processed {evidence_saved_count} significant events for Bill {bill_number_code_from_detail_xml} (Parl ID: {bill_parl_id_str}).")

# --- Main Execution ---
if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Ingest LEGISinfo bill data and legislative events into Firestore.")
    parser.add_argument(
        "--limit", 
        type=int, 
        default=None, 
        help="Limit the number of bills to process. Processes all if not specified."
    )
    args = parser.parse_args()

    logger.info(f"--- Starting LEGISinfo Evidence Ingestion --- ") 

    all_bills_from_feed = fetch_all_bill_parl_ids_from_feed(BILL_LIST_XML_FEED_URL) # Renamed variable

    if not all_bills_from_feed:
        logger.critical("No Bill data was fetched from the feed. Exiting script.")
        exit()

    bills_to_process = all_bills_from_feed
    if args.limit is not None and args.limit > 0:
        bills_to_process = all_bills_from_feed[:args.limit]
        logger.info(f"Limiting processing to the first {len(bills_to_process)} of {len(all_bills_from_feed)} bills found in the feed (due to --limit={args.limit}).")
    else:
        logger.info(f"Will attempt to process all {len(bills_to_process)} bills found in the feed.")

    processed_bills_count = 0

    for bill_data_from_feed in bills_to_process: # Iterating over list of dicts
        bill_parl_id = bill_data_from_feed['id']
        parliament_num = bill_data_from_feed['parliament_number']
        session_num = bill_data_from_feed['session_number']
        bill_code = bill_data_from_feed['bill_code']

        logger.info(f"--- Checking Bill {bill_code} (Parl ID: {bill_parl_id}, Parl: {parliament_num}, Sess: {session_num}) ({processed_bills_count + 1} of {len(bills_to_process)}) ---")
        
        # Always fetch fresh XML to check for updates
        xml_data = fetch_bill_details_xml(parliament_num, session_num, bill_code)

        if not xml_data:
            logger.warning(f"Could not fetch XML for Bill {bill_code} (Parl ID {bill_parl_id}). Skipping.")
            time.sleep(1.2) # Keep sleep even on error to be polite
            continue

        try:
            # Parse key fields from fresh XML for comparison
            fresh_root = ET.fromstring(xml_data)
            fresh_bill_node = fresh_root.find('.//Bill')
            if fresh_bill_node is None:
                if fresh_root.tag == 'Bill': fresh_bill_node = fresh_root
                else: fresh_bill_node = fresh_root.find('Bill')
            
            if fresh_bill_node is None:
                logger.error(f"Could not find <Bill> node in freshly fetched XML for Bill {bill_code}. Skipping.")
                time.sleep(1.2)
                continue

            fresh_latest_stage_datetime_str = fresh_bill_node.findtext('LatestCompletedBillStageDateTime')
            fresh_latest_stage_datetime = parse_legisinfo_datetime(fresh_latest_stage_datetime_str)
            fresh_status_name = fresh_bill_node.findtext('StatusNameEn')

            bill_doc_ref = db.collection(FIRESTORE_BILLS_DATA_COLLECTION).document(bill_parl_id)
            existing_bill_doc = bill_doc_ref.get()

            if existing_bill_doc.exists:
                stored_bill_data = existing_bill_doc.to_dict()
                stored_latest_stage_datetime = stored_bill_data.get('latest_completed_bill_stage_datetime')
                stored_status_name = stored_bill_data.get('status_name')
                
                # Firestore timestamps may have nanosecond precision, python datetimes may not. Best effort comparison.
                # If both are None, they match. If one is None and other is not, they don't.
                # If both are datetime, compare them. Allow for minor diffs if not critical or convert to common format/granularity.
                # For simplicity here, direct comparison. Ensure parse_legisinfo_datetime normalizes timezone.
                
                # Convert Firestore timestamp to datetime object if necessary for comparison
                if isinstance(stored_latest_stage_datetime, firestore.SERVER_TIMESTAMP.__class__): # Should not happen if correctly stored
                     # this case is unlikely if it was stored as python datetime previously
                    pass # Cannot directly compare server_timestamp placeholder with actual datetime
                elif isinstance(stored_latest_stage_datetime, datetime):
                    # Ensure both are offset-aware for comparison if one is from Firestore (UTC) and other parsed.
                    # parse_legisinfo_datetime should return tz-aware (UTC).
                    pass # Already datetime

                # Key comparison logic
                if (fresh_latest_stage_datetime == stored_latest_stage_datetime and 
                    fresh_status_name == stored_status_name):
                    logger.info(f"Bill {bill_code} (Parl ID {bill_parl_id}) appears current. Updating check time and skipping detailed processing.")
                    bill_doc_ref.update({'last_checked_legisinfo_at': firestore.SERVER_TIMESTAMP})
                    processed_bills_count +=1 # Count as processed for the limit logic
                    time.sleep(0.5) # Shorter sleep if just updating timestamp
                    continue # Skip to the next bill
                else:
                    logger.info(f"Bill {bill_code} (Parl ID {bill_parl_id}) has changed or is new. Proceeding with full processing.")
            else:
                logger.info(f"Bill {bill_code} (Parl ID {bill_parl_id}) is new. Proceeding with full processing.")

        except ET.ParseError as e:
            logger.error(f"Error parsing freshly fetched XML for currency check of Bill {bill_code}: {e}. Proceeding with full processing just in case.")
        except Exception as e:
            logger.error(f"Unexpected error during currency check for Bill {bill_code}: {e}. Proceeding with full processing.", exc_info=True)
            # Fall through to full processing if currency check has an issue

        # If we reach here, bill is new, changed, or currency check failed -> process fully
        logger.info(f"--- Processing Bill {bill_code} (Parl ID: {bill_parl_id}, Parl: {parliament_num}, Sess: {session_num}) ({processed_bills_count + 1} of {len(bills_to_process)}) ---")
        process_and_save_bill_data(xml_data, bill_parl_id, parliament_num, session_num, bill_code)
        processed_bills_count +=1
        
        time.sleep(1.2)

    logger.info(f"--- LEGISinfo Evidence Ingestion Finished ---")
    logger.info(f"Processed details for {processed_bills_count} bills.")
    # Note: The total count of *evidence items* saved is now logged within the processing loop.