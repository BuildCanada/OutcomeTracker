# scripts/scrape_mandate_letter_index.py
import requests
from bs4 import BeautifulSoup
import csv
import os
import time
import logging
import re
from urllib.parse import urljoin, urlparse
import tenacity # Import tenacity for retries

# --- Logger Setup ---
logging.basicConfig(level=logging.INFO,
                    format='%(asctime)s - %(levelname)s - %(filename)s:%(lineno)d - %(message)s',
                    datefmt='%Y-%m-%d %H:%M:%S')
logger = logging.getLogger(__name__)
# --- End Logger Setup ---

# --- Constants ---
WAYBACK_INDEX_URL = "https://web.archive.org/web/20240516200902/https://www.pm.gc.ca/en/mandate-letters"
WAYBACK_BASE = "https://web.archive.org"
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
OUTPUT_CSV_PATH = os.path.join(SCRIPT_DIR, '..', 'raw-data', 'MandateLetters.csv')
HEADERS = {'User-Agent': 'BuildCanadaPromiseTrackerBot/1.1 (+https://buildcanada.com/tracker-info)'}
REQUEST_DELAY = 2.0 # Seconds to wait between requests (Increased slightly)
REQUEST_TIMEOUT = 60  # Seconds for request timeout
MAX_RETRIES = 3 # Maximum number of retries for fetching individual pages
INITIAL_RETRY_DELAY = 5 # Initial delay in seconds for retries
# --- End Constants ---

def get_original_url_from_wayback(wayback_href):
    """Extracts the original URL from a Wayback Machine href."""
    # Example href: /web/20240516200902/https://www.pm.gc.ca/en/mandate-letters/...
    match = re.search(r'/(https?://.*)', wayback_href)
    if match:
        return match.group(1)
    logger.warning(f"Could not extract original URL from Wayback href: {wayback_href}")
    return None

def get_minister_name_from_h1(h1_text):
    """Extracts the Minister's name/title from the H1 text."""
    # Example H1: "Deputy Prime Minister and Minister of Finance Mandate Letter"
    # Example H1: "Minister of Citizens' Services Mandate Letter"
    # Handles potential variations in spacing or case
    match = re.match(r"^(.*?)\s+Mandate Letter$", h1_text.strip(), re.IGNORECASE)
    if match:
        return match.group(1).strip()
    logger.warning(f"Could not parse Minister name from H1: '{h1_text}'")
    return None # Return None if parsing fails

# Use tenacity for retries on connection errors/timeouts
@tenacity.retry(
    wait=tenacity.wait_exponential(multiplier=1, min=INITIAL_RETRY_DELAY, max=30), # Exponential backoff starting at 5s, max 30s
    stop=tenacity.stop_after_attempt(MAX_RETRIES),
    retry=(tenacity.retry_if_exception_type(requests.exceptions.RequestException)), # Retry on general request exceptions (includes connection/timeout)
    before_sleep=tenacity.before_sleep_log(logger, logging.WARNING), # Log before retrying
    reraise=True # Reraise the exception if all retries fail
)
def fetch_with_retry(url):
    """Fetches a URL with retries on failure."""
    logger.debug(f"  Fetching (attempt): {url}")
    response = requests.get(url, headers=HEADERS, timeout=REQUEST_TIMEOUT)
    response.raise_for_status() # Raise HTTPError for bad responses (4xx or 5xx)
    return response

