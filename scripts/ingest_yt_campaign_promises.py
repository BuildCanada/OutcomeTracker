import json
import os
import subprocess
import time
import re # Added import for regular expressions
import logging # Added import for logging
import firebase_admin
from firebase_admin import credentials, firestore
from dotenv import load_dotenv # Import load_dotenv
import argparse # Import argparse
import webvtt 
from io import StringIO # Import StringIO

load_dotenv() # Load environment variables from .env file

# --- Logger Setup --- 
# Configure root logger once at the beginning.
logging.basicConfig(level=logging.INFO, 
                    format='%(asctime)s - %(levelname)s - %(filename)s:%(lineno)d - %(message)s',
                    datefmt='%Y-%m-%d %H:%M:%S',
                    force=True) # Use force=True to allow re-configuration if necessary, or ensure this is the only call.
logger = logging.getLogger(__name__)
# --- End Logger Setup ---

# --- Firebase Configuration ---
db = None # Initialize db to None
if not firebase_admin._apps:
    # Cloud Firestore initialization
    # GOOGLE_APPLICATION_CREDENTIALS environment variable must be set
    if not os.getenv('GOOGLE_APPLICATION_CREDENTIALS'):
        logger.critical("GOOGLE_APPLICATION_CREDENTIALS environment variable not set.")
        logger.critical("This is required for authentication with Google Cloud Firestore.")
        exit("Exiting YT Ingest: GOOGLE_APPLICATION_CREDENTIALS not set.")
    try:
        firebase_admin.initialize_app() # Default initialization for cloud
        logger.info("Python (YT Ingest): Successfully connected to Google Cloud Firestore.")
        db = firestore.client() # Assign the client to db
    except Exception as e:
        logger.critical(f"Python (YT Ingest): Firebase initialization failed for Google Cloud Firestore: {e}", exc_info=True)
        exit("Exiting YT Ingest: Firebase connection failed.")
else:
    logger.info("Python (YT Ingest): Firebase app already initialized. Getting client for Google Cloud Firestore.")
    db = firestore.client() # Get client if already initialized

# Final check if db is assigned
if db is None:
     logger.critical("Python (YT Ingest): Failed to obtain Firestore client after attempting cloud connection. Exiting.")
     exit("Exiting YT Ingest: Firestore client not available.")
# --- End Firebase Configuration ---

# --- YT-DLP Path (confirm if this is still needed or should be from config/env) ---
# Or provide the full path to the executable
YT_DLP_PATH = "yt-dlp" 
# --- End YT-DLP Path ---

def _parse_and_normalize_cues_from_file(file_path, lang_code_from_filename, video_id):
    """Parses VTT/SRT file using webvtt-py and normalize cues to {'start', 'end', 'text'} with float seconds."""
    normalized_cues = []
    html_tag_pattern = re.compile(r'<[^>]+>') # Keep basic tag cleaning for text

    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        captions = webvtt.read_buffer(StringIO(content))
        for caption in captions:
            # Clean text: remove tags, normalize whitespace
            cleaned_text = html_tag_pattern.sub('', caption.text).strip()
            cleaned_text = " ".join(cleaned_text.split()) # Normalize whitespace
            
            if cleaned_text: # Only add cues with actual text content
                normalized_cues.append({
                    'start': convert_timestamp_to_seconds(caption.start),
                    'end': convert_timestamp_to_seconds(caption.end),
                    'text': cleaned_text
                })
            # else: logger.debug(f"Skipping cue with empty text after cleaning from {file_path} for {video_id}")

        if normalized_cues:
            logger.info(f"Successfully parsed and normalized cues using webvtt-py from file {file_path} for {video_id}")
            # webvtt-py might not always preserve the original lang hint, so we trust the one passed in
            return normalized_cues, lang_code_from_filename if lang_code_from_filename != 'unknown' else None
        else:
             logger.warning(f"webvtt-py parsed file {file_path} but yielded no valid cues for {video_id}.")
             return None, None # No cues found even if parsing succeeded
             
    except webvtt.errors.MalformedCaptionError as e_parse:
        logger.error(f"webvtt-py MalformedCaptionError parsing file {file_path} for {video_id}: {e_parse}")
    except Exception as e:
        logger.error(f"Error parsing/normalizing file {file_path} with webvtt-py for {video_id}: {e}", exc_info=True)
        
    return None, None # Return None if any error occurs


