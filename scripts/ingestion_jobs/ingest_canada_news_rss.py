"""
Ingests raw news release data from Canada News Centre RSS feeds into Firestore. Filters out items that are not in the target categories of backgrounders, statements, or speeches.
Also filters out items that are outside the date range specified.
Also filters out items that are already in the Firestore database.

CLI arguments:
--start_date: The start date to ingest from. Format: YYYY-MM-DD. Default: 2025-03-25
--end_date: The end date to ingest to. Format: YYYY-MM-DD. Default: today
--dry_run: If True, will not write to Firestore. Default: False
--output_to_json: If True, will write to a JSON file. Default: False
--JSON_output_dir: The directory to write the JSON file to. Default: ./JSON_outputs

Next steps to make ready for production:
- add check for last run date in Firestore and only ingest items that are newer than that
- add any changes or config to run with docker
- schedule cron job run hourly
"""

import os
import logging
import feedparser
import hashlib
from datetime import datetime, timezone, date
from dotenv import load_dotenv
import firebase_admin
from firebase_admin import credentials, firestore
import argparse
import time # For unique app name fallback
from dateutil import parser as dateutil_parser # For parsing date strings flexibly
import json # Added for JSON output
import requests # Added for web scraping
from bs4 import BeautifulSoup 

# --- Configuration ---
load_dotenv()
# --- Logger Setup ---
logging.basicConfig(level=logging.INFO,
                    format='%(asctime)s - %(levelname)s - %(filename)s:%(lineno)d - %(message)s',
                    datefmt='%Y-%m-%d %H:%M:%S')
logger = logging.getLogger("ingest_canada_news_rss")
# --- End Logger Setup ---

# --- Constants ---
RSS_FEEDS_TO_MONITOR = {
    "National News": "https://api.io.canada.ca/io-server/gc/news/en/v2?sort=publishedDate&orderBy=desc&pick=100&format=atom&atomtitle=National%20News&publishedDate%3E={start_date}",
    #"Backgrounders": "https://api.io.canada.ca/io-server/gc/news/en/v2?type=backgrounders&sort=publishedDate&orderBy=desc&pick=100&format=atom&atomtitle=backgrounders&publishedDate%3E={start_date}",
    #"Speeches": "https://api.io.canada.ca/io-server/gc/news/en/v2?type=speeches&sort=publishedDate&orderBy=desc&pick=100&format=atom&atomtitle=speeches&publishedDate%3E={start_date}",

}

RAW_NEWS_RELEASES_COLLECTION = "raw_news_releases"
DEFAULT_PAGE_SIZE = 100
DEFAULT_START_DATE_STR = "2025-03-25"
# Define JSON_OUTPUT_DIR relative to the script's location
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
JSON_OUTPUT_DIR = os.path.join(SCRIPT_DIR, "..", "JSON_outputs") # Corrected path
# --- End Constants ---

# --- Firebase Configuration ---
db = None
if not firebase_admin._apps:
    try:
        firebase_admin.initialize_app()
        project_id_env = os.getenv('FIREBASE_PROJECT_ID', '[Not Set - Using Default]')
        logger.info(f"Connected to CLOUD Firestore (Project: {project_id_env}) using default credentials.")
        db = firestore.client()
    except Exception as e_default:
        logger.warning(f"Cloud Firestore init with default creds failed: {e_default}. Attempting service account.")
        cred_path = os.getenv('FIREBASE_SERVICE_ACCOUNT_KEY_PATH')
        if cred_path:
            try:
                logger.info(f"Attempting Firebase init with service account key from env var: {cred_path}")
                cred = credentials.Certificate(cred_path)
                app_name = 'ingest_news_rss_app'
                try:
                    firebase_admin.initialize_app(cred, name=app_name)
                except ValueError: # App already exists
                    app_name_unique = f"{app_name}_{str(time.time())}"
                    firebase_admin.initialize_app(cred, name=app_name_unique)
                    app_name = app_name_unique

                project_id_sa_env = os.getenv('FIREBASE_PROJECT_ID', '[Not Set - Using Service Account]')
                logger.info(f"Connected to CLOUD Firestore (Project: {project_id_sa_env}) via service account.")
                db = firestore.client(app=firebase_admin.get_app(name=app_name))
            except Exception as e_sa:
                logger.critical(f"Firebase init with service account key from {cred_path} failed: {e_sa}", exc_info=True)
        else:
            logger.warning("FIREBASE_SERVICE_ACCOUNT_KEY_PATH environment variable not set, and default creds failed.")

