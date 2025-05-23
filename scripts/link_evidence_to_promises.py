#!/usr/bin/env python
# PromiseTracker/scripts/link_evidence_to_promises.py
# This script links evidence items to promises based on LLM analysis.

import firebase_admin
from firebase_admin import firestore, credentials
import os
from google import genai
from google.genai.types import GenerationConfig, Tool, GoogleSearch
import time
import asyncio
import logging
import traceback
from dotenv import load_dotenv
import json
import argparse
from datetime import datetime, timezone # Updated import
import uuid # For generating unique IDs
import re

# Attempt to import from sibling directory common_utils
try:
    import common_utils 
except ImportError:
    logger.warning("Could not import common_utils. Department standardization will not be available if common_utils is missing.")
    common_utils = None

# --- Load Environment Variables ---
load_dotenv()
# --- End Load Environment Variables ---

# --- Logger Setup ---
logging.basicConfig(level=logging.INFO,
                    format='%(asctime)s - %(levelname)s - %(filename)s:%(lineno)d - %(message)s',
                    datefmt='%Y-%m-%d %H:%M:%S')
logger = logging.getLogger("link_evidence_to_promises")
# --- End Logger Setup ---

# --- Firebase Configuration ---
db = None
if not firebase_admin._apps:
    try:
        firebase_admin.initialize_app()
        project_id = os.getenv('FIREBASE_PROJECT_ID', '[Not Set - Using Default]')
        logger.info(f"Connected to CLOUD Firestore (Project: {project_id}) using default credentials.")
        db = firestore.client()
    except Exception as e_default:
        logger.warning(f"Cloud Firestore init with default creds failed: {e_default}. Attempting service account.")
        cred_path = os.getenv('FIREBASE_SERVICE_ACCOUNT_KEY_PATH')
        if cred_path:
            try:
                logger.info(f"Attempting Firebase init with service account key from env var: {cred_path}")
                cred = credentials.Certificate(cred_path)
                app_name = 'link_evidence_app'
                try:
                    firebase_admin.initialize_app(cred, name=app_name)
                except ValueError: # App already exists
                    app_name_unique = f"{app_name}_{str(time.time())}"
                    firebase_admin.initialize_app(cred, name=app_name_unique)
                    app_name = app_name_unique

                project_id_sa = os.getenv('FIREBASE_PROJECT_ID', '[Not Set - Using Service Account]')
                logger.info(f"Connected to CLOUD Firestore (Project: {project_id_sa}) via service account.")
                db = firestore.client(app=firebase_admin.get_app(name=app_name))
            except Exception as e_sa:
                logger.critical(f"Firebase init with service account key from {cred_path} failed: {e_sa}", exc_info=True)
        else:
            logger.warning("FIREBASE_SERVICE_ACCOUNT_KEY_PATH environment variable not set, and default creds failed.")

if db is None:
    logger.critical("CRITICAL: Failed to obtain Firestore client. Exiting.")
    exit("Exiting: Firestore client not available.")
# --- End Firebase Configuration ---

# --- Gemini Configuration ---
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
if not GEMINI_API_KEY:
    logger.critical("GEMINI_API_KEY not found in environment variables or .env file.")
    exit("Exiting: Missing GEMINI_API_KEY.")
# genai.configure(api_key=GEMINI_API_KEY) # Implicitly handled by GOOGLE_API_KEY env var for GenerativeModel

# Ensure GOOGLE_API_KEY is set if GEMINI_API_KEY is used, as genai.Client() might prefer GOOGLE_API_KEY
if "GOOGLE_API_KEY" not in os.environ and GEMINI_API_KEY:
    os.environ["GOOGLE_API_KEY"] = GEMINI_API_KEY

LLM_MODEL_NAME = os.getenv("GEMINI_MODEL_NAME_EVIDENCE_LINKING", "models/gemini-2.5-pro-preview-05-06")
GENERATION_CONFIG_DICT = {
    "temperature": 0.0,
    "top_p": 0.95,
    "top_k": 64,
    "max_output_tokens": 65536, 
    "response_mime_type": "application/json",
}

# Define tools using the correctly imported classes
TOOLS_LIST = [
    Tool(google_search=GoogleSearch()) 
]

client = None
try:
    client = genai.Client() # api_key will be picked from GOOGLE_API_KEY env var
    logger.info(f"Successfully initialized Gemini Client.")
except Exception as e:
    logger.critical(f"Failed to initialize Gemini client: {e}", exc_info=True)
    exit("Exiting: Gemini client initialization failed.")
