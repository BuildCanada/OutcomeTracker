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
from common_utils import PROMISE_CATEGORIES # <<< CHANGED: Removed leading dot for direct import
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
PROMISES_COLLECTION = 'promises' # <<< CHANGED collection name
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
    """Processes one video document: extracts promises via LLM and saves them."""
    video_id = video_doc_snapshot.id
    video_data = video_doc_snapshot.to_dict()
    logger.info(f"Processing video transcript for ID: {video_id} (Title: {video_data.get('title', 'N/A')})")

    # Determine Parliament Session ID from video upload date
    determined_session_id = None
    upload_date_str = video_data.get('upload_date') # Expected format YYYYMMDD
    upload_date_obj = None
    if upload_date_str:
        try:
            upload_date_obj = datetime.strptime(upload_date_str, "%Y%m%d").date()
            # Call the synchronous helper function (db is globally available in this script)
            determined_session_id = get_session_id_for_date(upload_date_obj, db) 
            logger.info(f"Determined session ID '{determined_session_id}' for video {video_id} with upload date {upload_date_obj}")
        except ValueError:
            logger.warning(f"Invalid upload_date format for video {video_id}: {upload_date_str}. Cannot determine session ID by date. Will use default from helper.")
            determined_session_id = get_session_id_for_date(None, db) # Get default session ID
    else:
        logger.warning(f"Missing upload_date for video {video_id}. Cannot determine session ID by date. Will use default from helper.")
        determined_session_id = get_session_id_for_date(None, db) # Get default session ID

    # 1. Select English Transcript
    transcript_to_process = None
    if video_data.get('transcript_en_translated'): # Check for translation first
        transcript_to_process = video_data['transcript_en_translated']
        logger.info(f"  Using translated English transcript for {video_id}.")
    elif video_data.get('transcript_text_generated'): # Use generated original English text
        transcript_to_process = video_data['transcript_text_generated']
        logger.info(f"  Using original generated English transcript for {video_id}.")
    
    if not transcript_to_process or not transcript_to_process.strip():
        logger.warning(f"  No usable English transcript found for {video_id}. Skipping promise extraction.")
        doc_ref = db.collection('youtube_video_data').document(video_id)
        update_data_yt_video = {
            PROCESSING_FLAG_FIELD: firestore.SERVER_TIMESTAMP, 
            'promise_extraction_status': 'skipped_no_transcript'
        }
        if determined_session_id:
            update_data_yt_video['parliament_session_id'] = determined_session_id
        doc_ref.update(update_data_yt_video)
        return 0 

    # 2. Infer Candidate/Party
    candidate_name, party_name = infer_candidate_party(video_data)
    candidate_info = f"{candidate_name} ({party_name})"

    # 3. Build Prompt
    upload_date_str = video_data.get('upload_date', 'Unknown Date') # Format YYYYMMDD
    if upload_date_str and len(upload_date_str) == 8:
        upload_date_str = f"{upload_date_str[:4]}-{upload_date_str[4:6]}-{upload_date_str[6:8]}"
    
    prompt = build_gemini_prompt(
        transcript_to_process,
        video_data.get('title', 'N/A'),
        upload_date_str,
        candidate_info,
        PROMISE_CATEGORIES
    )

    # 4. Call Gemini API
    logger.debug(f"  Sending prompt to Gemini for {video_id}...")
    try:
        response = await model.generate_content_async(prompt)
        # Accessing the JSON response correctly
        if not response.candidates or not response.candidates[0].content.parts:
             logger.warning(f"  Warning: No content parts in Gemini response for {video_id}")
             extracted_promises_json_str = "[]"
        else:
            # response.text should contain the JSON string when response_mime_type is application/json
            extracted_promises_json_str = response.text 
        
        logger.debug(f"  Raw Gemini response text (first 500 chars): {extracted_promises_json_str[:500]}")
        
        # Attempt to parse the JSON response
        extracted_promises = json.loads(extracted_promises_json_str)
        
        if not isinstance(extracted_promises, list):
             logger.error(f"  Error: Gemini response was not a valid JSON list for {video_id}. Response: {extracted_promises_json_str}")
             raise ValueError("LLM response not a list")
             
        logger.info(f"  Gemini identified {len(extracted_promises)} potential promises for {video_id}.")

    except json.JSONDecodeError as json_err:
        logger.error(f"  Error: Failed to decode JSON response from Gemini for {video_id}: {json_err}")
        logger.error(f"  Problematic Gemini response text: {extracted_promises_json_str}")
        # Update status to reflect error
        doc_ref = db.collection('youtube_video_data').document(video_id)
        doc_ref.update({PROCESSING_FLAG_FIELD: firestore.SERVER_TIMESTAMP, 'promise_extraction_status': 'error_llm_json_decode'})
        return 0 # Return 0 promises processed
    except Exception as e:
        logger.error(f"  Error during Gemini API call for {video_id}: {e}", exc_info=True)
        # Update status to reflect error
        doc_ref = db.collection('youtube_video_data').document(video_id)
        doc_ref.update({PROCESSING_FLAG_FIELD: firestore.SERVER_TIMESTAMP, 'promise_extraction_status': f'error_llm_api: {str(e)[:100]}'})
        return 0 # Return 0 promises processed

    # 5. Save extracted promises to Firestore
    promises_added_count = 0
    batch = db.batch()
    promises_collection_ref = db.collection(PROMISES_COLLECTION)
    video_doc_ref = db.collection('youtube_video_data').document(video_id)

    for promise in extracted_promises:
        try:
            # Validate essential fields from LLM
            summary = promise.get('promise_summary')
            details = promise.get('promise_details_extracted')
            category = promise.get('category')
            key_points = promise.get('key_points')

            if not all([summary, details, category, key_points]):
                 logger.warning(f"  Skipping promise due to missing required fields from LLM for {video_id}. Data: {promise}")
                 continue
            
            # Validate category against known list
            if category not in PROMISE_CATEGORIES:
                 logger.warning(f"  Invalid category '{category}' from LLM for promise in {video_id}. Setting to 'Other'. Summary: {summary}")
                 category = "Other" # Assign to 'Other' if invalid
            
             # Ensure key_points is a list of strings
            if not isinstance(key_points, list) or not all(isinstance(item, str) for item in key_points):
                 logger.warning(f"  Invalid 'key_points' format from LLM for promise in {video_id}. Skipping this promise. Data: {promise}")
                 continue

            # Generate a unique ID for the promise
            promise_uuid = str(uuid.uuid4())

            # Prepare promise data for Firestore
            promise_data = {
                'promise_id': promise_uuid,
                'text': summary, # Using summary as the primary text
                'key_points': key_points, # Using LLM extracted key points
                'source_document_url': video_data.get('webpage_url'), # Link back to YT video
                'source_type': 'Video Transcript (YouTube)',
                'date_issued': upload_date_str, # Use formatted date
                'candidate_or_government': candidate_name,
                'party': party_name,
                'category': category,
                'responsible_department_lead': None, # Cannot determine from video
                'relevant_departments': [], # Cannot determine from video
                'video_source_id': video_id, # Link back to the video doc
                'video_timestamp_cue_raw': promise.get('timestamp_cue_raw'), # Raw cue from LLM
                'video_source_title': video_data.get('title'),
                'video_upload_date': video_data.get('upload_date'), # Store original YYYYMMDD

                 # --- New Fields ---
                'commitment_history_rationale': None, # Placeholder for future LLM enrichment
                'linked_evidence_ids': [], # Placeholder for linking to evidence items

                # --- Metadata ---
                'ingested_at': firestore.SERVER_TIMESTAMP,
                'last_updated_at': firestore.SERVER_TIMESTAMP,
                'parliament_session_id': determined_session_id, # NEW: Add determined session ID
            }

            # Add promise document creation to the batch
            new_promise_ref = promises_collection_ref.document(promise_uuid)
            batch.set(new_promise_ref, promise_data)
            promises_added_count += 1
        
        except Exception as e:
             logger.error(f"  Error preparing promise data from LLM output for {video_id}: {e}\nPromise data: {promise}", exc_info=True)
             # Continue to next promise if one fails


    # 6. Update video document status and commit batch
    try:
        batch.update(video_doc_ref, {
             PROCESSING_FLAG_FIELD: firestore.SERVER_TIMESTAMP,
             'promise_extraction_status': 'success',
             'extracted_promise_count': promises_added_count
        })
        batch.commit() # <<< REMOVED await
        logger.info(f"  Successfully saved {promises_added_count} promises and updated status for {video_id}.")
        return promises_added_count
    except Exception as e:
         logger.error(f"  Error committing Firestore batch for {video_id}: {e}", exc_info=True)
         # Attempt to update status anyway, but mark as batch commit error
         try:
              video_doc_ref.update({
                   PROCESSING_FLAG_FIELD: firestore.SERVER_TIMESTAMP,
                   'promise_extraction_status': f'error_batch_commit: {str(e)[:100]}'
              })
         except Exception as update_err:
              logger.error(f"  Failed to even update error status for {video_id}: {update_err}")
         return 0 # Return 0 promises successfully processed due to commit failure


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


