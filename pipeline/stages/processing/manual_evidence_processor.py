"""
Manual Evidence Processor Job

Processes raw manual evidence additions from the admin interface into evidence items.
This handles the automated pathway where users provide URLs for automatic processing.
"""

import logging
import sys
from datetime import datetime, timezone
from typing import Dict, Any, Optional
import requests
from bs4 import BeautifulSoup
import re
from pathlib import Path

# Handle imports for both module execution and testing
try:
    from .base_processor import BaseProcessorJob
    from ...config.evidence_source_types import get_standardized_source_type_for_processor
except ImportError:
    # Add pipeline directory to path for testing
    pipeline_dir = Path(__file__).parent.parent.parent
    sys.path.insert(0, str(pipeline_dir))
    from stages.processing.base_processor import BaseProcessorJob
    from config.evidence_source_types import get_standardized_source_type_for_processor


class ManualEvidenceProcessor(BaseProcessorJob):
    """
    Processing job for manual evidence additions from admin interface.
    
    Transforms raw manual evidence items (URLs) into structured evidence items
    with automatic content extraction and LLM-based analysis.
    """
    
    def __init__(self, job_name: str, config: Dict[str, Any] = None):
        """Initialize the Manual Evidence processor"""
        super().__init__(job_name, config)
        
        # Content extraction settings
        self.max_content_length = self.config.get('max_content_length', 10000)
        self.request_timeout = self.config.get('request_timeout', 30)
        self.user_agent = self.config.get('user_agent', 
            'Mozilla/5.0 (compatible; PromiseTracker/1.0; +https://promisetracker.ca)')
    
    def _get_source_collection(self) -> str:
        """Return the Firestore collection name for raw data"""
        return "raw_manual_evidence_addition"
    
    def _get_target_collection(self) -> str:
        """Return the Firestore collection name for evidence items"""
        return "evidence_items_test"
    
    def _get_evidence_id_source_type(self) -> str:
        """Get the source type identifier for evidence ID generation"""
        return 'Manual'
    
    def _process_raw_item(self, raw_item: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        Process a single raw manual evidence item into an evidence item.
        
        Args:
            raw_item: Raw manual evidence item from admin interface
            
        Returns:
            Evidence item ready for storage or None if processing failed
        """
        try:
            # Extract basic information
            source_url = raw_item.get('source_url', '')
            selected_promise_ids = raw_item.get('selected_promise_ids', [])
            
            if not source_url:
                self.logger.warning(f"Manual evidence item missing source URL: {raw_item.get('_doc_id', 'unknown')}")
                return None
            
            # Extract content from URL
            content_data = self._extract_content_from_url(source_url)
            if not content_data:
                self.logger.error(f"Failed to extract content from URL: {source_url}")
                return None
            
            # Perform LLM analysis if enabled
            llm_analysis = None
            if content_data.get('full_text'):
                llm_analysis = self._analyze_with_llm(content_data)
            
            # Create evidence item
            evidence_item = {
                # Core identification
                'title_or_summary': content_data.get('title', ''),
                'description_or_details': content_data.get('description', ''),
                'full_text': content_data.get('full_text', ''),
                'evidence_source_type': self._determine_source_type(source_url, content_data),
                'source_url': source_url,
                
                # Promise linking
                'promise_ids': selected_promise_ids,
                
                # Dates
                'publication_date': content_data.get('publication_date'),
                'scraped_at': datetime.now(timezone.utc),
                
                # Source metadata
                'source_metadata': {
                    'creation_mode': 'automated',
                    'created_via': 'admin_interface',
                    'content_extraction': content_data.get('extraction_metadata', {}),
                    'raw_item_id': raw_item.get('raw_item_id', '')
                },
                
                # Parliament context
                'parliament_session_id': raw_item.get('parliament_session_id_assigned'),
                
                # Processing metadata
                'evidence_type': 'manual_entry',
                'processing_notes': [],
                
                # LLM analysis results
                'llm_analysis': llm_analysis,
                
                # Extracted fields from LLM analysis
                'topics': llm_analysis.get('topics', []) if llm_analysis else [],
                'policy_areas': llm_analysis.get('policy_areas', []) if llm_analysis else [],
                'departments': llm_analysis.get('departments', []) if llm_analysis else [],
                'summary': llm_analysis.get('summary', '') if llm_analysis else content_data.get('description', ''),
                
                # Status tracking
                'promise_linking_status': 'pending',
                'created_at': datetime.now(timezone.utc),
                'last_updated_at': datetime.now(timezone.utc)
            }
            
            return evidence_item
            
        except Exception as e:
            self.logger.error(f"Error processing manual evidence item {raw_item.get('_doc_id', 'unknown')}: {e}")
            return None
    
    def _extract_content_from_url(self, url: str) -> Optional[Dict[str, Any]]:
        """
        Extract content from a given URL.
        
        Args:
            url: URL to extract content from
            
        Returns:
            Dictionary containing extracted content or None if extraction failed
        """
        try:
            headers = {
                'User-Agent': self.user_agent,
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
                'Accept-Language': 'en-US,en;q=0.5',
                'Accept-Encoding': 'gzip, deflate',
                'Connection': 'keep-alive',
            }
            
            response = requests.get(url, headers=headers, timeout=self.request_timeout)
            response.raise_for_status()
            
            # Parse HTML content
            soup = BeautifulSoup(response.content, 'html.parser')
            
            # Extract title
            title = self._extract_title(soup)
            
            # Extract description/summary
            description = self._extract_description(soup)
            
            # Extract main content
            full_text = self._extract_main_content(soup)
            
            # Try to extract publication date
            publication_date = self._extract_publication_date(soup)
            
            # Truncate content if too long
            if len(full_text) > self.max_content_length:
                full_text = full_text[:self.max_content_length] + "..."
            
            return {
                'title': title,
                'description': description,
                'full_text': full_text,
                'publication_date': publication_date,
                'extraction_metadata': {
                    'content_length': len(full_text),
                    'extraction_timestamp': datetime.now(timezone.utc),
                    'response_status': response.status_code,
                    'content_type': response.headers.get('content-type', '')
                }
            }
            
        except requests.RequestException as e:
            self.logger.error(f"Error fetching URL {url}: {e}")
            return None
        except Exception as e:
            self.logger.error(f"Error extracting content from {url}: {e}")
            return None
    
    def _extract_title(self, soup: BeautifulSoup) -> str:
        """Extract title from HTML"""
        # Try various title sources
        title_selectors = [
            'h1',
            'title',
            '[property="og:title"]',
            '[name="twitter:title"]',
            '.title',
            '.headline'
        ]
        
        for selector in title_selectors:
            element = soup.select_one(selector)
            if element:
                title = element.get_text(strip=True) if hasattr(element, 'get_text') else element.get('content', '')
                if title and len(title) > 10:  # Ensure meaningful title
                    return title[:200]  # Limit length
        
        return "Extracted Content"
    
    def _extract_description(self, soup: BeautifulSoup) -> str:
        """Extract description/summary from HTML"""
        # Try various description sources
        description_selectors = [
            '[name="description"]',
            '[property="og:description"]',
            '[name="twitter:description"]',
            '.summary',
            '.excerpt',
            '.lead'
        ]
        
        for selector in description_selectors:
            element = soup.select_one(selector)
            if element:
                desc = element.get_text(strip=True) if hasattr(element, 'get_text') else element.get('content', '')
                if desc and len(desc) > 20:  # Ensure meaningful description
                    return desc[:500]  # Limit length
        
        # Fallback: use first paragraph
        first_p = soup.select_one('p')
        if first_p:
            desc = first_p.get_text(strip=True)
            if len(desc) > 20:
                return desc[:500]
        
        return ""
    
    def _extract_main_content(self, soup: BeautifulSoup) -> str:
        """Extract main content from HTML"""
        # Remove unwanted elements
        for element in soup(['script', 'style', 'nav', 'header', 'footer', 'aside']):
            element.decompose()
        
        # Try to find main content area
        content_selectors = [
            'main',
            'article',
            '.content',
            '.main-content',
            '.article-body',
            '.post-content',
            '#content'
        ]
        
        for selector in content_selectors:
            content_element = soup.select_one(selector)
            if content_element:
                text = content_element.get_text(separator=' ', strip=True)
                if len(text) > 100:  # Ensure substantial content
                    return text
        
        # Fallback: extract all paragraph text
        paragraphs = soup.find_all('p')
        if paragraphs:
            text = ' '.join([p.get_text(strip=True) for p in paragraphs])
            if len(text) > 100:
                return text
        
        # Final fallback: body text
        body = soup.find('body')
        if body:
            return body.get_text(separator=' ', strip=True)
        
        return soup.get_text(separator=' ', strip=True)
    
    def _extract_publication_date(self, soup: BeautifulSoup) -> Optional[datetime]:
        """Extract publication date from HTML"""
        date_selectors = [
            '[property="article:published_time"]',
            '[name="date"]',
            '[name="publish_date"]',
            '.date',
            '.published',
            'time[datetime]'
        ]
        
        for selector in date_selectors:
            element = soup.select_one(selector)
            if element:
                date_str = element.get('content') or element.get('datetime') or element.get_text(strip=True)
                if date_str:
                    try:
                        # Try to parse various date formats
                        from dateutil import parser
                        return parser.parse(date_str)
                    except:
                        continue
        
        return None
    
    def _determine_source_type(self, url: str, content_data: Dict[str, Any]) -> str:
        """Determine the evidence source type based on URL and content"""
        url_lower = url.lower()
        title = content_data.get('title', '').lower()
        content = content_data.get('full_text', '').lower()
        
        # Government domains
        if any(domain in url_lower for domain in ['canada.ca', 'gc.ca', 'parl.ca']):
            if 'news' in url_lower or 'announcement' in title:
                return 'government_announcement'
            elif 'policy' in url_lower or 'policy' in title:
                return 'policy_document'
            elif 'budget' in url_lower or 'budget' in title:
                return 'budget_document'
            else:
                return 'government_announcement'  # Default for government domains
        
        # News sources
        elif any(domain in url_lower for domain in ['cbc.ca', 'globalnews.ca', 'ctv', 'nationalpost']):
            return 'news_release'
        
        # Legislative sources
        elif 'parl.ca' in url_lower or 'legisinfo' in url_lower:
            return 'legislation'
        
        # Default based on content
        elif any(word in content for word in ['minister', 'government', 'policy']):
            return 'government_announcement'
        else:
            return 'other'
    
    def _analyze_with_llm(self, content_data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        Analyze content with LLM to extract structured information.
        
        Args:
            content_data: Extracted content data
            
        Returns:
            LLM analysis results or None if analysis failed
        """
        try:
            # Prepare content for analysis
            title = content_data.get('title', '')
            description = content_data.get('description', '')
            full_text = content_data.get('full_text', '')
            
            content_for_analysis = f"Title: {title}\n\nDescription: {description}\n\nContent: {full_text}"
            
            # TODO: Replace with actual LLM call
            # For now, return a placeholder analysis structure
            analysis = {
                'summary': description or title,
                'topics': self._extract_basic_topics(content_for_analysis),
                'policy_areas': self._extract_basic_policy_areas(content_for_analysis),
                'departments': self._extract_basic_departments(content_for_analysis),
                'relevance_score': self._calculate_basic_relevance(content_for_analysis),
                'analysis_timestamp': datetime.now(timezone.utc)
            }
            
            return analysis
            
        except Exception as e:
            self.logger.error(f"Error in LLM analysis: {e}")
            return None
    
    def _extract_basic_topics(self, content: str) -> list:
        """Basic topic extraction using keyword matching"""
        content_lower = content.lower()
        topics = []
        
        topic_keywords = {
            'healthcare': ['health', 'medical', 'hospital', 'healthcare'],
            'education': ['education', 'school', 'student', 'university'],
            'environment': ['environment', 'climate', 'carbon', 'green'],
            'economy': ['economy', 'economic', 'business', 'trade'],
            'infrastructure': ['infrastructure', 'transport', 'road', 'bridge'],
            'immigration': ['immigration', 'immigrant', 'refugee'],
            'defense': ['defense', 'military', 'security']
        }
        
        for topic, keywords in topic_keywords.items():
            if any(keyword in content_lower for keyword in keywords):
                topics.append(topic)
        
        return topics
    
    def _extract_basic_policy_areas(self, content: str) -> list:
        """Basic policy area extraction"""
        return self._extract_basic_topics(content)  # Reuse topic extraction
    
    def _extract_basic_departments(self, content: str) -> list:
        """Basic department extraction using keyword matching"""
        content_lower = content.lower()
        departments = []
        
        department_patterns = [
            'Health Canada',
            'Transport Canada',
            'Environment and Climate Change Canada',
            'Immigration, Refugees and Citizenship Canada',
            'Public Safety Canada'
        ]
        
        for dept in department_patterns:
            if dept.lower() in content_lower:
                departments.append(dept)
        
        return departments
    
    def _calculate_basic_relevance(self, content: str) -> float:
        """Calculate basic relevance score"""
        content_lower = content.lower()
        score = 0.5  # Base score
        
        # Boost for policy-related content
        if any(word in content_lower for word in ['policy', 'government', 'minister']):
            score += 0.2
        
        # Boost for action words
        if any(word in content_lower for word in ['announce', 'implement', 'launch']):
            score += 0.2
        
        return min(score, 1.0)
    
    def _should_update_evidence(self, existing_evidence: Dict[str, Any], 
                               new_evidence: Dict[str, Any]) -> bool:
        """Determine if existing evidence should be updated"""
        # Update if content has changed significantly
        content_fields = ['title_or_summary', 'description_or_details', 'full_text']
        for field in content_fields:
            if existing_evidence.get(field) != new_evidence.get(field):
                return True
        
        # Update if publication date has changed
        if existing_evidence.get('publication_date') != new_evidence.get('publication_date'):
            return True
        
        return False 