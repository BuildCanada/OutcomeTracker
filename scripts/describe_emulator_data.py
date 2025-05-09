# scripts/describe_emulator_data.py

import firebase_admin
from firebase_admin import firestore
import os
import sys
import logging
import traceback
from dotenv import load_dotenv # Import load_dotenv

# --- Load Environment Variables ---
# Load variables from .env file into environment BEFORE trying to use them
load_dotenv() 
# --- End Load Environment Variables ---


# --- Logger Setup --- 
logging.basicConfig(level=logging.INFO, 
                    format='%(asctime)s - %(levelname)s - %(filename)s:%(lineno)d - %(message)s',
                    datefmt='%Y-%m-%d %H:%M:%S')
logger = logging.getLogger(__name__)
# --- End Logger Setup ---

# --- Firebase Configuration ---
# Initialize db variable to None initially
db = None 
if not firebase_admin._apps:
    # Cloud Firestore initialization
    # GOOGLE_APPLICATION_CREDENTIALS environment variable must be set
    if not os.getenv('GOOGLE_APPLICATION_CREDENTIALS'):
        logger.critical("GOOGLE_APPLICATION_CREDENTIALS environment variable not set.")
        logger.critical("This is required for authentication with Google Cloud Firestore.")
        exit("Exiting: GOOGLE_APPLICATION_CREDENTIALS not set.")
    try:
        firebase_admin.initialize_app() # Default initialization for cloud
        logger.info("Successfully connected to Google Cloud Firestore.")
        db = firestore.client() # Assign the client to db
    except Exception as e:
        logger.critical(f"Firebase initialization failed for Google Cloud Firestore: {e}", exc_info=True)
        exit("Exiting: Firebase connection failed.")
else:
    logger.info("Firebase app already initialized. Getting client for Google Cloud Firestore.")
    db = firestore.client() # Get client if already initialized

# Final check if db is assigned
if db is None:
     logger.critical("Failed to obtain Firestore client after attempting cloud connection. Exiting.")
     exit("Exiting: Firestore client not available.")
# --- End Firebase Configuration ---


def describe_firestore_data():
    """Lists collections and sample document fields in the connected Firestore instance."""
    logger.info("--- Describing Firestore Data ---")
    
    try:
        collections = db.collections()
        collection_list = list(collections) # Consume the generator

        if not collection_list:
            logger.info("No collections found in the emulator.")
            return

        logger.info(f"Found {len(collection_list)} collection(s):")
        
        for i, col_ref in enumerate(collection_list):
            collection_id = col_ref.id
            print(f"\n{i+1}. Collection: '{collection_id}'")
            
            # Get one sample document to inspect fields
            try:
                docs = col_ref.limit(1).stream()
                first_doc = next(docs, None) # Get the first doc, or None if empty

                if first_doc:
                    doc_data = first_doc.to_dict()
                    if doc_data:
                        print(f"   Sample Document ID: {first_doc.id}")
                        print(f"   Sample Fields (Top-Level Keys):")
                        for key in sorted(doc_data.keys()):
                            field_type = type(doc_data[key]).__name__
                            # Show nested structure for lists/dicts slightly
                            if isinstance(doc_data[key], list):
                                field_type = f"list (size {len(doc_data[key])})"
                            elif isinstance(doc_data[key], dict):
                                field_type = f"map (dict)"
                            print(f"     - {key} ({field_type})")
                    else:
                        print(f"   Sample document {first_doc.id} has no data (empty).")
                else:
                    print("   Collection appears to be empty (no documents found).")
                    
            except Exception as e:
                 logger.error(f"   Error fetching sample document for collection '{collection_id}': {e}", exc_info=True)

    except Exception as e:
        logger.error(f"An error occurred while listing collections: {e}", exc_info=True)
        
    logger.info("\n--- End of Description ---")


if __name__ == "__main__":
    # Ensure necessary environment variables are loaded before calling the function
    # The script now relies on GOOGLE_APPLICATION_CREDENTIALS for cloud connection
    if not firebase_admin._apps: # Check if Firebase was initialized
         logger.error("Firebase not initialized. This script requires GOOGLE_APPLICATION_CREDENTIALS to be set for cloud connection.")
    elif db is None:
         logger.error("Firestore client not available. Cannot describe data.")
    else:
         describe_firestore_data() # Call the renamed function