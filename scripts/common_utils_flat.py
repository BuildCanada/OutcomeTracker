# common_utils_flat.py
# Updated common utilities for flat promises collection structure

import logging
import os
import firebase_admin
from firebase_admin import credentials, firestore
from google.cloud.firestore_v1.base_query import FieldFilter
from dotenv import load_dotenv
import hashlib
from datetime import datetime

# Load environment variables
load_dotenv()

logger = logging.getLogger(__name__)

# --- Constants for Flat Structure ---
TARGET_PROMISES_COLLECTION_ROOT = os.getenv("TARGET_PROMISES_COLLECTION", "promises")
DEFAULT_REGION_CODE = "Canada"

# Updated party mapping (consistent with existing structure)
PARTY_NAME_TO_CODE_MAPPING = {
    "Liberal Party of Canada": "LPC",
    "Liberal Party of Canada (2025 Platform)": "LPC",
    "Conservative Party of Canada": "CPC",
    "New Democratic Party": "NDP",
    "Bloc Québécois": "BQ",
    "Green Party of Canada": "GP",
}

# Known party codes for iteration
KNOWN_PARTY_CODES = ["LPC", "CPC", "NDP", "BQ", "GP"]

# Source type mappings
SOURCE_TYPE_TO_ID_CODE_MAPPING = {
    "Video Transcript (YouTube)": "YTVID",
    "Mandate Letter Commitment (Structured)": "MANDL",
    "2021 LPC Mandate Letters": "MANDL",
    "2025 LPC Platform": "PLTFM",
    "DEFAULT_SOURCE_ID_CODE": "OTHER"
}

PROMISE_CATEGORIES = [
    "Finance", "Health", "Immigration", "Defence", "Housing", "Energy",
    "Innovation", "Government Transformation", "Environment",
    "Indigenous Relations", "Foreign Affairs", "Other"
]

# Global Firestore client instance
db = None

def _initialize_firestore_client():
    """Initializes the global Firestore client if not already done."""
    global db
    if db is None:
        try:
            if not firebase_admin._apps:
                logger.info("Initializing Firebase Admin SDK for common_utils_flat...")
                try:
                    firebase_admin.initialize_app()
                    project_id = os.getenv('FIREBASE_PROJECT_ID', '[Not Set - Using Default]')
                    logger.info(f"common_utils_flat: Connected to CLOUD Firestore (Project: {project_id}) using default credentials.")
                except Exception as e_default:
                    logger.warning(f"common_utils_flat: Cloud Firestore init with default creds failed: {e_default}")
                    cred_path = os.getenv('FIREBASE_SERVICE_ACCOUNT_KEY_PATH')
                    if cred_path:
                        try:
                            logger.info(f"common_utils_flat: Attempting Firebase init with service account key from env var: {cred_path}")
                            cred = credentials.Certificate(cred_path)
                            firebase_admin.initialize_app(cred)
                            project_id_sa = os.getenv('FIREBASE_PROJECT_ID', '[Not Set - Using Service Account]')
                            logger.info(f"common_utils_flat: Connected to CLOUD Firestore (Project: {project_id_sa}) via service account.")
                        except Exception as e_sa:
                            logger.critical(f"common_utils_flat: Firebase init with service account key from {cred_path} failed: {e_sa}", exc_info=True)
                            raise
                    else:
                        logger.error("common_utils_flat: FIREBASE_SERVICE_ACCOUNT_KEY_PATH env var not set and default creds failed.")
                        raise ConnectionError("Failed to initialize Firestore: No credentials provided.")
            else:
                logger.info("common_utils_flat: Firebase Admin SDK already initialized elsewhere.")
            db = firestore.client()
        except Exception as e:
            logger.critical(f"common_utils_flat: CRITICAL - Failed to initialize Firestore client: {e}", exc_info=True)
            db = None

