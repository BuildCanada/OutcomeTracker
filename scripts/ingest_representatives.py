import os
import requests
import firebase_admin
from firebase_admin import credentials, firestore
import logging
from dotenv import load_dotenv
from datetime import datetime, date
from dateutil.parser import parse as parse_date
import re

# Load environment variables from .env file
load_dotenv()

# --- Logger Setup ---
logging.basicConfig(level=logging.DEBUG,
                    format='%(asctime)s - %(levelname)s - %(filename)s:%(lineno)d - %(message)s',
                    datefmt='%Y-%m-%d %H:%M:%S')
logger = logging.getLogger(__name__)
# --- End Logger Setup ---

# --- Firebase Configuration ---
db = None # Initialize db to None
if not firebase_admin._apps: # Check if app is already initialized
    # Check for emulator host first
    if os.getenv('FIRESTORE_EMULATOR_HOST'):
        options = {'projectId': os.getenv('FIREBASE_PROJECT_ID', 'promisetrackerapp')}
        try:
            firebase_admin.initialize_app(options=options)
            logger.info(f"Python (Civics Ingest): Connected to Firestore Emulator at {os.getenv('FIRESTORE_EMULATOR_HOST')} using project ID '{options['projectId']}'")
            db = firestore.client()
        except Exception as e:
            logger.critical(f"Python (Civics Ingest): Firebase emulator initialization failed: {e}", exc_info=True)
            exit("Exiting: Firebase emulator connection failed.")
    else:
        # Connect to Cloud Firestore
        if not os.getenv('GOOGLE_APPLICATION_CREDENTIALS'):
            logger.critical("CRITICAL: GOOGLE_APPLICATION_CREDENTIALS environment variable not set.")
            logger.critical("CRITICAL: This is required for authentication with Google Cloud Firestore.")
            exit("Exiting: GOOGLE_APPLICATION_CREDENTIALS not set.")
        try:
            firebase_admin.initialize_app()
            project_id = os.getenv('FIREBASE_PROJECT_ID', '[Not Set]')
            logger.info(f"Python (Civics Ingest): Connected to CLOUD Firestore using Application Default Credentials (Project: {project_id}).")
            db = firestore.client()
        except Exception as e:
            logger.critical(f"Python (Civics Ingest): Firebase initialization failed for Google Cloud Firestore: {e}", exc_info=True)
            exit("Exiting: Firebase connection failed.")
else:
    logger.info("Python (Civics Ingest): Firebase app already initialized. Getting client.")
    db = firestore.client()

# Final check if db is assigned
if db is None:
    logger.critical("CRITICAL: Python (Civics Ingest): Failed to obtain Firestore client. Exiting.")
    exit("Exiting: Firestore client not available.")
# --- End Firestore Configuration ---

API_URL = "https://api.civicsproject.org/region/canada/representatives"
API_TOKEN = os.getenv('CIVICS_PROJECT_API_TOKEN') # provided by civics project / Mikaal Naik

# --- Helper: Load department_config and build name variant mapping ---
def load_department_config():
    logger.info("Loading department_config collection for name variant mapping...")
    dep_configs = db.collection('department_config').stream()
    variant_to_dept = {}
    dept_id_to_name = {}
    for doc in dep_configs:
        data = doc.to_dict()
        dept_id = doc.id
        dept_name = data.get('official_full_name', dept_id)
        dept_id_to_name[dept_id] = dept_name
        name_variants = data.get('name_variants', [])
        # Always include the department's official name as a variant
        all_variants = set(name_variants)
        all_variants.add(dept_name)
        for variant in all_variants:
            if isinstance(variant, str) and variant.strip():
                variant_to_dept[variant.strip().lower()] = dept_id
    logger.info(f"Loaded {len(variant_to_dept)} department name variants.")
    return variant_to_dept, dept_id_to_name

