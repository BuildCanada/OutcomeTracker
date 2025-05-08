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
# Configure logging basic settings
logging.basicConfig(level=logging.INFO, 
                    format='%(asctime)s - %(levelname)s - %(filename)s:%(lineno)d - %(message)s',
                    datefmt='%Y-%m-%d %H:%M:%S')
# Get the logger instance for this module
logger = logging.getLogger(__name__)
# --- End Logger Setup ---

# --- Firebase Configuration ---
# Initialize db variable to None initially
db = None 
if not firebase_admin._apps:
    if os.getenv('FIRESTORE_EMULATOR_HOST'):
        options = {'projectId': 'promisetrackerapp'} # Replace with your actual project ID if different
        try:
             firebase_admin.initialize_app(options=options)
             logger.info(f"Python (Mandate Scraper): Connected to Firestore Emulator at {os.getenv('FIRESTORE_EMULATOR_HOST')} using project ID '{options['projectId']}'")
             db = firestore.client() # Assign the client to db
        except Exception as e:
             logger.critical(f"Firebase init failed: {e}", exc_info=True)
             exit("Exiting: Firebase connection failed.")
    else:
        logger.error("FIRESTORE_EMULATOR_HOST environment variable not set.")
        exit("Exiting: Firestore emulator not configured.")
else:
    logger.info("Firebase app already initialized. Getting client.")
    db = firestore.client() # Get client if already initialized

# Final check if db is assigned
if db is None:
     logger.critical("Failed to obtain Firestore client. Exiting.")
     exit("Exiting: Firestore client not available.")
# --- End Firebase Configuration ---

# --- Constants ---
BLOG_URL = "https://librarianship.ca/blog/ministerial-mandate-letters-2021-2/"
TARGET_DOMAIN = "pm.gc.ca"
TARGET_PATH_CONTAINS = "/en/mandate-letters/" 
TARGET_YEAR_IN_PATH = "/2021/" 
HEADERS = {'User-Agent': 'BuildCanadaPromiseTrackerBot/1.0 (+https://buildcanada.com/tracker-info)'}
FIRESTORE_COLLECTION = 'mandate_letters_fulltext'
# --- End Constants ---

def get_mandate_letter_urls(blog_url):
    """Fetches the blog page and extracts relevant mandate letter URLs."""
    urls = set()
    logger.info(f"Fetching mandate letter links from: {blog_url}")
    try:
        response = requests.get(blog_url, headers=HEADERS, timeout=30) # Increased timeout
        logger.debug(f"Blog page status code: {response.status_code}")
        response.raise_for_status()
        soup = BeautifulSoup(response.content, 'html.parser')

        # Find H3 tags, then the link inside them
        h3_tags = soup.find_all('h3')
        logger.debug(f"Found {len(h3_tags)} total <h3> tags.")

        found_matching_links = 0
        for h3 in h3_tags:
            link_tag = h3.find('a', href=True) 
            if link_tag:
                href = link_tag['href']
                # Apply filters
                if TARGET_DOMAIN in href and TARGET_PATH_CONTAINS in href and TARGET_YEAR_IN_PATH in href:
                    found_matching_links += 1
                    absolute_url = urljoin(blog_url, href)
                    if absolute_url not in urls:
                        urls.add(absolute_url)
                        logger.info(f"  SUCCESS: Found matching URL: {absolute_url} (Text: '{link_tag.get_text(strip=True)}')")

        if found_matching_links == 0:
             logger.warning(f"No links matched the criteria on blog page. Check TARGET_DOMAIN/PATH_CONTAINS/YEAR_IN_PATH.")

        logger.info(f"Found {len(urls)} unique potential mandate letter URLs matching criteria.")
        return list(urls)

    except requests.exceptions.Timeout:
        logger.error(f"Timeout occurred while fetching blog page {blog_url}")
        return []
    except requests.exceptions.RequestException as e:
        logger.error(f"Failed to fetch or read blog page {blog_url}: {e}")
        return []
    except Exception as e:
        logger.error(f"Unexpected error getting URLs: {e}", exc_info=True)
        return []

