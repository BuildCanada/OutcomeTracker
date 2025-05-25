"""
Checks LEGISinfo RSS feed for recently updated bills to optimize ingestion efficiency.
Parses the RSS feed to identify bills that have had recent activity, allowing the
main ingestion system to focus only on bills that actually need updating.

CLI arguments:
--hours_threshold: Only return bills updated within this many hours (default: 24)
--max_items: Maximum number of RSS items to check (default: 100, RSS feed typically shows ~50-100 recent items)
--parliament_filter: Only include bills from this parliament number (e.g., 44)
--output_format: Output format - 'json', 'csv', or 'list' (default: json)
--output_file: File to write results to (optional, prints to stdout if not specified)
--log_level: Set the logging level (default: INFO)

Usage examples:
# Get bills updated in last 24 hours
python check_legisinfo_rss_updates.py

# Get bills updated in last 6 hours, Parliament 44 only
python check_legisinfo_rss_updates.py --hours_threshold 6 --parliament_filter 44

# Output as CSV file
python check_legisinfo_rss_updates.py --output_format csv --output_file recent_bills.csv

# Integration with main ingestion (example)
python check_legisinfo_rss_updates.py --hours_threshold 12 --output_file bills_to_update.json
python ingest_legisinfo_raw_bills.py --rss_filter_file bills_to_update.json
"""

import os
import logging
import json
import csv
import argparse
import feedparser
from datetime import datetime, timezone, timedelta
from dotenv import load_dotenv
import re
import time

# --- Configuration ---
load_dotenv()

# --- Logger Setup ---
logging.basicConfig(level=logging.INFO,
                    format='%(asctime)s - %(levelname)s - %(filename)s:%(lineno)d - %(message)s',
                    datefmt='%Y-%m-%d %H:%M:%S')
logger = logging.getLogger("check_legisinfo_rss_updates")
# --- End Logger Setup ---

# --- Constants ---
LEGISINFO_RSS_URL = "https://www.parl.ca/legisinfo/en/bills/rss"
DEFAULT_HOURS_THRESHOLD = 24
DEFAULT_MAX_ITEMS = 100
HEADERS = {'User-Agent': 'BuildCanadaPromiseTrackerBot/1.0 RSS Checker'}
# --- End Constants ---

def parse_bill_info_from_rss_item(item):
    """
    Extract bill information from an RSS item.
    
    Returns:
        dict: Bill information including parliament, session, bill_code, title, description, pub_date
        None: If parsing fails
    """
    try:
        # Extract from GUID/link: https://www.parl.ca/legisinfo/en/bill/44-1/S-1
        guid = item.get('guid', item.get('link', ''))
        if not guid:
            logger.warning("RSS item missing GUID/link")
            return None
        
        # Parse parliament session and bill code from URL
        # Expected format: https://www.parl.ca/legisinfo/en/bill/44-1/S-1
        match = re.search(r'/bill/(\d+)-(\d+)/([A-Z]-\d+)', guid)
        if not match:
            logger.warning(f"Could not parse bill info from GUID: {guid}")
            return None
        
        parliament_num = match.group(1)
        session_num = match.group(2) 
        bill_code = match.group(3)
        
        # Parse publication date
        pub_date = None
        if 'published_parsed' in item and item['published_parsed']:
            pub_date = datetime(*item['published_parsed'][:6], tzinfo=timezone.utc)
        elif 'published' in item:
            # Fallback to string parsing
            try:
                from email.utils import parsedate_to_datetime
                pub_date = parsedate_to_datetime(item['published'])
                if pub_date.tzinfo is None:
                    pub_date = pub_date.replace(tzinfo=timezone.utc)
            except Exception as e:
                logger.warning(f"Could not parse publication date: {item.get('published', 'N/A')} - {e}")
        
        # Extract title and description
        title = item.get('title', '').strip()
        description = item.get('description', '').strip()
        
        return {
            'parliament_num': parliament_num,
            'session_num': session_num,
            'bill_code': bill_code,
            'parliament_session_id': f"{parliament_num}-{session_num}",
            'human_readable_id': f"{parliament_num}-{session_num}_{bill_code}",
            'title': title,
            'description': description,
            'pub_date': pub_date,
            'pub_date_iso': pub_date.isoformat() if pub_date else None,
            'rss_guid': guid,
            'legisinfo_url': guid,
            'json_detail_url': f"https://www.parl.ca/legisinfo/en/bill/{parliament_num}-{session_num}/{bill_code}/json?view=details"
        }
        
    except Exception as e:
        logger.error(f"Error parsing RSS item: {e}")
        return None