# --- Helper: Load Parliament Sessions ---
def load_parliament_sessions(db_client):
    logger.info("Loading parliament_session collection...")
    sessions = []
    try:
        sessions_ref = db_client.collection('parliament_session')
        for doc in sessions_ref.stream():
            data = doc.to_dict()
            try:
                start_date_str = data.get('start_date')
                end_date_str = data.get('end_date')
                election_called_date_str = data.get('election_called_date') # Get election_called_date
                parliament_num = data.get('parliament_number')

                if not start_date_str or not parliament_num:
                    logger.warning(f"Session {doc.id} is missing start_date or parliament_number. Skipping.")
                    continue

                parsed_start_date = parse_date(start_date_str).date()
                
                parsed_election_called_date = None
                if election_called_date_str:
                    try:
                        # Ensure it's a string before parsing, handle potential direct date objects if Firestore ever returns them
                        parsed_election_called_date = parse_date(str(election_called_date_str)).date()
                    except Exception as e_ec:
                        logger.warning(f"Could not parse election_called_date '{election_called_date_str}' (type: {type(election_called_date_str)}) for session {doc.id}: {e_ec}")

                # Handle 'current' for end_date_str
                if end_date_str and isinstance(end_date_str, str) and end_date_str.lower() == 'current':
                    parsed_end_date = None
                else:
                    parsed_end_date = parse_date(end_date_str).date() if end_date_str else None
                
                sessions.append({
                    'id': doc.id,
                    'parliament_number': str(parliament_num),
                    'start_date': parsed_start_date,
                    'end_date': parsed_end_date,
                    'election_called_date': parsed_election_called_date, # Store parsed date
                    'is_current_for_tracking': data.get('is_current_for_tracking', False)
                })
            except Exception as e:
                logger.error(f"Error parsing session data for doc {doc.id}: {e}", exc_info=True)
        # Sort by start_date descending (newest first)
        sessions.sort(key=lambda s: s['start_date'], reverse=True)
        logger.info(f"Loaded and sorted {len(sessions)} parliament sessions.")
    except Exception as e:
        logger.error(f"Failed to load parliament_session collection: {e}", exc_info=True)
    return sessions

# --- Helper: Parliament number extraction from parliamentaryPosition ---
def extract_parliament_number(position, sorted_parliament_sessions):
    # HACK: Assume positions starting on 2025-05-13 are for the 45th Parliament
    # pos_from_hack_check = position.get('from')
    # if pos_from_hack_check and pos_from_hack_check.startswith('2025-05-13'):
    #     logger.info(f"HACK: Assigning parliament number '45' to position '{position.get('title')}' starting on {pos_from_hack_check}.")
    #     return "45"

    # 1. Try to extract parliament number directly from the position object
    parliament_num_direct = position.get('parliamentNumber') or position.get('parliament_number')
    if parliament_num_direct is not None:
        # logger.debug(f"Found parliament number at top level: {parliament_num_direct} for position '{position.get('title')}'")
        return str(parliament_num_direct)

    caucus_roles = position.get('caucusRoles', [])
    if caucus_roles:
        for role_idx, role in enumerate(caucus_roles):
            if role and role.get('parliament') is not None:
                parliament_in_role = role.get('parliament')
                # logger.debug(f"Found parliament number in caucusRoles[{role_idx}]: {parliament_in_role} for position '{position.get('title')}'")
                return str(parliament_in_role)

    # 2. If not found directly, use date-based overlap logic with sorted_parliament_sessions
    pos_from_str = position.get('from')
    pos_to_str = position.get('to')

    if not pos_from_str:
        # logger.debug(f"Position '{position.get('title')}' missing 'from' date. Cannot determine parliament number by date.")
        return ""

    try:
        pos_start_date = parse_date(pos_from_str).date()
        # If pos_to_str is None or empty, it's an ongoing position. Use a very future date for open-ended comparison.
        pos_end_date = parse_date(pos_to_str).date() if pos_to_str else date.max
    except Exception as e:
        logger.warning(f"Could not parse dates for position '{position.get('title')}' (from: {pos_from_str}, to: {pos_to_str}): {e}. Cannot determine parliament by date.")
        return ""

    for sess in sorted_parliament_sessions:
        sess_start_for_calc = sess['start_date']
        # Use election_called_date if it's available and earlier than the official start_date,
        # making the session's effective window for matching positions start earlier.
        if sess.get('election_called_date') and sess['election_called_date'] < sess['start_date']:
            sess_start_for_calc = sess['election_called_date']
            logger.debug(f"For session {sess['id']} (Parl {sess['parliament_number']}), using election_called_date {sess_start_for_calc} as effective start for matching (actual start: {sess['start_date']}).")

        sess_end_for_calc = sess['end_date'] if sess['end_date'] is not None else date.max
        
        # Check for overlap: max(start1, start2) <= min(end1, end2)
        overlap_start = max(pos_start_date, sess_start_for_calc)
        overlap_end = min(pos_end_date, sess_end_for_calc)

        if overlap_start <= overlap_end:
            logger.debug(f"Position '{position.get('title')}' (active {pos_start_date} to {'Ongoing' if not pos_to_str else pos_end_date}) "
                         f"assigned parliament {sess['parliament_number']} from session '{sess['id']}' (effective range {sess_start_for_calc} to {'Ongoing' if not sess['end_date'] else sess_end_for_calc})")
            return sess['parliament_number']

    logger.debug(f"Position '{position.get('title')}' (active {pos_start_date} to {'Ongoing' if not pos_to_str else pos_end_date}) did not overlap with any loaded parliament sessions.")
    return ""

