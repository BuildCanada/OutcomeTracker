# Ensure the 'requests' library is installed in your Python environment:
# pip install requests

import requests
import xml.etree.ElementTree as ET
import firebase_admin
from firebase_admin import credentials, firestore
import google.generativeai as genai
import os
import time
import uuid
import json
import logging
from datetime import datetime, timezone
import argparse

# --- Load Environment Variables ---
from dotenv import load_dotenv
load_dotenv()
# --- End Load Environment Variables ---

# --- Logger Setup ---
logging.basicConfig(level=logging.INFO,
                    format='%(asctime)s - %(levelname)s - %(filename)s:%(lineno)d - %(message)s',
                    datefmt='%Y-%m-%d %H:%M:%S')
logger = logging.getLogger(__name__)
# --- End Logger Setup ---

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
            # Fallback for environments where GOOGLE_APPLICATION_CREDENTIALS might not be set
            # but default service account might be available (e.g. Cloud Functions, Cloud Run)
            firebase_admin.initialize_app()
            logger.info("Firebase Admin SDK initialized with default or environment-provided credentials.")
        
        project_id = os.getenv('FIREBASE_PROJECT_ID', firebase_admin.get_app().project_id if firebase_admin.get_app() else '[Cloud Project ID Not Set]')
        logger.info(f"Python (LinkBillsToPromises): Connected to CLOUD Firestore (Project: {project_id}).")
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

# --- LLM Configuration ---
gemini_model = None
try:
    GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
    if not GEMINI_API_KEY:
        logger.warning("Gemini API key (GEMINI_API_KEY) not set. Relevance assessment will be skipped.")
    else:
        genai.configure(api_key=GEMINI_API_KEY)
        llm_model_name = os.getenv("GEMINI_MODEL_LINKING", "gemini-2.5-flash-preview-04-17")
        logger.info(f"Using Gemini model for linking: {llm_model_name}")
        gemini_model = genai.GenerativeModel(llm_model_name)
except ImportError:
    logger.warning("google.generativeai library not found. Relevance assessment will be skipped.")
except Exception as e:
    logger.error(f"Error initializing Gemini model: {e}", exc_info=True)
# --- End LLM Configuration ---

# --- Constants ---
PROMISES_COLLECTION = 'promises'
BILLS_DATA_COLLECTION = 'bills_data'
EVIDENCE_ITEMS_COLLECTION = 'evidence_items'
POTENTIAL_LINKS_COLLECTION = 'promise_evidence_links'
DEFAULT_FIRESTORE_BATCH_SIZE = 50
KEYWORD_JACCARD_THRESHOLD = 0.1
KEYWORD_COMMON_COUNT_THRESHOLD = 2 # Common keywords needed if Jaccard is low
MAX_LLM_RETRIES = 2
PAGINATION_LIMIT_EVIDENCE_ITEMS = 50 # Number of evidence items to fetch per Firestore query loop
LLM_RETRY_DELAY = 5 # seconds
# --- End Constants ---

def calculate_keyword_overlap(promise_keywords, bill_keywords):
    """Calculates Jaccard index and common keyword count."""
    if not promise_keywords or not bill_keywords:
        return {"jaccard": 0.0, "common_count": 0}
    
    # Convert all keywords to lowercase for case-insensitive comparison
    set_promise = set(k.lower() for k in promise_keywords if isinstance(k, str))
    set_bill = set(k.lower() for k in bill_keywords if isinstance(k, str))
    
    intersection_len = len(set_promise.intersection(set_bill))
    union_len = len(set_promise.union(set_bill))
    
    jaccard = intersection_len / union_len if union_len > 0 else 0.0
    common_count = intersection_len
    
    return {"jaccard": jaccard, "common_count": common_count}