def fetch_video_metadata_and_transcript(video_id):
    """
    Fetches metadata and transcript for a single video using yt-dlp.
    Uses a multi-attempt strategy focusing on getting subtitle files downloaded.
    Returns: (metadata_json, list_of_cue_maps, language_code)
             Cue maps are {'start': float_seconds, 'end': float_seconds, 'text': str}
    """
    video_url = f"https://www.youtube.com/watch?v={video_id}"
    logger.info(f"Processing video: {video_url}")
    
    temp_dir = f"temp_subtitles_{video_id}" 
    video_data_json = None
    found_cues = None
    found_lang = None

    # Party leader filter is applied later, after metadata is fetched.
    LEADER_NAMES = [
        "justin trudeau", "trudeau", "erin o'toole", "o'toole",
        "jagmeet singh", "singh", "yves-francois blanchet", "yves francois blanchet", "blanchet",
        "annamie paul", "paul"
    ]

    try:
        os.makedirs(temp_dir, exist_ok=True)
        logger.debug(f"Created temporary directory: {temp_dir} for video {video_id}")

        # --- Attempt 1: Standard download, dump JSON, check files --- 
        cmd_attempt1 = [
            YT_DLP_PATH,
            '--skip-download',
            '--write-auto-sub', '--write-sub',
            '--sub-langs', 'en.*,fr.*',
            '--sub-format', 'vtt/srt/best', # Use flexible format
            '-o', os.path.join(temp_dir, 'att1_%(id)s.%(language)s.%(ext)s'), # Prefixed filename
            '--dump-json', # Get metadata JSON
            video_url
        ]
        logger.info(f"Attempt 1 for {video_id}: Fetch metadata and try downloading subs.")
        logger.debug(f"Command (Attempt 1): {' '.join(cmd_attempt1)}")
        
        process1 = subprocess.run(cmd_attempt1, capture_output=True, text=True, check=False, encoding='utf-8')

        if process1.returncode != 0:
            logger.warning(f"yt-dlp process (Attempt 1) for {video_id} failed with code {process1.returncode}. Will still check for partial output/files.")
            if process1.stderr:
                bar = '-' * 20; stderr_content = process1.stderr.strip()
                logger.warning(f"yt-dlp stderr (Attempt 1) for {video_id}:\n{bar}\n{stderr_content}\n{bar}")
        
        # Process metadata JSON from attempt 1 (even if file download part failed)
        if process1.stdout:
            try:
                video_data_json = json.loads(process1.stdout)
            except json.JSONDecodeError as je:
                logger.error(f"JSONDecodeError parsing metadata from Attempt 1 for {video_id}: {je}. Cannot proceed.")
                # No point continuing without metadata for filtering etc.
                return None, None, None
        else:
            logger.error(f"No stdout (JSON metadata) from yt-dlp (Attempt 1) for {video_id}. Cannot proceed.")
            return None, None, None

        # --- Apply party leader filter --- 
        if video_data_json:
            description = video_data_json.get('description', '').lower()
            title = video_data_json.get('title', '').lower()
            search_text = title + " " + description 
            if not any(name in search_text for name in LEADER_NAMES):
                logger.info(f"Skipping video {video_id} - no party leader mentioned (checked after metadata fetch). Filter applied.")
                # Return metadata even if skipped, maybe useful later?
                # Or return None, None, None? For now, return Nones as transcript won't be processed.
                return None, None, None 
            else:
                logger.info(f"Party leader found for {video_id}. Continuing to process transcript files.")
        else: # Should be caught above, but safety first
            logger.error(f"Metadata missing after fetch for {video_id}, cannot apply filter or proceed.")
            return None, None, None
            
        # --- Check files from Attempt 1 --- 
        logger.info(f"Checking files in {temp_dir} after Attempt 1 for {video_id}")
        att1_files = []
        if os.path.exists(temp_dir):
             att1_files = [os.path.join(temp_dir, f) for f in os.listdir(temp_dir) if f.startswith('att1_') and f.endswith(('.vtt', '.srt'))]
             logger.info(f"Files found from Attempt 1: {att1_files}")

        file_preference = [('.en.vtt', 'en'), ('.fr.vtt', 'fr'), ('.en.srt', 'en'), ('.fr.srt', 'fr'),
                           ('.vtt', None), ('.srt', None)] # Generic fallback

        for suffix, specific_lang_code in file_preference:
            for f_path in att1_files:
                matches_specific_lang = (specific_lang_code and f'.{specific_lang_code}.' in os.path.basename(f_path).lower() and f_path.endswith(suffix))
                matches_generic_ext = (not specific_lang_code and f_path.endswith(suffix))
                
                if video_id in f_path and (matches_specific_lang or matches_generic_ext):
                    lang_to_pass = specific_lang_code
                    if not lang_to_pass: # Infer from filename
                        fn_lower = os.path.basename(f_path).lower()
                        if '.en.' in fn_lower: lang_to_pass = 'en'
                        elif '.fr.' in fn_lower: lang_to_pass = 'fr'
                    
                    logger.info(f"Attempt 1: Parsing file {f_path} (lang hint: {lang_to_pass}) for {video_id}")
                    parsed_cues, lang_from_file = _parse_and_normalize_cues_from_file(f_path, lang_to_pass or 'unknown', video_id)
                    if parsed_cues:
                        found_cues = parsed_cues
                        found_lang = lang_from_file if lang_from_file != 'unknown' else (specific_lang_code or 'unknown')
                        if found_lang == 'unknown' and specific_lang_code: found_lang = specific_lang_code
                        logger.info(f"Attempt 1: Success from file {f_path} (lang: {found_lang}). Cues: {len(found_cues)}. Snippet: {found_cues[0]['text'][:100] if found_cues else 'N/A'}")
                        break
            if found_cues: break

        # --- Attempt 2: Compatibility Mode (Files Only) --- 
        if not found_cues:
            logger.info(f"Attempt 2 for {video_id}: Using youtube-dl compatibility mode with targeted VTT download.")
            
            # Try English auto VTT first
            logger.info(f"Attempt 2a for {video_id}: Explicitly fetching 'en' auto VTT.")
            cmd_attempt2_en = [
                YT_DLP_PATH, '--skip-download',
                '--write-auto-sub', # Focus on auto-subs
                '--sub-lang', 'en',
                '--sub-format', 'vtt',
                '--compat-options', 'youtube-dl',
                '-o', os.path.join(temp_dir, 'att2_%(id)s.en.%(ext)s'), # Specific lang in filename
                '--verbose',
                video_url
            ]
            logger.debug(f"Command (Attempt 2a - en): {' '.join(cmd_attempt2_en)}")
            process2_en = subprocess.run(cmd_attempt2_en, capture_output=True, text=True, check=False, encoding='utf-8')

            if process2_en.returncode != 0:
                logger.warning(f"yt-dlp process (Attempt 2a - en) for {video_id} failed with code {process2_en.returncode}.")
                if process2_en.stderr: logger.warning(f"yt-dlp stderr (Attempt 2a - en) for {video_id}:\\n{'-'*20}\\n{process2_en.stderr.strip()}\\n{'-'*20}")
            else:
                logger.info(f"yt-dlp process (Attempt 2a - en) for {video_id} completed (exit code 0).")

            # Check if English VTT was downloaded
            # We will check specific filenames later, this subprocess run is just to trigger download.
            # The file checking logic below will pick up 'att2_*.en.vtt'

            # If English didn't result in a file (or we want to try French anyway if EN is not primary)
            # For now, let's assume we just want one, and the file checking logic will find what was downloaded.
            # Let's try French only if the English command failed or we specifically need French (not implemented here)
            # The current file preference logic handles picking the best file.
            # The main change is to be more specific in the download command.
            # We might still need a broader attempt if these specific ones fail.
            # For now, let's stick to the an explicit 'en' and an explicit 'fr' if 'en' failed to run or no files found yet.

            # Let's re-evaluate: the original Attempt 2 was a single command.
            # If the issue is the broadness of sub-langs, let's try two specific commands.
            
            # Check files from Attempt 2a (English)
            logger.info(f"Checking files in {temp_dir} after Attempt 2a (en) for {video_id} using targeted logic.")
            files_after_att2a = []
            if os.path.exists(temp_dir):
                files_after_att2a = [os.path.join(temp_dir, f) for f in os.listdir(temp_dir) if f.startswith('att2_') and f.endswith('.en.vtt')]
            
            if not files_after_att2a: # If no English VTT found, try French
                logger.info(f"Attempt 2b for {video_id}: No English VTT found from 2a, explicitly fetching 'fr' auto VTT.")
                cmd_attempt2_fr = [
                    YT_DLP_PATH, '--skip-download',
                    '--write-auto-sub',
                    '--sub-lang', 'fr',
                    '--sub-format', 'vtt',
                    '--compat-options', 'youtube-dl',
                    '-o', os.path.join(temp_dir, 'att2_%(id)s.fr.%(ext)s'), # Specific lang in filename
                    '--verbose',
                    video_url
                ]
                logger.debug(f"Command (Attempt 2b - fr): {' '.join(cmd_attempt2_fr)}")
                process2_fr = subprocess.run(cmd_attempt2_fr, capture_output=True, text=True, check=False, encoding='utf-8')

                if process2_fr.returncode != 0:
                    logger.warning(f"yt-dlp process (Attempt 2b - fr) for {video_id} failed with code {process2_fr.returncode}.")
                    if process2_fr.stderr: logger.warning(f"yt-dlp stderr (Attempt 2b - fr) for {video_id}:\\n{'-'*20}\\n{process2_fr.stderr.strip()}\\n{'-'*20}")
                else:
                    logger.info(f"yt-dlp process (Attempt 2b - fr) for {video_id} completed (exit code 0).")
            
            # The rest of the file checking logic remains the same, it will pick up whatever was downloaded.
            # The key is that we've tried to be more specific with the download commands.

            # Check files from Attempt 2 using targeted pattern matching
            logger.info(f"Checking files in {temp_dir} after Attempt 2 (a/b) for {video_id} using targeted logic.")
            att2_files = []
            if os.path.exists(temp_dir):
                att2_files = [os.path.join(temp_dir, f) for f in os.listdir(temp_dir) if f.startswith('att2_') and f.endswith(('.vtt'))] # Focus on VTT from Attempt 2
                logger.info(f"Files found from Attempt 2 (VTT): {att2_files}")

            # Define target filename patterns (more specific)
            target_patterns = [
                (('.en.en.vtt', '.en.en-orig.vtt'), 'en'),      # Priority 1: English original/ASR
                (('.fr.en.vtt',), 'en'),                       # Priority 2: French translated to English
                (('.fr.fr.vtt', '.fr.fr-orig.vtt'), 'fr')       # Priority 3: French original/ASR
            ]

            for suffixes, target_lang in target_patterns:
                if found_cues: break # Stop if we found one in a previous priority level
                for f_path in att2_files:
                    # Check if filename ends with any of the suffixes for the current priority
                    if any(f_path.endswith(suffix) for suffix in suffixes):
                        logger.info(f"Attempt 2: Found matching file pattern {suffixes} for target lang '{target_lang}'. Parsing file {f_path} for {video_id}")
                        parsed_cues, _ = _parse_and_normalize_cues_from_file(f_path, target_lang, video_id) # Use target_lang directly
                        if parsed_cues:
                            found_cues = parsed_cues
                            found_lang = target_lang # Assign language based on the pattern matched
                            logger.info(f"Attempt 2: Success from file {f_path} (lang: {found_lang}). Cues: {len(found_cues)}. Snippet: {found_cues[0]['text'][:100] if found_cues else 'N/A'}")
                            break # Found the best match for this priority, move to next video
            # End of priority loop

        # --- Final Result --- 
        if not found_cues:
            logger.warning(f"No transcript (cues) could be obtained for {video_id} after all attempts.")
            # Return metadata, but None for cues and lang
            return video_data_json, None, None 
        else:
            # Log before returning success
            logger.info(f"Successfully obtained transcript for {video_id}. Returning lang='{found_lang}', cues found={len(found_cues)}")
            return video_data_json, found_cues, found_lang
    
    except Exception as e:
        logger.error(f"Major unexpected error in fetch_video_metadata_and_transcript for {video_id}: {e}", exc_info=True)
        return None, None, None 
    finally: # Keep commented out to inspect temp folders
        if os.path.exists(temp_dir):
            try:
                for file_to_remove in os.listdir(temp_dir):
                    try: os.remove(os.path.join(temp_dir, file_to_remove))
                    except OSError as e_remove: logger.warning(f"Could not remove file {file_to_remove} in {temp_dir} for {video_id}: {e_remove}")
                os.rmdir(temp_dir)
                logger.debug(f"Successfully cleaned up temporary directory: {temp_dir} for {video_id}")
            except OSError as e_rmdir:
                logger.warning(f"Could not remove directory {temp_dir} for {video_id}: {e_rmdir} (it might not be empty or access denied)")

