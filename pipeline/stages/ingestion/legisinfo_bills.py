"""
LEGISinfo Bills Ingestion Job

Ingests bill information from the LEGISinfo API into the raw_bills collection.

"""

import logging
import sys
import requests
import json
from datetime import datetime, timezone, timedelta
from typing import Dict, Any, List, Optional
from pathlib import Path

# Handle imports for both module execution and testing
try:
    from .base_ingestion import BaseIngestionJob
except ImportError:
    # Add pipeline directory to path for testing
    pipeline_dir = Path(__file__).parent.parent.parent
    sys.path.insert(0, str(pipeline_dir))
    from stages.ingestion.base_ingestion import BaseIngestionJob


class LegisInfoBillsIngestion(BaseIngestionJob):
    """
    Ingestion job for LEGISinfo bill data.
    
    Fetches bill information from LEGISinfo JSON API and stores in 
    raw_legisinfo_bill_details collection.
    """
    
    def __init__(self, job_name: str, config: Dict[str, Any] = None):
        """Initialize the LEGISinfo Bills ingestion job"""
        # Set config first so we can access override before super().__init__()
        self.config = config or {}
        
        # Allow test collection override
        self._collection_name_override = self.config.get('collection_name')
        
        super().__init__(job_name, config)
        
        # API endpoints
        self.bill_list_url = "https://www.parl.ca/legisinfo/en/bills/json"
        self.bill_details_base_url = "https://www.parl.ca/legisinfo/en/bill"
        
        # Request settings
        self.headers = {'User-Agent': 'Promise Tracker Pipeline/2.0 (Government Data Ingestion)'}
        self.request_timeout = self.config.get('request_timeout', 60)
        self.max_retries = self.config.get('max_retries', 3)
        
        # Processing settings
        self.min_parliament = self.config.get('min_parliament', 44)  # Start from Parliament 44
        self.max_parliament = self.config.get('max_parliament', None)  # Optional upper bound
        self.max_bills_per_run = self.config.get('max_bills_per_run', None)
    
    def _get_source_name(self) -> str:
        """Return the human-readable name of the data source"""
        return "LEGISinfo Bills"
    
    def _get_collection_name(self) -> str:
        """Return the Firestore collection name for raw data"""
        return self._collection_name_override or "raw_legisinfo_bill_details"
    
    def _fetch_new_items(self, since_date: datetime = None) -> List[Dict[str, Any]]:
        """
        Fetch new bill items from LEGISinfo API.
        
        Args:
            since_date: Only fetch bills updated since this date
            
        Returns:
            List of raw bill items
        """
        self.logger.info("Fetching bill list from LEGISinfo API")
        
        # Fetch main bill list
        bill_list = self._fetch_bill_list()
        if not bill_list:
            self.logger.error("Failed to fetch bill list")
            return []
        
        # Filter bills by parliament number
        filtered_bills = self._filter_bills_by_parliament(bill_list)
        
        # Filter by update date if specified
        if since_date:
            filtered_bills = self._filter_bills_by_date(filtered_bills, since_date)
        
        # Limit number of bills if configured
        if self.max_bills_per_run:
            filtered_bills = filtered_bills[:self.max_bills_per_run]
        
        self.logger.info(f"Processing {len(filtered_bills)} bills")
        
        # Fetch detailed data for each bill
        detailed_bills = []
        for i, bill in enumerate(filtered_bills):
            try:
                self.logger.info(f"Processing bill {i+1}/{len(filtered_bills)}: {bill.get('BillNumberFormatted', 'Unknown')}")
                
                # Fetch detailed JSON for this bill
                detailed_data = self._fetch_bill_details(bill)
                if detailed_data:
                    # Combine list data with detailed data
                    combined_data = {
                        'bill_list_data': bill,
                        'bill_details_data': detailed_data,
                        'fetch_timestamp': datetime.now(timezone.utc)
                    }
                    detailed_bills.append(combined_data)
                
            except Exception as e:
                self.logger.error(f"Error processing bill {bill.get('BillNumberFormatted', 'Unknown')}: {e}")
                continue
        
        return detailed_bills
    
    def _fetch_bill_list(self) -> Optional[List[Dict[str, Any]]]:
        """Fetch the main bill list from LEGISinfo JSON API"""
        try:
            response = self._make_request(self.bill_list_url)
            return response.json()
        except Exception as e:
            self.logger.error(f"Error fetching bill list: {e}")
            return None
    
    def _fetch_bill_details(self, bill: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        Fetch detailed JSON for a specific bill.
        
        Args:
            bill: Bill data from main list
            
        Returns:
            Detailed bill data or None if fetch fails
        """
        parliament_num = bill.get('ParliamentNumber')
        session_num = bill.get('SessionNumber')
        bill_code = bill.get('BillNumberFormatted', '')
        
        if not all([parliament_num, session_num, bill_code]):
            self.logger.warning(f"Missing required fields for bill: {bill}")
            return None
        
        url = f"{self.bill_details_base_url}/{parliament_num}-{session_num}/{bill_code}/json?view=details"
        
        try:
            response = self._make_request(url)
            return response.json()
        except Exception as e:
            self.logger.error(f"Error fetching details for bill {bill_code}: {e}")
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
    
    def _filter_bills_by_parliament(self, bills: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Filter bills by parliament number range"""
        filtered_bills = []
        excluded_count = 0
        
        for bill in bills:
            parliament_num = bill.get('ParliamentNumber')
            if parliament_num:
                parliament_num = int(parliament_num)
                
                # Check minimum parliament
                if parliament_num < self.min_parliament:
                    excluded_count += 1
                    continue
                
                # Check maximum parliament if specified
                if self.max_parliament is not None and parliament_num > self.max_parliament:
                    excluded_count += 1
                    continue
                
                filtered_bills.append(bill)
            else:
                excluded_count += 1
        
        if excluded_count > 0:
            parliament_range = f"{self.min_parliament}"
            if self.max_parliament:
                parliament_range += f"-{self.max_parliament}"
            else:
                parliament_range += "+"
            self.logger.info(f"Excluded {excluded_count} bills outside parliament range {parliament_range}")
        
        self.logger.info(f"Filtered to {len(filtered_bills)} bills from parliament {self.min_parliament}" + 
                        (f"-{self.max_parliament}" if self.max_parliament else "+"))
        return filtered_bills
    
    def _filter_bills_by_date(self, bills: List[Dict[str, Any]], since_date: datetime) -> List[Dict[str, Any]]:
        """Filter bills by last activity date"""
        filtered_bills = []
        
        for bill in bills:
            last_activity = bill.get('LatestActivityDateTime')
            if last_activity:
                try:
                    activity_date = self._parse_legisinfo_datetime(last_activity)
                    if activity_date and activity_date >= since_date:
                        filtered_bills.append(bill)
                except Exception as e:
                    self.logger.debug(f"Error parsing date for bill {bill.get('BillNumberFormatted', 'Unknown')}: {e}")
                    # Include bills with unparseable dates to be safe
                    filtered_bills.append(bill)
            else:
                # Include bills without activity dates
                filtered_bills.append(bill)
        
        self.logger.info(f"Filtered to {len(filtered_bills)} bills with activity since {since_date}")
        return filtered_bills
    
    def _parse_legisinfo_datetime(self, date_str: str) -> Optional[datetime]:
        """Parse datetime string from LEGISinfo JSON API"""
        if not date_str:
            return None
        try:
            return datetime.fromisoformat(date_str).astimezone(timezone.utc)
        except ValueError:
            try:
                # Fallback to dateutil parser
                return dateutil_parser.parse(date_str).astimezone(timezone.utc)
            except Exception:
                self.logger.warning(f"Could not parse LEGISinfo date string: {date_str}")
                return None
    
    def _process_raw_item(self, raw_item: Dict[str, Any]) -> Dict[str, Any]:
        """
        Process a single raw bill item into standardized format that matches
        the existing Parliament 44 bill structure.
        
        Args:
            raw_item: Raw bill item with list and detail data
            
        Returns:
            Processed item ready for Firestore storage
        """
        bill_list_data = raw_item['bill_list_data']
        bill_details_data = raw_item['bill_details_data']
        
        # Handle case where bill_details_data is a list (API returns list containing one dict)
        if isinstance(bill_details_data, list) and len(bill_details_data) > 0:
            bill_details_data = bill_details_data[0]
        elif isinstance(bill_details_data, list) and len(bill_details_data) == 0:
            self.logger.warning("Empty bill_details_data list received")
            bill_details_data = {}
        
        # Extract key information
        parliament_num = bill_list_data.get('ParliamentNumber')
        session_num = bill_list_data.get('SessionNumber')
        bill_code = bill_list_data.get('BillNumberFormatted', '')
        
        # Create parliament session ID (format: "44-1")
        parliament_session_id = f"{parliament_num}-{session_num}"
        
        # Parse dates
        latest_activity = self._parse_legisinfo_datetime(bill_list_data.get('LatestActivityDateTime'))
        
        # Extract ID from bill details
        parl_id = str(bill_details_data.get('Id', ''))
        
        # Create source URL
        source_url = f"https://www.parl.ca/legisinfo/en/bill/{parliament_session_id}/{bill_code}/json?view=details"
        
        # Store raw JSON content as string (matching Parliament 44 format)
        raw_json_content = json.dumps([bill_details_data]) if bill_details_data else "[]"
        
        # Use existing Parliament 44 field structure
        processed_item = {
            # Core identification (matching Parliament 44 format)
            'bill_number_code_feed': bill_code,
            'parl_id': parl_id,
            'parliament_session_id': parliament_session_id,
            
            # Store raw JSON as string (like Parliament 44)
            'raw_json_content': raw_json_content,
            'source_detailed_json_url': source_url,
            
            # Dates
            'ingested_at': latest_activity,
            
            # Processing status 
            'processing_status': 'pending_processing',
            
            # Metadata
            'fetch_timestamp': raw_item['fetch_timestamp'],
            'last_updated_at': datetime.now(timezone.utc)
        }
        
        return processed_item
    
    def _clean_html_text(self, html_text: str) -> str:
        """Clean HTML tags from text"""
        if not html_text:
            return ""
        
        import re
        # Replace <br> with newline
        cleaned = re.sub(r'<br\s*/?>', '\n', html_text)
        # Strip other HTML tags
        cleaned = re.sub(r'<[^>]+>', '', cleaned).strip()
        return cleaned
    
    def _generate_item_id(self, item: Dict[str, Any]) -> str:
        """
        Generate a unique ID for the bill item using the same pattern as Parliament 44.
        
        Args:
            item: Processed bill item
            
        Returns:
            Unique item ID
        """
        # Use format: {parliament_session_id}_{bill_code} (like "44-1_C-1")
        parliament_session = item.get('parliament_session_id', '')
        bill_code = item.get('bill_number_code_feed', '')
        
        if parliament_session and bill_code:
            return f"{parliament_session}_{bill_code}"
        
        # Fallback to parl_id if available
        return item.get('parl_id', f"bill_{item.get('fetch_timestamp', '')}")
    
    def _should_update_item(self, existing_item: Dict[str, Any], 
                           new_item: Dict[str, Any]) -> bool:
        """
        Determine if an existing bill item should be updated.
        
        Args:
            existing_item: Current item in database
            new_item: New item from API
            
        Returns:
            True if item should be updated
        """
        # Always update if processing status allows it
        status = existing_item.get('processing_status', '')
        if status == 'error_processing_script':
            return True
        
        # Check if latest activity date has changed
        existing_activity = existing_item.get('ingested_at')
        new_activity = new_item.get('ingested_at')
        
        if existing_activity != new_activity:
            return True
        
        # Check if status has changed
        if existing_item.get('status') != new_item.get('status'):
            return True
        
        return False 