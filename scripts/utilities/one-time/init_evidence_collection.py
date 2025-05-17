# scripts/init_evidence_collection.py
import firebase_admin
from firebase_admin import credentials # Keep for potential explicit credential use, though ADC is default
from firebase_admin import firestore # Import firestore module from firebase_admin
import os
import uuid
from datetime import datetime, timezone
import logging

# --- Logger Setup ---
logging.basicConfig(level=logging.INFO,
                    format='%(asctime)s - %(levelname)s - %(filename)s:%(lineno)d - %(message)s',
                    datefmt='%Y-%m-%d %H:%M:%S')
logger = logging.getLogger(__name__)
# --- End Logger Setup ---

# --- Firebase Configuration (aligned with process_mandate_commitments.py) ---
try:
    if not firebase_admin._apps:
        # Default initialization uses GOOGLE_APPLICATION_CREDENTIALS
        firebase_admin.initialize_app()
    # Use the imported firestore module to get the client
    db = firestore.client() 
    project_id = os.getenv('FIREBASE_PROJECT_ID', firebase_admin.get_app().project_id if firebase_admin.get_app() else "unknown-project")
    logger.info(f"Connected to Firestore project: {project_id}")
except Exception as e:
    logger.critical(f"Firebase initialization failed: {e}", exc_info=True)
    logger.critical("Ensure GOOGLE_APPLICATION_CREDENTIALS environment variable is set correctly.")
    exit("Exiting: Firebase connection failed.")
# --- End Firebase Configuration ---

def add_dummy_evidence_item():
    """Adds a single dummy document to the 'evidence_items' collection."""
    
    collection_ref = db.collection('evidence_items')
    doc_id = str(uuid.uuid4())
    
    # Use SERVER_TIMESTAMP for both date fields in this dummy document
    now_ts = firestore.SERVER_TIMESTAMP 

    dummy_data = {
        'evidence_id': doc_id,
        'promise_ids': ['dummy_promise_id_1', 'dummy_promise_id_2'],
        'evidence_source_type': "Bill (LEGISinfo)",
        'evidence_date': now_ts, # Use server timestamp instead of specific date
        'title_or_summary': "Example Bill C-123: The Placeholder Act",
        'description_or_details': "This is a sample description for the dummy evidence item.",
        'source_url': "https://www.parl.ca/legisinfo/en/bill/44-1/c-123",
        'source_document_raw_id': "C-123_44-1",
        'linked_departments': ["Finance Canada", "Innovation, Science and Economic Development Canada"],
        'status_impact_on_promise': "Potential Progress",
        'ingested_at': now_ts, 
        'additional_metadata': {
            'bill_status': 'First Reading',
            'sponsor': 'Hon. Placeholder Minister'
        }
    }

    try:
        doc_ref = collection_ref.document(doc_id)
        doc_ref.set(dummy_data)
        logger.info(f"Successfully added dummy document with ID: {doc_id} to 'evidence_items' collection.")
        logger.info(f"The 'evidence_items' collection should now exist in your Firestore database.")
    except Exception as e:
        logger.error(f"Failed to add dummy document to 'evidence_items': {e}", exc_info=True)

if __name__ == "__main__":
    logger.info("Running script to initialize 'evidence_items' collection...")
    add_dummy_evidence_item()
    logger.info("Script finished.") 