if db is None:
    logger.critical("CRITICAL: Failed to obtain Firestore client. Exiting.")
    exit("Exiting: Firestore client not available.")
# --- End Firebase Configuration ---

# --- Helper Functions ---

def scrape_full_text(url, logger_instance):
    """
    Scrapes the main content from a given URL.
    Prioritizes content within <main property='mainContentOfPage'>.
    Returns the cleaned text or None if an error occurs or content isn't found.
    """
    try:
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        }
        response = requests.get(url, headers=headers, timeout=15) # Added timeout
        response.raise_for_status()  # Raises an HTTPError for bad responses (4XX or 5XX)

        soup = BeautifulSoup(response.content, 'html.parser')

        # Try to find the specific main content container for Canada.ca news
        main_content = soup.find('main', attrs={'property': 'mainContentOfPage'})

        if main_content:
            # Remove known non-content sections if necessary (e.g., social media share buttons, related links within main)
            # Example: for el in main_content.select('.wb-share, .related-links'): el.decompose()
            text = main_content.get_text(separator='\n', strip=True)
            logger_instance.debug(f"Successfully scraped main content from {url} using <main property='mainContentOfPage'>.")
            return text
        else:
            # Fallback: try to get all text from body, might be noisy
            # You might want to refine this further, e.g., by targeting specific divs or removing header/footer
            logger_instance.warning(f"<main property='mainContentOfPage'> not found on {url}. Attempting generic body text extraction.")
            body_content = soup.find('body')
            if body_content:
                text = body_content.get_text(separator='\n', strip=True)
                # Basic clean up for very long texts or script/style tags if not handled well by get_text
                # This is a very naive cleanup, more sophisticated methods exist
                lines = [line for line in text.splitlines() if len(line.strip()) > 20] # Keep lines with some substance
                cleaned_text = "\n".join(lines)
                if len(cleaned_text) > 10000: # Arbitrary limit to avoid huge unwanted data
                    cleaned_text = cleaned_text[:10000] + "... [truncated]"
                logger_instance.debug(f"Scraped generic body text from {url} (length: {len(cleaned_text)}).")
                return cleaned_text
            else:
                logger_instance.warning(f"Could not find <body> tag in {url}. No text scraped.")
                return None

    except requests.exceptions.RequestException as e:
        logger_instance.error(f"Error fetching URL {url} for scraping: {e}")
        return None
    except Exception as e:
        logger_instance.error(f"Error scraping content from {url}: {e}", exc_info=True)
        return None

def get_parliament_session_id(db_client, publication_date_dt):
    # Implementation of get_parliament_session_id function
    return None

def parse_publication_date(entry):
    """
    Parses the publication date from an RSS entry.
    Handles 'published_parsed' (struct_time) and 'published' (string).
    Also falls back to 'updated' and 'updated_parsed'.
    Returns a timezone-aware datetime object or None.
    """
    pub_date_dt = None
    logger.debug(f"Attempting to parse date for entry. Available date fields: published='{entry.get('published')}', published_parsed='{entry.get('published_parsed')}', updated='{entry.get('updated')}', updated_parsed='{entry.get('updated_parsed')}'")

    if hasattr(entry, 'published_parsed') and entry.published_parsed:
        logger.debug(f"Using 'published_parsed': {entry.published_parsed}")
        pub_date_dt = datetime(*entry.published_parsed[:6], tzinfo=timezone.utc)
    elif hasattr(entry, 'published') and entry.published:
        logger.debug(f"Attempting to parse 'published' string: {entry.published}")
        try:
            pub_date_dt = dateutil_parser.parse(entry.published)
            if pub_date_dt.tzinfo is None:
                 pub_date_dt = pub_date_dt.replace(tzinfo=timezone.utc)
            logger.debug(f"Successfully parsed 'published' string to: {pub_date_dt}")
        except Exception as e:
            logger.warning(f"Could not parse 'published' string '{entry.published}': {e}")
    # Fallback to 'updated' if 'published' is not available or failed parsing
    if not pub_date_dt:
        logger.debug("'published' parsing failed or not available. Checking 'updated' fields.")
        if hasattr(entry, 'updated_parsed') and entry.updated_parsed:
            logger.debug(f"Using 'updated_parsed': {entry.updated_parsed}")
            pub_date_dt = datetime(*entry.updated_parsed[:6], tzinfo=timezone.utc)
        elif hasattr(entry, 'updated') and entry.updated:
            logger.debug(f"Attempting to parse 'updated' string: {entry.updated}")
            try:
                pub_date_dt = dateutil_parser.parse(entry.updated)
                if pub_date_dt.tzinfo is None:
                    pub_date_dt = pub_date_dt.replace(tzinfo=timezone.utc)
                logger.debug(f"Successfully parsed 'updated' string to: {pub_date_dt}")
            except Exception as e:
                logger.warning(f"Could not parse 'updated' string '{entry.updated}': {e}")

    if not pub_date_dt:
        logger.warning(f"Failed to parse any date field for entry with link: {entry.get('link', 'N/A')}")
    return pub_date_dt

