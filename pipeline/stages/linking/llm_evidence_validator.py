#!/usr/bin/env python3
"""
LLM Evidence Validator

Validates semantic evidence-promise matches using LLM analysis for improved precision.
Provides contextual evaluation of semantic similarity matches to filter out false positives
and rank genuine policy relationships.

This module provides:
- Individual evidence-promise pair validation
- Batch validation of semantic candidates
- Confidence scoring and categorization
- Integration with existing langchain configuration
"""

import logging
import time
import json
from typing import List, Dict, Any, Optional
from dataclasses import dataclass
from pathlib import Path
import sys

# Add lib directory to path for imports
sys.path.append(str(Path(__file__).parent.parent.parent.parent / 'lib'))

from langchain_config import get_langchain_instance
from langchain.prompts import PromptTemplate
from langchain_core.prompts import PromptTemplate as LangchainPromptTemplate
from langchain_core.output_parsers import JsonOutputParser
from langchain_core.exceptions import LangChainException

# Set up logging
logger = logging.getLogger(__name__)

@dataclass
class MatchEvaluation:
    """Structured evaluation result from LLM validation."""
    confidence_score: float  # 0.0-1.0
    reasoning: str
    category: str  # "Direct Implementation" | "Supporting Action" | "Related Policy" | "Not Related"
    thematic_alignment: float
    department_overlap: bool
    timeline_relevance: str
    implementation_type: str
    semantic_quality_assessment: str
    progress_indicator: str
    
    # Original semantic data
    promise_id: str
    semantic_similarity_score: float
    
    @property
    def is_valid_match(self) -> bool:
        """Returns True if this is considered a valid match."""
        return self.confidence_score >= 0.4 and self.category != "Not Related"
    
    @property
    def is_high_confidence(self) -> bool:
        """Returns True if this is a high confidence match."""
        return self.confidence_score >= 0.7


