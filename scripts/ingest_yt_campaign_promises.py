import json
import os
import subprocess
import time
import re # Added import for regular expressions
import logging # Added import for logging
import firebase_admin
from firebase_admin import credentials, firestore

# --- Firebase Configuration ---
if not firebase_admin._apps:
    if os.getenv('FIRESTORE_EMULATOR_HOST'):
        # Connect to the Firestore Emulator
        options = {'projectId': 'promisetrackerapp'} # Use your desired project ID for the emulator
        firebase_admin.initialize_app(options=options)
        print(f"Python (YT Ingest): Connected to Firestore Emulator at {os.getenv('FIRESTORE_EMULATOR_HOST')} using project ID '{options['projectId']}'")
    else:
        # Use logging for errors as well
        logging.error("FIRESTORE_EMULATOR_HOST environment variable not set for YT Ingest script.")
        logging.error("Please set it to connect to the local Firestore emulator (e.g., 'localhost:8080').")
        exit("Exiting YT Ingest: Firestore emulator not configured.")
      
db = firestore.client()
# --- End Firebase Configuration ---

# --- Logger Setup ---
logging.basicConfig(level=logging.INFO, 
                    format='%(asctime)s - %(levelname)s - %(filename)s:%(lineno)d - %(message)s',
                    datefmt='%Y-%m-%d %H:%M:%S')
logger = logging.getLogger(__name__)
# --- End Logger Setup ---

# Or provide the full path to the executable
YT_DLP_PATH = "yt-dlp" 

