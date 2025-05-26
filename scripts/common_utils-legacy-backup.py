# common_utils.py
import logging
import os
import firebase_admin
from firebase_admin import credentials, firestore
from google.cloud.firestore_v1.base_query import FieldFilter
from dotenv import load_dotenv
import hashlib # For content hashing
from datetime import datetime # For date parsing

# --- Load Environment Variables (for Firestore init if needed) ---
load_dotenv() # Loads .env file from current dir or parent dirs
# --- End Load Environment Variables ---

logger = logging.getLogger(__name__) 

# --- Begin: Constants for Promise ID and Path Generation ---
TARGET_PROMISES_COLLECTION_ROOT = os.getenv("TARGET_PROMISES_COLLECTION", "promises")
DEFAULT_REGION_CODE = "Canada"

PARTY_NAME_TO_CODE_MAPPING = {
    "Liberal Party of Canada": "LPC",
    "Liberal Party of Canada (2025 Platform)": "LPC", # Added variation
    "Conservative Party of Canada": "CPC",
    "New Democratic Party": "NDP",
    "Bloc Québécois": "BQ",
    # Add other variations as observed in your 'party' field
}

SOURCE_TYPE_TO_ID_CODE_MAPPING = {
    "Video Transcript (YouTube)": "YTVID",
    "Mandate Letter Commitment (Structured)": "MANDL",
    "2021 LPC Mandate Letters": "MANDL",
    "2025 LPC Platform": "PLTFM",
    # Add more as needed
    "DEFAULT_SOURCE_ID_CODE": "OTHER" # Fallback code
}
# --- End: Constants for Promise ID and Path Generation ---

PROMISE_CATEGORIES = [
    "Finance", "Health", "Immigration", "Defence", "Housing", "Energy",  
    "Innovation", "Government", "Environment",
    "Indigenous Relations", "Foreign Affairs", "Other" 
]

# --- Firestore Client Initialization ---
# Global Firestore client instance for this module
db = None

def _initialize_firestore_client():
    """Initializes the global Firestore client if not already done."""
    global db
    if db is None:
        try:
            if not firebase_admin._apps:
                logger.info("Initializing Firebase Admin SDK for common_utils...")
                # Attempt to initialize with application default credentials first 
                try:
                    firebase_admin.initialize_app()
                    project_id = os.getenv('FIREBASE_PROJECT_ID', '[Not Set - Using Default]')
                    logger.info(f"common_utils: Connected to CLOUD Firestore (Project: {project_id}) using default credentials.")
                except Exception as e_default:
                    logger.warning(f"common_utils: Cloud Firestore init with default creds failed: {e_default}")
                    cred_path = os.getenv('FIREBASE_SERVICE_ACCOUNT_KEY_PATH')
                    if cred_path:
                        try:
                            logger.info(f"common_utils: Attempting Firebase init with service account key from env var: {cred_path}")
                            cred = credentials.Certificate(cred_path)
                            firebase_admin.initialize_app(cred)
                            project_id_sa = os.getenv('FIREBASE_PROJECT_ID', '[Not Set - Using Service Account]')
                            logger.info(f"common_utils: Connected to CLOUD Firestore (Project: {project_id_sa}) via service account.")
                        except Exception as e_sa:
                            logger.critical(f"common_utils: Firebase init with service account key from {cred_path} failed: {e_sa}", exc_info=True)
                            raise  # Re-raise critical error
                    else:
                        logger.error("common_utils: FIREBASE_SERVICE_ACCOUNT_KEY_PATH env var not set and default creds failed. Firestore client not initialized.")
                        raise ConnectionError("Failed to initialize Firestore: No credentials provided.")
            else:
                 logger.info("common_utils: Firebase Admin SDK already initialized elsewhere.")
            db = firestore.client()
        except Exception as e:
            logger.critical(f"common_utils: CRITICAL - Failed to initialize Firestore client: {e}", exc_info=True)
            db = None # Ensure db is None on failure
            # Depending on application needs, this might need to be a fatal error.
            # For now, functions will check if db is None.

# Call initialization once when the module is loaded, or rely on first function call.
# _initialize_firestore_client() # Option 1: Initialize on module load

# --- Department Standardization Functions (Firestore-backed) ---

