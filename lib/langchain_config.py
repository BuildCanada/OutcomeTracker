#!/usr/bin/env python3
"""
Langchain Configuration Framework for Promise Tracker

This module provides centralized configuration for:
- LLM providers (Gemini)
- Prompt templates
- Chain configurations
- Error handling and retry logic
- Cost tracking and monitoring
"""

import os
import logging
from typing import Dict, List, Optional, Any, Union
from pathlib import Path
import json
from datetime import datetime

from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.prompts import PromptTemplate, ChatPromptTemplate
from langchain_core.output_parsers import JsonOutputParser, StrOutputParser
from langchain_core.runnables import RunnablePassthrough, RunnableLambda
from langchain_core.exceptions import LangChainException
from langchain.callbacks.base import BaseCallbackHandler

# Setup logging
logger = logging.getLogger(__name__)

class CostTrackingCallback(BaseCallbackHandler):
    """Callback to track LLM usage costs and performance."""
    
    def __init__(self):
        self.costs = []
        self.responses = []
        
    def on_llm_start(self, serialized: Dict[str, Any], prompts: List[str], **kwargs) -> None:
        """Track when LLM call starts."""
        self.start_time = datetime.now()
        
    def on_llm_end(self, response, **kwargs) -> None:
        """Track when LLM call ends."""
        end_time = datetime.now()
        duration = (end_time - self.start_time).total_seconds()
        
        # Estimate costs (rough approximation for Gemini)
        # These are estimates - actual costs may vary
        input_tokens = getattr(response, 'prompt_tokens', 0)
        output_tokens = getattr(response, 'completion_tokens', 0)
        
        cost_estimate = (input_tokens * 0.00001) + (output_tokens * 0.00003)  # Rough Gemini pricing
        
        self.costs.append({
            'timestamp': end_time,
            'duration_seconds': duration,
            'input_tokens': input_tokens,
            'output_tokens': output_tokens,
            'cost_estimate_usd': cost_estimate
        })
        
    def get_total_cost(self) -> float:
        """Get total estimated cost."""
        return sum(cost['cost_estimate_usd'] for cost in self.costs)
        
    def get_total_tokens(self) -> Dict[str, int]:
        """Get total token usage."""
        return {
            'input_tokens': sum(cost['input_tokens'] for cost in self.costs),
            'output_tokens': sum(cost['output_tokens'] for cost in self.costs)
        }

