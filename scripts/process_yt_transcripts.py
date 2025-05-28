# scripts/process_transcripts_gemini.py

import firebase_admin
from firebase_admin import firestore
import os
import google.generativeai as genai
import time
import asyncio
import json # For parsing LLM response
import uuid # For generating unique promise IDs
import logging
import traceback
from dotenv import load_dotenv
import argparse # Added for CLI arguments
from common_utils import PROMISE_CATEGORIES, get_promise_document_path_flat, DEFAULT_REGION_CODE, PARTY_NAME_TO_CODE_MAPPING 
from datetime import datetime, date # ADDED date

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
# (Same connection logic as other scripts, ensure it checks for EMULATOR_HOST first)
db = None 
if not firebase_admin._apps:
    if os.getenv('FIRESTORE_EMULATOR_HOST'):
        options = {'projectId': os.getenv('FIREBASE_PROJECT_ID', 'promisetrackerapp')}
        try:
             firebase_admin.initialize_app(options=options)
             logger.info(f"Python (YT Process): Connected to Firestore Emulator at {os.getenv('FIRESTORE_EMULATOR_HOST')} using project ID '{options['projectId']}'")
             db = firestore.client()
        except Exception as e:
             logger.critical(f"Firebase init failed: {e}", exc_info=True)
             exit("Exiting: Firebase connection failed.")
    else:
        # Connect to Cloud - ensure GOOGLE_APPLICATION_CREDENTIALS is set
        try:
            firebase_admin.initialize_app() 
            project_id = os.getenv('FIREBASE_PROJECT_ID', '[Not Set]') # Get project ID if available for logging
            logger.info(f"Python (YT Process): Connected to CLOUD Firestore using Application Default Credentials (Project: {project_id}).")
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


# --- Gemini Configuration ---
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
if not GEMINI_API_KEY:
    logger.critical("GEMINI_API_KEY not found in environment variables or .env file.")
    exit("Exiting: Missing GEMINI_API_KEY.")
genai.configure(api_key=GEMINI_API_KEY)

MODEL_NAME = "models/gemini-2.5-flash-preview-04-17" 

GENERATION_CONFIG = {
    "temperature": 0.6, # Slightly lower temp for more deterministic extraction
    "top_p": 0.95,
    "top_k": 64,
    "max_output_tokens": 65536, 
    "response_mime_type": "application/json", # Request JSON output
}

# Initialize the Generative Model
try:
    model = genai.GenerativeModel(
        model_name=MODEL_NAME,
        generation_config=GENERATION_CONFIG
    )
    logger.info(f"Initialized Gemini model: {MODEL_NAME}")
except Exception as e:
    logger.critical(f"Failed to initialize Gemini model '{MODEL_NAME}': {e}", exc_info=True)
    exit("Exiting: Gemini model initialization failed.")
# --- End Gemini Configuration ---

# --- Constants ---
# Define categories for the LLM prompt
# PROMISE_CATEGORIES = [
#     "Economy", "Healthcare", "Immigration", "Defence", "Housing", 
#     "Cost of Living", "Environment", "Social Programs", "Governance", 
#     "Indigenous Relations", "Foreign Affairs", "Infrastructure", "Other" 
# ]
# Firestore collection to write promises to
# PROMISES_COLLECTION = 'promises' # <<< OLD WAY: Commented out, will use TARGET_PROMISES_COLLECTION_ROOT
# Field to check/update in youtube_video_data to track processing
PROCESSING_FLAG_FIELD = 'llm_promise_extraction_processed_at' 
# PROCESSING_LIMIT = 5 # Set to None to process all unprocessed # Replaced by CLI arg
# Max characters of transcript to send to LLM (adjust based on token limits / performance)
MAX_TRANSCRIPT_CHARS = 800000 # Approx 200k tokens, increased from 30000
# --- End Constants ---