# --- End Gemini Configuration ---

# --- Constants ---
PROMISES_COLLECTION_ROOT = os.getenv("TARGET_PROMISES_COLLECTION", "promises")
EVIDENCE_COLLECTION = "evidence_items" # As per user notes

# Determine script directory to make prompt path robust
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROMPT_FILE_PATH = os.path.join(SCRIPT_DIR, "..", "prompts", "prompt_add_evidence_items_to_promises.md")

DEFAULT_REGION_CODE = "Canada" # Assuming this is still relevant for promise path construction
KNOWN_PARTY_CODES = ["LPC", "CPC", "NDP", "BQ"] # Reuse from enrich script if necessary for path, or simplify if not
RATE_LIMIT_DELAY_SECONDS = 5 # Increased delay for potentially larger LLM calls
# --- End Constants ---


def clean_json_from_markdown(text_blob: str) -> str:
    """
    Extracts a JSON string from a potential markdown code block.
    Handles \`\`\`json ... \`\`\` or \`\`\` ... \`\`\`.
    """
    logger.debug(f"clean_json_from_markdown received (repr, first 100 chars): {repr(text_blob[:100])}")
    # Regex to find content within ```json ... ``` or ``` ... ```
    # It looks for an optional "json" after the first triple backticks,
    # then captures everything (non-greedily) until the closing triple backticks.
    #regex_pattern = r"```(?:json)?\\s*([\\s\\S]+?)\\s*```" previous pattern
    regex_pattern = r"```(?:json)?\s*([\s\S]+?)\s*```"
    match = re.search(regex_pattern, text_blob)
    if match:
        extracted_json = match.group(1).strip()
        logger.debug(f"clean_json_from_markdown: Regex matched. Extracted JSON (repr, first 100 chars): {repr(extracted_json[:100])}")
        return extracted_json
    else:
        logger.warning(f"clean_json_from_markdown: Regex did NOT match. Pattern was: {regex_pattern}. Returning stripped original (repr, first 100 chars): {repr(text_blob.strip()[:100])}")
        return text_blob.strip()


async def query_promises(parliament_session_id: str, source_type: str | None, limit: int | None) -> list[dict]:
    """
    Queries promises from Firestore based on parliament_session_id and optional source_type, for the LPC party only.
    Extracts promise ID, text, responsible_department_lead, and the document reference.
    """
    logger.info(f"Querying promises for session '{parliament_session_id}', source_type: '{source_type}', limit: {limit}")
    all_matching_promises = []
    total_retrieved_count = 0

    party_code = "LPC"  # Hardcoded to LPC
    collection_path = f"{PROMISES_COLLECTION_ROOT}/{DEFAULT_REGION_CODE}/{party_code}"
    logger.debug(f"Querying collection: {collection_path}")
    try:
        query = db.collection(collection_path).where(
            filter=firestore.FieldFilter("parliament_session_id", "==", parliament_session_id)
        )
        query = query.where(
            filter=firestore.FieldFilter("bc_promise_rank", "in", ["medium", "strong"])
        )
        if source_type:
            query = query.where(filter=firestore.FieldFilter("source_type", "==", source_type))
        # Do NOT apply limit here; apply after department filtering

        promise_docs_stream = query.select(["text", "responsible_department_lead"]).stream()
        for doc_snapshot in await asyncio.to_thread(list, promise_docs_stream):
            promise_data = doc_snapshot.to_dict()
            if promise_data and promise_data.get("text"):
                all_matching_promises.append({
                    "id": doc_snapshot.id,
                    "text": promise_data["text"],
                    "responsible_department_lead": promise_data.get("responsible_department_lead"),
                    "doc_ref": doc_snapshot.reference
                })
            else:
                logger.warning(f"Promise {doc_snapshot.id} in {collection_path} missing 'text' field, skipping.")
        logger.info(f"Total promises retrieved matching criteria: {len(all_matching_promises)}")
        return all_matching_promises
    except Exception as e:
        logger.error(f"Error querying promises for party {party_code} in {collection_path}: {e}", exc_info=True)
        return []


async def load_llm_prompt(prompt_file: str) -> str:
    """Loads the LLM prompt from a specified file."""
    try:
        with open(prompt_file, 'r') as f:
            prompt_content = f.read()
        logger.info(f"Successfully loaded LLM prompt from {prompt_file}")
        return prompt_content
    except FileNotFoundError:
        logger.critical(f"Prompt file not found: {prompt_file}. Please ensure it exists.")
        exit(f"Exiting: Prompt file {prompt_file} not found.")
    except Exception as e:
        logger.critical(f"Error reading prompt file {prompt_file}: {e}", exc_info=True)
        exit(f"Exiting: Could not read prompt file {prompt_file}.")