def standardize_department_name(name_variant):
    """Standardizes a department or minister name to its official full name using Firestore department_config."""
    global db
    if db is None: # Option 2: Initialize on first use if not done on module load
        _initialize_firestore_client()
        if db is None: # Check again after attempt
            logger.error("standardize_department_name: Firestore client is not available. Cannot proceed.")
            return None

    original_name_str = str(name_variant).strip()
    normalized_name = original_name_str.lower().strip()

    if not normalized_name or normalized_name == 'nan':
         logger.debug(f"Input '{original_name_str}' normalized to empty or NaN, returning None.")
         return None 

    try:
        dept_config_ref = db.collection('department_config')
        # 1. Try name_variants
        query = dept_config_ref.where(filter=FieldFilter('name_variants', 'array_contains', normalized_name)).limit(1)
        results = list(query.stream()) # Using list() to execute and get results easily
        if results:
            department_doc = results[0].to_dict()
            official_full_name = department_doc.get('official_full_name')
            if official_full_name:
                logger.debug(f"Standardized '{original_name_str}' (Normalized: '{normalized_name}') to '{official_full_name}' via name_variants.")
                return official_full_name
        # 2. Try official_full_name (case-insensitive, exact match)
        query2 = dept_config_ref.where(filter=FieldFilter('official_full_name', '==', original_name_str)).limit(1)
        results2 = list(query2.stream())
        if results2:
            department_doc = results2[0].to_dict()
            official_full_name = department_doc.get('official_full_name')
            if official_full_name:
                logger.debug(f"Standardized '{original_name_str}' to '{official_full_name}' via official_full_name (case-sensitive match).")
                return official_full_name
        # 3. Try official_full_name (lowercase match)
        for doc in dept_config_ref.stream():
            doc_dict = doc.to_dict()
            if doc_dict.get('official_full_name', '').lower() == normalized_name:
                logger.debug(f"Standardized '{original_name_str}' to '{doc_dict.get('official_full_name')}' via official_full_name (lowercase match).")
                return doc_dict.get('official_full_name')
        logger.warning(f"Unmapped department variant: '{normalized_name}' (for input '{original_name_str}') in Firestore department_config.")
        _log_unmapped_variant(original_name_str, normalized_name)
        return None
    except Exception as e:
        logger.error(f"Error querying Firestore for department standardization of '{normalized_name}': {e}", exc_info=True)
        # Log unmapped variant on error too, as it might be a persistent issue
        _log_unmapped_variant(original_name_str, normalized_name)
        return None

def _log_unmapped_variant(raw_variant, normalized_variant, source_promise_id=None):
    """Logs an unmapped department variant to the 'unmapped_department_activity' collection."""
    global db
    if db is None:
        logger.error("_log_unmapped_variant: Firestore client is not available. Cannot log unmapped variant.")
        return

    try:
        # Use the normalized_variant as the document ID for easy lookup and aggregation
        # Firestore IDs have limitations, so replace problematic characters if any (though unlikely for dept names)
        doc_id = normalized_variant.replace('/', '_SLASH_') # Basic sanitization for document ID
        
        activity_ref = db.collection('unmapped_department_activity').document(doc_id)
        
        # Atomically increment count and update timestamps
        # We use a transaction to safely read-modify-write.
        @firestore.transactional
        def update_in_transaction(transaction, doc_ref):
            snapshot = doc_ref.get(transaction=transaction)
            current_server_time = firestore.SERVER_TIMESTAMP

            if snapshot.exists:
                new_count = snapshot.get('count') + 1
                example_ids = snapshot.get('example_source_identifiers') or []
                if source_promise_id and source_promise_id not in example_ids and len(example_ids) < 10: # Limit array size
                    example_ids.append(source_promise_id)
                
                transaction.update(doc_ref, {
                    'count': new_count,
                    'last_seen_at': current_server_time,
                    'variant_text_raw': raw_variant, # Update raw text in case it differs slightly but normalizes the same
                    'example_source_identifiers': example_ids
                })
            else:
                example_ids = [source_promise_id] if source_promise_id else []
                transaction.set(doc_ref, {
                    'variant_text_raw': raw_variant,
                    'variant_text_normalized': normalized_variant,
                    'count': 1,
                    'first_seen_at': current_server_time,
                    'last_seen_at': current_server_time,
                    'status': 'new', # Initial status
                    'example_source_identifiers': example_ids,
                    'notes': ''
                })
        
        transaction = db.transaction()
        update_in_transaction(transaction, activity_ref)
        logger.info(f"Logged/updated unmapped variant activity for: '{normalized_variant}' (Raw: '{raw_variant}')")

    except Exception as e:
        logger.error(f"Error logging unmapped variant '{normalized_variant}': {e}", exc_info=True)

