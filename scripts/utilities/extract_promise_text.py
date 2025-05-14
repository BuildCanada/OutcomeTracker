import firebase_admin
from firebase_admin import firestore
import os
import sys
import logging
import traceback
from dotenv import load_dotenv # Import load_dotenv
import csv # For CSV output
import argparse # For command-line arguments

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
    promises_dev_ref = db.collection("promises_dev")

    # Base query
    query = promises_dev_ref.where("source_type", "==", "Mandate Letter Commitment (Structured)").select(["text"])

    # Apply limit if provided
    if limit is not None and limit > 0:
        query = query.limit(limit)
        logger.info(f"Limiting query to {limit} records.")

    results = query.stream()

    # Determine output path (same directory as script)
    script_dir = os.path.dirname(os.path.abspath(__file__))
    output_path = os.path.join(script_dir, output_filename)

    logger.info(f"Exporting extracted texts to: {output_path}")

    count = 0
    missing_text_count = 0
    try:
        with open(output_path, 'w', newline='', encoding='utf-8') as csvfile:
            csv_writer = csv.writer(csvfile)
            # Optional: Write a header row if you prefer, e.g., csv_writer.writerow(['promise_text'])
            
            for doc in results:
                promise_data = doc.to_dict()
                if "text" in promise_data and promise_data["text"]:
                    csv_writer.writerow([promise_data["text"]])
                    count += 1
                else:
                    logger.warning(f"  ID: {doc.id}, Text field missing or empty.")
                    missing_text_count += 1
                
                if count > 0 and count % 100 == 0:
                    logger.info(f"Processed {count} records so far...")

        logger.info(f"Successfully exported {count} promise texts to {output_path}")
        if missing_text_count > 0:
            logger.info(f"{missing_text_count} documents were missing the 'text' field or it was empty.")

    except Exception as e:
        logger.error(f"Error during CSV export: {e}", exc_info=True)
        traceback.print_exc()

    logger.info(f"\nQuery execution and export finished. Found and exported {count} texts.")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Extract 'text' field from 'promises_dev' collection for specific source_type and export to CSV.")
    parser.add_argument("--limit", type=int, help="Number of records to process.")
    parser.add_argument("--output_file", type=str, default="extracted_promise_texts.csv", help="Name of the output CSV file (e.g., texts.csv).")
    
    args = parser.parse_args()

    logger.info("--- Starting Promise Text Extraction Utility ---")
    logger.info(f"Processing up to {args.limit if args.limit else 'all'} records.")
    logger.info(f"Output CSV file: {args.output_file}")

    extract_and_export_promise_text(limit=args.limit, output_filename=args.output_file)

    logger.info("--- Promise Text Extraction Utility Finished ---")