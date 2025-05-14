import firebase_admin
from firebase_admin import credentials, firestore
import os
import logging
from dotenv import load_dotenv
import argparse
import csv
from datetime import datetime

# Load environment variables from .env file, assuming it's in the parent directory of 'scripts'
load_dotenv(dotenv_path=os.path.join(os.path.dirname(__file__), '..', '..', '.env'))

# --- Logger Setup ---
logging.basicConfig(level=logging.INFO,
                    format='%(asctime)s - %(levelname)s - %(filename)s:%(lineno)d - %(message)s',
                    datefmt='%Y-%m-%d %H:%M:%S')
logger = logging.getLogger(__name__)
# --- End Logger Setup ---

# --- Firebase Configuration ---
db = None
POTENTIAL_LINKS_COLLECTION = 'promise_evidence_links'
PROMISES_COLLECTION = 'promises' # Assuming this is your promises collection

def initialize_firebase():
    global db
    if not firebase_admin._apps:
        try:
            cred_path = os.getenv('GOOGLE_APPLICATION_CREDENTIALS')
            if cred_path:
                logger.info(f"Attempting Firebase init with GOOGLE_APPLICATION_CREDENTIALS: {cred_path}")
                cred = credentials.Certificate(cred_path)
                firebase_admin.initialize_app(cred)
            else:
                logger.info("Attempting Firebase init with default credentials (e.g., from ADC or environment).")
                firebase_admin.initialize_app()
            
            project_id = os.getenv('FIREBASE_PROJECT_ID', firebase_admin.get_app().project_id if firebase_admin.get_app() else '[Cloud Project ID Not Set]')
            logger.info(f"Connected to CLOUD Firestore (Project: {project_id}).")
            db = firestore.client()
        except Exception as e:
            logger.critical(f"Firebase init failed: {e}", exc_info=True)
            return False
    else:
        db = firestore.client()
        logger.info("Firebase Admin SDK already initialized.")
    
    if db is None:
        logger.critical("Firestore client not available.")
        return False
    return True
# --- End Firebase Configuration ---