def call_gemini_for_relevance(promise_doc_data, bill_doc_data, evidence_doc_data):
    """
    Calls Gemini model to assess relevance between a promise and a bill event.
    Returns a dictionary with 'likelihood_score' and 'explanation' or None on failure.
    """
    if not gemini_model:
        logger.warning("Gemini model not available. Skipping relevance assessment.")
        return None

    promise_text = promise_doc_data.get('text', 'N/A')
    promise_dept_lead = promise_doc_data.get('responsible_department_lead', 'N/A')
    promise_relevant_depts = promise_doc_data.get('relevant_departments', [])
    promise_depts_list = [promise_dept_lead] + promise_relevant_depts
    promise_depts_str = ", ".join(filter(None, set(promise_depts_list))) or "N/A"
    promise_keywords = promise_doc_data.get('extracted_keywords_concepts', [])
    implied_action = promise_doc_data.get('implied_action_type', 'N/A')

    bill_number = bill_doc_data.get('bill_number_code', 'N/A')
    bill_title = bill_doc_data.get('long_title_en', 'N/A')
    bill_sponsoring_dept = bill_doc_data.get('sponsoring_department', 'N/A')
    bill_keywords = bill_doc_data.get('extracted_keywords_concepts', [])
    
    # Use evidence_title_or_summary from the evidence_item for Bill Summary/Details
    evidence_summary = evidence_doc_data.get('title_or_summary', 'N/A')


    prompt = f"""CONTEXT: You are an assistant determining if a Canadian federal Bill directly relates to fulfilling a government promise.

GOVERNMENT PROMISE (from `promises`):
- Promise Text: "{promise_text}"
- Lead/Relevant Department(s): "{promise_depts_str}"
- Key Concepts from Promise: {json.dumps(promise_keywords)}
- Implied Action Type: "{implied_action}"

BILL INFORMATION (from `bills_data` & `evidence_items`):
- Bill Number: "{bill_number}"
- Bill Title: "{bill_title}"
- Bill Summary/Details: "{evidence_summary}"
- Sponsoring Department: "{bill_sponsoring_dept}"
- Key Concepts from Bill: {json.dumps(bill_keywords)}

QUESTION:
Based on the information provided, how likely is it that this Bill ({bill_number}) represents a direct action or a significant step towards fulfilling the stated Government Promise?
Provide your assessment as a JSON object with the following fields:
- "likelihood_score": String, one of ["High", "Medium", "Low", "Not Related"]
- "explanation": String, 1-3 sentences explaining your reasoning, highlighting specific connections or discrepancies in scope, intent, or keywords.
"""
    logger.debug(f"Gemini Prompt for Promise ID {promise_doc_data.get('id', 'N/A')} & Evidence ID {evidence_doc_data.get('evidence_id', 'N/A')}:\n{prompt}")
    
    generation_config = genai.types.GenerationConfig(
        temperature=0.3 # You can adjust the temperature value here
        # thinking_config=genai.types.ThinkingConfig(thinking_budget=0) # Removed due to AttributeError
    )

    for attempt in range(MAX_LLM_RETRIES + 1):
        try:
            response = gemini_model.generate_content(prompt, generation_config=generation_config)
            cleaned_response_text = response.text.strip()

            # Handle potential markdown code block
            if cleaned_response_text.startswith("```json"):
                cleaned_response_text = cleaned_response_text[7:]
            if cleaned_response_text.endswith("```"):
                cleaned_response_text = cleaned_response_text[:-3]
            
            result = json.loads(cleaned_response_text.strip())
            if isinstance(result, dict) and "likelihood_score" in result and "explanation" in result:
                logger.info(f"Gemini assessment for Promise ID {promise_doc_data.get('id','N/A')} & Bill {bill_number}: {result['likelihood_score']}")
                return result
            else:
                logger.warning(f"Gemini response for P:{promise_doc_data.get('id','N/A')}/B:{bill_number} not in expected format: {response.text}")
                return None # Or raise an error / return specific error indicator
        except json.JSONDecodeError:
            logger.error(f"Error decoding JSON from Gemini response for P:{promise_doc_data.get('id','N/A')}/B:{bill_number}. Response: {response.text if 'response' in locals() else 'N/A'}", exc_info=True)
        except Exception as e:
            logger.error(f"Error calling Gemini for P:{promise_doc_data.get('id','N/A')}/B:{bill_number}: {e}", exc_info=True)
        
        if attempt < MAX_LLM_RETRIES:
            logger.info(f"Retrying LLM call in {LLM_RETRY_DELAY}s... (Attempt {attempt+1}/{MAX_LLM_RETRIES})")
            time.sleep(LLM_RETRY_DELAY)
    return None


