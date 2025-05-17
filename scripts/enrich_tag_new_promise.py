#!/usr/bin/env python
# PromiseTracker/scripts/enrich_and_preprocess_promise.py
# This script is used to enrich and preprocess new promises after they are added to the promise collection.

import firebase_admin
from firebase_admin import firestore, credentials
import os
import google.generativeai as genai
import time
import asyncio
import logging
import traceback
from dotenv import load_dotenv
import json
import argparse
import re
from datetime import datetime # Keep this for potential future use with timestamps

# --- Load Environment Variables ---
load_dotenv()
# --- End Load Environment Variables ---

# --- Logger Setup ---
# Using a generic logger name for this new script
logging.basicConfig(level=logging.INFO,
                    format='%(asctime)s - %(levelname)s - %(filename)s:%(lineno)d - %(message)s',
                    datefmt='%Y-%m-%d %H:%M:%S')
logger = logging.getLogger("enrich_preprocess_promise")
# --- End Logger Setup ---

# --- Firebase Configuration ---
db = None
if not firebase_admin._apps:
    # Attempt to initialize with default credentials first (e.g., for Cloud Functions, local ADC)
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
                # If default app exists due to partial success or another init, use specific name
                app_name = 'enrich_preprocess_promise_app' if firebase_admin._apps else firebase_admin.DEFAULT_APP_NAME
                try:
                    firebase_admin.initialize_app(cred, name=app_name)
                except ValueError: # Default app already exists
                     firebase_admin.initialize_app(cred, name=app_name + str(time.time())) # Unique name

                project_id_sa = os.getenv('FIREBASE_PROJECT_ID', '[Not Set - Using Service Account]')
                logger.info(f"Connected to CLOUD Firestore (Project: {project_id_sa}) via service account.")
                db = firestore.client(app=firebase_admin.get_app(name=app_name)) if app_name != firebase_admin.DEFAULT_APP_NAME else firestore.client()

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
genai.configure(api_key=GEMINI_API_KEY)

# Using a single model configuration, adaptable for different tasks via prompts
# Taking the more specific one from process_mandate_commitments.py as a base
LLM_MODEL_NAME = os.getenv("GEMINI_MODEL_NAME", "models/gemini-2.5-flash-preview-04-17") # More general model
GENERATION_CONFIG = {
    "temperature": 0.2,
    "top_p": 0.95,
    "top_k": 64,
    "max_output_tokens": 65536, 
    "response_mime_type": "application/json", # Standardize on JSON output
}

# System instruction for History Rationale (can be passed per call if needed, or set if model is dedicated)
HISTORY_RATIONALE_SYSTEM_INSTRUCTION = """You are a meticulous AI research assistant specializing in Canadian federal government policy and history.
Your task is to analyze Canadian government commitments and construct a factual timeline of key preceding events.
These events include policies, legislative actions, official announcements, significant public reports, or court decisions that directly contributed to or motivated the specific commitment.
For each timeline entry, you MUST provide:
1. The exact date (formatted as YYYY-MM-DD) of its publication, announcement, or decision.
2. A concise description of the 'Action' or event that is 30 words or less.
3. A verifiable 'Source URL' pointing to an official government document, parliamentary record, press release, or a reputable news article about the event.
Focus only on concrete, verifiable federal-level events that *preceded* the commitment date.
Return no more than four of the most directly impactful and relevant preceding events. Present events chronologically.
If no specific preceding events are found that meet the relevance criteria, return an empty JSON array []."""

# Initialize the Generative Model
# We'll initialize one model and use it for all tasks.
# If specific system instructions are needed per task, they can be part of the `generate_content_async` call.
try:
    generative_model = genai.GenerativeModel(
        model_name=LLM_MODEL_NAME,
        generation_config=GENERATION_CONFIG,
        # System instruction can be set here if it's globally applicable,
        # or passed during generate_content_async for task-specific instructions.
        # For history rationale, we'll pass it during the call.
    )
    logger.info(f"Initialized Gemini model: {LLM_MODEL_NAME}")
except Exception as e:
    logger.critical(f"Failed to initialize Gemini model '{LLM_MODEL_NAME}': {e}", exc_info=True)
    exit("Exiting: Gemini model initialization failed.")
# --- End Gemini Configuration ---

# --- Constants ---
PROMISES_COLLECTION = 'promises'

# Fields for history/rationale
HISTORY_RATIONALE_FIELD = 'commitment_history_rationale'

# Fields for linking preprocessing
LINKING_KEYWORDS_FIELD = 'extracted_keywords_concepts'
LINKING_ACTION_TYPE_FIELD = 'implied_action_type'
LINKING_PREPROCESSING_DONE_FIELD = 'linking_preprocessing_done_at' # Timestamp

