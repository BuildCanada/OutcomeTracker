# scripts/enrich_promises_llm.py

import firebase_admin
from firebase_admin import firestore
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

# --- Load Environment Variables ---
load_dotenv()
# --- End Load Environment Variables ---

# --- Logger Setup ---
logging.basicConfig(level=logging.INFO,
                    format='%(asctime)s - %(levelname)s - %(filename)s:%(lineno)d - %(message)s',
                    datefmt='%Y-%m-%d %H:%M:%S')
logger = logging.getLogger(__name__)
# --- End Logger Setup ---

# --- Firebase Configuration (Cloud Focused) ---
db = None
if not firebase_admin._apps:
    # This script is intended for Cloud Firestore.
    # Ensure GOOGLE_APPLICATION_CREDENTIALS is set.
    if not os.getenv('GOOGLE_APPLICATION_CREDENTIALS'):
        logger.critical("CRITICAL: GOOGLE_APPLICATION_CREDENTIALS environment variable not set.")
        logger.critical("This script requires credentials for Google Cloud Firestore.")
        exit("Exiting: GOOGLE_APPLICATION_CREDENTIALS not set.")
    try:
        firebase_admin.initialize_app() # Default initialization uses GOOGLE_APPLICATION_CREDENTIALS
        project_id = os.getenv('FIREBASE_PROJECT_ID', '[Not Set]') # Get project ID if available for logging
        logger.info(f"Python (Enrich Promises): Connected to CLOUD Firestore using Application Default Credentials (Project: {project_id}).")
        db = firestore.client()
    except Exception as e:
        logger.critical(f"Python (Enrich Promises): Firebase initialization failed for Google Cloud Firestore: {e}", exc_info=True)
        exit("Exiting: Firebase connection failed.")
else:
    logger.info("Python (Enrich Promises): Firebase app already initialized. Getting client.")
    db = firestore.client()

if db is None:
    logger.critical("CRITICAL: Python (Enrich Promises): Failed to obtain Firestore client. Exiting.")
    exit("Exiting: Firestore client not available.")
# --- End Firebase Configuration ---

# --- Gemini Configuration ---
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
if not GEMINI_API_KEY:
    logger.critical("GEMINI_API_KEY not found in environment variables or .env file.")
    exit("Exiting: Missing GEMINI_API_KEY.")
genai.configure(api_key=GEMINI_API_KEY)

# Configure the model name and generation settings as needed
MODEL_NAME = "models/gemini-2.5-flash-preview-04-17" # Or your preferred model
GENERATION_CONFIG = {
    "temperature": 0.2,
    "top_p": 0.95,
    "top_k": 64,
    "max_output_tokens": 65536,
    "response_mime_type": "application/json",
}

SYSTEM_INSTRUCTION = """You are a meticulous AI research assistant specializing in Canadian federal government policy and history.
Your task is to analyze Canadian government commitments and construct a factual timeline of key preceding events.
These events include policies, legislative actions, official announcements, significant public reports, or court decisions that directly contributed to or motivated the specific commitment.
For each timeline entry, you MUST provide:
1. The exact date (formatted as YYYY-MM-DD) of its publication, announcement, or decision.
2. A concise description of the 'Action' or event that is 30 words or less.
3. A verifiable 'Source URL' pointing to an official government document, parliamentary record, press release, or a reputable news article about the event.
Focus only on concrete, verifiable federal-level events that *preceded* the commitment date.
Return no more than four of the most directly impactful and relevant preceding events. Present events chronologically.
"""

# Initialize the Generative Model
try:
    model = genai.GenerativeModel(
        model_name=MODEL_NAME,
        generation_config=GENERATION_CONFIG,
        system_instruction=SYSTEM_INSTRUCTION
    )
    logger.info(f"Initialized Gemini model: {MODEL_NAME}")
except Exception as e:
    logger.critical(f"Failed to initialize Gemini model '{MODEL_NAME}': {e}", exc_info=True)
    exit("Exiting: Gemini model initialization failed.")
# --- End Gemini Configuration ---

# --- Constants ---
PROMISES_COLLECTION = 'promises'
FIELD_TO_POPULATE = 'commitment_history_rationale'
PROCESSING_LIMIT = 10 # Limit the number of documents processed per run (set to None for all)
RATE_LIMIT_DELAY = 2 # Seconds to wait between Gemini API calls
# --- End Constants ---