async def generate_evidence_with_llm(promises_data: list[dict], base_prompt: str) -> list[dict] | None:
    """ 
    Generates evidence timeline entries for a list of promises using the LLM.
    
    Args:
        promises_data: A list of dictionaries, where each dictionary contains at least 'text' for a promise.
        base_prompt: The base LLM prompt template, excluding the specific commitment texts.

    Returns:
        A list of dictionaries structured according to the LLM output format if successful, otherwise None.
    """
    if not promises_data:
        logger.info("No promises provided to LLM for evidence generation.")
        return []

    commitments_section = "\n\n**Commitments to Process**\n"
    for promise in promises_data:
        commitments_section += f"* {promise['text']}\n"
    
    full_prompt = base_prompt + commitments_section
    logger.debug(f"Constructed full LLM prompt. Length: {len(full_prompt)}")
    # Log only a small part for general debugging, not the full potentially sensitive prompt.
    logger.debug(f"Full prompt starts with: {full_prompt[:200]}...")
    logger.debug(f"Full prompt ends with: ...{full_prompt[-200:]}")

    try:
        logger.info(f"Sending {len(promises_data)} promises to LLM for evidence generation using model: {LLM_MODEL_NAME}")
        
        if not client:
            logger.critical("Gemini client not initialized. Cannot call LLM.")
            return None
        
        # Reverted to the call that previously worked to get a response (though markdown-wrapped)
        response = await client.aio.models.generate_content(
            model=LLM_MODEL_NAME, 
            contents=full_prompt # Pass full_prompt directly as it was in the version that got a response
        )
        
        # Assuming response_mime_type="application/json" (set in GENERATION_CONFIG_DICT)
        # ensures response.text is raw JSON if the API call respects it.
        # For this reverted call, response.text is likely markdown and needs cleaning.
        raw_response_text = response.text
        logger.debug(f"LLM Raw Response Text (first 500 chars): {raw_response_text[:500]}")

        cleaned_response_text = clean_json_from_markdown(raw_response_text)
        logger.debug(f"LLM Cleaned Response Text (first 500 chars): {cleaned_response_text[:500]}")

        llm_output = json.loads(cleaned_response_text)

        # Basic validation of the LLM output structure
        if not isinstance(llm_output, list):
            logger.error(f"LLM output is not a list as expected. Type: {type(llm_output)}. Response: {cleaned_response_text[:1000]}")
            return None
        
        if len(llm_output) != len(promises_data):
            logger.warning(f"LLM output items ({len(llm_output)}) does not match input promises ({len(promises_data)}). This might indicate partial processing or an issue.")
            # Depending on strictness, you might return None or try to match what you can.
            # For now, let's be a bit lenient but log a clear warning.

        validated_output = []
        for i, item in enumerate(llm_output):
            if not isinstance(item, dict) or \
               "commitment_text" not in item or \
               "timeline_entries" not in item or \
               not isinstance(item["timeline_entries"], list) or \
               "progress_score" not in item or \
               "progress_summary" not in item:
                logger.warning(f"LLM output item {i} has incorrect structure or missing 'progress_score' or 'progress_summary': {str(item)[:200]}. Skipping this item.")
                # Potentially, try to map this back to the original promise or handle gracefully.
                # For now, we'll just skip malformed items but keep processing others if the main structure is a list.
                continue 
            validated_output.append(item)
        
        if not validated_output and llm_output: # If all items were malformed but we got a list
             logger.error("All LLM output items were malformed, though a list was returned.")
             return None

        logger.info(f"Successfully received and parsed LLM response. Found evidence structures for {len(validated_output)} commitments.")
        return validated_output

    except json.JSONDecodeError as json_err:
        logger.error(f"LLM response was not valid JSON. Error: {json_err}. Raw Response (after cleaning attempt): \n{cleaned_response_text if 'cleaned_response_text' in locals() else raw_response_text if 'raw_response_text' in locals() else 'Response not captured'}", exc_info=True)
        return None
    except Exception as e:
        # Catching specific genai.types.generation_types.StopCandidateException if needed
        # or other API-specific errors.
        if hasattr(e, 'message') and "response was blocked" in e.message.lower():
             logger.error(f"LLM generation failed because the response was blocked. Details: {e}", exc_info=True)
        elif hasattr(e, 'message') and "API key not valid" in e.message:
             logger.error(f"LLM generation failed due to an invalid API key. Details: {e}", exc_info=True)    
        else:
            logger.error(f"Error calling LLM for evidence generation: {e}", exc_info=True)
        return None