# For Action Type classification
ACTION_TYPES_LIST = [
    "legislative", "funding_allocation", "policy_development", 
    "program_launch", "consultation", "international_agreement", 
    "appointment", "other"
]

RATE_LIMIT_DELAY_SECONDS = 2 # Seconds to wait between promises (for multiple LLM calls per promise)
# --- End Constants ---


# --- LLM Interaction Functions ---

async def generate_commitment_history_llm(promise_text: str, source_type: str, entity: str, date_issued: str):
    """Generates a timeline of preceding events using Gemini for the 'commitment_history_rationale' field."""
    logger.debug(f"Generating commitment history for promise: {promise_text[:70]}...")
    date_issued_str = date_issued or 'Unknown'

    prompt = f"""Given the following Canadian government commitment:

Commitment Text:
\"\"\"
{promise_text}
\"\"\"

Source Type: {source_type or 'Unknown'}
Announced By: {entity or 'Unknown'}
Date Commitment Announced: {date_issued_str}

Task:
Construct a timeline of key Canadian federal policies, legislative actions, official announcements, significant public reports, or court decisions that *preceded* and *directly contributed to or motivated* this specific commitment.
Prioritize the **top 2-4 most directly relevant and impactful** federal-level events that demonstrate the context and motivation for this commitment.
For every distinct event in the timeline, provide:
1.  The exact date (YYYY-MM-DD) of its publication, announcement, or decision.
2.  A concise description of the 'Action' or event.
3.  A verifiable 'Source URL' pointing to an official government document, parliamentary record, press release, or a reputable news article about the event.

Output Requirements:
*   Format: Respond with ONLY a valid JSON array of objects, containing **0 to 4** timeline event objects. If no relevant preceding events are found, return an empty array `[]`.
*   Object Structure: Each object MUST contain the keys "date" (string, "YYYY-MM-DD"), "action" (string), and "source_url" (string).
*   Content: Focus only on concrete, verifiable federal-level events.
*   Chronology: Present timeline events chronologically (earliest first), all preceding the 'Date Commitment Announced' ({date_issued_str}).

Example JSON Output (should be an array of objects like this):
```json
[
  {{
    "date": "YYYY-MM-DD",
    "action": "Description of a key preceding policy, legislative action, or official announcement.",
    "source_url": "https://example.com/official-source-link1"
  }},
  {{
    "date": "YYYY-MM-DD",
    "action": "Description of another relevant preceding event.",
    "source_url": "https://example.com/official-source-link2"
  }}
]
```
If no events are found, return:
```json
[]
```
Ensure the output is ONLY the JSON array.
"""

    try:
        # Pass system instruction during the call for this specific task
        response = await generative_model.generate_content_async(
            prompt,
            generation_config=GENERATION_CONFIG, # Ensure config is passed if not default on model
            # To pass system_instruction here, it should be part of `contents` or a different model init
            # For now, relying on it being part of the prompt or a global model setting if that's how it works.
            # Re-checking: system_instruction is usually set at model initialization.
            # Let's create a specific model instance if system_instruction is critical and different per call.
            # For simplicity now, assume HISTORY_RATIONALE_SYSTEM_INSTRUCTION guides the main model if set,
            # or the detailed prompt is sufficient.
            # If using a single model, system_instruction should be general or prompts very explicit.
            # The current `generative_model` was init'd without a system instruction.
            # The `process_mandate_commitments.py` set it on its model. Let's try passing it:
        )
        # The `genai.GenerativeModel` takes `system_instruction` at init.
        # To have different system instructions, you'd typically use different model objects or
        # ensure the user prompt is comprehensive enough.
        # Let's re-initialize a model specifically for this task if needed, or ensure prompt is king.
        # For now, this prompt is very detailed.

        # The response_mime_type="application/json" should ensure `response.text` is parseable JSON.
        timeline_events = json.loads(response.text) # Direct parsing due to mime_type

        if not isinstance(timeline_events, list):
            logger.warning(f"LLM history response was not a JSON list for promise: {promise_text[:70]}. Response: {response.text}")
            return None
        
        if not timeline_events: # Empty list is valid
            logger.debug(f"LLM returned an empty list for history (0 events found) for promise: {promise_text[:70]}.")
            return []

        if not (0 <= len(timeline_events) <= 4): # Allow 0-4 events
            logger.warning(f"LLM history response list length ({len(timeline_events)}) is not 0-4 for promise: {promise_text[:70]}. Response: {response.text}")
            return None # Or return [] if we want to be lenient and just cap it. For now, strict.

        validated_events = []
        for i, event in enumerate(timeline_events):
            if not (isinstance(event, dict) and \
                    all(key in event for key in ["date", "action", "source_url"]) and \
                    isinstance(event.get("date"), str) and \
                    isinstance(event.get("action"), str) and \
                    isinstance(event.get("source_url"), str) and \
                    re.match(r"^\d{4}-\d{2}-\d{2}$", event["date"])):
                logger.warning(f"Invalid event structure in LLM history response for promise: {promise_text[:70]}. Event {i}: {event}. Full response: {response.text}")
                return None # One bad event invalidates all
            validated_events.append(event)
        
        logger.debug(f"Successfully parsed commitment history: {validated_events}")
        return validated_events

    except json.JSONDecodeError as json_err:
        logger.warning(f"LLM history response was not valid JSON for promise: {promise_text[:70]}. Error: {json_err}. Raw Response: \n{response.text if 'response' in locals() else 'N/A'}")
        return None
    except Exception as e:
        logger.error(f"Error calling Gemini for commitment history: {e}. Promise: {promise_text[:70]}", exc_info=True)
        return None


