"""
LEGISinfo Processor Job

Processes raw bill data into evidence items with legislative analysis.
This replaces the existing process_legisinfo_to_evidence.py script with a more robust,
class-based implementation.
"""

import logging
import sys
from datetime import datetime, timezone
from typing import Dict, Any, Optional
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


class LegisInfoProcessor(BaseProcessorJob):
    """
    Processing job for LEGISinfo bill data.
    
    Transforms raw bill data into structured evidence items
    with analysis of legislative progress and relevance.
    """
    
    def __init__(self, job_name: str, config: Dict[str, Any] = None):
        """Initialize the LEGISinfo processor"""
        super().__init__(job_name, config)
        
        # Processing settings
        self.include_private_bills = self.config.get('include_private_bills', False)
        self.min_relevance_threshold = self.config.get('min_relevance_threshold', 0.3)
    
    def _get_source_collection(self) -> str:
        """Return the Firestore collection name for raw data"""
        return "raw_legisinfo_bill_details"
    
    def _get_target_collection(self) -> str:
        """Return the Firestore collection name for evidence items"""
        return "evidence_items"
    
    def _process_raw_item(self, raw_item: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        Process a single raw bill item into an evidence item.
        
        Args:
            raw_item: Raw bill item from LEGISinfo
            
        Returns:
            Evidence item ready for storage or None if processing failed
        """
        try:
            # Extract bill information
            bill_list_data = raw_item.get('bill_list_json', {})
            bill_details_data = raw_item.get('bill_details_json', {})
            
            # Basic validation
            bill_number = raw_item.get('bill_number_formatted', '')
            title = raw_item.get('title', '')
            
            if not bill_number or not title:
                self.logger.warning(f"Bill missing required fields: {raw_item.get('_doc_id', 'unknown')}")
                return None
            
            # Check if we should include this bill
            if not self._should_include_bill(raw_item):
                return None
            
            # Extract and analyze bill content
            bill_analysis = self._analyze_bill_content(raw_item)
            
            # Create evidence item
            evidence_item = {
                # Core identification
                'title_or_summary': title,
                'description_or_details': self._extract_bill_description(raw_item),
                'full_text': self._extract_bill_full_text(raw_item),
                'evidence_source_type': get_standardized_source_type_for_processor('legisinfo'),
                'source_url': self._build_bill_url(raw_item),
                
                # Bill-specific fields
                'bill_number': bill_number,
                'bill_type': raw_item.get('bill_type', ''),
                'parliament_number': raw_item.get('parliament_number'),
                'session_number': raw_item.get('session_number'),
                'status': raw_item.get('status', ''),
                'short_title': raw_item.get('short_title', ''),
                
                # Dates
                'publication_date': raw_item.get('latest_activity_datetime'),
                'introduction_date': raw_item.get('introduction_date'),
                'scraped_at': raw_item.get('fetch_timestamp'),
                
                # Sponsor information
                'sponsor_name': raw_item.get('sponsor_name', ''),
                'sponsor_affiliation': raw_item.get('sponsor_affiliation', ''),
                
                # Source metadata
                'source_metadata': {
                    'human_readable_id': raw_item.get('human_readable_id', ''),
                    'bill_list_data': bill_list_data,
                    'bill_details_data': bill_details_data
                },
                
                # Parliament context
                'parliament_session_id': self._determine_parliament_session(raw_item),
                
                # Processing metadata
                'evidence_type': 'legislative_action',
                'evidence_subtype': self._classify_bill_type(raw_item),
                'confidence_score': self._calculate_confidence_score(raw_item, bill_analysis),
                'processing_notes': [],
                
                # Bill analysis results
                'bill_analysis': bill_analysis,
                
                # Extracted fields
                'topics': bill_analysis.get('topics', []),
                'policy_areas': bill_analysis.get('policy_areas', []),
                'departments': bill_analysis.get('departments', []),
                'summary': bill_analysis.get('summary', ''),
                
                # Status tracking
                'promise_linking_status': 'pending',
                'created_at': datetime.now(timezone.utc),
                'last_updated_at': datetime.now(timezone.utc)
            }
            
            return evidence_item
            
        except Exception as e:
            self.logger.error(f"Error processing bill {raw_item.get('_doc_id', 'unknown')}: {e}")
            return None
    
    def _should_include_bill(self, raw_item: Dict[str, Any]) -> bool:
        """Determine if a bill should be included in evidence processing"""
        # Check bill type
        bill_type = raw_item.get('bill_type', '').lower()
        
        # Skip private member bills unless configured to include them
        if 'private' in bill_type and not self.include_private_bills:
            return False
        
        # Check relevance threshold
        relevance_score = self._calculate_bill_relevance(raw_item)
        if relevance_score < self.min_relevance_threshold:
            return False
        
        return True
    
    def _calculate_bill_relevance(self, raw_item: Dict[str, Any]) -> float:
        """Calculate relevance score for a bill"""
        score = 0.5  # Base score
        
        title = raw_item.get('title', '').lower()
        bill_type = raw_item.get('bill_type', '').lower()
        
        # Government bills are more relevant
        if 'government' in bill_type:
            score += 0.3
        
        # Bills with policy-related keywords
        policy_keywords = [
            'act', 'amendment', 'budget', 'tax', 'healthcare', 'environment',
            'immigration', 'education', 'infrastructure', 'security'
        ]
        
        keyword_matches = sum(1 for keyword in policy_keywords if keyword in title)
        score += min(keyword_matches * 0.1, 0.3)
        
        # Recent bills are more relevant
        latest_activity = raw_item.get('latest_activity_datetime')
        if latest_activity:
            days_old = (datetime.now(timezone.utc) - latest_activity).days
            if days_old < 365:  # Within last year
                score += 0.2
        
        return min(score, 1.0)
    
    def _analyze_bill_content(self, raw_item: Dict[str, Any]) -> Dict[str, Any]:
        """Analyze bill content to extract structured information"""
        title = raw_item.get('title', '')
        short_title = raw_item.get('short_title', '')
        bill_details = raw_item.get('bill_details_json', {})
        
        # Combine text for analysis
        text_content = f"{title} {short_title}"
        
        # Extract summary from bill details if available
        summary = self._extract_bill_summary(bill_details)
        if summary:
            text_content += f" {summary}"
        
        analysis = {
            'summary': summary or self._generate_bill_summary(raw_item),
            'topics': self._extract_bill_topics(text_content),
            'policy_areas': self._extract_policy_areas(text_content),
            'departments': self._extract_affected_departments(text_content),
            'legislative_stage': self._determine_legislative_stage(raw_item),
            'urgency_level': self._assess_urgency_level(raw_item),
            'analysis_timestamp': datetime.now(timezone.utc)
        }
        
        return analysis
    
    def _extract_bill_description(self, raw_item: Dict[str, Any]) -> str:
        """Extract or generate bill description"""
        # Try short title first
        short_title = raw_item.get('short_title', '')
        if short_title:
            return short_title
        
        # Fallback to truncated title
        title = raw_item.get('title', '')
        if len(title) > 200:
            return title[:200] + "..."
        
        return title
    
    def _extract_bill_full_text(self, raw_item: Dict[str, Any]) -> str:
        """Extract full text content from bill data"""
        text_parts = []
        
        # Add title and short title
        title = raw_item.get('title', '')
        short_title = raw_item.get('short_title', '')
        
        if title:
            text_parts.append(f"Title: {title}")
        
        if short_title and short_title != title:
            text_parts.append(f"Short Title: {short_title}")
        
        # Add bill details if available
        bill_details = raw_item.get('bill_details_json', {})
        summary = self._extract_bill_summary(bill_details)
        if summary:
            text_parts.append(f"Summary: {summary}")
        
        # Add sponsor information
        sponsor = raw_item.get('sponsor_name', '')
        if sponsor:
            text_parts.append(f"Sponsor: {sponsor}")
        
        return "\n\n".join(text_parts)
    
    def _extract_bill_summary(self, bill_details: Dict[str, Any]) -> str:
        """Extract summary from bill details JSON"""
        # Look for summary in various fields
        summary_fields = ['Summary', 'summary', 'Description', 'description']
        
        for field in summary_fields:
            if field in bill_details and bill_details[field]:
                summary_data = bill_details[field]
                if isinstance(summary_data, dict):
                    # Handle nested summary structure
                    return summary_data.get('Text', summary_data.get('text', ''))
                elif isinstance(summary_data, str):
                    return summary_data
        
        return ''
    
    def _generate_bill_summary(self, raw_item: Dict[str, Any]) -> str:
        """Generate a summary for bills without explicit summaries"""
        bill_number = raw_item.get('bill_number_formatted', '')
        title = raw_item.get('title', '')
        bill_type = raw_item.get('bill_type', '')
        status = raw_item.get('status', '')
        
        return f"{bill_type} {bill_number}: {title}. Current status: {status}."
    
    def _build_bill_url(self, raw_item: Dict[str, Any]) -> str:
        """Build the URL for the bill on LEGISinfo"""
        parliament_num = raw_item.get('parliament_number')
        session_num = raw_item.get('session_number')
        bill_code = raw_item.get('bill_number_formatted', '')
        
        if all([parliament_num, session_num, bill_code]):
            return f"https://www.parl.ca/legisinfo/en/bill/{parliament_num}-{session_num}/{bill_code}"
        
        return ''
    
    def _extract_bill_topics(self, text_content: str) -> list:
        """Extract topics from bill content"""
        topic_keywords = {
            'healthcare': ['health', 'medical', 'hospital', 'medicare', 'healthcare'],
            'taxation': ['tax', 'taxation', 'revenue', 'fiscal', 'income tax'],
            'environment': ['environment', 'climate', 'carbon', 'emission', 'pollution'],
            'immigration': ['immigration', 'citizenship', 'refugee', 'visa'],
            'criminal_justice': ['criminal', 'justice', 'court', 'sentence', 'crime'],
            'employment': ['employment', 'labour', 'worker', 'workplace', 'job'],
            'transportation': ['transport', 'railway', 'aviation', 'shipping', 'highway'],
            'telecommunications': ['telecommunication', 'broadcasting', 'internet', 'radio'],
            'agriculture': ['agriculture', 'farming', 'food', 'agricultural'],
            'finance': ['financial', 'banking', 'insurance', 'securities', 'investment']
        }
        
        text_lower = text_content.lower()
        topics = []
        
        for topic, keywords in topic_keywords.items():
            if any(keyword in text_lower for keyword in keywords):
                topics.append(topic)
        
        return topics
    
    def _extract_policy_areas(self, text_content: str) -> list:
        """Extract policy areas from bill content"""
        # For bills, policy areas often align with topics
        return self._extract_bill_topics(text_content)
    
    def _extract_affected_departments(self, text_content: str) -> list:
        """Extract government departments that might be affected"""
        department_keywords = {
            'Health Canada': ['health', 'medical', 'drug', 'food safety'],
            'Transport Canada': ['transport', 'aviation', 'railway', 'marine'],
            'Environment and Climate Change Canada': ['environment', 'climate', 'pollution'],
            'Immigration, Refugees and Citizenship Canada': ['immigration', 'citizenship', 'refugee'],
            'Public Safety Canada': ['public safety', 'emergency', 'security'],
            'Employment and Social Development Canada': ['employment', 'labour', 'social'],
            'Innovation, Science and Economic Development Canada': ['innovation', 'science', 'economic development'],
            'Finance Canada': ['finance', 'tax', 'fiscal', 'budget'],
            'Justice Canada': ['justice', 'criminal', 'legal', 'court']
        }
        
        text_lower = text_content.lower()
        departments = []
        
        for dept, keywords in department_keywords.items():
            if any(keyword in text_lower for keyword in keywords):
                departments.append(dept)
        
        return departments
    
    def _determine_legislative_stage(self, raw_item: Dict[str, Any]) -> str:
        """Determine the current legislative stage of the bill"""
        status = raw_item.get('status', '').lower()
        
        if 'royal assent' in status:
            return 'royal_assent'
        elif 'third reading' in status:
            return 'third_reading'
        elif 'committee' in status:
            return 'committee_stage'
        elif 'second reading' in status:
            return 'second_reading'
        elif 'first reading' in status:
            return 'first_reading'
        elif 'introduced' in status:
            return 'introduced'
        else:
            return 'unknown'
    
    def _assess_urgency_level(self, raw_item: Dict[str, Any]) -> str:
        """Assess the urgency level of the bill"""
        # Check for urgency indicators
        title = raw_item.get('title', '').lower()
        bill_type = raw_item.get('bill_type', '').lower()
        
        # Budget bills are typically urgent
        if any(word in title for word in ['budget', 'appropriation', 'supply']):
            return 'high'
        
        # Government bills are generally more urgent than private member bills
        if 'government' in bill_type:
            return 'medium'
        
        return 'low'
    
    def _determine_parliament_session(self, raw_item: Dict[str, Any]) -> str:
        """Determine parliament session ID for the bill"""
        parliament_num = raw_item.get('parliament_number')
        session_num = raw_item.get('session_number')
        
        if parliament_num and session_num:
            return f"{parliament_num}-{session_num}"
        
        return ''
    
    def _classify_bill_type(self, raw_item: Dict[str, Any]) -> str:
        """Classify the type of legislative action"""
        bill_type = raw_item.get('bill_type', '').lower()
        title = raw_item.get('title', '').lower()
        
        if 'government' in bill_type:
            if 'budget' in title or 'appropriation' in title:
                return 'budget_bill'
            else:
                return 'government_bill'
        elif 'private' in bill_type:
            return 'private_member_bill'
        else:
            return 'legislative_bill'
    
    def _calculate_confidence_score(self, raw_item: Dict[str, Any], 
                                   bill_analysis: Dict[str, Any]) -> float:
        """Calculate confidence score for the evidence item"""
        confidence = 0.8  # Base confidence for LEGISinfo bills (official source)
        
        # Boost for government bills
        bill_type = raw_item.get('bill_type', '').lower()
        if 'government' in bill_type:
            confidence += 0.1
        
        # Boost for bills with detailed information
        if raw_item.get('bill_details_json'):
            confidence += 0.05
        
        # Boost for recent activity
        latest_activity = raw_item.get('latest_activity_datetime')
        if latest_activity:
            days_old = (datetime.now(timezone.utc) - latest_activity).days
            if days_old < 90:  # Recent activity
                confidence += 0.05
        
        return min(confidence, 1.0)
    
    def _get_evidence_id_source_type(self) -> str:
        """Get the source type identifier for evidence ID generation"""
        return 'LegisInfo'
    
    def _should_update_evidence(self, existing_evidence: Dict[str, Any], 
                               new_evidence: Dict[str, Any]) -> bool:
        """Determine if existing evidence should be updated"""
        # Update if bill status has changed
        if existing_evidence.get('status') != new_evidence.get('status'):
            return True
        
        # Update if latest activity date has changed
        existing_date = existing_evidence.get('publication_date')
        new_date = new_evidence.get('publication_date')
        if existing_date != new_date:
            return True
        
        # Update if content has changed
        content_fields = ['title_or_summary', 'description_or_details', 'full_text']
        for field in content_fields:
            if existing_evidence.get(field) != new_evidence.get(field):
                return True
        
        return False 