# --- Main Ingestion Logic ---

def _process_entry(entry, db_client, start_date_filter, end_date_filter, feed_name, paginated_feed_url, logger_instance):
    """
    Processes a single RSS entry, performs filtering, and prepares data.
    Returns news_item_data if successful and filters pass, otherwise None.
    """
    try:
        source_url = entry.get("link")
        title_raw = entry.get("title")
        publication_date_dt = parse_publication_date(entry)

        if not source_url or not title_raw or not publication_date_dt:
            logger_instance.warning(f"Skipping entry due to missing critical data (URL, Title, or PubDate): {entry.get('id', 'N/A')}")
            return None, False # Data, is_error
        
        # Create a unique ID
        date_yyyymmdd_str = publication_date_dt.strftime('%Y%m%d')
        original_hash_input = f"{source_url}_{publication_date_dt.isoformat()}"
        full_hash = hashlib.sha256(original_hash_input.encode('utf-8')).hexdigest()
        short_hash = full_hash[:12]
        raw_item_id = f"{date_yyyymmdd_str}_CANADANEWS_{short_hash}"

        logger_instance.debug(f"RAW_ITEM_ID_DEBUG: For URL '{source_url}'")
        logger_instance.debug(f"RAW_ITEM_ID_DEBUG:   Generated raw_item_id: {raw_item_id}")

        # Date range filter (applied client-side after API filter)
        if start_date_filter and publication_date_dt.date() < start_date_filter:
            logger_instance.debug(f"CLIENT_FILTER_SKIP (Before Start): Item {source_url} with pub date {publication_date_dt.date()} (before {start_date_filter})")
            return None, False # Skipped, not an error in processing entry itself
        if end_date_filter and publication_date_dt.date() > end_date_filter:
            logger_instance.debug(f"CLIENT_FILTER_SKIP (After End): Item {source_url} with pub date {publication_date_dt.date()} (after {end_date_filter})")
            return None, False # Skipped, not an error

        summary_or_snippet_raw = entry.get("summary") or entry.get("description")
        categories_rss_original = [tag.term for tag in entry.get("tags", []) if hasattr(tag, 'term') and tag.term]
        department_rss_tag = next((tag.term for tag in entry.get("tags", []) if hasattr(tag, 'scheme') and tag.scheme and "department" in tag.scheme.lower()), None)
        department_rss_author = entry.get("author_detail", {}).get("name") if entry.get("author_detail") else entry.get("author")
        dc_creator = entry.get('dc_creator')
        department_rss = department_rss_tag or dc_creator or department_rss_author

        parliament_session_id = get_parliament_session_id(db_client, publication_date_dt) if db_client else None

        parsed_categories_lower = [cat.lower() for cat in categories_rss_original]
        target_categories = {"backgrounders", "statements", "speeches"}
        if not any(cat_lower in target_categories for cat_lower in parsed_categories_lower):
            logger_instance.debug(f"Skipping item (ID: {raw_item_id}) due to category filter. Categories: {categories_rss_original}. URL: {source_url}")
            return None, False # Skipped due to category, not an error

        full_text = None
        if source_url:
            logger_instance.debug(f"Attempting to scrape full text for: {source_url}")
            full_text = scrape_full_text(source_url, logger_instance)
            if full_text:
                logger_instance.debug(f"Successfully scraped text for {source_url} (length: {len(full_text)}).")
            else:
                logger_instance.warning(f"Failed to scrape text or no text found for {source_url}.")

        news_item_data = {
            "raw_item_id": raw_item_id,
            "source_url": source_url,
            "publication_date": publication_date_dt,
            "title_raw": title_raw,
            "summary_or_snippet_raw": summary_or_snippet_raw,
            "full_text_scraped": full_text,
            "rss_feed_url_used": paginated_feed_url,
            "source_feed_name": feed_name,
            "categories_rss": categories_rss_original if categories_rss_original else None,
            "department_rss": department_rss,
            "ingested_at": firestore.SERVER_TIMESTAMP, # Placeholder, will be set for JSON
            "evidence_processing_status": "pending_evidence_creation",
            "related_evidence_item_id": None,
            "parliament_session_id_assigned": parliament_session_id
        }
        return news_item_data, False # Successful processing, not an error

    except Exception as e:
        logger_instance.error(f"Error processing entry {entry.get('link', 'N/A')} within _process_entry: {e}", exc_info=True)
        return None, True # Indicate an error occurred


