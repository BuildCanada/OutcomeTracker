#!/usr/bin/env python3
"""
Re-ingestion script to fetch missing XML content for Parliament 45 bills.

This script will:
1. Find all Parliament 45-1 bills that don't have XML content
2. Attempt to fetch XML for those bills using the improved ingestion logic
3. Update the bills with the fetched XML content
"""

import logging
import sys
import requests
import json
import firebase_admin
from firebase_admin import firestore
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Any, Optional, List

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)

logger = logging.getLogger(__name__)

# Initialize Firebase
if not firebase_admin._apps:
    firebase_admin.initialize_app()

db = firestore.client()

class Parliament45XMLReingestion:
    """Re-ingestion class for Parliament 45 XML content"""
    
    def __init__(self):
        self.headers = {'User-Agent': 'Promise Tracker Pipeline/2.0 (XML Re-ingestion)'}
        self.xml_request_timeout = 120
        self.xml_max_retries = 5
        
    def run_reingestion(self):
        """Main method to run the re-ingestion process"""
        logger.info("🔄 Starting Parliament 45 XML re-ingestion...")
        
        # Get all Parliament 45-1 bills
        bills = self._get_parliament_45_bills()
        logger.info(f"Found {len(bills)} Parliament 45-1 bills")
        
        # Filter bills that need XML updates
        bills_needing_xml = self._filter_bills_needing_xml(bills)
        logger.info(f"Found {len(bills_needing_xml)} bills that need XML content")
        
        if not bills_needing_xml:
            logger.info("✅ All Parliament 45 bills already have XML content!")
            return
        
        # Process each bill to fetch XML
        success_count = 0
        error_count = 0
        
        for i, (doc_id, bill_data) in enumerate(bills_needing_xml):
            bill_code = bill_data.get('bill_number_code_feed', 'Unknown')
            logger.info(f"\n📄 Processing bill {i+1}/{len(bills_needing_xml)}: {bill_code}")
            
            try:
                # Parse bill details to get XML construction data
                bill_details = self._parse_bill_details(bill_data)
                if not bill_details:
                    logger.warning(f"Could not parse bill details for {bill_code}")
                    error_count += 1
                    continue
                
                # Fetch XML content
                xml_content = self._fetch_bill_xml(bill_details)
                
                if xml_content:
                    # Update the bill with XML content
                    self._update_bill_with_xml(doc_id, xml_content)
                    logger.info(f"✅ Successfully added XML to {bill_code} ({len(xml_content)} chars)")
                    success_count += 1
                else:
                    logger.info(f"ℹ️  No XML available for {bill_code}")
                    error_count += 1
                    
            except Exception as e:
                logger.error(f"❌ Error processing {bill_code}: {e}")
                error_count += 1
        
        logger.info(f"\n🎯 Re-ingestion complete!")
        logger.info(f"   ✅ Successfully updated: {success_count} bills")
        logger.info(f"   ❌ Failed/No XML: {error_count} bills")
        logger.info(f"   📊 Total processed: {len(bills_needing_xml)} bills")
        
        if success_count > 0:
            logger.info(f"\n🔄 Consider running the processor to create evidence items for newly updated bills")
    
    def _get_parliament_45_bills(self) -> List[tuple]:
        """Get all Parliament 45-1 bills from Firestore"""
        try:
            from firebase_admin import firestore as fb_firestore
            
            query = db.collection('raw_legisinfo_bill_details').where(
                filter=fb_firestore.FieldFilter('parliament_session_id', '==', '45-1')
            )
            
            bills = []
            for doc in query.stream():
                bills.append((doc.id, doc.to_dict()))
            
            return bills
            
        except Exception as e:
            logger.error(f"Error fetching Parliament 45 bills: {e}")
            return []
    
    def _filter_bills_needing_xml(self, bills: List[tuple]) -> List[tuple]:
        """Filter bills that don't have XML content or have very short XML"""
        bills_needing_xml = []
        
        for doc_id, bill_data in bills:
            bill_code = bill_data.get('bill_number_code_feed', 'Unknown')
            xml_content = bill_data.get('raw_xml_content')
            
            # Check if bill needs XML
            needs_xml = False
            
            if not xml_content:
                logger.debug(f"{bill_code}: No XML content")
                needs_xml = True
            elif len(xml_content) < 1000:
                logger.debug(f"{bill_code}: XML too short ({len(xml_content)} chars)")
                needs_xml = True
            elif not xml_content.strip().startswith('<?xml'):
                logger.debug(f"{bill_code}: Invalid XML format")
                needs_xml = True
                
            if needs_xml:
                bills_needing_xml.append((doc_id, bill_data))
        
        return bills_needing_xml
    
    def _parse_bill_details(self, bill_data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Parse bill details from the raw JSON content"""
        try:
            raw_json_content = bill_data.get('raw_json_content', '[]')
            if isinstance(raw_json_content, str):
                bill_details_list = json.loads(raw_json_content)
            else:
                bill_details_list = raw_json_content
            
            if bill_details_list and len(bill_details_list) > 0:
                return bill_details_list[0]
            else:
                return None
                
        except Exception as e:
            logger.error(f"Error parsing bill details: {e}")
            return None
    
    def _construct_xml_url(self, bill_data: Dict[str, Any]) -> Optional[str]:
        """Construct XML URL from bill data"""
        parl = bill_data.get('ParliamentNumber')
        session = bill_data.get('SessionNumber') 
        bill_code = (bill_data.get('BillNumberFormatted') or 
                    bill_data.get('NumberCode'))
        is_government_bill = bill_data.get('IsGovernmentBill', True)

        if not all([parl, session, bill_code]):
            logger.warning(f"Cannot construct XML URL for bill {bill_code} due to missing basic data.")
            return None

        # Determine bill type folder based on IsGovernmentBill field
        if is_government_bill:
            bill_type_url_part = 'Government'
        else:
            bill_type_url_part = 'Private'

        url = f"https://www.parl.ca/Content/Bills/{parl}{session}/{bill_type_url_part}/{bill_code}/{bill_code}_1/{bill_code}_E.xml"
        logger.debug(f"Constructed XML URL for {bill_code}: {url}")
        return url
    
    def _fetch_bill_xml(self, bill_details: Dict[str, Any]) -> Optional[str]:
        """Fetch XML content for a bill with robust retry logic"""
        xml_url = self._construct_xml_url(bill_details)
        if not xml_url:
            return None
        
        bill_code = bill_details.get('NumberCode') or bill_details.get('BillNumberFormatted', 'Unknown')
        
        try:
            response = self._make_xml_request(xml_url, bill_code)
            if response:
                response.encoding = response.apparent_encoding or 'utf-8'
                xml_content = response.text
                
                # Validate XML content
                if self._validate_xml_content(xml_content, bill_code):
                    return xml_content
                else:
                    logger.warning(f"Invalid XML content received for {bill_code}")
                    return None
            else:
                return None
                
        except Exception as e:
            logger.warning(f"Could not fetch XML for bill {bill_code} from {xml_url}: {e}")
            return None
    
    def _make_xml_request(self, url: str, bill_code: str) -> Optional[requests.Response]:
        """Make XML request with enhanced retry logic"""
        import time
        
        for attempt in range(self.xml_max_retries):
            try:
                # Calculate exponential backoff delay
                if attempt > 0:
                    delay = min(2 ** attempt, 30)  # Cap at 30 seconds
                    logger.debug(f"Waiting {delay}s before retry {attempt + 1} for {bill_code} XML...")
                    time.sleep(delay)
                
                logger.debug(f"Attempting XML fetch for {bill_code} (attempt {attempt + 1}/{self.xml_max_retries})")
                
                response = requests.get(
                    url,
                    headers=self.headers,
                    timeout=self.xml_request_timeout,
                    allow_redirects=True,
                    stream=False
                )
                
                if response.status_code == 200:
                    return response
                elif response.status_code == 404:
                    logger.debug(f"XML not available for {bill_code} (404)")
                    return None
                else:
                    response.raise_for_status()
                
            except requests.exceptions.Timeout as e:
                if attempt < self.xml_max_retries - 1:
                    logger.warning(f"XML request timeout for {bill_code} (attempt {attempt + 1}/{self.xml_max_retries})")
                    continue
                else:
                    logger.error(f"XML request timed out for {bill_code} after {self.xml_max_retries} attempts")
                    return None
                    
            except requests.exceptions.RequestException as e:
                if attempt < self.xml_max_retries - 1:
                    logger.warning(f"XML request failed for {bill_code} (attempt {attempt + 1}/{self.xml_max_retries})")
                    continue
                else:
                    logger.error(f"XML request failed for {bill_code} after {self.xml_max_retries} attempts")
                    return None
        
        return None
    
    def _validate_xml_content(self, xml_content: str, bill_code: str) -> bool:
        """Validate XML content"""
        if not xml_content:
            return False
        
        # Check minimum length
        if len(xml_content) < 1000:
            logger.debug(f"XML content for {bill_code} is too short: {len(xml_content)} characters")
            return False
        
        # Check for XML declaration
        if not xml_content.strip().startswith('<?xml'):
            logger.debug(f"XML content for {bill_code} doesn't start with XML declaration")
            return False
        
        # Check for Bill root element
        if '<Bill' not in xml_content:
            logger.debug(f"XML content for {bill_code} doesn't contain Bill element")
            return False
        
        return True
    
    def _update_bill_with_xml(self, doc_id: str, xml_content: str):
        """Update bill document with XML content"""
        try:
            db.collection('raw_legisinfo_bill_details').document(doc_id).update({
                'raw_xml_content': xml_content,
                'xml_updated_at': datetime.now(timezone.utc)
            })
        except Exception as e:
            logger.error(f"Error updating bill {doc_id} with XML: {e}")
            raise

def main():
    """Main function"""
    reingestion = Parliament45XMLReingestion()
    reingestion.run_reingestion()

if __name__ == "__main__":
    main() 