# --- API Fetch ---
def fetch_representatives_data():
    """Fetches representative data from the Civics Project API."""
    if not API_TOKEN:
        logger.critical("CIVICS_PROJECT_API_TOKEN environment variable not set.")
        return None

    headers = {
        "Authorization": f"Bearer {API_TOKEN}"
    }
    logger.info(f"Fetching data from API: {API_URL}")
    try:
        response = requests.get(API_URL, headers=headers, timeout=30) # Added timeout
        response.raise_for_status()  # Raises an HTTPError for bad responses (4XX or 5XX)
        logger.info(f"Successfully fetched data from API. Status: {response.status_code}")
        data = response.json()
        if isinstance(data, list): # Check if the response is a list as expected
            logger.info(f"Fetched {len(data)} representatives from the API.")
            return data
        else: # Handle unexpected API response format
            logger.error(f"API response was not in the expected list format. Response: {data}")
            return None
    except requests.exceptions.HTTPError as e:
        logger.error(f"HTTP error occurred during API request: {e.response.status_code} - {e.response.text}", exc_info=True)
    except requests.exceptions.RequestException as e:
        logger.error(f"Error during API request: {e}", exc_info=True)
    except ValueError as e: # Catch JSON decoding errors
        logger.error(f"Error decoding JSON response from API: {e}", exc_info=True)
    return None