def fetch_and_process_feeds(db_client, dry_run=False, start_date_filter=None, end_date_filter=None, output_to_json=False):
    """
    Fetches RSS feeds, processes items, and stores them in Firestore or outputs to JSON.
    Uses the provided db_client for Firestore operations.
    """
    logger.info("Starting RSS feed ingestion process...")
    if dry_run:
        logger.info("*** DRY RUN MODE ENABLED - No data will be written to Firestore. ***")
    if start_date_filter:
        logger.info(f"Filtering entries: Only processing items published on or after {start_date_filter.strftime('%Y-%m-%d')}")
    if end_date_filter:
        logger.info(f"Filtering entries: Only processing items published on or before {end_date_filter.strftime('%Y-%m-%d')}")
    if output_to_json: # Added
        logger.info("*** JSON OUTPUT MODE ENABLED - New items will be written to a JSON file instead of Firestore. ***")

    newly_ingested_count = 0 # For items actually added or that would be added
    skipped_duplicates_count = 0
    error_count = 0
    min_publication_date_ingested = None
    max_publication_date_ingested = None
    items_considered_for_processing = 0
    items_for_json_output = [] # Added for JSON output
    item_id_to_feed_sources = {} # For tracking item_id across feeds in this run
    processed_item_ids_in_current_run = set() # To ensure only first encounter goes to JSON/Firestore

    for feed_name, feed_url_template in RSS_FEEDS_TO_MONITOR.items():
        current_skip = 0
        fetch_more = True

        while fetch_more:
            feed_url = feed_url_template
            if "{start_date}" in feed_url_template:
                if start_date_filter:
                    # Format YYYY-MM-DD for the API
                    api_start_date = start_date_filter.strftime('%Y-%m-%d') 
                    feed_url = feed_url_template.format(start_date=api_start_date)
                else:
                    # This case should ideally not be reached if main() ensures start_date_filter is always set.
                    logger.error(f"CRITICAL_ERROR: Feed {feed_name} is templated for a start date, but no start_date_filter was provided to fetch_and_process_feeds. This should not happen. Skipping this feed.")
                    fetch_more = False
                    continue # Skip this feed
            
            # Add skip parameter for pagination if not already present in a base template
            # Assuming pick is already in the template or defaults to 100
            # The API uses 'pick' for page size and we are testing 'skip' for offset.
            paginated_feed_url = f"{feed_url}&skip={current_skip}"
            # Ensure 'pick' is also there. The templates already have pick=100.
            # If templates didn't have pick, we would add &pick={DEFAULT_PAGE_SIZE} here too.

            logger.info(f"Fetching feed: {feed_name} - Page offset: {current_skip} - URL: {paginated_feed_url}")
            try:
                feed = feedparser.parse(paginated_feed_url)
            except Exception as e:
                logger.error(f"Error fetching or parsing feed {paginated_feed_url}: {e}", exc_info=True)
                error_count += 1
                fetch_more = False # Stop trying this feed on error
                continue

            if not feed.entries:
                logger.info(f"No more entries found for {feed_name} at offset {current_skip}. Moving to next feed or finishing.")
                fetch_more = False
                continue
            
            entries_in_batch = len(feed.entries)
            logger.debug(f"Received {entries_in_batch} entries in current batch for {feed_name} (offset {current_skip}).")

            batch_had_new_ingestable_items = False # Reset for each batch from API

            for entry in feed.entries:
                items_considered_for_processing += 1 # Counted as soon as it's pulled from feed
                
                news_item_data, entry_processing_error = _process_entry(
                    entry, db_client, start_date_filter, end_date_filter, 
                    feed_name, paginated_feed_url, logger
                )

                if entry_processing_error:
                    error_count += 1
                    continue # to next entry
                
                if not news_item_data: # Skipped due to filters or missing data in _process_entry
                    # The specific skip reason (date, category) is logged within _process_entry
                    # We need to update the main skip counters if we want to maintain them here.
                    # For now, simplifying by letting _process_entry log the skip and we just continue.
                    # If detailed skip counts are crucial, _process_entry could return a skip type.
                    # For this refactor, let's assume detailed main counters for skips are less critical than clarity.
                    # We will rely on the logs from _process_entry for why it was skipped.
                    # However, we still need to update skipped_date_filter_count and skipped_category_filter_count
                    # For now, let's remove those counters from the summary and rely on logs, or decide to return detailed skip reasons.
                    # Decision: for now, _process_entry logs skips, main function tracks general errors.
                    # The specific counters for date/category skips at the summary level will be less accurate with this change
                    # unless _process_entry returns a more detailed status.
                    # To maintain accuracy of skipped_date_filter_count and skipped_category_filter_count, 
                    # _process_entry would need to return *why* it returned None.
                    # Let's adjust _process_entry slightly to return a skip reason for accurate counting.

                    # Re-thinking: For now, _process_entry handles its own logging of skips.
                    # The main function will just note an item was skipped if news_item_data is None and not an error.
                    # The summary counts for `skipped_date_filter_count` and `skipped_category_filter_count` 
                    # will become inaccurate. We should remove them or enhance _process_entry.
                    # For this iteration, I will remove those specific counters from the summary to avoid confusion,
                    # as their logic is now fully encapsulated in _process_entry's logging.
                    continue

                raw_item_id = news_item_data["raw_item_id"]
                publication_date_dt = news_item_data["publication_date"] # Already a datetime object

                # --- Overlap Tracking --- Start
                if raw_item_id not in item_id_to_feed_sources:
                    item_id_to_feed_sources[raw_item_id] = set()
                item_id_to_feed_sources[raw_item_id].add(feed_name)
                # --- Overlap Tracking --- End
                
                # Firestore Idempotency Check (against previous runs)
                firestore_doc_exists = False
                if db_client:
                    doc_ref = db_client.collection(RAW_NEWS_RELEASES_COLLECTION).document(raw_item_id)
                    existing_doc = doc_ref.get()
                    if existing_doc.exists:
                        firestore_doc_exists = True
                        logger.debug(f"FIRESTORE_CHECK_DEBUG: raw_item_id '{raw_item_id}' - existing_doc.exists: TRUE")
                    else:
                        logger.debug(f"FIRESTORE_CHECK_DEBUG: raw_item_id '{raw_item_id}' - existing_doc.exists: FALSE")
                else:
                    logger.debug(f"FIRESTORE_CHECK_DEBUG: db_client is None, cannot check Firestore for raw_item_id '{raw_item_id}'")

                if firestore_doc_exists:
                    if not dry_run:
                        logger.debug(f"Skipping duplicate item (ID: {raw_item_id}) already in Firestore: {news_item_data['source_url']}")
                        skipped_duplicates_count += 1
                        continue
                    else:
                        logger.info(f"[DRY RUN] Item (ID: {raw_item_id}) already exists in Firestore: {news_item_data['source_url']}. Would be skipped.")
                        skipped_duplicates_count += 1
                        continue
                
                if raw_item_id in processed_item_ids_in_current_run:
                    logger.debug(f"Skipping item (ID: {raw_item_id}) as it was already encountered from another feed/page in THIS run. URL: {news_item_data['source_url']}")
                    continue

                # If we reach here, the item is new for this run and not in Firestore from previous runs.
                processed_item_ids_in_current_run.add(raw_item_id)
                batch_had_new_ingestable_items = True # Crucial: set this if an item makes it this far

                if output_to_json:
                    json_compatible_item_data = news_item_data.copy()
                    if json_compatible_item_data.get("ingested_at") == firestore.SERVER_TIMESTAMP:
                        json_compatible_item_data["ingested_at"] = datetime.now(timezone.utc).isoformat()
                    elif isinstance(json_compatible_item_data.get("ingested_at"), datetime):
                         json_compatible_item_data["ingested_at"] = json_compatible_item_data["ingested_at"].isoformat()

                    for key, value in json_compatible_item_data.items():
                        if isinstance(value, datetime):
                            json_compatible_item_data[key] = value.isoformat()
                        elif isinstance(value, date):
                            json_compatible_item_data[key] = value.isoformat()
                        
                    items_for_json_output.append(json_compatible_item_data)
                    logger.info(f"Prepared for JSON output (ID: {raw_item_id}): {news_item_data['source_url']}")
                    newly_ingested_count +=1
                elif not dry_run:
                    if db_client:
                        doc_ref_for_write = db_client.collection(RAW_NEWS_RELEASES_COLLECTION).document(raw_item_id)
                        doc_ref_for_write.set(news_item_data)
                        logger.info(f"Successfully ingested item (ID: {raw_item_id}) into Firestore: {news_item_data['source_url']}")
                        newly_ingested_count +=1
                    else:
                        logger.error(f"CRITICAL: Attempted to write to Firestore but db_client is None. Item: {raw_item_id}")
                        error_count += 1
                else: # dry_run and not output_to_json
                    log_data = {k: (v.isoformat() if isinstance(v, (datetime, date)) else v) for k, v in news_item_data.items()}
                    logger.info(f"[DRY RUN] Would ingest item (ID: {raw_item_id}) into Firestore: {news_item_data['source_url']} with data: {log_data}")
                    newly_ingested_count +=1

                if min_publication_date_ingested is None or publication_date_dt < min_publication_date_ingested:
                    min_publication_date_ingested = publication_date_dt
                if max_publication_date_ingested is None or publication_date_dt > max_publication_date_ingested:
                    max_publication_date_ingested = publication_date_dt
                
                # Note: entry_processing_error and other specific skips are handled/logged inside _process_entry or immediately after its call.

            # Pagination logic update
            if entries_in_batch < DEFAULT_PAGE_SIZE:
                logger.info(f"Last page for {feed_name} reached (received {entries_in_batch} items, expected up to {DEFAULT_PAGE_SIZE}).")
                fetch_more = False
            else:
                 # If we got a full page, there might be more.
                 # Add a safeguard: if a full batch yielded no new ingestable items (all filtered out or duplicates from a previous identical page due to API error),
                 # then stop to prevent infinite loops on faulty feeds.
                if not batch_had_new_ingestable_items and entries_in_batch > 0:
                    logger.warning(f"Full batch of {entries_in_batch} items for {feed_name} at offset {current_skip} yielded no new items to ingest. Stopping pagination for this feed to prevent potential loop.")
                    fetch_more = False
                else:
                    current_skip += DEFAULT_PAGE_SIZE
                    logger.info(f"Potentially more items for {feed_name}. Moving to next page, offset {current_skip}.")

    # After processing all feeds
    if output_to_json and items_for_json_output:
        try:
            os.makedirs(JSON_OUTPUT_DIR, exist_ok=True)
            timestamp_str = datetime.now().strftime("%Y%m%d_%H%M%S")
            json_filename = os.path.join(JSON_OUTPUT_DIR, f"ingested_news_{timestamp_str}.json")
            with open(json_filename, 'w') as f:
                json.dump(items_for_json_output, f, indent=4, ensure_ascii=False)
            logger.info(f"Successfully wrote {len(items_for_json_output)} items to JSON file: {json_filename}")
        except Exception as e:
            logger.error(f"Error writing items to JSON file: {e}", exc_info=True)
            error_count += len(items_for_json_output) # Count these as errors if file write fails

    # --- Log Overlapping Items --- Start
    logger.info("--- Feed Overlap Analysis (Items appearing in multiple feeds THIS RUN) ---")
    overlapping_items_count = 0
    for item_id, sources in item_id_to_feed_sources.items():
        if len(sources) > 1:
            logger.info(f"Overlap: Item ID {item_id} found in feeds: {sources}")
            overlapping_items_count += 1
    if overlapping_items_count == 0:
        logger.info("No items appeared in more than one feed during this run.")
    else:
        logger.info(f"Total items appearing in multiple feeds this run: {overlapping_items_count}")
    logger.info("--- End Feed Overlap Analysis ---")
    # --- Log Overlapping Items --- End

    logger.info("--- Ingestion Summary ---")
    logger.info(f"Total items considered for processing (after basic API fetch, before script date filter): {items_considered_for_processing}")
    if output_to_json:
        logger.info(f"Items prepared for JSON output: {newly_ingested_count}")
    elif dry_run:
        logger.info(f"Items that WOULD BE newly ingested (Dry Run): {newly_ingested_count}")
    else:
        logger.info(f"Items newly ingested into Firestore: {newly_ingested_count}")
    logger.info(f"Items skipped (already existed in Firestore): {skipped_duplicates_count}")
    logger.info(f"Errors during processing: {error_count}")
    if min_publication_date_ingested:
        logger.info(f"Earliest publication date ingested: {min_publication_date_ingested.strftime('%Y-%m-%d %H:%M:%S %Z')}")
    if max_publication_date_ingested:
        logger.info(f"Latest publication date ingested: {max_publication_date_ingested.strftime('%Y-%m-%d %H:%M:%S %Z')}")
    logger.info("--- End of Ingestion Summary ---")