def fetch_video_metadata_and_transcript(video_id):
    """
    Fetches metadata and transcript for a single video using yt-dlp.
    Attempts to get English or French auto-captions or subtitles.
    Prioritizes English; translates French using a placeholder.
    """
    video_url = f"https://www.youtube.com/watch?v={video_id}"
    logger.info(f"Processing video: {video_url}")
    
    temp_dir = f"temp_subtitles_{video_id}" # Make temp_dir unique per video to avoid conflicts if run in parallel
    video_data_json = None
    transcript_content = None
    transcript_language = None

    # Define party leaders for filtering (consider moving to config or env var)
    LEADER_NAMES = [
        "justin trudeau", "trudeau",
        "erin o'toole", "o'toole",
        "jagmeet singh", "singh",
        "yves-francois blanchet", "yves francois blanchet", "blanchet",
        "annamie paul", "paul"
    ]

    try:
        os.makedirs(temp_dir, exist_ok=True)
        logger.debug(f"Created temporary directory: {temp_dir} for video {video_id}")

        # Attempt 1: Fetch metadata and standard subtitles
        # This command also fetches metadata with --dump-json
        cmd_attempt1 = [
            YT_DLP_PATH,
            '--skip-download',
            '--write-auto-sub',
            '--write-sub',
            '--sub-langs', 'en.*,fr.*',
            '--sub-format', 'vtt', # Prefer VTT
            '-o', os.path.join(temp_dir, '%(id)s.%(ext)s'),
            '--verbose', # Keep verbose for now, can be reduced later
            '--dump-json',
            video_url
        ]
        logger.info(f"Attempting to fetch metadata and subtitles for {video_id}")
        logger.debug(f"Command (Metadata & Attempt 1): {' '.join(cmd_attempt1)}")
        
        process = subprocess.run(cmd_attempt1, capture_output=True, text=True, check=False, encoding='utf-8') # check=False to handle errors manually

        if process.returncode != 0:
            logger.error(f"yt-dlp process for metadata/subs (Attempt 1) for {video_id} failed with code {process.returncode}")
            if process.stderr:
                bar = '-' * 20
                stderr_content = process.stderr.strip()
                logger.error(f"yt-dlp stderr (Attempt 1) for {video_id}:\n{bar}\n{stderr_content}\n{bar}")
            # No specific return here, will proceed to see if any files were partially downloaded or if metadata was output despite error

        # Process stdout for JSON metadata (even if subtitle part failed, metadata might be there)
        if process.stdout:
            try:
                video_data_json = json.loads(process.stdout)
            except json.JSONDecodeError as je:
                logger.error(f"JSONDecodeError for video {video_id} during metadata fetch: {je}")
                stdout_head = "\n".join(process.stdout.splitlines()[:20])
                bar = '-' * 20
                logger.error(f"First 20 lines of stdout causing JSON error for {video_id}:\n{bar}\n{stdout_head}\n{bar}")
        else:
            logger.warning(f"No stdout from yt-dlp for metadata fetch for {video_id}.")

        # --- Filter based on party leader in description --- (Needs video_data_json)
        if video_data_json:
            description = video_data_json.get('description')
            if description:
                description_lower = description.lower()
                found_leader = any(name in description_lower for name in LEADER_NAMES)
                if not found_leader:
                    logger.info(f"Skipping video {video_id} - no party leader mentioned in the description.")
                    return None, None, None # Skip processing this video (temp_dir cleaned in finally)
                else:
                    logger.info(f"Party leader found in description for {video_id}. Processing video.")
            else:
                logger.warning(f"Video description not available in metadata for {video_id}. Proceeding with transcript attempts.")
        else:
            logger.warning(f"Could not parse video metadata for {video_id} to check description. Proceeding with transcript attempts. This might mean the video is unavailable or restricted.")
            # Decide if we should return or continue if metadata is critical
            # For now, we continue to try and get transcripts, but this video might be unlistable later if metadata is strictly required

        # --- Attempt to process downloaded subtitles --- 
        subtitle_files = []
        if os.path.exists(temp_dir):
            for file_name in os.listdir(temp_dir):
                if file_name.endswith(('.vtt', '.srt')) and video_id in file_name:
                    subtitle_files.append(os.path.join(temp_dir, file_name))
        
        logger.debug(f"Found subtitle files after initial attempt for {video_id}: {subtitle_files}")

        for s_file_path in subtitle_files:
            try:
                with open(s_file_path, 'r', encoding='utf-8') as f:
                    file_content = f.read()
                
                if s_file_path.endswith('.vtt'):
                    parsed_cues = parse_vtt(file_content)
                elif s_file_path.endswith('.srt'):
                    parsed_cues = parse_srt(file_content) # Assuming parse_srt will be updated
                else:
                    continue

                if parsed_cues:
                    transcript_content = parsed_cues
                    # Determine language from filename (basic check)
                    fn_lower = os.path.basename(s_file_path).lower()
                    if any(f'.{lang_code}.' in fn_lower for lang_code in ['en', 'eng', 'english']):
                        transcript_language = 'en'
                    elif any(f'.{lang_code}.' in fn_lower for lang_code in ['fr', 'fra', 'french']):
                        transcript_language = 'fr'
                    else: # Fallback: check if yt-dlp included lang in requested_subtitles
                        if video_data_json and video_data_json.get('requested_subtitles'):
                            req_subs = video_data_json['requested_subtitles']
                            for lang_key, sub_info in req_subs.items():
                                if sub_info.get('ext') in s_file_path:
                                    transcript_language = lang_key.split('-')[0] # e.g. en-US -> en
                                    break
                        if not transcript_language: transcript_language = 'unknown'
                    
                    logger.info(f"Successfully read and parsed transcript from {s_file_path} for {video_id} (lang: {transcript_language})")
                    break # Found a transcript
            except Exception as read_err:
                logger.error(f"Error reading or parsing subtitle file {s_file_path} for {video_id}: {read_err}")

        # --- Subsequent attempts if no transcript found yet --- 
        # This section can be refactored into a loop or helper function if attempts become more complex
        # For now, keeping a simplified structure for clarity given the original three attempts

        if not transcript_content:
            logger.info(f"No transcript from initial attempt for {video_id}. Trying alternative methods.")
            # Simplified additional attempt (example: trying --write-auto-sub only if not already tried effectively)
            # The original script had complex, somewhat overlapping attempts. 
            # A more robust approach might involve checking yt-dlp's reported available subs first (--list-subs)
            # and then specifically requesting them.
            
            # Example: A single, more focused second attempt targeting auto-subs specifically if not primary
            cmd_attempt_auto_subs = [
                YT_DLP_PATH,
                '--skip-download',
                '--write-auto-sub', # Focus on auto-subs
                '--sub-langs', 'en.*,fr.*',
                '--sub-format', 'vtt', # Stick to VTT for auto if possible
                '-o', os.path.join(temp_dir, 'auto_%(id)s.%(ext)s'),
                video_url
            ]
            logger.info(f"Attempting to fetch auto-subtitles specifically for {video_id}")
            logger.debug(f"Command (Auto-Subs Attempt): {' '.join(cmd_attempt_auto_subs)}")
            
            try:
                process_auto = subprocess.run(cmd_attempt_auto_subs, capture_output=True, text=True, check=False, encoding='utf-8')
                if process_auto.returncode != 0:
                    logger.warning(f"yt-dlp auto-subs attempt for {video_id} failed or produced no new files. Code: {process_auto.returncode}")
                    if process_auto.stderr:
                        bar = '-' * 20
                        stderr_content = process_auto.stderr.strip()
                        logger.warning(f"yt-dlp stderr (Auto-Subs Attempt) for {video_id}:\n{bar}\n{stderr_content}\n{bar}")

                # Check for newly downloaded auto-sub files
                auto_subtitle_files = []
                if os.path.exists(temp_dir):
                    for file_name in os.listdir(temp_dir):
                        if file_name.startswith('auto_') and file_name.endswith(('.vtt', '.srt')) and video_id in file_name:
                            auto_subtitle_files.append(os.path.join(temp_dir, file_name))
                
                logger.debug(f"Found auto-subtitle files for {video_id}: {auto_subtitle_files}")

                for s_file_path in auto_subtitle_files:
                    # Avoid reprocessing files already checked if names overlap, though 'auto_' prefix helps
                    try:
                        with open(s_file_path, 'r', encoding='utf-8') as f:
                            file_content = f.read()
                        
                        if s_file_path.endswith('.vtt'): parsed_cues = parse_vtt(file_content)
                        elif s_file_path.endswith('.srt'): parsed_cues = parse_srt(file_content)
                        else: continue

                        if parsed_cues:
                            transcript_content = parsed_cues
                            # Language determination similar to above, can be a helper
                            fn_lower = os.path.basename(s_file_path).lower()
                            if any(f'.{lang_code}.' in fn_lower for lang_code in ['en', 'eng', 'english']):
                                transcript_language = 'en'
                            elif any(f'.{lang_code}.' in fn_lower for lang_code in ['fr', 'fra', 'french']):
                                transcript_language = 'fr'
                            else: transcript_language = 'unknown' # Simpler fallback for auto-subs

                            logger.info(f"Successfully read and parsed transcript from auto-sub attempt: {s_file_path} for {video_id} (lang: {transcript_language})")
                            break # Found a transcript
                    except Exception as read_err:
                        logger.error(f"Error reading or parsing auto-subtitle file {s_file_path} for {video_id}: {read_err}")
            except Exception as e_auto:
                 logger.error(f"Error during dedicated auto-subtitle fetch for {video_id}: {e_auto}")

        if not transcript_content:
            logger.warning(f"No transcript could be obtained for {video_id} after all attempts.")

        # video_data_json might be None if initial yt-dlp call failed badly for metadata
        return video_data_json, transcript_content, transcript_language
    
    except subprocess.CalledProcessError as e: # Should be less frequent with check=False
        logger.error(f"A subprocess.CalledProcessError occurred unexpectedly for {video_id}: {e}")
        if e.stderr:
            bar = '-' * 20
            stderr_content = e.stderr.strip()
            logger.error(f"Associated stderr for {video_id}:\n{bar}\n{stderr_content}\n{bar}")
        return None, None, None # Ensure this path also cleans up
    except Exception as e:
        logger.error(f"An unexpected error in fetch_video_metadata_and_transcript for {video_id}: {e}", exc_info=True)
        return None, None, None # Ensure this path also cleans up
    finally:
        if os.path.exists(temp_dir):
            try:
                for file_to_remove in os.listdir(temp_dir):
                    try:
                        os.remove(os.path.join(temp_dir, file_to_remove))
                    except OSError as e_remove:
                        logger.warning(f"Could not remove file {file_to_remove} in {temp_dir} for {video_id}: {e_remove}")
                os.rmdir(temp_dir)
                logger.debug(f"Successfully cleaned up temporary directory: {temp_dir} for {video_id}")
            except OSError as e_rmdir:
                logger.warning(f"Could not remove directory {temp_dir} for {video_id}: {e_rmdir} (it might not be empty or access denied)")