# --- Helper function to get Parliament Session ID ---
def get_session_id_for_date(target_date, db_client, default_session_id="44"):
    """Queries Firestore to find the parliament_session_id for a given date."""
    if not target_date or not db_client:
        logger.warning("get_session_id_for_date: Missing target_date or db_client. Returning default.")
        return default_session_id # Or None, depending on desired strictness

    try:
        sessions_ref = db_client.collection('parliament_session')
        # Attempt to order by parliament_number descending to check more recent sessions first.
        # Firestore requires a composite index for range (target_date) and order on different field.
        # For simplicity with a small collection, fetch all and sort in Python, or rely on specific queries.
        # We will fetch all for now as the collection is small.
        sessions = sessions_ref.stream()

        matching_session = None

        for session_doc in sessions:
            session_data = session_doc.to_dict()
            parliament_number = session_data.get('parliament_number')
            
            start_date_str = session_data.get('election_called_date') # Use election_called_date as start
            end_date_str = session_data.get('end_date')

            if not parliament_number or not start_date_str or not end_date_str:
                logger.debug(f"Session {session_doc.id} missing key date fields or parliament_number. Skipping.")
                continue

            try:
                session_start_date = datetime.strptime(start_date_str, "%Y-%m-%d").date()
                
                # Handle flexible end_date (e.g., "current", or actual date)
                session_end_date = None
                if end_date_str.lower() == "current":
                    # If current, treat it as open-ended (effectively a very far future date for comparison)
                    # Or, if only one session is marked is_current_for_tracking, it could be prioritized.
                    # For this logic, if 'current', assume it includes the target_date if target_date >= session_start_date
                    # and no other session with a concrete end_date matches better.
                    # A simpler approach for now: if it's current, and target_date is after its start, it's a candidate.
                    pass # We will check is_current_for_tracking later if no date range matches
                else:
                    session_end_date = datetime.strptime(end_date_str, "%Y-%m-%d").date()
                
                if session_end_date: # Concrete end date
                    if session_start_date <= target_date < session_end_date:
                        logger.info(f"Date {target_date} matches session {parliament_number} ({start_date_str} to {end_date_str})")
                        # Prioritize specific range matches
                        return parliament_number 
                else: # End date is "current" or not a concrete date
                    # If end_date is effectively open, and target_date is on or after start_date,
                    # this session is a candidate. We might find a more specific match later.
                    if session_start_date <= target_date:
                        if session_data.get('is_current_for_tracking', False):
                            # If it's the designated 'current for tracking' and date is good, store it
                            matching_session = parliament_number
                        elif not matching_session: # Store if nothing else found yet
                            matching_session = parliament_number
                            
            except ValueError as ve:
                logger.warning(f"Could not parse dates for session {parliament_number} (ID: {session_doc.id}): {ve}. Skipping this session for date matching.")
                continue
        
        if matching_session:
            logger.info(f"Date {target_date} best matches session {matching_session} (possibly current or fallback).")
            return matching_session

        # Fallback if no session explicitly matched the date range (e.g. date is outside all defined ranges)
        # Try to get the one marked as is_current_for_tracking as a last resort if not already chosen
        logger.warning(f"No specific session range matched for date {target_date}. Looking for 'is_current_for_tracking'.")
        sessions_again = db_client.collection('parliament_session').where('is_current_for_tracking', '==', True).limit(1).stream()
        for sess_doc in sessions_again:
            logger.info(f"Falling back to default tracking session: {sess_doc.to_dict().get('parliament_number')}")
            return sess_doc.to_dict().get('parliament_number')

        logger.error(f"No session found for date {target_date}, and no default 'is_current_for_tracking' session found. Returning provided default: {default_session_id}")
        return default_session_id # Fallback to the hardcoded default or None

    except Exception as e:
        logger.error(f"Error querying parliament_session collection: {e}", exc_info=True)
        return default_session_id # Or None, on error
# --- End Helper function ---


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