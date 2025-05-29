"""
Canada Gazette Ingestion Job

Ingests regulatory notices from the Canada Gazette Part II RSS feed into the raw_canada_gazette collection.
This replaces the existing ingest_canada_gazette_p2.py script with a more robust,
class-based implementation.
"""

import logging
import sys
import feedparser
import requests
import re
import hashlib
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional
from bs4 import BeautifulSoup
from dateutil import parser as dateutil_parser
from pathlib import Path

# Handle imports for both module execution and testing
try:
    from .base_ingestion import BaseIngestionJob
except ImportError:
    # Add pipeline directory to path for testing
    pipeline_dir = Path(__file__).parent.parent.parent
    sys.path.insert(0, str(pipeline_dir))
    from stages.ingestion.base_ingestion import BaseIngestionJob


class CanadaGazetteIngestion(BaseIngestionJob):
    """
    Ingestion job for Canada Gazette Part II data.
    
    Fetches Gazette issues from RSS feed, scrapes table of contents to find
    individual regulations, and stores in raw_gazette_p2_notices collection.
    """
    
    def __init__(self, job_name: str, config: Dict[str, Any] = None):
        """Initialize the Canada Gazette ingestion job"""
        super().__init__(job_name, config)
        
        # RSS and scraping configuration
        self.rss_url = "https://gazette.gc.ca/rss/p2-eng.xml"
        self.headers = {
            'User-Agent': 'Promise Tracker Pipeline/2.0 (Government Data Ingestion)'
        }
        
        # Processing settings
        self.max_issues_per_run = self.config.get('max_issues_per_run', 10)
        self.scrape_full_text = self.config.get('scrape_full_text', True)
        
        # Request settings
        self.request_timeout = self.config.get('request_timeout', 30)
        self.max_retries = self.config.get('max_retries', 3)
        
        # Parliament sessions cache
        self._parliament_sessions_cache = None
    
    def _get_source_name(self) -> str:
        """Return the human-readable name of the data source"""
        return "Canada Gazette Part II"
    
    def _get_collection_name(self) -> str:
        """Return the Firestore collection name for raw data"""
        return "raw_gazette_p2_notices"
    
    def _fetch_new_items(self, since_date: datetime = None) -> List[Dict[str, Any]]:
        """
        Fetch new Gazette notices from RSS feed and issue pages.
        
        Args:
            since_date: Only fetch items newer than this date
            
        Returns:
            List of raw Gazette notice items
        """
        self.logger.info("Fetching Canada Gazette Part II RSS feed")
        
        # Fetch RSS feed
        rss_entries = self._fetch_rss_feed()
        if not rss_entries:
            self.logger.error("Failed to fetch RSS feed")
            return []
        
        # Filter entries by date if specified
        if since_date:
            rss_entries = self._filter_entries_by_date(rss_entries, since_date)
        
        # Limit number of issues to process
        if self.max_issues_per_run:
            rss_entries = rss_entries[:self.max_issues_per_run]
        
        self.logger.info(f"Processing {len(rss_entries)} Gazette issues")
        
        # Process each issue to extract regulations
        all_regulations = []
        for i, entry in enumerate(rss_entries):
            try:
                self.logger.info(f"Processing issue {i+1}/{len(rss_entries)}: {entry.get('title', 'Unknown')}")
                
                # Extract issue metadata
                issue_data = self._extract_issue_metadata(entry)
                
                # Scrape issue page for regulations
                regulations = self._scrape_issue_page(entry['link'], issue_data)
                
                all_regulations.extend(regulations)
                self.logger.info(f"Found {len(regulations)} regulations in issue")
                
            except Exception as e:
                self.logger.error(f"Error processing Gazette issue: {e}")
                continue
        
        self.logger.info(f"Total regulations found: {len(all_regulations)}")
        return all_regulations
    
    def _fetch_rss_feed(self) -> List[Dict[str, Any]]:
        """Fetch and parse the Gazette RSS feed"""
        try:
            response = self._make_request(self.rss_url)
            feed = feedparser.parse(response.content)
            
            if feed.bozo:
                self.logger.warning(f"RSS feed has parsing issues: {feed.bozo_exception}")
            
            entries = []
            for entry in feed.entries:
                try:
                    # Parse publication date
                    pub_date = self._parse_rss_publication_date(entry)
                    
                    entry_data = {
                        'title': entry.get('title', '').strip(),
                        'link': entry.get('link', ''),
                        'description': entry.get('summary', '').strip(),
                        'publication_date': pub_date,
                        'guid': entry.get('id', entry.get('guid', '')),
                        'raw_entry': dict(entry)
                    }
                    
                    if entry_data['title'] and entry_data['link']:
                        entries.append(entry_data)
                    
                except Exception as e:
                    self.logger.error(f"Error processing RSS entry: {e}")
                    continue
            
            return entries
            
        except Exception as e:
            self.logger.error(f"Error fetching RSS feed: {e}")
            return []
    
    def _parse_rss_publication_date(self, entry: Dict[str, Any]) -> Optional[datetime]:
        """Parse publication date from RSS entry"""
        # Try published_parsed first (struct_time)
        if hasattr(entry, 'published_parsed') and entry.published_parsed:
            try:
                return datetime(*entry.published_parsed[:6], tzinfo=timezone.utc)
            except Exception as e:
                self.logger.debug(f"Could not parse published_parsed: {e}")
        
        # Try published string
        if hasattr(entry, 'published') and entry.published:
            try:
                dt = dateutil_parser.parse(entry.published)
                if dt.tzinfo is None:
                    dt = dt.replace(tzinfo=timezone.utc)
                return dt
            except Exception as e:
                self.logger.debug(f"Could not parse published string: {e}")
        
        return None
    
    def _filter_entries_by_date(self, entries: List[Dict[str, Any]], 
                               since_date: datetime) -> List[Dict[str, Any]]:
        """Filter RSS entries by publication date"""
        filtered_entries = []
        
        for entry in entries:
            pub_date = entry.get('publication_date')
            if pub_date and pub_date >= since_date:
                filtered_entries.append(entry)
            elif not pub_date:
                # Include entries without dates to be safe
                filtered_entries.append(entry)
        
        self.logger.info(f"Filtered to {len(filtered_entries)} issues since {since_date}")
        return filtered_entries
    
    def _extract_issue_metadata(self, entry: Dict[str, Any]) -> Dict[str, Any]:
        """Extract metadata from RSS entry for the issue"""
        return {
            'issue_title': entry.get('title', ''),
            'issue_url': entry.get('link', ''),
            'issue_description': entry.get('description', ''),
            'issue_publication_date': entry.get('publication_date'),
            'issue_guid': entry.get('guid', '')
        }
    
    def _scrape_issue_page(self, issue_url: str, issue_data: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Scrape a Gazette issue page to extract individual regulations.
        
        Args:
            issue_url: URL of the issue page
            issue_data: Metadata about the issue
            
        Returns:
            List of regulation data dictionaries
        """
        regulations = []
        
        try:
            response = self._make_request(issue_url)
            soup = BeautifulSoup(response.content, 'html.parser')
            
            # Find regulation entries in the table of contents
            regulation_links = self._extract_regulation_links(soup)
            
            for reg_link in regulation_links:
                try:
                    # Extract basic regulation metadata
                    reg_data = self._extract_regulation_metadata(reg_link, soup)
                    
                    # Add issue metadata
                    reg_data.update(issue_data)
                    
                    # Scrape full text if enabled
                    if self.scrape_full_text and reg_data.get('regulation_url'):
                        full_text = self._scrape_regulation_full_text(reg_data['regulation_url'])
                        if full_text:
                            reg_data['full_text'] = full_text
                    
                    # Add scraping metadata
                    reg_data['scraped_at'] = datetime.now(timezone.utc)
                    
                    regulations.append(reg_data)
                    
                except Exception as e:
                    self.logger.error(f"Error processing regulation link: {e}")
                    continue
            
        except Exception as e:
            self.logger.error(f"Error scraping issue page {issue_url}: {e}")
        
        return regulations
    
    def _extract_regulation_links(self, soup: BeautifulSoup) -> List[Dict[str, Any]]:
        """Extract regulation links from the issue page"""
        regulation_links = []
        
        # Look for regulation links in various patterns
        # This may need adjustment based on actual Gazette page structure
        
        # Pattern 1: Links in table of contents
        for link in soup.find_all('a', href=True):
            href = link.get('href', '')
            text = link.get_text().strip()
            
            # Check if this looks like a regulation link
            if self._is_regulation_link(href, text):
                regulation_links.append({
                    'url': href,
                    'text': text,
                    'element': link
                })
        
        return regulation_links
    
    def _is_regulation_link(self, href: str, text: str) -> bool:
        """Determine if a link points to a regulation"""
        # Look for patterns that indicate regulation links
        regulation_patterns = [
            r'SOR/',  # Statutory Orders and Regulations
            r'SI/',   # Statutory Instruments
            r'regulation',
            r'order.*council',
            r'statutory'
        ]
        
        combined_text = f"{href} {text}".lower()
        
        for pattern in regulation_patterns:
            if re.search(pattern, combined_text, re.IGNORECASE):
                return True
        
        return False
    
    def _extract_regulation_metadata(self, reg_link: Dict[str, Any], 
                                   soup: BeautifulSoup) -> Dict[str, Any]:
        """Extract metadata for a regulation from the link and surrounding context"""
        link_element = reg_link['element']
        
        # Extract basic information
        reg_data = {
            'regulation_title': reg_link['text'],
            'regulation_url': reg_link['url'],
        }
        
        # Try to extract regulation number/identifier
        reg_number = self._extract_regulation_number(reg_link['text'])
        if reg_number:
            reg_data['regulation_number'] = reg_number
        
        # Look for additional metadata in surrounding elements
        parent = link_element.parent
        if parent:
            # Try to find date information
            date_text = parent.get_text()
            reg_date = self._extract_date_from_text(date_text)
            if reg_date:
                reg_data['regulation_date'] = reg_date
        
        return reg_data
    
    def _extract_regulation_number(self, text: str) -> Optional[str]:
        """Extract regulation number from text"""
        # Look for common regulation number patterns
        patterns = [
            r'SOR/\d{4}-\d+',
            r'SI/\d{4}-\d+',
            r'P\.C\.\s*\d{4}-\d+',
            r'\d{4}-\d+'
        ]
        
        for pattern in patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                return match.group(0)
        
        return None
    
    def _extract_date_from_text(self, text: str) -> Optional[datetime]:
        """Extract date from text using various patterns"""
        # Look for date patterns
        date_patterns = [
            r'\b(\d{4}-\d{2}-\d{2})\b',
            r'\b(\d{1,2}/\d{1,2}/\d{4})\b',
            r'\b(\w+ \d{1,2}, \d{4})\b'
        ]
        
        for pattern in date_patterns:
            match = re.search(pattern, text)
            if match:
                try:
                    date_str = match.group(1)
                    dt = dateutil_parser.parse(date_str)
                    if dt.tzinfo is None:
                        dt = dt.replace(tzinfo=timezone.utc)
                    return dt
                except Exception:
                    continue
        
        return None
    
    def _scrape_regulation_full_text(self, regulation_url: str) -> Optional[str]:
        """Scrape the full text of a regulation"""
        try:
            # Make URL absolute if needed
            if regulation_url.startswith('/'):
                regulation_url = f"https://gazette.gc.ca{regulation_url}"
            
            response = self._make_request(regulation_url)
            soup = BeautifulSoup(response.content, 'html.parser')
            
            # Remove script and style elements
            for script in soup(["script", "style"]):
                script.decompose()
            
            # Get text content
            text = soup.get_text()
            
            # Clean up whitespace
            lines = (line.strip() for line in text.splitlines())
            chunks = (phrase.strip() for line in lines for phrase in line.split("  "))
            text = ' '.join(chunk for chunk in chunks if chunk)
            
            return text if text else None
            
        except Exception as e:
            self.logger.error(f"Error scraping regulation full text from {regulation_url}: {e}")
            return None
    
    def _make_request(self, url: str) -> requests.Response:
        """
        Make HTTP request with retries and proper error handling.
        
        Args:
            url: URL to fetch
            
        Returns:
            Response object
        """
        for attempt in range(self.max_retries):
            try:
                response = requests.get(
                    url,
                    headers=self.headers,
                    timeout=self.request_timeout,
                    allow_redirects=True
                )
                response.raise_for_status()
                return response
                
            except requests.exceptions.RequestException as e:
                if attempt < self.max_retries - 1:
                    self.logger.warning(f"Request failed (attempt {attempt + 1}/{self.max_retries}): {e}")
                    continue
                else:
                    self.logger.error(f"Request failed after {self.max_retries} attempts: {e}")
                    raise
    
    def _process_raw_item(self, raw_item: Dict[str, Any]) -> Dict[str, Any]:
        """
        Process a single raw Gazette notice item into standardized format.
        
        Args:
            raw_item: Raw regulation item from scraping
            
        Returns:
            Processed item ready for Firestore storage
        """
        # Determine parliament session ID
        parliament_session_id = None
        reg_date = raw_item.get('regulation_date') or raw_item.get('issue_publication_date')
        if reg_date:
            parliament_session_id = self._get_parliament_session_id(reg_date)
        
        processed_item = {
            # Core fields
            'regulation_title': raw_item.get('regulation_title', ''),
            'regulation_number': raw_item.get('regulation_number', ''),
            'regulation_url': raw_item.get('regulation_url', ''),
            'regulation_date': raw_item.get('regulation_date'),
            'full_text': raw_item.get('full_text', ''),
            
            # Issue metadata
            'issue_title': raw_item.get('issue_title', ''),
            'issue_url': raw_item.get('issue_url', ''),
            'issue_publication_date': raw_item.get('issue_publication_date'),
            'issue_guid': raw_item.get('issue_guid', ''),
            
            # Metadata
            'parliament_session_id_assigned': parliament_session_id,
            'scraped_at': raw_item.get('scraped_at'),
            
            # Processing status
            'evidence_processing_status': 'pending_evidence_creation',
            
            # Timestamps
            'last_updated_at': datetime.now(timezone.utc)
        }
        
        return processed_item
    
    def _get_parliament_session_id(self, publication_date: datetime) -> Optional[str]:
        """
        Determine parliament session ID based on publication date.
        
        Args:
            publication_date: Publication date of the regulation
            
        Returns:
            Parliament session ID or None
        """
        if not publication_date:
            return None
        
        # Load parliament sessions cache if not already loaded
        if self._parliament_sessions_cache is None:
            self._load_parliament_sessions_cache()
        
        if not self._parliament_sessions_cache:
            return None
        
        # Ensure publication_date is timezone-aware
        if publication_date.tzinfo is None:
            publication_date = publication_date.replace(tzinfo=timezone.utc)
        else:
            publication_date = publication_date.astimezone(timezone.utc)
        
        # Find matching session
        for session in self._parliament_sessions_cache:
            election_called = session.get('election_called_date')
            session_end = session.get('session_end_date')
            
            if election_called and election_called <= publication_date:
                if session_end is None or publication_date < session_end:
                    return session['id']
        
        return None
    
    def _load_parliament_sessions_cache(self):
        """Load parliament sessions from Firestore"""
        try:
            self._parliament_sessions_cache = []
            sessions_ref = self.db.collection('parliament_session').stream()
            
            for session_doc in sessions_ref:
                session_data = session_doc.to_dict()
                session_data['id'] = session_doc.id
                
                # Ensure dates are timezone-aware
                for date_field in ['election_called_date', 'session_end_date']:
                    if date_field in session_data and session_data[date_field]:
                        date_val = session_data[date_field]
                        if isinstance(date_val, datetime):
                            if date_val.tzinfo is None:
                                session_data[date_field] = date_val.replace(tzinfo=timezone.utc)
                            else:
                                session_data[date_field] = date_val.astimezone(timezone.utc)
                
                self._parliament_sessions_cache.append(session_data)
            
            # Sort by election date (newest first)
            self._parliament_sessions_cache.sort(
                key=lambda s: s.get('election_called_date', datetime.min.replace(tzinfo=timezone.utc)), 
                reverse=True
            )
            
            self.logger.info(f"Loaded {len(self._parliament_sessions_cache)} parliament sessions")
            
        except Exception as e:
            self.logger.error(f"Error loading parliament sessions: {e}")
            self._parliament_sessions_cache = []
    
    def _generate_item_id(self, item: Dict[str, Any]) -> str:
        """
        Generate a unique ID for the Gazette notice item.
        
        Args:
            item: Processed Gazette notice item
            
        Returns:
            Unique item ID
        """
        # Use regulation number if available
        reg_number = item.get('regulation_number')
        if reg_number:
            return reg_number.replace('/', '_').replace(' ', '_')
        
        # Fallback to hash of URL + title
        url = item.get('regulation_url', '')
        title = item.get('regulation_title', '')
        id_source = f"{url}_{title}"
        return hashlib.sha256(id_source.encode()).hexdigest()[:16]
    
    def _should_update_item(self, existing_item: Dict[str, Any], 
                           new_item: Dict[str, Any]) -> bool:
        """
        Determine if an existing Gazette notice item should be updated.
        
        Args:
            existing_item: Current item in database
            new_item: New item from scraping
            
        Returns:
            True if item should be updated
        """
        # Always update if processing status allows it
        status = existing_item.get('evidence_processing_status', '')
        if status in ['pending_evidence_creation', 'error_processing_script']:
            return True
        
        # Check if content has changed
        content_fields = ['regulation_title', 'full_text', 'regulation_number']
        for field in content_fields:
            if existing_item.get(field) != new_item.get(field):
                return True
        
        return False 