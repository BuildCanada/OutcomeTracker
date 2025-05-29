"""
Processes raw LEGISinfo bill JSON data into evidence_items_test using Gemini LLM.
Queries raw_legisinfo_bill_details with processing_status == 'pending_processing',
extracts bill information and legislative events, sends to Gemini for analysis,
and creates evidence items for each legislative event.

CLI arguments:
--dry_run: If True, do not write to Firestore but still call Gemini and log outputs. Default: False
--log_level: Set the logging level. Default: INFO
--JSON: If True, output processed evidence docs to a JSON file instead of Firestore. Default: False
--json_output_dir: The directory to write the JSON file to. Default: ./JSON_outputs
--force_reprocessing: If True, reprocess all items up to the limit, ignoring current status. Default: False
--start_date: The start date to process from. Format: YYYY-MM-DD. Default: None
--end_date: The end date to process to. Format: YYYY-MM-DD. Default: None
--limit: Limit the number of bills to process. Default: None

Stage 2 of LEGISinfo two-stage ingestion. Processes data from ingest_legisinfo_raw_bills.py.
"""

import os
import logging
import json
import asyncio
import hashlib
import re
from datetime import datetime, timezone, date
from dotenv import load_dotenv
import firebase_admin
from firebase_admin import credentials, firestore
import argparse
import time
from google import genai
import traceback

# Import common utilities
import sys
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))
from common_utils import standardize_department_name

# --- Configuration ---
load_dotenv()

# --- Logger Setup ---
logging.basicConfig(level=logging.INFO,
                    format='%(asctime)s - %(levelname)s - %(filename)s:%(lineno)d - %(message)s',
                    datefmt='%Y-%m-%d %H:%M:%S')
logger = logging.getLogger("process_raw_legisinfo_to_evidence")
# --- End Logger Setup ---

# --- Constants ---
RAW_LEGISINFO_BILLS_COLLECTION = "raw_legisinfo_bill_details"
EVIDENCE_ITEMS_COLLECTION = "evidence_items"
DEFAULT_JSON_OUTPUT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'JSON_outputs', 'bill_processing')
PROMPT_FILE_PATH = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', 'prompts', 'prompt_bill_evidence.md'))
# --- End Constants ---

# --- Firebase Configuration ---
db = None
if not firebase_admin._apps:
    try:
        firebase_admin.initialize_app()
        db = firestore.client()
        project_id = os.getenv('FIREBASE_PROJECT_ID', 'Default')
        logger.info(f"Connected to CLOUD Firestore (Project: {project_id}) using default credentials.")
    except Exception as e:
        logger.critical(f"Firebase init failed: {e}", exc_info=True)
        exit("Exiting: Firestore client not available.")
else:
    db = firestore.client()

if db is None:
    logger.critical("CRITICAL: Failed to obtain Firestore client. Exiting.")
    exit("Exiting: Firestore client not available.")
# --- End Firebase Configuration ---

# --- Gemini Configuration ---
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
if not GEMINI_API_KEY:
    logger.critical("GEMINI_API_KEY not found in environment variables or .env file.")
    exit("Exiting: Missing GEMINI_API_KEY.")

if "GOOGLE_API_KEY" not in os.environ and GEMINI_API_KEY:
    os.environ["GOOGLE_API_KEY"] = GEMINI_API_KEY

LLM_MODEL_NAME = os.getenv("GEMINI_MODEL_BILL_PROCESSING", "models/gemini-2.5-flash-preview-05-20")
logger.info(f"Using Gemini model: {LLM_MODEL_NAME}")

# Generation configuration
GENERATION_CONFIG_DICT = {
    "response_mime_type": "application/json",
    "temperature": 0.1,
    "max_output_tokens": 65536
}

client = None
try:
    client = genai.Client()
    logger.info(f"Successfully initialized Gemini Client with model {LLM_MODEL_NAME}.")
except Exception as e:
    logger.critical(f"Failed to initialize Gemini client: {e}", exc_info=True)
    exit("Exiting: Gemini client initialization failed.")
# --- End Gemini Configuration ---