def scrape_single_letter(letter_url):
    """Scrapes the Minister's title/name and full text from a single mandate letter page."""
    logger.info(f"Scraping: {letter_url}")
    try:
        response = requests.get(letter_url, headers=HEADERS, timeout=30) # Increased timeout
        response.raise_for_status()
        # Use 'html5lib' parser for potentially better handling of modern HTML
        soup = BeautifulSoup(response.content, 'html5lib') 

        minister_name_raw = None
        minister_title_raw = None
        full_text = None

        # --- STRATEGY 1: Extract Title from H1 ---
        # Use a more specific selector based on inspection of pm.gc.ca source
        title_h1 = soup.select_one('div.title-header-inner h1') 
        if title_h1:
            title_text = title_h1.get_text(strip=True)
            # Extract the part before " Mandate Letter"
            match = re.match(r"(.*?)\s+Mandate Letter", title_text, re.IGNORECASE)
            if match:
                minister_title_raw = match.group(1).strip()
                logger.info(f"    Extracted Title from H1: '{minister_title_raw}'")
            else:
                 logger.warning(f"    Could not parse expected format from H1: '{title_text}'")
        else:
            logger.warning(f"    Could not find H1 title element using selector on page: {letter_url}")
            # --- Fallback: Extract Title from <title> tag ---
            page_title_tag = soup.find('title')
            if page_title_tag:
                page_title_text = page_title_tag.get_text(strip=True)
                logger.debug(f"    Page <title>: '{page_title_text}'")
                match = re.match(r"(.*?)\s+Mandate Letter", page_title_text, re.IGNORECASE)
                if match:
                    minister_title_raw = match.group(1).strip()
                    logger.info(f"    Extracted Title from <title> (Fallback): '{minister_title_raw}'")
                else:
                    logger.warning(f"    Could not parse expected title format from <title> tag (Fallback): '{page_title_text}'")

        # --- STRATEGY 2: Extract Minister Name from Greeting ---
        # Selector for the div containing the paragraphs 
        content_div = soup.select_one('div.field--name-body.field--type-text-with-summary') 
        if content_div:
            first_p = content_div.find('p', recursive=False) # Find direct child paragraph
            if first_p:
                greeting = first_p.get_text(strip=True)
                # Example: "Dear Minister Champagne:" or "Dear Minister O'Regan:" etc.
                name_match = re.match(r"Dear Minister (.*?):", greeting, re.IGNORECASE)
                if name_match:
                    minister_name_raw = name_match.group(1).strip()
                    # Handle titles like "LeBlanc" which might be extracted if not careful
                    if minister_name_raw.lower() == 'leblanc': # Add other single names if needed
                         # Try finding a stronger name indicator elsewhere if this happens often
                         logger.warning(f"    Extracted name '{minister_name_raw}' might be incomplete.")
                    logger.info(f"    Extracted Name from Greeting: '{minister_name_raw}'")
                else:
                    logger.warning(f"    Could not parse name from greeting: '{greeting}'")
            else:
                 logger.warning(f"    Could not find first paragraph directly in content div for greeting.")
                 
            # --- STRATEGY 3: Extract Full Text from paragraphs within the content div ---
            paragraphs = content_div.find_all('p') # Find all paragraphs within
            letter_paragraphs = []
            skip_greeting = True 
            for p in paragraphs:
                 # Skip the first paragraph which is the greeting
                 if skip_greeting:
                      skip_greeting = False
                      continue
                      
                 p_text = p.get_text(separator=' ', strip=True)
                 # Basic filter - avoid signature lines and potentially empty paragraphs after cleaning
                 if p_text and not p_text.lower().startswith("sincerely,") \
                    and not p_text.lower().startswith("rt. hon.") \
                    and not p_text.lower() == "prime minister of canada" \
                    and "*this ministerial mandate letter was signed" not in p_text.lower():
                    letter_paragraphs.append(p_text)

            if letter_paragraphs:
                full_text = "\n\n".join(letter_paragraphs).strip() # Join and strip final whitespace
                extracted_text_length = len(full_text)
                logger.info(f"    Extracted text length: {extracted_text_length} characters.")
            else:
                logger.warning(f"    No suitable paragraphs found within content div for {letter_url}")
        else:
            logger.warning(f"    Could not find main content div using selector 'div.field--name-body...' for {letter_url}")


        # --- Standardize Title/Department ---
        standardized_department_or_title = None
        if minister_title_raw:
            # Use the common_utils function
            standardized_department_or_title = standardize_department_name(minister_title_raw) 
            if standardized_department_or_title:
                 logger.info(f"    Standardized Title/Dept: '{standardized_department_or_title}'")
            else:
                 # Log failure and create a placeholder based on raw title
                 logger.warning(f"    Failed to standardize title: '{minister_title_raw}' - Check common_utils.py map")
                 safe_slug = re.sub(r'[^a-z0-9-]+', '-', minister_title_raw.lower()).strip('-')
                 standardized_department_or_title = f"unmapped-{safe_slug[:40]}" 
        else:
             logger.error(f"    Cannot proceed without extracted minister title for {letter_url}")
             return None # Cannot create a meaningful record without the title


        # --- Generate Document ID ---
        # Preferentially use the standardized department name for linking
        doc_id = None
        if standardized_department_or_title and not standardized_department_or_title.startswith("unmapped-"):
            # Slugify the standardized name
            doc_id = standardized_department_or_title.lower()
            doc_id = re.sub(r'\s+', '-', doc_id) # Replace spaces with hyphens
            doc_id = re.sub(r'[^a-z0-9-]+', '', doc_id) # Remove non-alphanumeric/hyphens
            doc_id = doc_id.strip('-')
        elif minister_title_raw: # Fallback to raw title if standardization failed but title exists
            doc_id = re.sub(r'[^a-z0-9-]+', '-', minister_title_raw.lower()).strip('-')[:50]
        else: # Last resort using URL part
            try:
                # Try getting a meaningful part from the URL slug
                url_slug = letter_url.split('/')[-1] # Get last part of URL path
                if url_slug.endswith('-mandate-letter'):
                     url_slug = url_slug[:-len('-mandate-letter')]
                doc_id = re.sub(r'[^a-z0-9-]+', '-', url_slug.lower()).strip('-')[:50]
            except Exception: # Broad exception if URL parsing fails
                 doc_id = f"unknown-mandate-{int(time.time())}" # Absolute fallback
        
        if not doc_id: # Ensure we always have an ID
            doc_id = f"fallback-id-{int(time.time())}"
        logger.debug(f"    Generated Doc ID: '{doc_id}'")

        # --- Return Data ---
        if minister_title_raw and full_text:
            return {
                "doc_id": doc_id, 
                "minister_name_raw": minister_name_raw, # Extracted from greeting
                "minister_title_raw": minister_title_raw, # Extracted from H1 or Title
                "standardized_department_or_title": standardized_department_or_title, # Standardized name (or placeholder)
                "letter_url": letter_url,
                "full_text": full_text, # Excludes greeting and closing
                "date_scraped": firestore.SERVER_TIMESTAMP
            }
        else:
            missing_parts = []
            if not minister_title_raw: missing_parts.append("title")
            if not full_text: missing_parts.append("text")
            logger.error(f"    Failed to extract required component(s) ({', '.join(missing_parts)}) from {letter_url}. Skipping.")
            return None

    except requests.exceptions.Timeout:
        logger.error(f"    Timeout occurred while scraping {letter_url}")
        return None
    except requests.exceptions.RequestException as e:
        logger.error(f"    Request failed for {letter_url}: {e}")
        return None
    except Exception as e:
        logger.error(f"    Unexpected error scraping {letter_url}: {e}", exc_info=True)
        return None

