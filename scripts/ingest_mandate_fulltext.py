# scripts/ingest_mandate_fulltext.py

import firebase_admin
from firebase_admin import firestore
import os
import requests
from bs4 import BeautifulSoup
import time
import re
import traceback
from urllib.parse import urljoin
import logging
import csv # Added for CSV reading
from dotenv import load_dotenv

load_dotenv()

# Import the utility function from common_utils.py (ensure this file exists)
try:
    from common_utils import standardize_department_name
except ImportError:
    print("ERROR: Could not import 'standardize_department_name' from common_utils.py")
    print("Please ensure common_utils.py exists in the same directory or Python path.")
    exit("Exiting: Missing common_utils.py")

# --- Logger Setup ---
logging.basicConfig(level=logging.INFO,
                    format='%(asctime)s - %(levelname)s - %(filename)s:%(lineno)d - %(message)s',
                    datefmt='%Y-%m-%d %H:%M:%S')
logger = logging.getLogger(__name__)
# --- End Logger Setup ---

# --- Firebase Configuration ---
db = None
if not firebase_admin._apps:
    if not os.getenv('GOOGLE_APPLICATION_CREDENTIALS'):
        logger.critical("GOOGLE_APPLICATION_CREDENTIALS environment variable not set.")
        exit("Exiting: GOOGLE_APPLICATION_CREDENTIALS not set.")
    try:
        firebase_admin.initialize_app()
        logger.info("Successfully connected to Google Cloud Firestore.")
        db = firestore.client()
    except Exception as e:
        logger.critical(f"Firebase initialization failed: {e}", exc_info=True)
        exit("Exiting: Firebase connection failed.")
else:
    logger.info("Firebase app already initialized. Getting client for Google Cloud Firestore.")
    db = firestore.client()

if db is None:
     logger.critical("Failed to obtain Firestore client. Exiting.")
     exit("Exiting: Firestore client not available.")
# --- End Firebase Configuration ---

# --- Constants ---
# Path to the CSV file, making it relative to this script's location
SCRIPT_DIR = os.path.dirname(os.path.realpath(__file__))
# The CSV is in 'raw-data', which is a sibling to the 'scripts' directory's parent.
# So we go up one level from 'scripts' to 'PromiseTracker', then into 'raw-data'.
MANDATE_LETTERS_CSV_PATH = os.path.join(SCRIPT_DIR, '..', 'raw-data', 'MandateLetters.csv')
HEADERS = {'User-Agent': 'BuildCanadaPromiseTrackerBot/1.0 (+https://buildcanada.com/tracker-info)'}
FIRESTORE_COLLECTION = 'mandate_letters_fulltext'
# --- End Constants ---

def get_mandate_letters_data_from_csv(csv_file_path):
    """
    Reads mandate letter data from a CSV file.
    The CSV should have columns: 'Department', 'Responsible Minister', 'Mandate Letter URL'.
    """
    minister_data_list = []
    logger.info(f"Fetching mandate letter data from CSV: {csv_file_path}")
    try:
        with open(csv_file_path, mode='r', encoding='utf-8') as infile:
            reader = csv.DictReader(infile)
            for row in reader:
                department = row.get('Department')
                responsible_minister = row.get('Responsible Minister')
                mandate_url = row.get('Mandate Letter URL')

                if not all([department, responsible_minister, mandate_url]):
                    logger.warning(f"Skipping row due to missing data: {row}")
                    continue
                
                # Use new generic key names for consistency with what scrape_single_letter will expect
                minister_data_list.append({
                    "url": mandate_url,
                    "minister_full_name_input": responsible_minister.strip(),
                    "minister_title_input": department.strip(),
                })
        logger.info(f"Found {len(minister_data_list)} minister entries from CSV.")
        return minister_data_list
    except FileNotFoundError:
        logger.error(f"CSV file not found: {csv_file_path}")
        return []
    except Exception as e:
        logger.error(f"Error reading or processing CSV file {csv_file_path}: {e}", exc_info=True)
        return []