def scrape_individual_letter_page(letter_wayback_url):
    """Scrapes the Minister's full name from an individual letter page, with retries."""
    logger.debug(f"Attempting to scrape individual letter page: {letter_wayback_url}")
    try:
        # Add delay *before* each attempt (moved from inside the fetch)
        time.sleep(REQUEST_DELAY)
        response = fetch_with_retry(letter_wayback_url)
        soup = BeautifulSoup(response.content, 'html5lib')

        # --- Refined Parsing Logic ---
        minister_name = None

        # Attempt 1: Find H1 specifically within common main content wrappers
        main_content = soup.find('main') or soup.find(id='main-content') or soup.find(class_='page-content') # Add common selectors
        if main_content:
            title_h1 = main_content.find('h1')
            if title_h1:
                minister_name = get_minister_name_from_h1(title_h1.get_text(strip=True))
                if minister_name:
                    logger.debug(f"    Extracted minister name from H1 within main content: {minister_name}")
                    return minister_name
                else:
                     logger.warning(f"    Found H1 in main content, but failed to parse name: '{title_h1.get_text(strip=True)}'")


        # Attempt 2: Find *any* H1 as a broader fallback (original logic, less reliable)
        if not minister_name:
             title_h1_any = soup.find('h1')
             if title_h1_any:
                 minister_name = get_minister_name_from_h1(title_h1_any.get_text(strip=True))
                 if minister_name:
                     logger.debug(f"    Extracted minister name from *any* H1 (fallback): {minister_name}")
                     return minister_name
                 else:
                     # Avoid logging 'Main Container' warning again if already tried above implicitly
                     if 'main_content' not in locals() or not main_content or not main_content.find('h1') == title_h1_any:
                          logger.warning(f"    Found generic H1, but failed to parse name: '{title_h1_any.get_text(strip=True)}'")


        # Attempt 3: Extract from the <title> tag (original fallback)
        if not minister_name:
            page_title_tag = soup.find('title')
            if page_title_tag:
                title_text = page_title_tag.get_text(strip=True)
                # Example: "Minister of Citizens' Services Mandate Letter | Prime Minister of Canada"
                # More robust regex to handle potential prefixes/suffixes from Wayback/Site
                title_match = re.search(r"^(?:Archived\s*-\s*)?(.*?)\s+Mandate Letter(?:.*\|\s*Prime Minister of Canada)?$", title_text, re.IGNORECASE)
                if title_match:
                    minister_name = title_match.group(1).strip()
                    # Basic sanity check - avoid things like just "Mandate Letter" if parsing goes wrong
                    if minister_name.lower() != "mandate letter" and len(minister_name) > 5:
                         logger.debug(f"    Extracted minister name from <title> (fallback): {minister_name}")
                         return minister_name
                    else:
                        logger.warning(f"    Parsed potential name from <title> seems invalid: '{minister_name}' (from title: '{title_text}')")
                        minister_name = None # Reset if invalid
                else:
                     logger.warning(f"    Could not parse minister name structure from <title>: '{title_text}'")

        logger.warning(f"    Could not find Minister name via H1 or Title tag on page: {letter_wayback_url}")
        return None # Return None if name couldn't be found after all attempts

    except tenacity.RetryError as e:
         logger.error(f"    Failed to fetch {letter_wayback_url} after {MAX_RETRIES} retries: {e}", exc_info=True)
         return None
    # Keep specific RequestException catch for non-retryable errors if fetch_with_retry reraises something unexpected
    except requests.exceptions.RequestException as e:
        logger.error(f"    Request failed unexpectedly for {letter_wayback_url} (outside retries): {e}")
        return None
    except Exception as e:
        logger.error(f"    Unexpected error processing {letter_wayback_url}: {e}", exc_info=True)
        return None