def analyze_links(limit=None, output_csv_path=None):
    if not initialize_firebase():
        logger.error("Could not initialize Firebase. Exiting analysis.")
        return

    logger.info(f"--- Starting Analysis of '{POTENTIAL_LINKS_COLLECTION}' ---")

    potential_links_query = db.collection(POTENTIAL_LINKS_COLLECTION)
    if limit:
        potential_links_query = potential_links_query.limit(limit)
        logger.info(f"Analyzing up to {limit} documents from '{POTENTIAL_LINKS_COLLECTION}'.")

    # Store more details from links to associate with promises later
    # { promise_id: [{bill_parl_id: X, llm_score: Y}, ...], ...}
    promise_to_link_details_map = {}
    total_links_processed = 0

    try:
        for link_doc_snapshot in potential_links_query.stream():
            total_links_processed += 1
            link_data = link_doc_snapshot.to_dict()
            promise_id = link_data.get('promise_id')
            bill_parl_id = link_data.get('bill_parl_id')
            llm_score = link_data.get('llm_likelihood_score')
            
            if promise_id:
                if promise_id not in promise_to_link_details_map:
                    promise_to_link_details_map[promise_id] = []
                link_detail = {}
                if bill_parl_id: link_detail['bill_parl_id'] = bill_parl_id
                if llm_score: link_detail['llm_likelihood_score'] = llm_score
                promise_to_link_details_map[promise_id].append(link_detail)
            else:
                logger.warning(f"Link document {link_doc_snapshot.id} missing 'promise_id'.")
        
        logger.info(f"Processed {total_links_processed} link documents.")
        unique_promise_ids_in_links = set(promise_to_link_details_map.keys())
        logger.info(f"Found {len(unique_promise_ids_in_links)} unique promise IDs referenced in these links.")

        if not unique_promise_ids_in_links:
            logger.info("No unique promises found to analyze.")
            return

        legislative_promise_count = 0
        promises_checked_count = 0
        missing_promise_data_count = 0
        
        csv_data_rows = []
        csv_headers = [
            'promise_id', 'promise_text_snippet', 'responsible_department_lead',
            'relevant_departments', 'implied_action_type', 'extracted_keywords_concepts',
            'is_legislative_type', 'linked_bill_parl_ids', 'link_likelihood_scores'
        ]
        if output_csv_path:
            csv_data_rows.append(csv_headers)

        for promise_id in unique_promise_ids_in_links:
            promises_checked_count += 1
            promise_doc_ref = db.collection(PROMISES_COLLECTION).document(promise_id)
            promise_doc = promise_doc_ref.get()
            
            row_data = {'promise_id': promise_id}
            linked_bill_ids_for_csv = []
            link_scores_for_csv = []            

            if promise_id in promise_to_link_details_map:
                for detail in promise_to_link_details_map[promise_id]:
                    linked_bill_ids_for_csv.append(detail.get('bill_parl_id', 'N/A'))
                    link_scores_for_csv.append(detail.get('llm_likelihood_score', 'N/A'))
            
            row_data['linked_bill_parl_ids'] = ", ".join(linked_bill_ids_for_csv)
            row_data['link_likelihood_scores'] = ", ".join(link_scores_for_csv)

            if promise_doc.exists:
                promise_data = promise_doc.to_dict()
                action_type = promise_data.get('implied_action_type')
                is_legislative = (action_type == "legislative")
                if is_legislative:
                    legislative_promise_count += 1
                
                row_data.update({
                    'promise_text_snippet': promise_data.get('text', '')[:250],
                    'responsible_department_lead': promise_data.get('responsible_department_lead', ''),
                    'relevant_departments': ", ".join(promise_data.get('relevant_departments', [])),
                    'implied_action_type': action_type,
                    'extracted_keywords_concepts': ", ".join(promise_data.get('extracted_keywords_concepts', [])),
                    'is_legislative_type': is_legislative
                })
            else:
                logger.warning(f"Promise document {promise_id} (referenced in links) not found in '{PROMISES_COLLECTION}'.")
                missing_promise_data_count +=1
                row_data.update({
                    'promise_text_snippet': 'PROMISE DATA NOT FOUND',
                    'responsible_department_lead': '',
                    'relevant_departments': '',
                    'implied_action_type': '',
                    'extracted_keywords_concepts': '',
                    'is_legislative_type': False
                })
            
            if output_csv_path:
                csv_data_rows.append([row_data.get(h, '') for h in csv_headers])
            
            if promises_checked_count % 50 == 0:
                logger.info(f"Checked {promises_checked_count}/{len(unique_promise_ids_in_links)} unique promises...")

        if output_csv_path:
            try:
                with open(output_csv_path, 'w', newline='', encoding='utf-8') as csvfile:
                    writer = csv.writer(csvfile)
                    writer.writerows(csv_data_rows)
                logger.info(f"Successfully wrote promise analysis data to {output_csv_path}")
            except IOError as e:
                logger.error(f"Error writing to CSV file {output_csv_path}: {e}", exc_info=True)

        logger.info("--- Analysis Results ---")
        logger.info(f"Total unique promise IDs found in '{POTENTIAL_LINKS_COLLECTION}': {len(unique_promise_ids_in_links)}")
        logger.info(f"Number of these unique promises with implied_action_type == 'legislative': {legislative_promise_count}")
        
        if len(unique_promise_ids_in_links) > 0:
            percentage_legislative = (legislative_promise_count / len(unique_promise_ids_in_links)) * 100
            logger.info(f"Percentage of linked unique promises that are 'legislative': {percentage_legislative:.2f}%")
        else:
            logger.info("Percentage cannot be calculated as no unique promises were found.")
        
        if missing_promise_data_count > 0:
            logger.warning(f"Could not find data for {missing_promise_data_count} promise IDs referenced in links.")

    except Exception as e:
        logger.error(f"Error during analysis: {e}", exc_info=True)

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=f"Analyze implied_action_type of promises in '{POTENTIAL_LINKS_COLLECTION}' and optionally output to CSV.")
    parser.add_argument("--limit", type=int, default=None, 
                        help="Limit the number of documents to read from promise_evidence_links for analysis.")
    parser.add_argument("--output_csv", type=str, default=None,
                        help="Path to save the output CSV file (e.g., analysis_output.csv)")
    
    args = parser.parse_args()

    analyze_links(limit=args.limit, output_csv_path=args.output_csv)
    logger.info(f"--- Analysis Script Finished ---") 