# --- save_letter_to_firestore function ---
def save_letter_to_firestore(letter_data):
    """Saves the scraped letter data to Firestore."""
    if not letter_data or not letter_data.get('doc_id'):
        logger.error("Invalid letter data or missing doc_id, cannot save.")
        return False

    # Use the generated doc_id as the Firestore document ID
    doc_id = letter_data.pop('doc_id') 
    # Ensure doc_id is not empty after popping
    if not doc_id:
        logger.error(f"Cannot save data with empty doc_id for URL {letter_data.get('letter_url')}")
        return False

    try:
        doc_ref = db.collection(FIRESTORE_COLLECTION).document(doc_id)
        doc_ref.set(letter_data) # Use set() to overwrite or create
        logger.info(f"  SUCCESS: Saved letter for '{letter_data.get('minister_title_raw', doc_id)}' to Firestore (ID: {doc_id}).")
        return True
    except Exception as e:
        logger.error(f"  ERROR: Failed to save letter '{doc_id}' to Firestore: {e}", exc_info=True)
        return False

# --- Main Execution ---
if __name__ == "__main__":
    logger.info("Starting 2021 Mandate Letter Scraper...")
    letter_urls = get_mandate_letter_urls(BLOG_URL)

    if not letter_urls:
        logger.warning("No mandate letter URLs found matching criteria or error fetching blog page. Exiting.")
        exit() 

    logger.info(f"Found {len(letter_urls)} URLs. Starting scraping process...")
    success_count = 0
    fail_count = 0

    for url in letter_urls:
        scraped_data = scrape_single_letter(url)
        if scraped_data:
            if save_letter_to_firestore(scraped_data):
                success_count += 1
            else:
                fail_count += 1
        else:
            fail_count += 1
        
        # Be polite - add a small delay between requests
        time.sleep(1.5) # Keep delay

    logger.info(f"\n--- Scraping Complete ---")
    logger.info(f"Successfully scraped and saved: {success_count}")
    logger.info(f"Failed to scrape or save: {fail_count}")