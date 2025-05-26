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
        
        # Initialize LLM
        self.llm = ChatGoogleGenerativeAI(
            model=self.model_name,
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
        prompts['evidence_linking'] = self._load_file_template(prompts_dir / 'prompt_add_evidence_items_to_promises.md')
        
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
        """Create the promise explanation template."""
        template = """You are a policy analyst helping to explain Canadian federal government promises.

Given the following promise information, provide a clear, comprehensive explanation:

Promise Text: {promise_text}
Department: {department}
Party: {party}
Context: {context}

Please provide:
1. **What it means**: A clear explanation of what this promise entails
2. **Background and context**: Relevant background information and policy context
3. **Key components**: Main elements or steps involved
4. **Potential impact**: Who would be affected and how

Return your response as a JSON object with the following structure:
{{
    "what_it_means": "Clear explanation of the promise",
    "background_and_context": "Relevant background and policy context",
    "key_components": ["Component 1", "Component 2", "Component 3"],
    "potential_impact": "Description of potential impact"
}}"""
        
        return PromptTemplate.from_template(template)
    
    def _create_promise_keywords_template(self) -> PromptTemplate:
        """Create the promise keywords extraction template."""
        template = """Extract key concepts and keywords from this Canadian federal government promise.

Promise Text: {promise_text}
Department: {department}

Extract:
1. Policy areas (e.g., healthcare, environment, economy)
2. Key actions (e.g., implement, increase, create, reduce)
3. Target groups (e.g., families, seniors, businesses)
4. Important concepts and terms

Return as a JSON object:
{{
    "policy_areas": ["area1", "area2"],
    "actions": ["action1", "action2"],
    "target_groups": ["group1", "group2"],
    "key_concepts": ["concept1", "concept2"]
}}"""
        
        return PromptTemplate.from_template(template)
    
    def _create_promise_action_type_template(self) -> PromptTemplate:
        """Create the promise action type classification template."""
        template = """Classify the type of action required for this Canadian federal government promise.

Promise Text: {promise_text}

Classify into one of these categories:
- legislative: Requires new laws or amendments to existing laws
- funding_allocation: Requires budget allocation or spending
- policy_development: Requires new policies or policy changes
- program_launch: Requires creating new programs or services
- consultation: Requires stakeholder consultation or engagement
- international_agreement: Requires international negotiations or agreements
- appointment: Requires appointments to positions or bodies
- other: Other types of actions

Return as a JSON object:
{{
    "action_type": "category_name",
    "confidence": 0.95,
    "rationale": "Explanation of why this classification was chosen"
}}"""
        
        return PromptTemplate.from_template(template)
    
    def _create_promise_history_template(self) -> PromptTemplate:
        """Create the promise commitment history template."""
        template = """Analyze the commitment history and context for this Canadian federal government promise.

Promise Text: {promise_text}
Party: {party}
Election/Mandate Year: {year}
Department: {department}

Please provide:
1. Historical context of similar commitments
2. Past attempts or related initiatives
3. Political significance
4. Implementation challenges or considerations

Return as a JSON object:
{{
    "historical_context": "Background on similar past commitments",
    "past_initiatives": "Related previous initiatives or attempts",
    "political_significance": "Why this commitment is politically important",
    "implementation_notes": "Key considerations for implementation"
}}"""
        
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
        chains['evidence_linking'] = self.prompts['evidence_linking'] | self.llm | JsonOutputParser()
        
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
    
    def generate_promise_history(self, promise_text: str, party: str, year: str, department: str) -> Dict[str, Any]:
        """Generate commitment history for a promise."""
        try:
            result = self.chains['promise_history'].invoke({
                'promise_text': promise_text,
                'party': party,
                'year': year,
                'department': department
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
            combined_data = {
                'evidence': evidence_data,
                'promise': promise_data
            }
            result = self.chains['evidence_linking'].invoke(combined_data)
            return result
        except Exception as e:
            logger.error(f"Error linking evidence to promise: {e}")
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