# --- Upsert to members ---
def upsert_representatives_to_firestore(representatives_data):
    """Upserts representative data to the 'members' collection in Firestore."""
    if not representatives_data:
        logger.info("No representative data to process.")
        return 0, 0, 0 # added, updated, skipped

    members_collection = db.collection('members')
    added_count = 0
    updated_count = 0
    skipped_count = 0

    logger.info(f"Starting Firestore upsert for {len(representatives_data)} representatives.")

    for rep_data in representatives_data:
        unique_id_raw = rep_data.get('uniqueID')

        if not isinstance(unique_id_raw, str) or not unique_id_raw.strip():
            logger.warning(f"Skipping representative due to missing, empty, or non-string 'uniqueID'. Name: {rep_data.get('name', 'N/A')}")
            skipped_count += 1
            continue

        # Sanitize the uniqueID: remove trailing slashes and ensure it's not just invalid chars like '.' or '..'
        # Firestore document IDs cannot end with a forward slash.
        # Also, path segments like "." or ".." are invalid.
        # We split by '/', filter invalid parts, and rejoin. This also handles cases like "a//b" -> "a/b".
        parts = [part for part in unique_id_raw.split('/') if part.strip() and part != '.' and part != '..']
        
        if not parts: # If all parts were invalid or empty
            logger.warning(f"Skipping representative. 'uniqueID' '{unique_id_raw}' resulted in an empty path after sanitization. Name: {rep_data.get('name', 'N/A')}")
            skipped_count += 1
            continue
        
        # Reconstruct the sanitized unique_id path string
        path_str_from_unique_id = "/".join(parts)

        if not path_str_from_unique_id: # Should have been caught by `if not parts:` but as a safeguard.
             logger.warning(f"Skipping representative. Sanitized 'uniqueID' from '{unique_id_raw}' is empty. Name: {rep_data.get('name', 'N/A')}")
             skipped_count += 1
             continue

        # If the number of segments in path_str_from_unique_id is EVEN,
        # the full path (e.g., "members/segment1/segment2") would be ODD,
        # which is a path to a collection. To make it a document path,
        # we append a canonical segment like "_self_".
        if len(parts) % 2 == 0: 
            path_str_for_doc = f"{path_str_from_unique_id}/_self_"
            #logger.debug(f"Original uniqueID path ('{path_str_from_unique_id}') has even segments. Appended '/_self_'. New path for doc: {path_str_for_doc}")
        else:
            path_str_for_doc = path_str_from_unique_id

        try:
            # Construct the full path to the document
            full_doc_path = f"members/{path_str_for_doc}"
            doc_ref = db.document(full_doc_path)
            doc_snapshot = doc_ref.get()

            # Add ingestion timestamp
            rep_data_with_timestamp = {**rep_data, "ingested_at": firestore.SERVER_TIMESTAMP, "last_updated_at": firestore.SERVER_TIMESTAMP}

            if doc_snapshot.exists:
                doc_ref.set(rep_data_with_timestamp, merge=True) 
                updated_count += 1
               #logger.debug(f"Updated representative document for path: {full_doc_path} (Original API uniqueID: '{unique_id_raw}')")
            else:
                doc_ref.set(rep_data_with_timestamp)
                added_count += 1
                #logger.debug(f"Added new representative document for path: {full_doc_path} (Original API uniqueID: '{unique_id_raw}')")

        except Exception as e:
            logger.error(f"Error upserting representative (path: {full_doc_path}, original API uniqueID: '{unique_id_raw}') to Firestore: {e}", exc_info=True)
            skipped_count += 1
            # Optionally, re-raise or exit if a Firestore error is critical
            # exit(1) 

    logger.info(f"Finished Firestore upsert.")
    logger.info(f"  - Added: {added_count} new representative documents.")
    logger.info(f"  - Updated: {updated_count} existing representative documents.")
    logger.info(f"  - Skipped: {skipped_count} representatives.")
    return added_count, updated_count, skipped_count