def generate_evidence_doc_id(parliament_session_id: str, evidence_source_type: str) -> str:
    """Generates a unique document ID for an evidence item."""
    # A simpler UUID-based approach for now. Can be refined.
    # e.g., P44-1_CanadaNewsCentre_20240115T123045Z_abc123xyz
    # Using a simpler UUID for now to ensure uniqueness easily.
    timestamp_str = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    short_uuid = str(uuid.uuid4())[:8]
    # Sanitize evidence_source_type for use in ID
    safe_source_type = evidence_source_type.replace(" ", "").replace("(", "").replace(")", "").replace(",", "")
    return f"EVD_{parliament_session_id}_{safe_source_type}_{timestamp_str}_{short_uuid}"


def generate_bill_evidence_doc_id(
    parliament_session_id: str, 
    bill_number_raw: str, 
    action_summary: str, 
    evidence_date_dt: datetime
) -> str:
    """Generates a unique document ID for a bill evidence item matching the specified pattern."""
    parl_sess_formatted = parliament_session_id.replace("-", "_") # e.g., 44-1 -> 44_1
    bill_num_formatted = bill_number_raw.replace("-", "") # e.g., C-49 -> C49 (or keep hyphen if preferred, example has C-10)
                                                     # Based on example legisinfo_bill_44_1_C-10..., hyphen is kept.
    bill_num_formatted = bill_number_raw # Use as is, C-10 example

    # Sanitize eventType from action_summary
    action_words = re.sub(r'[^a-z0-9\s]', '', action_summary.lower()).split()
    event_type_slug = "".join(action_words[:4])[:30] # First 4 words, max 30 chars, no spaces
    if not event_type_slug: event_type_slug = "event" # Fallback

    date_timestamp_str = evidence_date_dt.strftime("%Y%m%d000000")

    # Generate hash parts from UUID
    full_hash = uuid.uuid4().hex
    hash1 = full_hash[:5]  # Matches 60110 length
    hash2 = full_hash[5:9] # Matches 5fe6 length 

    return f"legisinfo_bill_{parl_sess_formatted}_{bill_num_formatted}_{event_type_slug}_{date_timestamp_str}_{hash1}_{hash2}"


