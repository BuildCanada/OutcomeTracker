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
        # Set config first so we can access override before super().__init__()
        self.config = config or {}
        
        # Allow test collection override
        self._collection_name_override = self.config.get('collection_name')
        
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
        self.start_attach_id = self.config.get('start_attach_id', 47280)  # Updated to recent attach_id
        
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
        return self._collection_name_override or "raw_orders_in_council"
    
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
                    self.logger.info(f"No valid OIC found for attach_id {current_attach_id} (miss {consecutive_misses}/{self.max_consecutive_misses})")
                
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
        url = f"{self.base_url}?attach={attach_id}&lang=en"
        
        try:
            response = self._make_request(url)
            soup = BeautifulSoup(response.content, 'html.parser')
            
            # Check if page contains OIC data
            if not self._is_valid_oic_page(soup):
                return None  # Return None for invalid pages (will be treated as a miss)
            
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
        # Use the same validation as the working deprecated script
        main_content = soup.find('main', id='wb-cont')
        if not main_content:
            return False
        
        # Check that main content has meaningful text (not just whitespace)
        main_text = main_content.get_text(strip=True)
        if not main_text or len(main_text) < 20:  # Require at least 20 chars of content (reduced from 50)
            return False
        
        return True
    
    def _extract_oic_number(self, soup: BeautifulSoup) -> Optional[str]:
        """Extract OIC number from the page using the logic from the working deprecated script"""
        # Find main content first
        main_content = soup.find('main', id='wb-cont')
        if not main_content:
            return None
        
        pc_number_raw = None
        
        # Method 1: Try finding <strong> tags first (from deprecated script)
        pc_strong_tag = main_content.find('strong', string=re.compile(r"^\s*PC Number:\s*$", re.IGNORECASE))
        if pc_strong_tag:
            if pc_strong_tag.next_sibling and isinstance(pc_strong_tag.next_sibling, str) and pc_strong_tag.next_sibling.strip():
                pc_number_raw = pc_strong_tag.next_sibling.strip()
            elif pc_strong_tag.parent:
                parent_text = pc_strong_tag.parent.get_text(separator=' ', strip=True)
                match = re.search(r"PC Number:\s*([\w-]+)", parent_text, re.IGNORECASE)
                if match: 
                    pc_number_raw = match.group(1)
        
        # Method 2: Fallback using the <p> tag sequence if strong tags didn't work well
        if not pc_number_raw:
            all_p_tags_in_main = main_content.find_all('p', recursive=False)
            if len(all_p_tags_in_main) > 0:
                p_pc_text = all_p_tags_in_main[0].get_text(strip=True)
                match = re.search(r"PC Number:\s*([\w-]+)", p_pc_text, re.IGNORECASE)
                if match: 
                    pc_number_raw = match.group(1)
        
        # Method 3: Look for P.C. YYYY-NNNN pattern anywhere in main content
        if not pc_number_raw:
            oic_pattern = re.compile(r'P\.C\.\s*(\d{4}-\d{3,4})', re.IGNORECASE)
            match = oic_pattern.search(main_content.get_text())
            if match:
                pc_number_raw = match.group(1)
        
        # Format as P.C. if we found a number
        if pc_number_raw:
            # Add P.C. prefix if not already present
            if not pc_number_raw.lower().startswith('p.c.'):
                return f"P.C. {pc_number_raw}"
            else:
                return pc_number_raw
        
        return None
    
    def _extract_title(self, soup: BeautifulSoup) -> Optional[str]:
        """Extract title from the page"""
        # This method extracts page title, but we want the first line of content
        # The actual title will be extracted from full_text in _process_raw_item
        return None
    
    def _extract_publication_date(self, soup: BeautifulSoup) -> Optional[datetime]:
        """Extract publication date from the page using the logic from the working deprecated script"""
        # Find main content first
        main_content = soup.find('main', id='wb-cont')
        if not main_content:
            return None
        
        oic_date_str = None
        
        # Method 1: Try finding <strong> tags first (from deprecated script)
        date_strong_tag = main_content.find('strong', string=re.compile(r"^\s*Date:\s*$", re.IGNORECASE))
        if date_strong_tag:
            if date_strong_tag.next_sibling and isinstance(date_strong_tag.next_sibling, str) and date_strong_tag.next_sibling.strip():
                date_str_candidate = date_strong_tag.next_sibling.strip()
                match = re.match(r"(\d{4}-\d{2}-\d{2})", date_str_candidate)
                if match: 
                    oic_date_str = match.group(1)
            elif date_strong_tag.parent:
                parent_text = date_strong_tag.parent.get_text(separator=' ', strip=True)
                match = re.search(r"Date:\s*(\d{4}-\d{2}-\d{2})", parent_text, re.IGNORECASE)
                if match: 
                    oic_date_str = match.group(1)

        # Method 2: Fallback using the <p> tag sequence if strong tags didn't work well
        if not oic_date_str:
            all_p_tags_in_main = main_content.find_all('p', recursive=False)
            if len(all_p_tags_in_main) > 1:
                p_date_text = all_p_tags_in_main[1].get_text(strip=True)
                match = re.search(r"Date:\s*(\d{4}-\d{2}-\d{2})", p_date_text, re.IGNORECASE)
                if match: 
                    oic_date_str = match.group(1)
        
        # Method 3: Look for date patterns anywhere in main content
        if not oic_date_str:
            date_pattern = re.compile(r'\b(\d{4}-\d{2}-\d{2})\b')
            match = date_pattern.search(main_content.get_text())
            if match:
                oic_date_str = match.group(1)
        
        # Parse the date string
        if oic_date_str:
            try:
                dt_naive = datetime.strptime(oic_date_str, "%Y-%m-%d")
                return dt_naive.replace(tzinfo=timezone.utc)
            except ValueError as e:
                self.logger.warning(f"Could not parse OIC date string '{oic_date_str}': {e}")
                return None
        
        return None
    
    def _extract_content(self, soup: BeautifulSoup) -> Optional[str]:
        """Extract full text content from the page using the logic from the working deprecated script"""
        # Find main content first
        main_content = soup.find('main', id='wb-cont')
        if not main_content:
            return None
        
        full_text_content = None
        
        # Remove "Back to Form" button from main_content before processing
        overall_form = main_content.find('form', action='index.php')
        if overall_form:
            overall_form.decompose()

        # Look for HR tag to find content section (from deprecated script)
        hr_tag = main_content.find('hr')
        if hr_tag:
            content_node = hr_tag.find_next_sibling()
            if content_node:
                target_text_element = None
                if content_node.name == 'p':
                    section_div = content_node.find('div', class_=re.compile(r"Section\d*$", re.IGNORECASE))
                    if not section_div:
                        section_div = content_node.find('div', style=re.compile(r"line-height", re.IGNORECASE))
                    target_text_element = section_div if section_div else content_node
                elif content_node.name == 'div' and \
                     (re.search(r"Section\d*$", " ".join(content_node.get('class', [])), re.IGNORECASE) or \
                      re.search(r"line-height", content_node.get('style',''), re.IGNORECASE)):
                    target_text_element = content_node
                else:
                    target_text_element = content_node
                
                if target_text_element:
                    for s in target_text_element.select('script, style, noscript, header, footer, nav, form'): 
                        s.decompose()
                    full_text_content = target_text_element.get_text(separator='\n', strip=True)
            else:
                self.logger.warning(f"Could not find content node (sibling) after <hr>")
        else:
            # Fallback: Try to find content in <p> tags after the ones for PC#/Date (from deprecated script)
            all_p_tags = main_content.find_all('p', recursive=False)
            
            potential_content_p = None
            start_index_for_content = 2  # Skip PC number and date paragraphs
            
            if len(all_p_tags) > start_index_for_content:
                potential_content_p = all_p_tags[start_index_for_content]
            
            if potential_content_p:
                section_div = potential_content_p.find('div', class_=re.compile(r"Section\d*$", re.IGNORECASE))
                if not section_div: 
                    section_div = potential_content_p.find('div', style=re.compile(r"line-height", re.IGNORECASE))
                
                target_text_element = section_div if section_div else potential_content_p
                for s in target_text_element.select('script, style, noscript, header, footer, nav, form'): 
                    s.decompose()
                full_text_content = target_text_element.get_text(separator='\n', strip=True)
                self.logger.debug("Used fallback for full text (no HR)")
        
        return full_text_content if full_text_content else None
    
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
            # Use different config document for test collections
            config_doc_name = 'ingest_raw_oic_config'
            collection_name = self._get_collection_name()
            if 'test_' in collection_name:
                config_doc_name = f'test_{config_doc_name}'
                
            config_doc = self.db.collection('script_config').document(config_doc_name).get()
            if config_doc.exists:
                config_data = config_doc.to_dict()
                last_attach_id = config_data.get('last_successfully_scraped_attach_id', self.start_attach_id)
                self.logger.info(f"Retrieved last scraped attach_id: {last_attach_id}")
                return last_attach_id
            else:
                self.logger.info(f"No previous scraping state found, starting from {self.start_attach_id}")
                # Initialize the config document with current starting point
                self.db.collection('script_config').document(config_doc_name).set({
                    'last_successfully_scraped_attach_id': self.start_attach_id,
                    'initialized_at': datetime.now(timezone.utc),
                    'updated_at': datetime.now(timezone.utc)
                })
                return self.start_attach_id
        except Exception as e:
            self.logger.error(f"Error getting last scraped attach_id: {e}")
            return self.start_attach_id
    
    def _update_last_scraped_attach_id(self, attach_id: int):
        """Update the last successfully scraped attach_id in Firestore"""
        try:
            # Use different config document for test collections
            config_doc_name = 'ingest_raw_oic_config'
            collection_name = self._get_collection_name()
            if 'test_' in collection_name:
                config_doc_name = f'test_{config_doc_name}'
                
            self.db.collection('script_config').document(config_doc_name).set({
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
        Process a single raw OIC item into standardized format that matches
        the existing raw_orders_in_council collection structure.
        
        Args:
            raw_item: Raw OIC item from scraping
            
        Returns:
            Processed item ready for Firestore storage
        """
        # Extract key information
        attach_id = raw_item['attach_id']
        oic_number = raw_item.get('oic_number', '')
        oic_number_normalized = raw_item.get('oic_number_normalized', '')
        full_text = raw_item.get('full_text', '')
        title = raw_item.get('title', '')
        source_url = raw_item['source_url']
        publication_date = raw_item.get('publication_date')
        scraped_at = raw_item['scraped_at']
        
        # Determine parliament session ID
        parliament_session_id = None
        if publication_date:
            parliament_session_id = self._get_parliament_session_id(publication_date)
        
        # Extract OIC number without P.C. prefix for raw_oic_id
        raw_oic_id = oic_number_normalized or oic_number.replace('P.C. ', '') if oic_number else str(attach_id)
        
        # Extract title from first non-empty line of full text (matching deprecated script)
        title_or_summary_raw = None
        if full_text:
            for line in full_text.split('\n'):
                stripped_line = line.strip()
                if stripped_line:  # Take the first non-empty line
                    title_or_summary_raw = stripped_line
                    break
        
        # Create processed item matching the existing structure
        processed_item = {
            # Core identification (matching sample structure)
            'attach_id': attach_id,
            'oic_number_full_raw': oic_number or '',
            'raw_oic_id': raw_oic_id,
            'title_or_summary_raw': title_or_summary_raw or '',
            
            # Content
            'full_text_scraped': full_text or '',
            
            # URLs
            'source_url_oic_detail_page': source_url,
            
            # Dates (using 'oic_date' to match sample, and 'ingested_at')
            'oic_date': publication_date,
            'ingested_at': scraped_at,
            
            # Parliament context
            'parliament_session_id_assigned': parliament_session_id,
            
            # Processing status (matching the pattern from other pipelines)
            'evidence_processing_status': 'pending_evidence_creation',
            
            # Department fields (often not available from scraping)
            'responsible_department_raw': None,
            'responsible_minister_raw': None,
            'act_citation_raw': None,
            
            # Linking fields
            'related_evidence_item_id': None,
            
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
        # Use raw_oic_id as the primary identifier (matches production structure)
        raw_oic_id = item.get('raw_oic_id')
        if raw_oic_id:
            return raw_oic_id
        
        # Fallback to attach_id if no OIC number available
        attach_id = item.get('attach_id')
        if attach_id:
            return str(attach_id)
        
        # Final fallback to hash of content
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