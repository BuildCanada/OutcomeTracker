"""
Orders in Council Processor Job

Processes raw Orders in Council into evidence items with regulatory analysis.
This replaces the existing process_oic_to_evidence.py script with a more robust,
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


class OrdersInCouncilProcessor(BaseProcessorJob):
    """
    Processing job for Orders in Council data.
    
    Transforms raw OIC data into structured evidence items
    with analysis of regulatory actions and policy implementation.
    """
    
    def __init__(self, job_name: str, config: Dict[str, Any] = None):
        """Initialize the Orders in Council processor"""
        super().__init__(job_name, config)
        
        # Processing settings
        self.min_content_length = self.config.get('min_content_length', 100)
        self.extract_appointments = self.config.get('extract_appointments', True)
    
    def _get_source_collection(self) -> str:
        """Return the Firestore collection name for raw data"""
        return "raw_orders_in_council"
    
    def _get_target_collection(self) -> str:
        """Return the Firestore collection name for evidence items"""
        return "evidence_items"
    
    def _process_raw_item(self, raw_item: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        Process a single raw OIC item into an evidence item.
        
        Args:
            raw_item: Raw OIC item from scraping
            
        Returns:
            Evidence item ready for storage or None if processing failed
        """
        try:
            # Extract basic information
            oic_number = raw_item.get('oic_number', '')
            title = raw_item.get('title', '')
            full_text = raw_item.get('full_text', '')
            
            # Basic validation
            if not oic_number and not title:
                self.logger.warning(f"OIC missing required fields: {raw_item.get('_doc_id', 'unknown')}")
                return None
            
            # Check content length
            if len(full_text) < self.min_content_length:
                self.logger.debug(f"OIC content too short, skipping: {oic_number}")
                return None
            
            # Analyze OIC content
            oic_analysis = self._analyze_oic_content(raw_item)
            
            # Create evidence item
            evidence_item = {
                # Core identification
                'title_or_summary': title or f"Order in Council {oic_number}",
                'description_or_details': self._extract_oic_description(raw_item),
                'full_text': full_text,
                'evidence_source_type': get_standardized_source_type_for_processor('orders_in_council'),
                'source_url': raw_item.get('source_url', ''),
                
                # OIC-specific fields
                'oic_number': oic_number,
                'oic_number_normalized': raw_item.get('oic_number_normalized', ''),
                'attach_id': raw_item.get('attach_id'),
                
                # Dates
                'publication_date': raw_item.get('publication_date'),
                'scraped_at': raw_item.get('scraped_at'),
                
                # Source metadata
                'source_metadata': {
                    'attach_id': raw_item.get('attach_id'),
                    'source_url': raw_item.get('source_url', '')
                },
                
                # Parliament context
                'parliament_session_id': raw_item.get('parliament_session_id_assigned'),
                
                # Processing metadata
                'evidence_type': 'regulatory_action',
                'evidence_subtype': self._classify_oic_type(raw_item, oic_analysis),
                'confidence_score': self._calculate_confidence_score(raw_item, oic_analysis),
                'processing_notes': [],
                
                # OIC analysis results
                'oic_analysis': oic_analysis,
                
                # Extracted fields
                'topics': oic_analysis.get('topics', []),
                'policy_areas': oic_analysis.get('policy_areas', []),
                'departments': oic_analysis.get('departments', []),
                'summary': oic_analysis.get('summary', ''),
                
                # Special extractions
                'appointments': oic_analysis.get('appointments', []) if self.extract_appointments else [],
                'regulatory_actions': oic_analysis.get('regulatory_actions', []),
                
                # Status tracking
                'promise_linking_status': 'pending',
                'created_at': datetime.now(timezone.utc),
                'last_updated_at': datetime.now(timezone.utc)
            }
            
            return evidence_item
            
        except Exception as e:
            self.logger.error(f"Error processing OIC {raw_item.get('_doc_id', 'unknown')}: {e}")
            return None
    
    def _analyze_oic_content(self, raw_item: Dict[str, Any]) -> Dict[str, Any]:
        """Analyze OIC content to extract structured information"""
        title = raw_item.get('title', '')
        full_text = raw_item.get('full_text', '')
        
        # Combine text for analysis
        text_content = f"{title} {full_text}"
        
        analysis = {
            'summary': self._generate_oic_summary(raw_item),
            'topics': self._extract_oic_topics(text_content),
            'policy_areas': self._extract_policy_areas(text_content),
            'departments': self._extract_mentioned_departments(text_content),
            'oic_type': self._determine_oic_type(text_content),
            'urgency_level': self._assess_urgency_level(text_content),
            'analysis_timestamp': datetime.now(timezone.utc)
        }
        
        # Extract appointments if enabled
        if self.extract_appointments:
            analysis['appointments'] = self._extract_appointments(text_content)
        
        # Extract regulatory actions
        analysis['regulatory_actions'] = self._extract_regulatory_actions(text_content)
        
        return analysis
    
    def _extract_oic_description(self, raw_item: Dict[str, Any]) -> str:
        """Extract or generate OIC description"""
        title = raw_item.get('title', '')
        oic_number = raw_item.get('oic_number', '')
        
        if title and len(title) < 200:
            return title
        elif title:
            return title[:200] + "..."
        elif oic_number:
            return f"Order in Council {oic_number}"
        else:
            return "Order in Council"
    
    def _generate_oic_summary(self, raw_item: Dict[str, Any]) -> str:
        """Generate a summary for the OIC"""
        oic_number = raw_item.get('oic_number', '')
        title = raw_item.get('title', '')
        pub_date = raw_item.get('publication_date')
        
        summary_parts = []
        
        if oic_number:
            summary_parts.append(f"Order in Council {oic_number}")
        
        if pub_date:
            date_str = pub_date.strftime("%B %d, %Y") if isinstance(pub_date, datetime) else str(pub_date)
            summary_parts.append(f"published on {date_str}")
        
        if title:
            summary_parts.append(f"regarding {title.lower()}")
        
        return ", ".join(summary_parts) + "."
    
    def _extract_oic_topics(self, text_content: str) -> list:
        """Extract topics from OIC content"""
        topic_keywords = {
            'appointments': ['appoint', 'appointment', 'designate', 'nomination'],
            'regulations': ['regulation', 'regulatory', 'rule', 'standard'],
            'funding': ['funding', 'grant', 'contribution', 'financial assistance'],
            'policy_implementation': ['implement', 'establish', 'create', 'authorize'],
            'administrative': ['administrative', 'procedure', 'process', 'operation'],
            'international': ['international', 'treaty', 'agreement', 'foreign'],
            'emergency': ['emergency', 'urgent', 'immediate', 'crisis'],
            'taxation': ['tax', 'taxation', 'duty', 'tariff', 'revenue'],
            'healthcare': ['health', 'medical', 'healthcare', 'hospital'],
            'environment': ['environment', 'environmental', 'climate', 'pollution'],
            'transportation': ['transport', 'transportation', 'railway', 'aviation'],
            'immigration': ['immigration', 'citizenship', 'refugee', 'visa'],
            'defense': ['defense', 'defence', 'military', 'armed forces', 'security']
        }
        
        text_lower = text_content.lower()
        topics = []
        
        for topic, keywords in topic_keywords.items():
            if any(keyword in text_lower for keyword in keywords):
                topics.append(topic)
        
        return topics
    
    def _extract_policy_areas(self, text_content: str) -> list:
        """Extract policy areas from OIC content"""
        # For OICs, policy areas often align with topics
        return self._extract_oic_topics(text_content)
    
    def _extract_mentioned_departments(self, text_content: str) -> list:
        """Extract government departments mentioned in the OIC"""
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
            'Crown-Indigenous Relations and Northern Affairs Canada'
        ]
        
        departments = []
        text_lower = text_content.lower()
        
        for dept in department_patterns:
            if dept.lower() in text_lower:
                departments.append(dept)
        
        return departments
    
    def _determine_oic_type(self, text_content: str) -> str:
        """Determine the type of Order in Council"""
        text_lower = text_content.lower()
        
        if any(word in text_lower for word in ['appoint', 'appointment', 'designate']):
            return 'appointment'
        elif any(word in text_lower for word in ['regulation', 'regulatory', 'rule']):
            return 'regulatory'
        elif any(word in text_lower for word in ['funding', 'grant', 'contribution']):
            return 'funding'
        elif any(word in text_lower for word in ['treaty', 'agreement', 'international']):
            return 'international'
        elif any(word in text_lower for word in ['emergency', 'urgent', 'immediate']):
            return 'emergency'
        else:
            return 'administrative'
    
    def _assess_urgency_level(self, text_content: str) -> str:
        """Assess the urgency level of the OIC"""
        text_lower = text_content.lower()
        
        if any(word in text_lower for word in ['emergency', 'urgent', 'immediate', 'crisis']):
            return 'high'
        elif any(word in text_lower for word in ['expedite', 'priority', 'important']):
            return 'medium'
        else:
            return 'low'
    
    def _extract_appointments(self, text_content: str) -> list:
        """Extract appointment information from OIC text"""
        appointments = []
        
        # Simple pattern matching for appointments
        # In practice, this would use more sophisticated NLP
        
        text_lower = text_content.lower()
        
        if 'appoint' in text_lower or 'appointment' in text_lower:
            # Look for common appointment patterns
            appointment_keywords = [
                'chief executive officer', 'ceo', 'president', 'director',
                'commissioner', 'chairperson', 'chair', 'member',
                'judge', 'justice', 'minister', 'deputy minister'
            ]
            
            for keyword in appointment_keywords:
                if keyword in text_lower:
                    appointments.append({
                        'position_type': keyword,
                        'context': 'appointment_mentioned'
                    })
        
        return appointments
    
    def _extract_regulatory_actions(self, text_content: str) -> list:
        """Extract regulatory actions from OIC text"""
        actions = []
        
        text_lower = text_content.lower()
        
        action_keywords = {
            'establish': 'establishment',
            'create': 'creation',
            'authorize': 'authorization',
            'approve': 'approval',
            'implement': 'implementation',
            'amend': 'amendment',
            'repeal': 'repeal',
            'suspend': 'suspension'
        }
        
        for keyword, action_type in action_keywords.items():
            if keyword in text_lower:
                actions.append({
                    'action_type': action_type,
                    'keyword': keyword
                })
        
        return actions
    
    def _classify_oic_type(self, raw_item: Dict[str, Any], oic_analysis: Dict[str, Any]) -> str:
        """Classify the type of regulatory action"""
        oic_type = oic_analysis.get('oic_type', 'administrative')
        
        # Map OIC types to evidence subtypes
        type_mapping = {
            'appointment': 'government_appointment',
            'regulatory': 'regulatory_implementation',
            'funding': 'funding_authorization',
            'international': 'international_agreement',
            'emergency': 'emergency_measure',
            'administrative': 'administrative_action'
        }
        
        return type_mapping.get(oic_type, 'regulatory_action')
    
    def _calculate_confidence_score(self, raw_item: Dict[str, Any], 
                                   oic_analysis: Dict[str, Any]) -> float:
        """Calculate confidence score for the evidence item"""
        confidence = 0.8  # Base confidence for OICs (official government documents)
        
        # Boost for complete OIC number
        if raw_item.get('oic_number_normalized'):
            confidence += 0.1
        
        # Boost for substantial content
        full_text = raw_item.get('full_text', '')
        if len(full_text) > 500:
            confidence += 0.05
        
        # Boost for recent publication
        pub_date = raw_item.get('publication_date')
        if pub_date:
            days_old = (datetime.now(timezone.utc) - pub_date).days
            if days_old < 180:  # Within 6 months
                confidence += 0.05
        
        return min(confidence, 1.0)
    
    def _generate_evidence_id(self, evidence_item: Dict[str, Any], 
                             raw_item: Dict[str, Any]) -> str:
        """Generate a unique ID for the evidence item"""
        # Use normalized OIC number if available
        oic_number_normalized = raw_item.get('oic_number_normalized', '')
        if oic_number_normalized:
            return f"oic_{oic_number_normalized}".replace('-', '_')
        
        # Use attach_id as fallback
        attach_id = raw_item.get('attach_id')
        if attach_id:
            return f"oic_attach_{attach_id}"
        
        # Final fallback to source document ID
        return f"oic_{raw_item.get('_doc_id', 'unknown')}"
    
    def _should_update_evidence(self, existing_evidence: Dict[str, Any], 
                               new_evidence: Dict[str, Any]) -> bool:
        """Determine if existing evidence should be updated"""
        # Update if content has changed
        content_fields = ['title_or_summary', 'full_text']
        for field in content_fields:
            if existing_evidence.get(field) != new_evidence.get(field):
                return True
        
        # Update if analysis has improved
        existing_analysis = existing_evidence.get('oic_analysis', {})
        new_analysis = new_evidence.get('oic_analysis', {})
        
        # Check if new analysis has more extracted information
        for field in ['appointments', 'regulatory_actions', 'departments']:
            existing_count = len(existing_analysis.get(field, []))
            new_count = len(new_analysis.get(field, []))
            if new_count > existing_count:
                return True
        
        return False
    
    def _get_evidence_id_source_type(self) -> str:
        """Get the source type identifier for evidence ID generation"""
        return 'OrdersInCouncil' 