def infer_candidate_party(video_data):
    """Infers candidate name and party from video metadata (best effort for 2021)."""
    title = video_data.get('title', '').lower()
    uploader = video_data.get('uploader', '').lower()
    description = video_data.get('description', '').lower()
    search_text = f"{title} {uploader} {description}"

    # Simple keyword matching - Needs refinement for accuracy
    if 'trudeau' in search_text or 'liberal party' in search_text:
        return "Justin Trudeau", "Liberal Party of Canada"
    elif "o'toole" in search_text or 'conservative party' in search_text:
         return "Erin O'Toole", "Conservative Party of Canada"
    elif 'jagmeet singh' in search_text or 'ndp' in search_text or 'new democratic party' in search_text:
         return "Jagmeet Singh", "New Democratic Party"
    elif 'yves-francois blanchet' in search_text or 'yves francois blanchet' in search_text or 'bloc quebecois' in search_text or 'bloc québécois' in search_text:
         return "Yves-Francois Blanchet", "Bloc Québécois"
    elif 'annamie paul' in search_text or 'green party' in search_text:
        return "Annamie Paul", "Green Party of Canada"
    
    # Fallback if no clear match
    logger.warning(f"Could not reliably infer candidate/party for video {video_data.get('video_id')}. Title: '{video_data.get('title')}'. Uploader: '{video_data.get('uploader')}'.")
    return video_data.get('uploader', 'Unknown Candidate'), "Unknown Party" # Default


def build_gemini_prompt(transcript_text, video_title, video_date, candidate_info, categories):
    """Builds the prompt for Gemini, requesting JSON output."""
    # Truncate transcript if too long
    if len(transcript_text) > MAX_TRANSCRIPT_CHARS:
        logger.warning(f"Transcript too long ({len(transcript_text)} chars), truncating to {MAX_TRANSCRIPT_CHARS}.")
        transcript_text = transcript_text[:MAX_TRANSCRIPT_CHARS] + "\n... [TRUNCATED]"

    # Prompt structure requesting JSON list
    prompt = f"""
CONTEXT: You are an expert assistant analyzing Canadian political campaign video transcripts from the 2021 federal election to identify specific, actionable promises made by political candidates. Focus ONLY on concrete commitments to take specific actions, implement policies, spend funds, or achieve measurable outcomes. Ignore general statements of values, criticisms of opponents, descriptions of past actions (unless directly linked to a future promise), and vague aspirations.

VIDEO METADATA:
- Title: "{video_title}"
- Date: {video_date}
- Speaker (if known): {candidate_info}

AVAILABLE CATEGORIES FOR PROMISES:
{", ".join(categories)}

INSTRUCTIONS:
1. Carefully read the following transcript.
2. Identify all distinct, actionable promises made by the speaker.
3. For EACH promise identified, provide the following information within a JSON object:
   - "promise_summary": A concise summary title for the promise (e.g., "Increase Minimum Wage", "Build 1 Million Homes", "Cut Carbon Emissions by 40%"). Use title case. Max 15 words.
   - "promise_details_extracted": The direct quote(s) or key phrases from the transcript that constitute the promise. Be specific.
   - "key_points": A JSON list of 2-4 strings, where each string is a bullet point elaborating on the promise's specifics, targets, or mechanisms mentioned in the transcript.
   - "category": The single most relevant category from the AVAILABLE CATEGORIES list provided above.
   - "timestamp_cue_raw": Provide distinct phrases immediately surrounding the core promise text in the transcript. This helps locate the promise. E.g., "...will invest $5 billion to build..."

4. Structure your entire output as a single JSON list containing one object for each promise identified.
5. If no specific, actionable promises are identified in the transcript, return an empty JSON list: []

TRANSCRIPT:
\"\"\"
{transcript_text}
\"\"\"

JSON OUTPUT:
"""
    return prompt