def load_gemini_prompt_template(prompt_file: str) -> str:
    """Load the Gemini prompt template from file"""
    try:
        with open(prompt_file, 'r') as f:
            return f.read()
    except Exception as e:
        logger.critical(f"Could not load Gemini prompt template from {prompt_file}: {e}")
        raise

def build_bill_gemini_prompt(bill_data, prompt_template: str) -> str:
    """Build the Gemini prompt for bill analysis"""
    return prompt_template.format(
        bill_long_title_en=bill_data.get('long_title_en', ''),
        bill_short_title_en=bill_data.get('short_title_en', ''),
        short_legislative_summary_en_cleaned=bill_data.get('short_legislative_summary_en_cleaned', ''),
        sponsor_affiliation_title_en=bill_data.get('sponsor_affiliation_title_en', ''),
        sponsor_person_name=bill_data.get('sponsor_person_name', ''),
        parliament_session_id=bill_data.get('parliament_session_id', '')
    )

def clean_json_from_markdown(text_blob: str) -> str:
    """Clean JSON from markdown code blocks"""
    regex_pattern = r"```(?:json)?\s*([\s\S]+?)\s*```"
    match = re.search(regex_pattern, text_blob)
    if match:
        return match.group(1).strip()
    return text_blob.strip()

async def call_gemini_llm(prompt_text: str):
    """Call Gemini LLM for bill analysis"""
    if not client:
        logger.critical("Gemini model client not initialized. Cannot call LLM.")
        return None, LLM_MODEL_NAME

    try:
        logger.debug(f"Calling Gemini with prompt (first 200 chars): {prompt_text[:200]}...")
        
        response = await client.aio.models.generate_content(
            model=LLM_MODEL_NAME,
            contents=[prompt_text]
        )
        
        if response and response.text:
            try:
                raw_response_text = response.text
                json_str = clean_json_from_markdown(raw_response_text)
                result_dict = json.loads(json_str)
                logger.debug(f"Gemini response parsed successfully")
                return result_dict, LLM_MODEL_NAME
            except json.JSONDecodeError as e:
                logger.error(f"Error parsing Gemini response as JSON: {e}")
                logger.error(f"Raw response: {raw_response_text[:500] if 'raw_response_text' in locals() else ''}")
                return None, LLM_MODEL_NAME
        else:
            logger.error("Empty or no response from Gemini")
            return None, LLM_MODEL_NAME
            
    except Exception as e:
        logger.error(f"Error calling Gemini LLM: {e}", exc_info=True)
        return None, LLM_MODEL_NAME

def parse_legisinfo_datetime(date_str):
    """Parse datetime string from LEGISinfo JSON"""
    if not date_str:
        return None
    try:
        return datetime.fromisoformat(date_str).astimezone(timezone.utc)
    except ValueError:
        logger.warning(f"Could not parse LEGISinfo date string: {date_str}")
        return None

def is_terminal_bill_status(status_name):
    """Check if a bill status represents a terminal (final) state"""
    if not status_name:
        return False
    
    terminal_statuses = [
        'defeated',
        'not proceeded with',
        'royal assent',
        'bill not proceeded with',
        'defeated at second reading',
        'defeated at third reading',
        'withdrawn',
        'bill withdrawn'
    ]
    
    status_lower = status_name.lower()
    return any(terminal in status_lower for terminal in terminal_statuses)

