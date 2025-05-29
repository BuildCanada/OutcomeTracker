"""
Canada Gazette Processor Job

Processes raw Canada Gazette notices into evidence items with regulatory analysis.
This replaces the existing process_gazette_p2_to_evidence.py script with a more robust,
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
except ImportError:
    # Add pipeline directory to path for testing
    pipeline_dir = Path(__file__).parent.parent.parent
    sys.path.insert(0, str(pipeline_dir))
    from stages.processing.base_processor import BaseProcessorJob


class CanadaGazetteProcessor(BaseProcessorJob):
    """
    Processing job for Canada Gazette Part II notices.
    
    Transforms raw gazette regulation notices into structured evidence items
    with analysis of regulatory changes and policy implementation.
    """
    
    def __init__(self, job_name: str, config: Dict[str, Any] = None):
        """Initialize the Canada Gazette processor"""
        super().__init__(job_name, config)
        
        # Processing settings
        self.min_content_length = self.config.get('min_content_length', 50)
        self.extract_regulatory_details = self.config.get('extract_regulatory_details', True)
    
    def _get_source_collection(self) -> str:
        """Return the Firestore collection name for raw data"""
        return "raw_gazette_p2_notices"
    
    def _get_target_collection(self) -> str:
        """Return the Firestore collection name for evidence items"""
        return "evidence_items"
    
    def _process_raw_item(self, raw_item: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        Process a single raw gazette notice into an evidence item.
        
        Args:
            raw_item: Raw gazette notice from scraping
            
        Returns:
            Evidence item ready for storage or None if processing failed
        """
        try:
            # Extract basic information
            regulation_title = raw_item.get('regulation_title', '')
            regulation_number = raw_item.get('regulation_number', '')
            full_text = raw_item.get('full_text', '')
            
            # Basic validation
            if not regulation_title and not regulation_number:
                self.logger.warning(f"Gazette notice missing required fields: {raw_item.get('_doc_id', 'unknown')}")
                return None
            
            # Check content length
            if len(regulation_title) < self.min_content_length and len(full_text) < self.min_content_length:
                self.logger.debug(f"Gazette notice content too short, skipping: {regulation_number}")
                return None
            
            # Analyze gazette content
            gazette_analysis = self._analyze_gazette_content(raw_item)
            
            # Create evidence item
            evidence_item = {
                # Core identification
                'title': regulation_title or f"Regulation {regulation_number}",
                'description': self._extract_gazette_description(raw_item),
                'full_text': full_text,
                'source_type': 'canada_gazette',
                'source_url': raw_item.get('regulation_url', ''),
                
                # Gazette-specific fields
                'regulation_title': regulation_title,
                'regulation_number': regulation_number,
                'regulation_url': raw_item.get('regulation_url', ''),
                'regulation_date': raw_item.get('regulation_date'),
                
                # Issue metadata
                'issue_title': raw_item.get('issue_title', ''),
                'issue_url': raw_item.get('issue_url', ''),
                'issue_publication_date': raw_item.get('issue_publication_date'),
                'issue_guid': raw_item.get('issue_guid', ''),
                
                # Dates
                'publication_date': raw_item.get('regulation_date') or raw_item.get('issue_publication_date'),
                'scraped_at': raw_item.get('scraped_at'),
                
                # Source metadata
                'source_metadata': {
                    'regulation_url': raw_item.get('regulation_url', ''),
                    'issue_title': raw_item.get('issue_title', ''),
                    'issue_url': raw_item.get('issue_url', ''),
                    'issue_guid': raw_item.get('issue_guid', '')
                },
                
                # Parliament context
                'parliament_session_id': raw_item.get('parliament_session_id_assigned'),
                
                # Processing metadata
                'evidence_type': 'regulatory_publication',
                'evidence_subtype': self._classify_regulation_type(raw_item, gazette_analysis),
                'confidence_score': self._calculate_confidence_score(raw_item, gazette_analysis),
                'processing_notes': [],
                
                # Gazette analysis results
                'gazette_analysis': gazette_analysis,
                
                # Extracted fields
                'topics': gazette_analysis.get('topics', []),
                'policy_areas': gazette_analysis.get('policy_areas', []),
                'departments': gazette_analysis.get('departments', []),
                'summary': gazette_analysis.get('summary', ''),
                
                # Regulatory details
                'regulatory_details': gazette_analysis.get('regulatory_details', {}) if self.extract_regulatory_details else {},
                
                # Status tracking
                'linking_status': 'pending',
                'created_at': datetime.now(timezone.utc),
                'last_updated_at': datetime.now(timezone.utc)
            }
            
            return evidence_item
            
        except Exception as e:
            self.logger.error(f"Error processing gazette notice {raw_item.get('_doc_id', 'unknown')}: {e}")
            return None
    
    def _analyze_gazette_content(self, raw_item: Dict[str, Any]) -> Dict[str, Any]:
        """Analyze gazette content to extract structured information"""
        regulation_title = raw_item.get('regulation_title', '')
        full_text = raw_item.get('full_text', '')
        regulation_number = raw_item.get('regulation_number', '')
        
        # Combine text for analysis
        text_content = f"{regulation_title} {full_text}"
        
        analysis = {
            'summary': self._generate_gazette_summary(raw_item),
            'topics': self._extract_gazette_topics(text_content),
            'policy_areas': self._extract_policy_areas(text_content),
            'departments': self._extract_mentioned_departments(text_content),
            'regulation_type': self._determine_regulation_type(regulation_number, text_content),
            'urgency_level': self._assess_urgency_level(text_content),
            'analysis_timestamp': datetime.now(timezone.utc)
        }
        
        # Extract regulatory details if enabled
        if self.extract_regulatory_details:
            analysis['regulatory_details'] = self._extract_regulatory_details(raw_item, text_content)
        
        return analysis
    
    def _extract_gazette_description(self, raw_item: Dict[str, Any]) -> str:
        """Extract or generate gazette notice description"""
        regulation_title = raw_item.get('regulation_title', '')
        regulation_number = raw_item.get('regulation_number', '')
        
        if regulation_title and len(regulation_title) < 200:
            return regulation_title
        elif regulation_title:
            return regulation_title[:200] + "..."
        elif regulation_number:
            return f"Regulation {regulation_number}"
        else:
            return "Canada Gazette Part II Notice"
    
    def _generate_gazette_summary(self, raw_item: Dict[str, Any]) -> str:
        """Generate a summary for the gazette notice"""
        regulation_number = raw_item.get('regulation_number', '')
        regulation_title = raw_item.get('regulation_title', '')
        reg_date = raw_item.get('regulation_date') or raw_item.get('issue_publication_date')
        
        summary_parts = []
        
        if regulation_number:
            summary_parts.append(f"Regulation {regulation_number}")
        
        if reg_date:
            date_str = reg_date.strftime("%B %d, %Y") if isinstance(reg_date, datetime) else str(reg_date)
            summary_parts.append(f"published on {date_str}")
        
        if regulation_title:
            summary_parts.append(f"regarding {regulation_title.lower()}")
        
        return ", ".join(summary_parts) + "."
    
    def _extract_gazette_topics(self, text_content: str) -> list:
        """Extract topics from gazette content"""
        topic_keywords = {
            'environmental_regulations': ['environment', 'environmental', 'pollution', 'emission', 'waste'],
            'food_safety': ['food', 'safety', 'inspection', 'contamination', 'pesticide'],
            'transportation_safety': ['transport', 'transportation', 'safety', 'vehicle', 'aviation', 'marine'],
            'health_regulations': ['health', 'medical', 'drug', 'pharmaceutical', 'device'],
            'financial_regulations': ['financial', 'banking', 'insurance', 'securities', 'investment'],
            'telecommunications': ['telecommunication', 'broadcasting', 'radio', 'television', 'spectrum'],
            'immigration_regulations': ['immigration', 'visa', 'refugee', 'citizenship'],
            'employment_standards': ['employment', 'labour', 'workplace', 'worker', 'safety'],
            'tax_regulations': ['tax', 'taxation', 'duty', 'tariff', 'customs'],
            'energy_regulations': ['energy', 'electricity', 'gas', 'pipeline', 'nuclear'],
            'agricultural_regulations': ['agriculture', 'farming', 'livestock', 'crop', 'fertilizer'],
            'consumer_protection': ['consumer', 'protection', 'product', 'recall', 'safety']
        }
        
        text_lower = text_content.lower()
        topics = []
        
        for topic, keywords in topic_keywords.items():
            if any(keyword in text_lower for keyword in keywords):
                topics.append(topic)
        
        return topics
    
    def _extract_policy_areas(self, text_content: str) -> list:
        """Extract policy areas from gazette content"""
        # For gazette notices, policy areas often align with topics
        return self._extract_gazette_topics(text_content)
    
    def _extract_mentioned_departments(self, text_content: str) -> list:
        """Extract government departments mentioned in the gazette notice"""
        department_patterns = [
            'Health Canada',
            'Transport Canada',
            'Environment and Climate Change Canada',
            'Immigration, Refugees and Citizenship Canada',
            'Public Safety Canada',
            'Global Affairs Canada',
            'Innovation, Science and Economic Development Canada',
            'Finance Canada',
            'Justice Canada',
            'Employment and Social Development Canada',
            'Natural Resources Canada',
            'Agriculture and Agri-Food Canada',
            'Fisheries and Oceans Canada',
            'Canadian Heritage',
            'Indigenous Services Canada',
            'Crown-Indigenous Relations and Northern Affairs Canada',
            'Canadian Food Inspection Agency',
            'Canada Revenue Agency',
            'Canadian Nuclear Safety Commission'
        ]
        
        departments = []
        text_lower = text_content.lower()
        
        for dept in department_patterns:
            if dept.lower() in text_lower:
                departments.append(dept)
        
        return departments
    
    def _determine_regulation_type(self, regulation_number: str, text_content: str) -> str:
        """Determine the type of regulation based on number and content"""
        if not regulation_number:
            return 'unknown'
        
        reg_number_upper = regulation_number.upper()
        text_lower = text_content.lower()
        
        # Statutory Orders and Regulations
        if reg_number_upper.startswith('SOR/'):
            return 'statutory_order_regulation'
        
        # Statutory Instruments
        elif reg_number_upper.startswith('SI/'):
            return 'statutory_instrument'
        
        # Orders in Council (sometimes appear in Gazette)
        elif 'P.C.' in reg_number_upper or 'order in council' in text_lower:
            return 'order_in_council'
        
        # Determine by content
        elif any(word in text_lower for word in ['regulation', 'regulatory']):
            return 'regulation'
        elif any(word in text_lower for word in ['order', 'directive']):
            return 'order'
        else:
            return 'notice'
    
    def _assess_urgency_level(self, text_content: str) -> str:
        """Assess the urgency level of the regulation"""
        text_lower = text_content.lower()
        
        if any(word in text_lower for word in ['emergency', 'urgent', 'immediate', 'interim']):
            return 'high'
        elif any(word in text_lower for word in ['expedited', 'priority', 'important']):
            return 'medium'
        else:
            return 'low'
    
    def _extract_regulatory_details(self, raw_item: Dict[str, Any], text_content: str) -> Dict[str, Any]:
        """Extract detailed regulatory information"""
        details = {}
        
        # Extract effective date
        effective_date = self._extract_effective_date(text_content)
        if effective_date:
            details['effective_date'] = effective_date
        
        # Extract regulatory authority
        authority = self._extract_regulatory_authority(text_content)
        if authority:
            details['regulatory_authority'] = authority
        
        # Extract affected acts/regulations
        affected_acts = self._extract_affected_acts(text_content)
        if affected_acts:
            details['affected_acts'] = affected_acts
        
        # Extract amendment type
        amendment_type = self._determine_amendment_type(text_content)
        if amendment_type:
            details['amendment_type'] = amendment_type
        
        return details
    
    def _extract_effective_date(self, text_content: str) -> Optional[str]:
        """Extract effective date from regulation text"""
        # Look for common effective date patterns
        date_patterns = [
            r'effective\s+(?:on\s+)?(\w+\s+\d{1,2},\s+\d{4})',
            r'comes?\s+into\s+force\s+(?:on\s+)?(\w+\s+\d{1,2},\s+\d{4})',
            r'in\s+force\s+(?:on\s+)?(\w+\s+\d{1,2},\s+\d{4})'
        ]
        
        for pattern in date_patterns:
            match = re.search(pattern, text_content, re.IGNORECASE)
            if match:
                return match.group(1)
        
        return None
    
    def _extract_regulatory_authority(self, text_content: str) -> Optional[str]:
        """Extract the regulatory authority from text"""
        # Look for common authority patterns
        authority_patterns = [
            'minister of',
            'governor in council',
            'canadian food inspection agency',
            'canada revenue agency'
        ]
        
        text_lower = text_content.lower()
        
        for pattern in authority_patterns:
            if pattern in text_lower:
                return pattern.title()
        
        return None
    
    def _extract_affected_acts(self, text_content: str) -> list:
        """Extract acts or regulations that are being amended"""
        # Look for act references
        act_pattern = r'([A-Z][a-zA-Z\s]+Act)'
        matches = re.findall(act_pattern, text_content)
        
        acts = []
        for match in matches:
            if len(match.strip()) > 5:  # Filter out very short matches
                acts.append(match.strip())
        
        # Remove duplicates and return
        return list(set(acts))
    
    def _determine_amendment_type(self, text_content: str) -> Optional[str]:
        """Determine the type of amendment being made"""
        text_lower = text_content.lower()
        
        if any(word in text_lower for word in ['amend', 'amendment', 'amending']):
            return 'amendment'
        elif any(word in text_lower for word in ['repeal', 'repealing']):
            return 'repeal'
        elif any(word in text_lower for word in ['enact', 'enacting', 'establish']):
            return 'enactment'
        elif any(word in text_lower for word in ['revoke', 'revoking']):
            return 'revocation'
        else:
            return None
    
    def _classify_regulation_type(self, raw_item: Dict[str, Any], gazette_analysis: Dict[str, Any]) -> str:
        """Classify the type of regulatory publication"""
        regulation_type = gazette_analysis.get('regulation_type', 'notice')
        
        # Map regulation types to evidence subtypes
        type_mapping = {
            'statutory_order_regulation': 'statutory_regulation',
            'statutory_instrument': 'statutory_instrument',
            'order_in_council': 'order_in_council',
            'regulation': 'regulation',
            'order': 'regulatory_order',
            'notice': 'regulatory_notice'
        }
        
        return type_mapping.get(regulation_type, 'regulatory_publication')
    
    def _calculate_confidence_score(self, raw_item: Dict[str, Any], 
                                   gazette_analysis: Dict[str, Any]) -> float:
        """Calculate confidence score for the evidence item"""
        confidence = 0.85  # Base confidence for Canada Gazette (official publication)
        
        # Boost for complete regulation number
        if raw_item.get('regulation_number'):
            confidence += 0.1
        
        # Boost for substantial content
        full_text = raw_item.get('full_text', '')
        if len(full_text) > 300:
            confidence += 0.05
        
        # Boost for recent publication
        pub_date = raw_item.get('regulation_date') or raw_item.get('issue_publication_date')
        if pub_date:
            days_old = (datetime.now(timezone.utc) - pub_date).days
            if days_old < 90:  # Within 3 months
                confidence += 0.05
        
        return min(confidence, 1.0)
    
    def _generate_evidence_id(self, evidence_item: Dict[str, Any], 
                             raw_item: Dict[str, Any]) -> str:
        """Generate a unique ID for the evidence item"""
        # Use regulation number if available
        regulation_number = raw_item.get('regulation_number', '')
        if regulation_number:
            # Clean regulation number for use as document ID
            clean_number = re.sub(r'[^a-zA-Z0-9_-]', '_', regulation_number)
            return f"gazette_{clean_number}"
        
        # Use issue GUID + regulation title hash as fallback
        issue_guid = raw_item.get('issue_guid', '')
        regulation_title = raw_item.get('regulation_title', '')
        
        if issue_guid and regulation_title:
            import hashlib
            title_hash = hashlib.sha256(regulation_title.encode()).hexdigest()[:8]
            clean_guid = re.sub(r'[^a-zA-Z0-9_-]', '_', issue_guid)
            return f"gazette_{clean_guid}_{title_hash}"
        
        # Final fallback to source document ID
        return f"gazette_{raw_item.get('_doc_id', 'unknown')}"
    
    def _should_update_evidence(self, existing_evidence: Dict[str, Any], 
                               new_evidence: Dict[str, Any]) -> bool:
        """Determine if existing evidence should be updated"""
        # Update if content has changed
        content_fields = ['regulation_title', 'full_text']
        for field in content_fields:
            if existing_evidence.get(field) != new_evidence.get(field):
                return True
        
        # Update if regulatory details have been enhanced
        existing_details = existing_evidence.get('regulatory_details', {})
        new_details = new_evidence.get('regulatory_details', {})
        
        # Check if new analysis has more regulatory details
        if len(new_details) > len(existing_details):
            return True
        
        # Update if analysis has improved
        existing_analysis = existing_evidence.get('gazette_analysis', {})
        new_analysis = new_evidence.get('gazette_analysis', {})
        
        for field in ['departments', 'topics']:
            existing_count = len(existing_analysis.get(field, []))
            new_count = len(new_analysis.get(field, []))
            if new_count > existing_count:
                return True
        
        return False 