async def process_single_video_transcript(video_doc_snapshot):
    """Processes one video document: extracts promises via LLM and saves them to the new hierarchical structure."""
    video_id = video_doc_snapshot.id
    video_data = video_doc_snapshot.to_dict()
    logger.info(f"Processing video transcript for ID: {video_id} (Title: {video_data.get('title', 'N/A')})")

    # Determine Parliament Session ID from video upload date
    determined_session_id = None
    upload_date_str_yyyymmdd = video_data.get('upload_date') # Expected format YYYYMMDD
    upload_date_obj = None
    formatted_upload_date_for_path = None # YYYY-MM-DD for path generation

    if upload_date_str_yyyymmdd:
        try:
            upload_date_obj = datetime.strptime(upload_date_str_yyyymmdd, "%Y%m%d").date()
            formatted_upload_date_for_path = upload_date_obj.strftime("%Y-%m-%d")
            determined_session_id = get_parliament_session_for_date(upload_date_obj)
            logger.info(f"Determined session ID '{determined_session_id}' for video {video_id} with upload date {formatted_upload_date_for_path}")
        except ValueError:
            logger.warning(f"Invalid upload_date format for video {video_id}: {upload_date_str_yyyymmdd}. Cannot determine session ID by date or use for promise path. Will use default session ID.")
            determined_session_id = get_parliament_session_for_date(None)
    else:
        logger.warning(f"Missing upload_date for video {video_id}. Cannot determine session ID by date or use for promise path. Will use default session ID.")
        determined_session_id = get_parliament_session_for_date(None)

    # 1. Select English Transcript
    transcript_to_process = None
    if video_data.get('transcript_en_translated'):
        transcript_to_process = video_data['transcript_en_translated']
        logger.info(f"  Using translated English transcript for {video_id}.")
    elif video_data.get('transcript_text_generated'):
        transcript_to_process = video_data['transcript_text_generated']
        logger.info(f"  Using original generated English transcript for {video_id}.")
    
    if not transcript_to_process or not transcript_to_process.strip():
        logger.warning(f"  No usable English transcript found for {video_id}. Skipping promise extraction.")
        doc_ref = db.collection('youtube_video_data').document(video_id)
        update_data_yt_video = {
            PROCESSING_FLAG_FIELD: firestore.SERVER_TIMESTAMP, 
            'promise_extraction_status': 'skipped_no_transcript'
        }
        if determined_session_id: # Save session ID even if skipping promise extraction
            update_data_yt_video['parliament_session_id'] = determined_session_id
        doc_ref.update(update_data_yt_video)
        return 0 

    # 2. Infer Candidate/Party
    candidate_name, party_name = infer_candidate_party(video_data)
    candidate_info = f"{candidate_name} ({party_name})"

    # 3. Build Prompt
    prompt_upload_date_str = formatted_upload_date_for_path if formatted_upload_date_for_path else "Unknown Date"
        
    prompt = build_gemini_prompt(
        transcript_to_process,
        video_data.get('title', 'N/A'),
        prompt_upload_date_str, # Use YYYY-MM-DD formatted date
        candidate_info,
        PROMISE_CATEGORIES
    )

    # 4. Call Gemini API
    logger.debug(f"  Sending prompt to Gemini for {video_id}...")
    try:
        response = await model.generate_content_async(prompt)
        if not response.candidates or not response.candidates[0].content.parts:
             logger.warning(f"  Warning: No content parts in Gemini response for {video_id}")
             extracted_promises_json_str = "[]"
        else:
            extracted_promises_json_str = response.text 
        
        logger.debug(f"  Raw Gemini response text (first 500 chars): {extracted_promises_json_str[:500]}")
        
        extracted_promises = json.loads(extracted_promises_json_str)
    
    except json.JSONDecodeError as e_json:
        logger.error(f"  Error decoding JSON from Gemini for {video_id}: {e_json}")
        logger.error(f"  Problematic JSON string (first 1000 chars): {extracted_promises_json_str[:1000]}")
        # Update video status to reflect error
        db.collection('youtube_video_data').document(video_id).update({
            PROCESSING_FLAG_FIELD: firestore.SERVER_TIMESTAMP,
            'promise_extraction_status': f'error_json_decode: {str(e_json)[:100]}'
        })
        return 0 
    except Exception as e_gemini:
        logger.error(f"  Error calling Gemini API for {video_id}: {e_gemini}", exc_info=True)
        # Update video status
        db.collection('youtube_video_data').document(video_id).update({
            PROCESSING_FLAG_FIELD: firestore.SERVER_TIMESTAMP,
            'promise_extraction_status': f'error_gemini_api: {str(e_gemini)[:100]}'
        })
        return 0

    # 5. Prepare and Save Promises to Firestore (NEW LOGIC for path and ID)
    video_doc_ref = db.collection('youtube_video_data').document(video_id) # Ref to the video document for status update
    batch = db.batch()
    promises_added_count = 0
    
    source_type_for_promise = "Video Transcript (YouTube)" # Define source type for these promises

    if not extracted_promises:
        logger.info(f"  No promises extracted by LLM for {video_id}.")
    else:
        logger.info(f"  LLM extracted {len(extracted_promises)} potential promises for {video_id}. Preparing to save with new structure.")

        for promise_detail_from_llm in extracted_promises:
            try:
                text_for_hash = promise_detail_from_llm.get('promise_summary', '').strip()
                if not text_for_hash:
                    logger.warning(f"    Skipping a promise for {video_id} due to empty 'promise_summary' from LLM.")
                    continue
                
                if not party_name or party_name == "Unknown Party":
                    logger.warning(f"    Skipping a promise for {video_id} (summary: '{text_for_hash[:50]}...') due to unknown party.")
                    continue

                if not formatted_upload_date_for_path:
                    logger.warning(f"    Skipping a promise for {video_id} (summary: '{text_for_hash[:50]}...') due to missing formatted upload date for path generation.")
                    continue

                # Generate the new flat document path
                new_doc_full_path = get_promise_document_path_flat(
                    party_name_str=party_name,
                    date_issued_str=formatted_upload_date_for_path,
                    source_type_str=source_type_for_promise,
                    promise_text=text_for_hash, # Use summary for hashing
                    region_code=DEFAULT_REGION_CODE
                )

                if not new_doc_full_path:
                    logger.error(f"    Failed to generate document path for a promise from {video_id} (summary: '{text_for_hash[:50]}...'). Skipping this promise.")
                    continue
                
                leaf_id = new_doc_full_path.split("/")[-1]

                # Construct promise data for flat structure
                promise_data = {
                    'promise_id': leaf_id, # Store the deterministic leaf ID
                    'text': promise_detail_from_llm.get('promise_summary', 'N/A'), # Main text/summary
                    'promise_details_extracted': promise_detail_from_llm.get('promise_details_extracted'),
                    'key_points': promise_detail_from_llm.get('key_points'),
                    'category': promise_detail_from_llm.get('category'),
                    'llm_raw_timestamp_cue': promise_detail_from_llm.get('timestamp_cue_raw'), # From LLM

                    # Information from video_data
                    'source_type': source_type_for_promise,
                    'date_issued': formatted_upload_date_for_path, # Store YYYY-MM-DD
                    'party': party_name,
                    'candidate_or_government': candidate_name, # Specific candidate if known
                    
                    # Flat structure fields
                    'region_code': DEFAULT_REGION_CODE,
                    'party_code': PARTY_NAME_TO_CODE_MAPPING.get(party_name, 'UNK'),

                    'video_source_id': video_id,
                    'video_title': video_data.get('title', 'N/A'),
                    'video_uploader': video_data.get('uploader', 'N/A'),
                    'video_webpage_url': video_data.get('webpage_url'),
                    'video_upload_date_yyyymmdd': upload_date_str_yyyymmdd, # Original YYYYMMDD format

                    # Standard fields
                    'commitment_history_rationale': None,
                    'linked_evidence_ids': [],
                    'ingested_at': firestore.SERVER_TIMESTAMP,
                    'last_updated_at': firestore.SERVER_TIMESTAMP,
                    'parliament_session_id': determined_session_id,
                }

                new_promise_ref = db.document(new_doc_full_path)
                batch.set(new_promise_ref, promise_data, merge=True) # Use merge=True in case of re-processing same summary
                promises_added_count += 1
                logger.info(f"    Prepared promise for batch: {new_doc_full_path}")
            
            except Exception as e:
                 logger.error(f"  Error preparing promise data from LLM output for {video_id}: {e}\nPromise data from LLM: {promise_detail_from_llm}", exc_info=True)
                 # Continue to next promise if one fails

    # 6. Update video document status and commit batch (existing logic for batch commit)
    try:
        batch.update(video_doc_ref, { # video_doc_ref was defined before the loop
             PROCESSING_FLAG_FIELD: firestore.SERVER_TIMESTAMP,
             'promise_extraction_status': 'success' if promises_added_count > 0 or not extracted_promises else 'llm_extracted_none',
             'extracted_promise_count': promises_added_count,
             'processed_with_new_path_structure': True # Flag that this video was processed with new logic
        })
        batch.commit() 
        logger.info(f"  Successfully saved {promises_added_count} promises (new structure) and updated status for {video_id}.")
        return promises_added_count
    except Exception as e:
         logger.error(f"  Error committing Firestore batch for {video_id}: {e}", exc_info=True)
         try:
              video_doc_ref.update({
                   PROCESSING_FLAG_FIELD: firestore.SERVER_TIMESTAMP,
                   'promise_extraction_status': f'error_batch_commit_new_path: {str(e)[:100]}'
              })
         except Exception as update_err:
              logger.error(f"  Failed to even update error status for {video_id}: {update_err}")
         return 0