async def extract_keywords_llm(promise_text: str):
    """Extracts keywords using Gemini for the 'extracted_keywords_concepts' field."""
    logger.debug(f"Extracting keywords for promise: {promise_text[:70]}...")
    
    prompt = f"""From the following government promise text:
\"\"\"
{promise_text}
\"\"\"
Extract a list of 5-10 key nouns and specific named entities (e.g., program names, specific laws mentioned, key organizations) that represent the core subjects and significant concepts of this promise.

Output Requirements:
*   Format: Respond with ONLY a valid JSON array of strings.
*   Content: Each string should be a distinct keyword or named entity.
*   Quantity: Aim for 5 to 10 items. If fewer are truly relevant, provide those. If many are relevant, prioritize the most important.

Example JSON Output:
```json
["Affordable Child Care", "National System", "Early Learning", "$10-a-day", "Provinces and Territories"]
```
If no specific keywords can be extracted, return an empty JSON array `[]`.
Ensure the output is ONLY the JSON array.
"""
    try:
        response = await generative_model.generate_content_async(prompt) # Using the global model
        keywords = json.loads(response.text) # Direct parsing due to mime_type

        if not isinstance(keywords, list) or not all(isinstance(k, str) for k in keywords):
            logger.warning(f"LLM keyword extraction did not return a valid list of strings. Promise: {promise_text[:70]}. Response: {response.text}")
            return [] # Default to empty list on bad structure
        
        logger.debug(f"Extracted keywords: {keywords}")
        return keywords
    except json.JSONDecodeError as e:
        logger.error(f"Error decoding JSON from Gemini keyword response: {e}. Promise: {promise_text[:70]}. Response text: {response.text if 'response' in locals() else 'N/A'}", exc_info=True)
        return []
    except Exception as e:
        logger.error(f"Error calling Gemini for keyword extraction: {e}. Promise: {promise_text[:70]}", exc_info=True)
        return []


async def infer_action_type_llm(promise_text: str):
    """Infers action type using Gemini for the 'implied_action_type' field."""
    logger.debug(f"Inferring action type for promise: {promise_text[:70]}...")
    action_types_string = ", ".join([f'"{t}"' for t in ACTION_TYPES_LIST]) # Quote for JSON style

    prompt = f"""Analyze the following government promise:
\"\"\"
{promise_text}
\"\"\"
What is the primary type of action being committed to? Choose one from the following list: {action_types_string}.

Output Requirements:
*   Format: Respond with ONLY a valid JSON object containing a single key "action_type" whose value is one of the provided action types.
*   Content: The value for "action_type" MUST be exactly one of the strings from the list: {action_types_string}.

Example JSON Output:
```json
{{
  "action_type": "legislative"
}}
```
Ensure the output is ONLY the JSON object.
"""
    try:
        response = await generative_model.generate_content_async(prompt) # Using the global model
        data = json.loads(response.text) # Direct parsing due to mime_type

        if isinstance(data, dict) and "action_type" in data and data["action_type"] in ACTION_TYPES_LIST:
            action_type = data["action_type"]
            logger.debug(f"Inferred action type: {action_type}")
            return action_type
        else:
            logger.warning(f"Gemini action type classification returned an unknown or badly formatted type. Promise: {promise_text[:70]}. Response: {response.text}. Defaulting to 'other'.")
            # Attempt to find a match even if there's extra content, e.g. "The action type is: legislative"
            raw_response_text = response.text.lower()
            for valid_type in ACTION_TYPES_LIST:
                if f'"{valid_type}"' in raw_response_text: # Check for quoted type in raw string
                    logger.info(f"Found valid action type '{valid_type}' via fallback search in: '{raw_response_text}'. Using '{valid_type}'.")
                    return valid_type
            return "other"
    except json.JSONDecodeError as e:
        logger.error(f"Error decoding JSON from Gemini action type response: {e}. Promise: {promise_text[:70]}. Response text: {response.text if 'response' in locals() else 'N/A'}", exc_info=True)
        return "other"
    except Exception as e:
        logger.error(f"Error calling Gemini for action type classification: {e}. Promise: {promise_text[:70]}", exc_info=True)
        return "other"