def get_department_short_name(standardized_full_name):
    """
    Takes a standardized FULL department name and returns its display_short_name from Firestore department_config.
    Returns the short name string, or the input full name if no short name is mapped.
    """
    global db
    if db is None: # Option 2: Initialize on first use
        _initialize_firestore_client()
        if db is None: # Check again after attempt
            logger.error("get_department_short_name: Firestore client is not available. Cannot proceed.")
            return standardized_full_name # Fallback as per original spec

    if not standardized_full_name:
        logger.debug("Input standardized_full_name is empty, returning None.")
        return None 
        
    try:
        dept_config_ref = db.collection('department_config')
        query = dept_config_ref.where(filter=FieldFilter('official_full_name', '==', standardized_full_name)).limit(1)
        results = list(query.stream())

        if results:
            department_doc = results[0].to_dict()
            display_short_name = department_doc.get('display_short_name')
            if display_short_name:
                logger.debug(f"Retrieved short name '{display_short_name}' for full name '{standardized_full_name}' from Firestore.")
                return display_short_name
            else:
                logger.warning(f"Found doc for '{standardized_full_name}' but 'display_short_name' is missing. Doc ID: {results[0].id}. Returning full name.")
                return standardized_full_name # Fallback
        else:
            logger.warning(f"No short name mapping found in Firestore department_config for full name: '{standardized_full_name}'. Returning full name.")
            return standardized_full_name # Fallback as per original spec
    except Exception as e:
        logger.error(f"Error querying Firestore for department short name of '{standardized_full_name}': {e}", exc_info=True)
        return standardized_full_name # Fallback

# --- Begin: Helper Functions for Promise ID and Path Generation ---
def generate_content_hash(text: str, length: int = 10) -> str:
    """Generates a truncated SHA-256 hash of the input text."""
    if not text:
        logger.warning("generate_content_hash received empty text, returning unique 'nohash' placeholder.")
        # Return a unique placeholder if text is empty to avoid collisions on empty strings
        return "nohash" + datetime.utcnow().strftime("%Y%m%d%H%M%S%f")[-length:] 
        
    normalized_text = text.lower().strip()
    # Consider more aggressive normalization (e.g., remove punctuation, multiple spaces) 
    # for better deduplication if strictly identical promises should have identical hashes.
    # Example:
    # import re
    # normalized_text = re.sub(r'\s+', ' ', normalized_text) # Replace multiple spaces with one
    # normalized_text = re.sub(r'[^a-z0-9\s-]', '', normalized_text) # Keep alphanumeric, spaces, hyphens

    hasher = hashlib.sha256()
    hasher.update(normalized_text.encode('utf-8'))
    return hasher.hexdigest()[:length]