# --- Build/Update department_ministers ---
def build_department_ministers(representatives_data, variant_to_dept, dept_id_to_name, parliament_sessions):
    """Builds/updates the department_ministers flat collection."""
    logger.info("Starting build_department_ministers.")
    if not representatives_data:
        logger.info("No representative data to process for department_ministers.")
        return 0, 0
    ministers_collection = db.collection('department_ministers')
    upserted = 0
    skipped = 0
    # Define the cutoff date for filtering positions
    cutoff_date = datetime(2021, 11, 22).date()

    for rep in representatives_data:
        member_id = rep.get('id') or rep.get('uniqueID') # Prioritize 'id' if available
        if not member_id: # Ensure we have a member_id
            logger.warning(f"Representative missing 'id' and 'uniqueID'. Name: {rep.get('name', 'N/A')}. Skipping for department_ministers.")
            continue

        first_name = rep.get('firstName')
        last_name = rep.get('lastName')
        full_name = f"{first_name} {last_name}".strip() if first_name or last_name else rep.get('name', '')
        party = rep.get('party')
        api_unique_id = rep.get('uniqueID') # This is the original uniqueID from API, may not be member_id
        avatar_url = rep.get('avatarUrl') if rep.get('avatarUrl') else None
        parliamentary_positions = rep.get('parliamentaryPositions', [])
        
        if not parliamentary_positions:
            # logger.debug(f"No parliamentaryPositions for {full_name} ({member_id}). Skipping representative for department_ministers build.")
            continue

        # logger.debug(f"Processing positions for {full_name} ({member_id}). Found {len(parliamentary_positions)} positions.")

        for pos_index, pos in enumerate(parliamentary_positions):
            title = pos.get('title')
            # logger.debug(f"Processing position {pos_index} for {full_name}: Title='{title}'")
            if not title:
                # logger.debug(f"  Skipping position {pos_index} for {full_name}: Title is missing or empty.")
                skipped += 1
                continue

            # --- Date Check (Skip if ended before cutoff) ---
            position_end_str = pos.get('to')
            if position_end_str:
                try:
                    # Use dateutil.parser.parse to handle various date string formats
                    position_end_date_obj = parse_date(position_end_str).date()
                    if position_end_date_obj < cutoff_date:
                        # logger.debug(f"  Skipping position {pos_index} for {full_name} ('{title}'): Position ended before {cutoff_date} (End Date: {position_end_str}).")
                        skipped += 1
                        continue
                except Exception as e:
                    logger.warning(f"  Could not parse or check position end date '{position_end_str}' for {full_name} ('{title}'): {e}. Not skipping based on date.", exc_info=True)
            # --- End Date Check ---

            parliament_number = extract_parliament_number(pos, parliament_sessions) # Pass sessions
            if not parliament_number:
                # logger.debug(f"  Skipping position {pos_index} for {full_name} ('{title}'): Parliament number is missing or empty after all checks.")
                skipped += 1
                continue
            # logger.debug(f"  Extracted/Derived parliament number: {parliament_number}")

            position_start_str = pos.get('from')
            if not position_start_str:
                 # logger.debug(f"  Skipping position {pos_index} for {full_name} ('{title}'): Position start date is missing.")
                 skipped += 1
                 continue
            
            # Attempt department match (for data inclusion, not skipping)
            cleaned_title = title.strip().lower()
            logger.debug(f"  Attempting to match title: '{title}' (cleaned: '{cleaned_title}') for member {full_name} (Parl: {parliament_number}) to a departmentId.")
            dept_id = variant_to_dept.get(cleaned_title)
            dept_name_from_config = None # Initialize
            
            if dept_id:
                dept_name_from_config = dept_id_to_name.get(dept_id, None)
                logger.info(f"    MATCHED: Title '{title}' mapped to dept_id='{dept_id}', dept_name='{dept_name_from_config}' for member {full_name} (Parl: {parliament_number})")
            else:
                logger.warning(f"    NO MATCH: Title '{title}' (cleaned: '{cleaned_title}') did not map to any departmentId for member {full_name} (Parl: {parliament_number}). departmentId will be null.")
                # Log some of the available variants for debugging if the dictionary is small
                if len(variant_to_dept) < 30: # Increased limit slightly for more debug info
                    logger.debug(f"    Available variant keys for matching (first {len(variant_to_dept)} of {len(variant_to_dept)}): {list(variant_to_dept.keys())}")
                else:
                    logger.debug(f"    Not logging all {len(variant_to_dept)} variant keys. Total variants: {len(variant_to_dept)}. Check department_config collection and script logs for load_department_config output.")
            
            # Construct doc ID and data
            try:
                 # Sanitize characters that might be problematic in Firestore IDs
                 safe_position_start_str = position_start_str.replace(' ','_').replace(':','_').replace('.','_').replace('+','_').replace('/','_') # Added /
                 # Ensure the ID doesn't start or end with invalid characters or contain ".." "//"
                 safe_position_start_str = "_".join(filter(None, safe_position_start_str.split('_')))
                 
                 # Ensure member_id is a string for doc_id construction
                 member_id_str = str(member_id)


                 # Use a consistent and unique doc_id construction
                 doc_id_parts = [
                     member_id_str,
                     parliament_number, # Already a string or empty
                     safe_position_start_str,
                     str(pos_index) # Ensure uniqueness if other parts are identical for multiple positions
                 ]
                 doc_id = "_".join(filter(None, doc_id_parts)) # Filter out empty strings before joining

                 # Further sanitize to Firestore allowed characters
                 allowed_chars_pattern = re.compile(r'[^a-zA-Z0-9_.~-]')
                 doc_id = allowed_chars_pattern.sub('', doc_id)
                 
                 if not doc_id or doc_id.startswith('.') or doc_id.startswith('-') or len(doc_id) > 1500: # Firestore ID length limit
                     logger.warning(f"Generated invalid or too long doc_id '{doc_id}' for {full_name} pos {pos_index}. Skipping.")
                     skipped += 1
                     continue

            except Exception as e:
                 logger.error(f"Error creating doc_id for position {pos_index} for {full_name} ('{title}'): {e}", exc_info=True)
                 skipped += 1
                 continue
            
            # Position end can be None, ensure it's stored as such
            final_position_end = parse_date(position_end_str).isoformat() if position_end_str else None
            final_position_start = parse_date(position_start_str).isoformat() if position_start_str else None


            doc_data = {
                "departmentId": dept_id, 
                "departmentName": dept_name_from_config,
                "parliamentNumber": parliament_number,
                "ministerMemberId": member_id_str, # Ensure it's a string
                "firstName": first_name,
                "lastName": last_name,
                "fullName": full_name,
                "party": party,
                "apiUniqueID": api_unique_id, # Store the original uniqueID from API
                "avatarUrl": avatar_url,
                "title": title,
                "positionStart": final_position_start,
                "positionEnd": final_position_end,
                "memberDocPath": f"members/{api_unique_id}" if api_unique_id else None, # Path based on API uniqueID
                "source": "civics-api",
                "created_at": firestore.SERVER_TIMESTAMP,
                "updated_at": firestore.SERVER_TIMESTAMP
            }
            # logger.debug(f"  Attempting to upsert doc: {doc_id} for minister {full_name}, title '{title}'")

            try:
                ministers_collection.document(doc_id).set(doc_data, merge=True)
                upserted += 1
                # logger.info(f"  Successfully upserted department_minister doc: {doc_id} for {full_name} - {title}")
            except Exception as e:
                logger.error(f"Error upserting department_ministers doc {doc_id} for {full_name} ('{title}'): {e}", exc_info=True)
                skipped += 1

    logger.info(f"Finished department_ministers upsert. Upserted: {upserted}, Skipped: {skipped}")
    return upserted, skipped

