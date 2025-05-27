"""
BULK INGESTION - One-time ingestion of all available Canada News items
for specific content types: backgrounders, speeches, and statements.

This script is designed for a one-time bulk import to get all historical data
available from the Canada News API for the three content types we care about.

Based on ingest_canada_news.py but simplified for bulk processing:
- Removes date filtering (since API ignores it anyway)
- Increases batch size for efficiency
- Focuses on the three specific content types
- Optimized for one-time use

CLI arguments:
--dry_run: If True, will not write to Firestore. Default: False
--output_to_json: If True, will write to a JSON file instead of Firestore. Default: False
--max_pages: Maximum number of pages to fetch per content type. Default: 50
--batch_size: Number of items to fetch per API call. Default: 200
"""

import os
import sys
import logging
import feedparser
import hashlib
from datetime import datetime, timezone, date
from dotenv import load_dotenv
import firebase_admin
from firebase_admin import credentials, firestore
import argparse
import time
from dateutil import parser as dateutil_parser
import json
import requests
from bs4 import BeautifulSoup 

# --- Configuration ---
load_dotenv()

# --- Logger Setup ---
logging.basicConfig(level=logging.INFO,
                    format='%(asctime)s - %(levelname)s - %(filename)s:%(lineno)d - %(message)s',
                    datefmt='%Y-%m-%d %H:%M:%S')
logger = logging.getLogger("bulk_ingest_canada_news")

# --- Constants for Bulk Ingestion ---
BULK_CONTENT_TYPES = {
    "backgrounders": "https://api.io.canada.ca/io-server/gc/news/en/v2?type=backgrounders&sort=publishedDate&orderBy=desc&pick={batch_size}&format=atom&atomtitle=backgrounders",
    "speeches": "https://api.io.canada.ca/io-server/gc/news/en/v2?type=speeches&sort=publishedDate&orderBy=desc&pick={batch_size}&format=atom&atomtitle=speeches", 
    "statements": "https://api.io.canada.ca/io-server/gc/news/en/v2?type=statements&sort=publishedDate&orderBy=desc&pick={batch_size}&format=atom&atomtitle=statements"
}

RAW_NEWS_RELEASES_COLLECTION = "raw_news_releases"
DEFAULT_BATCH_SIZE = 200  # Increased from 100 for bulk ingestion
DEFAULT_MAX_PAGES = 50    # Limit to prevent infinite loops
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
JSON_OUTPUT_DIR = os.path.join(SCRIPT_DIR, "..", "JSON_outputs")

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
                app_name = 'bulk_ingest_news_app'
                try:
                    firebase_admin.initialize_app(cred, name=app_name)
                except ValueError:
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
        response = requests.get(url, headers=headers, timeout=15)
        response.raise_for_status()

        soup = BeautifulSoup(response.content, 'html.parser')
        main_content = soup.find('main', attrs={'property': 'mainContentOfPage'})

        if main_content:
            text = main_content.get_text(separator='\n', strip=True)
            logger_instance.debug(f"Successfully scraped main content from {url} using <main property='mainContentOfPage'>.")
            return text
        else:
            logger_instance.warning(f"<main property='mainContentOfPage'> not found on {url}. Attempting generic body text extraction.")
            body_content = soup.find('body')
            if body_content:
                text = body_content.get_text(separator='\n', strip=True)
                lines = [line for line in text.splitlines() if len(line.strip()) > 20]
                cleaned_text = "\n".join(lines)
                if len(cleaned_text) > 10000:
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