def extract_bill_final_status_event(raw_json_content):
    """Extract the final status event for terminal bills"""
    try:
        bill_json = json.loads(raw_json_content)
        
        # Handle case where API returns an array containing the bill object
        if isinstance(bill_json, list) and len(bill_json) > 0:
            bill_json = bill_json[0]
        elif isinstance(bill_json, list):
            logger.error("Empty array in raw JSON content for status extraction")
            return None
        
        status_name = bill_json.get('StatusNameEn', '')
        
        # Only create status event for terminal statuses
        if not is_terminal_bill_status(status_name):
            return None
        
        # Try to get the latest bill event details
        latest_completed_stage_datetime_str = bill_json.get('LatestCompletedBillStageDateTime')
        latest_completed_stage_name = bill_json.get('LatestCompletedBillStageNameEn', '')
        latest_completed_major_stage_name = bill_json.get('LatestCompletedMajorStageNameEn', '')
        
        # If no specific latest stage datetime, try to extract from LatestBillEvent if available
        event_date_str = latest_completed_stage_datetime_str
        if not event_date_str:
            # Look for latest bill event section
            latest_bill_event = bill_json.get('LatestBillEvent', {})
            if isinstance(latest_bill_event, dict):
                event_date_str = latest_bill_event.get('EventDateTime')
        
        # Parse the event date
        if event_date_str:
            event_date = parse_legisinfo_datetime(event_date_str)
            if event_date:
                return {
                    'event_date': event_date,
                    'status_name': status_name,
                    'stage_name': latest_completed_stage_name or latest_completed_major_stage_name or 'Final Status',
                    'is_terminal': True
                }
        
        logger.warning(f"Could not extract event date for terminal status: {status_name}")
        return None
        
    except Exception as e:
        logger.error(f"Error extracting bill final status: {e}", exc_info=True)
        return None

def clean_html_text(html_text):
    """Clean HTML tags from text"""
    if not html_text:
        return ""
    # Replace <br> with newline
    cleaned = re.sub(r'<br\s*/?>', '\n', html_text)
    # Strip other HTML tags
    cleaned = re.sub(r'<[^>]+>', '', cleaned).strip()
    return cleaned

def extract_bill_data_from_json(raw_json_content):
    """Extract bill information from the raw JSON content"""
    try:
        bill_json = json.loads(raw_json_content)
        
        # Handle case where API returns an array containing the bill object
        if isinstance(bill_json, list) and len(bill_json) > 0:
            bill_json = bill_json[0]
        elif isinstance(bill_json, list):
            logger.error("Empty array in raw JSON content")
            return None
        
        # Extract basic bill information
        long_title_en = bill_json.get('LongTitleEn', '')
        short_title_en = bill_json.get('ShortTitleEn', '')
        
        # Clean legislative summary
        summary_html = bill_json.get('ShortLegislativeSummaryEn', '')
        summary_cleaned = clean_html_text(summary_html)
        
        # Extract sponsor information
        sponsor_name = bill_json.get('SponsorPersonName', '')
        sponsor_title = bill_json.get('SponsorAffiliationTitleEn', '')
        
        # Extract other key fields
        introduction_date_str = bill_json.get('IntroductionDate', '')
        introduction_date = parse_legisinfo_datetime(introduction_date_str)
        
        status_name = bill_json.get('StatusNameEn', '')
        is_government_bill = bill_json.get('IsGovernmentBill', False)
        
        return {
            'long_title_en': long_title_en,
            'short_title_en': short_title_en,
            'short_legislative_summary_en_cleaned': summary_cleaned,
            'sponsor_person_name': sponsor_name,
            'sponsor_affiliation_title_en': sponsor_title,
            'introduction_date': introduction_date,
            'status_name': status_name,
            'is_government_bill': is_government_bill
        }
        
    except Exception as e:
        logger.error(f"Error extracting bill data from JSON: {e}", exc_info=True)
        return None

def extract_legislative_events_from_json(raw_json_content):
    """Extract legislative events from the raw JSON content"""
    try:
        bill_json = json.loads(raw_json_content)
        
        # Handle case where API returns an array containing the bill object
        if isinstance(bill_json, list) and len(bill_json) > 0:
            bill_json = bill_json[0]
        elif isinstance(bill_json, list):
            logger.error("Empty array in raw JSON content for events extraction")
            return []
        
        events = []
        
        # Look for BillStages structure
        bill_stages = bill_json.get('BillStages', {})
        
        # Process House stages
        house_stages = bill_stages.get('HouseBillStages', [])
        if not isinstance(house_stages, list):
            house_stages = [house_stages] if house_stages else []
            
        for stage in house_stages:
            events.extend(extract_events_from_stage(stage, 'House of Commons'))
        
        # Process Senate stages
        senate_stages = bill_stages.get('SenateBillStages', [])
        if not isinstance(senate_stages, list):
            senate_stages = [senate_stages] if senate_stages else []
            
        for stage in senate_stages:
            events.extend(extract_events_from_stage(stage, 'Senate'))
        
        # Process Royal Assent
        royal_assent = bill_stages.get('RoyalAssent')
        if royal_assent:
            events.extend(extract_events_from_stage(royal_assent, 'Royal Assent'))
        
        return events
        
    except Exception as e:
        logger.error(f"Error extracting events from JSON: {e}", exc_info=True)
        return []

