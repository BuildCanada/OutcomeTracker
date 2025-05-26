#!/usr/bin/env python3
"""
Consolidated Promise Enrichment Script - FIXED VERSION

This script restores the original field structure and prompt quality
by using the optimized prompts from the working legacy scripts.
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
from google import genai

# Load environment variables
load_dotenv()

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Constants
PROMISES_COLLECTION_ROOT = "promises"
TARGET_SOURCE_TYPES = ["2021 LPC Mandate Letters", "2025 LPC Platform"]
RATE_LIMIT_DELAY_SECONDS = 2

# Action types list - from original script
ACTION_TYPES_LIST = [
    "legislative", "funding_allocation", "policy_development", 
    "program_launch", "consultation", "international_agreement", 
    "appointment", "other"
]

class FixedPromiseEnricher:
    """Restored promise enricher using original field structure and prompts."""
    
    def __init__(self):
        """Initialize the enricher with the original Gemini configuration."""
        self.model_name = os.getenv("GEMINI_MODEL_NAME_EXPLANATION_ENRICHMENT", "models/gemini-2.5-flash-preview-05-20")
        self.db = self._initialize_firebase()
        self.client = self._initialize_gemini()
        self.stats = {
            'total_processed': 0,
            'explanations_generated': 0,
            'keywords_extracted': 0,
            'action_types_classified': 0,
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
        """Initialize Gemini client."""
        try:
            gemini_api_key = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
            if not gemini_api_key:
                raise ValueError("No Gemini API key found")
            
            if "GOOGLE_API_KEY" not in os.environ:
                os.environ["GOOGLE_API_KEY"] = gemini_api_key
            
            client = genai.Client()
            logger.info(f"Successfully initialized Gemini Client with model {self.model_name}")
            return client
        except Exception as e:
            logger.critical(f"Failed to initialize Gemini client: {e}")
            raise
    
    async def query_promises_for_enrichment(self, parliament_session_id: str, source_type: str = None, 
                                          limit: int = None, force_reprocessing: bool = False) -> list[dict]:
        """Query promises that need enrichment using original logic."""
        logger.info(f"Querying promises for enrichment: session '{parliament_session_id}', source_type: '{source_type}', limit: {limit}, force: {force_reprocessing}")
        
        try:
            query = self.db.collection(PROMISES_COLLECTION_ROOT).where(
                filter=firestore.FieldFilter("party_code", "==", "LPC")
            ).where(
                filter=firestore.FieldFilter("parliament_session_id", "==", parliament_session_id)
            )
            
            if source_type:
                query = query.where(
                    filter=firestore.FieldFilter("source_type", "==", source_type)
                )
            else:
                query = query.where(
                    filter=firestore.FieldFilter("source_type", "in", TARGET_SOURCE_TYPES)
                )
            
            if not force_reprocessing:
                # Only get promises that haven't been enriched
                query = query.where(
                    filter=firestore.FieldFilter("what_it_means_for_canadians", "==", None)
                )
            
            if limit:
                query = query.limit(limit)
            
            promise_docs_stream = query.select([
                "text", "responsible_department_lead", "source_type"
            ]).stream()
            
            promises = []
            for doc_snapshot in await asyncio.to_thread(list, promise_docs_stream):
                promise_data = doc_snapshot.to_dict()
                if promise_data and promise_data.get("text"):
                    promises.append({
                        "id": doc_snapshot.id,
                        "text": promise_data["text"],
                        "responsible_department_lead": promise_data.get("responsible_department_lead"),
                        "source_type": promise_data.get("source_type"),
                        "doc_ref": doc_snapshot.reference
                    })
            
            logger.info(f"Retrieved {len(promises)} promises for enrichment")
            return promises
            
        except Exception as e:
            logger.error(f"Error querying promises: {e}", exc_info=True)
            return []
    
    async def load_explanation_prompt(self) -> str:
        """Load the original explanation prompt template."""
        prompt_file = os.path.join("..", "prompts", "prompt_generate_whatitmeans.md")
        try:
            with open(prompt_file, 'r') as f:
                return f.read()
        except FileNotFoundError:
            logger.critical(f"Prompt file not found: {prompt_file}")
            raise
    
    async def generate_explanations_batch(self, promises_data: list[dict]) -> list[dict]:
        """Generate explanations for a batch of promises using original prompt."""
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
            
            response = await self.client.aio.models.generate_content(
                model=self.model_name,
                contents=[full_prompt]
            )
            
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
                    validated_output.append(item)
                else:
                    logger.warning(f"LLM output item has incorrect structure: {str(item)[:200]}")
            
            logger.info(f"Successfully parsed {len(validated_output)} explanations")
            return validated_output
            
        except Exception as e:
            logger.error(f"Error calling LLM for explanation generation: {e}", exc_info=True)
            return []
    
    def _clean_json_from_markdown(self, response_text: str) -> str:
        """Clean JSON from markdown code blocks."""
        cleaned = response_text.strip()
        if cleaned.startswith("```json"):
            cleaned = cleaned[7:]
        if cleaned.startswith("```"):
            cleaned = cleaned[3:]
        if cleaned.endswith("```"):
            cleaned = cleaned[:-3]
        return cleaned.strip()
    
    async def extract_keywords_llm(self, promise_text: str) -> list:
        """Extract keywords using original prompt structure."""
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
            response = await self.client.aio.models.generate_content(
                model=self.model_name,
                contents=[prompt]
            )
            
            cleaned_response = self._clean_json_from_markdown(response.text)
            keywords = json.loads(cleaned_response)
            
            if isinstance(keywords, list) and all(isinstance(k, str) for k in keywords):
                return keywords
            else:
                logger.warning(f"Invalid keywords format returned: {response.text}")
                return []
                
        except Exception as e:
            logger.error(f"Error extracting keywords: {e}")
            return []
    
    async def infer_action_type_llm(self, promise_text: str) -> str:
        """Infer action type using original prompt structure."""
        action_types_string = ", ".join([f'"{t}"' for t in ACTION_TYPES_LIST])
        
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
            response = await self.client.aio.models.generate_content(
                model=self.model_name,
                contents=[prompt]
            )
            
            cleaned_response = self._clean_json_from_markdown(response.text)
            data = json.loads(cleaned_response)
            
            if isinstance(data, dict) and "action_type" in data and data["action_type"] in ACTION_TYPES_LIST:
                return data["action_type"]
            else:
                # Try fallback parsing
                raw_response = response.text.lower()
                for valid_type in ACTION_TYPES_LIST:
                    if f'"{valid_type}"' in raw_response:
                        logger.info(f"Found valid action type '{valid_type}' via fallback search")
                        return valid_type
                logger.warning(f"Unknown action type returned: {response.text}")
                return "other"
                
        except Exception as e:
            logger.error(f"Error inferring action type: {e}")
            return "other"
    
    async def store_explanations(self, llm_results: list[dict], original_promises_data: list[dict], dry_run: bool = False) -> int:
        """Store explanations using original field structure."""
        if not llm_results:
            return 0
        
        updated_count = 0
        promise_text_to_ref_map = {p['text']: p['doc_ref'] for p in original_promises_data}
        
        for llm_item in llm_results:
            commitment_text = llm_item.get("commitment_text")
            target_promise_ref = promise_text_to_ref_map.get(commitment_text)
            
            if not target_promise_ref:
                logger.warning(f"Could not match LLM result to promise: {commitment_text[:100]}")
                continue
            
            # Use ORIGINAL field structure
            payload = {
                "concise_title": llm_item.get("concise_title"),
                "what_it_means_for_canadians": llm_item.get("what_it_means_for_canadians"),  # Should be array
                "description": llm_item.get("description"),  # Should be array
                "background_and_context": llm_item.get("background_and_context"),
                "explanation_enriched_at": firestore.SERVER_TIMESTAMP,
                "explanation_enrichment_model": self.model_name,
                "explanation_enrichment_status": "processed"
            }
            
            if not dry_run:
                await asyncio.to_thread(target_promise_ref.update, payload)
            else:
                logger.info(f"[DRY RUN] Would update promise with: {payload}")
            
            updated_count += 1
            self.stats['explanations_generated'] += 1
        
        return updated_count
    
    async def store_keywords(self, promise: dict, keywords: list, dry_run: bool = False):
        """Store keywords using original field structure."""
        payload = {
            "extracted_keywords_concepts": keywords,
            "keywords_enriched_at": firestore.SERVER_TIMESTAMP,
            "keywords_enrichment_model": self.model_name,
            "keywords_enrichment_status": "processed"
        }
        
        if not dry_run:
            await asyncio.to_thread(promise['doc_ref'].update, payload)
        else:
            logger.info(f"[DRY RUN] Would update keywords: {keywords}")
        
        self.stats['keywords_extracted'] += 1
    
    async def store_action_type(self, promise: dict, action_type: str, dry_run: bool = False):
        """Store action type using original field structure."""
        payload = {
            "implied_action_type": action_type,
            "action_type_enriched_at": firestore.SERVER_TIMESTAMP,
            "action_type_enrichment_model": self.model_name,
            "action_type_enrichment_status": "processed"
        }
        
        if not dry_run:
            await asyncio.to_thread(promise['doc_ref'].update, payload)
        else:
            logger.info(f"[DRY RUN] Would update action type: {action_type}")
        
        self.stats['action_types_classified'] += 1
    
    async def enrich_promises(self, parliament_session_id: str, source_type: str = None, 
                            limit: int = None, force_reprocessing: bool = False,
                            enrichment_types: list = None, dry_run: bool = False,
                            batch_size: int = 5):
        """Main enrichment function using original approach."""
        if enrichment_types is None:
            enrichment_types = ['explanation', 'keywords', 'action_type']
        
        logger.info(f"Starting enrichment with types: {enrichment_types}")
        
        # Query promises
        promises = await self.query_promises_for_enrichment(
            parliament_session_id, source_type, limit, force_reprocessing
        )
        
        if not promises:
            logger.info("No promises found for enrichment")
            return
        
        # Process explanations in batches (original approach)
        if 'explanation' in enrichment_types:
            logger.info("Processing explanations...")
            for i in range(0, len(promises), batch_size):
                batch = promises[i:i + batch_size]
                logger.info(f"Processing explanation batch {i // batch_size + 1}")
                
                llm_results = await self.generate_explanations_batch(batch)
                if llm_results:
                    await self.store_explanations(llm_results, batch, dry_run)
                
                if i + batch_size < len(promises):
                    await asyncio.sleep(RATE_LIMIT_DELAY_SECONDS)
        
        # Process keywords individually (if not done in explanation)
        if 'keywords' in enrichment_types:
            logger.info("Processing keywords...")
            for promise in promises:
                keywords = await self.extract_keywords_llm(promise['text'])
                await self.store_keywords(promise, keywords, dry_run)
                await asyncio.sleep(1)  # Small delay between requests
        
        # Process action types individually
        if 'action_type' in enrichment_types:
            logger.info("Processing action types...")
            for promise in promises:
                action_type = await self.infer_action_type_llm(promise['text'])
                await self.store_action_type(promise, action_type, dry_run)
                await asyncio.sleep(1)  # Small delay between requests
        
        self.stats['total_processed'] = len(promises)
        logger.info(f"Enrichment complete. Stats: {self.stats}")

async def main():
    """Main function."""
    parser = argparse.ArgumentParser(description='Fixed Promise Enrichment Script')
    parser.add_argument('--parliament_session_id', type=str, required=True,
                       help='Parliament session ID (e.g., "44")')
    parser.add_argument('--source_type', type=str,
                       help='Source type filter (e.g., "2021 LPC Mandate Letters")')
    parser.add_argument('--limit', type=int,
                       help='Limit number of promises to process')
    parser.add_argument('--force_reprocessing', action='store_true',
                       help='Force reprocessing of already enriched promises')
    parser.add_argument('--enrichment_types', type=str, default='all',
                       help='Types to enrich: explanation,keywords,action_type or "all"')
    parser.add_argument('--dry_run', action='store_true',
                       help='Dry run mode - no database updates')
    parser.add_argument('--batch_size', type=int, default=5,
                       help='Batch size for LLM calls')
    
    args = parser.parse_args()
    
    # Parse enrichment types
    if args.enrichment_types == 'all':
        enrichment_types = ['explanation', 'keywords', 'action_type']
    else:
        enrichment_types = [t.strip() for t in args.enrichment_types.split(',')]
    
    logger.info("=== Fixed Promise Enrichment Script ===")
    if args.dry_run:
        logger.info("*** DRY RUN MODE ***")
    
    enricher = FixedPromiseEnricher()
    
    await enricher.enrich_promises(
        parliament_session_id=args.parliament_session_id,
        source_type=args.source_type,
        limit=args.limit,
        force_reprocessing=args.force_reprocessing,
        enrichment_types=enrichment_types,
        dry_run=args.dry_run,
        batch_size=args.batch_size
    )

if __name__ == "__main__":
    asyncio.run(main()) 