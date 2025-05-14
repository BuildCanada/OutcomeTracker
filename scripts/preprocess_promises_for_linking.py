# This script preprocesses promises for linking by extracting keywords and action types using LLM. It will take approximately X minutes to process Y promises.
#!/usr/bin/env python
# scripts/preprocess_promises_for_linking.py

import firebase_admin
from firebase_admin import firestore, credentials
import os
import argparse
import logging
from datetime import datetime, timezone
from dotenv import load_dotenv
import time # For potential rate limiting if calling LLM rapidly
import json # For parsing LLM responses

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
db = None
if not firebase_admin._apps:
    try:
        firebase_admin.initialize_app()
        project_id = os.getenv('FIREBASE_PROJECT_ID', '[Not Set - Using Default]')
        logger.info(f"Python (Preprocess Promises): Connected to CLOUD Firestore (Project: {project_id}).")
        db = firestore.client()
    except Exception as e_default:
        logger.warning(f"Cloud Firestore init with default creds failed: {e_default}")
        cred_path = os.getenv('FIREBASE_SERVICE_ACCOUNT_KEY_PATH')
        if cred_path:
            try:
                logger.info(f"Attempting Firebase init with service account key: {cred_path}")
                cred = credentials.Certificate(cred_path)
                firebase_admin.initialize_app(cred)
                project_id = os.getenv('FIREBASE_PROJECT_ID', '[Not Set - Using Service Account]')
                logger.info(f"Python (Preprocess Promises): Connected to CLOUD Firestore (Project: {project_id}) via service account.")
                db = firestore.client()
            except Exception as e_sa:
                logger.critical(f"Firebase init with service account key failed: {e_sa}", exc_info=True)
                db = None
        else:
            db = None

if db is None:
    logger.critical("Failed to obtain Firestore client. Exiting.")
    exit("Exiting: Firestore client not available.")
# --- End Firebase Configuration ---

# --- LLM Configuration ---
gemini_model = None # Initialize gemini_model to None by default
try:
    import google.generativeai as genai
    GEMINI_API_KEY = os.getenv("GEMINI_API_KEY") 
    if not GEMINI_API_KEY:
        logger.critical("GOOGLE_API_KEY environment variable not set. LLM calls will fail.")
        # gemini_model remains None, which is intended if API key is missing
    else:
        genai.configure(api_key=GEMINI_API_KEY)
        llm_model_name = "gemini-2.0-flash" 
        logger.info(f"Using Gemini model: {llm_model_name}")
        gemini_model = genai.GenerativeModel(llm_model_name)
except ImportError:
    logger.critical("google.generativeai library not found. Please install it: pip install google-generativeai")
    # gemini_model remains None (or explicitly set it again if you prefer, though already None)
    gemini_model = None 
except Exception as e:
    logger.critical(f"Error initializing Gemini model: {e}", exc_info=True)
    gemini_model = None # Ensure it's None on other exceptions too

# Re-adding ACTION_TYPES_LIST here
ACTION_TYPES_LIST = [
    "legislative", 
    "funding_allocation", 
    "policy_development", 
    "program_launch", 
    "consultation", 
    "international_agreement", 
    "appointment", 
    "other"
]

def call_gemini_for_keywords(promise_text):
    """
    Calls Gemini API to extract keywords.
    """
    if not gemini_model:
        logger.error("Gemini model not initialized. Skipping keyword extraction.")
        return ["placeholder_keyword1_model_error", "placeholder_keyword2_model_error"]

    prompt = f"""From the {promise_text}, extract a list of 5-10 key nouns and specific named entities (like program names or specific laws mentioned) that represent the core subjects, objects, and significant concepts of this promise. Output as a JSON list of strings only, with no other text before or after the JSON list."""
    logger.info(f"Attempting to extract keywords for promise text (first 50 chars): '{promise_text[:50]}...'")
    
    try:
        response = gemini_model.generate_content(prompt)
        # Clean the response text to ensure it's valid JSON
        # Models can sometimes add ```json ... ``` or other markdown
        cleaned_response_text = response.text.strip()
        if cleaned_response_text.startswith("```json"):
            cleaned_response_text = cleaned_response_text[7:]
        if cleaned_response_text.endswith("```"):
            cleaned_response_text = cleaned_response_text[:-3]
        
        keywords = json.loads(cleaned_response_text.strip())
        if isinstance(keywords, list) and all(isinstance(k, str) for k in keywords):
            logger.info(f"Extracted keywords: {keywords}")
            return keywords
        else:
            logger.warning(f"Gemini keyword extraction did not return a valid list of strings. Response: {response.text}")
            return []
    except json.JSONDecodeError as e:
        logger.error(f"Error decoding JSON from Gemini keyword response: {e}. Response text: {response.text if 'response' in locals() else 'N/A'}", exc_info=True)
        return []
    except Exception as e:
        logger.error(f"Error calling Gemini for keyword extraction: {e}", exc_info=True)
        return []