# Department standardization functions (reuse from original)
def standardize_department_name(name_variant):
    """Standardizes a department or minister name to its official full name using Firestore department_config."""
    global db
    if db is None:
        _initialize_firestore_client()
        if db is None:
            logger.error("standardize_department_name: Firestore client is not available. Cannot proceed.")
            return None

    original_name_str = str(name_variant).strip()
    normalized_name = original_name_str.lower().strip()

    if not normalized_name or normalized_name == 'nan':
        logger.debug(f"Input '{original_name_str}' normalized to empty or NaN, returning None.")
        return None

    try:
        dept_config_ref = db.collection('department_config')
        # Try name_variants
        query = dept_config_ref.where(filter=FieldFilter('name_variants', 'array_contains', normalized_name)).limit(1)
        results = list(query.stream())
        if results:
            department_doc = results[0].to_dict()
            official_full_name = department_doc.get('official_full_name')
            if official_full_name:
                logger.debug(f"Standardized '{original_name_str}' to '{official_full_name}' via name_variants.")
                return official_full_name

        # Try official_full_name (case-insensitive)
        for doc in dept_config_ref.stream():
            doc_dict = doc.to_dict()
            if doc_dict.get('official_full_name', '').lower() == normalized_name:
                logger.debug(f"Standardized '{original_name_str}' to '{doc_dict.get('official_full_name')}' via official_full_name.")
                return doc_dict.get('official_full_name')

        logger.warning(f"Unmapped department variant: '{normalized_name}' (for input '{original_name_str}') in Firestore department_config.")
        _log_unmapped_variant(original_name_str, normalized_name)
        return None
    except Exception as e:
        logger.error(f"Error querying Firestore for department standardization of '{normalized_name}': {e}", exc_info=True)
        _log_unmapped_variant(original_name_str, normalized_name)
        return None