def split_full_name(full_name_str):
    """Splits a full name string into first name(s) and last name."""
    if not full_name_str:
        return None, None
    parts = full_name_str.strip().split()
    if not parts:
        return None, None
    if len(parts) == 1:
        # Assuming single name is a last name, common in some contexts or if data is imperfect
        return None, parts[0]
    last_name = parts[-1]
    first_name = " ".join(parts[:-1])
    return first_name, last_name

def scrape_single_letter(letter_url, minister_full_name_input=None, minister_title_input=None):
    """
    Scrapes the Minister's title (from pm.gc.ca) and full text from a single mandate letter page.
    Uses pre-fetched minister_full_name_input and minister_title_input from the CSV.
    """
    logger.info(f"Scraping: {letter_url}")
    if minister_full_name_input:
        logger.info(f"  Using Full Name from input: '{minister_full_name_input}'")
    if minister_title_input:
        logger.info(f"  Using Title from input: '{minister_title_input}'")

    minister_first_name, minister_last_name = split_full_name(minister_full_name_input)

    try:
        response = requests.get(letter_url, headers=HEADERS, timeout=30)
        response.raise_for_status()
        soup = BeautifulSoup(response.content, 'html5lib')

        minister_title_scraped = None # Title scraped from pm.gc.ca
        full_text = None
        minister_greeting_lastname = None # Last name from "Dear Minister X:" on pm.gc.ca

        # --- STRATEGY 1: Extract Title from H1 on pm.gc.ca ---
        title_h1 = soup.select_one('div.title-header-inner h1')
        if title_h1:
            h1_text_content = title_h1.get_text(strip=True)
            title_match = re.match(r"(.*?)\s+Mandate Letter", h1_text_content, re.IGNORECASE)
            if title_match:
                minister_title_scraped = title_match.group(1).strip()
                logger.info(f"    Extracted Title from pm.gc.ca H1: '{minister_title_scraped}'")
            else:
                 logger.warning(f"    Could not parse expected title format from pm.gc.ca H1: '{h1_text_content}'")
        else: # Fallback: Extract Title from <title> tag on pm.gc.ca
            logger.warning(f"    Could not find H1 title element on {letter_url}. Trying <title> tag.")
            page_title_tag = soup.find('title')
            if page_title_tag:
                page_title_text = page_title_tag.get_text(strip=True)
                title_match = re.match(r"(.*?)\s+Mandate Letter", page_title_text, re.IGNORECASE)
                if title_match:
                    minister_title_scraped = title_match.group(1).strip()
                    logger.info(f"    Extracted Title from pm.gc.ca <title> (Fallback): '{minister_title_scraped}'")
                else:
                    logger.warning(f"    Could not parse expected title format from <title> tag (Fallback): '{page_title_text}'")

        # Use the pm.gc.ca scraped title as the primary `minister_title_raw` for consistency
        # minister_title_input can be stored for reference.
        final_minister_title_raw = minister_title_scraped if minister_title_scraped else minister_title_input
        if not final_minister_title_raw:
            logger.error(f"    CRITICAL: No minister title could be determined for {letter_url}. Cannot create valid record.")
            return None # Cannot create a meaningful record without any title

        # --- STRATEGY 2: Extract Minister Last Name from Greeting on pm.gc.ca ---
        content_div = soup.select_one('div.field--name-body.field--type-text-with-summary')
        if content_div:
            first_p = content_div.find('p', recursive=False)
            if first_p:
                greeting = first_p.get_text(strip=True)
                name_match = re.match(r"Dear Minister (.*?):", greeting, re.IGNORECASE)
                if name_match:
                    minister_greeting_lastname = name_match.group(1).strip()
                    logger.info(f"    Extracted Last Name from pm.gc.ca Greeting: '{minister_greeting_lastname}'")
                    # If input didn't provide a last name, use this.
                    if not minister_last_name and minister_greeting_lastname:
                        minister_last_name = minister_greeting_lastname
                        logger.info(f"    Using greeting last name '{minister_greeting_lastname}' as primary last name.")
                    elif minister_last_name and minister_greeting_lastname and minister_last_name.lower() != minister_greeting_lastname.lower():
                        logger.warning(f"    Last name mismatch: Input='{minister_last_name}', Greeting='{minister_greeting_lastname}'. Prioritizing name from input.")
            else:
                 logger.warning(f"    Could not find first paragraph in content div for greeting on {letter_url}.")

            # --- STRATEGY 3: Extract Full Text from paragraphs ---
            paragraphs = content_div.find_all('p')
            letter_paragraphs = []
            skip_greeting = True
            for p in paragraphs:
                 if skip_greeting:
                      skip_greeting = False
                      continue
                 p_text = p.get_text(separator=' ', strip=True)
                 if p_text and not p_text.lower().startswith("sincerely,") \
                    and not p_text.lower().startswith("rt. hon.") \
                    and not p_text.lower() == "prime minister of canada" \
                    and "*this ministerial mandate letter was signed" not in p_text.lower():
                    letter_paragraphs.append(p_text)

            if letter_paragraphs:
                full_text = "\n\n".join(letter_paragraphs).strip()
                logger.info(f"    Extracted text length: {len(full_text)} characters.")
            else:
                logger.warning(f"    No suitable paragraphs found for full text on {letter_url}")
        else:
            logger.warning(f"    Could not find main content div for text extraction on {letter_url}")

        # --- Standardize Title/Department ---
        standardized_department_or_title = None
        # Prefer standardizing the title scraped directly from pm.gc.ca if available
        title_to_standardize = minister_title_scraped if minister_title_scraped else minister_title_input
        
        if title_to_standardize:
            standardized_department_or_title = standardize_department_name(title_to_standardize)
            if standardized_department_or_title:
                 logger.info(f"    Standardized Title/Dept (from '{title_to_standardize}'): '{standardized_department_or_title}'")
            else:
                 logger.warning(f"    Failed to standardize title: '{title_to_standardize}' - Check common_utils.py map")
                 safe_slug = re.sub(r'[^a-z0-9-]+', '-', title_to_standardize.lower()).strip('-')
                 standardized_department_or_title = f"unmapped-{safe_slug[:40]}"
        else:
             # This should ideally be caught by the `final_minister_title_raw` check earlier
             logger.error(f"    Cannot standardize department without a title for {letter_url}")
             # Create a fallback standardized name if absolutely necessary, though doc_id might also be generic
             standardized_department_or_title = f"unmapped-unknown-{int(time.time())}"


        # --- Generate Document ID ---
        doc_id_base = standardized_department_or_title if standardized_department_or_title and not standardized_department_or_title.startswith("unmapped-") else \
                      final_minister_title_raw # Use the actual title if standardization fails or is unmapped

        if doc_id_base:
            doc_id = re.sub(r'[^a-z0-9-]+', '-', doc_id_base.lower()).strip('-')[:70] # Increased length slightly
            if not doc_id: # if stripping leaves it empty
                 url_slug_part = letter_url.split('/')[-1].replace('-mandate-letter','').replace('.html','')
                 doc_id = f"generated-{re.sub(r'[^a-z0-9-]+', '-', url_slug_part.lower()).strip('-')[:50]}"
        else: # Absolute fallback for doc_id
            url_slug_part = letter_url.split('/')[-1].replace('-mandate-letter','').replace('.html','')
            doc_id = f"unknown-title-{re.sub(r'[^a-z0-9-]+', '-', url_slug_part.lower()).strip('-')[:50]}"
        
        if not doc_id: # Final fallback to ensure doc_id is never empty
             doc_id = f"fallback-id-{int(time.time())}"
        logger.debug(f"    Generated Doc ID: '{doc_id}'")

        # --- Return Data ---
        if not full_text:
            logger.error(f"    Failed to extract full_text from {letter_url}. Skipping record.")
            return None
        if not final_minister_title_raw: # Should have been caught, but double check
            logger.error(f"    Missing final_minister_title_raw for {letter_url}. Skipping record.")
            return None


        return {
            "doc_id": doc_id,
            "minister_first_name": minister_first_name, # From input via minister_full_name_input
            "minister_last_name": minister_last_name,   # From input or pm.gc.ca greeting
            "minister_full_name_input": minister_full_name_input, # Full name from CSV
            "minister_title_input": minister_title_input,       # Title as listed in the CSV
            "minister_title_scraped_pm_gc_ca": minister_title_scraped, # Title scraped from pm.gc.ca
            "standardized_department_or_title": standardized_department_or_title,
            "letter_url": letter_url,
            "full_text": full_text,
            "date_scraped": firestore.SERVER_TIMESTAMP,
            "minister_greeting_lastname_pm_gc_ca": minister_greeting_lastname, # Last name from "Dear Minister X:"
            "parliament_session_id": "44"
        }

    except requests.exceptions.Timeout:
        logger.error(f"    Timeout occurred while scraping {letter_url}")
        return None
    except requests.exceptions.RequestException as e:
        logger.error(f"    Request failed for {letter_url}: {e}")
        return None
    except Exception as e:
        logger.error(f"    Unexpected error scraping {letter_url}: {e}", exc_info=True)
        return None