async def generate_history_rationale(promise_text: str, source_type: str, entity: str, date_issued: str):
    """Generates a timeline of preceding events using Gemini, requesting JSON output and parsing it."""
    logger.debug(f"Generating timeline for promise: {promise_text[:100]}...")

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
*   Format: A valid JSON array of objects, containing **2 to 4** timeline event objects. If fewer than 2 truly relevant preceding events are found, return only those found. If none, return an empty array `[]`.
*   Object Structure: Each object MUST contain the keys "date" (string, "YYYY-MM-DD"), "action" (string), and "source_url" (string).
*   Content: Focus only on concrete, verifiable federal-level events.
*   Chronology: Present timeline events chronologically (earliest first), all preceding the 'Date Commitment Announced' ({date_issued_str}).

Example JSON Output (should be an array of objects like this, with 2-4 items):
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
  // Potentially 1 or 2 more items if highly relevant
]
```

Generate ONLY the JSON array. If no specific preceding events are found that meet the relevance criteria, return an empty JSON array []."""

    try:
        response = await model.generate_content_async(prompt)
        try:
            json_string = response.text.strip()
            if json_string.startswith('```json'):
                json_string = json_string[7:].strip()
            if json_string.endswith('```'):
                json_string = json_string[:-3].strip()

            timeline_events = json.loads(json_string)

            if not isinstance(timeline_events, list):
                logger.warning(f"LLM response was not a JSON list for promise: {promise_text[:100]}. Response: {json_string}")
                return None
            
            # Allow an empty list as a valid response (0 events found)
            if not timeline_events: # If the list is empty
                logger.debug(f"LLM returned an empty list, indicating no relevant preceding events found for promise: {promise_text[:100]}.")
                return [] # Return the empty list

            # Validate list length (now 1 to 4, as 0 is handled above)
            if not (1 <= len(timeline_events) <= 4):
                logger.warning(f"LLM response list length ({len(timeline_events)}) is not within the expected 1-4 range for promise: {promise_text[:100]}. Response: {json_string}")
                return None

            validated_events = []
            for i, event in enumerate(timeline_events):
                valid_event = True # Assume valid until a check fails
                if not isinstance(event, dict):
                    logger.warning(f"Event {i} is not a dictionary. Promise: {promise_text[:100]}. Event: {event}")
                    valid_event = False
                
                if valid_event and not all(key in event for key in ["date", "action", "source_url"]):
                    logger.warning(f"Event {i} missing required keys ('date', 'action', 'source_url'). Promise: {promise_text[:100]}. Event: {event}")
                    valid_event = False
                
                if valid_event and not isinstance(event.get("date"), str):
                    logger.warning(f"Event {i} 'date' is not a string. Promise: {promise_text[:100]}. Event: {event}")
                    valid_event = False
                
                if valid_event and not isinstance(event.get("action"), str):
                    logger.warning(f"Event {i} 'action' is not a string. Promise: {promise_text[:100]}. Event: {event}")
                    valid_event = False
                
                if valid_event and not isinstance(event.get("source_url"), str):
                    logger.warning(f"Event {i} 'source_url' is not a string. Promise: {promise_text[:100]}. Event: {event}")
                    valid_event = False
                
                # Check date format only if it's confirmed to be a string
                if valid_event and isinstance(event.get("date"), str) and not re.match(r"^\d{4}-\d{2}-\d{2}$", event["date"]):
                    logger.warning(f"Event {i} 'date' format is invalid (expected YYYY-MM-DD). Promise: {promise_text[:100]}. Event: {event}")
                    valid_event = False

                if valid_event:
                    validated_events.append(event)
                else:
                    logger.warning(f"Invalid event structure in LLM response for promise: {promise_text[:100]}. Event {i}: {event}. Full response: {json_string}")
                    return None # One bad event invalidates all
            
            logger.debug(f"Successfully parsed timeline: {validated_events}")
            return validated_events

        except json.JSONDecodeError as json_err:
            logger.warning(f"LLM response was not valid JSON for promise: {promise_text[:100]}. Error: {json_err}. Response: \n{response.text}")
            return None
        except Exception as parse_err:
            logger.error(f"Error parsing LLM JSON response: {parse_err}", exc_info=True)
            return None

    except Exception as e:
        logger.error(f"Error calling Gemini API for timeline generation: {e}", exc_info=True)
        return None