def parse_srt(srt_content):
    """Parse SRT format subtitles into a list of cue dictionaries.
       Each cue: {"start_time": "HH:MM:SS,mmm", "end_time": "HH:MM:SS,mmm", "text": "cue text"}
       Note: SRT uses comma for millisecond separator, VTT uses dot. We keep SRT's format here.
    """
    cues = []
    lines = srt_content.splitlines()
    idx = 0
    
    # SRT timestamp pattern: HH:MM:SS,mmm --> HH:MM:SS,mmm
    # We also capture optional styling that might appear on the timestamp line in some SRT variants, though it's rare.
    timestamp_pattern = re.compile(r'(\d{2}:\d{2}:\d{2},\d{3})\s*-->\s*(\d{2}:\d{2}:\d{2},\d{3})(.*)')
    # Basic HTML-like tag removal, common in SRT for formatting
    html_tag_pattern = re.compile(r'<[^>]+>')

    while idx < len(lines):
        line = lines[idx].strip()
        idx += 1

        if not line: # Skip empty lines between cues
            continue

        # Try to parse as a sequence number, then expect timestamp, then text
        if line.isdigit():
            current_sequence_number = line
            if idx < len(lines):
                timestamp_line = lines[idx].strip()
                idx += 1
                timestamp_match = timestamp_pattern.match(timestamp_line)
                
                if timestamp_match:
                    start_time = timestamp_match.group(1)
                    end_time = timestamp_match.group(2)
                    # Trailing content on timestamp line is rare in SRT but handle if present
                    # For SRT, typically text starts on the next line.
                    # styling_info_on_ts_line = timestamp_match.group(3).strip()
                    
                    text_lines = []
                    while idx < len(lines) and lines[idx].strip():
                        text_lines.append(lines[idx].strip())
                        idx += 1
                    
                    if text_lines:
                        full_text = " ".join(text_lines)
                        # Clean common HTML-like tags (e.g., <i>, <b>, <font>)
                        cleaned_text = html_tag_pattern.sub('', full_text).strip()
                        cleaned_text = " ".join(cleaned_text.split()) # Normalize whitespace
                        if cleaned_text:
                            cues.append({
                                "start_time": start_time, 
                                "end_time": end_time, 
                                "text": cleaned_text
                            })
                else:
                    # This wasn't a valid timestamp line after a number, log or handle as malformed
                    logger.debug(f"Malformed SRT? Expected timestamp after number '{current_sequence_number}', got: {timestamp_line}")
                    # Continue to try and find next cue block
            # else: sequence number at EOF
        # else: line is not a number, so not start of a typical SRT block, skip to find next potential block.
        # This makes the parser more robust to malformed SRTs or text files that are not SRTs.

    if not cues and srt_content: # Fallback for very simple SRTs or plain text mistaken for SRT
        # This is a very basic fallback if no structured cues were parsed, 
        # treat the whole content as a single block of text with unknown timing.
        # The original parse_srt was even simpler, just joining lines. This is slightly better.
        logger.warning("Could not parse SRT into structured cues. Falling back to joining non-empty lines.")
        text_only_lines = [html_tag_pattern.sub('', l.strip()) for l in srt_content.splitlines() if l.strip() and not l.strip().isdigit() and '-->' not in l]
        joined_text = " ".join(text_only_lines).strip()
        if joined_text:
            cues.append({"start_time": "00:00:00,000", "end_time": "00:00:00,000", "text": joined_text, "is_fallback": True})

    return cues