def parse_publication_date(entry):
    """
    Parses the publication date from an RSS entry.
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

def _process_entry(entry, content_type, feed_url_template, batch_size, logger_instance):
    """
    Processes a single RSS entry for bulk ingestion.
    Returns news_item_data if successful, otherwise None.
    """
    try:
        # Basic field extraction
        title = entry.get('title', '').strip()
        description = entry.get('summary', '').strip()
        source_url = entry.get('link', '').strip()
        
        if not source_url:
            logger_instance.warning("Entry missing source URL, skipping.")
            return None
            
        if not title:
            logger_instance.warning(f"Entry missing title for URL {source_url}, skipping.")
            return None

        # Parse publication date
        publication_date_dt = parse_publication_date(entry)
        if not publication_date_dt:
            logger_instance.warning(f"Could not parse publication date for entry {source_url}, skipping.")
            return None

        # Generate unique ID using consistent format
        date_yyyymmdd_str = publication_date_dt.strftime('%Y%m%d')
        original_hash_input = f"{source_url}_{publication_date_dt.isoformat()}"
        full_hash = hashlib.sha256(original_hash_input.encode('utf-8')).hexdigest()
        short_hash = full_hash[:12]
        raw_item_id = f"{date_yyyymmdd_str}_CANADANEWS_{short_hash}"

        # Scrape full content
        full_content = scrape_full_text(source_url, logger_instance)
        
        # Prepare news item data with consistent field names
        news_item_data = {
            "raw_item_id": raw_item_id,
            "title_raw": title,  # Consistent with ingest_canada_news.py
            "summary_or_snippet_raw": description,  # Consistent with ingest_canada_news.py
            "source_url": source_url,
            "publication_date": publication_date_dt,
            "full_text_scraped": full_content,  # Consistent with ingest_canada_news.py
            "ingested_at": firestore.SERVER_TIMESTAMP,
            "evidence_processing_status": "pending_evidence_creation",  # Ready for evidence processing
            "related_evidence_item_id": None,
            "parliament_session_id_assigned": None,  # Could be enhanced later
            # Additional fields from bulk ingestion
            "content_type": content_type,  # backgrounders, speeches, or statements
            "source_feed": "canada_news_api",
            "rss_feed_url_used": feed_url_template.format(batch_size=batch_size),
            "source_feed_name": f"canada_news_{content_type}",
            "categories_rss": [content_type],  # Set content type as category
            "department_rss": None  # Could be enhanced with department extraction
        }
        
        logger_instance.debug(f"Successfully processed entry: {title} ({source_url})")
        return news_item_data
        
    except Exception as e:
        logger_instance.error(f"Error processing entry: {e}", exc_info=True)
        return None

# --- Main Bulk Ingestion Logic ---

def bulk_ingest_content_type(content_type, feed_url_template, batch_size, max_pages, db_client, dry_run=False, output_to_json=False):
    """
    Performs bulk ingestion for a specific content type.
    Returns statistics about the ingestion.
    """
    logger.info(f"Starting bulk ingestion for content type: {content_type}")
    
    newly_ingested_count = 0
    skipped_duplicates_count = 0
    error_count = 0
    processed_item_ids = set()
    items_for_json = []
    min_date = None
    max_date = None
    
    current_skip = 0
    page_count = 0
    consecutive_empty_pages = 0
    
    while page_count < max_pages:
        # Build paginated URL
        feed_url = feed_url_template.format(batch_size=batch_size)
        paginated_url = f"{feed_url}&skip={current_skip}"
        
        logger.info(f"Fetching {content_type} - Page {page_count + 1}/{max_pages} (offset: {current_skip})")
        logger.debug(f"URL: {paginated_url}")
        
        try:
            feed = feedparser.parse(paginated_url)
        except Exception as e:
            logger.error(f"Error fetching feed for {content_type}: {e}", exc_info=True)
            error_count += 1
            break
            
        if not feed.entries:
            consecutive_empty_pages += 1
            logger.info(f"No entries found for {content_type} at offset {current_skip}")
            
            if consecutive_empty_pages >= 3:  # Stop after 3 consecutive empty pages
                logger.info(f"Stopping {content_type} ingestion after {consecutive_empty_pages} consecutive empty pages")
                break
        else:
            consecutive_empty_pages = 0  # Reset counter
            
        entries_in_batch = len(feed.entries)
        logger.info(f"Processing {entries_in_batch} entries for {content_type}")
        
        new_items_in_batch = 0
        
        for entry in feed.entries:
            news_item_data = _process_entry(entry, content_type, feed_url_template, batch_size, logger)
            
            if not news_item_data:
                error_count += 1
                continue
                
            raw_item_id = news_item_data["raw_item_id"]
            publication_date_dt = news_item_data["publication_date"]
            
            # Check if already processed in this run
            if raw_item_id in processed_item_ids:
                logger.debug(f"Item {raw_item_id} already processed in this run, skipping")
                continue
                
            # Check if exists in Firestore
            firestore_doc_exists = False
            if db_client:
                doc_ref = db_client.collection(RAW_NEWS_RELEASES_COLLECTION).document(raw_item_id)
                existing_doc = doc_ref.get()
                firestore_doc_exists = existing_doc.exists
                
            if firestore_doc_exists:
                logger.debug(f"Item {raw_item_id} already exists in Firestore, skipping")
                skipped_duplicates_count += 1
                continue
                
            # Track dates
            if min_date is None or publication_date_dt < min_date:
                min_date = publication_date_dt
            if max_date is None or publication_date_dt > max_date:
                max_date = publication_date_dt
                
            processed_item_ids.add(raw_item_id)
            new_items_in_batch += 1
            
            # Store or output the item
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
                        
                items_for_json.append(json_compatible_item_data)
                logger.info(f"Prepared {content_type} item for JSON: {news_item_data['title_raw'][:80]}...")
                newly_ingested_count += 1
                
            elif not dry_run:
                if db_client:
                    doc_ref = db_client.collection(RAW_NEWS_RELEASES_COLLECTION).document(raw_item_id)
                    doc_ref.set(news_item_data)
                    logger.info(f"Ingested {content_type} item: {news_item_data['title_raw'][:80]}...")
                    newly_ingested_count += 1
                else:
                    logger.error(f"No Firestore client available for item: {raw_item_id}")
                    error_count += 1
            else:  # dry run
                logger.info(f"[DRY RUN] Would ingest {content_type} item: {news_item_data['title_raw'][:80]}...")
                newly_ingested_count += 1
        
        logger.info(f"Processed page {page_count + 1} for {content_type}: {new_items_in_batch} new items, {entries_in_batch} total entries")
        
        # Check if we should continue pagination
        if entries_in_batch < batch_size:
            logger.info(f"Last page reached for {content_type} (got {entries_in_batch} < {batch_size})")
            break
            
        # Move to next page
        current_skip += batch_size
        page_count += 1
    
    # Save JSON output if applicable
    if output_to_json and items_for_json:
        try:
            os.makedirs(JSON_OUTPUT_DIR, exist_ok=True)
            timestamp_str = datetime.now().strftime("%Y%m%d_%H%M%S")
            json_filename = os.path.join(JSON_OUTPUT_DIR, f"bulk_ingest_{content_type}_{timestamp_str}.json")
            with open(json_filename, 'w') as f:
                json.dump(items_for_json, f, indent=4, ensure_ascii=False)
            logger.info(f"Wrote {len(items_for_json)} {content_type} items to: {json_filename}")
        except Exception as e:
            logger.error(f"Error writing {content_type} JSON file: {e}", exc_info=True)
            error_count += len(items_for_json)
    
    # Return statistics
    return {
        "content_type": content_type,
        "newly_ingested": newly_ingested_count,
        "skipped_duplicates": skipped_duplicates_count,
        "errors": error_count,
        "pages_processed": page_count,
        "min_date": min_date,
        "max_date": max_date
    }

def main():
    parser = argparse.ArgumentParser(description="Bulk ingest Canada News Centre content for backgrounders, speeches, and statements.")
    parser.add_argument("--dry_run", action="store_true", help="Perform a dry run without writing to Firestore.")
    parser.add_argument("--output_to_json", action="store_true", help="Output to JSON files instead of Firestore.")
    parser.add_argument("--max_pages", type=int, default=DEFAULT_MAX_PAGES, help=f"Maximum pages per content type (default: {DEFAULT_MAX_PAGES})")
    parser.add_argument("--batch_size", type=int, default=DEFAULT_BATCH_SIZE, help=f"Items per API call (default: {DEFAULT_BATCH_SIZE})")
    parser.add_argument("--log_level", type=str, default="INFO", choices=["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"], help="Set the logging level.")
    parser.add_argument("--content_types", nargs='+', choices=list(BULK_CONTENT_TYPES.keys()), default=list(BULK_CONTENT_TYPES.keys()), help="Specific content types to ingest")

    args = parser.parse_args()
    logger.setLevel(getattr(logging, args.log_level.upper()))

    if db is None:
        logger.critical("Firestore client not initialized. Check Firebase configuration.")
        return

    logger.info("=== STARTING BULK CANADA NEWS INGESTION ===")
    logger.info(f"Content types: {args.content_types}")
    logger.info(f"Batch size: {args.batch_size}")
    logger.info(f"Max pages per type: {args.max_pages}")
    logger.info(f"Dry run: {args.dry_run}")
    logger.info(f"Output to JSON: {args.output_to_json}")

    start_time = time.time()
    all_stats = []
    
    for content_type in args.content_types:
        feed_url_template = BULK_CONTENT_TYPES[content_type]
        stats = bulk_ingest_content_type(
            content_type=content_type,
            feed_url_template=feed_url_template,
            batch_size=args.batch_size,
            max_pages=args.max_pages,
            db_client=db,
            dry_run=args.dry_run,
            output_to_json=args.output_to_json
        )
        all_stats.append(stats)
        
        logger.info(f"=== {content_type.upper()} COMPLETED ===")
        logger.info(f"  New items: {stats['newly_ingested']}")
        logger.info(f"  Duplicates skipped: {stats['skipped_duplicates']}")
        logger.info(f"  Errors: {stats['errors']}")
        logger.info(f"  Pages processed: {stats['pages_processed']}")
        if stats['min_date'] and stats['max_date']:
            logger.info(f"  Date range: {stats['min_date'].strftime('%Y-%m-%d')} to {stats['max_date'].strftime('%Y-%m-%d')}")
    
    # Final summary
    total_time = time.time() - start_time
    total_new = sum(s['newly_ingested'] for s in all_stats)
    total_duplicates = sum(s['skipped_duplicates'] for s in all_stats)
    total_errors = sum(s['errors'] for s in all_stats)
    
    logger.info("=== BULK INGESTION COMPLETE ===")
    logger.info(f"Total runtime: {total_time:.2f} seconds")
    logger.info(f"Total new items: {total_new}")
    logger.info(f"Total duplicates skipped: {total_duplicates}")
    logger.info(f"Total errors: {total_errors}")
    
    # Show overall date range
    all_min_dates = [s['min_date'] for s in all_stats if s['min_date']]
    all_max_dates = [s['max_date'] for s in all_stats if s['max_date']]
    if all_min_dates and all_max_dates:
        overall_min = min(all_min_dates)
        overall_max = max(all_max_dates)
        logger.info(f"Overall date range: {overall_min.strftime('%Y-%m-%d')} to {overall_max.strftime('%Y-%m-%d')}")

if __name__ == "__main__":
    main() 