async def main_async(overwrite: bool = False, limit_arg: int | None = None):
    """Fetches promises missing the rationale (or all if overwrite=True) and populates it using an LLM."""
    logger.info(f"Starting promise enrichment process for field '{FIELD_TO_POPULATE}'.")
    if overwrite:
        logger.info("Overwrite mode enabled: Existing rationales will be regenerated.")
    else:
        logger.info("Overwrite mode disabled: Only processing promises with missing rationales.")

    processed_count = 0
    updated_count = 0
    error_count = 0

    # Query for documents where the target field is null AND source type is Mandate Letter
    # OR query for ALL mandate letters if overwrite is True
    base_query = db.collection(PROMISES_COLLECTION).where(filter=firestore.FieldFilter('source_type', '==', 'Mandate Letter Commitment (Structured))')

    if not overwrite:
        query = base_query.where(FIELD_TO_POPULATE, '==', None)
        logger.info(f"Querying for documents where '{FIELD_TO_POPULATE}' is null.")
    else:
        query = base_query # Query all documents matching the source type
        logger.info("Querying for all documents with source type 'Mandate Letter Commitment (Structured)'.")

    # Apply the limit if provided via command line argument
    if limit_arg is not None:
        query = query.limit(limit_arg)
        logger.info(f"Processing limit set to {limit_arg} documents via --limit argument.")
    elif PROCESSING_LIMIT is not None: # Fallback to constant if --limit not used
        query = query.limit(PROCESSING_LIMIT)
        logger.info(f"Processing limit set to {PROCESSING_LIMIT} documents via constant (use --limit to override).")

    try:
        # Convert stream to a list to process asynchronously with controlled concurrency if needed
        # For now, processing sequentially with a delay
        docs_snapshot = await asyncio.to_thread(query.get) # Use to_thread for sync SDK call in async context

        for doc in docs_snapshot:
            processed_count += 1
            promise_id = doc.id
            promise_data = doc.to_dict()
            logger.info(f"Processing promise ID: {promise_id}")

            promise_text = promise_data.get('text')
            source_type = promise_data.get('source_type')
            entity = promise_data.get('candidate_or_government')
            date_issued = promise_data.get('date_issued')

            if not promise_text:
                logger.warning(f"Skipping promise ID {promise_id} due to missing 'text' field.")
                continue

            rationale = await generate_history_rationale(promise_text, source_type, entity, date_issued)

            if rationale:
                try:
                    doc_ref = db.collection(PROMISES_COLLECTION).document(promise_id)
                    # Firestore client library for Python is synchronous, direct await won't work on update.
                    # If true async firestore operations are needed, consider google-cloud-firestore-async library
                    # For now, running update synchronously or wrapping in to_thread if it becomes a bottleneck.
                    doc_ref.update({FIELD_TO_POPULATE: rationale, 'last_updated_at': firestore.SERVER_TIMESTAMP})
                    logger.info(f"Successfully updated rationale for promise ID: {promise_id}")
                    updated_count += 1
                except Exception as e:
                    logger.error(f"Failed to update Firestore for promise ID {promise_id}: {e}", exc_info=True)
                    error_count += 1
            else:
                logger.warning(f"Failed to generate rationale for promise ID {promise_id}. Skipping update.")
                error_count += 1

            await asyncio.sleep(RATE_LIMIT_DELAY)

    except Exception as e:
        logger.error(f"An error occurred during the Firestore query or processing loop: {e}", exc_info=True)
        error_count += 1

    logger.info("--- Promise Enrichment Complete ---")
    logger.info(f"Documents considered: {processed_count}")
    logger.info(f"Documents successfully updated: {updated_count}")
    logger.info(f"Errors encountered (incl. generation failures): {error_count}")

if __name__ == "__main__":
    # --- Argument Parsing ---
    parser = argparse.ArgumentParser(description='Enrich Firestore promises with LLM-generated history rationale.')
    parser.add_argument(
        '--overwrite',
        action='store_true',
        help='If set, overwrite existing rationale fields. Otherwise, only process documents where the rationale is missing.'
    )
    parser.add_argument(
        '--limit',
        type=int,
        default=None,
        help='Limit the number of documents to process. Overrides the PROCESSING_LIMIT constant.'
    )
    args = parser.parse_args()
    # --- End Argument Parsing ---

    logger.info("Running LLM Promise Enrichment Script...")
    # Pass the overwrite flag and the limit argument to main_async
    asyncio.run(main_async(overwrite=args.overwrite, limit_arg=args.limit))
    logger.info("Script finished.")