def call_gemini_for_action_type(promise_text):
    """
    Calls Gemini API to infer action type.
    """
    if not gemini_model:
        logger.error("Gemini model not initialized. Skipping action type inference.")
        return "other"

    action_types_string = ", ".join(ACTION_TYPES_LIST)
    prompt = f"""Analyze the following government promise: '{promise_text}'. What is the primary type of action being committed to? Choose one from the following list: [{action_types_string}]. Output only the chosen type string, with no other text before or after it."""
    logger.info(f"Attempting to infer action type for promise text (first 50 chars): '{promise_text[:50]}...'")
    
    try:
        response = gemini_model.generate_content(prompt)
        action_type = response.text.strip()
        
        if action_type in ACTION_TYPES_LIST:
            logger.info(f"Inferred action type: {action_type}")
            return action_type
        else:
            # Attempt to find a match even if there's extra content, e.g. "The action type is: legislative"
            for valid_type in ACTION_TYPES_LIST:
                if valid_type in action_type:
                    logger.warning(f"Found valid action type '{valid_type}' within a longer response: '{action_type}'. Using '{valid_type}'.")
                    return valid_type
            logger.warning(f"Gemini action type classification returned an unknown or badly formatted type: '{action_type}'. Defaulting to 'other'.")
            return "other"
    except Exception as e:
        logger.error(f"Error calling Gemini for action type classification: {e}", exc_info=True)
        return "other" # Default to 'other' on error

def preprocess_promises(collection_name, batch_size=50, force_reprocessing=False):
    """
    Iterates through promise documents, extracts keywords and action types using LLM,
    and updates them in Firestore.
    """
    if not gemini_model:
        logger.critical("Gemini model is not available. Cannot proceed with preprocessing.")
        return

    logger.info(f"Starting preprocessing for collection '{collection_name}'. Force reprocessing: {force_reprocessing}")
    promises_ref = db.collection(collection_name)
    processed_count = 0
    updated_count = 0
    skipped_count = 0 # For documents already processed

    # Fetch documents in batches
    last_snapshot = None
    while True:
        query = promises_ref.order_by("__name__").limit(batch_size)
        if last_snapshot:
            query = query.start_after(last_snapshot)
        
        docs_batch = list(query.stream())
        if not docs_batch:
            break # No more documents

        logger.info(f"Processing batch of {len(docs_batch)} documents...")
        
        firestore_batch = db.batch()
        docs_in_current_firestore_batch = 0

        for doc_snapshot in docs_batch:
            processed_count += 1
            promise_id = doc_snapshot.id
            promise_data = doc_snapshot.to_dict()
            promise_text = promise_data.get('text')

            if not promise_text:
                logger.warning(f"Promise {promise_id} has no 'text' field. Skipping.")
                skipped_count += 1
                continue

            if not force_reprocessing and promise_data.get('linking_preprocessing_done_at'):
                # logger.info(f"Promise {promise_id} already preprocessed on {promise_data['linking_preprocessing_done_at']}. Skipping.")
                skipped_count +=1
                continue

            # --- Call LLM for keywords and action type ---
            # Add a small delay to avoid hitting API rate limits if processing many docs quickly
            time.sleep(1) # Adjust as needed based on API limits and batch size
            extracted_keywords = call_gemini_for_keywords(promise_text)
            
            time.sleep(1) # Delay before next call
            implied_action_type = call_gemini_for_action_type(promise_text)
            # --- End LLM Call ---

            update_data = {
                'extracted_keywords_concepts': extracted_keywords,
                'implied_action_type': implied_action_type,
                'linking_preprocessing_done_at': firestore.SERVER_TIMESTAMP
            }

            doc_ref = promises_ref.document(promise_id)
            firestore_batch.update(doc_ref, update_data)
            docs_in_current_firestore_batch += 1
            updated_count += 1
            
            if docs_in_current_firestore_batch >= 400: # Commit Firestore batch
                logger.info(f"Committing Firestore batch of {docs_in_current_firestore_batch} updates...")
                firestore_batch.commit()
                firestore_batch = db.batch() # Start new batch
                docs_in_current_firestore_batch = 0
                logger.info(f"Processed {processed_count} documents so far. Updated: {updated_count}, Skipped: {skipped_count}.")


        if docs_in_current_firestore_batch > 0: # Commit any remaining updates in the current document batch
            logger.info(f"Committing final Firestore batch of {docs_in_current_firestore_batch} updates for this document batch...")
            firestore_batch.commit()
            # firestore_batch = db.batch() # Reset for next iteration - not strictly needed here as it's end of doc batch processing.

        last_snapshot = docs_batch[-1] # For pagination
        logger.info(f"Completed processing {processed_count} documents so far. Updated: {updated_count}, Skipped: {skipped_count}.")
        if len(docs_batch) < batch_size: # Last batch
            break
            
    logger.info(f"Preprocessing finished for collection '{collection_name}'.")
    logger.info(f"Total documents processed: {processed_count}")
    logger.info(f"Total documents updated: {updated_count}")
    logger.info(f"Total documents skipped (already processed or no text): {skipped_count}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Preprocess promise documents in Firestore for linking.")
    parser.add_argument("collection_name", 
                        default="promises",
                        type=str,
                        help="Name of the Firestore collection to preprocess (default: promises).")
    parser.add_argument("--force",
                        action="store_true",
                        help="Force reprocessing of all documents, even if 'linking_preprocessing_done_at' is set.")
    parser.add_argument("--batch_size",
                        type=int,
                        default=50,
                        help="Number of documents to fetch and process in each batch (default: 50).")
    
    args = parser.parse_args()

    logger.info(f"--- Starting Promise Preprocessing Utility for Linking ---")
    logger.info(f"Target Collection: {args.collection_name}")
    logger.info(f"Force Reprocessing: {args.force}")
    logger.info(f"Batch Size: {args.batch_size}")

    preprocess_promises(args.collection_name, batch_size=args.batch_size, force_reprocessing=args.force)

    logger.info(f"--- Promise Preprocessing Utility Finished ---") 