def main():
    parser = argparse.ArgumentParser(description="Ingest Canada News Centre RSS feeds into Firestore.")
    parser.add_argument("--dry_run", action="store_true", help="Perform a dry run without writing to Firestore.")
    parser.add_argument("--start_date", type=str, help=f"Start date filter (YYYY-MM-DD). Overrides default: {DEFAULT_START_DATE_STR}")
    parser.add_argument("--end_date", type=str, help="End date filter (YYYY-MM-DD). Defaults to today if not specified.")
    parser.add_argument("--log_level", type=str, default="INFO", choices=["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"], help="Set the logging level.")
    parser.add_argument("--JSON", action="store_true", help="Output ingested items to a JSON file instead of Firestore.") # Added

    args = parser.parse_args()
    logger.setLevel(getattr(logging, args.log_level.upper()))

    if db is None: # Check if Firestore client was initialized
        logger.critical("Firestore client (db) is not initialized. Cannot proceed. Check Firebase configuration and credentials.")
        return # Exit if db is not available

    effective_start_date = None
    if args.start_date:
        try:
            effective_start_date = datetime.strptime(args.start_date, "%Y-%m-%d").date()
            logger.info(f"Using command-line --start_date: {effective_start_date.strftime('%Y-%m-%d')}")
        except ValueError:
            logger.error(f"Invalid --start_date format: {args.start_date}. Please use YYYY-MM-DD. Exiting.")
            return
    else:
        try:
            effective_start_date = datetime.strptime(DEFAULT_START_DATE_STR, "%Y-%m-%d").date()
            logger.info(f"Using hardcoded default start date: {effective_start_date.strftime('%Y-%m-%d')}")
        except ValueError: # Should not happen with a valid hardcoded date string
            logger.critical(f"CRITICAL: Hardcoded DEFAULT_START_DATE_STR ('{DEFAULT_START_DATE_STR}') is invalid. Please fix. Exiting.")
            return

    effective_end_date = None
    if args.end_date:
        try:
            effective_end_date = datetime.strptime(args.end_date, "%Y-%m-%d").date()
            logger.info(f"Using command-line --end_date: {effective_end_date.strftime('%Y-%m-%d')}")
        except ValueError:
            logger.error(f"Invalid --end_date format: {args.end_date}. Please use YYYY-MM-DD. Exiting.")
            return
    else:
        effective_end_date = date.today() # Use date.today() for a date object
        logger.info(f"No --end_date provided. Defaulting to today: {effective_end_date.strftime('%Y-%m-%d')}")

    # Validate that start_date is not after end_date
    if effective_start_date and effective_end_date and effective_start_date > effective_end_date:
        logger.error(f"Error: Start date ({effective_start_date.strftime('%Y-%m-%d')}) cannot be after end date ({effective_end_date.strftime('%Y-%m-%d')}). Exiting.")
        return

    fetch_and_process_feeds(db, args.dry_run, effective_start_date, effective_end_date, args.JSON)

if __name__ == "__main__":
    main() 