def extract_events_from_stage(stage_data, chamber_name):
    """Extract events from a single stage"""
    events = []
    
    if not stage_data:
        return events
    
    # Handle case where stage_data might be a list (e.g., RoyalAssent can be a list)
    if isinstance(stage_data, list):
        # If it's a list, process each item in the list
        for stage_item in stage_data:
            events.extend(extract_events_from_stage(stage_item, chamber_name))
        return events
    
    stage_name = stage_data.get('BillStageNameEn', chamber_name)
    
    # Look for SignificantEvents - this is an array, not an object
    significant_events_list = stage_data.get('SignificantEvents', [])
    
    # Handle case where it might be a single object instead of a list
    if isinstance(significant_events_list, dict):
        significant_events_list = [significant_events_list]
    
    for significant_event in significant_events_list:
        if not significant_event:
            continue
            
        event_date_str = significant_event.get('EventDateTime')
        event_name = significant_event.get('EventNameEn', f'Event in {stage_name}')
        additional_info = significant_event.get('AdditionalInformationEn', '')
        event_type_id = significant_event.get('EventTypeId', '')
        
        if event_date_str:
            event_date = parse_legisinfo_datetime(event_date_str)
            if event_date:
                events.append({
                    'event_date': event_date,
                    'chamber': chamber_name,
                    'stage_name': stage_name,
                    'event_name': event_name,
                    'additional_info': additional_info,
                    'event_type_id': event_type_id
                })
    
    return events