def parse_vtt(vtt_content):
    """Parse VTT format subtitles into a list of cue dictionaries.
       Each cue: {"start_time": "HH:MM:SS.mmm", "end_time": "HH:MM:SS.mmm", "text": "cue text"}
    """
    cues = []
    lines = vtt_content.splitlines()
    idx = 0
    current_cue_lines = []
    current_start_time = None
    current_end_time = None

    # Regex to capture VTT timestamp and optional settings on the same line
    # Corrected regex: removed trailing single quote
    timestamp_pattern = re.compile(r'(\d{2}:\d{2}:\d{2}\.\d{3})\s*-->\s*(\d{2}:\d{2}:\d{2}\.\d{3})(.*)')
    # Regex to clean common VTT styling from text lines (basic)
    style_pattern = re.compile(r'(align|line|position|size|vertical):[\w\-%#]+(\s|$)', flags=re.IGNORECASE)

    while idx < len(lines):
        line = lines[idx].strip()
        idx += 1

        if line.startswith('WEBVTT') or line.startswith('NOTE') or not line:
            # For empty lines, if it signifies end of a current cue, process it
            if not line and current_start_time and current_cue_lines:
                full_text = " ".join(current_cue_lines)
                cleaned_text = re.sub(r'<[^>]+>', '', full_text).strip() # Remove HTML-like tags
                cleaned_text = style_pattern.sub('', cleaned_text).strip() # Remove VTT settings
                cleaned_text = " ".join(cleaned_text.split()) # Normalize whitespace
                if cleaned_text:
                    cues.append({
                        "start_time": current_start_time,
                        "end_time": current_end_time,
                        "text": cleaned_text
                    })
                current_start_time = None # Reset for next cue block
                current_end_time = None
                current_cue_lines = []
            continue

        timestamp_match = timestamp_pattern.match(line)

        if timestamp_match:
            # If there was a previous cue, finalize it
            if current_start_time and current_cue_lines:
                full_text = " ".join(current_cue_lines)
                cleaned_text = re.sub(r'<[^>]+>', '', full_text).strip() # Remove HTML-like tags
                cleaned_text = style_pattern.sub('', cleaned_text).strip() # Remove VTT settings
                cleaned_text = " ".join(cleaned_text.split()) # Normalize whitespace
                if cleaned_text:
                    cues.append({
                        "start_time": current_start_time,
                        "end_time": current_end_time,
                        "text": cleaned_text
                    })
            # Start new cue
            current_start_time = timestamp_match.group(1)
            current_end_time = timestamp_match.group(2)
            current_cue_lines = []

            # Check for text on the same line as the timestamp (after styling info)
            trailing_text_on_timestamp_line = timestamp_match.group(3).strip()
            if trailing_text_on_timestamp_line:
                # Remove common VTT settings from this trailing text to isolate actual speech
                # This is a basic removal; more sophisticated parsing of settings could be added if needed
                cleaned_trailing_text = style_pattern.sub('', trailing_text_on_timestamp_line).strip()
                if cleaned_trailing_text:
                    # Further clean HTML-like tags from this line
                    current_cue_lines.append(re.sub(r'<[^>]+>', '', cleaned_trailing_text).strip())
        elif not line and current_start_time: # Empty line signifies end of current cue text
            if current_cue_lines:
                full_text = " ".join(current_cue_lines)
                cleaned_text = re.sub(r'<[^>]+>', '', full_text).strip()
                cleaned_text = style_pattern.sub('', cleaned_text).strip() # Remove VTT settings
                cleaned_text = " ".join(cleaned_text.split()) # Normalize whitespace
                if cleaned_text:
                    cues.append({
                        "start_time": current_start_time,
                        "end_time": current_end_time,
                        "text": cleaned_text
                    })
            current_start_time = None # Reset for next cue block
            current_end_time = None
            current_cue_lines = []

        elif current_start_time: # This is a text line for the current active cue
             # Avoid adding cue numbers as text if they appear on their own line
            if not (line.isdigit() and not current_cue_lines and (idx > 1 and '-->' not in lines[idx-2].strip())):
                current_cue_lines.append(line)

    # Add the last cue if it exists and hasn't been added yet
    if current_start_time and current_cue_lines:
        full_text = " ".join(current_cue_lines)
        cleaned_text = re.sub(r'<[^>]+>', '', full_text).strip()
        cleaned_text = style_pattern.sub('', cleaned_text).strip() # Remove VTT settings
        cleaned_text = " ".join(cleaned_text.split()) # Normalize whitespace
        if cleaned_text:
            cues.append({
                "start_time": current_start_time,
                "end_time": current_end_time,
                "text": cleaned_text
            })

    return cues


