#!/usr/bin/env python3
"""
Consolidated Promise Enrichment Script - CORRECTED VERSION

This script addresses all quality issues:
1. Uses exact original prompt language from working scripts
2. Restores proper field structure (arrays vs strings)
3. Removes unwanted fields (implementation_notes, key_points, migration_metadata, political_significance)
4. Allows longer concise_title
5. Uses original background_and_context and commitment_history_rationale prompts
"""

import sys
import os
sys.path.append('..')

import firebase_admin
from firebase_admin import credentials, firestore
import logging
import json
import asyncio
from datetime import datetime
import argparse
from dotenv import load_dotenv
import time
import re
import google.generativeai as genai

# Load environment variables
load_dotenv()

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Constants
PROMISES_COLLECTION_ROOT = "promises"

# Action types from original script
ACTION_TYPES_LIST = [
    "legislative", "funding_allocation", "policy_development", 
    "program_launch", "consultation", "international_agreement", 
    "appointment", "other"
]

class CorrectedPromiseEnricher:
    """Fully corrected promise enricher using original prompts and field structure."""
    
    def __init__(self):
        """Initialize the enricher with the original Gemini configuration."""
        self.model_name = os.getenv("GEMINI_MODEL_NAME_EXPLANATION_ENRICHMENT", "models/gemini-2.5-flash-preview-05-20")
        self.db = self._initialize_firebase()
        self._initialize_gemini()
        self.stats = {
            'total_processed': 0,
            'explanations_generated': 0,
            'keywords_extracted': 0,
            'action_types_classified': 0,
            'history_generated': 0,
            'errors': 0
        }
    
    def _initialize_firebase(self):
        """Initialize Firebase if not already initialized."""
        try:
            app = firebase_admin.get_app()
            logger.info("Firebase already initialized")
        except ValueError:
            cred = credentials.ApplicationDefault()
            app = firebase_admin.initialize_app(cred)
            logger.info("Firebase initialized")
        
        return firestore.client()
    
    def _initialize_gemini(self):
        """Initialize Gemini client exactly like the working script."""
        api_key = os.getenv("GOOGLE_API_KEY") or os.getenv("GEMINI_API_KEY")
        if not api_key:
            raise ValueError("No API key found in environment variables")
        
        # Configure the client and create model exactly like working script
        genai.configure(api_key=api_key)
        
        # Generation config from working script
        generation_config = {
            "temperature": 0.1,
            "top_p": 0.95,
            "top_k": 64,
            "max_output_tokens": 65536, 
            "response_mime_type": "application/json",
        }
        
        # Create the generative model instance
        self.generative_model = genai.GenerativeModel(
            model_name=self.model_name,
            generation_config=generation_config,
        )
        
        logger.info(f"Initialized Gemini model: {self.model_name}")
    
    def _clean_json_from_markdown(self, text: str) -> str:
        """Clean JSON from markdown formatting."""
        # Remove markdown code blocks
        text = re.sub(r'```json\n?', '', text)
        text = re.sub(r'```\n?', '', text)
        text = text.strip()
        return text
    
    async def load_explanation_prompt(self) -> str:
        """Load the original explanation prompt exactly as it was."""
        prompt_path = os.path.join("prompts", "prompt_generate_whatitmeans.md")
        try:
            with open(prompt_path, 'r', encoding='utf-8') as f:
                return f.read()
        except FileNotFoundError:
            logger.error(f"Prompt file not found: {prompt_path}")
            raise
    
    async def generate_explanations_batch(self, promises_data: list[dict]) -> list[dict]:
        """Generate explanations for a batch of promises using EXACT original prompt."""
        if not promises_data:
            return []
        
        base_prompt = await self.load_explanation_prompt()
        
        # Build the commitments section exactly like the original
        commitments_section_header = "\n\n**Commitments to Process:**\n"
        commitments_list_str = ""
        for promise in promises_data:
            commitments_list_str += f"* {promise['text']}\n"
        
        full_prompt = base_prompt + commitments_section_header + commitments_list_str
        
        try:
            logger.info(f"Sending {len(promises_data)} promises to LLM for explanation generation")
            
            response = await self.generative_model.generate_content_async(
                full_prompt
            )
            
            # Handle safety-filtered responses
            if not response.candidates or not response.candidates[0].content.parts:
                finish_reason = response.candidates[0].finish_reason if response.candidates else "UNKNOWN"
                logger.warning(f"LLM explanation response was filtered. Finish reason: {finish_reason}")
                return []
            
            raw_response_text = response.text
            cleaned_response_text = self._clean_json_from_markdown(raw_response_text)
            llm_output = json.loads(cleaned_response_text)
            
            if not isinstance(llm_output, list):
                logger.error(f"LLM output is not a list. Type: {type(llm_output)}")
                return []
            
            # Validate structure matches original expectations
            validated_output = []
            for item in llm_output:
                if (isinstance(item, dict) and 
                    "commitment_text" in item and 
                    "concise_title" in item and 
                    "what_it_means_for_canadians" in item and 
                    "description" in item and 
                    "background_and_context" in item):
                    
                    # Validate field types match original structure
                    if (isinstance(item["what_it_means_for_canadians"], list) and
                        isinstance(item["description"], str) and
                        isinstance(item["background_and_context"], str)):
                        validated_output.append(item)
                    else:
                        logger.warning(f"LLM output item has incorrect field types: {str(item)[:200]}")
                else:
                    logger.warning(f"LLM output item has incorrect structure: {str(item)[:200]}")
            
            self.stats['explanations_generated'] += len(validated_output)
            return validated_output
            
        except Exception as e:
            logger.error(f"Error in explanation generation: {e}")
            self.stats['errors'] += 1
            return []
    
    async def generate_commitment_history(self, promise_text: str, source_type: str, entity: str, date_issued: str) -> list:
        """Generate commitment history using EXACT original prompt and return array structure."""
        logger.debug(f"Generating commitment history for promise: {promise_text[:70]}...")
        date_issued_str = date_issued or 'Unknown'

        # EXACT prompt from original enrich_tag_new_promise.py
        prompt = f"""Given the following Canadian government commitment:

Commitment Text:
\"\"\"
{promise_text}
\"\"\"

Source Type: {source_type or 'Unknown'}
Announced By: {entity or 'Unknown'}
Date Commitment Announced: {date_issued_str}

Task:
Construct a timeline of key Canadian federal policies, legislative actions, official announcements, significant public reports, or court decisions that *preceded* and *directly contributed to or motivated* this specific commitment.
Prioritize the **top 2-4 most directly relevant and impactful** federal-level events that demonstrate the context and motivation for this commitment.
For every distinct event in the timeline, provide:
1.  The exact date (YYYY-MM-DD) of its publication, announcement, or decision.
2.  A concise description of the 'Action' or event.
3.  A verifiable 'Source URL' pointing to an official government document, parliamentary record, press release, or a reputable news article about the event.

Output Requirements:
*   Format: Respond with ONLY a valid JSON array of objects, containing **0 to 4** timeline event objects. If no relevant preceding events are found, return an empty array `[]`.
*   Object Structure: Each object MUST contain the keys "date" (string, "YYYY-MM-DD"), "action" (string), and "source_url" (string).
*   Content: Focus only on concrete, verifiable federal-level events.
*   Chronology: Present timeline events chronologically (earliest first), all preceding the 'Date Commitment Announced' ({date_issued_str}).

Example JSON Output (should be an array of objects like this):
```json
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
```
If no events are found, return:
```json
[]
```
Ensure the output is ONLY the JSON array.
"""

        try:
            response = await self.generative_model.generate_content_async(
                prompt
            )

            raw_response_text = response.text
            cleaned_response_text = self._clean_json_from_markdown(raw_response_text)
            timeline_events = json.loads(cleaned_response_text)

            if not isinstance(timeline_events, list):
                logger.warning(f"LLM history response was not a JSON list for promise: {promise_text[:70]}. Response: {response.text}")
                return []
            
            if not timeline_events:  # Empty list is valid
                logger.debug(f"LLM returned an empty list for history (0 events found) for promise: {promise_text[:70]}.")
                return []

            if not (0 <= len(timeline_events) <= 4):  # Allow 0-4 events
                logger.warning(f"LLM history response list length ({len(timeline_events)}) is not 0-4 for promise: {promise_text[:70]}. Response: {response.text}")
                return []

            validated_events = []
            for i, event in enumerate(timeline_events):
                if not (isinstance(event, dict) and 
                        all(key in event for key in ["date", "action", "source_url"]) and
                        isinstance(event.get("date"), str) and
                        isinstance(event.get("action"), str) and
                        isinstance(event.get("source_url"), str) and
                        re.match(r"^\d{4}-\d{2}-\d{2}$", event["date"])):
                    logger.warning(f"Invalid event structure in LLM history response for promise: {promise_text[:70]}. Event {i}: {event}. Full response: {response.text}")
                    return []  # One bad event invalidates all
                validated_events.append(event)
            
            logger.debug(f"Successfully parsed commitment history: {validated_events}")
            self.stats['history_generated'] += 1
            return validated_events

        except json.JSONDecodeError as json_err:
            logger.warning(f"LLM history response was not valid JSON for promise: {promise_text[:70]}. Error: {json_err}. Raw Response: \n{response.text if 'response' in locals() else 'N/A'}")
            return []
        except Exception as e:
            logger.error(f"Error calling Gemini for commitment history: {e}. Promise: {promise_text[:70]}", exc_info=True)
            return []
    
    async def extract_keywords(self, promise_text: str) -> list[str]:
        """Extract keywords using EXACT original prompt."""
        logger.debug(f"Extracting keywords for promise: {promise_text[:70]}...")
        
        # EXACT prompt from original enrich_tag_new_promise.py
        prompt = f"""From the following government promise text:
\"\"\"
{promise_text}
\"\"\"
Extract a list of 5-10 key nouns and specific named entities (e.g., program names, specific laws mentioned, key organizations) that represent the core subjects and significant concepts of this promise.

Output Requirements:
*   Format: Respond with ONLY a valid JSON array of strings.
*   Content: Each string should be a distinct keyword or named entity.
*   Quantity: Aim for 5 to 10 items. If fewer are truly relevant, provide those. If many are relevant, prioritize the most important.

Example JSON Output:
```json
["Affordable Child Care", "National System", "Early Learning", "$10-a-day", "Provinces and Territories"]
```
If no specific keywords can be extracted, return an empty JSON array `[]`.
Ensure the output is ONLY the JSON array.
"""
        try:
            response = await self.generative_model.generate_content_async(
                prompt
            )
            
            raw_response_text = response.text
            cleaned_response_text = self._clean_json_from_markdown(raw_response_text)
            keywords = json.loads(cleaned_response_text)

            if not isinstance(keywords, list) or not all(isinstance(k, str) for k in keywords):
                logger.warning(f"LLM keyword extraction did not return a valid list of strings. Promise: {promise_text[:70]}. Response: {response.text}")
                return []  # Default to empty list on bad structure
            
            logger.debug(f"Extracted keywords: {keywords}")
            self.stats['keywords_extracted'] += 1
            return keywords
        except json.JSONDecodeError as e:
            logger.error(f"Error decoding JSON from Gemini keyword response: {e}. Promise: {promise_text[:70]}. Response text: {response.text if 'response' in locals() else 'N/A'}", exc_info=True)
            return []
        except Exception as e:
            logger.error(f"Error calling Gemini for keyword extraction: {e}. Promise: {promise_text[:70]}", exc_info=True)
            return []
    
    async def classify_action_type(self, promise_text: str) -> str:
        """Classify action type using EXACT original prompt."""
        logger.debug(f"Inferring action type for promise: {promise_text[:70]}...")
        action_types_string = ", ".join([f'"{t}"' for t in ACTION_TYPES_LIST])  # Quote for JSON style

        # EXACT prompt from original enrich_tag_new_promise.py
        prompt = f"""Analyze the following government promise:
\"\"\"
{promise_text}
\"\"\"
What is the primary type of action being committed to? Choose one from the following list: {action_types_string}.

Output Requirements:
*   Format: Respond with ONLY a valid JSON object containing a single key "action_type" whose value is one of the provided action types.
*   Content: The value for "action_type" MUST be exactly one of the strings from the list: {action_types_string}.

Example JSON Output:
```json
{{
  "action_type": "legislative"
}}
```
Ensure the output is ONLY the JSON object.
"""
        try:
            response = await self.generative_model.generate_content_async(
                prompt
            )
            
            raw_response_text = response.text
            cleaned_response_text = self._clean_json_from_markdown(raw_response_text)
            data = json.loads(cleaned_response_text)

            if isinstance(data, dict) and "action_type" in data and data["action_type"] in ACTION_TYPES_LIST:
                action_type = data["action_type"]
                logger.debug(f"Inferred action type: {action_type}")
                self.stats['action_types_classified'] += 1
                return action_type
            else:
                logger.warning(f"Gemini action type classification returned an unknown or badly formatted type. Promise: {promise_text[:70]}. Response: {response.text}. Defaulting to 'other'.")
                # Attempt to find a match even if there's extra content
                raw_response_text = response.text.lower()
                for valid_type in ACTION_TYPES_LIST:
                    if f'"{valid_type}"' in raw_response_text:  # Check for quoted type in raw string
                        logger.info(f"Found valid action type '{valid_type}' via fallback search in: '{raw_response_text}'. Using '{valid_type}'.")
                        self.stats['action_types_classified'] += 1
                        return valid_type
                return "other"
        except json.JSONDecodeError as e:
            logger.error(f"Error decoding JSON from Gemini action type response: {e}. Promise: {promise_text[:70]}. Response text: {response.text if 'response' in locals() else 'N/A'}", exc_info=True)
            return "other"
        except Exception as e:
            logger.error(f"Error calling Gemini for action type classification: {e}. Promise: {promise_text[:70]}", exc_info=True)
            return "other"
    
    async def enrich_promise(self, promise_id: str, promise_data: dict, enrichment_types: list[str], force_reprocessing: bool = False) -> bool:
        """Enrich a single promise with the specified enrichment types."""
        try:
            update_payload = {}
            made_changes = False
            
            # 1. EXPLANATION enrichment (concise_title, description, what_it_means_for_canadians, background_and_context)
            if 'explanation' in enrichment_types:
                needs_explanation = (force_reprocessing or 
                                   'explanation_enriched_at' not in promise_data or 
                                   promise_data.get('explanation_enriched_at') is None)
                
                if needs_explanation:
                    logger.info(f"Generating explanation for promise: {promise_id}")
                    explanations = await self.generate_explanations_batch([promise_data])
                    
                    if explanations and len(explanations) > 0:
                        explanation = explanations[0]  # Single promise batch
                        
                        # CORRECTED: Allow longer concise_title
                        update_payload['concise_title'] = explanation.get('concise_title', '')
                        update_payload['description'] = explanation.get('description', '')
                        update_payload['what_it_means_for_canadians'] = explanation.get('what_it_means_for_canadians', [])
                        update_payload['background_and_context'] = explanation.get('background_and_context', '')
                        update_payload['explanation_enriched_at'] = firestore.SERVER_TIMESTAMP
                        made_changes = True
                        
                        logger.info(f"Successfully generated explanation for promise: {promise_id}")
                    else:
                        logger.warning(f"Failed to generate explanation for promise: {promise_id}")
                        self.stats['errors'] += 1
            
            # 2. KEYWORDS enrichment
            if 'keywords' in enrichment_types:
                needs_keywords = (force_reprocessing or 
                                'keywords_enriched_at' not in promise_data or 
                                promise_data.get('keywords_enriched_at') is None)
                
                if needs_keywords:
                    logger.info(f"Extracting keywords for promise: {promise_id}")
                    keywords = await self.extract_keywords(promise_data['text'])
                    
                    if keywords is not None:
                        update_payload['extracted_keywords_concepts'] = keywords
                        update_payload['keywords_enriched_at'] = firestore.SERVER_TIMESTAMP
                        made_changes = True
                        
                        logger.info(f"Successfully extracted keywords for promise: {promise_id}")
                    else:
                        logger.warning(f"Failed to extract keywords for promise: {promise_id}")
                        self.stats['errors'] += 1
            
            # 3. ACTION TYPE enrichment
            if 'action_type' in enrichment_types:
                needs_action_type = (force_reprocessing or 
                                   'action_type_enriched_at' not in promise_data or 
                                   promise_data.get('action_type_enriched_at') is None)
                
                if needs_action_type:
                    logger.info(f"Classifying action type for promise: {promise_id}")
                    action_type = await self.classify_action_type(promise_data['text'])
                    
                    if action_type:
                        update_payload['implied_action_type'] = action_type
                        update_payload['action_type_enriched_at'] = firestore.SERVER_TIMESTAMP
                        made_changes = True
                        
                        logger.info(f"Successfully classified action type for promise: {promise_id}")
                    else:
                        logger.warning(f"Failed to classify action type for promise: {promise_id}")
                        self.stats['errors'] += 1
            
            # 4. HISTORY enrichment (commitment_history_rationale)
            if 'history' in enrichment_types:
                needs_history = (force_reprocessing or 
                               'commitment_history_rationale' not in promise_data or 
                               promise_data.get('commitment_history_rationale') is None)
                
                if needs_history:
                    logger.info(f"Generating commitment history for promise: {promise_id}")
                    history = await self.generate_commitment_history(
                        promise_data['text'],
                        promise_data.get('source_type', ''),
                        promise_data.get('candidate_or_government', ''),
                        promise_data.get('date_issued', '')
                    )
                    
                    if history is not None:
                        update_payload['commitment_history_rationale'] = history
                        update_payload['history_generated_at'] = firestore.SERVER_TIMESTAMP
                        made_changes = True
                        
                        logger.info(f"Successfully generated commitment history for promise: {promise_id}")
                    else:
                        logger.warning(f"Failed to generate commitment history for promise: {promise_id}")
                        self.stats['errors'] += 1
            
            # CORRECTED: Clean up unwanted fields if they exist
            remove_fields = ['implementation_notes', 'key_points', 'migration_metadata', 'political_significance']
            for field in remove_fields:
                if field in promise_data:
                    update_payload[field] = firestore.DELETE_FIELD
                    made_changes = True
                    logger.info(f"Removing unwanted field '{field}' from promise: {promise_id}")
            
            # Apply updates
            if made_changes and update_payload:
                doc_ref = self.db.collection(PROMISES_COLLECTION_ROOT).document(promise_id)
                doc_ref.update(update_payload)
                logger.info(f"Successfully updated promise: {promise_id}")
                self.stats['total_processed'] += 1
                return True
            else:
                logger.info(f"No updates needed for promise: {promise_id}")
                return False
                
        except Exception as e:
            logger.error(f"Error enriching promise {promise_id}: {e}")
            self.stats['errors'] += 1
            return False
    
    async def process_promises(self, parliament_session_id: int = None, source_type: str = None, 
                             limit: int = None, force_reprocessing: bool = False,
                             enrichment_types: list[str] = None) -> dict:
        """Process multiple promises with the specified filters and enrichment types."""
        
        if enrichment_types is None:
            enrichment_types = ['explanation', 'keywords', 'action_type', 'history']
        
        logger.info(f"Starting promise enrichment with filters:")
        logger.info(f"  Parliament Session ID: {parliament_session_id}")
        logger.info(f"  Source Type: {source_type}")
        logger.info(f"  Limit: {limit}")
        logger.info(f"  Force Reprocessing: {force_reprocessing}")
        logger.info(f"  Enrichment Types: {enrichment_types}")
        
        # Build query
        query = self.db.collection(PROMISES_COLLECTION_ROOT)
        
        if parliament_session_id is not None:
            # Convert to string to match Firestore storage format
            query = query.where('parliament_session_id', '==', str(parliament_session_id))
        
        if source_type is not None:
            query = query.where('source_type', '==', source_type)
        
        if limit is not None:
            query = query.limit(limit)
        
        # Execute query
        docs = query.get()
        total_docs = len(docs)
        
        logger.info(f"Found {total_docs} promises to process")
        
        processed_count = 0
        success_count = 0
        
        for doc in docs:
            promise_id = doc.id
            promise_data = doc.to_dict()
            
            logger.info(f"Processing promise {processed_count + 1}/{total_docs}: {promise_id}")
            
            success = await self.enrich_promise(promise_id, promise_data, enrichment_types, force_reprocessing)
            if success:
                success_count += 1
            
            processed_count += 1
            
            # Rate limiting (reduced for better performance)
            await asyncio.sleep(0.2)
        
        return {
            'total_found': total_docs,
            'total_processed': processed_count,
            'successful_updates': success_count,
            'stats': self.stats
        }


