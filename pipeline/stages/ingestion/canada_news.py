"""
Canada News Ingestion Job

Ingests news releases from Canada.ca RSS feeds into the raw_news_releases collection.
This replaces the existing ingest_canada_news.py script with a more robust,
class-based implementation.
"""

import logging
import sys
import feedparser
import requests
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional
from urllib.parse import urljoin, urlparse
from pathlib import Path
from bs4 import BeautifulSoup

# Handle imports for both module execution and testing
try:
    from .base_ingestion import BaseIngestionJob
except ImportError:
    # Add pipeline directory to path for testing
    pipeline_dir = Path(__file__).parent.parent.parent
    sys.path.insert(0, str(pipeline_dir))
    from stages.ingestion.base_ingestion import BaseIngestionJob


class CanadaNewsIngestion(BaseIngestionJob):
    """
    Ingestion job for Canada.ca news releases.
    
    Fetches news from RSS feeds and stores in raw_news_releases collection.
    """
    
    def __init__(self, job_name: str, config: Dict[str, Any] = None):
        """Initialize the Canada News ingestion job"""
        super().__init__(job_name, config)
        
        # RSS feed URLs for different departments - using working Canada.ca API
        self.rss_feeds = self.config.get('rss_feeds', {
            # Use the working Canada.ca API format from original scripts
            # 'national_news': 'https://api.io.canada.ca/io-server/gc/news/en/v2?sort=publishedDate&orderBy=desc&pick=100&format=atom&atomtitle=National%20News&publishedDate%3E={start_date}',
            # 'pmo': 'https://www.pm.gc.ca/en/news/rss.xml',
            'backgrounders': 'https://api.io.canada.ca/io-server/gc/news/en/v2?type=backgrounders&sort=publishedDate&orderBy=desc&pick=100&format=atom&atomtitle=backgrounders&publishedDate%3E={start_date}',
            'speeches': 'https://api.io.canada.ca/io-server/gc/news/en/v2?type=speeches&sort=publishedDate&orderBy=desc&pick=100&format=atom&atomtitle=speeches&publishedDate%3E={start_date}',
            'statements': 'https://api.io.canada.ca/io-server/gc/news/en/v2?type=statements&sort=publishedDate&orderBy=desc&pick=100&format=atom&atomtitle=statements&publishedDate%3E={start_date}'
        })
        
        # Request timeout and retry settings
        self.request_timeout = self.config.get('request_timeout', 30)
        self.max_retries = self.config.get('max_retries', 3)
    
    def _get_source_name(self) -> str:
        """Return the human-readable name of the data source"""
        return "Canada.ca News Releases"
    
    def _get_collection_name(self) -> str:
        """Return the Firestore collection name for raw data"""
        return "raw_news_releases"
    
    def _fetch_new_items(self, since_date: datetime = None) -> List[Dict[str, Any]]:
        """
        Fetch new news items from RSS feeds.
        
        Args:
            since_date: Only fetch items newer than this date
            
        Returns:
            List of raw news items
        """
        all_items = []
        
        for feed_name, feed_url_template in self.rss_feeds.items():
            try:
                # Format URL with start date if it contains placeholder
                if '{start_date}' in feed_url_template:
                    # Format date for Canada.ca API (YYYY-MM-DD format)
                    start_date_str = since_date.strftime('%Y-%m-%d') if since_date else '2021-11-21'
                    feed_url = feed_url_template.format(start_date=start_date_str)
                else:
                    feed_url = feed_url_template
                
                self.logger.info(f"Fetching RSS feed: {feed_name} ({feed_url})")
                items = self._fetch_rss_feed(feed_url, feed_name, since_date)
                all_items.extend(items)
                self.logger.info(f"Found {len(items)} items from {feed_name}")
                
            except requests.exceptions.HTTPError as e:
                if e.response and e.response.status_code == 404:
                    self.logger.warning(f"RSS feed not available (404): {feed_name} - {feed_url}")
                    # Continue with other feeds instead of failing completely
                    continue
                else:
                    self.logger.error(f"HTTP error fetching RSS feed {feed_name}: {e}")
                    # Continue with other feeds for non-404 HTTP errors too
                    continue
            except Exception as e:
                self.logger.error(f"Error fetching RSS feed {feed_name}: {e}", exc_info=True)
                # Continue with other feeds even if one fails
                continue
        
        self.logger.info(f"Total items fetched: {len(all_items)}")
        return all_items
    
    def _fetch_rss_feed(self, feed_url: str, feed_name: str, 
                       since_date: datetime = None) -> List[Dict[str, Any]]:
        """
        Fetch and parse a single RSS feed.
        
        Args:
            feed_url: URL of the RSS feed
            feed_name: Name identifier for the feed
            since_date: Only return items newer than this date
            
        Returns:
            List of parsed RSS items
        """
        items = []
        
        try:
            # Fetch RSS feed with timeout and retries
            response = self._make_request(feed_url)
            
            # Parse RSS feed
            feed = feedparser.parse(response.content)
            
            if feed.bozo:
                self.logger.warning(f"RSS feed {feed_name} has parsing issues: {feed.bozo_exception}")
            
            # Process each entry
            for entry in feed.entries:
                try:
                    # Parse publication date
                    pub_date = self._parse_publication_date(entry)
                    
                    # Skip if older than since_date
                    if since_date and pub_date and pub_date < since_date:
                        continue
                    
                    # Extract item data
                    item = {
                        'title': entry.get('title', '').strip(),
                        'description': entry.get('summary', '').strip(),
                        'source_url': entry.get('link', ''),
                        'publication_date': pub_date,
                        'feed_name': feed_name,
                        'feed_url': feed_url,
                        'guid': entry.get('id', entry.get('guid', '')),
                        'author': entry.get('author', ''),
                        'tags': [tag.get('term', '') for tag in entry.get('tags', [])],
                        'raw_entry': dict(entry)  # Store full entry for debugging
                    }
                    
                    # Extract full text content from the article URL
                    full_text = self._extract_full_text(item['source_url'])
                    if full_text:
                        item['full_text'] = full_text
                    
                    # Only include items with required fields
                    if item['title'] and item['source_url']:
                        # Add category filtering (critical missing feature from deprecated script)
                        categories_rss = item.get('tags', [])
                        if categories_rss:
                            parsed_categories_lower = [cat.lower() for cat in categories_rss]
                            target_categories = {"backgrounders", "statements", "speeches"}
                            if not any(cat_lower in target_categories for cat_lower in parsed_categories_lower):
                                self.logger.debug(f"Skipping item due to category filter. Categories: {categories_rss}. URL: {item['source_url']}")
                                continue
                        
                        items.append(item)
                    else:
                        self.logger.warning(f"Skipping item with missing title or URL: {entry.get('id', 'unknown')}")
                        
                except Exception as e:
                    self.logger.error(f"Error processing RSS entry: {e}", exc_info=True)
                    continue
            
        except Exception as e:
            self.logger.error(f"Error fetching RSS feed {feed_url}: {e}", exc_info=True)
            raise
        
        return items
    
    def _make_request(self, url: str) -> requests.Response:
        """
        Make HTTP request with retries and proper error handling.
        
        Args:
            url: URL to fetch
            
        Returns:
            Response object
        """
        headers = {
            'User-Agent': 'Promise Tracker Pipeline/2.0 (Government Data Ingestion)',
            'Accept': 'application/rss+xml, application/xml, text/xml'
        }
        
        for attempt in range(self.max_retries):
            try:
                response = requests.get(
                    url,
                    headers=headers,
                    timeout=self.request_timeout,
                    allow_redirects=True
                )
                response.raise_for_status()
                return response
                
            except requests.exceptions.HTTPError as e:
                # Handle 404 errors more gracefully - these are common for government feeds
                if e.response.status_code == 404:
                    self.logger.warning(f"RSS feed not found (404): {url}")
                    raise  # Still raise to handle at caller level
                elif attempt < self.max_retries - 1:
                    self.logger.warning(f"HTTP error (attempt {attempt + 1}/{self.max_retries}): {e}")
                    continue
                else:
                    self.logger.error(f"HTTP error after {self.max_retries} attempts: {e}")
                    raise
            except requests.exceptions.RequestException as e:
                if attempt < self.max_retries - 1:
                    self.logger.warning(f"Request failed (attempt {attempt + 1}/{self.max_retries}): {e}")
                    continue
                else:
                    self.logger.error(f"Request failed after {self.max_retries} attempts: {e}")
                    raise
    
    def _parse_publication_date(self, entry: Dict[str, Any]) -> Optional[datetime]:
        """
        Parse publication date from RSS entry.
        
        Args:
            entry: RSS entry dictionary
            
        Returns:
            Parsed datetime or None if parsing fails
        """
        # Try different date fields
        date_fields = ['published', 'updated', 'created']
        
        for field in date_fields:
            if field in entry:
                try:
                    # feedparser usually provides parsed dates
                    if f"{field}_parsed" in entry:
                        time_struct = entry[f"{field}_parsed"]
                        if time_struct:
                            return datetime(*time_struct[:6], tzinfo=timezone.utc)
                    
                    # Fallback to string parsing
                    date_str = entry[field]
                    if date_str:
                        # Try common date formats
                        formats = [
                            '%a, %d %b %Y %H:%M:%S %z',
                            '%Y-%m-%dT%H:%M:%S%z',
                            '%Y-%m-%d %H:%M:%S',
                            '%Y-%m-%d'
                        ]
                        
                        for fmt in formats:
                            try:
                                dt = datetime.strptime(date_str, fmt)
                                if dt.tzinfo is None:
                                    dt = dt.replace(tzinfo=timezone.utc)
                                return dt
                            except ValueError:
                                continue
                                
                except Exception as e:
                    self.logger.debug(f"Error parsing date field {field}: {e}")
                    continue
        
        self.logger.warning(f"Could not parse publication date for entry: {entry.get('id', 'unknown')}")
        return None
    
    def _extract_full_text(self, url: str) -> Optional[str]:
        """
        Extract full text content from a news article URL using BeautifulSoup.
        
        Args:
            url: URL of the news article
            
        Returns:
            Extracted full text content or None if extraction fails
        """
        if not url:
            return None
            
        try:
            self.logger.debug(f"Extracting full text from: {url}")
            
            # Make request with same headers and timeout as RSS requests
            response = self._make_request(url)
            soup = BeautifulSoup(response.content, 'html.parser')
            
            # Remove script and style elements
            for script in soup(["script", "style", "nav", "header", "footer"]):
                script.decompose()
            
            # Try Canada.ca specific selector first (from deprecated script)
            main_content = soup.find('main', attrs={'property': 'mainContentOfPage'})
            
            if main_content:
                # Canada.ca specific extraction
                text = main_content.get_text(separator='\n', strip=True)
                self.logger.debug(f"Successfully extracted main content using Canada.ca selector")
            else:
                # Fallback to generic content selectors
                content_selectors = [
                    'main',
                    '.content', 
                    '.article-content',
                    '.news-content',
                    '#content',
                    '.main-content'
                ]
                
                for selector in content_selectors:
                    main_content = soup.select_one(selector)
                    if main_content:
                        break
                
                # If no main content area found, use the whole body
                if not main_content:
                    main_content = soup.find('body') or soup
                
                # Extract text from paragraphs and other text elements
                text_elements = main_content.find_all(['p', 'div', 'span', 'h1', 'h2', 'h3', 'h4', 'h5', 'h6'])
                
                # Get text content and clean it up
                text_parts = []
                for element in text_elements:
                    element_text = element.get_text().strip()
                    if element_text and len(element_text) > 10:  # Filter out very short text snippets
                        text_parts.append(element_text)
                
                text = ' '.join(text_parts)
            
            # Clean up whitespace
            lines = (line.strip() for line in text.splitlines())
            chunks = (phrase.strip() for line in lines for phrase in line.split("  "))
            cleaned_text = ' '.join(chunk for chunk in chunks if chunk)
            
            if cleaned_text and len(cleaned_text) > 100:  # Ensure we got meaningful content
                self.logger.debug(f"Successfully extracted {len(cleaned_text)} characters of text")
                return cleaned_text
            else:
                self.logger.warning(f"Extracted text too short or empty for URL: {url}")
                return None
                
        except Exception as e:
            self.logger.warning(f"Failed to extract full text from {url}: {e}")
            return None
    
    def _process_raw_item(self, raw_item: Dict[str, Any]) -> Dict[str, Any]:
        """
        Process a single raw RSS item into standardized format.
        
        Args:
            raw_item: Raw RSS item
            
        Returns:
            Processed item ready for Firestore storage
        """
        # Determine department from feed name or URL
        department = self._extract_department(raw_item)
        
        # Determine parliament session ID based on publication date
        parliament_session_id = self._get_parliament_session_id(raw_item['publication_date'])
        
        # Generate the document ID
        doc_id = self._generate_item_id(raw_item)
        
        processed_item = {
            # Core fields (using production field names)
            'title_raw': raw_item['title'],
            'summary_or_snippet_raw': raw_item['description'],
            'source_url': raw_item['source_url'],
            'publication_date': raw_item['publication_date'],
            'full_text_scraped': raw_item.get('full_text', ''),  # Use production field name
            
            # Metadata (using production field names)
            'department_rss': department,
            'source_feed_name': raw_item['feed_name'],  # Use production field name
            'rss_feed_url_used': raw_item['feed_url'],  # Use production field name
            'source_feed': 'canada_news_api',  # Add missing field
            'parliament_session_id_assigned': parliament_session_id,
            
            # Processing status
            'evidence_processing_status': 'pending_evidence_creation',
            
            # Additional fields (using production field names)
            'raw_item_id': doc_id,  # Add missing field - document ID reference
            'categories_rss': raw_item.get('tags', []),  # Use production field name
            'content_type': raw_item['feed_name'],  # Add missing field - map from feed name
            
            # Timestamps
            'ingested_at': datetime.now(timezone.utc),
            'last_updated_at': datetime.now(timezone.utc)
        }
        
        return processed_item
    
    def _extract_department(self, item: Dict[str, Any]) -> str:
        """
        Extract department name from RSS item.
        
        Args:
            item: RSS item
            
        Returns:
            Department name or 'Unknown'
        """
        # Map feed names to departments
        department_mapping = {
            'national_news': 'Government of Canada',
            'pmo': 'Prime Minister\'s Office',
            'backgrounders': 'Government of Canada',
            'speeches': 'Government of Canada',
            'statements': 'Government of Canada'
        }
        
        feed_name = item.get('feed_name', '')
        department = department_mapping.get(feed_name)
        
        if department:
            return department
        
        # Try to extract from URL
        url = item.get('source_url', '')
        if 'pm.gc.ca' in url:
            return 'Prime Minister\'s Office'
        elif 'fin.gc.ca' in url or 'finance' in url:
            return 'Department of Finance Canada'
        elif 'hc-sc.gc.ca' in url or 'health' in url:
            return 'Health Canada'
        
        return 'Government of Canada'
    
    def _get_parliament_session_id(self, publication_date: datetime) -> Optional[str]:
        """
        Determine parliament session ID based on publication date.
        
        Args:
            publication_date: Publication date of the news item
            
        Returns:
            Parliament session ID (format: "44", "45", etc.)
        """
        if not publication_date:
            return None
        
        # Return only the parliament number, not the subsession
        if publication_date.year >= 2025:
            return "45"  # 45th Parliament
        elif publication_date.year >= 2021:
            return "44"  # 44th Parliament
        elif publication_date.year >= 2019:
            return "43"  # 43rd Parliament
        else:
            return "42"  # 42nd Parliament
    
    def _generate_item_id(self, item: Dict[str, Any]) -> str:
        """
        Generate a unique ID for the news item following the pattern: YYYYMMDD_CANADANEWS_{hash}
        
        Args:
            item: Processed news item
            
        Returns:
            Unique item ID following production naming convention
        """
        import hashlib
        
        # Get publication date for date prefix
        pub_date = item.get('publication_date')
        if pub_date:
            date_prefix = pub_date.strftime('%Y%m%d')
        else:
            date_prefix = datetime.now(timezone.utc).strftime('%Y%m%d')
        
        # Create hash from URL + title for uniqueness
        url = item.get('source_url', '')
        title = item.get('title', '')
        guid = item.get('guid', '')
        
        # Use GUID first if available, otherwise URL + title
        if guid:
            hash_source = guid
        else:
            hash_source = f"{url}_{title}"
        
        # Generate short hash (12 characters like in production)
        short_hash = hashlib.sha256(hash_source.encode()).hexdigest()[:12]
        
        # Return in format: YYYYMMDD_CANADANEWS_{hash}
        return f"{date_prefix}_CANADANEWS_{short_hash}"
    
    def _should_update_item(self, existing_item: Dict[str, Any], 
                           new_item: Dict[str, Any]) -> bool:
        """
        Determine if an existing news item should be updated.
        
        Args:
            existing_item: Current item in database
            new_item: New item from RSS feed
            
        Returns:
            True if item should be updated
        """
        # Check if title or description has changed
        if (existing_item.get('title') != new_item.get('title') or
            existing_item.get('description') != new_item.get('description')):
            return True
        
        # Check if processing status allows updates
        status = existing_item.get('evidence_processing_status', '')
        if status in ['pending_evidence_creation', 'error_processing_script']:
            return True
        
        return False 