async def process_and_store_evidence(
    llm_evidence_results: list[dict],
    original_promises_data: list[dict],
    parliament_session_id: str,
    dry_run: bool, # Added dry_run parameter
    db_batch_size: int = 250 # Firestore batch limit is 500 operations, good to stay under
) -> list[str]: # Returns list of processed evidence IDs (new or updated)
    """
    Processes LLM-generated evidence, matches it to original promises, 
    and stores/updates evidence items in Firestore.
    Returns a list of (new or updated) evidence document IDs that were processed.
    """
    if not llm_evidence_results:
        logger.info("No LLM evidence results to process.")
        return []

    processed_evidence_ids_in_batch = []
    firestore_batch = db.batch() # For batching Firestore writes
    operations_in_batch = 0

    # Create a mapping from original promise text to promise details for easier lookup
    # This assumes promise texts are unique enough for this matching.
    # If not, a more robust mapping (e.g., using IDs if LLM could return them) would be needed.
    promise_text_to_details_map = {p['text']: p for p in original_promises_data}

    for llm_item in llm_evidence_results:
        commitment_text_from_llm = llm_item.get("commitment_text")
        timeline_entries = llm_item.get("timeline_entries", [])
        progress_score_for_commitment = llm_item.get("progress_score")
        progress_summary_for_commitment = llm_item.get("progress_summary") # Extract progress_summary

        original_promise = promise_text_to_details_map.get(commitment_text_from_llm)

        if not original_promise:
            logger.warning(f"Could not match LLM commitment text to an original promise. Text: {commitment_text_from_llm[:100]}... Skipping its timeline entries.")
            continue
        
        promise_id = original_promise['id']
        promise_doc_ref = original_promise['doc_ref'] # Reference to the promise document
        responsible_department = original_promise.get("responsible_department_lead")
        linked_departments_array = [responsible_department] if responsible_department else []

        logger.info(f"Processing {len(timeline_entries)} timeline entries for promise ID: {promise_id}")

        newly_linked_evidence_ids_for_this_promise = []

        for entry_idx, evidence_entry in enumerate(timeline_entries):
            try:
                evidence_source_type = evidence_entry.get("evidence_source_type")
                evidence_date_str = evidence_entry.get("date") # YYYY-MM-DD
                action_summary = evidence_entry.get("action")
                source_url = evidence_entry.get("source_url")
                # progress_score_commitment = llm_item.get("progress_score") # At commitment level
                # status_impact_on_promise: Not directly in prompt, handle if available or clarify need
                status_impact = evidence_entry.get("status_impact_on_promise") 

                if not all([evidence_source_type, evidence_date_str, action_summary, source_url]):
                    logger.warning(f"Timeline entry for promise {promise_id} is missing required fields (type, date, action, url). Entry: {evidence_entry}. Skipping.")
                    continue

                current_timestamp = firestore.SERVER_TIMESTAMP # For ingested_at, dev_linking_processed_at
                evidence_date_dt = None
                try:
                    evidence_date_dt = datetime.strptime(evidence_date_str, "%Y-%m-%d").replace(tzinfo=timezone.utc)
                except ValueError:
                    logger.warning(f"Invalid date format '{evidence_date_str}' for evidence. Skipping.")
                    continue
                
                evidence_data_payload = {
                    "dev_linking_error_message": None,
                    "dev_linking_processed_at": current_timestamp,
                    "dev_linking_status": "processed",
                    "evidence_date": evidence_date_dt,
                    "evidence_source_type": evidence_source_type,
                    "ingested_at": current_timestamp,
                    "linked_departments": linked_departments_array,
                    "parliament_session_id": parliament_session_id,
                    "source_url": source_url,
                    "title_or_summary": action_summary,
                    "promise_ids": firestore.ArrayUnion([promise_id]) # Initialize/add current promise_id
                    # "evidence_id" from source - will be handled by bill logic or if found in URL
                }
                if status_impact: # Only add if LLM provided it
                    evidence_data_payload["status_impact_on_promise"] = status_impact

                # Handle Bill Events specifically
                if evidence_source_type == "Bill Event (LEGISinfo)":
                    # Attempt to parse bill number (e.g., C-49, S-10)
                    bill_match = re.search(r'\b([CS]-\d+)\b', action_summary, re.IGNORECASE) or \
                                 re.search(r'/([CS]-\d+)(?:/|_|$|\\.)\'', source_url, re.IGNORECASE)
                    bill_number_raw = bill_match.group(1).upper() if bill_match else None

                    if not bill_number_raw:
                        logger.warning(f"Could not parse bill number for LEGISinfo event for promise {promise_id}. Action: {action_summary}. URL: {source_url}. Creating as generic evidence.")
                        # Fallback to generic new evidence item if bill number not found
                        new_evidence_id = generate_evidence_doc_id(parliament_session_id, evidence_source_type)
                        evidence_doc_ref = db.collection(EVIDENCE_COLLECTION).document(new_evidence_id)
                        if not dry_run:
                            firestore_batch.set(evidence_doc_ref, evidence_data_payload)
                            operations_in_batch +=1
                        else:
                            logger.info(f"[DRY RUN] Would create new generic evidence item {new_evidence_id} for promise {promise_id} with payload: {evidence_data_payload}")
                        processed_evidence_ids_in_batch.append(new_evidence_id)
                        newly_linked_evidence_ids_for_this_promise.append(new_evidence_id)
                    else:
                        evidence_data_payload["source_document_raw_id"] = bill_number_raw
                        # Look for existing bill(s)
                        bill_query = db.collection(EVIDENCE_COLLECTION)\
                            .where(filter=firestore.FieldFilter("source_document_raw_id", "==", bill_number_raw)) \
                            .where(filter=firestore.FieldFilter("evidence_source_type", "==", "Bill Event (LEGISinfo)"))
                        # Remove .limit(1) to get all matching docs
                        existing_bill_docs = list(await asyncio.to_thread(bill_query.stream))

                        if existing_bill_docs:
                            for existing_bill_doc in existing_bill_docs:
                                existing_bill_doc_ref = existing_bill_doc.reference
                                logger.info(f"Found existing bill {bill_number_raw} (ID: {existing_bill_doc_ref.id}). Updating promise_ids for promise {promise_id}.")
                                update_data = {"promise_ids": firestore.ArrayUnion([promise_id])}
                                if not dry_run:
                                    firestore_batch.update(existing_bill_doc_ref, update_data)
                                    operations_in_batch +=1
                                else:
                                    logger.info(f"[DRY RUN] Would update existing bill {existing_bill_doc_ref.id} for promise {promise_id} with: {update_data}")
                                processed_evidence_ids_in_batch.append(existing_bill_doc_ref.id)
                                newly_linked_evidence_ids_for_this_promise.append(existing_bill_doc_ref.id)
                        else:
                            logger.info(f"Creating new evidence item for bill {bill_number_raw} for promise {promise_id}.")
                            # Use new ID generation for bills
                            new_bill_evidence_id = generate_bill_evidence_doc_id(
                                parliament_session_id,
                                bill_number_raw,
                                action_summary, # for eventType
                                evidence_date_dt # for eventDateTimestamp
                            )
                            evidence_doc_ref = db.collection(EVIDENCE_COLLECTION).document(new_bill_evidence_id)
                            if not dry_run:
                                firestore_batch.set(evidence_doc_ref, evidence_data_payload)
                                operations_in_batch +=1
                            else:
                                logger.info(f"[DRY RUN] Would create new bill evidence item {new_bill_evidence_id} for promise {promise_id} with payload: {evidence_data_payload}")
                            processed_evidence_ids_in_batch.append(new_bill_evidence_id)
                            newly_linked_evidence_ids_for_this_promise.append(new_bill_evidence_id)
                else:
                    # For all other types, create a new document
                    new_evidence_id = generate_evidence_doc_id(parliament_session_id, evidence_source_type)
                    # Try to extract a source-specific ID from URL if possible for 'evidence_id' field
                    # This is a placeholder, more robust extraction might be needed based on source patterns
                    url_id_match = re.search(r'id=(\w+)', source_url) or re.search(r'/(\d{4,})', source_url) # Basic patterns
                    if url_id_match:
                        evidence_data_payload["evidence_id"] = url_id_match.group(1)
                    else:
                         evidence_data_payload["evidence_id"] = "" # Leave blank as per notes

                    evidence_doc_ref = db.collection(EVIDENCE_COLLECTION).document(new_evidence_id)
                    if not dry_run:
                        firestore_batch.set(evidence_doc_ref, evidence_data_payload)
                        operations_in_batch +=1
                    else:
                        logger.info(f"[DRY RUN] Would create new evidence item {new_evidence_id} for promise {promise_id} with payload: {evidence_data_payload}")
                    processed_evidence_ids_in_batch.append(new_evidence_id)
                    newly_linked_evidence_ids_for_this_promise.append(new_evidence_id)

                # Commit batch if it reaches size limit
                if operations_in_batch >= db_batch_size and not dry_run:
                    logger.info(f"Committing batch of {operations_in_batch} Firestore operations (evidence create/update)...")
                    await asyncio.to_thread(firestore_batch.commit)
                    logger.info("Batch committed.")
                    firestore_batch = db.batch() # Start a new batch
                    operations_in_batch = 0
            except Exception as e_entry:
                logger.error(f"Error processing timeline entry #{entry_idx} for promise {promise_id}: {e_entry}. Entry: {evidence_entry}", exc_info=True)
                # Log error to the promise itself if possible, or a separate error log
                # For now, just logging to script output
                continue # Skip to next entry
        
        # After processing all evidence for a promise, update the promise with new evidence IDs
        if newly_linked_evidence_ids_for_this_promise:
            logger.info(f"Updating promise {promise_id} with {len(newly_linked_evidence_ids_for_this_promise)} new linked_evidence_ids.")
            # Ensure promise_doc_ref is valid
            if promise_doc_ref:
                update_promise_payload = {
                    "linked_evidence_ids": firestore.ArrayUnion(newly_linked_evidence_ids_for_this_promise),
                    "last_evidence_linking_at": firestore.SERVER_TIMESTAMP,
                    "dev_evidence_linking_status": "processed" # General status for this promise
                }
                if progress_score_for_commitment is not None: 
                    update_promise_payload["progress_score"] = progress_score_for_commitment
                if progress_summary_for_commitment is not None: # Add progress_summary if available
                    update_promise_payload["progress_summary"] = progress_summary_for_commitment
                
                if not dry_run:
                    firestore_batch.update(promise_doc_ref, update_promise_payload)
                    operations_in_batch +=1
                else:
                    logger.info(f"[DRY RUN] Would update promise {promise_id} with: {update_promise_payload}")
                
                 # Commit batch if it reaches size limit (also after promise updates)
                if operations_in_batch >= db_batch_size and not dry_run:
                    logger.info(f"Committing batch of {operations_in_batch} Firestore operations (promise update included)...")
                    await asyncio.to_thread(firestore_batch.commit)
                    logger.info("Batch committed.")
                    firestore_batch = db.batch() # Start a new batch
                    operations_in_batch = 0      
            else:
                 logger.warning(f"Promise doc_ref was None for promise ID {promise_id}. Cannot update linked_evidence_ids.")

    # Commit any remaining operations in the last batch
    if operations_in_batch > 0 and not dry_run:
        logger.info(f"Committing final batch of {operations_in_batch} Firestore operations...")
        await asyncio.to_thread(firestore_batch.commit)
        logger.info("Final batch committed.")
    elif operations_in_batch > 0 and dry_run:
        logger.info(f"[DRY RUN] Would commit final batch of {operations_in_batch} Firestore operations.")

    logger.info(f"Finished processing and storing evidence. Total evidence items processed in this run (new or updated): {len(set(processed_evidence_ids_in_batch))}")
    return list(set(processed_evidence_ids_in_batch)) # Return unique IDs


