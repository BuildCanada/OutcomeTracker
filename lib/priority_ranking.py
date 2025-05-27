#!/usr/bin/env python3
"""
Priority Ranking Module

Wrapper for the existing priority ranking logic from rank_promise_priority.py
to integrate with the Langchain-based pipeline.
"""

import os
import sys
import logging
from typing import Dict, List, Optional, Any
from pathlib import Path

import google.generativeai as genai
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Setup logging
logger = logging.getLogger(__name__)

class PromisePriorityRanker:
    """Wrapper class for promise priority ranking."""
    
    def __init__(self):
        """Initialize the priority ranker."""
        self.api_key = os.getenv("GEMINI_API_KEY")
        if not self.api_key:
            logger.warning("GEMINI_API_KEY not found - priority ranking will not be available")
            self.model = None
            return
            
        try:
            genai.configure(api_key=self.api_key)
            self.model = genai.GenerativeModel(
                model_name=os.getenv("GEMINI_MODEL_NAME", "models/gemini-2.5-flash-preview-05-20"),
                generation_config={
                    "temperature": 0.1,
                    "top_p": 0.95,
                    "top_k": 64,
                    "max_output_tokens": 65536,
                    "response_mime_type": "application/json",
                },
                system_instruction="You are the Build-Canada Mandate Scorer. You are an expert in Canadian policy and economics. Provide only fact-based, neutral analysis without opinions or subjective language."
            )
            logger.info("Priority ranker initialized successfully")
        except Exception as e:
            logger.warning(f"Failed to initialize priority ranker: {e}")
            self.model = None
    
    def rank_promise(self, promise_text: str, department: str, keywords: List[str]) -> Optional[Dict[str, Any]]:
        """
        Rank a promise using the same logic as rank_promise_priority.py
        """
        if not self.model:
            logger.warning("Priority ranker not available (model not initialized)")
            return None
            
        try:
            # Load the same prompt files as the main ranking script
            import os
            from pathlib import Path
            
            prompts_dir = Path(__file__).parent.parent / 'prompts'
            
            # Load Build Canada tenets
            tenets_path = prompts_dir / 'build_canada_tenets.txt'
            if not tenets_path.exists():
                logger.error("Build Canada tenets file not found")
                return None
            tenets_text = tenets_path.read_text()
            
            # Load detailed instructions
            instructions_path = prompts_dir / 'detailed_rating_instructions.md'
            if not instructions_path.exists():
                logger.error("Detailed rating instructions file not found")
                return None
            instructions_text = instructions_path.read_text()
            
            # Load economic context (default to 2025 platform)
            economic_context_path = prompts_dir / 'economic_contexts' / '2025_platform.txt'
            if economic_context_path.exists():
                economic_context_text = economic_context_path.read_text()
                context_name = "2025 Federal Election"
            else:
                # Fallback to a generic context
                economic_context_text = "Current Canadian federal election context focusing on economic growth and competitiveness."
                context_name = "Federal Election"
            
            # Construct the full prompt using the same structure as rank_promise_priority.py
            user_prompt = f"You will be provided with a government commitment, Build Canada Core Tenets, the Election Economic Context, and detailed scoring instructions.\n\n"
            user_prompt += f"== Build Canada Core Tenets ==\n{tenets_text}\n\n"
            user_prompt += f"== Election Economic Context: {context_name} ==\n{economic_context_text}\n\n"
            user_prompt += f"== Government Commitment to Evaluate ==\n```text\n{promise_text}\n```\n\n"
            user_prompt += f"== Detailed Scoring Instructions (Task, Scoring Criteria, Method, Guidance, Examples) ==\n{instructions_text}"
            
            response = self.model.generate_content(user_prompt)
            
            # Parse JSON response (same logic as rank_promise_priority.py)
            import re
            import json
            
            raw_response_text = response.text
            logger.debug(f"Raw LLM response text: {raw_response_text}")
            
            # Try to find JSON within ```json ... ``` if present
            match = re.search(r"```json\n(.*\n)```", raw_response_text, re.DOTALL)
            if match:
                json_text = match.group(1).strip()
            else:
                # Clean and extract JSON
                json_text = raw_response_text.strip()
                if not json_text.startswith("{") or not json_text.endswith("}"):
                    first_brace = json_text.find('{')
                    last_brace = json_text.rfind('}')
                    if first_brace != -1 and last_brace != -1 and last_brace > first_brace:
                        json_text = json_text[first_brace:last_brace+1]
                    else:
                        logger.warning("Could not reliably extract JSON object from response.")
                        return None
            
            parsed_json = json.loads(json_text)
            
            # Validate the required fields match rank_promise_priority.py
            required_fields = ['bc_promise_rank', 'bc_promise_direction', 'bc_promise_rank_rationale']
            if all(key in parsed_json for key in required_fields):
                # Validate values
                rank_val = parsed_json['bc_promise_rank']
                direction_val = parsed_json['bc_promise_direction']
                
                if rank_val not in ['strong', 'medium', 'weak']:
                    logger.warning(f"Invalid rank value: {rank_val}")
                    return None
                    
                if direction_val not in ['positive', 'negative', 'neutral']:
                    logger.warning(f"Invalid direction value: {direction_val}")
                    return None
                
                return {
                    'bc_promise_rank': rank_val,
                    'bc_promise_direction': direction_val,
                    'bc_promise_rank_rationale': parsed_json['bc_promise_rank_rationale']
                }
            else:
                logger.warning(f"Missing required fields in response: {parsed_json}")
                return None
                
        except Exception as e:
            logger.error(f"Error in priority ranking: {e}")
            return None
    
    def is_available(self) -> bool:
        """Check if priority ranking is available."""
        return self.model is not None 