def convert_timestamp_to_seconds(timestamp_str):
    """Converts HH:MM:SS.mmm or HH:MM:SS,mmm to float seconds."""
    if not timestamp_str or not isinstance(timestamp_str, str):
        return 0.0 # Or raise an error, or return None

    # Normalize separator for milliseconds
    timestamp_str = timestamp_str.replace(',', '.')
    
    parts = timestamp_str.split(':')
    seconds_str = parts[-1]
    try:
        if len(parts) == 3: # HH:MM:SS.mmm
            h, m = int(parts[0]), int(parts[1])
            s_ms = float(seconds_str)
            return h * 3600 + m * 60 + s_ms
        elif len(parts) == 2: # MM:SS.mmm
            m = int(parts[0])
            s_ms = float(seconds_str)
            return m * 60 + s_ms
        elif len(parts) == 1: # SS.mmm
            return float(seconds_str)
        else:
            logger.warning(f"Unexpected timestamp format: {timestamp_str}")
            return 0.0
    except ValueError as e:
        logger.error(f"ValueError converting timestamp '{timestamp_str}': {e}")
        return 0.0

def deduplicate_cues(raw_cues):
    """Deduplicates cues based on case-insensitive comparison of consecutive text content."""
    if not raw_cues:
        return []

    cleaned_cues = []
    if not isinstance(raw_cues, list) or len(raw_cues) == 0:
        return []

    # Filter out cues that are not dicts or don't have text
    # We process the original list
    process_list = [cue for cue in raw_cues if isinstance(cue, dict) and 'text' in cue]
    
    if not process_list: return [] 

    for i, current_cue in enumerate(process_list):
        current_text_stripped = current_cue.get('text', '').strip()
        if not current_text_stripped: # Skip cues that become empty after stripping
            continue

        # Add first valid cue unconditionally
        if not cleaned_cues:
            cleaned_cues.append(current_cue)
            continue

        # Get the text of the last cue added to cleaned_cues
        last_added_text_stripped = cleaned_cues[-1].get('text', '').strip()
        
        current_text_lower = current_text_stripped.lower() # current_text_stripped is defined in the loop
        last_added_text_lower = last_added_text_stripped.lower()

        # Rule 1: Current cue expands on (or is identical to) the last added cue.
        if last_added_text_lower in current_text_lower:
            # Handles progressive reveals (e.g., last="A", current="A B") -> replaces A with A B.
            # Also handles exact duplicates (e.g., last="A", current="A") -> replaces A with A.
            cleaned_cues[-1] = current_cue
            # logger.debug(f"DEDUPE Rule 1: Replaced last '{last_added_text_lower[:30]}...' with current '{current_text_lower[:30]}...'")
            continue 

        # Rule 2: Last added cue already contains the current cue's text (and is longer).
        # This means current_cue is a shorter, redundant part of what's already captured.
        if current_text_lower in last_added_text_lower: 
            # logger.debug(f"DEDUPE Rule 2: Skipped current '{current_text_lower[:30]}...' as it's part of last '{last_added_text_lower[:30]}...'")
            continue
            
        # If neither of the above, it's a new, different cue.
        cleaned_cues.append(current_cue)
        # logger.debug(f"DEDUPE Rule 3: Appended new cue '{current_text_lower[:30]}...'")
            
    return cleaned_cues


