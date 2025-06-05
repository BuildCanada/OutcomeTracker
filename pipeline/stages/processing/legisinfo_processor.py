"""
LEGISinfo Processor Job

Processes raw bill data into evidence items with legislative analysis.
This replaces the existing process_legisinfo_to_evidence.py script with a more robust,
class-based implementation.
"""

import logging
import sys
import re
import json
from datetime import datetime, timezone
from typing import Dict, Any, Optional, List
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

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
        # Set config first so we can access overrides before super().__init__()
        self.config = config or {}
        
        # Allow test collection override
        self._source_collection_override = self.config.get('source_collection')
        self._target_collection_override = self.config.get('target_collection')
        
        super().__init__(job_name, config)
        
        # Processing settings
        self.include_private_bills = self.config.get('include_private_bills', False)
        self.min_relevance_threshold = self.config.get('min_relevance_threshold', 0.3)
        
        # Lazy initialization for langchain
        self._langchain_instance = None
    
    @property
    def langchain_instance(self):
        """Lazy initialization of langchain instance"""
        if self._langchain_instance is None:
            try:
                # Lazy import to avoid circular dependencies
                try:
                    from ...lib.langchain_config import get_langchain_instance
                except ImportError:
                    from lib.langchain_config import get_langchain_instance
                
                self._langchain_instance = get_langchain_instance()
                if not self._langchain_instance:
                    self.logger.error("Could not get langchain instance")
            except Exception as e:
                self.logger.error(f"Error initializing langchain: {e}")
                self._langchain_instance = None
        return self._langchain_instance
    
    def _get_source_collection(self) -> str:
        """Return the Firestore collection name for raw data"""
        return self._source_collection_override or "raw_legisinfo_bill_details"
    
    def _get_target_collection(self) -> str:
        """Return the Firestore collection name for evidence items"""
        return self._target_collection_override or "evidence_items"
    
    def _get_items_to_process(self) -> List[Dict[str, Any]]:
        """Get raw LegisInfo items that need processing using the correct field name"""
        try:
            # LegisInfo uses 'processing_status' field instead of 'evidence_processing_status'
            query = (self.db.collection(self.source_collection)
                    .where(filter=firestore.FieldFilter('processing_status', '==', 'pending_processing'))
                    .order_by('last_updated_at')
                    .limit(self.max_items_per_run * 2))  # Get extra to account for filtering
            
            items = []
            for doc in query.stream():
                item_data = doc.to_dict()
                item_data['_doc_id'] = doc.id
                items.append(item_data)
            
            self.logger.info(f"Found {len(items)} LegisInfo items with pending processing status")
            return items
            
        except Exception as e:
            self.logger.error(f"Error querying LegisInfo items to process: {e}")
            return []
    
    def _process_raw_item(self, raw_item: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        Process a single raw bill item from Parliament 44 format into an evidence item.
        
        Args:
            raw_item: Raw bill item with raw_json_content string
            
        Returns:
            Evidence item ready for storage or None if processing failed
        """
        try:
            # Parse the raw JSON content string (Parliament 44 format)
            raw_json_content = raw_item.get('raw_json_content', '[]')
            if isinstance(raw_json_content, str):
                bill_data_list = json.loads(raw_json_content)
            else:
                bill_data_list = raw_json_content
            
            # Extract the bill data (should be first item in list)
            if not bill_data_list or len(bill_data_list) == 0:
                self.logger.warning(f"Empty bill data for {raw_item.get('bill_number_code_feed', 'unknown')}")
                self._update_processing_status(raw_item, 'error_processing_script')
                return None
            
            bill_data = bill_data_list[0]
            
            # Extract basic information
            bill_number = raw_item.get('bill_number_code_feed', '')
            long_title_en = bill_data.get('LongTitleEn', '')
            
            if not bill_number or not long_title_en:
                self.logger.warning(f"Bill missing required fields: {raw_item.get('bill_number_code_feed', 'unknown')}")
                self._update_processing_status(raw_item, 'error_processing_script')
                return None
            
            # Check if we should include this bill
            if not self._should_include_bill_parliament44(raw_item, bill_data):
                self._update_processing_status(raw_item, 'skipped_not_relevant')
                return None
            
            # Extract and analyze bill content
            bill_analysis = self._analyze_bill_content_parliament44(raw_item, bill_data)
            
            # Create evidence item in Parliament 44 format
            evidence_item = self._create_parliament44_evidence_item(raw_item, bill_data, bill_analysis)
            
            # Update processing status to indicate successful processing
            self._update_processing_status(raw_item, 'processed')
            
            return evidence_item
            
        except Exception as e:
            self.logger.error(f"Error processing bill {raw_item.get('bill_number_code_feed', 'unknown')}: {e}")
            self._update_processing_status(raw_item, 'error_processing_script')
            return None
    
    def _should_include_bill(self, raw_item: Dict[str, Any]) -> bool:
        """Determine if a bill should be included in evidence processing"""
        # Check bill type using new field name
        bill_type = raw_item.get('bill_document_type_name', '').lower()
        
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
        
        # Use new field names
        title = raw_item.get('long_title_en', '').lower()
        bill_type = raw_item.get('bill_document_type_name', '').lower()
        
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
        """Analyze bill content using LLM to extract structured information"""
        try:
            # Load the prompt template
            prompt_template = self._load_prompt_template()
            if not prompt_template:
                self.logger.error("Could not load prompt template")
                return self._get_fallback_analysis(raw_item)
            
            # Build the prompt with correct field mapping
            prompt_text = self._build_bill_prompt(raw_item, prompt_template)
            
            # Call LLM for analysis
            llm_response = self._call_llm_for_analysis(prompt_text)
            
            if llm_response:
                # Parse LLM response and add extracted content
                analysis = self._parse_llm_response(llm_response)
                
                # Add fallback topics and policy areas
                text_content = f"{raw_item.get('long_title_en', '')} {raw_item.get('short_title_en', '')}"
                analysis['topics'] = self._extract_bill_topics(text_content)
                analysis['policy_areas'] = self._extract_policy_areas(text_content)
                analysis['departments'] = self._extract_affected_departments(text_content)
                
                return analysis
            else:
                self.logger.warning(f"LLM analysis failed for bill {raw_item.get('human_readable_id', 'unknown')}")
                return self._get_fallback_analysis(raw_item)
            
        except Exception as e:
            self.logger.error(f"Error in bill content analysis: {e}")
            return self._get_fallback_analysis(raw_item)
    
    def _load_prompt_template(self) -> Optional[str]:
        """Load the prompt template for bill analysis"""
        try:
            prompt_file = Path("/Users/tscheidt/promise-tracker/PromiseTracker/prompts/prompt_bill_evidence.md")
            with open(prompt_file, 'r', encoding='utf-8') as f:
                return f.read()
        except Exception as e:
            self.logger.error(f"Error loading prompt template: {e}")
            return None
    
    def _build_bill_prompt(self, raw_item: Dict[str, Any], prompt_template: str) -> str:
        """Build the LLM prompt with bill data"""
        # Map the fields to match the prompt template expectations
        return prompt_template.format(
            bill_long_title_en=raw_item.get('long_title_en', ''),
            bill_short_title_en=raw_item.get('short_title_en', ''),
            short_legislative_summary_en_cleaned=raw_item.get('short_legislative_summary_en_cleaned', ''),
            sponsor_affiliation_title_en=raw_item.get('sponsor_affiliation_title_en', ''),
            sponsor_person_name=raw_item.get('sponsor_person_name', ''),
            parliament_session_id=raw_item.get('parliament_session_id', '')
        )
    
    def _call_llm_for_analysis(self, prompt_text: str) -> Optional[Dict[str, Any]]:
        """Call LLM for bill analysis"""
        try:
            # Generate content using the LLM from the langchain instance
            response = self.langchain_instance.llm.invoke(prompt_text)
            
            if response and hasattr(response, 'content'):
                # Clean and parse JSON response
                json_str = self._clean_json_from_markdown(response.content)
                return json.loads(json_str)
            else:
                self.logger.error("Empty or invalid response from LLM")
                return None
            
        except Exception as e:
            self.logger.error(f"Error calling LLM: {e}")
            return None
    
    def _clean_json_from_markdown(self, text_blob: str) -> str:
        """Clean JSON from markdown code blocks"""
        regex_pattern = r"```(?:json)?\s*([\s\S]+?)\s*```"
        match = re.search(regex_pattern, text_blob)
        if match:
            return match.group(1).strip()
        return text_blob.strip()
    
    def _parse_llm_response(self, llm_response: Dict[str, Any]) -> Dict[str, Any]:
        """Parse LLM response into structured analysis"""
        return {
            'summary': llm_response.get('timeline_summary_llm', ''),
            'description': llm_response.get('one_sentence_description_llm', ''),
            'key_concepts': llm_response.get('key_concepts_llm', []),
            'sponsoring_department': llm_response.get('sponsoring_department_standardized_llm', ''),
            'llm_analysis': llm_response  # Store full LLM response
        }
    
    def _get_fallback_analysis(self, raw_item: Dict[str, Any]) -> Dict[str, Any]:
        """Get fallback analysis when LLM fails"""
        title = raw_item.get('long_title_en', raw_item.get('title', ''))
        bill_number = raw_item.get('bill_number_formatted', '')
        
        return {
            'summary': f"Bill {bill_number}: {title[:50]}..." if len(title) > 50 else f"Bill {bill_number}: {title}",
            'description': title,
            'key_concepts': [],
            'sponsoring_department': '',
            'topics': self._extract_bill_topics(title),
            'policy_areas': self._extract_policy_areas(title),
            'departments': []
        }
    
    def _extract_bill_description(self, raw_item: Dict[str, Any]) -> str:
        """Extract bill description from raw item data"""
        # Build description from available fields using new field names
        description_parts = []
        
        # Use long title as primary description
        long_title = raw_item.get('long_title_en', '')
        if long_title:
            description_parts.append(long_title)
        
        # Add short title if different
        short_title = raw_item.get('short_title_en', '')
        if short_title and short_title != long_title:
            description_parts.append(f"Short title: {short_title}")
        
        # Add legislative summary if available
        summary = raw_item.get('short_legislative_summary_en_cleaned', '')
        if summary:
            description_parts.append(f"Summary: {summary}")
        
        # Add bill type and status
        bill_type = raw_item.get('bill_document_type_name', '')
        if bill_type:
            description_parts.append(f"Type: {bill_type}")
        
        status = raw_item.get('status_name_en', '')
        if status:
            description_parts.append(f"Status: {status}")
        
        # Add sponsor if available
        sponsor = raw_item.get('sponsor_person_name', '')
        if sponsor:
            description_parts.append(f"Sponsor: {sponsor}")
        
        return "\n\n".join(description_parts)
    
    def _extract_bill_full_text(self, raw_item: Dict[str, Any]) -> str:
        """Extract full text content from bill data"""
        # Combine various text fields for full text using new field names
        text_parts = []
        
        # Long title
        long_title = raw_item.get('long_title_en', '')
        if long_title:
            text_parts.append(f"Long Title: {long_title}")
        
        # Short title
        short_title = raw_item.get('short_title_en', '')
        if short_title:
            text_parts.append(f"Short Title: {short_title}")
        
        # Legislative summary
        summary = raw_item.get('short_legislative_summary_en_cleaned', '')
        if summary:
            text_parts.append(f"Legislative Summary: {summary}")
        
        # Bill details from JSON if available
        bill_details = raw_item.get('bill_details_json', {})
        if bill_details:
            # Add any additional text from bill details
            notes = bill_details.get('NotesEn', '')
            if notes:
                text_parts.append(f"Notes: {notes}")
        
        # Parliament and session info
        parliament_session = raw_item.get('parliament_session_id', '')
        if parliament_session:
            text_parts.append(f"Parliament Session: {parliament_session}")
        
        # Bill type and status
        bill_type = raw_item.get('bill_document_type_name', '')
        if bill_type:
            text_parts.append(f"Bill Type: {bill_type}")
        
        status = raw_item.get('status_name_en', '')
        if status:
            text_parts.append(f"Current Status: {status}")
        
        # Sponsor info
        sponsor = raw_item.get('sponsor_person_name', '')
        if sponsor:
            text_parts.append(f"Sponsor: {sponsor}")
        
        return "\n\n".join(text_parts)
    
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
        # Use new field names
        bill_type = raw_item.get('bill_document_type_name', '').lower()
        title = raw_item.get('long_title_en', '').lower()
        
        if 'government' in bill_type:
            if 'budget' in title or 'appropriation' in title:
                return 'budget_bill'
            else:
                return 'government_bill'
        elif 'private' in bill_type:
            return 'private_member_bill'
        else:
            return 'legislative_bill'
    
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
    
    def _should_include_bill_parliament44(self, raw_item: Dict[str, Any], bill_data: Dict[str, Any]) -> bool:
        """Determine if a Parliament 44 bill should be included in evidence processing"""
        # Check bill type
        bill_type = bill_data.get('BillDocumentTypeName', '').lower()
        
        # Skip private member bills unless configured to include them
        if 'private' in bill_type and not self.include_private_bills:
            return False
        
        # Check relevance threshold
        relevance_score = self._calculate_bill_relevance_parliament44(raw_item, bill_data)
        if relevance_score < self.min_relevance_threshold:
            return False
        
        return True
    
    def _calculate_bill_relevance_parliament44(self, raw_item: Dict[str, Any], bill_data: Dict[str, Any]) -> float:
        """Calculate relevance score for a Parliament 44 bill"""
        score = 0.5  # Base score
        
        title = bill_data.get('LongTitleEn', '').lower()
        bill_type = bill_data.get('BillDocumentTypeName', '').lower()
        
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
        latest_activity = raw_item.get('ingested_at')  # Updated field name
        if latest_activity:
            days_old = (datetime.now(timezone.utc) - latest_activity).days
            if days_old < 365:  # Within last year
                score += 0.2
        
        return min(score, 1.0)
    
    def _analyze_bill_content_parliament44(self, raw_item: Dict[str, Any], bill_data: Dict[str, Any]) -> Dict[str, Any]:
        """Analyze Parliament 44 bill content using LLM to extract structured information"""
        try:
            # Load the prompt template
            prompt_template = self._load_prompt_template()
            if not prompt_template:
                self.logger.error("Could not load prompt template")
                return self._get_fallback_analysis_parliament44(raw_item, bill_data)
            
            # Build the prompt with Parliament 44 data
            prompt_text = self._build_bill_prompt_parliament44(raw_item, bill_data, prompt_template)
            
            # Call LLM for analysis
            llm_response = self._call_llm_for_analysis(prompt_text)
            
            if llm_response:
                # Parse LLM response and add extracted content
                analysis = self._parse_llm_response(llm_response)
                
                # Add fallback topics and policy areas
                text_content = f"{bill_data.get('LongTitleEn', '')} {bill_data.get('ShortTitleEn', '')}"
                analysis['topics'] = self._extract_bill_topics(text_content)
                analysis['policy_areas'] = self._extract_policy_areas(text_content)
                analysis['departments'] = self._extract_affected_departments(text_content)
                
                return analysis
            else:
                self.logger.warning(f"LLM analysis failed for bill {raw_item.get('bill_number_code_feed', 'unknown')}")
                return self._get_fallback_analysis_parliament44(raw_item, bill_data)
            
        except Exception as e:
            self.logger.error(f"Error in bill content analysis: {e}")
            return self._get_fallback_analysis_parliament44(raw_item, bill_data)
    
    def _build_bill_prompt_parliament44(self, raw_item: Dict[str, Any], bill_data: Dict[str, Any], prompt_template: str) -> str:
        """Build the LLM prompt with Parliament 44 bill data"""
        # Clean legislative summary from HTML
        summary_html = bill_data.get('ShortLegislativeSummaryEn', '')
        short_legislative_summary_cleaned = self._clean_html_text(summary_html) if summary_html else ''
        
        # Map the fields to match the prompt template expectations
        return prompt_template.format(
            bill_long_title_en=bill_data.get('LongTitleEn', ''),
            bill_short_title_en=bill_data.get('ShortTitleEn', ''),
            short_legislative_summary_en_cleaned=short_legislative_summary_cleaned,
            sponsor_affiliation_title_en=bill_data.get('SponsorAffiliationTitleEn', ''),
            sponsor_person_name=bill_data.get('SponsorPersonName', ''),
            parliament_session_id=raw_item.get('parliament_session_id', '')
        )
    
    def _get_fallback_analysis_parliament44(self, raw_item: Dict[str, Any], bill_data: Dict[str, Any]) -> Dict[str, Any]:
        """Get fallback analysis when LLM fails for Parliament 44 bills"""
        title = bill_data.get('LongTitleEn', '')
        bill_number = raw_item.get('bill_number_code_feed', '')
        
        return {
            'summary': f"Bill {bill_number}: {title[:50]}..." if len(title) > 50 else f"Bill {bill_number}: {title}",
            'description': title,
            'key_concepts': [],
            'sponsoring_department': '',
            'topics': self._extract_bill_topics(title),
            'policy_areas': self._extract_policy_areas(title),
            'departments': []
        }
    
    def _extract_bill_description_parliament44(self, raw_item: Dict[str, Any], bill_data: Dict[str, Any]) -> str:
        """Extract bill description from Parliament 44 data"""
        description_parts = []
        
        # Use long title as primary description
        long_title = bill_data.get('LongTitleEn', '')
        if long_title:
            description_parts.append(long_title)
        
        # Add short title if different
        short_title = bill_data.get('ShortTitleEn', '')
        if short_title and short_title != long_title:
            description_parts.append(f"Short title: {short_title}")
        
        # Add legislative summary if available
        summary = bill_data.get('ShortLegislativeSummaryEn', '')
        if summary:
            cleaned_summary = self._clean_html_text(summary)
            if cleaned_summary:
                description_parts.append(f"Summary: {cleaned_summary}")
        
        # Add bill type and status
        bill_type = bill_data.get('BillDocumentTypeName', '')
        if bill_type:
            description_parts.append(f"Type: {bill_type}")
        
        status = bill_data.get('StatusNameEn', '')
        if status:
            description_parts.append(f"Status: {status}")
        
        # Add sponsor if available
        sponsor = bill_data.get('SponsorPersonName', '')
        if sponsor:
            description_parts.append(f"Sponsor: {sponsor}")
        
        return "\n\n".join(description_parts)
    
    def _extract_bill_full_text_parliament44(self, raw_item: Dict[str, Any], bill_data: Dict[str, Any]) -> str:
        """Extract full text content from Parliament 44 bill data"""
        text_parts = []
        
        # Long title
        long_title = bill_data.get('LongTitleEn', '')
        if long_title:
            text_parts.append(f"Long Title: {long_title}")
        
        # Short title
        short_title = bill_data.get('ShortTitleEn', '')
        if short_title:
            text_parts.append(f"Short Title: {short_title}")
        
        # Legislative summary
        summary = bill_data.get('ShortLegislativeSummaryEn', '')
        if summary:
            cleaned_summary = self._clean_html_text(summary)
            if cleaned_summary:
                text_parts.append(f"Legislative Summary: {cleaned_summary}")
        
        # Notes
        notes = bill_data.get('NotesEn', '')
        if notes:
            text_parts.append(f"Notes: {notes}")
        
        # Parliament and session info
        parliament_session = raw_item.get('parliament_session_id', '')
        if parliament_session:
            text_parts.append(f"Parliament Session: {parliament_session}")
        
        # Bill type and status
        bill_type = bill_data.get('BillDocumentTypeName', '')
        if bill_type:
            text_parts.append(f"Bill Type: {bill_type}")
        
        status = bill_data.get('StatusNameEn', '')
        if status:
            text_parts.append(f"Current Status: {status}")
        
        # Sponsor info
        sponsor = bill_data.get('SponsorPersonName', '')
        if sponsor:
            text_parts.append(f"Sponsor: {sponsor}")
        
        affiliation = bill_data.get('SponsorAffiliationTitleEn', '')
        if affiliation:
            text_parts.append(f"Sponsor Affiliation: {affiliation}")
        
        return "\n\n".join(text_parts)
    
    def _classify_bill_type_parliament44(self, bill_data: Dict[str, Any]) -> str:
        """Classify the type of legislative action for Parliament 44 bills"""
        bill_type = bill_data.get('BillDocumentTypeName', '').lower()
        title = bill_data.get('LongTitleEn', '').lower()
        
        if 'government' in bill_type:
            if 'budget' in title or 'appropriation' in title:
                return 'budget_bill'
            else:
                return 'government_bill'
        elif 'private' in bill_type:
            return 'private_member_bill'
        else:
            return 'legislative_bill'
    
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
    
    def _update_processing_status(self, raw_item: Dict[str, Any], status: str):
        """Update the processing_status field in the source collection"""
        try:
            # Get document ID (should match the ingestion pattern)
            parliament_session = raw_item.get('parliament_session_id', '')
            bill_code = raw_item.get('bill_number_code_feed', '')
            
            if parliament_session and bill_code:
                doc_id = f"{parliament_session}_{bill_code}"
            else:
                doc_id = raw_item.get('parl_id', '')
            
            if doc_id:
                # Update the processing status and add timestamp
                update_data = {
                    'processing_status': status,
                    'last_attempted_processing_at': datetime.now(timezone.utc)
                }
                
                # Add LLM model name for successful processing
                if status == 'processed':
                    try:
                        # Try to get model name from different possible attributes
                        if hasattr(self.langchain_instance.llm, 'model'):
                            model_name = self.langchain_instance.llm.model
                        elif hasattr(self.langchain_instance.llm, 'model_name'):
                            model_name = self.langchain_instance.llm.model_name
                        elif hasattr(self.langchain_instance.llm, '_model_name'):
                            model_name = self.langchain_instance.llm._model_name
                        else:
                            # Default to a known model name for Gemini
                            model_name = "models/gemini-2.5-flash-preview-05-20"
                        update_data['llm_model_name_last_attempt'] = model_name
                    except Exception:
                        # Default to known Gemini model if extraction fails
                        update_data['llm_model_name_last_attempt'] = "models/gemini-2.5-flash-preview-05-20"
                
                # Update in Firestore
                from firebase_admin import firestore
                db = firestore.client()
                doc_ref = db.collection(self._get_source_collection()).document(doc_id)
                doc_ref.update(update_data)
                
                self.logger.debug(f"Updated processing status for {doc_id}: {status}")
                
        except Exception as e:
            self.logger.warning(f"Could not update processing status: {e}")
    
    def _create_parliament44_evidence_item(self, raw_item: Dict[str, Any], bill_data: Dict[str, Any], bill_analysis: Dict[str, Any]) -> Dict[str, Any]:
        """Create evidence item in Parliament 44 format"""
        # Extract key information
        bill_number = raw_item.get('bill_number_code_feed', '')
        parliament_session = raw_item.get('parliament_session_id', '')
        long_title_en = bill_data.get('LongTitleEn', '')
        
        # Create bill_parl_id in Parliament 44 format
        bill_parl_id = f"{parliament_session}_{bill_number}"
        
        # Create evidence_id in Parliament 44 format
        # Format: YYYYMMDD_parliament_billnumber_event_chamber_eventid
        ingested_date = raw_item.get('ingested_at') or datetime.now(timezone.utc)
        date_str = ingested_date.strftime('%Y%m%d')
        # Use a consistent event ID for bill events
        evidence_id = f"{date_str}_{parliament_session.replace('-', '_')}_{bill_number}_event_senate_60663690"
        
        # Build URLs
        parliament_num, session_num = parliament_session.split('-')
        about_url = f"https://www.parl.ca/legisinfo/en/bill/{parliament_session}/{bill_number}?view=about"
        details_url = f"https://www.parl.ca/legisinfo/en/bill/{parliament_session}/{bill_number}?view=details"
        source_url = f"https://www.parl.ca/legisinfo/en/bill/{parliament_session}/{bill_number}"
        
        # Determine chamber based on bill number
        chamber = "Senate" if bill_number.startswith('S-') else "House of Commons"
        
        # Extract stage information
        status = bill_data.get('StatusNameEn', '')
        stage_name = "First reading"  # Default stage
        event_type_id = 60110  # Introduction and first reading
        
        # Create evidence item matching Parliament 44 structure
        evidence_item = {
            # Additional information map (contains event_specific_details)
            'additional_information': {
                'about_url': about_url,
                'details_url': details_url,
                'event_specific_details': {
                    'additional_info': '',
                    'chamber': chamber,
                    'event_type_id': event_type_id,
                    'is_terminal_status': False,
                    'stage_name': stage_name
                }
            },
            
            # Bill analysis fields
            'bill_extracted_keywords_concepts': bill_analysis.get('key_concepts', []),
            'bill_one_sentence_description_llm': bill_analysis.get('description', ''),
            'bill_parl_id': bill_parl_id,
            'bill_timeline_summary_llm': bill_analysis.get('summary', ''),
            
            # Core evidence fields
            'description_or_details': f"Chamber: {chamber}. Stage: {stage_name}. Event: Introduction and first reading.",
            'evidence_date': ingested_date,
            'evidence_id': evidence_id,
            'evidence_source_type': 'Bill Event (LEGISinfo)',
            'ingested_at': raw_item.get('ingested_at') or datetime.now(timezone.utc),
            
            # Department and promise linking
            'linked_departments': bill_analysis.get('departments', []),
            'promise_ids': [],
            'promise_linking_status': 'pending',
            
            # Source information
            'source_document_raw_id': bill_number,
            'source_url': source_url,
            
            # Title
            'title_or_summary': f"Bill {bill_number}: Introduction and first reading in {chamber}",
            
            # Parliament context
            'parliament_session_id': parliament_session,
            
            # Additional metadata for compatibility
            'evidence_type': 'legislative_action',
            'evidence_subtype': self._classify_bill_type_parliament44(bill_data),
            'created_at': datetime.now(timezone.utc),
            'last_updated_at': datetime.now(timezone.utc)
        }
        
        return evidence_item 