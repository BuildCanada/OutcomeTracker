"""
Orders in Council Ingestion Job

Ingests Orders in Council from the Privy Council Office website into the raw_orders_in_council collection.
This replaces the existing ingest_oic.py script with a more robust,
class-based implementation.
"""

import logging
import sys
import requests
import re
import hashlib
from datetime import datetime, timezone, timedelta
from typing import Dict, Any, List, Optional
from bs4 import BeautifulSoup
from pathlib import Path

# Handle imports for both module execution and testing
try:
    from .base_ingestion import BaseIngestionJob
except ImportError:
    # Add pipeline directory to path for testing
    pipeline_dir = Path(__file__).parent.parent.parent
    sys.path.insert(0, str(pipeline_dir))
    from stages.ingestion.base_ingestion import BaseIngestionJob


class OrdersInCouncilIngestion(BaseIngestionJob):
    """
    Ingestion job for Orders in Council data.
    
    Scrapes OIC data from orders-in-council.canada.ca and stores in 
    raw_orders_in_council collection.
    """
    
    def __init__(self, job_name: str, config: Dict[str, Any] = None):
        """Initialize the Orders in Council ingestion job"""
        super().__init__(job_name, config)
        
        # Scraping configuration
        self.base_url = "https://orders-in-council.canada.ca/attachment.php"
        self.headers = {
            'User-Agent': 'Promise Tracker Pipeline/2.0 (Government Data Ingestion)'
        }
        
        # Processing settings
        self.max_consecutive_misses = self.config.get('max_consecutive_misses', 50)
        self.iteration_delay_seconds = self.config.get('iteration_delay_seconds', 2)
        self.max_items_per_run = self.config.get('max_items_per_run', 100)
        self.start_attach_id = self.config.get('start_attach_id', 47204)  # Default starting point
        
        # Request settings
        self.request_timeout = self.config.get('request_timeout', 30)
        self.max_retries = self.config.get('max_retries', 3)
        
        # Parliament sessions cache
        self._parliament_sessions_cache = None
    
    def _get_source_name(self) -> str:
        """Return the human-readable name of the data source"""
        return "Orders in Council"
    
    def _get_collection_name(self) -> str:
        """Return the Firestore collection name for raw data"""
        return "raw_orders_in_council"
    
    def _fetch_new_items(self, since_date: datetime = None) -> List[Dict[str, Any]]:
        """
        Fetch new OIC items by iteratively scraping attachment pages.
        
        Args:
            since_date: Only fetch items newer than this date
            
        Returns:
            List of raw OIC items
        """
        self.logger.info("Starting Orders in Council scraping")
        
        # Get starting attach_id from last successful run or config
        start_id = self._get_last_scraped_attach_id()
        
        items = []
        current_attach_id = start_id
        consecutive_misses = 0
        items_processed = 0
        
        while (consecutive_misses < self.max_consecutive_misses and 
               items_processed < self.max_items_per_run):
            
            try:
                self.logger.info(f"Scraping attach_id: {current_attach_id}")
                
                # Scrape OIC page
                oic_data = self._scrape_oic_page(current_attach_id)
                
                if oic_data:
                    # Check if item is newer than since_date
                    if since_date:
                        oic_date = oic_data.get('publication_date')
                        if oic_date and oic_date < since_date:
                            self.logger.debug(f"OIC {current_attach_id} is older than since_date, skipping")
                            current_attach_id += 1
                            continue
                    
                    items.append(oic_data)
                    consecutive_misses = 0  # Reset miss counter
                    self.logger.info(f"Successfully scraped OIC: {oic_data.get('oic_number', 'Unknown')}")
                    
                    # Update last scraped ID
                    self._update_last_scraped_attach_id(current_attach_id)
                    
                else:
                    consecutive_misses += 1
                    self.logger.debug(f"No OIC found for attach_id {current_attach_id} (miss {consecutive_misses}/{self.max_consecutive_misses})")
                
                items_processed += 1
                current_attach_id += 1
                
                # Add delay between requests
                if self.iteration_delay_seconds > 0:
                    import time
                    time.sleep(self.iteration_delay_seconds)
                
            except Exception as e:
                self.logger.error(f"Error scraping attach_id {current_attach_id}: {e}")
                consecutive_misses += 1
                current_attach_id += 1
                continue
        
        self.logger.info(f"Scraping completed. Found {len(items)} OICs, {consecutive_misses} consecutive misses")
        return items
    
    def _scrape_oic_page(self, attach_id: int) -> Optional[Dict[str, Any]]:
        """
        Scrape a single OIC page.
        
        Args:
            attach_id: Attachment ID to scrape
            
        Returns:
            OIC data dictionary or None if not found
        """
        url = f"{self.base_url}?attach_id={attach_id}"
        
        try:
            response = self._make_request(url)
            soup = BeautifulSoup(response.content, 'html.parser')
            
            # Check if page contains OIC data
            if not self._is_valid_oic_page(soup):
                return None
            
            # Extract OIC data
            oic_data = {
                'attach_id': attach_id,
                'source_url': url,
                'scraped_at': datetime.now(timezone.utc)
            }
            
            # Extract OIC number
            oic_number = self._extract_oic_number(soup)
            if oic_number:
                oic_data['oic_number'] = oic_number
                oic_data['oic_number_normalized'] = self._normalize_oic_number(oic_number)
            
            # Extract title
            title = self._extract_title(soup)
            if title:
                oic_data['title'] = title
            
            # Extract publication date
            pub_date = self._extract_publication_date(soup)
            if pub_date:
                oic_data['publication_date'] = pub_date
            
            # Extract full text content
            content = self._extract_content(soup)
            if content:
                oic_data['full_text'] = content
            
            # Extract additional metadata
            metadata = self._extract_metadata(soup)
            oic_data.update(metadata)
            
            return oic_data
            
        except Exception as e:
            self.logger.error(f"Error scraping OIC page {attach_id}: {e}")
            return None
    
    def _is_valid_oic_page(self, soup: BeautifulSoup) -> bool:
        """Check if the page contains valid OIC data"""
        # Look for key indicators that this is a valid OIC page
        oic_indicators = [
            soup.find(text=re.compile(r'P\.C\.\s*\d{4}-\d{3,4}', re.IGNORECASE)),
            soup.find('title', text=re.compile(r'Order in Council', re.IGNORECASE)),
            soup.find(text=re.compile(r'His Excellency.*Governor General', re.IGNORECASE))
        ]
        
        return any(indicator for indicator in oic_indicators)
    
    def _extract_oic_number(self, soup: BeautifulSoup) -> Optional[str]:
        """Extract OIC number from the page"""
        # Look for P.C. YYYY-NNNN pattern
        oic_pattern = re.compile(r'P\.C\.\s*(\d{4}-\d{3,4})', re.IGNORECASE)
        
        # Search in various elements
        for element in soup.find_all(['h1', 'h2', 'h3', 'p', 'div']):
            text = element.get_text()
            match = oic_pattern.search(text)
            if match:
                return f"P.C. {match.group(1)}"
        
        return None
    
    def _extract_title(self, soup: BeautifulSoup) -> Optional[str]:
        """Extract title from the page"""
        # Try different selectors for title
        title_selectors = [
            'h1',
            'h2',
            '.title',
            '[class*="title"]'
        ]
        
        for selector in title_selectors:
            element = soup.select_one(selector)
            if element:
                title = element.get_text().strip()
                if title and len(title) > 10:  # Basic validation
                    return title
        
        # Fallback to page title
        title_element = soup.find('title')
        if title_element:
            return title_element.get_text().strip()
        
        return None
    
    def _extract_publication_date(self, soup: BeautifulSoup) -> Optional[datetime]:
        """Extract publication date from the page"""
        # Look for date patterns
        date_pattern = re.compile(r'\b(\d{4}-\d{2}-\d{2})\b')
        
        # Search in various elements
        for element in soup.find_all(['p', 'div', 'span']):
            text = element.get_text()
            match = date_pattern.search(text)
            if match:
                try:
                    date_str = match.group(1)
                    return datetime.strptime(date_str, "%Y-%m-%d").replace(tzinfo=timezone.utc)
                except ValueError:
                    continue
        
        return None
    
    def _extract_content(self, soup: BeautifulSoup) -> Optional[str]:
        """Extract full text content from the page"""
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
    
    def _extract_metadata(self, soup: BeautifulSoup) -> Dict[str, Any]:
        """Extract additional metadata from the page"""
        metadata = {}
        
        # Extract any additional structured data
        # This can be expanded based on the actual page structure
        
        return metadata
    
    def _normalize_oic_number(self, raw_oic_number: str) -> Optional[str]:
        """Normalize OIC number format"""
        if not raw_oic_number:
            return None
        
        # Remove "P.C. " prefix and strip whitespace
        normalized = re.sub(r"P\.C\.\s*", "", raw_oic_number, flags=re.IGNORECASE).strip()
        
        # Basic validation for YYYY-NNNN or YYYY-NNN format
        if re.match(r"^\d{4}-\d{3,4}$", normalized):
            return normalized
        
        self.logger.warning(f"Could not normalize OIC number: '{raw_oic_number}'")
        return raw_oic_number.strip()
    
    def _get_last_scraped_attach_id(self) -> int:
        """Get the last successfully scraped attach_id from Firestore"""
        try:
            config_doc = self.db.collection('script_config').document('ingest_raw_oic_config').get()
            if config_doc.exists:
                return config_doc.to_dict().get('last_successfully_scraped_attach_id', self.start_attach_id)
            else:
                self.logger.info(f"No previous scraping state found, starting from {self.start_attach_id}")
                return self.start_attach_id
        except Exception as e:
            self.logger.error(f"Error getting last scraped attach_id: {e}")
            return self.start_attach_id
    
    def _update_last_scraped_attach_id(self, attach_id: int):
        """Update the last successfully scraped attach_id in Firestore"""
        try:
            self.db.collection('script_config').document('ingest_raw_oic_config').set({
                'last_successfully_scraped_attach_id': attach_id,
                'updated_at': datetime.now(timezone.utc)
            }, merge=True)
        except Exception as e:
            self.logger.warning(f"Failed to update last scraped attach_id: {e}")
    
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
        Process a single raw OIC item into standardized format.
        
        Args:
            raw_item: Raw OIC item from scraping
            
        Returns:
            Processed item ready for Firestore storage
        """
        # Determine parliament session ID
        parliament_session_id = None
        if raw_item.get('publication_date'):
            parliament_session_id = self._get_parliament_session_id(raw_item['publication_date'])
        
        processed_item = {
            # Core fields
            'attach_id': raw_item['attach_id'],
            'oic_number': raw_item.get('oic_number', ''),
            'oic_number_normalized': raw_item.get('oic_number_normalized', ''),
            'title': raw_item.get('title', ''),
            'full_text': raw_item.get('full_text', ''),
            'source_url': raw_item['source_url'],
            'publication_date': raw_item.get('publication_date'),
            
            # Metadata
            'parliament_session_id_assigned': parliament_session_id,
            'scraped_at': raw_item['scraped_at'],
            
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
            publication_date: Publication date of the OIC
            
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
        Generate a unique ID for the OIC item.
        
        Args:
            item: Processed OIC item
            
        Returns:
            Unique item ID
        """
        # Use attach_id as the primary identifier
        attach_id = item.get('attach_id')
        if attach_id:
            return str(attach_id)
        
        # Fallback to hash of OIC number + title
        oic_number = item.get('oic_number_normalized', item.get('oic_number', ''))
        title = item.get('title', '')
        id_source = f"{oic_number}_{title}"
        return hashlib.sha256(id_source.encode()).hexdigest()[:16]
    
    def _should_update_item(self, existing_item: Dict[str, Any], 
                           new_item: Dict[str, Any]) -> bool:
        """
        Determine if an existing OIC item should be updated.
        
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
        content_fields = ['title', 'full_text', 'oic_number']
        for field in content_fields:
            if existing_item.get(field) != new_item.get(field):
                return True
        
        return False 