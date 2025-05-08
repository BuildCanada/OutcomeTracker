from dotenv import load_dotenv
load_dotenv()

import firebase_admin
from firebase_admin import credentials
from firebase_admin import firestore
import pandas as pd
import os

# Import the new common utility for department standardization
from common_utils import standardize_department_name

if not firebase_admin._apps: # Check if app is already initialized
    if os.getenv('FIRESTORE_EMULATOR_HOST'):
        # Connect to the Firestore Emulator
        options = {'projectId': 'promisetrackerapp'} # Use your desired project ID for the emulator
        firebase_admin.initialize_app(options=options)
        print(f"Python (Mandate Processing): Connected to Firestore Emulator at {os.getenv('FIRESTORE_EMULATOR_HOST')} using project ID '{options['projectId']}'")
    else:
        print("ERROR: FIRESTORE_EMULATOR_HOST environment variable not set.")
        print("Please set it to connect to the local Firestore emulator (e.g., 'localhost:8080').")
        exit("Exiting: Firestore emulator not configured.")

db = firestore.client()
# --- End Firestore Configuration ---

def process_mlc_csv(file_path):
    df = pd.read_csv(file_path)
    promises_collection = db.collection('promises_2021_mandate') # Using a specific collection

    for index, row in df.iterrows():
        # Standardize lead department
        reporting_lead_standardized = standardize_department_name(row['Reporting Lead'])

        # Parse and standardize 'All ministers'
        all_ministers_raw = str(row['All ministers']).split(';')
        all_ministers_standardized = []
        if row['All ministers'] and str(row['All ministers']).lower() != 'nan':
            all_ministers_standardized = [standardize_department_name(m.strip()) for m in all_ministers_raw if standardize_department_name(m.strip()) is not None]
            all_ministers_standardized = list(set(all_ministers_standardized)) # Remove duplicates

        promise_doc = {
            'promise_id': str(row['MLC ID']),
            'text': str(row['Commitment']),
            'key_points': [str(row['Commitment'])], # Placeholder, Gemini to refine later
            'source_document_url': 'https_pm.gc.ca_eng_ministerial-mandate-letters_2021', # Generic placeholder
            'source_type': 'Mandate Letter Commitment (Structured)',
            'date_issued': '2021-12-16', # Common date for 2021 letters
            'candidate_or_government': 'Government of Canada (2021 Mandate)',
            'party': 'Liberal Party of Canada',
            'category': None, # To be filled by Gemini or department mapping
            'responsible_department_lead': reporting_lead_standardized,
            'relevant_departments': all_ministers_standardized,
            'mlc_raw_reporting_lead': str(row['Reporting Lead']), # Keep raw for reference
            'mlc_raw_all_ministers': str(row['All ministers'])    # Keep raw for reference
        }
        
        # Add to Firestore
        promises_collection.document(promise_doc['promise_id']).set(promise_doc)
        # print(f"Added MLC ID: {promise_doc['promise_id']}") # Commented out to only show warnings
    print("Finished processing MLC CSV.")

# --- Main execution ---
if __name__ == "__main__":
    # The check for FIRESTORE_EMULATOR_HOST is now part of the Firebase initialization.
    # If the script reaches here, it means the emulator host was set.
    # If it wasn't, the script would have exited during Firebase setup.
    
    # Construct path to CSV relative to this script's location
    script_dir = os.path.dirname(os.path.abspath(__file__))
    # Go up one directory from script_dir (scripts -> PromiseTracker) then into raw-data
    csv_file_path = os.path.join(script_dir, '..', 'raw-data', '2021-mandate-commitments.csv')
    
    # Verify the path exists before processing
    if not os.path.exists(csv_file_path):
        print(f"ERROR: CSV file not found at the constructed path: {csv_file_path}")
        print("Please ensure '2021-mandate-commitments.csv' is in the 'PromiseTracker/raw-data' directory.")
        exit("Exiting: CSV file missing.")

    print(f"Processing CSV file from: {csv_file_path}") # Add print statement for path verification
    process_mlc_csv(csv_file_path)