async def process_pending_raw_bills(db_client, dry_run=False, output_to_json=False, json_output_dir=None, 
                                   force_reprocessing=False, start_date_filter_dt=None, end_date_filter_dt=None, limit=None):
    """Main processing function"""
    prompt_template = load_gemini_prompt_template(PROMPT_FILE_PATH)
    logger.info(f"Starting raw bill processing. Dry run: {dry_run}, JSON: {output_to_json}, Force: {force_reprocessing}, Limit: {limit or 'All'}")
    
    if start_date_filter_dt:
        logger.info(f"Date filter: From {start_date_filter_dt.strftime('%Y-%m-%d')}")
    if end_date_filter_dt:
        logger.info(f"Date filter: To {end_date_filter_dt.strftime('%Y-%m-%d')}")
    
    processed_count = 0
    evidence_created_count = 0
    error_count = 0
    all_outputs_for_json = []
    
    if output_to_json:
        os.makedirs(json_output_dir, exist_ok=True)
    
    try:
        # Query for raw bill documents
        query = db_client.collection(RAW_LEGISINFO_BILLS_COLLECTION)
        
        if not force_reprocessing:
            query = query.where(filter=firestore.FieldFilter("processing_status", "==", "pending_processing"))
        
        if limit:
            query = query.limit(limit)
            logger.info(f"Applying limit of {limit} records to the query.")
        
        pending_docs = list(query.stream())
        
        if not pending_docs:
            logger.info("No pending raw bill documents found matching criteria.")
            return
            
        logger.info(f"Found {len(pending_docs)} raw bill documents to process.")
        
        for raw_doc_snapshot in pending_docs:
            raw_doc_data = raw_doc_snapshot.to_dict()
            doc_id = raw_doc_snapshot.id
            
            logger.info(f"Processing raw bill document: {doc_id} - {raw_doc_data.get('bill_number_code_feed', 'Unknown')}")
            processed_count += 1
            
            try:
                # Extract bill data from raw JSON
                bill_data = extract_bill_data_from_json(raw_doc_data.get('raw_json_content', ''))
                if not bill_data:
                    logger.error(f"Failed to extract bill data from {doc_id}")
                    error_count += 1
                    continue
                
                # Add metadata from the raw document
                bill_data['parliament_session_id'] = raw_doc_data.get('parliament_session_id', '')
                
                # Call Gemini for bill analysis
                llm_prompt = build_bill_gemini_prompt(bill_data, prompt_template)
                gemini_result_dict, model_name = await call_gemini_llm(llm_prompt)
                
                if not gemini_result_dict:
                    logger.error(f"LLM analysis failed for {doc_id}")
                    if not dry_run:
                        await asyncio.to_thread(db_client.collection(RAW_LEGISINFO_BILLS_COLLECTION).document(doc_id).update, {
                            "processing_status": "error_llm_processing",
                            "last_attempted_processing_at": firestore.SERVER_TIMESTAMP,
                            "llm_model_name_last_attempt": model_name
                        })
                    error_count += 1
                    continue
                
                # Extract LLM results
                timeline_summary_llm = gemini_result_dict.get("timeline_summary_llm", "")
                one_sentence_description_llm = gemini_result_dict.get("one_sentence_description_llm", "")
                key_concepts_llm = gemini_result_dict.get("key_concepts_llm", [])
                sponsoring_department_llm = gemini_result_dict.get("sponsoring_department_standardized_llm", "")
                
                # Standardize department using script logic
                sponsoring_department_script = None
                if bill_data.get('sponsor_affiliation_title_en'):
                    sponsoring_department_script = standardize_department_name(bill_data['sponsor_affiliation_title_en'])
                elif bill_data.get('sponsor_person_name'):
                    sponsoring_department_script = standardize_department_name(bill_data['sponsor_person_name'])
                
                # Use LLM result if script didn't find anything
                final_sponsoring_department = sponsoring_department_script or sponsoring_department_llm
                
                # Construct URLs
                parliament_session_id = raw_doc_data.get('parliament_session_id', '')
                bill_code = raw_doc_data.get('bill_number_code_feed', '')
                
                # Parse parliament and session from consolidated ID (e.g., "44-1" -> "44" and "1")
                if '-' in parliament_session_id:
                    parliament_num, session_num = parliament_session_id.split('-', 1)
                else:
                    parliament_num = parliament_session_id
                    session_num = '1'  # Default fallback
                
                details_url = f"https://www.parl.ca/legisinfo/en/bill/{parliament_session_id}/{bill_code.lower()}?view=details"
                about_url = f"https://www.parl.ca/legisinfo/en/bill/{parliament_session_id}/{bill_code.lower()}?view=about"
                
                # Extract legislative events
                events = extract_legislative_events_from_json(raw_doc_data.get('raw_json_content', ''))
                
                # Extract terminal status event if applicable
                terminal_status_event = extract_bill_final_status_event(raw_doc_data.get('raw_json_content', ''))
                if terminal_status_event:
                    # Add terminal status as a special event
                    terminal_event = {
                        'event_date': terminal_status_event['event_date'],
                        'chamber': 'Parliament',  # General chamber for final status
                        'stage_name': terminal_status_event['stage_name'],
                        'event_name': f"Bill {terminal_status_event['status_name']}",
                        'additional_info': f"Final bill status: {terminal_status_event['status_name']}",
                        'event_type_id': 'terminal_status',
                        'is_terminal': True
                    }
                    events.append(terminal_event)
                    logger.info(f"Added terminal status event: {terminal_status_event['status_name']}")
                
                # Apply date filtering to events if specified
                filtered_events = []
                for event in events:
                    event_date = event['event_date']
                    if start_date_filter_dt and event_date.date() < start_date_filter_dt:
                        continue
                    if end_date_filter_dt and event_date.date() > end_date_filter_dt:
                        continue
                    filtered_events.append(event)
                
                logger.info(f"Creating evidence items for {len(filtered_events)} events (filtered from {len(events)} total)")
                
                # Create evidence items for each event
                batch = db_client.batch() if not dry_run else None
                batch_count = 0
                
                for event in filtered_events:
                    # Generate unique evidence ID (date only, no timestamp)
                    event_date_str = event['event_date'].strftime('%Y%m%d')
                    chamber_slug = re.sub(r'\W+', '', event['chamber'].lower())[:15]
                    event_type_slug = re.sub(r'\W+', '', str(event.get('event_type_id', 'event')).lower())[:15]
                    
                    hash_input = f"{doc_id}_{event['event_date'].strftime('%Y%m%d%H%M%S')}_{chamber_slug}_{event_type_slug}"
                    short_hash = hashlib.sha256(hash_input.encode('utf-8')).hexdigest()[:8]
                    evidence_id = f"{event_date_str}_{parliament_num}_{bill_code}_event_{chamber_slug}_{short_hash}"
                    
                    # Determine source type based on event type
                    is_terminal = event.get('is_terminal', False)
                    source_type = "Bill Final Status (LEGISinfo)" if is_terminal else "Bill Event (LEGISinfo)"
                    
                    # Create evidence item
                    evidence_item_data = {
                        "evidence_id": evidence_id,
                        "bill_parl_id": doc_id,
                        "parliament_session_id": parliament_session_id,
                        "promise_ids": [],
                        "evidence_source_type": source_type,
                        "evidence_date": event['event_date'],
                        "title_or_summary": f"Bill {bill_code}: {event['event_name']} in {event['chamber']}",
                        "description_or_details": f"Chamber: {event['chamber']}. Stage: {event['stage_name']}. Event: {event['event_name']}. {event.get('additional_info', '')}".strip(),
                        "source_url": f"https://www.parl.ca/legisinfo/en/bill/{parliament_session_id}/{bill_code}",
                        "source_document_raw_id": bill_code,
                        "linked_departments": [final_sponsoring_department] if final_sponsoring_department else [],
                        "bill_extracted_keywords_concepts": key_concepts_llm,
                        "bill_timeline_summary_llm": timeline_summary_llm,
                        "bill_one_sentence_description_llm": one_sentence_description_llm,
                        "additional_information": {
                            "details_url": details_url,
                            "about_url": about_url,
                            "event_specific_details": {
                                "chamber": event['chamber'],
                                "stage_name": event['stage_name'],
                                "event_type_id": event.get('event_type_id', ''),
                                "additional_info": event.get('additional_info', ''),
                                "is_terminal_status": is_terminal
                            }
                        },
                        "promise_linking_status": "pending",
                        "ingested_at": datetime.now(timezone.utc)
                    }
                    
                    if output_to_json:
                        # Convert datetime objects for JSON serialization
                        json_compatible_doc = {k: (v.isoformat() if isinstance(v, datetime) else v) for k, v in evidence_item_data.items()}
                        all_outputs_for_json.append(json_compatible_doc)
                        logger.info(f"Prepared for JSON: evidence {evidence_id}")
                    elif not dry_run:
                        batch.set(db_client.collection(EVIDENCE_ITEMS_COLLECTION).document(evidence_id), evidence_item_data)
                        batch_count += 1
                        
                        # Commit batch if it gets large
                        if batch_count >= 400:
                            await asyncio.to_thread(batch.commit)
                            logger.info(f"Committed batch of {batch_count} evidence items")
                            batch = db_client.batch()
                            batch_count = 0
                    else:
                        logger.info(f"[DRY RUN] Would create evidence item {evidence_id}")
                    
                    evidence_created_count += 1
                
                # Commit any remaining items in batch
                if not dry_run and batch_count > 0:
                    await asyncio.to_thread(batch.commit)
                    logger.info(f"Committed final batch of {batch_count} evidence items")
                
                # Update raw document status
                if not dry_run:
                    await asyncio.to_thread(db_client.collection(RAW_LEGISINFO_BILLS_COLLECTION).document(doc_id).update, {
                        "processing_status": "processed",
                        "last_attempted_processing_at": firestore.SERVER_TIMESTAMP,
                        "llm_model_name_last_attempt": model_name
                    })
                    logger.info(f"Updated status for raw bill document {doc_id}")
                else:
                    logger.info(f"[DRY RUN] Would update status for {doc_id}")
                
            except Exception as e:
                logger.error(f"Error processing raw bill document {doc_id}: {e}", exc_info=True)
                error_count += 1
                if not dry_run:
                    try:
                        await asyncio.to_thread(db_client.collection(RAW_LEGISINFO_BILLS_COLLECTION).document(doc_id).update, {
                            "processing_status": "error_processing_script",
                            "processing_error_message": str(e),
                            "last_attempted_processing_at": firestore.SERVER_TIMESTAMP
                        })
                    except Exception as update_err:
                        logger.error(f"Failed to mark document {doc_id} as error: {update_err}")
    
    except Exception as e:
        logger.error(f"Major error in process_pending_raw_bills: {e}", exc_info=True)
    
    # Write JSON output if specified
    if output_to_json and all_outputs_for_json:
        try:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = os.path.join(json_output_dir, f"processed_bill_evidence_{timestamp}.json")
            with open(filename, 'w', encoding='utf-8') as f:
                json.dump(all_outputs_for_json, f, indent=4, ensure_ascii=False, default=str)
            logger.info(f"Wrote {len(all_outputs_for_json)} processed items to JSON: {filename}")
        except Exception as e:
            logger.error(f"Error writing to JSON: {e}", exc_info=True)
    
    logger.info(f"Processing finished. Attempted: {processed_count}, Evidence Created: {evidence_created_count}, Errors: {error_count}")

