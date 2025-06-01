"""
Canada News Processor Job

Processes raw news releases into evidence items with LLM-based analysis.
This replaces the existing process_news_to_evidence.py script with a more robust,
class-based implementation.
"""

import logging
import sys
from datetime import datetime, timezone
from typing import Dict, Any, Optional
import re
from pathlib import Path
import hashlib

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


class CanadaNewsProcessor(BaseProcessorJob):
    """
    Processing job for Canada News items.
    
    Transforms raw news items into structured evidence items
    with LLM-based analysis and enrichment.
    """
    
    def __init__(self, job_name: str, config: Dict[str, Any] = None):
        """Initialize the Canada News processor"""
        super().__init__(job_name, config)
        
        # LLM settings
        self.use_llm_analysis = self.config.get('use_llm_analysis', True)
        self.llm_model = self.config.get('llm_model', 'gpt-4')
        self.max_content_length = self.config.get('max_content_length', 8000)
    
    def _get_source_collection(self) -> str:
        """Return the Firestore collection name for raw data"""
        return "raw_news_releases"
    
    def _get_target_collection(self) -> str:
        """Return the Firestore collection name for evidence items"""
        return "evidence_items"
    
    def _process_raw_item(self, raw_item: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        Process a single raw news item into an evidence item.
        
        Args:
            raw_item: Raw news item from Canada News RSS
            
        Returns:
            Evidence item ready for storage or None if processing failed
        """
        try:
            # Extract basic information (using production field names only)
            title = raw_item.get('title_raw', '').strip()
            description = raw_item.get('summary_or_snippet_raw', '').strip()
            full_text = raw_item.get('full_text_scraped', '').strip()
            
            if not title:
                self.logger.warning(f"News item missing title: {raw_item.get('_doc_id', 'unknown')}")
                return None
            
            # Prepare content for LLM analysis
            content_for_analysis = self._prepare_content_for_analysis(title, description, full_text)
            
            # Perform LLM analysis if enabled
            llm_analysis = None
            if self.use_llm_analysis and content_for_analysis:
                llm_analysis = self._analyze_with_llm(content_for_analysis)
            
            # Create evidence item
            evidence_item = {
                # Core identification
                'title_or_summary': title,
                'description_or_details': description,
                'full_text': full_text,
                'evidence_source_type': get_standardized_source_type_for_processor('canada_news'),
                'source_url': raw_item.get('source_url', ''),
                
                # Dates
                'publication_date': raw_item.get('publication_date'),
                'scraped_at': raw_item.get('ingested_at'),  # Use production field name
                
                # Source metadata (using production field names)
                'source_metadata': {
                    'rss_feed_url': raw_item.get('rss_feed_url_used', ''),
                    'categories': raw_item.get('categories_rss', []),
                    'content_type': raw_item.get('content_type', ''),
                    'source_feed': raw_item.get('source_feed', ''),
                    'department_rss': raw_item.get('department_rss', '')
                },
                
                # Parliament context
                'parliament_session_id': raw_item.get('parliament_session_id_assigned'),
                
                # Processing metadata
                'evidence_type': 'government_announcement',
                'processing_notes': [],
                
                # LLM analysis results
                'llm_analysis': llm_analysis,
                
                # Status tracking
                'promise_linking_status': 'pending',
                'created_at': datetime.now(timezone.utc),
                'last_updated_at': datetime.now(timezone.utc),
                
                # Additional metadata for tracking
                'additional_metadata': {
                    'raw_news_release_id': raw_item.get('raw_item_id', raw_item.get('_doc_id', ''))
                }
            }
            
            # Add LLM-derived fields if available
            if llm_analysis:
                self._enrich_with_llm_analysis(evidence_item, llm_analysis)
            
            return evidence_item
            
        except Exception as e:
            self.logger.error(f"Error processing news item {raw_item.get('_doc_id', 'unknown')}: {e}")
            return None
    
    def _prepare_content_for_analysis(self, title: str, description: str, full_text: str) -> str:
        """Prepare content for LLM analysis by combining and truncating"""
        # Combine all available text
        content_parts = []
        
        if title:
            content_parts.append(f"Title: {title}")
        
        if description:
            content_parts.append(f"Description: {description}")
        
        if full_text and full_text != description:
            content_parts.append(f"Full Text: {full_text}")
        
        combined_content = "\n\n".join(content_parts)
        
        # Truncate if too long
        if len(combined_content) > self.max_content_length:
            combined_content = combined_content[:self.max_content_length] + "..."
        
        return combined_content
    
    def _analyze_with_llm(self, content: str) -> Optional[Dict[str, Any]]:
        """
        Analyze content with LLM to extract structured information.
        
        Args:
            content: Text content to analyze
            
        Returns:
            LLM analysis results or None if analysis failed
        """
        try:
            # This would integrate with your LLM service
            # For now, returning a placeholder structure
            
            prompt = self._build_analysis_prompt(content)
            
            # TODO: Replace with actual LLM call
            # response = self.llm_client.analyze(prompt, model=self.llm_model)
            
            # Placeholder analysis structure
            analysis = {
                'summary': self._extract_summary(content),
                'key_topics': self._extract_key_topics(content),
                'government_departments': self._extract_departments(content),
                'policy_areas': self._extract_policy_areas(content),
                'announcement_type': self._classify_announcement_type(content),
                'relevance_score': self._calculate_relevance_score(content),
                'analysis_timestamp': datetime.now(timezone.utc)
            }
            
            return analysis
            
        except Exception as e:
            self.logger.error(f"Error in LLM analysis: {e}")
            return None
    
    def _build_analysis_prompt(self, content: str) -> str:
        """Build prompt for LLM analysis"""
        return f"""
        Analyze the following government news announcement and extract structured information:

        {content}

        Please provide:
        1. A concise summary (2-3 sentences)
        2. Key topics and themes
        3. Government departments mentioned
        4. Policy areas addressed
        5. Type of announcement (policy, funding, appointment, etc.)
        6. Relevance score for promise tracking (0-1)

        Format your response as structured data.
        """
    
    def _extract_summary(self, content: str) -> str:
        """Extract or generate a summary from content"""
        # Simple implementation - take first sentence or description
        sentences = content.split('.')
        if sentences:
            return sentences[0].strip() + '.'
        return content[:200] + "..." if len(content) > 200 else content
    
    def _extract_key_topics(self, content: str) -> list:
        """Extract key topics from content"""
        # Simple keyword-based extraction
        # In practice, this would use more sophisticated NLP
        
        topic_keywords = {
            'healthcare': ['health', 'medical', 'hospital', 'doctor', 'patient'],
            'education': ['education', 'school', 'student', 'university', 'college'],
            'environment': ['environment', 'climate', 'carbon', 'emission', 'green'],
            'economy': ['economy', 'economic', 'business', 'trade', 'investment'],
            'infrastructure': ['infrastructure', 'transport', 'road', 'bridge', 'transit'],
            'defense': ['defense', 'military', 'security', 'armed forces'],
            'immigration': ['immigration', 'immigrant', 'refugee', 'citizenship']
        }
        
        content_lower = content.lower()
        topics = []
        
        for topic, keywords in topic_keywords.items():
            if any(keyword in content_lower for keyword in keywords):
                topics.append(topic)
        
        return topics
    
    def _extract_departments(self, content: str) -> list:
        """Extract government departments mentioned"""
        # Common department patterns
        department_patterns = [
            'Health Canada',
            'Transport Canada',
            'Environment and Climate Change Canada',
            'Immigration, Refugees and Citizenship Canada',
            'Public Safety Canada',
            'Global Affairs Canada',
            'Innovation, Science and Economic Development Canada'
        ]
        
        departments = []
        content_lower = content.lower()
        
        for dept in department_patterns:
            if dept.lower() in content_lower:
                departments.append(dept)
        
        return departments
    
    def _extract_policy_areas(self, content: str) -> list:
        """Extract policy areas from content"""
        # This would be more sophisticated in practice
        return self._extract_key_topics(content)  # Reuse topic extraction for now
    
    def _classify_announcement_type(self, content: str) -> str:
        """Classify the type of government announcement"""
        content_lower = content.lower()
        
        if any(word in content_lower for word in ['funding', 'investment', 'budget', 'million', 'billion']):
            return 'funding_announcement'
        elif any(word in content_lower for word in ['policy', 'regulation', 'law', 'legislation']):
            return 'policy_announcement'
        elif any(word in content_lower for word in ['appointment', 'minister', 'deputy']):
            return 'appointment'
        elif any(word in content_lower for word in ['program', 'initiative', 'launch']):
            return 'program_launch'
        else:
            return 'general_announcement'
    
    def _calculate_relevance_score(self, content: str) -> float:
        """Calculate relevance score for promise tracking"""
        # Simple scoring based on content indicators
        score = 0.5  # Base score
        
        content_lower = content.lower()
        
        # Boost for policy-related content
        if any(word in content_lower for word in ['policy', 'commitment', 'promise', 'pledge']):
            score += 0.2
        
        # Boost for concrete actions
        if any(word in content_lower for word in ['funding', 'investment', 'launch', 'implement']):
            score += 0.2
        
        # Boost for specific departments
        if any(word in content_lower for word in ['minister', 'government', 'canada']):
            score += 0.1
        
        return min(score, 1.0)
    
    def _enrich_with_llm_analysis(self, evidence_item: Dict[str, Any], 
                                 llm_analysis: Dict[str, Any]):
        """Enrich evidence item with LLM analysis results"""
        # Add summary if not already present
        if llm_analysis.get('summary') and not evidence_item.get('summary'):
            evidence_item['summary'] = llm_analysis['summary']
        
        # Add extracted topics and departments
        evidence_item['topics'] = llm_analysis.get('key_topics', [])
        evidence_item['departments'] = llm_analysis.get('government_departments', [])
        evidence_item['policy_areas'] = llm_analysis.get('policy_areas', [])
        
        # Update evidence type based on analysis
        announcement_type = llm_analysis.get('announcement_type')
        if announcement_type:
            evidence_item['evidence_subtype'] = announcement_type
        
        # Update relevance score
        relevance_score = llm_analysis.get('relevance_score', 0)
        if relevance_score > 0:
            current_relevance = evidence_item.get('relevance_score', 0)
            evidence_item['relevance_score'] = min(current_relevance + (relevance_score * 0.2), 1.0)
    
    def _generate_evidence_id(self, evidence_item: Dict[str, Any], 
                             raw_item: Dict[str, Any]) -> str:
        """Generate a unique ID for the evidence item following pattern: YYYYMMDD_{parliament}_{source}_{hash}"""
        # Get publication date for date prefix
        pub_date = evidence_item.get('publication_date') or raw_item.get('publication_date')
        if pub_date:
            date_prefix = pub_date.strftime('%Y%m%d')
        else:
            date_prefix = datetime.now(timezone.utc).strftime('%Y%m%d')
        
        # Get parliament session ID
        parliament_id = evidence_item.get('parliament_session_id', '44')  # Default to 44
        
        # Source type identifier
        source_type = 'News'
        
        # Create hash from raw item ID or GUID for uniqueness
        raw_doc_id = raw_item.get('_doc_id', '')
        guid = raw_item.get('guid', '')
        
        if raw_doc_id:
            hash_source = raw_doc_id
        elif guid:
            hash_source = guid
        else:
            # Fallback to URL + title
            url = raw_item.get('source_url', '')
            title = raw_item.get('title', '')
            hash_source = f"{url}_{title}"
        
        # Generate short hash (8-10 characters like in production)
        short_hash = hashlib.sha256(hash_source.encode()).hexdigest()[:9]
        
        # Return in format: YYYYMMDD_{parliament}_{source}_{hash}
        return f"{date_prefix}_{parliament_id}_{source_type}_{short_hash}"
    
    def _should_update_evidence(self, existing_evidence: Dict[str, Any], 
                               new_evidence: Dict[str, Any]) -> bool:
        """Determine if existing evidence should be updated"""
        # Update if content has changed
        content_fields = ['title_or_summary', 'description_or_details', 'full_text']
        for field in content_fields:
            if existing_evidence.get(field) != new_evidence.get(field):
                return True
        
        # Update if LLM analysis is new or improved
        existing_analysis = existing_evidence.get('llm_analysis')
        new_analysis = new_evidence.get('llm_analysis')
        
        if new_analysis and not existing_analysis:
            return True
        
        if new_analysis and existing_analysis:
            # Update if relevance score improved significantly
            existing_relevance = existing_analysis.get('relevance_score', 0)
            new_relevance = new_analysis.get('relevance_score', 0)
            if new_relevance > existing_relevance + 0.1:
                return True
        
        return False
    
    def _get_evidence_id_source_type(self) -> str:
        """Get the source type identifier for evidence ID generation"""
        return 'CanadaNews' 