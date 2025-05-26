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
from common_utils import KNOWN_PARTY_CODES # Added imports
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
# PROMISES_COLLECTION = 'promises' # OLD WAY
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

            # --- Client-side filter for promise_linking_status --- START
            current_linking_status = evidence_doc.to_dict().get('promise_linking_status')
            if current_linking_status is not None and current_linking_status != "pending":
                logger.info(f"Skipping evidence_item {evidence_id} due to client-side status check: '{current_linking_status}'")
                continue # Skip to the next document if status is not None and not "pending"
            # --- Client-side filter for promise_linking_status --- END

            # If we are here, the item needs processing (status is None or "pending")
            actual_processed_count += 1
            logger.info(f"Processing evidence_item: {evidence_id} (Status: {current_linking_status if current_linking_status else 'None'}) - Item {actual_processed_count} of {processing_limit if processing_limit else 'unlimited'}")

            evidence_item_updates = {'promise_linking_processed_at': firestore.SERVER_TIMESTAMP}

            try:
                bill_parl_id = evidence_doc.to_dict().get('bill_parl_id')
                if not bill_parl_id:
                    logger.warning(f"Skipping evidence_item {evidence_id}: missing 'bill_parl_id'.")
                    evidence_item_updates['promise_linking_status'] = 'error_missing_bill_id'
                    evidence_item_updates['promise_linking_error_message'] = "Missing bill_parl_id"
                    failed_updates[evidence_id] = "Missing bill_parl_id"
                    continue

                bill_doc_ref = db.collection(BILLS_DATA_COLLECTION).document(bill_parl_id)
                bill_doc_snapshot = bill_doc_ref.get()
                if not bill_doc_snapshot.exists:
                    logger.warning(f"Bill document {bill_parl_id} not found for evidence {evidence_id}. Skipping promise linking for this bill.")
                    evidence_item_updates['promise_linking_status'] = 'error_bill_doc_not_found'
                    evidence_item_updates['promise_linking_error_message'] = f"Bill {bill_parl_id} not found"
                    failed_updates[evidence_id] = f"Bill {bill_parl_id} not found"
                    continue
                
                bill_data = bill_doc_snapshot.to_dict()
                bill_keywords = bill_data.get('extracted_keywords_concepts', [])
                if not bill_keywords: # Only attempt to link if bill has keywords
                    logger.info(f"Skipping bill {bill_parl_id} for evidence {evidence_id} as it has no extracted keywords.")
                    evidence_item_updates['promise_linking_status'] = 'skipped_no_bill_keywords'
                    failed_updates[evidence_id] = "Bill has no keywords"
                    continue

                # Fetch all promises (using flat structure)
                all_promises_info = []
                logger.debug(f"Fetching all promises to compare with bill {bill_parl_id} (evidence {evidence_id}).")
                try:
                    # Query the flat promises collection directly
                    promises_collection = db.collection("promises")
                    promises_stream = promises_collection.stream()
                    
                    for p_snap in promises_stream:
                        p_data = p_snap.to_dict()
                        if 'id' not in p_data: # Ensure id (leaf) is present for internal logic
                            p_data['id'] = p_snap.id
                        all_promises_info.append({'data': p_data, 'path': p_snap.reference.path})
                        
                except Exception as e_promises:
                    logger.error(f"Error fetching promises from flat collection for bill {bill_parl_id}: {e_promises}")
                
                logger.debug(f"Fetched {len(all_promises_info)} total promises to check against bill {bill_parl_id}.")

                if not all_promises_info:
                    logger.warning("No promises found in the database to link against. Skipping bill linking for this batch.")
                    # Update evidence item status to reflect no promises were available for linking at this time
                    evidence_item_updates['promise_linking_status'] = 'skipped_no_promises_in_db'
                    failed_updates[evidence_id] = "No promises in DB for linking"
                    continue # Continue to next evidence item

                found_at_least_one_potential_link_for_evidence = False

                for promise_info in all_promises_info:
                    promise_doc_data = promise_info['data']
                    promise_full_path = promise_info['path'] # Full path to the promise
                    promise_leaf_id = promise_doc_data.get('id') # Leaf ID from promise_data

                    promise_keywords = promise_doc_data.get('extracted_keywords_concepts', [])
                    if not promise_keywords: # Only link if promise has keywords
                        continue

                    # Keyword Overlap Check (existing logic)
                    overlap_metrics = calculate_keyword_overlap(promise_keywords, bill_keywords)
                    jaccard_score = overlap_metrics["jaccard"]
                    common_keyword_count = overlap_metrics["common_count"]

                    is_potential_match_by_keyword = (
                        jaccard_score >= KEYWORD_JACCARD_THRESHOLD or \
                        (jaccard_score > 0.05 and common_keyword_count >= KEYWORD_COMMON_COUNT_THRESHOLD +1) or \
                        common_keyword_count >= KEYWORD_COMMON_COUNT_THRESHOLD + 2
                    )
                    
                    llm_assessment = None
                    if is_potential_match_by_keyword and gemini_model:
                        # Only call LLM if keyword match and model is available
                        if llm_calls_made_for_this_evidence < 10: # Limit LLM calls per evidence item
                            llm_assessment = call_gemini_for_relevance(promise_doc_data, bill_data, evidence_doc.to_dict())
                            llm_calls_made_for_this_evidence += 1
                        else:
                            logger.warning(f"Max LLM calls (10) reached for evidence {evidence_id}. Further keyword matches will not use LLM.")
                    
                    if llm_assessment and llm_assessment.get("likelihood_score") in ["High", "Medium"]:
                        link_strength = llm_assessment.get("likelihood_score")
                        explanation = llm_assessment.get("explanation")
                        logger.info(f"  LLM Confirmed Link: Promise '{promise_leaf_id}' (Path: {promise_full_path}) to Bill {bill_parl_id} (Evidence: {evidence_id}). Strength: {link_strength}")
                    elif is_potential_match_by_keyword and not gemini_model:
                        link_strength = "Keyword Match (LLM N/A)"
                        explanation = f"Jaccard: {jaccard_score:.2f}, Common: {common_keyword_count}. LLM not available."
                        logger.info(f"  Keyword Match (LLM N/A): Promise '{promise_leaf_id}' (Path: {promise_full_path}) to Bill {bill_parl_id} (Evidence: {evidence_id})")
                    elif is_potential_match_by_keyword and llm_assessment and llm_assessment.get("likelihood_score") in ["Low", "Not Related"]:
                        logger.info(f"  LLM Rejected Keyword Match: Promise '{promise_leaf_id}' (Path: {promise_full_path}) to Bill {bill_parl_id} (Evidence: {evidence_id}). LLM said: {llm_assessment.get('likelihood_score')}")
                        continue # Skip creating a link if LLM says low/not related despite keywords
                    elif is_potential_match_by_keyword:
                        logger.info(f"  Keyword Match (LLM Error/Format): Promise '{promise_leaf_id}' (Path: {promise_full_path}) to Bill {bill_parl_id} (Evidence: {evidence_id}). Fallback due to LLM issue.")
                        link_strength = "Keyword Match (LLM Error)"
                        explanation = f"Jaccard: {jaccard_score:.2f}, Common: {common_keyword_count}. LLM assessment failed or format issue."
                    else:
                        continue # No match

                    # Create Potential Link Document
                    potential_link_id = str(uuid.uuid4())
                    potential_link_data = {
                        'link_id': potential_link_id,
                        'promise_id': promise_full_path,  # IMPORTANT: Store FULL PATH here
                        'evidence_id': evidence_id, # This is evidence_item doc ID
                        'link_type': 'bill_to_promise',
                        'link_status': 'pending_review',
                        'link_strength_or_type': link_strength, 
                        'created_at': firestore.SERVER_TIMESTAMP,
                        'created_by_script': 'link_bills_to_promises.py',
                        'keyword_jaccard_score': jaccard_score,
                        'keyword_common_count': common_keyword_count,
                        'llm_assessment_score': llm_assessment.get("likelihood_score") if llm_assessment else None,
                        'llm_assessment_explanation': llm_assessment.get("explanation") if llm_assessment else None,
                        'parliament_session_id': bill_data.get('parliament_session_id'),
                        'promise_text_snippet': promise_doc_data.get('text', '')[:200],
                        'evidence_text_snippet': evidence_doc.to_dict().get('title_or_summary', '')[:200],
                    }
                    db.collection(POTENTIAL_LINKS_COLLECTION).document(potential_link_id).set(potential_link_data)
                    total_potential_links_created += 1
                    found_at_least_one_potential_link_for_evidence = True
                    logger.info(f"    Created potential link: {potential_link_id} (Promise Path: {promise_full_path} <=> Evi: {evidence_id})")

                if found_at_least_one_potential_link_for_evidence:
                    evidence_item_updates['promise_linking_status'] = 'completed_links_created'
                else:
                    evidence_item_updates['promise_linking_status'] = 'completed_no_links_found'
            
            except Exception as e_inner:
                logger.error(f"Error processing evidence_item {evidence_id} for bill linking: {e_inner}", exc_info=True)
                failed_updates[evidence_id] = str(e_inner)
                evidence_item_updates['promise_linking_status'] = 'error_processing_item'
                evidence_item_updates['promise_linking_error_message'] = str(e_inner)[:500]
            
            finally:
                # Update the evidence item's linking status
                if evidence_item_updates:
                    try:
                        db.collection(EVIDENCE_ITEMS_COLLECTION).document(evidence_id).update(evidence_item_updates)
                        logger.debug(f"Updated promise_linking_status for evidence {evidence_id} to: {evidence_item_updates.get('promise_linking_status')}")
                    except Exception as e_update:
                        logger.error(f"Failed to update promise_linking_status for evidence {evidence_id}: {e_update}")
                        failed_updates[evidence_id] = f"Failed to update status: {e_update}"
                
                last_processed_evidence_snapshot = evidence_doc # For pagination

            # Check overall processing limit
            if processing_limit is not None and actual_processed_count >= processing_limit:
                logger.info(f"Reached processing limit of {processing_limit} items. Stopping.")
                break # Break from inner loop (processing evidence items in current page)
        
        # After processing a page, check if outer processing limit was hit
        if processing_limit is not None and actual_processed_count >= processing_limit:
            logger.info("Overall processing limit met. Exiting pagination loop.")
            break # Break from outer while loop (pagination)
        
        # If current page was smaller than limit, it means it was the last page
        if len(current_page_evidence_docs_list) < PAGINATION_LIMIT_EVIDENCE_ITEMS:
            logger.info("Processed the last page of evidence items.")
            break

    logger.info(f"--- Bill to Promise Linking Process Finished ---")
    logger.info(f"Total potential links created: {total_potential_links_created}")
    if failed_updates:
        logger.warning(f"Failed to process or update status for {len(failed_updates)} evidence items:")
        for fid, err_msg in failed_updates.items():
            logger.warning(f"  - {fid}: {err_msg}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Link bills from evidence_items to promises in Firestore.")
    parser.add_argument("--limit", type=int, default=None, help="Limit the number of evidence_items to process (after client-side status filter).")
    parser.add_argument("--batch_size", type=int, default=DEFAULT_FIRESTORE_BATCH_SIZE, help="Batch size for Firestore writes of potential links.")
    
    args = parser.parse_args()

    link_bills_to_promises(processing_limit=args.limit, batch_size=args.batch_size)