def translate_to_english(text, source_lang="fr"):
    # This function is no longer used directly for immediate translation.
    # It can be removed or kept for future direct use if needed.
    if not text:
        return None
    # logger.debug(f"TRANSLATION_PLACEHOLDER: Simulating translation of text from {source_lang} to English.")
    # return f"[TRANSLATED FROM {source_lang.upper()} (Placeholder)] {text}" # Commented out as it's not used
    return None # Explicitly return None if not used


def save_video_data_to_firestore(video_id, metadata, raw_cue_list, transcript_language_original):
    """
    Saves the extracted video metadata, cleaned transcript cues, and generated text to Firestore.
    """
    if not metadata:
        logger.warning(f"No metadata to save for {video_id}, skipping Firestore save.")
        return

    doc_ref = db.collection('youtube_video_data').document(video_id)
    
    logger.info(f"SAVE_VIDEO_DATA for {video_id}: Received lang='{transcript_language_original}', raw cues count={len(raw_cue_list) if isinstance(raw_cue_list, list) else 'N/A'}.")

    # Deduplicate cues and generate text
    cleaned_cues = []
    transcript_text_generated = ""
    if raw_cue_list and isinstance(raw_cue_list, list):
        cleaned_cues = deduplicate_cues(raw_cue_list)
        logger.info(f"SAVE_VIDEO_DATA for {video_id}: Cues after deduplication: {len(cleaned_cues)}.")
        # Generate text only from non-empty, stripped cue texts
        transcript_text_generated = "\n".join([cue.get('text', '').strip() for cue in cleaned_cues if cue.get('text', '').strip()])
        logger.info(f"SAVE_VIDEO_DATA for {video_id}: Length of generated transcript text: {len(transcript_text_generated)}.")
    elif raw_cue_list: 
        logger.warning(f"SAVE_VIDEO_DATA for {video_id}: Received non-list raw_cue_list type: {type(raw_cue_list)}. Storing as empty transcript.")
    else: # raw_cue_list is None or empty
        logger.info(f"SAVE_VIDEO_DATA for {video_id}: No raw cues provided or raw_cue_list is empty. Transcript will be empty.")

    data_to_store = {
        'video_id': video_id,
        'title': metadata.get('title'),
        'description': metadata.get('description'),
        'upload_date': metadata.get('upload_date'), 
        'uploader': metadata.get('uploader'),
        'uploader_id': metadata.get('uploader_id'),
        'channel_id': metadata.get('channel_id'),
        'channel_url': metadata.get('channel_url'),
        'duration': metadata.get('duration'), # This is usually in seconds from yt-dlp JSON
        'duration_string': metadata.get('duration_string'),
        'view_count': metadata.get('view_count'),
        'like_count': metadata.get('like_count'),
        'comment_count': metadata.get('comment_count'),
        'tags': metadata.get('tags'),
        'categories': metadata.get('categories'),
        'thumbnail_url': metadata.get('thumbnail'), 
        'webpage_url': metadata.get('webpage_url', f"https://www.youtube.com/watch?v={video_id}"),
        'original_url': metadata.get('original_url'),
        
        # New transcript fields
        'transcript_cues_cleaned': cleaned_cues, # Store the list of cleaned cue maps
        'transcript_text_generated': transcript_text_generated, # Store the flat text from cleaned cues
        'transcript_language_original': transcript_language_original, # 'en', 'fr', or None/unknown
        
        'raw_yt_dlp_json_snippet': json.dumps(metadata, indent=2)[:2000], 
        'ingested_at': firestore.SERVER_TIMESTAMP,
        'needs_translation': transcript_language_original == 'fr' 
    }
    # Removed old fields: transcript_text_original, transcript_cues_original (effectively replaced)

    try:
        doc_ref.set(data_to_store, merge=True) 
        logger.info(f"Successfully saved data for video {video_id} to Firestore.")
    except Exception as e:
        logger.error(f"Error saving video {video_id} to Firestore: {e}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Ingest YouTube campaign promise videos.")
    parser.add_argument("-n", "--limit", type=int, default=None, 
                        help="Limit the number of videos to process from the input file. Processes all if not set.")
    args = parser.parse_args()

    video_ids_file_path = os.path.join(os.path.dirname(__file__), '..', 'raw-data', '2021-yt-playlist-ids.md')
    processed_video_ids = []

    try:
        with open(video_ids_file_path, 'r', encoding='utf-8') as f:
            all_lines = f.readlines()
        
        # Skip header/comment lines (e.g., lines starting with '#') and strip whitespace
        processed_video_ids = [line.strip() for line in all_lines if line.strip() and not line.strip().startswith('#')]
        
        if not processed_video_ids:
            logger.warning(f"No video IDs found in {video_ids_file_path}. Exiting.")
            exit()
            
        logger.info(f"Found {len(processed_video_ids)} video IDs to process from {video_ids_file_path}")

    except FileNotFoundError:
        logger.error(f"Video ID file not found at {video_ids_file_path}. Please ensure the file exists.")
        exit()
    except Exception as e:
        logger.error(f"An error occurred while reading video IDs from {video_ids_file_path}: {e}")
        exit()

    # Apply the limit if provided
    if args.limit is not None and args.limit > 0:
        logger.info(f"Processing a limited number of videos: {args.limit} of {len(processed_video_ids)} total.")
        processed_video_ids = processed_video_ids[:args.limit]
    elif args.limit is not None and args.limit <= 0:
        logger.warning(f"Invalid limit {args.limit} specified. Processing all videos.")

    logger.info(f"Starting processing for {len(processed_video_ids)} videos.")

    for video_id in processed_video_ids:
        logger.info(f"--- Processing video ID: {video_id} ---")
        metadata, transcript_cues, transcript_lang = fetch_video_metadata_and_transcript(video_id)
        if metadata: # Only save if metadata (and potentially transcript) was fetched
            # Pass the structured cues to Firestore saving function
            save_video_data_to_firestore(video_id, metadata, transcript_cues, transcript_lang)
        else:
            logger.warning(f"Skipping save for {video_id} due to fetch error, no metadata, or filtered out.")
        
        logger.info("-" * 40) # Use logger for separators too, or remove them if too noisy
        time.sleep(1) # Reduced sleep time for potentially faster processing, adjust as needed

    logger.info("Finished processing all videos from the input file.") 