async def main():
    parser = argparse.ArgumentParser(description="Process raw LEGISinfo bill data into evidence items using LLM analysis.")
    parser.add_argument("--dry_run", action="store_true", help="Dry run, no Firestore writes.")
    parser.add_argument("--log_level", type=str, default="INFO", choices=['DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL'])
    parser.add_argument("--JSON", dest="output_to_json", action="store_true", help="Output to JSON instead of Firestore.")
    parser.add_argument("--json_output_dir", type=str, default=DEFAULT_JSON_OUTPUT_DIR)
    parser.add_argument("--force_reprocessing", action="store_true", help="Reprocess all bills, ignoring current status.")
    parser.add_argument("--start_date", type=str, help="Start date for event filtering (YYYY-MM-DD).")
    parser.add_argument("--end_date", type=str, help="End date for event filtering (YYYY-MM-DD).")
    parser.add_argument("--limit", type=int, help="Limit the number of bills to process.")
    
    args = parser.parse_args()
    logger.setLevel(getattr(logging, args.log_level.upper()))
    
    # Parse date filters
    start_date_dt = None
    end_date_dt = None
    
    if args.start_date:
        try:
            start_date_dt = datetime.strptime(args.start_date, "%Y-%m-%d").date()
        except ValueError:
            logger.error(f"Invalid start_date: {args.start_date}. Use YYYY-MM-DD.")
            return
    
    if args.end_date:
        try:
            end_date_dt = datetime.strptime(args.end_date, "%Y-%m-%d").date()
        except ValueError:
            logger.error(f"Invalid end_date: {args.end_date}. Use YYYY-MM-DD.")
            return
    
    if start_date_dt and end_date_dt and start_date_dt > end_date_dt:
        logger.error(f"Start date {start_date_dt} after end date {end_date_dt}.")
        return
    
    if args.dry_run:
        logger.info("*** DRY RUN MODE ENABLED ***")
    if args.output_to_json:
        logger.info(f"*** JSON OUTPUT to {args.json_output_dir} ***")
    if args.force_reprocessing:
        logger.info("*** FORCE REPROCESSING ENABLED ***")
    
    await process_pending_raw_bills(db,
                                   dry_run=args.dry_run,
                                   output_to_json=args.output_to_json,
                                   json_output_dir=args.json_output_dir,
                                   force_reprocessing=args.force_reprocessing,
                                   start_date_filter_dt=start_date_dt,
                                   end_date_filter_dt=end_date_dt,
                                   limit=args.limit)
    
    logger.info("--- Raw LEGISinfo to Evidence Processing Script Finished ---")

if __name__ == "__main__":
    asyncio.run(main()) 