# --- Main execution ---
if __name__ == "__main__":
    logger.info("Starting Civics Project Representatives Ingestion Script...")
    
    # Load parliament sessions once
    parliament_sessions_data = load_parliament_sessions(db)
    if not parliament_sessions_data:
        logger.warning("No parliament session data loaded. Parliament number derivation by date will not be possible.")
        # Decide if this is critical enough to exit, or proceed with only direct extraction
        # exit(1) 

    representatives = fetch_representatives_data()

    if representatives is not None:
        added, updated, skipped_members_upsert = upsert_representatives_to_firestore(representatives)
        variant_to_dept, dept_id_to_name = load_department_config()
        
        # Pass parliament_sessions_data to build_department_ministers
        upserted_ministers, skipped_ministers_build = build_department_ministers(representatives, variant_to_dept, dept_id_to_name, parliament_sessions_data)
        
        if skipped_members_upsert > 0 and (added == 0 and updated == 0) : 
             logger.error("Critical: All representatives were skipped during 'members' collection Firestore operation. Check logs for details.")
             # exit(1) # Optionally exit if this is critical
    else:
        logger.error("Failed to fetch representative data from API. Exiting.")
        exit(1)

    logger.info("Civics Project Representatives ingestion script finished.")
    # logger.info("Note for future improvement: Consider implementing logic to handle representatives removed from the API, e.g., by comparing with existing Firestore data and deleting stale records.")