def get_promise_document_path(
    party_name_str: str,
    date_issued_str: str, # Expected format YYYY-MM-DD
    source_type_str: str,
    promise_text: str,
    target_collection_root: str = TARGET_PROMISES_COLLECTION_ROOT,
    region_code: str = DEFAULT_REGION_CODE
) -> str | None:
    """
    Constructs the full Firestore document path for a promise based on its attributes.
    Returns the path string or None if critical information is missing or invalid.
    """
    # 1. Get Party Code
    party_code = PARTY_NAME_TO_CODE_MAPPING.get(party_name_str)
    if not party_code:
        # Fallback for party if direct match fails (e.g. "Liberal Party of Canada (2025 Platform)")
        for key, value in PARTY_NAME_TO_CODE_MAPPING.items():
            if party_name_str and key in party_name_str:
                party_code = value
                logger.debug(f"get_promise_document_path: Found party code '{party_code}' using substring for '{party_name_str}'.")
                break
    if not party_code:
        logger.warning(f"get_promise_document_path: No party code mapping for party '{party_name_str}'. Cannot generate path.")
        return None

    # 2. Format Date (YYYY-MM-DD -> YYYYMMDD)
    yyyymmdd_str = ""
    if not date_issued_str or not isinstance(date_issued_str, str):
        logger.warning(f"get_promise_document_path: Invalid or missing date_issued_str ('{date_issued_str}'). Using 'nodate'.")
        yyyymmdd_str = "nodate" + datetime.utcnow().strftime("%Y%m%d%H%M%S%f")[-4:] # Unique placeholder
    else:
        try:
            dt_obj = datetime.strptime(date_issued_str, "%Y-%m-%d")
            yyyymmdd_str = dt_obj.strftime("%Y%m%d")
        except ValueError:
            logger.warning(f"get_promise_document_path: Malformed date_issued_str ('{date_issued_str}'), attempting direct replace. Using 'baddate'.")
            yyyymmdd_str = date_issued_str.replace("-", "")
            if len(yyyymmdd_str) != 8 or not yyyymmdd_str.isdigit():
                yyyymmdd_str = "baddate" + datetime.utcnow().strftime("%Y%m%d%H%M%S%f")[-4:] # Unique placeholder
    
    # 3. Get Source Type Code
    source_id_code = SOURCE_TYPE_TO_ID_CODE_MAPPING.get(source_type_str, SOURCE_TYPE_TO_ID_CODE_MAPPING["DEFAULT_SOURCE_ID_CODE"])
    if source_type_str not in SOURCE_TYPE_TO_ID_CODE_MAPPING:
        logger.debug(f"get_promise_document_path: Source type '{source_type_str}' not in explicit map, used default '{source_id_code}'.")

    # 4. Generate Content Hash
    content_hash = generate_content_hash(promise_text)

    # 5. Construct Leaf Document ID
    doc_leaf_id = f"{yyyymmdd_str}_{source_id_code}_{content_hash}"

    # 6. Construct Full Path
    full_path = f"{target_collection_root}/{region_code}/{party_code}/{doc_leaf_id}"
    logger.debug(f"get_promise_document_path: Generated path '{full_path}' for promise based on inputs.")
    return full_path

# --- End: Helper Functions for Promise ID and Path Generation ---

# Ensure logger is configured for scripts that might import this utility early
if __name__ == '__main__':
    # Basic logging config for direct testing of this module
    logging.basicConfig(level=logging.DEBUG,
                        format='%(asctime)s - %(levelname)s - %(module)s - %(funcName)s - %(message)s')
    logger.info("common_utils.py executed directly for testing.")

    # --- Test Cases (requires Firestore to be populated and accessible) ---
    # Ensure your .env or GOOGLE_APPLICATION_CREDENTIALS is set up for these tests.
    _initialize_firestore_client() # Explicitly initialize for testing if not done on module load
    if db:
        logger.info("--- Running Test Cases for Department Standardization ---")
        
        test_variants = [
            "minister of finance",
            "MINISTER OF HEALTH",
            "Minister of natural resources",
            "Natural Resources Canada", 
            "treasury board of canada secretariat",
            "non_existent_department_variant",
            "MINISTRE OF FOREIGN AFFAIRS", # Typo from old map
            None,
            "  "
        ]
        
        for variant in test_variants:
            print(f"\nInput Variant: '{variant}'")
            full_name = standardize_department_name(variant)
            print(f"  -> Standardized Full Name: '{full_name}'")
            if full_name:
                short_name = get_department_short_name(full_name)
                print(f"  -> Display Short Name: '{short_name}'")
            else:
                print(f"  -> No short name lookup due to None full name.")

        logger.info("--- Test Cases Complete ---")
        logger.info("--- Running Test Cases for Promise Path Generation ---")
        test_promise_data = [
            ("Liberal Party of Canada", "2025-04-19", "2025 LPC Platform", "Build 1 million new homes."),
            ("Conservative Party of Canada", "2024-01-01", "Speech", "Lower taxes for families."),
            ("NDP", "2023-11-15", "Press Release", "Invest in public healthcare."), # Example with unmapped party name if NDP not in mapping
            ("Bloc Québécois", "bad-date-format", "Some Custom Source", "Represent Quebec."),
            ("Liberal Party of Canada", "2025-05-20", "Video Transcript (YouTube)", "Another LPC promise text example."),
            ("Unknown Party", "2025-06-01", "Unknown Source", "A test promise from an unknown party.")
        ]
        for party, date_str, source_str, text_str in test_promise_data:
            print(f"\nInput: Party='{party}', Date='{date_str}', Source='{source_str}', Text=\"{text_str[:30]}...\"")
            path = get_promise_document_path(party, date_str, source_str, text_str)
            print(f"  -> Generated Path: '{path}'")
        logger.info("--- Promise Path Generation Test Cases Complete ---")
    else:
        logger.error("Firestore client not initialized. Skipping test cases.")