async def main_async_promises(limit_arg: int | None):
    """Main async function to fetch unprocessed videos and process them."""
    logger.info(f"Starting LLM promise extraction process... Processing limit: {limit_arg if limit_arg is not None else 'All'}")
    processed_videos_count = 0
    total_promises_extracted = 0

    # Fetch all documents. When re-enabling filtering for unprocessed videos (currently bypassed for testing),
    # the commented-out .where() clause below shows the updated syntax.
    videos_query = db.collection('youtube_video_data') # Original: .where(filter=firestore.FieldFilter(PROCESSING_FLAG_FIELD, '==', None))
    videos_stream = videos_query.stream()

    logger.info("Fetching ALL video transcripts from Firestore and filtering for Liberal Party (processing flag check is currently bypassed for testing)...")

    tasks = []
    liberal_videos_added_to_queue = 0

    for video_doc in videos_stream: # Iterate through the stream of all videos
        # Check if we've already reached the processing limit for Liberal videos
        if limit_arg is not None and liberal_videos_added_to_queue >= limit_arg:
            logger.info(f"Reached processing limit of {limit_arg} Liberal Party videos. Stopping queue population.")
            break # Stop iterating through the stream

        video_data = video_doc.to_dict()

        # --- Bypassed for testing ---
        # Double-check processing flag (safety for long-running streams or concurrent ops)
        # if video_data.get(PROCESSING_FLAG_FIELD) is not None:
        #     logger.debug(f"Video {video_doc.id} was already processed (flag found). Intentionally reprocessing for testing.")
        #     # continue # Original skip logic commented out for testing
        # else:
        #     logger.debug(f"Video {video_doc.id} has no processing flag. Queuing for processing.")
        # --- End Bypassed for testing ---
            
        _candidate_name, party_name = infer_candidate_party(video_data)

        if party_name == "Liberal Party of Canada":
            logger.info(f"Found Liberal Party video for processing: {video_doc.id} (Candidate: {_candidate_name})")
            tasks.append(process_single_video_transcript(video_doc))
            liberal_videos_added_to_queue += 1
            logger.info(f"Added Liberal video {video_doc.id} to queue. Total Liberal videos queued: {liberal_videos_added_to_queue}.")
        else:
            # Log non-liberal videos at debug level to avoid clutter unless verbose logging is on
            logger.debug(f"Skipping video {video_doc.id} - Party: '{party_name}' (not Liberal Party of Canada).")

    if not tasks:
        if limit_arg is not None and liberal_videos_added_to_queue >= limit_arg:
             logger.info(f"Processing limit of {limit_arg} Liberal Party videos was met. No further tasks to run in this batch if limit was low.")
        else:
             logger.info("No new Liberal Party video transcripts found meeting criteria for promise extraction in this run.")
        logger.info(f"--- YouTube Transcript Processing Finished (No tasks executed) ---")
        return

    logger.info(f"Starting LLM promise extraction for {len(tasks)} Liberal Party video transcript(s)...")
    results = await asyncio.gather(*tasks) # Run them concurrently
    total_promises_extracted = sum(results)
    logger.info(f"Finished LLM processing batch. Extracted a total of {total_promises_extracted} promises from {len(tasks)} Liberal Party videos.")

    logger.info(f"--- YouTube Transcript Processing Finished ---")