class LLMEvidenceValidator:
    """
    LLM-based validator for semantic evidence-promise matches.
    
    Uses contextual analysis to evaluate whether semantic similarity represents
    genuine policy relationships and provides confidence scoring.
    """
    
    def __init__(self, validation_threshold: float = 0.7, firebase_config: Optional[Dict[str, Any]] = None):
        """Initialize the LLM Evidence Validator"""
        logger.info("Initializing LLM validator with faster gemini-2.5-flash model")
        
        self.validation_threshold = validation_threshold
        
        # Initialize langchain with faster model for validation
        self.langchain = get_langchain_instance()
        logger.info(f"LLM Evidence Validator initialized with model: {self.langchain.model_name}")
        
        # Load validation prompt template
        self.prompt_template = self._load_prompt_template()
        
        # Validation statistics
        self.stats = {
            'validations_performed': 0,
            'total_validation_time': 0.0,
            'successful_validations': 0,
            'failed_validations': 0,
            'avg_validation_time': 0.0,
            'batch_optimizations': 0
        }
        
        logger.info("LLM Evidence Validator initialized successfully")
    
    def _load_prompt_template(self) -> PromptTemplate:
        """Load the evidence-promise validation prompt template."""
        try:
            prompts_dir = Path(__file__).parent.parent.parent.parent / 'prompts'
            prompt_file = prompts_dir / 'prompt_evidence_promise_validation.md'
            
            if not prompt_file.exists():
                raise FileNotFoundError(f"Validation prompt not found: {prompt_file}")
            
            prompt_content = prompt_file.read_text()
            return PromptTemplate.from_template(prompt_content)
            
        except Exception as e:
            logger.error(f"Failed to load validation prompt: {e}")
            raise
    
    def validate_match(
        self,
        evidence_item: Dict[str, Any],
        promise_item: Dict[str, Any],
        semantic_similarity_score: float
    ) -> MatchEvaluation:
        """
        Validate a single evidence-promise match using LLM analysis.
        
        Args:
            evidence_item: Evidence item data
            promise_item: Promise item data
            semantic_similarity_score: Cosine similarity score from semantic analysis
            
        Returns:
            MatchEvaluation object with detailed assessment
        """
        if not self.langchain or not self.prompt_template:
            raise Exception("Validator not initialized. Call initialize() first.")
        
        start_time = time.time()
        
        try:
            # Prepare input data for the prompt
            # Defensive checks to prevent TypeError on .join() if data is not an iterable list
            key_concepts = evidence_item.get('key_concepts')
            key_concepts_str = ', '.join(key_concepts) if isinstance(key_concepts, list) else ''
            
            linked_departments = evidence_item.get('linked_departments')
            linked_departments_str = ', '.join(linked_departments) if isinstance(linked_departments, list) else ''

            intended_impact = promise_item.get('intended_impact_and_objectives')
            intended_impact_str = ', '.join(intended_impact) if isinstance(intended_impact, list) else ''

            prompt_data = {
                'parliament_session_id': evidence_item.get('parliament_session_id', ''),
                'evidence_source_type': evidence_item.get('evidence_source_type', ''),
                'evidence_date': str(evidence_item.get('evidence_date', '')),
                'evidence_title_or_summary': evidence_item.get('title_or_summary', ''),
                'evidence_description_or_details': evidence_item.get('description_or_details', ''),
                'evidence_key_concepts': key_concepts_str,
                'evidence_linked_departments': linked_departments_str,
                
                'promise_id': promise_item.get('promise_id', promise_item.get('_doc_id', '')),
                'promise_text': promise_item.get('text', ''),
                'promise_description': promise_item.get('description', ''),
                'promise_background_and_context': promise_item.get('background_and_context', ''),
                'promise_intended_impact_and_objectives': intended_impact_str,
                'promise_responsible_department_lead': promise_item.get('responsible_department_lead', ''),
                'semantic_similarity_score': semantic_similarity_score
            }
            
            # Generate LLM evaluation
            formatted_prompt = self.prompt_template.format(**prompt_data)
            
            logger.debug(f"Validating match: {promise_item.get('promise_id', 'unknown')} (similarity: {semantic_similarity_score:.3f})")
            
            # Use the linking LLM for better analysis
            response = self.langchain.linking_llm.invoke(formatted_prompt)
            
            # Debug logging for troubleshooting
            if hasattr(response, 'content'):
                raw_response = response.content
            else:
                raw_response = str(response)
            
            logger.debug(f"Raw LLM response: {raw_response[:500]}...")
            
            # Parse JSON response
            try:
                if hasattr(response, 'content'):
                    response_text = response.content
                else:
                    response_text = str(response)
                
                # Clean the response to extract JSON more robustly
                response_text = response_text.strip()
                
                # Remove markdown code blocks if present
                if response_text.startswith('```json'):
                    response_text = response_text[7:]
                elif response_text.startswith('```'):
                    response_text = response_text[3:]
                    
                if response_text.endswith('```'):
                    response_text = response_text[:-3]
                
                # Remove any leading/trailing whitespace and newlines
                response_text = response_text.strip()
                
                # Try to find JSON content between curly braces if response is malformed
                if not response_text.startswith('{'):
                    # Look for the first opening brace
                    start_idx = response_text.find('{')
                    if start_idx != -1:
                        response_text = response_text[start_idx:]
                
                if not response_text.endswith('}'):
                    # Look for the last closing brace
                    end_idx = response_text.rfind('}')
                    if end_idx != -1:
                        response_text = response_text[:end_idx + 1]
                
                # Additional fallback: if still malformed, try to extract just the JSON part
                if not (response_text.startswith('{') and response_text.endswith('}')):
                    logger.warning(f"Malformed response, attempting to extract JSON: {response_text[:100]}...")
                    
                    # Try to find a complete JSON object
                    import re
                    json_match = re.search(r'\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\}', response_text, re.DOTALL)
                    if json_match:
                        response_text = json_match.group(0)
                    else:
                        raise json.JSONDecodeError("No valid JSON found in response", response_text, 0)
                
                evaluation_data = json.loads(response_text)
                
            except json.JSONDecodeError as e:
                logger.warning(f"Failed to parse LLM response as JSON: {e}")
                logger.warning(f"Full response was: {response_text}")
                
                # Create a fallback evaluation
                evaluation_data = {
                    'confidence_score': 0.1,
                    'reasoning': f"Failed to parse LLM response: {str(e)}",
                    'category': 'Not Related',
                    'thematic_alignment': 0.1,
                    'department_overlap': False,
                    'timeline_relevance': 'Unknown',
                    'implementation_type': 'Unknown',
                    'semantic_quality_assessment': 'Failed to evaluate',
                    'progress_indicator': 'No assessment available'
                }
            
            # Create evaluation object
            evaluation = MatchEvaluation(
                confidence_score=float(evaluation_data.get('confidence_score', 0.0)),
                reasoning=evaluation_data.get('reasoning', ''),
                category=evaluation_data.get('category', 'Not Related'),
                thematic_alignment=float(evaluation_data.get('thematic_alignment', 0.0)),
                department_overlap=bool(evaluation_data.get('department_overlap', False)),
                timeline_relevance=evaluation_data.get('timeline_relevance', ''),
                implementation_type=evaluation_data.get('implementation_type', ''),
                semantic_quality_assessment=evaluation_data.get('semantic_quality_assessment', ''),
                progress_indicator=evaluation_data.get('progress_indicator', ''),
                promise_id=promise_item.get('promise_id', promise_item.get('_doc_id', '')),
                semantic_similarity_score=semantic_similarity_score
            )
            
            # Update statistics
            processing_time = time.time() - start_time
            self.stats['validations_performed'] += 1
            self.stats['total_validation_time'] += processing_time
            
            if evaluation.is_valid_match:
                self.stats['successful_validations'] += 1
            else:
                self.stats['failed_validations'] += 1
            
            # Estimate cost (rough approximation)
            #estimated_tokens = len(formatted_prompt) / 4 + 200  # Rough token estimate
            #self.stats['total_cost_estimate'] += estimated_tokens * 0.00003  # Gemini pricing estimate
            
            logger.info(f"Validation complete: {evaluation.category} (confidence: {evaluation.confidence_score:.3f})")
            
            return evaluation
            
        except Exception as e:
            logger.error(f"Error during LLM validation: {e}")
            
            # Return a fallback evaluation
            return MatchEvaluation(
                confidence_score=0.0,
                reasoning=f"Validation error: {str(e)}",
                category='Not Related',
                thematic_alignment=0.0,
                department_overlap=False,
                timeline_relevance='Error',
                implementation_type='Error',
                semantic_quality_assessment='Validation failed',
                progress_indicator='No assessment due to error',
                promise_id=promise_item.get('promise_id', promise_item.get('_doc_id', '')),
                semantic_similarity_score=semantic_similarity_score
            )
    
    def validate_semantic_matches(
        self,
        evidence_item: Dict[str, Any],
        semantic_matches: List[Dict[str, Any]],
        validation_threshold: float = 0.7
    ) -> List[MatchEvaluation]:
        """
        Validate a list of semantic matches for a single evidence item.
        
        Args:
            evidence_item: Evidence item data
            semantic_matches: List of semantic match dictionaries
            
        Returns:
            List of MatchEvaluation objects, sorted by confidence score
        """
        if not semantic_matches:
            return []
        
        logger.info(f"Validating {len(semantic_matches)} semantic matches for evidence {evidence_item.get('evidence_id', 'unknown')}")
        
        evaluations = []
        
        for match in semantic_matches:
            try:
                # Extract promise data and similarity score from match
                promise_data = match.get('promise_full', {})
                similarity_score = match.get('similarity_score', 0.0)
                
                if not promise_data:
                    logger.warning("Semantic match missing promise data, skipping")
                    continue
                
                # Validate the match
                evaluation = self.validate_match(evidence_item, promise_data, similarity_score)
                evaluations.append(evaluation)
                
            except Exception as e:
                logger.error(f"Error validating semantic match: {e}")
                continue
        
        # Sort by confidence score (highest first)
        evaluations.sort(key=lambda x: x.confidence_score, reverse=True)
        
        # Filter by validation threshold
        valid_evaluations = [e for e in evaluations if e.confidence_score >= validation_threshold]
        
        logger.info(f"LLM validation complete: {len(valid_evaluations)}/{len(evaluations)} matches above threshold {validation_threshold}")
        
        return valid_evaluations
    
    def batch_validate(
        self,
        evidence_items: List[Dict[str, Any]],
        semantic_results: Dict[str, List[Dict[str, Any]]]
    ) -> Dict[str, List[MatchEvaluation]]:
        """
        Validate semantic matches for multiple evidence items.
        
        Args:
            evidence_items: List of evidence item data
            semantic_results: Dictionary mapping evidence_id to semantic matches
            
        Returns:
            Dictionary mapping evidence_id to validated matches
        """
        logger.info(f"Starting batch validation for {len(evidence_items)} evidence items")
        
        batch_results = {}
        
        for evidence_item in evidence_items:
            evidence_id = evidence_item.get('evidence_id')
            if not evidence_id:
                logger.warning("Evidence item missing evidence_id, skipping")
                continue
            
            semantic_matches = semantic_results.get(evidence_id, [])
            if not semantic_matches:
                batch_results[evidence_id] = []
                continue
            
            try:
                validated_matches = self.validate_semantic_matches(evidence_item, semantic_matches)
                batch_results[evidence_id] = validated_matches
                
            except Exception as e:
                logger.error(f"Error validating matches for evidence {evidence_id}: {e}")
                batch_results[evidence_id] = []
        
        logger.info(f"Batch validation complete. Processed {len(batch_results)} evidence items")
        
        return batch_results
    
    def get_stats(self) -> Dict[str, Any]:
        """Get validation statistics."""
        stats = self.stats.copy()
        if self.langchain:
            langchain_stats = self.langchain.get_cost_summary()
            stats.update(langchain_stats)
        return stats
    
    def reset_stats(self) -> None:
        """Reset validation statistics."""
        self.stats = {
            'validations_performed': 0,
            'total_validation_time': 0.0,
            'successful_validations': 0,
            'failed_validations': 0,
            'avg_validation_time': 0.0,
            'batch_optimizations': 0
        }
        if self.langchain:
            self.langchain.cost_tracker.costs = []

    def batch_validate_matches(
        self,
        evidence_item: Dict[str, Any],
        semantic_matches: List[Dict[str, Any]],
        validation_threshold: float = 0.7
    ) -> List[MatchEvaluation]:
        """
        Batch validate multiple semantic matches in a single LLM call for better performance.
        
        Args:
            evidence_item: Evidence item data
            semantic_matches: List of semantic match dictionaries
            validation_threshold: Minimum confidence score for valid matches
            
        Returns:
            List of MatchEvaluation objects, sorted by confidence score
        """
        if not semantic_matches:
            return []
        
        # Limit batch size to prevent extremely long prompts
        batch_size = min(len(semantic_matches), 8)  # Process up to 8 matches at once
        semantic_matches = semantic_matches[:batch_size]
        
        logger.info(f"🚀 BATCH VALIDATION: Processing {len(semantic_matches)} matches in single LLM call")
        
        start_time = time.time()
        
        try:
            # Create batch validation prompt
            # Defensive checks to prevent TypeError on .join() if data is not an iterable list
            key_concepts = evidence_item.get('key_concepts')
            key_concepts_str = ', '.join(key_concepts) if isinstance(key_concepts, list) else ''

            linked_departments = evidence_item.get('linked_departments')
            linked_departments_str = ', '.join(linked_departments) if isinstance(linked_departments, list) else ''

            evidence_data = {
                'parliament_session_id': evidence_item.get('parliament_session_id', ''),
                'evidence_source_type': evidence_item.get('evidence_source_type', ''),
                'evidence_date': str(evidence_item.get('evidence_date', '')),
                'evidence_title_or_summary': evidence_item.get('title_or_summary', ''),
                'evidence_description_or_details': evidence_item.get('description_or_details', ''),
                'evidence_key_concepts': key_concepts_str,
                'evidence_linked_departments': linked_departments_str,
            }
            
            # Build promises list for batch evaluation
            promises_data = []
            for i, match in enumerate(semantic_matches, 1):
                promise_data = match.get('promise_full', {})
                promises_data.append({
                    'match_number': i,
                    'promise_id': promise_data.get('promise_id', ''),
                    'promise_text': promise_data.get('text', ''),
                    'promise_description': promise_data.get('description', ''),
                    'semantic_similarity_score': match.get('similarity_score', 0.0)
                })
            
            # Create batch prompt
            batch_prompt = f"""You are evaluating evidence-promise relationships. Analyze this evidence against multiple promise candidates and return evaluations for each.

**EVIDENCE:**
- Source: {evidence_data['evidence_source_type']}
- Date: {evidence_data['evidence_date']}
- Title: {evidence_data['evidence_title_or_summary']}
- Description: {evidence_data['evidence_description_or_details']}
- Key Concepts: {evidence_data['evidence_key_concepts']}

**PROMISE CANDIDATES TO EVALUATE:**
"""
            
            for promise in promises_data:
                batch_prompt += f"""
**Match {promise['match_number']}:** (Semantic Similarity: {promise['semantic_similarity_score']:.3f})
- Promise ID: {promise['promise_id']}
- Text: {promise['promise_text'][:300]}...
- Description: {promise['promise_description'][:200]}...
"""
            
            batch_prompt += f"""

**INSTRUCTIONS:**
Evaluate each promise candidate and return a JSON array with {len(promises_data)} evaluation objects.
Each evaluation should assess whether the evidence represents meaningful progress toward that specific promise.

For each promise, provide:
- confidence_score: 0.0-1.0 (how confident you are this is a genuine relationship)
- category: "Direct Implementation" | "Supporting Action" | "Related Policy" | "Not Related"  
- reasoning: Brief explanation of your assessment

**RESPONSE FORMAT:**
Return a JSON array with {len(promises_data)} objects:
```json
[
  {{
    "match_number": 1,
    "confidence_score": 0.75,
    "category": "Supporting Action",
    "reasoning": "Brief explanation..."
  }},
  {{
    "match_number": 2,
    "confidence_score": 0.20,
    "category": "Not Related", 
    "reasoning": "Brief explanation..."
  }}
]
```
"""
            
            # Call LLM
            response = self.langchain.linking_llm.invoke(batch_prompt)
            
            # Parse response
            if hasattr(response, 'content'):
                response_text = response.content
            else:
                response_text = str(response)
            
            # Clean and parse JSON
            response_text = response_text.strip()
            if response_text.startswith('```json'):
                response_text = response_text[7:]
            elif response_text.startswith('```'):
                response_text = response_text[3:]
            if response_text.endswith('```'):
                response_text = response_text[:-3]
            response_text = response_text.strip()
            
            # Find JSON array
            start_idx = response_text.find('[')
            end_idx = response_text.rfind(']')
            if start_idx != -1 and end_idx != -1:
                response_text = response_text[start_idx:end_idx + 1]
            
            try:
                batch_results = json.loads(response_text)
            except json.JSONDecodeError as e:
                logger.warning(f"Failed to parse batch response as JSON: {e}")
                # Fallback to individual validation
                return self.validate_semantic_matches(evidence_item, semantic_matches, validation_threshold)
            
            # Convert batch results to MatchEvaluation objects
            evaluations = []
            for result in batch_results:
                try:
                    match_num = result.get('match_number', 1) - 1  # Convert to 0-based index
                    if 0 <= match_num < len(semantic_matches):
                        match = semantic_matches[match_num]
                        promise_data = match.get('promise_full', {})
                        
                        evaluation = MatchEvaluation(
                            confidence_score=float(result.get('confidence_score', 0.0)),
                            reasoning=result.get('reasoning', ''),
                            category=result.get('category', 'Not Related'),
                            thematic_alignment=float(result.get('confidence_score', 0.0)),
                            department_overlap=result.get('category') != 'Not Related',
                            timeline_relevance="Contemporary",
                            implementation_type="Policy Implementation",
                            semantic_quality_assessment="Batch validated",
                            progress_indicator="Assessed in batch",
                            promise_id=promise_data.get('promise_id', ''),
                            semantic_similarity_score=match.get('similarity_score', 0.0)
                        )
                        evaluations.append(evaluation)
                        
                except Exception as e:
                    logger.warning(f"Error processing batch result {match_num}: {e}")
                    continue
            
            # Update statistics
            processing_time = time.time() - start_time
            self.stats['validations_performed'] += len(evaluations)
            self.stats['total_validation_time'] += processing_time
            self.stats['batch_optimizations'] += 1
            
            # Filter and sort results
            valid_evaluations = [e for e in evaluations if e.confidence_score >= validation_threshold]
            valid_evaluations.sort(key=lambda x: x.confidence_score, reverse=True)
            
            logger.info(f"🚀 BATCH COMPLETE: {len(valid_evaluations)}/{len(evaluations)} matches above threshold {validation_threshold} in {processing_time:.1f}s")
            
            return valid_evaluations
            
        except Exception as e:
            logger.error(f"Error during batch LLM validation: {e}")
            # Fallback to individual validation
            return self.validate_semantic_matches(evidence_item, semantic_matches, validation_threshold)


# Convenience function for direct usage
def validate_evidence_matches(
    evidence_item: Dict[str, Any],
    semantic_matches: List[Dict[str, Any]],
    validation_threshold: float = 0.7
) -> List[MatchEvaluation]:
    """
    Convenience function to validate semantic matches for a single evidence item.
    
    Args:
        evidence_item: Evidence item data
        semantic_matches: List of semantic match dictionaries
        validation_threshold: Minimum confidence score for valid matches
        
    Returns:
        List of validated match evaluations
    """
    validator = LLMEvidenceValidator(validation_threshold=validation_threshold)
    validator.initialize()
    return validator.validate_semantic_matches(evidence_item, semantic_matches) 