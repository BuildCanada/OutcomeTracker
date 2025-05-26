import firebase_admin
from firebase_admin import firestore
import os
import sys
import logging
import traceback
from dotenv import load_dotenv # Import load_dotenv
import csv # For CSV output
import argparse # For command-line arguments
from common_utils import TARGET_PROMISES_COLLECTION_ROOT, DEFAULT_REGION_CODE, KNOWN_PARTY_CODES # Added imports

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

def extract_and_export_promise_text(limit=None, output_filename="extracted_promise_texts.csv"):
    all_extracted_texts = []
    target_source_type = "2021 LPC Mandate Letters" # Query for the final, updated source_type
    total_docs_scanned_across_parties = 0

    logger.info(f"Starting extraction for source_type: '{target_source_type}' from new structure.")

    for party_code in KNOWN_PARTY_CODES:
        logger.info(f"  Querying flat promises collection for party: {party_code}")
        
        try:
            query = db.collection(TARGET_PROMISES_COLLECTION_ROOT).where("party_code", "==", party_code).where("source_type", "==", target_source_type).select(["text"])
            results = query.stream()
            
            party_texts_count = 0
            for doc in results:
                total_docs_scanned_across_parties += 1
                promise_data = doc.to_dict()
                if "text" in promise_data and promise_data["text"]:
                    all_extracted_texts.append(promise_data["text"])
                    party_texts_count += 1
                else:
                    logger.debug(f"    ID: {doc.id} for party {party_code}, Text field missing or empty.")
            logger.info(f"    Found {party_texts_count} texts for party {party_code}.")

        except Exception as e_party_query:
            logger.error(f"  Error querying party {party_code} in flat collection: {e_party_query}", exc_info=True)
            continue # Continue to the next party if one fails

    logger.info(f"Scanned a total of {total_docs_scanned_across_parties} documents across all relevant party collections.")
    logger.info(f"Total texts extracted before limit: {len(all_extracted_texts)}.")

    # Apply limit if provided, after collecting all texts
    texts_to_export = all_extracted_texts
    if limit is not None and limit > 0 and len(all_extracted_texts) > limit:
        logger.info(f"Applying limit: selecting first {limit} of {len(all_extracted_texts)} extracted texts.")
        texts_to_export = all_extracted_texts[:limit]
    elif limit is not None and limit <= 0:
        logger.info("Limit is 0 or negative, no texts will be exported.")
        texts_to_export = []

    # Determine output path (same directory as script)
    script_dir = os.path.dirname(os.path.abspath(__file__))
    output_path = os.path.join(script_dir, output_filename)
    logger.info(f"Exporting {len(texts_to_export)} texts to: {output_path}")

    exported_count = 0
    try:
        with open(output_path, 'w', newline='', encoding='utf-8') as csvfile:
            csv_writer = csv.writer(csvfile)
            for text_content in texts_to_export:
                csv_writer.writerow([text_content])
                exported_count += 1
                
                if exported_count > 0 and exported_count % 100 == 0:
                    logger.info(f"Written {exported_count} texts to CSV so far...")

        logger.info(f"Successfully exported {exported_count} promise texts to {output_path}")
        if len(all_extracted_texts) > 0 and exported_count < len(all_extracted_texts) and limit is not None and limit > 0:
             logger.info(f"{len(all_extracted_texts) - exported_count} texts were not exported due to the limit of {limit}.")

    except Exception as e:
        logger.error(f"Error during CSV export: {e}", exc_info=True)
        traceback.print_exc()

    logger.info(f"\nQuery execution and export finished. Exported {exported_count} texts.")

if __name__ == "__main__":
    # --- Argument Parser Setup ---
    parser = argparse.ArgumentParser(description="Extract 'text' field from 'promises' collection for specific source_type and export to CSV.")
    parser.add_argument("--limit", type=int, help="Limit the number of documents to process.")
    parser.add_argument("--output_file", type=str, default="extracted_promise_texts.csv", help="Name of the output CSV file (e.g., texts.csv).")
    
    args = parser.parse_args()

    logger.info("--- Starting Promise Text Extraction Utility ---")
    logger.info(f"Processing up to {args.limit if args.limit else 'all'} records.")
    logger.info(f"Output CSV file: {args.output_file}")

    extract_and_export_promise_text(limit=args.limit, output_filename=args.output_file)

    logger.info("--- Promise Text Extraction Utility Finished ---")