class PromiseTrackerLangchain:
    """Main Langchain configuration and management class."""
    
    def __init__(self, api_key: Optional[str] = None, model_name: str = "gemini-2.5-flash-preview-05-20"):
        """Initialize Langchain configuration."""
        self.api_key = api_key or os.getenv('GOOGLE_API_KEY') or os.getenv('GEMINI_API_KEY')
        self.model_name = model_name
        self.cost_tracker = CostTrackingCallback()
        
        if not self.api_key:
            raise ValueError("Google API key not found. Set GOOGLE_API_KEY or GEMINI_API_KEY environment variable.")
        
        # Initialize primary LLM for general operations
        self.llm = ChatGoogleGenerativeAI(
            model=self.model_name,
            google_api_key=self.api_key,
            temperature=0.1,  # Low temperature for consistent results
            max_output_tokens=65536,
            callbacks=[self.cost_tracker]
        )
        
        # Initialize specialized LLM for evidence linking (more powerful model)
        self.linking_llm = ChatGoogleGenerativeAI(
            model="gemini-2.5-pro-preview-05-06",  # More powerful model for complex linking tasks
            google_api_key=self.api_key,
            temperature=0.1,  # Low temperature for consistent results
            max_output_tokens=65536,
            callbacks=[self.cost_tracker]
        )
        
        # Load prompt templates
        self.prompts = self._load_prompt_templates()
        
        # Initialize chains
        self.chains = self._initialize_chains()
        
        logger.info(f"Langchain initialized with model: {self.model_name}")
        logger.info(f"Evidence linking using enhanced model: gemini-2.5-flash-preview-05-20")
    
    def _load_prompt_templates(self) -> Dict[str, PromptTemplate]:
        """Load all prompt templates from the prompts directory."""
        prompts = {}
        prompts_dir = Path(__file__).parent.parent / 'prompts'
        
        # Promise enrichment prompts
        prompts['promise_explanation'] = self._create_promise_explanation_template()
        prompts['promise_keywords'] = self._create_promise_keywords_template()
        prompts['promise_action_type'] = self._create_promise_action_type_template()
        prompts['promise_history'] = self._create_promise_history_template()
        
        # Evidence processing prompts
        prompts['evidence_bill'] = self._load_file_template(prompts_dir / 'prompt_bill_evidence.md')
        prompts['evidence_news'] = self._load_file_template(prompts_dir / 'prompt_news_evidence.md')
        prompts['evidence_gazette'] = self._load_file_template(prompts_dir / 'prompt_gazette2_evidence.md')
        prompts['evidence_oic'] = self._load_file_template(prompts_dir / 'prompt_oic_evidence.md')
        
        # Evidence-promise linking prompts
        prompts['multi_promise_linking'] = self._load_file_template(prompts_dir / 'prompt_link_evidence_to_promise.md')
        
        return prompts
    
    def _load_file_template(self, file_path: Path) -> PromptTemplate:
        """Load a prompt template from a file."""
        try:
            if file_path.exists():
                content = file_path.read_text()
                # Extract variables from template (simple approach)
                return PromptTemplate.from_template(content)
            else:
                logger.warning(f"Prompt file not found: {file_path}")
                return PromptTemplate.from_template("Template not found: {input}")
        except Exception as e:
            logger.error(f"Error loading prompt template {file_path}: {e}")
            return PromptTemplate.from_template("Error loading template: {input}")
    
    def _create_promise_explanation_template(self) -> PromptTemplate:
        """Create the promise explanation template using tested logic from enrich_promises_with_explanation.py."""
        template = """You are a highly skilled policy analyst specializing in Canadian federal government commitments.
        
Your task is to process government commitments and provide clear, comprehensive explanations for Canadian citizens.

For the following government commitment, generate:

1. **concise_title**: A short, descriptive title (5-8 words) that captures the essence of the commitment
2. **what_it_means_for_canadians**: A list of 3-5 specific, concrete impacts or outcomes for Canadian citizens, written in clear, accessible language
3. **description**: A brief summary (1-2 sentences) explaining what the commitment involves  
4. **background_and_context**: Relevant policy background, context, and significance (2-3 sentences)

**Commitment Text**: {promise_text}
**Department**: {department}
**Party**: {party}
**Source Context**: {context}

**Output Requirements:**
- Use clear, accessible language that any Canadian can understand
- Focus on practical impacts and outcomes for citizens
- Be factual and non-partisan
- Each "what_it_means_for_canadians" item should be a complete sentence
- Keep descriptions concise but informative

Return your response as a JSON object:
{{
    "concise_title": "Brief descriptive title",
    "what_it_means_for_canadians": [
        "Specific impact or outcome 1",
        "Specific impact or outcome 2", 
        "Specific impact or outcome 3"
    ],
    "description": "Brief summary of what the commitment involves",
    "background_and_context": "Relevant policy background and context"
}}"""
        
        return PromptTemplate.from_template(template)
    
    def _create_promise_keywords_template(self) -> PromptTemplate:
        """Create the promise keywords extraction template from enrich_tag_new_promise.py."""
        template = """From the following government promise text:

"{promise_text}"

Extract a list of 5-10 key nouns and specific named entities (e.g., program names, specific laws mentioned, key organizations) that represent the core subjects and significant concepts of this promise.

**Output Requirements**:
- Format: Respond with ONLY a valid JSON array of strings.
- Content: Each string should be a distinct keyword or named entity.
- Quantity: Aim for 5 to 10 items. If fewer are truly relevant, provide those. If many are relevant, prioritize the most important.

Example JSON Output:
["Affordable Child Care", "National System", "Early Learning", "$10-a-day", "Provinces and Territories"]

If no specific keywords can be extracted, return an empty JSON array `[]`.
Ensure the output is ONLY the JSON array."""
        
        return PromptTemplate.from_template(template)
    
    def _create_promise_action_type_template(self) -> PromptTemplate:
        """Create the promise action type classification template from enrich_tag_new_promise.py."""
        template = """Analyze the following government promise:

"{promise_text}"

What is the primary type of action being committed to? Choose one from the following list: "legislative", "funding_allocation", "policy_development", "program_launch", "consultation", "international_agreement", "appointment", "other".

**Output Requirements**:
- Format: Respond with ONLY a valid JSON object containing a single key "action_type" whose value is one of the provided action types.
- Content: The value for "action_type" MUST be exactly one of the strings from the list above.

Example JSON Output:
{{
  "action_type": "legislative"
}}

Ensure the output is ONLY the JSON object."""
        
        return PromptTemplate.from_template(template)
    
    def _create_promise_history_template(self) -> PromptTemplate:
        """Create the commitment history rationale template from enrich_tag_new_promise.py."""
        template = """You are a meticulous AI research assistant specializing in Canadian federal government policy and history.

Your task is to analyze Canadian government commitments and construct a factual timeline of key preceding events.

Given the following Canadian government commitment:

**Commitment Text**: "{promise_text}"
**Source Type**: {source_type}
**Announced By**: {entity}
**Date Commitment Announced**: {date_issued}

**Task**:
Construct a timeline of key Canadian federal policies, legislative actions, official announcements, significant public reports, or court decisions that *preceded* and *directly contributed to or motivated* this specific commitment.

Prioritize the **top 2-4 most directly relevant and impactful** federal-level events that demonstrate the context and motivation for this commitment.

For every distinct event in the timeline, provide:
1. The exact date (YYYY-MM-DD) of its publication, announcement, or decision.
2. A concise description of the 'Action' or event.
3. A verifiable 'Source URL' pointing to an official government document, parliamentary record, press release, or a reputable news article about the event.

**Output Requirements**:
- Format: Respond with ONLY a valid JSON array of objects, containing **0 to 4** timeline event objects.
- If no relevant preceding events are found, return an empty array `[]`.
- Object Structure: Each object MUST contain the keys "date" (string, "YYYY-MM-DD"), "action" (string), and "source_url" (string).
- Content: Focus only on concrete, verifiable federal-level events.
- Chronology: Present timeline events chronologically (earliest first), all preceding the 'Date Commitment Announced'.

Example JSON Output:
[
  {{
    "date": "YYYY-MM-DD",
    "action": "Description of a key preceding policy, legislative action, or official announcement.",
    "source_url": "https://example.com/official-source-link1"
  }},
  {{
    "date": "YYYY-MM-DD", 
    "action": "Description of another relevant preceding event.",
    "source_url": "https://example.com/official-source-link2"
  }}
]

If no events are found, return: []"""
        
        return PromptTemplate.from_template(template)
    
    def _create_evidence_linking_template(self) -> PromptTemplate:
        """Create the evidence-promise linking template."""
        template = """You are an expert Canadian government policy analyst. Your task is to determine whether a piece of evidence should be linked to a specific government promise or commitment.

You will be provided with:
1. **Evidence Item**: A government action, announcement, bill, regulation, or other official document
2. **Promise/Commitment**: A government promise or commitment from a mandate letter, platform, or other source

**Evidence Details:**
- Title: {evidence_title}
- Content: {evidence_content}
- Type: {evidence_type}
- Date: {evidence_date}
- Source: {evidence_source}

**Promise Details:**
- Text: {promise_text}
- Party: {promise_party}
- Department: {promise_department}
- Source Type: {promise_source_type}
- Keywords: {promise_keywords}

**Your Task:**
Analyze whether this evidence item represents concrete action taken toward fulfilling the given promise. Consider:

1. **Direct Relevance**: Does the evidence directly address the policy area, objective, or specific action mentioned in the promise?
2. **Substantive Connection**: Is this a meaningful step toward fulfilling the promise (not just tangentially related)?
3. **Chronological Alignment**: Does the evidence occur at an appropriate time relative to when the promise was made?
4. **Scope and Scale**: Does the evidence represent a significant enough action to constitute progress on the promise?

**Evaluation Criteria:**
- **Link**: If the evidence clearly represents concrete action toward fulfilling the promise
- **No Link**: If the evidence is unrelated, tangentially related, or does not represent meaningful progress

**Output Requirements:**
Respond with ONLY a valid JSON object containing:
- "should_link": boolean (true if evidence should be linked to promise, false otherwise)
- "confidence_score": float between 0.0 and 1.0 indicating confidence in the decision
- "rationale": string explaining the reasoning for the decision (2-3 sentences)

Example Output:
{{
  "should_link": true,
  "confidence_score": 0.85,
  "rationale": "The evidence shows the introduction of Bill C-27 which directly addresses the promise to introduce legislation for digital privacy protections. This represents concrete legislative action toward fulfilling the commitment with strong alignment in timing and scope."
}}

Ensure the output is ONLY the JSON object."""
        
        return PromptTemplate.from_template(template)
    
    def _initialize_chains(self) -> Dict[str, Any]:
        """Initialize all Langchain chains."""
        chains = {}
        
        # Promise enrichment chains
        chains['promise_explanation'] = self.prompts['promise_explanation'] | self.llm | JsonOutputParser()
        chains['promise_keywords'] = self.prompts['promise_keywords'] | self.llm | JsonOutputParser()
        chains['promise_action_type'] = self.prompts['promise_action_type'] | self.llm | JsonOutputParser()
        chains['promise_history'] = self.prompts['promise_history'] | self.llm | JsonOutputParser()
        
        # Evidence processing chains
        chains['evidence_bill'] = self.prompts['evidence_bill'] | self.llm | JsonOutputParser()
        chains['evidence_news'] = self.prompts['evidence_news'] | self.llm | JsonOutputParser()
        chains['evidence_gazette'] = self.prompts['evidence_gazette'] | self.llm | JsonOutputParser()
        chains['evidence_oic'] = self.prompts['evidence_oic'] | self.llm | JsonOutputParser()
        
        # Evidence-promise linking chains  
        chains['evidence_linking'] = self._create_evidence_linking_template() | self.linking_llm | JsonOutputParser()
        chains['multi_promise_linking'] = self.prompts['multi_promise_linking'] | self.linking_llm | JsonOutputParser()
        
        return chains
    
    def enrich_promise_explanation(self, promise_text: str, department: str, party: str, context: str = "") -> Dict[str, Any]:
        """Generate explanation for a promise."""
        try:
            result = self.chains['promise_explanation'].invoke({
                'promise_text': promise_text,
                'department': department,
                'party': party,
                'context': context
            })
            return result
        except Exception as e:
            logger.error(f"Error enriching promise explanation: {e}")
            return {'error': str(e)}
    
    def extract_promise_keywords(self, promise_text: str, department: str) -> Dict[str, Any]:
        """Extract keywords and concepts from a promise."""
        try:
            result = self.chains['promise_keywords'].invoke({
                'promise_text': promise_text,
                'department': department
            })
            return result
        except Exception as e:
            logger.error(f"Error extracting promise keywords: {e}")
            return {'error': str(e)}
    
    def classify_promise_action_type(self, promise_text: str) -> Dict[str, Any]:
        """Classify the action type required for a promise."""
        try:
            result = self.chains['promise_action_type'].invoke({
                'promise_text': promise_text
            })
            return result
        except Exception as e:
            logger.error(f"Error classifying promise action type: {e}")
            return {'error': str(e)}
    
    def generate_promise_history(self, promise_text: str, source_type: str, entity: str, date_issued: str) -> Dict[str, Any]:
        """Generate commitment history for a promise."""
        try:
            result = self.chains['promise_history'].invoke({
                'promise_text': promise_text,
                'source_type': source_type,
                'entity': entity,
                'date_issued': date_issued
            })
            return result
        except Exception as e:
            logger.error(f"Error generating promise history: {e}")
            return {'error': str(e)}
    
    def process_evidence_item(self, evidence_type: str, evidence_data: Dict[str, Any]) -> Dict[str, Any]:
        """Process an evidence item based on its type."""
        try:
            chain_name = f'evidence_{evidence_type.lower()}'
            if chain_name in self.chains:
                result = self.chains[chain_name].invoke(evidence_data)
                return result
            else:
                logger.error(f"No chain found for evidence type: {evidence_type}")
                return {'error': f'Unsupported evidence type: {evidence_type}'}
        except Exception as e:
            logger.error(f"Error processing evidence item: {e}")
            return {'error': str(e)}
    
    def link_evidence_to_promise(self, evidence_data: Dict[str, Any], promise_data: Dict[str, Any]) -> Dict[str, Any]:
        """Determine if evidence should be linked to a promise and generate rationale."""
        try:
            # Flatten data for template
            combined_data = {
                'evidence_title': evidence_data.get('title', ''),
                'evidence_content': evidence_data.get('content', ''),
                'evidence_type': evidence_data.get('type', ''),
                'evidence_date': evidence_data.get('date', ''),
                'evidence_source': evidence_data.get('source', ''),
                'promise_text': promise_data.get('text', ''),
                'promise_party': promise_data.get('party', ''),
                'promise_department': promise_data.get('department', ''),
                'promise_source_type': promise_data.get('source_type', ''),
                'promise_keywords': ', '.join(promise_data.get('keywords', [])) if isinstance(promise_data.get('keywords'), list) else str(promise_data.get('keywords', ''))
            }
            result = self.chains['evidence_linking'].invoke(combined_data)
            return result
        except Exception as e:
            logger.error(f"Error linking evidence to promise: {e}")
            return {'error': str(e)}
    
    def link_evidence_to_multiple_promises(self, evidence_data: Dict[str, Any], promises_list: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Link a single evidence item to multiple promises using large-context LLM approach.
        
        Args:
            evidence_data: The evidence item to analyze
            promises_list: List of all promises to evaluate against
            
        Returns:
            LLM analysis result with links found
        """
        try:
            # Prepare evidence data
            evidence_template_data = {
                'evidence_source_type': evidence_data.get('evidence_source_type', 'Unknown'),
                'evidence_date': evidence_data.get('evidence_date', evidence_data.get('date', 'Unknown')),
                'evidence_title_or_summary': evidence_data.get('title_or_summary', evidence_data.get('title', '')),
                'evidence_description_or_details': evidence_data.get('description_or_details', evidence_data.get('description', '')),
                'parliament_session_id': evidence_data.get('parliament_session_id', 'Unknown')
            }
            
            # Prepare promises data for template
            promises_for_template = []
            for promise in promises_list:
                promises_for_template.append({
                    "promise_id": promise.get('promise_id', promise.get('_doc_id', 'Unknown')),
                    "text": promise.get('text', ''),
                    "description": promise.get('description', ''),
                    "background_and_context": promise.get('background_and_context', ''),
                    "reporting_lead_title": promise.get('reporting_lead_title', '')
                })
            
            # Combine template data
            template_data = evidence_template_data.copy()
            template_data['promises_json_list'] = json.dumps(promises_for_template, indent=2)
            
            # Invoke the multi-promise linking chain
            result = self.chains['multi_promise_linking'].invoke(template_data)
            return result
            
        except Exception as e:
            logger.error(f"Error linking evidence to multiple promises: {e}")
            return {'error': str(e)}
    
    def get_cost_summary(self) -> Dict[str, Any]:
        """Get cost and usage summary."""
        return {
            'total_cost_usd': self.cost_tracker.get_total_cost(),
            'total_tokens': self.cost_tracker.get_total_tokens(),
            'model_name': self.model_name,
            'total_calls': len(self.cost_tracker.costs)
        }

# Global instance (singleton pattern)
_langchain_instance = None

def get_langchain_instance() -> PromiseTrackerLangchain:
    """Get or create the global Langchain instance."""
    global _langchain_instance
    if _langchain_instance is None:
        _langchain_instance = PromiseTrackerLangchain()
    return _langchain_instance

# Convenience functions
def enrich_promise_explanation(promise_text: str, department: str, party: str, context: str = "") -> Dict[str, Any]:
    """Convenience function for promise explanation."""
    return get_langchain_instance().enrich_promise_explanation(promise_text, department, party, context)

def extract_promise_keywords(promise_text: str, department: str) -> Dict[str, Any]:
    """Convenience function for keyword extraction."""
    return get_langchain_instance().extract_promise_keywords(promise_text, department)

def classify_promise_action_type(promise_text: str) -> Dict[str, Any]:
    """Convenience function for action type classification."""
    return get_langchain_instance().classify_promise_action_type(promise_text)

def process_evidence_item(evidence_type: str, evidence_data: Dict[str, Any]) -> Dict[str, Any]:
    """Convenience function for evidence processing."""
    return get_langchain_instance().process_evidence_item(evidence_type, evidence_data)

def link_evidence_to_promise(evidence_data: Dict[str, Any], promise_data: Dict[str, Any]) -> Dict[str, Any]:
    """Convenience function for evidence-promise linking."""
    return get_langchain_instance().link_evidence_to_promise(evidence_data, promise_data)

def link_evidence_to_multiple_promises(evidence_data: Dict[str, Any], promises_list: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Convenience function for multi-promise evidence linking."""
    return get_langchain_instance().link_evidence_to_multiple_promises(evidence_data, promises_list) 