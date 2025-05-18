import os
import requests
import firebase_admin
from firebase_admin import credentials, firestore
import logging
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# --- Logger Setup ---
logging.basicConfig(level=logging.INFO,
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
API_TOKEN = os.getenv('CIVICS_PROJECT_API_TOKEN')

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
            logger.debug(f"Original uniqueID path ('{path_str_from_unique_id}') has even segments. Appended '/_self_'. New path for doc: {path_str_for_doc}")
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
                logger.debug(f"Updated representative document for path: {full_doc_path} (Original API uniqueID: '{unique_id_raw}')")
            else:
                doc_ref.set(rep_data_with_timestamp)
                added_count += 1
                logger.debug(f"Added new representative document for path: {full_doc_path} (Original API uniqueID: '{unique_id_raw}')")

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

# --- Main execution ---
if __name__ == "__main__":
    logger.info("Starting Civics Project Representatives Ingestion Script...")
    
    representatives = fetch_representatives_data()

    if representatives is not None:
        added, updated, skipped = upsert_representatives_to_firestore(representatives)
        if skipped > 0 and (added == 0 and updated == 0) : # If all were skipped and none processed
             logger.error("Critical: All representatives were skipped during Firestore operation. Check logs for details.")
             exit(1) # Exit with error if all records failed to process
    else:
        logger.error("Failed to fetch representative data from API. Exiting.")
        exit(1) # Exit with error if API fetch fails critically

    logger.info("Civics Project Representatives ingestion script finished.")
    logger.info("Note for future improvement: Consider implementing logic to handle representatives removed from the API, e.g., by comparing with existing Firestore data and deleting stale records.") 