def save_letter_to_firestore(letter_data):
    """Saves the scraped letter data to Firestore."""
    if not letter_data or not letter_data.get('doc_id'):
        logger.error("Invalid letter data or missing doc_id, cannot save.")
        return False

    doc_id = letter_data.pop('doc_id')
    if not doc_id: # Ensure doc_id is not empty after popping
        logger.error(f"Cannot save data with empty doc_id for URL {letter_data.get('letter_url')}")
        return False

    try:
        doc_ref = db.collection(FIRESTORE_COLLECTION).document(doc_id)
        doc_ref.set(letter_data) # Use set() to overwrite or create
        logger.info(f"  SUCCESS: Saved letter for '{letter_data.get('standardized_department_or_title', doc_id)}' to Firestore (ID: {doc_id}). Minister: {letter_data.get('minister_full_name_input')}") # Updated key here
        return True
    except Exception as e:
        logger.error(f"  ERROR: Failed to save letter '{doc_id}' to Firestore: {e}", exc_info=True)
        return False

# --- Main Execution ---
if __name__ == "__main__":
    logger.info("Starting Mandate Letter Scraper (CSV Input)...")
    # Get URLs, minister names, and titles from the CSV file
    minister_items = get_mandate_letters_data_from_csv(MANDATE_LETTERS_CSV_PATH)

    if not minister_items:
        logger.warning("No mandate letter items found from CSV or error fetching CSV file. Exiting.")
        exit()

    logger.info(f"Found {len(minister_items)} minister items from CSV. Starting scraping process...")
    success_count = 0
    fail_count = 0

    for item in minister_items:
        url = item.get("url")
        full_name = item.get("minister_full_name_input") # Use new key
        title_input = item.get("minister_title_input")   # Use new key

        if not url:
            logger.warning(f"Skipping item with no URL: {item}")
            fail_count += 1
            continue
        
        if not full_name:
            logger.warning(f"Processing URL {url} without a full name from CSV. Name fields might be sparse.")
        if not title_input:
            logger.warning(f"Processing URL {url} without a title from CSV. Title fields might be sparse.")


        scraped_data = scrape_single_letter(url, minister_full_name_input=full_name, minister_title_input=title_input)

        if scraped_data:
            if save_letter_to_firestore(scraped_data):
                success_count += 1
            else:
                fail_count += 1
        else:
            # scrape_single_letter already logs its errors
            fail_count += 1
        
        time.sleep(1.5) # Be polite

    logger.info(f"\n--- Scraping Complete ---")
    logger.info(f"Successfully scraped and saved: {success_count}")
    logger.info(f"Failed to scrape or save: {fail_count}")