async def main():
    """Main function."""
    parser = argparse.ArgumentParser(description='Consolidated Promise Enrichment Script - CORRECTED')
    parser.add_argument('--parliament_session_id', type=int, help='Filter by parliament session ID')
    parser.add_argument('--source_type', type=str, help='Filter by source type')
    parser.add_argument('--limit', type=int, help='Limit number of promises to process')
    parser.add_argument('--force_reprocessing', action='store_true', help='Force reprocessing of existing enrichments')
    parser.add_argument('--enrichment_types', nargs='+', choices=['explanation', 'keywords', 'action_type', 'history', 'all'],
                        default=['all'], help='Types of enrichment to perform')
    
    args = parser.parse_args()
    
    # Handle 'all' enrichment type
    if 'all' in args.enrichment_types:
        enrichment_types = ['explanation', 'keywords', 'action_type', 'history']
    else:
        enrichment_types = args.enrichment_types
    
    enricher = CorrectedPromiseEnricher()
    
    start_time = time.time()
    
    results = await enricher.process_promises(
        parliament_session_id=args.parliament_session_id,
        source_type=args.source_type,
        limit=args.limit,
        force_reprocessing=args.force_reprocessing,
        enrichment_types=enrichment_types
    )
    
    end_time = time.time()
    duration = end_time - start_time
    
    print("\n" + "="*60)
    print("CORRECTED PROMISE ENRICHMENT RESULTS")
    print("="*60)
    print(f"Total Found: {results['total_found']}")
    print(f"Total Processed: {results['total_processed']}")
    print(f"Successful Updates: {results['successful_updates']}")
    print(f"Duration: {duration:.2f} seconds")
    print("\nDetailed Stats:")
    for key, value in results['stats'].items():
        print(f"  {key}: {value}")
    print("="*60)


if __name__ == "__main__":
    asyncio.run(main()) 