def fetch_rss_updates(hours_threshold=DEFAULT_HOURS_THRESHOLD, max_items=DEFAULT_MAX_ITEMS, parliament_filter=None):
    """
    Fetch and parse LEGISinfo RSS feed for recent updates.
    
    Args:
        hours_threshold: Only include bills updated within this many hours
        max_items: Maximum RSS items to process
        parliament_filter: Only include bills from this parliament number
        
    Returns:
        list: List of bill info dictionaries for recently updated bills
    """
    logger.info(f"Fetching RSS feed from: {LEGISINFO_RSS_URL}")
    logger.info(f"Filtering for updates within last {hours_threshold} hours")
    if parliament_filter:
        logger.info(f"Filtering for Parliament {parliament_filter} only")
    
    # Import monitoring
    try:
        from .rss_monitoring_logger import rss_monitor
        monitor_id = rss_monitor.log_rss_check_start(hours_threshold, parliament_filter)
    except ImportError:
        try:
            from rss_monitoring_logger import rss_monitor
            monitor_id = rss_monitor.log_rss_check_start(hours_threshold, parliament_filter)
        except ImportError:
            logger.warning("RSS monitoring not available")
            rss_monitor = None
            monitor_id = None
    
    start_time = time.time()
    
    try:
        # Set user agent for feedparser
        feedparser.USER_AGENT = HEADERS['User-Agent']
        
        # Parse RSS feed
        feed = feedparser.parse(LEGISINFO_RSS_URL)
        
        if feed.bozo:
            logger.warning(f"RSS feed parsing had issues: {feed.bozo_exception}")
        
        if not hasattr(feed, 'entries') or not feed.entries:
            logger.error("No entries found in RSS feed")
            return []
        
        logger.info(f"Found {len(feed.entries)} total entries in RSS feed")
        
        # Calculate cutoff time
        cutoff_time = datetime.now(timezone.utc) - timedelta(hours=hours_threshold)
        logger.info(f"Filtering for items published after: {cutoff_time.isoformat()}")
        
        recent_bills = []
        processed_count = 0
        
        for entry in feed.entries[:max_items]:  # Limit to max_items
            processed_count += 1
            
            # Parse bill info from RSS entry
            bill_info = parse_bill_info_from_rss_item(entry)
            if not bill_info:
                continue
            
            # Apply parliament filter
            if parliament_filter and int(bill_info['parliament_num']) != parliament_filter:
                logger.debug(f"Skipping bill {bill_info['bill_code']} - not in Parliament {parliament_filter}")
                continue
            
            # Apply time filter
            if bill_info['pub_date'] and bill_info['pub_date'] >= cutoff_time:
                recent_bills.append(bill_info)
                logger.info(f"Found recent update: {bill_info['bill_code']} ({bill_info['parliament_session_id']}) - {bill_info['pub_date_iso']}")
            else:
                # RSS feeds are typically ordered by date, so we can break early for efficiency
                # if we start seeing older items (though not guaranteed)
                if bill_info['pub_date']:
                    logger.debug(f"Item {bill_info['bill_code']} too old: {bill_info['pub_date_iso']}")
        
        logger.info(f"Processed {processed_count} RSS entries")
        logger.info(f"Found {len(recent_bills)} bills with recent updates")
        
        # Log success
        if rss_monitor and monitor_id:
            response_time_ms = int((time.time() - start_time) * 1000)
            rss_monitor.log_rss_check_result(monitor_id, True, len(recent_bills), None, response_time_ms)
        
        return recent_bills
        
    except Exception as e:
        logger.error(f"Error fetching/parsing RSS feed: {e}", exc_info=True)
        
        # Log failure
        if rss_monitor and monitor_id:
            response_time_ms = int((time.time() - start_time) * 1000) if 'start_time' in locals() else None
            rss_monitor.log_rss_check_result(monitor_id, False, 0, str(e), response_time_ms)
        
        return []