# --- Core Processing Logic ---
async def process_promise(promise_id: str, force_reprocessing: bool = False):
    """
    Processes a single promise document for history rationale and linking preprocessing.
    Returns True if updates were made, False otherwise.
    """
    logger.info(f"Processing promise ID: {promise_id}. Force reprocessing: {force_reprocessing}")
    doc_ref = db.collection(PROMISES_COLLECTION).document(promise_id)
    
    try:
        doc_snapshot = await asyncio.to_thread(doc_ref.get) # Async fetch
        if not doc_snapshot.exists:
            logger.warning(f"Promise document {promise_id} not found. Skipping.")
            return False

        promise_data = doc_snapshot.to_dict()
        promise_text = promise_data.get('text')

        if not promise_text:
            logger.warning(f"Promise {promise_id} has no 'text' field. Skipping.")
            return False

        update_payload = {}
        made_changes = False
        llm_calls_made_this_promise = 0

        # 1. Commitment History Rationale
        needs_history = HISTORY_RATIONALE_FIELD not in promise_data or promise_data.get(HISTORY_RATIONALE_FIELD) is None
        if force_reprocessing or needs_history:
            logger.info(f"Generating commitment history for promise ID: {promise_id} (Force: {force_reprocessing}, Needs: {needs_history})")
            # Ensure all required fields for history generation are present
            source_type = promise_data.get('source_type')
            entity = promise_data.get('candidate_or_government')
            date_issued = promise_data.get('date_issued')
            
            # Optional: Add a check here if these fields are strictly necessary for history generation
            # For now, they are passed as-is (can be None)

            if llm_calls_made_this_promise > 0: await asyncio.sleep(RATE_LIMIT_DELAY_SECONDS / 2) # Brief intra-promise delay
            history_rationale = await generate_commitment_history_llm(promise_text, source_type, entity, date_issued)
            llm_calls_made_this_promise+=1

            if history_rationale is not None: # Empty list is a valid successful response (0 items)
                update_payload[HISTORY_RATIONALE_FIELD] = history_rationale
                logger.info(f"Successfully generated commitment history for promise ID: {promise_id}")
            else:
                logger.warning(f"Failed to generate or validate commitment history for promise ID: {promise_id}. Field will not be updated.")
        else:
            logger.info(f"Skipping commitment history generation for {promise_id} (already exists or not forced).")

        # 2. Linking Preprocessing (Keywords and Action Type)
        needs_linking_preprocessing = LINKING_PREPROCESSING_DONE_FIELD not in promise_data
        if force_reprocessing or needs_linking_preprocessing:
            logger.info(f"Performing linking preprocessing for promise ID: {promise_id} (Force: {force_reprocessing}, Needs: {needs_linking_preprocessing})")
            
            if llm_calls_made_this_promise > 0: await asyncio.sleep(RATE_LIMIT_DELAY_SECONDS / 2)
            extracted_keywords = await extract_keywords_llm(promise_text)
            llm_calls_made_this_promise+=1
            
            if llm_calls_made_this_promise > 0: await asyncio.sleep(RATE_LIMIT_DELAY_SECONDS / 2)
            implied_action_type = await infer_action_type_llm(promise_text)
            llm_calls_made_this_promise+=1

            # Keywords: empty list is acceptable if LLM returns it.
            update_payload[LINKING_KEYWORDS_FIELD] = extracted_keywords 
            # Action Type: defaults to "other" if issues.
            update_payload[LINKING_ACTION_TYPE_FIELD] = implied_action_type
            update_payload[LINKING_PREPROCESSING_DONE_FIELD] = firestore.SERVER_TIMESTAMP
            logger.info(f"Successfully performed linking preprocessing for promise ID: {promise_id}. Keywords: {len(extracted_keywords)}, Action Type: {implied_action_type}")
        else:
            logger.info(f"Skipping linking preprocessing for {promise_id} (already done or not forced).")


        if update_payload:
            update_payload['last_updated_at'] = firestore.SERVER_TIMESTAMP
            await asyncio.to_thread(doc_ref.update, update_payload)
            logger.info(f"Firestore document updated for promise ID: {promise_id} with fields: {list(update_payload.keys())}")
            made_changes = True
        
        return made_changes

    except Exception as e:
        logger.error(f"Error processing promise ID {promise_id}: {e}", exc_info=True)
        return False