async def filter_promises_by_department_priority_eq_1(promises: list[dict], firestore_db) -> list[dict]:
    """Filters a list of promises to only those whose responsible department has bc_priority == 1."""
    if not common_utils:
        logger.warning("common_utils not available, skipping department priority filtering.")
        return promises

    logger.info(f"Filtering {len(promises)} promises by department bc_priority == 1")
    filtered_promises = []
    department_priority_cache = {} # Cache to avoid re-fetching priority for the same department

    for promise_info in promises:
        responsible_dept_lead_raw = promise_info.get("responsible_department_lead")
        if not responsible_dept_lead_raw:
            logger.debug(f"Promise ID {promise_info.get('id')} has no 'responsible_department_lead'. Skipping for department priority filter.")
            continue

        # Standardize department name using common_utils
        standardized_dept_name = common_utils.standardize_department_name(responsible_dept_lead_raw)

        if not standardized_dept_name:
            logger.warning(f"Could not standardize department name for raw value '{responsible_dept_lead_raw}' from promise ID {promise_info.get('id')}. Skipping for department priority filter.")
            continue
        # Check cache first
        if standardized_dept_name in department_priority_cache:
            dept_bc_priority = department_priority_cache[standardized_dept_name]
        else:
            # Query department_config for bc_priority
            try:
                dept_config_query = firestore_db.collection('department_config') \
                                        .where(filter=firestore.FieldFilter('official_full_name', '==', standardized_dept_name)) \
                                        .limit(1)
                dept_docs = list(await asyncio.to_thread(dept_config_query.stream))
                if dept_docs:
                    dept_data = dept_docs[0].to_dict()
                    dept_bc_priority = dept_data.get('bc_priority')
                    department_priority_cache[standardized_dept_name] = dept_bc_priority # Cache it
                else:
                    logger.warning(f"No department_config entry found for standardized name '{standardized_dept_name}'. Cannot check bc_priority for promise ID {promise_info.get('id')}.")
                    department_priority_cache[standardized_dept_name] = None # Cache None to avoid re-query
                    dept_bc_priority = None
            except Exception as e:
                logger.error(f"Error querying department_config for '{standardized_dept_name}': {e}", exc_info=True)
                department_priority_cache[standardized_dept_name] = None # Cache None on error
                dept_bc_priority = None

        if dept_bc_priority == 1:
            logger.debug(f"Promise ID {promise_info.get('id')} (Dept: {standardized_dept_name}, Priority: {dept_bc_priority}) meets bc_priority == 1. Keeping.")
            filtered_promises.append(promise_info)
        else:
            logger.debug(f"Promise ID {promise_info.get('id')} (Dept: {standardized_dept_name}, Priority: {dept_bc_priority}) does not meet bc_priority == 1. Discarding.")
    logger.info(f"After department priority filtering, {len(filtered_promises)} promises remain.")
    return filtered_promises