def output_results(bills, output_format='json', output_file=None):
    """
    Output the results in the specified format.
    
    Args:
        bills: List of bill info dictionaries
        output_format: 'json', 'csv', or 'list'
        output_file: File path to write to (optional)
    """
    if not bills:
        logger.info("No bills to output")
        if output_file:
            # Create empty file
            with open(output_file, 'w') as f:
                if output_format == 'json':
                    f.write('[]')
                elif output_format == 'csv':
                    f.write('')  # Empty CSV
                else:
                    f.write('')
        return
    
    if output_format == 'json':
        output_data = json.dumps(bills, indent=2, ensure_ascii=False, default=str)
    elif output_format == 'csv':
        # Prepare CSV data
        import io
        output_buffer = io.StringIO()
        if bills:
            fieldnames = ['human_readable_id', 'parliament_session_id', 'bill_code', 'title', 'pub_date_iso', 'json_detail_url']
            writer = csv.DictWriter(output_buffer, fieldnames=fieldnames)
            writer.writeheader()
            for bill in bills:
                writer.writerow({k: bill.get(k, '') for k in fieldnames})
        output_data = output_buffer.getvalue()
    elif output_format == 'list':
        # Simple list of human-readable IDs
        output_data = '\n'.join([bill['human_readable_id'] for bill in bills])
    else:
        raise ValueError(f"Unsupported output format: {output_format}")
    
    if output_file:
        with open(output_file, 'w', encoding='utf-8') as f:
            f.write(output_data)
        logger.info(f"Results written to: {output_file}")
    else:
        print(output_data)

def main():
    parser = argparse.ArgumentParser(description="Check LEGISinfo RSS feed for recently updated bills.")
    parser.add_argument("--hours_threshold", type=int, default=DEFAULT_HOURS_THRESHOLD,
                       help=f"Only return bills updated within this many hours (default: {DEFAULT_HOURS_THRESHOLD})")
    parser.add_argument("--max_items", type=int, default=DEFAULT_MAX_ITEMS,
                       help=f"Maximum RSS items to check (default: {DEFAULT_MAX_ITEMS})")
    parser.add_argument("--parliament_filter", type=int,
                       help="Only include bills from this parliament number (e.g., 44)")
    parser.add_argument("--output_format", type=str, default="json", choices=['json', 'csv', 'list'],
                       help="Output format (default: json)")
    parser.add_argument("--output_file", type=str,
                       help="File to write results to (prints to stdout if not specified)")
    parser.add_argument("--log_level", type=str, default="INFO",
                       choices=['DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL'],
                       help="Set the logging level")
    
    args = parser.parse_args()
    logger.setLevel(getattr(logging, args.log_level.upper()))
    
    logger.info("--- Starting LEGISinfo RSS Update Check ---")
    
    # Fetch recent updates
    recent_bills = fetch_rss_updates(
        hours_threshold=args.hours_threshold,
        max_items=args.max_items,
        parliament_filter=args.parliament_filter
    )
    
    # Output results
    output_results(recent_bills, args.output_format, args.output_file)
    
    logger.info(f"--- RSS Update Check Complete: Found {len(recent_bills)} recent updates ---")

if __name__ == "__main__":
    main() 