def main():
    logger.info(f"Starting scraper for mandate letter index: {WAYBACK_INDEX_URL}")
    logger.info(f"Output will be written to: {OUTPUT_CSV_PATH}")
    logger.info(f"Will retry failed page fetches up to {MAX_RETRIES} times with exponential backoff (initial delay {INITIAL_RETRY_DELAY}s).")

    successfully_scraped_data = [] # <<< Changed: Store only successful scrapes
    failed_scrapes = [] # <<< Added: Track failures

    try:
        logger.info("Fetching index page...")
        response = requests.get(WAYBACK_INDEX_URL, headers=HEADERS, timeout=REQUEST_TIMEOUT)
        response.raise_for_status()
        logger.info("Index page fetched successfully.")
        soup = BeautifulSoup(response.content, 'html5lib')

        letter_list_items = soup.select('li.mandate-letters-row')
        logger.info(f"Found {len(letter_list_items)} potential letter entries on index page.")

        if not letter_list_items:
             logger.error("No mandate letter list items found matching selector 'li.mandate-letters-row'. Check URL or selector.")
             return

        for item in letter_list_items:
            title_div = item.select_one('div.views-field-title span.field-content a')
            date_div = item.select_one('div.views-field-field-date-range time')

            if not title_div or not date_div:
                logger.warning("Skipping list item due to missing title or date element.")
                continue

            wayback_href = title_div.get('href')
            original_url = get_original_url_from_wayback(wayback_href)
            letter_title = title_div.get_text(strip=True) # This is the text like "Minister X Mandate Letter"
            letter_date = date_div.get_text(strip=True)

            if not original_url:
                logger.warning(f"Skipping item with title '{letter_title}' due to invalid URL.")
                continue

            # Construct the full URL to scrape from Wayback
            individual_letter_scrape_url = urljoin(WAYBACK_BASE, wayback_href)

            logger.info(f"Processing: '{letter_title}' ({letter_date})")
            # Scrape the individual page for the minister's actual name/title
            # The letter_title from the index often includes " Mandate Letter", which we want to replace
            # with the actual Minister Name scraped from the letter page itself.
            minister_name_scraped = scrape_individual_letter_page(individual_letter_scrape_url)

            if minister_name_scraped:
                # <<< Changed: Append to successful data list
                successfully_scraped_data.append({
                    "Department": minister_name_scraped, 
                    "Responsible Minister": minister_name_scraped, 
                    "Date of Mandate Letter": letter_date,
                    "Mandate Letter URL": original_url
                })
            else:
                logger.error(f"Failed to get minister name for {original_url}. Recording failure.")
                # <<< Changed: Record failure details instead of adding placeholder
                failed_scrapes.append({
                    'original_url': original_url,
                    'index_page_title': letter_title, # Title from the main index page
                    'scrape_url': individual_letter_scrape_url
                })


    except requests.exceptions.Timeout:
        logger.critical(f"Timeout occurred fetching index page: {WAYBACK_INDEX_URL}")
        return
    except requests.exceptions.RequestException as e:
        logger.critical(f"Request failed for index page {WAYBACK_INDEX_URL}: {e}")
        return
    except Exception as e:
        logger.critical(f"Unexpected error during index processing: {e}", exc_info=True)
        return # Stop if index fails

    # --- Write successful data to CSV ---
    if successfully_scraped_data:
        logger.info(f"Writing {len(successfully_scraped_data)} successfully scraped entries to {OUTPUT_CSV_PATH}")
        try:
            os.makedirs(os.path.dirname(OUTPUT_CSV_PATH), exist_ok=True)
            with open(OUTPUT_CSV_PATH, 'w', newline='', encoding='utf-8') as csvfile:
                fieldnames = ["Department", "Responsible Minister", "Date of Mandate Letter", "Mandate Letter URL"]
                writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
                writer.writeheader()
                writer.writerows(successfully_scraped_data) # <<< Changed: Write successful data
            logger.info("CSV file written successfully with scraped data.")
        except IOError as e:
            logger.critical(f"Failed to write CSV file at {OUTPUT_CSV_PATH}: {e}", exc_info=True)
        except Exception as e:
            logger.critical(f"An unexpected error occurred during CSV writing: {e}", exc_info=True)
    else:
        logger.warning("No data successfully scraped, CSV file will not be written.")

    # --- Report failures ---
    if failed_scrapes:
        logger.warning(f"--- Failed to scrape Minister names for {len(failed_scrapes)} entries: ---")
        for failure in failed_scrapes:
            logger.warning(f"  - URL: {failure['original_url']}")
            logger.warning(f"    Index Title: {failure['index_page_title']}")
            # logger.debug(f"    Scrape URL: {failure['scrape_url']}") # Optional: more debug info
        logger.warning("These entries were NOT added to MandateLetters.csv. Manual addition or further processing needed.")
    else:
        logger.info("All entries scraped successfully!")

    logger.info("Script finished.")

if __name__ == "__main__":
    main() 