def _log_unmapped_variant(raw_variant, normalized_variant, source_promise_id=None):
    """Logs an unmapped department variant to the 'unmapped_department_activity' collection."""
    global db
    if db is None:
        logger.error("_log_unmapped_variant: Firestore client is not available. Cannot log unmapped variant.")
        return

    try:
        doc_id = normalized_variant.replace('/', '_SLASH_')
        activity_ref = db.collection('unmapped_department_activity').document(doc_id)

        @firestore.transactional
        def update_in_transaction(transaction, doc_ref):
            snapshot = doc_ref.get(transaction=transaction)
            current_server_time = firestore.SERVER_TIMESTAMP

            if snapshot.exists:
                new_count = snapshot.get('count') + 1
                example_ids = snapshot.get('example_source_identifiers') or []
                if source_promise_id and source_promise_id not in example_ids and len(example_ids) < 10:
                    example_ids.append(source_promise_id)

                transaction.update(doc_ref, {
                    'count': new_count,
                    'last_seen_at': current_server_time,
                    'variant_text_raw': raw_variant,
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
                    'status': 'new',
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
    """
    global db
    if db is None:
        _initialize_firestore_client()
        if db is None:
            logger.error("get_department_short_name: Firestore client is not available. Cannot proceed.")
            return standardized_full_name

    if not standardized_full_name:
        logger.debug("Input standardized_full_name is empty, returning None.")
        return None

    try:
        dept_config_ref = db.collection('department_config')
        query = dept_config_ref.where(filter=FieldFilter('official_full_name', '==', standardized_full_name)).limit(1)
        results = list(query.stream())
        
        if results:
            department_doc = results[0].to_dict()
            short_name = department_doc.get('display_short_name')
            if short_name:
                logger.debug(f"Found short name '{short_name}' for '{standardized_full_name}'")
                return short_name

        logger.debug(f"No short name mapping found for '{standardized_full_name}', returning full name")
        return standardized_full_name
    except Exception as e:
        logger.error(f"Error getting short name for '{standardized_full_name}': {e}", exc_info=True)
        return standardized_full_name

def generate_content_hash(text: str, length: int = 10) -> str:
    """Generate a hash from the text content for document ID purposes."""
    if not text:
        return "empty_content"
    hash_obj = hashlib.sha256(text.encode('utf-8'))
    return hash_obj.hexdigest()[:length]

# UPDATED FUNCTIONS FOR FLAT STRUCTURE

def get_promise_document_path_flat(
    party_name_str: str,
    date_issued_str: str,
    source_type_str: str,
    promise_text: str,
    target_collection_root: str = TARGET_PROMISES_COLLECTION_ROOT,
    region_code: str = DEFAULT_REGION_CODE
) -> str | None:
    """
    Constructs the document path for a promise in the FLAT structure.
    Returns: promises/{deterministic_document_id}
    The region and party are stored as fields, not in the path.
    """
    # Get party code
    party_code = PARTY_NAME_TO_CODE_MAPPING.get(party_name_str)
    if not party_code:
        for key, value in PARTY_NAME_TO_CODE_MAPPING.items():
            if party_name_str and key in party_name_str:
                party_code = value
                logger.debug(f"Found party code '{party_code}' using substring for '{party_name_str}'.")
                break
    if not party_code:
        logger.warning(f"No party code mapping for party '{party_name_str}'. Cannot generate path.")
        return None

    # Format date
    try:
        date_obj = datetime.strptime(date_issued_str, "%Y-%m-%d")
        yyyymmdd_str = date_obj.strftime("%Y%m%d")
    except ValueError:
        try:
            # Try YYYYMMDD format
            datetime.strptime(date_issued_str, "%Y%m%d")
            yyyymmdd_str = date_issued_str
        except ValueError:
            logger.warning(f"Invalid date format '{date_issued_str}'. Cannot generate path.")
            return None

    # Get source type code
    source_id_code = SOURCE_TYPE_TO_ID_CODE_MAPPING.get(source_type_str, 
                                                       SOURCE_TYPE_TO_ID_CODE_MAPPING["DEFAULT_SOURCE_ID_CODE"])

    # Generate deterministic document ID
    content_hash = generate_content_hash(promise_text, 8)
    document_id = f"{party_code}_{yyyymmdd_str}_{source_id_code}_{content_hash}"

    # Return flat path (just collection + document ID)
    flat_path = f"{target_collection_root}/{document_id}"
    
    logger.debug(f"Generated flat path: {flat_path} for party: {party_name_str}, date: {date_issued_str}")
    return flat_path

def get_legacy_promise_document_path(
    party_name_str: str,
    date_issued_str: str,
    source_type_str: str,
    promise_text: str,
    target_collection_root: str = TARGET_PROMISES_COLLECTION_ROOT,
    region_code: str = DEFAULT_REGION_CODE
) -> str | None:
    """
    Constructs the legacy subcollection path for backward compatibility.
    Returns: promises/{region}/{party}/{document_id}
    """
    # Get party code
    party_code = PARTY_NAME_TO_CODE_MAPPING.get(party_name_str)
    if not party_code:
        for key, value in PARTY_NAME_TO_CODE_MAPPING.items():
            if party_name_str and key in party_name_str:
                party_code = value
                break
    if not party_code:
        return None

    # Format date and generate ID (same logic as flat)
    try:
        date_obj = datetime.strptime(date_issued_str, "%Y-%m-%d")
        yyyymmdd_str = date_obj.strftime("%Y%m%d")
    except ValueError:
        try:
            datetime.strptime(date_issued_str, "%Y%m%d")
            yyyymmdd_str = date_issued_str
        except ValueError:
            return None

    source_id_code = SOURCE_TYPE_TO_ID_CODE_MAPPING.get(source_type_str, 
                                                       SOURCE_TYPE_TO_ID_CODE_MAPPING["DEFAULT_SOURCE_ID_CODE"])
    content_hash = generate_content_hash(promise_text, 8)
    document_id = f"{party_code}_{yyyymmdd_str}_{source_id_code}_{content_hash}"

    # Return legacy subcollection path
    legacy_path = f"{target_collection_root}/{region_code}/{party_code}/{document_id}"
    return legacy_path

def query_promises_flat(
    db_client,
    parliament_session_id: str = None,
    party_code: str = None,
    region_code: str = DEFAULT_REGION_CODE,
    source_type: str = None,
    responsible_department: str = None,
    limit_count: int = None
) -> list:
    """
    Query promises from the flat collection structure with various filters.
    """
    if not db_client:
        logger.error("Database client not provided to query_promises_flat")
        return []

    try:
        collection_ref = db_client.collection(TARGET_PROMISES_COLLECTION_ROOT)
        query = collection_ref

        # Apply filters
        if parliament_session_id:
            query = query.where(filter=FieldFilter("parliament_session_id", "==", parliament_session_id))
        
        if party_code:
            query = query.where(filter=FieldFilter("party_code", "==", party_code))
        
        if region_code:
            query = query.where(filter=FieldFilter("region_code", "==", region_code))
        
        if source_type:
            query = query.where(filter=FieldFilter("source_type", "==", source_type))
        
        if responsible_department:
            query = query.where(filter=FieldFilter("responsible_department_lead", "==", responsible_department))

        if limit_count:
            query = query.limit(limit_count)

        # Execute query
        results = []
        for doc in query.stream():
            doc_data = doc.to_dict()
            doc_data['id'] = doc.id
            doc_data['document_path'] = doc.reference.path
            results.append(doc_data)

        logger.info(f"Query returned {len(results)} promises with filters: session={parliament_session_id}, party={party_code}, region={region_code}")
        return results

    except Exception as e:
        logger.error(f"Error querying flat promises collection: {e}", exc_info=True)
        return []

def create_promise_document_flat(
    db_client,
    promise_data: dict,
    party_name: str,
    region_code: str = DEFAULT_REGION_CODE
) -> tuple[bool, str]:
    """
    Create a promise document in the flat structure.
    Returns (success, document_id_or_error_message)
    """
    if not db_client:
        logger.error("Database client not provided to create_promise_document_flat")
        return False, "No database client"

    try:
        # Get party code
        party_code = PARTY_NAME_TO_CODE_MAPPING.get(party_name)
        if not party_code:
            return False, f"Unknown party: {party_name}"

        # Generate document ID
        date_str = promise_data.get('date_issued', '')
        source_type = promise_data.get('source_type', '')
        text = promise_data.get('text', '')

        doc_path = get_promise_document_path_flat(
            party_name, date_str, source_type, text, region_code=region_code
        )
        
        if not doc_path:
            return False, "Failed to generate document path"

        document_id = doc_path.split('/')[-1]

        # Add flat structure fields to promise data
        enhanced_data = {
            **promise_data,
            'region_code': region_code,
            'party_code': party_code,
            'created_at': firestore.SERVER_TIMESTAMP,
            'last_updated_at': firestore.SERVER_TIMESTAMP
        }

        # Create document
        doc_ref = db_client.collection(TARGET_PROMISES_COLLECTION_ROOT).document(document_id)
        doc_ref.set(enhanced_data)

        logger.info(f"Created promise document: {document_id}")
        return True, document_id

    except Exception as e:
        error_msg = f"Error creating promise document: {e}"
        logger.error(error_msg, exc_info=True)
        return False, error_msg

def update_promise_references_for_flat_structure(
    db_client,
    old_promise_path: str,
    new_promise_id: str
) -> bool:
    """
    Update references to promises in other collections after migration to flat structure.
    This updates evidence_items and other collections that reference promise paths.
    """
    if not db_client:
        logger.error("Database client not provided to update_promise_references_for_flat_structure")
        return False

    try:
        # Update evidence_items collection
        evidence_collection = db_client.collection('evidence_items')
        
        # Find evidence items that reference the old promise path
        # This assumes evidence items store promise paths in some field
        # Adjust the field name based on your actual schema
        query = evidence_collection.where(filter=FieldFilter('promise_paths', 'array_contains', old_promise_path))
        
        batch = db_client.batch()
        update_count = 0

        for evidence_doc in query.stream():
            evidence_data = evidence_doc.to_dict()
            promise_paths = evidence_data.get('promise_paths', [])
            
            # Replace old path with new flat path
            if old_promise_path in promise_paths:
                new_promise_paths = [new_promise_id if path == old_promise_path else path for path in promise_paths]
                
                batch.update(evidence_doc.reference, {
                    'promise_paths': new_promise_paths,
                    'migration_updated_at': firestore.SERVER_TIMESTAMP
                })
                update_count += 1

        if update_count > 0:
            batch.commit()
            logger.info(f"Updated {update_count} evidence items to reference new promise ID: {new_promise_id}")

        return True

    except Exception as e:
        logger.error(f"Error updating promise references: {e}", exc_info=True)
        return False

# Export compatibility with existing code
def get_promise_document_path(*args, **kwargs):
    """Compatibility wrapper - defaults to flat structure."""
    return get_promise_document_path_flat(*args, **kwargs) 