def link_bills_to_promises(processing_limit=None, batch_size=50):
    """
    Main function to iterate through evidence items and link them to promises.
    """
    logger.info("--- Starting Bill to Promise Linking Process (Paginated) ---")
    logger.info(f"Will fetch evidence items in pages of {PAGINATION_LIMIT_EVIDENCE_ITEMS}.")
    if processing_limit:
        logger.info(f"Overall processing limit for items passing client-side filter: {processing_limit}")

    total_potential_links_created = 0
    failed_updates = {} # {evidence_id: error_message}
    
    actual_processed_count = 0 # Count of items that passed client-side status filter and were processed
    evaluated_from_db_count = 0 # Count of items pulled from DB in the current pagination loop

    last_processed_evidence_snapshot = None # For pagination

    while True: # Outer loop for pagination
        logger.info(f"Fetching next page of evidence items...")
        evidence_query_page = (db.collection(EVIDENCE_ITEMS_COLLECTION)
                             .where(filter=firestore.FieldFilter('evidence_source_type', '==', "Bill Event (LEGISinfo)"))
                             .order_by("__name__")) # Order by document ID for pagination

        if last_processed_evidence_snapshot:
            evidence_query_page = evidence_query_page.start_after(last_processed_evidence_snapshot)
        
        current_page_evidence_docs_list = list(evidence_query_page.limit(PAGINATION_LIMIT_EVIDENCE_ITEMS).stream())

        if not current_page_evidence_docs_list:
            logger.info("No more evidence items found in this page or overall. Concluding process.")
            break
        
        logger.info(f"Fetched {len(current_page_evidence_docs_list)} evidence items for this page.")

        for evidence_doc in current_page_evidence_docs_list:
            evaluated_from_db_count += 1
            evidence_id = evidence_doc.id

            # Initialize a counter for LLM calls for this specific evidence item
            llm_calls_made_for_this_evidence = 0

            # --- Client-side filter for dev_linking_status --- START
            current_linking_status = evidence_doc.to_dict().get('dev_linking_status')
            if current_linking_status is not None and current_linking_status != "pending":
                logger.info(f"Skipping evidence_item {evidence_id} due to client-side status check: '{current_linking_status}'")
                continue # Skip to the next document if status is not None and not "pending"
            # --- Client-side filter for dev_linking_status --- END

            # If we are here, the item needs processing (status is None or "pending")
            actual_processed_count += 1
            logger.info(f"Processing evidence_item: {evidence_id} (Status: {current_linking_status if current_linking_status else 'None'}) - Item {actual_processed_count} of {processing_limit if processing_limit else 'unlimited'}")

            evidence_item_updates = {'dev_linking_processed_at': firestore.SERVER_TIMESTAMP}

            try:
                bill_parl_id = evidence_doc.to_dict().get('bill_parl_id')
                if not bill_parl_id:
                    logger.warning(f"Skipping evidence_item {evidence_id}: missing 'bill_parl_id'.")
                    evidence_item_updates['dev_linking_status'] = 'error_missing_bill_id'
                    evidence_item_updates['dev_linking_error_message'] = "Missing bill_parl_id"
                    failed_updates[evidence_id] = "Missing bill_parl_id"
                    continue

                bill_doc_ref = db.collection(BILLS_DATA_COLLECTION).document(bill_parl_id)
                bill_doc = bill_doc_ref.get()

                if not bill_doc.exists:
                    logger.warning(f"Skipping evidence_item {evidence_id}: Bill data not found for bill_parl_id {bill_parl_id}.")
                    evidence_item_updates['dev_linking_status'] = 'error_bill_not_found'
                    evidence_item_updates['dev_linking_error_message'] = f"Bill data not found for bill_parl_id {bill_parl_id}"
                    failed_updates[evidence_id] = f"Bill data not found for bill_parl_id {bill_parl_id}"
                    continue
                
                bill_data = bill_doc.to_dict()
                bill_sponsoring_dept = bill_data.get('sponsoring_department')
                bill_keywords = bill_data.get('extracted_keywords_concepts', [])

                if not bill_keywords:
                     logger.info(f"Bill {bill_data.get('bill_number_code', bill_parl_id)} has no keywords. May limit matching.")


                # Departmental Match
                matched_promise_ids = set()
                if bill_sponsoring_dept:
                    logger.debug(f"Attempting department match for bill {bill_parl_id} with dept: {bill_sponsoring_dept}")
                    # Query 1: responsible_department_lead
                    promises_lead_dept_query = (db.collection(PROMISES_COLLECTION)
                                               .where(filter=firestore.FieldFilter('responsible_department_lead', '==', bill_sponsoring_dept))
                                               .stream())
                    for prom_doc in promises_lead_dept_query:
                        matched_promise_ids.add(prom_doc.id)
                    
                    # Query 2: relevant_departments (array-contains)
                    promises_relevant_dept_query = (db.collection(PROMISES_COLLECTION)
                                                   .where(filter=firestore.FieldFilter('relevant_departments', 'array_contains', bill_sponsoring_dept))
                                                   .stream())
                    for prom_doc in promises_relevant_dept_query:
                        matched_promise_ids.add(prom_doc.id)
                    logger.info(f"Found {len(matched_promise_ids)} promises via departmental match for bill {bill_parl_id} (Dept: {bill_sponsoring_dept}).")
                else:
                    logger.info(f"No sponsoring department for bill {bill_parl_id}. Proceeding to keyword search against all promises.")
                    # If no sponsoring department, matched_promise_ids will be empty.
                    # The logic below will handle fetching all promises if matched_promise_ids is empty.

                promise_ids_to_check = list(matched_promise_ids)

                if not promise_ids_to_check:
                    logger.info(f"No promises found via departmental match for bill {bill_parl_id} (or no sponsoring dept). Fetching all promises for keyword comparison.")
                    all_promises_query = db.collection(PROMISES_COLLECTION).select([]).stream() # select([]) fetches only IDs
                    promise_ids_to_check = [p.id for p in all_promises_query]
                    logger.info(f"Found {len(promise_ids_to_check)} total promises to check against bill {bill_parl_id}.")


                # Keyword Overlap & LLM for departmentally matched promises (or all promises if no dept match and we decide to change logic)
                # For now, only processes promises that came through departmental match:
                for promise_id in promise_ids_to_check: # Iterate over the determined list
                    promise_doc_snap = db.collection(PROMISES_COLLECTION).document(promise_id).get()
                    if not promise_doc_snap.exists:
                        logger.warning(f"Promise {promise_id} was matched by department but not found. Skipping.")
                        continue
                    
                    promise_data = promise_doc_snap.to_dict()
                    promise_data['id'] = promise_doc_snap.id # Add ID for logging
                    promise_keywords = promise_data.get('extracted_keywords_concepts', [])

                    if not promise_keywords:
                        logger.debug(f"Promise {promise_id} has no keywords. Skipping overlap calculation for this promise.")
                        continue

                    overlap_scores = calculate_keyword_overlap(promise_keywords, bill_keywords)
                    logger.info(f"P_ID:{promise_id} B_ID:{bill_parl_id} | P_KW:{json.dumps(promise_keywords)} | B_KW:{json.dumps(bill_keywords)} | Jaccard: {overlap_scores['jaccard']:.2f}, Common: {overlap_scores['common_count']}")

                    if overlap_scores['jaccard'] > KEYWORD_JACCARD_THRESHOLD or overlap_scores['common_count'] > KEYWORD_COMMON_COUNT_THRESHOLD:
                        logger.info(f"Keyword threshold met for P:{promise_id} & B:{bill_parl_id}. Sending to LLM.")
                        
                        llm_assessment = call_gemini_for_relevance(promise_data, bill_data, evidence_doc.to_dict())

                        if llm_assessment and llm_assessment.get('likelihood_score') in ["High", "Medium"]:
                            potential_link_id = str(uuid.uuid4())
                            link_doc_ref = db.collection(POTENTIAL_LINKS_COLLECTION).document(potential_link_id)
                            
                            promise_text_snippet = promise_data.get('text', '')[:150]

                            link_data = {
                                'potential_link_id': potential_link_id,
                                'promise_id': promise_id,
                                'evidence_id': evidence_id,
                                'bill_parl_id': bill_parl_id, # Adding for easier cross-reference
                                'promise_text_snippet': promise_text_snippet,
                                'evidence_title_or_summary': evidence_doc.to_dict().get('title_or_summary'),
                                'bill_long_title_en': bill_data.get('long_title_en', ''), # Added Bill Long Title
                                'evidence_source_url': evidence_doc.to_dict().get('source_url', ''), # Added Evidence Source URL
                                'keyword_overlap_score': overlap_scores, # Store both jaccard and common_count
                                'llm_likelihood_score': llm_assessment['likelihood_score'],
                                'llm_explanation': llm_assessment['explanation'],
                                'link_status': "pending_review",
                                'created_at': firestore.SERVER_TIMESTAMP,
                                'reviewed_at': None,
                                'reviewer_notes': None,
                                'reviewer_id': None
                            }
                            link_doc_ref.set(link_data)
                            total_potential_links_created += 1
                            logger.info(f"Potential link stored: {potential_link_id} (P:{promise_id} <> E:{evidence_id})")
                        elif llm_assessment:
                             logger.info(f"LLM assessment for P:{promise_id} & B:{bill_parl_id} was '{llm_assessment.get('likelihood_score', 'N/A')}'. Not storing link.")
                        else:
                            logger.warning(f"LLM assessment failed for P:{promise_id} & B:{bill_parl_id} after retries.")
                
                # Update status based on whether any promises were checked.
                if not promise_ids_to_check: # Should not happen if all promises are fetched as fallback
                    final_status = 'processed_no_promises_to_check'
                elif total_potential_links_created > 0: # We need a local counter for this
                    final_status = 'processed_links_created'
                else:
                     final_status = 'processed_no_kw_match'

                evidence_item_updates['dev_linking_status'] = final_status
                evidence_item_updates['dev_linking_error_message'] = None # Clear any previous error

            except Exception as e:
                logger.error(f"Error processing evidence_item {evidence_id}: {e}", exc_info=True)
                evidence_item_updates['dev_linking_status'] = "error"
                evidence_item_updates['dev_linking_error_message'] = str(e)
                failed_updates[evidence_id] = str(e)
            else: # No exception during processing of this evidence item
                evidence_item_updates['dev_linking_status'] = "processed"
                evidence_item_updates['dev_linking_error_message'] = None # Clear any previous error

            # Update the evidence_item itself
            try:
                db.collection(EVIDENCE_ITEMS_COLLECTION).document(evidence_id).update(evidence_item_updates)
                logger.debug(f"Updated evidence_item {evidence_id} with status: {evidence_item_updates['dev_linking_status']}")
            except Exception as e:
                logger.error(f"Failed to update evidence_item {evidence_id} status: {e}", exc_info=True)
                failed_updates[evidence_id] = f"Status update failed: {str(e)}"
            
            if processing_limit and actual_processed_count >= processing_limit:
                logger.info(f"Reached processing limit of {actual_processed_count} actual items after client-side filtering.")
                break # Break from inner loop (processing docs in current page)
        
        # After processing all items in the current_page_evidence_docs_list
        last_processed_evidence_snapshot = current_page_evidence_docs_list[-1]

        if processing_limit and actual_processed_count >= processing_limit:
            logger.info(f"Overall processing_limit of {processing_limit} met. Stopping pagination.")
            break # Break from outer while loop (fetching pages)
        
        if len(current_page_evidence_docs_list) < PAGINATION_LIMIT_EVIDENCE_ITEMS:
            logger.info("Fetched fewer items than pagination limit, indicating end of available data.")
            break # No more items to fetch

    logger.info("--- Bill to Promise Linking Process Finished ---")
    logger.info(f"Total evidence items evaluated from DB (across all pages): {evaluated_from_db_count}")
    logger.info(f"Total evidence items processed (passed client-side filter): {actual_processed_count}")
    logger.info(f"Total potential links created: {total_potential_links_created}")
    if failed_updates:
        logger.error("The following evidence items encountered errors during processing:")
        for evidence_id, error_message in failed_updates.items():
            logger.error(f"- {evidence_id}: {error_message}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Link bills from evidence_items to promises in Firestore.")
    parser.add_argument("--limit", type=int, default=None, help="Limit the number of evidence_items to process (after client-side status filter).")
    parser.add_argument("--batch_size", type=int, default=DEFAULT_FIRESTORE_BATCH_SIZE, help="Batch size for Firestore writes of potential links.")
    
    args = parser.parse_args()

    link_bills_to_promises(processing_limit=args.limit, batch_size=args.batch_size)