async def main_async_entrypoint():
    parser = argparse.ArgumentParser(description='Link evidence items to promises using LLM analysis.')
    parser.add_argument(
        '--parliament_session_id',
        type=str,
        required=True,
        help='The parliament_session_id to filter promises (e.g., "44").'
    )
    parser.add_argument(
        '--source_type',
        type=str,
        default=None,
        help='Optional source_type to further filter promises (e.g., "Mandate Letter").'
    )
    parser.add_argument(
        '--limit_promises',
        type=int,
        default=None,
        help='Optional limit on the number of promises to process.'
    )
    parser.add_argument(
        '--force_reprocessing_evidence', # For future use, if we want to re-link
        action='store_true',
        help='Force reprocessing of evidence linking even if evidence_ids already exist on a promise (Not fully implemented yet).'
    )
    parser.add_argument(
        '--dry_run',
        action='store_true',
        help='Perform a dry run without making any changes to Firestore.'
    )
    parser.add_argument(
        '--department_priority_threshold',
        type=int,
        default=None,
        help='Optional. Process promises only if their responsible department has a bc_priority less than or equal to this integer value.'
    )

    args = parser.parse_args()

    logger.info("--- Starting Evidence Linking Script ---")
    if args.dry_run:
        logger.info("*** DRY RUN MODE ENABLED: No changes will be written to Firestore. ***")
    logger.info(f"Parliament Session ID: {args.parliament_session_id}")
    if args.source_type:
        logger.info(f"Source Type: {args.source_type}")
    if args.limit_promises:
        logger.info(f"Promise processing limit: {args.limit_promises}")
    if args.department_priority_threshold is not None:
        logger.info(f"Department bc_priority threshold: <= {args.department_priority_threshold}")

    # 1. Load LLM Prompt
    # The prompt content will be used later when constructing the request to the LLM
    # We are loading it here to ensure it's available.
    # The actual prompt text that includes the commitments will be constructed dynamically.
    base_prompt_template = await load_llm_prompt(PROMPT_FILE_PATH)
    
    # 1. Query Promises from Firestore
    promises_to_process = await query_promises(
        parliament_session_id=args.parliament_session_id,
        source_type=args.source_type,
        limit=args.limit_promises
    )

    if not promises_to_process:
        logger.info("No promises found matching the initial query criteria. Exiting.")
        return

    logger.info(f"Found {len(promises_to_process)} promises after initial query.")

    # Apply department priority == 1 filter
    promises_to_process = await filter_promises_by_department_priority_eq_1(promises_to_process, db)
    if not promises_to_process:
        logger.info("No promises remain after department bc_priority == 1 filtering. Exiting.")
        return

    # Apply limit after filtering
    if args.limit_promises is not None:
        promises_to_process = promises_to_process[:args.limit_promises]
        logger.info(f"After applying limit, {len(promises_to_process)} promises will be processed.")

    logger.info(f"Processing {len(promises_to_process)} promises after all filters.")
    # Example: Log the first few promise texts for verification
    for i, p_info in enumerate(promises_to_process[:3]):
        logger.debug(f"Promise {i+1} ID: {p_info['id']}, Text: {p_info['text'][:100]}...")


    # 2. Feed promises to LLM for evidence generation
    if promises_to_process:
        for i, promise in enumerate(promises_to_process):
            logger.info(f"Processing promise {i+1}/{len(promises_to_process)}: {promise['id']}")
            llm_generated_evidence_data = await generate_evidence_with_llm([promise], base_prompt_template)
            if llm_generated_evidence_data is None:
                logger.error(f"Failed to generate evidence data from LLM for promise {promise['id']}. Skipping.")
                continue
            elif not llm_generated_evidence_data:
                logger.info(f"LLM returned no evidence data for promise {promise['id']}. Skipping.")
                continue
            else:
                logger.info(f"Successfully retrieved evidence structure from LLM for promise {promise['id']}.")
                processed_evidence_document_ids = await process_and_store_evidence(
                    llm_generated_evidence_data,
                    [promise], # Only the current promise
                    args.parliament_session_id,
                    args.dry_run
                )
                logger.info(f"Successfully processed and stored/updated {len(processed_evidence_document_ids)} evidence items for promise {promise['id']}.")
    else:
        logger.info("No promises found matching the initial query criteria. Exiting.")


    # Placeholder for the rest of the logic (step 4, updating promises, is partially handled in process_and_store_evidence)
    logger.info("Further implementation needed for:")
    # logger.info("3. Processing LLM response and validating JSON.") # Largely handled
    # logger.info("4. Writing evidence to 'evidence_items' collection (handling bills vs. other types).") # Implemented
    logger.info("5. Updating 'linked_evidence_ids' in the 'promises' collection.") # Implemented within process_and_store_evidence
    logger.info("6. Implementing helper functions for Firestore interactions and ID generation.") # Partially done


    logger.info("--- Evidence Linking Script Finished ---")

if __name__ == "__main__":
    asyncio.run(main_async_entrypoint()) 