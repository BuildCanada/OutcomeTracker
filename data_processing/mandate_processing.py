from dotenv import load_dotenv
load_dotenv()

import firebase_admin
from firebase_admin import credentials
from firebase_admin import firestore
import pandas as pd
import os

# Import the new common utility for department standardization
from common_utils import standardize_department_name

# --- Configuration for connecting to Firestore ---
# When FIRESTORE_EMULATOR_HOST is set, Admin SDK connects to the emulator
# For cloud, you'd unset this and ensure GOOGLE_APPLICATION_CREDENTIALS points to your service account key JSON
# or initialize with cred = credentials.Certificate("path/to/key.json")

if not firebase_admin._apps: # Check if app is already initialized
    if os.getenv('FIRESTORE_EMULATOR_HOST'):
        # When using the emulator, explicitly pass a project ID.
        # The SDK might still look for a project context even with the emulator host set.
        options = {'projectId': 'promisetrackerapp'} # Use your actual project ID
        firebase_admin.initialize_app(options=options)
        print(f"Python: Connected to Firestore Emulator at {os.getenv('FIRESTORE_EMULATOR_HOST')} using project ID 'promisetrackerapp'")
    else:

        firebase_admin.initialize_app() # Assumes GOOGLE_APPLICATION_CREDENTIALS is set for cloud
        print("Python: Connected to CLOUD Firestore (ensure GOOGLE_APPLICATION_CREDENTIALS is set if not using emulator)")

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

    if not os.getenv('FIRESTORE_EMULATOR_HOST'):
        print("ERROR: FIRESTORE_EMULATOR_HOST environment variable not set.")
        print("Please set it to 'localhost:8080' to connect to the emulator.")
    else:
        csv_file_path = 'PromiseTracker/raw-data/2021-mandate-commitments.csv' # Adjust path as needed
        process_mlc_csv(csv_file_path)