"""
Orders in Council Processor Job

Processes raw Orders in Council into evidence items with LLM analysis.
Uses the existing prompt_oic_evidence.md prompt for structured analysis.
"""

import logging
import sys
import json
from datetime import datetime, timezone
from typing import Dict, Any, Optional
from pathlib import Path
import os
from dotenv import load_dotenv

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

# Load environment variables
load_dotenv()


class OrdersInCouncilProcessor(BaseProcessorJob):
    """
    Processing job for Orders in Council data.
    
    Transforms raw OIC data into structured evidence items
    with LLM analysis using the prompt_oic_evidence.md prompt.
    """
    
    def __init__(self, job_name: str, config: Dict[str, Any] = None):
        """Initialize the Orders in Council processor"""
        super().__init__(job_name, config)
        
        # Processing settings
        self.min_content_length = self.config.get('min_content_length', 50)
        
        # Load the OIC evidence prompt
        self.prompt_template = self._load_prompt_template()
        
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
        return self.config.get('source_collection', "raw_orders_in_council")
    
    def _get_target_collection(self) -> str:
        """Return the Firestore collection name for evidence items"""
        return self.config.get('target_collection', "evidence_items")
    
    def _load_prompt_template(self) -> str:
        """Load the OIC evidence prompt template"""
        try:
            prompt_path = Path(__file__).parent.parent.parent / "prompts" / "prompt_oic_evidence.md"
            if prompt_path.exists():
                return prompt_path.read_text()
            else:
                self.logger.warning("OIC prompt template not found, using fallback")
                return self._get_fallback_prompt()
        except Exception as e:
            self.logger.error(f"Error loading prompt template: {e}")
            return self._get_fallback_prompt()
    
    def _get_fallback_prompt(self) -> str:
        """Fallback prompt if template file is not found"""
        return """
Analyze the following Order in Council and extract structured information:

ORDER IN COUNCIL DATA:
- OIC Number: {oic_number_full_raw}
- OIC Date: {oic_date}
- Title/Summary: {title_or_summary_raw}
- Responsible Department: {responsible_department_raw}
- Act Citation: {act_citation_raw}
- Parliamentary Session: {parliament_session_id}

FULL TEXT OF ORDER IN COUNCIL:
{full_text_scraped}

Please analyze this Order in Council and provide a JSON response with:
1. timeline_summary: Brief factual summary (max 30 words)
2. potential_relevance_score: High/Medium/Low relevance for government commitments
3. key_concepts: Array of up to 10 keywords or phrases
4. sponsoring_department_standardized: Primary responsible department
5. one_sentence_description: Core purpose (30-50 words)

Return ONLY valid JSON with these fields.
        """
    
    def _process_raw_item(self, raw_item: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        Process a single raw OIC item into an evidence item.
        
        Args:
            raw_item: Raw OIC item from ingestion
            
        Returns:
            Evidence item ready for storage or None if processing failed
        """
        try:
            # Extract basic information
            attach_id = raw_item.get('attach_id')
            oic_number = raw_item.get('oic_number_full_raw', '')
            raw_oic_id = raw_item.get('raw_oic_id', '')
            title = raw_item.get('title_or_summary_raw', '')
            full_text = raw_item.get('full_text_scraped', '')
            
            # Basic validation
            if not attach_id or (not oic_number and not title):
                self.logger.warning(f"OIC missing required fields: {raw_item.get('_doc_id', 'unknown')}")
                self._update_processing_status(raw_item, 'skipped_missing_data')
                return None
            
            # Check content length
            if len(full_text) < self.min_content_length:
                self.logger.debug(f"OIC content too short, skipping: {oic_number}")
                self._update_processing_status(raw_item, 'skipped_insufficient_content')
                return None
            
            # Analyze OIC content with LLM
            oic_analysis = self._analyze_oic_with_llm(raw_item)
            
            if not oic_analysis:
                self.logger.warning(f"Failed to analyze OIC {oic_number}")
                self._update_processing_status(raw_item, 'error_processing_script')
                return None
            
            # Create evidence item matching the existing structure
            evidence_item = self._create_evidence_item(raw_item, oic_analysis)
            
            # Update processing status to indicate successful processing
            self._update_processing_status(raw_item, 'evidence_created')
            
            return evidence_item
            
        except Exception as e:
            self.logger.error(f"Error processing OIC {raw_item.get('raw_oic_id', 'unknown')}: {e}")
            self._update_processing_status(raw_item, 'error_processing_script')
            return None
    
    def _analyze_oic_with_llm(self, raw_item: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Analyze OIC content using LLM with the OIC evidence prompt"""
        try:
            # Extract data for prompt
            oic_number = raw_item.get('oic_number_full_raw', '')
            oic_date = raw_item.get('oic_date')
            title = raw_item.get('title_or_summary_raw', '')
            full_text = raw_item.get('full_text_scraped', '')
            source_url = raw_item.get('source_url_oic_detail_page', '')
            parliament_session = raw_item.get('parliament_session_id_assigned', '')
            responsible_dept = raw_item.get('responsible_department_raw', '')
            act_citation = raw_item.get('act_citation_raw', '')
            
            # Format date for prompt
            date_str = oic_date.strftime("%Y-%m-%d") if oic_date else "Unknown"
            
            # Fill in the prompt template
            filled_prompt = self.prompt_template.format(
                oic_number_full_raw=oic_number,
                oic_date=date_str,
                title_or_summary_raw=title,
                responsible_department_raw=responsible_dept or "Not specified",
                act_citation_raw=act_citation or "Not specified",
                full_text_scraped=full_text[:3000] + ("..." if len(full_text) > 3000 else ""),
                parliament_session_id=parliament_session
            )
            
            # Debug logging
            self.logger.debug(f"Full text length: {len(full_text)}")
            self.logger.debug(f"Title: {title}")
            self.logger.debug(f"OIC Number: {oic_number}")
            self.logger.debug(f"Filled prompt length: {len(filled_prompt)}")
            
            # Get LLM instance and analyze
            langchain_instance = self.langchain_instance
            if not langchain_instance:
                self.logger.error("Could not get LangChain instance")
                return None
            
            # Make LLM call
            response = langchain_instance.llm.invoke(filled_prompt)
            
            # Parse JSON response
            if hasattr(response, 'content'):
                response_text = response.content
            else:
                response_text = str(response)
            
            # Extract JSON from response
            json_start = response_text.find('{')
            json_end = response_text.rfind('}') + 1
            
            if json_start >= 0 and json_end > json_start:
                json_str = response_text[json_start:json_end]
                analysis = json.loads(json_str)
                
                # Validate required fields
                required_fields = ['timeline_summary', 'potential_relevance_score', 'key_concepts']
                if all(field in analysis for field in required_fields):
                    analysis['analysis_timestamp'] = datetime.now(timezone.utc)
                    return analysis
                else:
                    self.logger.warning(f"LLM response missing required fields: {analysis}")
                    return None
            else:
                self.logger.warning(f"Could not extract JSON from LLM response: {response_text[:200]}")
                return None
                
        except Exception as e:
            self.logger.error(f"Error in LLM analysis: {e}")
            return None
    
    def _create_evidence_item(self, raw_item: Dict[str, Any], analysis: Dict[str, Any]) -> Dict[str, Any]:
        """Create evidence item matching the existing structure"""
        # Extract basic info
        attach_id = raw_item.get('attach_id')
        raw_oic_id = raw_item.get('raw_oic_id', '')
        oic_number = raw_item.get('oic_number_full_raw', '')
        title = raw_item.get('title_or_summary_raw', '')
        full_text = raw_item.get('full_text_scraped', '')
        oic_date = raw_item.get('oic_date')
        source_url = raw_item.get('source_url_oic_detail_page', '')
        parliament_session = raw_item.get('parliament_session_id_assigned', '')
        ingested_at = raw_item.get('ingested_at')
        
        # Generate evidence ID
        evidence_id = self._generate_evidence_id(raw_item, oic_date)
        
        # Create evidence item structure matching the sample
        evidence_item = {
            # Core identification (matching sample structure)
            'evidence_id': evidence_id,
            'attach_id': attach_id,
            'raw_oic_document_id': raw_oic_id,
            'source_document_raw_id': raw_oic_id,
            
            # Content fields
            'title_or_summary': analysis.get('timeline_summary', title or f"Order in Council {oic_number}"),
            'description_or_details': analysis.get('one_sentence_description', title or ''),
            
            # Source information
            'evidence_source_type': 'OrderInCouncil (PCO)',
            'source_url': source_url,
            
            # Dates
            'evidence_date': oic_date,
            'ingested_at': ingested_at,
            
            # LLM analysis results
            'key_concepts': analysis.get('key_concepts', []),
            'potential_relevance_score': analysis.get('potential_relevance_score', 'Low'),
            'linked_departments': self._extract_departments_from_analysis(analysis),
            
            # Parliament context
            'parliament_session_id': parliament_session,
            
            # Additional metadata
            'additional_metadata': {
                'oic_number_full_raw': oic_number,
                'analysis_timestamp': analysis.get('analysis_timestamp')
            },
            
            # Linking fields
            'promise_ids': [],
            'promise_linking_status': 'pending',
            
            # Timestamps
            'created_at': datetime.now(timezone.utc),
            'last_updated_at': datetime.now(timezone.utc)
        }
        
        return evidence_item
    
    def _extract_departments_from_analysis(self, analysis: Dict[str, Any]) -> list:
        """Extract department information from LLM analysis"""
        departments = []
        
        # Get standardized department from analysis
        dept = analysis.get('sponsoring_department_standardized', '')
        if dept and dept.strip():
            departments.append(dept.strip())
        
        return departments
    
    def _generate_evidence_id(self, raw_item: Dict[str, Any], oic_date: datetime) -> str:
        """Generate evidence ID matching the existing pattern"""
        # Use pattern: YYYYMMDD_parliament_OIC_hash
        if oic_date:
            date_str = oic_date.strftime("%Y%m%d")
        else:
            date_str = datetime.now().strftime("%Y%m%d")
        
        parliament_session = raw_item.get('parliament_session_id_assigned', 'XX')
        raw_oic_id = raw_item.get('raw_oic_id', '')
        
        # Create hash from OIC identifier
        import hashlib
        hash_input = f"{raw_oic_id}_{raw_item.get('attach_id', '')}"
        short_hash = hashlib.sha256(hash_input.encode()).hexdigest()[:10]
        
        return f"{date_str}_{parliament_session}_OIC_{short_hash}"
    
    def _update_processing_status(self, raw_item: Dict[str, Any], status: str):
        """Update the processing status of a raw OIC item"""
        try:
            doc_id = raw_item.get('_doc_id') or raw_item.get('raw_oic_id')
            if not doc_id:
                self.logger.error("Cannot update processing status: no document ID found")
                return
            
            collection_name = self._get_source_collection()
            
            # Prepare update data
            update_data = {
                'evidence_processing_status': status,
                'last_updated_at': datetime.now(timezone.utc)
            }
            
            # Add processed_at timestamp for successful processing
            if status == 'evidence_created':
                update_data['processed_at'] = datetime.now(timezone.utc)
                
                # Add LLM model name if available
                llm_instance = self.langchain_instance
                if hasattr(llm_instance, 'model_name'):
                    update_data['llm_model_name_last_attempt'] = llm_instance.model_name
                elif hasattr(llm_instance, 'model'):
                    update_data['llm_model_name_last_attempt'] = llm_instance.model
                else:
                    update_data['llm_model_name_last_attempt'] = 'unknown'
            
            self.db.collection(collection_name).document(doc_id).update(update_data)
            self.logger.debug(f"Updated processing status for {doc_id} to {status}")
            
        except Exception as e:
            self.logger.error(f"Failed to update processing status: {e}")
    
    def _should_update_evidence(self, existing_evidence: Dict[str, Any], 
                               new_evidence: Dict[str, Any]) -> bool:
        """Determine if existing evidence should be updated"""
        # Update if content has changed
        content_fields = ['title_or_summary', 'description_or_details']
        for field in content_fields:
            if existing_evidence.get(field) != new_evidence.get(field):
                return True
        
        # Update if analysis has improved
        existing_concepts = len(existing_evidence.get('key_concepts', []))
        new_concepts = len(new_evidence.get('key_concepts', []))
        if new_concepts > existing_concepts:
            return True
        
        return False 