async def run_batch_processing(limit: int | None, force_reprocessing: bool):
    """Queries for promises needing processing and handles them in batch."""
    logger.info(f"Starting batch processing. Limit: {limit}, Force Reprocessing: {force_reprocessing}")
    
    promises_ref = db.collection(PROMISES_COLLECTION)
    base_query = promises_ref

    # Constructing a query to find documents that need *either* type of processing,
    # or all if force_reprocessing. This is complex with OR conditions in Firestore.
    # A simpler approach for batch is to fetch and then check conditions in code,
    # or run two separate queries if strictness is needed.
    # For now, let's fetch based on a general marker or just iterate if force_reprocessing.
    # If not forcing, it's tricky. Let's fetch documents and decide in code.
    # This means we might fetch more than needed if not force_reprocessing.
    # A better way: query for docs missing field A, then query for docs missing field B.
    # Or, have a single "needs_enrichment_v2" flag.

    # Simpler: Iterate and let `process_promise` decide based on `force_reprocessing` and field existence.
    # The query below just gets documents, optionally limited.
    
    query = base_query
    if limit is not None:
        query = query.limit(limit)
        logger.info(f"Query limited to {limit} documents.")
    else:
        logger.info("No limit applied to document query (will process all found or up to internal Firestore limits per batch if not paginating).")


    docs_snapshot = await asyncio.to_thread(query.stream) # stream() for iterator

    processed_count = 0
    updated_count = 0
    error_in_batch_flag = False

    doc_list = list(docs_snapshot) # Convert stream to list to know total
    total_to_consider = len(doc_list)
    logger.info(f"Found {total_to_consider} documents to consider based on query (limit: {limit}).")


    for i, doc_snapshot in enumerate(doc_list):
        logger.info(f"--- Processing document {i+1} of {total_to_consider} (ID: {doc_snapshot.id}) ---")
        try:
            updated = await process_promise(doc_snapshot.id, force_reprocessing)
            if updated:
                updated_count += 1
            processed_count += 1
        except Exception as e:
            logger.error(f"Critical error processing promise ID {doc_snapshot.id} in batch: {e}", exc_info=True)
            error_in_batch_flag = True # Mark that an error occurred
        
        # Rate limiting between processing of individual promises
        if i < total_to_consider - 1: # Don't sleep after the last one
            logger.debug(f"Waiting {RATE_LIMIT_DELAY_SECONDS}s before next promise...")
            await asyncio.sleep(RATE_LIMIT_DELAY_SECONDS)

    logger.info("--- Batch Processing Summary ---")
    logger.info(f"Documents considered for processing: {processed_count} (out of {total_to_consider} found by query)")
    logger.info(f"Documents successfully updated/processed: {updated_count}")
    if error_in_batch_flag:
        logger.warning("One or more errors occurred during batch processing. Check logs above.")
    logger.info("--- Batch Processing Complete ---")


async def main_async_entrypoint():
    parser = argparse.ArgumentParser(description='Enrich and preprocess Firestore promise documents.')
    parser.add_argument(
        '--promise_id',
        type=str,
        default=None,
        help='Specific promise ID to process. If not provided, runs in batch mode.'
    )
    parser.add_argument(
        '--limit',
        type=int,
        default=None, # Default to no limit for batch mode, user can specify
        help='Limit the number of documents to process in batch mode. No effect if --promise_id is set.'
    )
    parser.add_argument(
        '--force',
        action='store_true',
        help='Force reprocessing of all fields, even if they already exist.'
    )
    args = parser.parse_args()

    logger.info("--- Starting Promise Enrichment & Preprocessing Script ---")
    if args.promise_id:
        logger.info(f"Mode: Single Promise Processing for ID: {args.promise_id}")
        await process_promise(args.promise_id, args.force)
    else:
        logger.info(f"Mode: Batch Processing. Limit: {args.limit}, Force: {args.force}")
        await run_batch_processing(limit=args.limit, force_reprocessing=args.force)
    
    logger.info("--- Promise Enrichment & Preprocessing Script Finished ---")

if __name__ == "__main__":
    asyncio.run(main_async_entrypoint())  