def translate_to_english(text, source_lang="fr"):
    # This function is no longer used directly for immediate translation.
    # It can be removed or kept for future direct use if needed.
    if not text:
        return None
    # logger.debug(f"TRANSLATION_PLACEHOLDER: Simulating translation of text from {source_lang} to English.")
    # return f"[TRANSLATED FROM {source_lang.upper()} (Placeholder)] {text}" # Commented out as it's not used
    return None # Explicitly return None if not used


def save_video_data_to_firestore(video_id, metadata, transcript_text_original, transcript_language_original):
    """
    Saves the extracted video metadata and original transcript to Firestore.
    `transcript_text_original` is the transcript in its original detected language.
    `transcript_language_original` is the language code ('en', 'fr', or None).
    """
    if not metadata:
        logger.warning(f"No metadata to save for {video_id}, skipping Firestore save.")
        return

    doc_ref = db.collection('youtube_video_data').document(video_id)
    
    # Prepare transcript text for storage: join cue texts if it's a list of cues
    final_transcript_text_original = transcript_text_original
    if isinstance(transcript_text_original, list): # It will be a list of cues
        final_transcript_text_original = "\n".join([cue['text'] for cue in transcript_text_original if 'text' in cue])

    data_to_store = {
        'video_id': video_id,
        'title': metadata.get('title'),
        'description': metadata.get('description'),
        'upload_date': metadata.get('upload_date'), 
        'uploader': metadata.get('uploader'),
        'uploader_id': metadata.get('uploader_id'),
        'channel_id': metadata.get('channel_id'),
        'channel_url': metadata.get('channel_url'),
        'duration': metadata.get('duration'),
        'duration_string': metadata.get('duration_string'),
        'view_count': metadata.get('view_count'),
        'like_count': metadata.get('like_count'),
        'comment_count': metadata.get('comment_count'),
        'tags': metadata.get('tags'),
        'categories': metadata.get('categories'),
        'thumbnail_url': metadata.get('thumbnail'), 
        'webpage_url': metadata.get('webpage_url', f"https://www.youtube.com/watch?v={video_id}"),
        'original_url': metadata.get('original_url'),
        
        'transcript_text_original': final_transcript_text_original, # Use the processed text
        'transcript_language_original': transcript_language_original,
        # Store structured cues as well, if available
        'transcript_cues_original': transcript_text_original if isinstance(transcript_text_original, list) else None,
        
        'raw_yt_dlp_json_snippet': json.dumps(metadata, indent=2)[:2000], 
        'ingested_at': firestore.SERVER_TIMESTAMP,
        # Flag to indicate if translation might be needed by a downstream process
        'needs_translation': bool(transcript_language_original and transcript_language_original != 'en')
    }
    # Removed old fields: transcript_en, translation_needed_review, raw_french_transcript_for_storage

    try:
        doc_ref.set(data_to_store, merge=True) 
        logger.info(f"Successfully saved data for video {video_id} to Firestore.")
    except Exception as e:
        logger.error(f"Error saving video {video_id} to Firestore: {e}")

if __name__ == "__main__":
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

    # Original test_video_ids for reference, now replaced by file input
    # test_video_ids = [
    #     "d3N0ZDXKsgM", 
    #     "CzFuP6m_Kds",
    #     "ZbK2Ep6SJUk",
    #     "tRP0E9D7O4A",
    #     "i7YwmbT-r4E",
    #     "NqWC7V6ZiOE",
    #     "CB4hv9yetnI",
    #     "ELr2-P1SmhM",
    #     "0c-2oLTO6hI" 
    # ]

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