def get_parliament_session_for_date(target_date, default_session_id="45"):
    """
    Determine the parliament session for a given date.
    
    Args:
        target_date (datetime): The date to check
        default_session_id (str): Default session ID if no match found
        
    Returns:
        str: Parliament session ID
    """
    try:
        # Get all parliament sessions
        sessions_ref = db.collection('parliament_session')
        sessions = sessions_ref.stream()
        
        for session_doc in sessions:
            session_data = session_doc.to_dict()
            
            # Check if the date falls within this session's range
            start_date = session_data.get('start_date')
            end_date = session_data.get('end_date')
            
            if start_date:
                if isinstance(start_date, str):
                    start_date = datetime.fromisoformat(start_date.replace('Z', '+00:00'))
                elif hasattr(start_date, 'timestamp'):
                    start_date = start_date.to_datetime()
                
                # Check if target_date is after start_date
                if target_date >= start_date:
                    # If no end_date, this is the current session
                    if not end_date:
                        return session_doc.id
                    
                    # If end_date exists, check if target_date is before it
                    if isinstance(end_date, str):
                        end_date = datetime.fromisoformat(end_date.replace('Z', '+00:00'))
                    elif hasattr(end_date, 'timestamp'):
                        end_date = end_date.to_datetime()
                    
                    if target_date <= end_date:
                        return session_doc.id
        
        # If no session range matched, try to get current session from admin settings
        logger.warning(f"No specific session range matched for date {target_date}. Checking admin settings for current session.")
        try:
            admin_config_ref = db.document('admin_settings/global_config')
            admin_config = admin_config_ref.get()
            if admin_config.exists:
                config_data = admin_config.to_dict()
                current_session = config_data.get('current_selected_parliament_session')
                if current_session:
                    logger.info(f"Using current session from admin settings: {current_session}")
                    return str(current_session)
        except Exception as e:
            logger.error(f"Error fetching admin settings: {e}")
        
        # Final fallback to provided default
        logger.error(f"No session found for date {target_date}, and no admin settings found. Returning provided default: {default_session_id}")
        return default_session_id
        
    except Exception as e:
        logger.error(f"Error determining parliament session for date {target_date}: {e}")
        return default_session_id


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Process YouTube video transcripts to extract promises using Gemini LLM, focusing on the Liberal Party.")
    parser.add_argument("-n", "--limit", type=int, help="Maximum number of Liberal Party video transcripts to process.", default=None)
    args = parser.parse_args()

    # Ensure necessary environment variables are loaded/checked before running async logic
    if not os.getenv('GEMINI_API_KEY'):
        logger.critical("Cannot run script as GEMINI_API_KEY is not set.")
    elif db is None: # Check db again just in case
         logger.critical("Cannot run script as Firestore client is not available.")
    else:
        # Run the main async function
        asyncio.run(main_async_promises(args.limit))