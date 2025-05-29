#!/usr/bin/env python3
"""
Promise Progress Score Update Pipeline

This script updates progress scores for promises when new evidence items are linked.
It runs after the consolidated_evidence_linking.py script to ensure progress scores
reflect the latest evidence.

The script:
1. Identifies promises with recently linked evidence (based on linked_at timestamps)
2. Uses the existing LLM-based progress scoring logic from link_evidence_to_promises.py
3. Updates progress_score and progress_summary fields in the promises collection

Usage:
    python update_promise_progress_scores.py --parliament_session_id "45" [options]
"""

import firebase_admin
from firebase_admin import firestore, credentials
import os
import sys
import asyncio
import logging
import traceback
from dotenv import load_dotenv
import json
import argparse
from datetime import datetime, timezone, timedelta
import time
from pathlib import Path
from typing import Dict, List, Any, Optional
import re

# Add parent directory to path to import langchain_config
sys.path.append(str(Path(__file__).parent.parent / 'lib'))

try:
    from langchain_config import get_langchain_instance
except ImportError as e:
    logging.error(f"Failed to import langchain_config: {e}")
    sys.exit("Please ensure langchain_config.py is available in the lib directory")

# Load environment variables
load_dotenv()

# Logger setup
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(filename)s:%(lineno)d - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger("progress_score_updater")

# Firebase Configuration
db = None
if not firebase_admin._apps:
    try:
        firebase_admin.initialize_app()
        project_id = os.getenv('FIREBASE_PROJECT_ID', '[Not Set - Using Default]')
        logger.info(f"Connected to CLOUD Firestore (Project: {project_id}) using default credentials.")
        db = firestore.client()
    except Exception as e_default:
        logger.warning(f"Cloud Firestore init with default creds failed: {e_default}. Attempting service account.")
        cred_path = os.getenv('FIREBASE_SERVICE_ACCOUNT_KEY_PATH')
        if cred_path:
            try:
                logger.info(f"Attempting Firebase init with service account key from env var: {cred_path}")
                cred = credentials.Certificate(cred_path)
                app_name = 'progress_score_updater_app'
                try:
                    firebase_admin.initialize_app(cred, name=app_name)
                except ValueError:
                    app_name_unique = f"{app_name}_{str(time.time())}"
                    firebase_admin.initialize_app(cred, name=app_name_unique)
                    app_name = app_name_unique

                project_id_sa = os.getenv('FIREBASE_PROJECT_ID', '[Not Set - Using Service Account]')
                logger.info(f"Connected to CLOUD Firestore (Project: {project_id_sa}) via service account.")
                db = firestore.client(app=firebase_admin.get_app(name=app_name))
            except Exception as e_sa:
                logger.critical(f"Firebase init with service account key from {cred_path} failed: {e_sa}", exc_info=True)
        else:
            logger.warning("FIREBASE_SERVICE_ACCOUNT_KEY_PATH environment variable not set, and default creds failed.")

if db is None:
    logger.critical("CRITICAL: Failed to obtain Firestore client. Exiting.")
    exit("Exiting: Firestore client not available.")

# Constants
PROMISES_COLLECTION_ROOT = os.getenv("TARGET_PROMISES_COLLECTION", "promises")
EVIDENCE_COLLECTION_ROOT = os.getenv("TARGET_EVIDENCE_COLLECTION", "evidence_items")
RATE_LIMIT_DELAY_SECONDS = 2

class PromiseProgressScoreUpdater:
    """Updates progress scores for promises with newly linked evidence."""
    
    def __init__(self):
        """Initialize the progress score updater."""
        self.langchain = get_langchain_instance()
        self.stats = {
            'promises_checked': 0,
            'promises_with_new_evidence': 0,
            'progress_scores_updated': 0,
            'errors': 0
        }
    
    async def load_progress_scoring_prompt(self) -> str:
        """Load the progress scoring prompt from the dedicated prompt file."""
        try:
            prompts_dir = os.path.join(os.path.dirname(__file__), "..", "prompts")
            prompt_file = os.path.join(prompts_dir, "prompt_progress_scoring.md")
            
            with open(prompt_file, 'r') as f:
                prompt_content = f.read()
            
            logger.info(f"Successfully loaded progress scoring prompt from {prompt_file}")
            return prompt_content
        except FileNotFoundError:
            logger.critical(f"Prompt file not found: {prompt_file}. Please ensure it exists.")
            raise
        except Exception as e:
            logger.critical(f"Error reading prompt file {prompt_file}: {e}", exc_info=True)
            raise
    
    async def query_promises_with_recent_evidence_links(self, parliament_session_id: str, 
                                                       since_hours: int = 24, 
                                                       limit: int = None,
                                                       force_all: bool = False) -> List[Dict[str, Any]]:
        """Query promises that have had evidence linked recently."""
        logger.info(f"Querying promises with evidence linked in the last {since_hours} hours...")
        
        try:
            # Build basic query for LPC promises (without the timestamp filter to avoid index requirement)
            query = db.collection(PROMISES_COLLECTION_ROOT).where(
                filter=firestore.FieldFilter("party_code", "==", "LPC")
            ).where(
                filter=firestore.FieldFilter("parliament_session_id", "==", parliament_session_id)
            )
            
            if limit:
                query = query.limit(limit)
            
            # Execute query
            promise_docs = list(await asyncio.to_thread(query.stream))
            
            promises = []
            cutoff_time = datetime.now(timezone.utc) - timedelta(hours=since_hours) if not force_all else None
            
            for doc in promise_docs:
                data = doc.to_dict()
                if data and data.get("text"):
                    # Check if this promise actually has linked evidence using linked_evidence field
                    linked_evidence = data.get('linked_evidence', [])
                    if linked_evidence:
                        # For now, if force_all is True or we have evidence, include the promise
                        # In the future, we could check timestamps on the evidence links themselves
                        if force_all or cutoff_time is None:
                            should_include = True
                        else:
                            # Check if any evidence was linked recently
                            has_recent_links = False
                            for link in linked_evidence:
                                if isinstance(link, dict) and link.get('linked_at'):
                                    linked_at = link['linked_at']
                                    if hasattr(linked_at, 'seconds'):  # Firestore Timestamp
                                        linked_datetime = datetime.fromtimestamp(linked_at.seconds, tz=timezone.utc)
                                    elif isinstance(linked_at, datetime):
                                        linked_datetime = linked_at
                                    else:
                                        continue
                                    
                                    if linked_datetime >= cutoff_time:
                                        has_recent_links = True
                                        break
                            
                            should_include = has_recent_links
                        
                        if should_include:
                            promises.append({
                                "id": doc.id,
                                "text": data["text"],
                                "responsible_department_lead": data.get("responsible_department_lead"),
                                "source_type": data.get("source_type"),
                                "party_code": data.get("party_code"),
                                "doc_ref": doc.reference,
                                "data": data,
                                "linked_evidence": linked_evidence
                            })
                        else:
                            logger.debug(f"Promise {doc.id} has no recent evidence links, skipping.")
                    else:
                        logger.debug(f"Promise {doc.id} has no linked evidence, skipping.")
                else:
                    logger.warning(f"Promise {doc.id} missing 'text' field, skipping.")
            
            logger.info(f"Retrieved {len(promises)} promises with linked evidence for progress scoring")
            return promises
            
        except Exception as e:
            logger.error(f"Error querying promises: {e}", exc_info=True)
            return []
    
    async def fetch_evidence_for_promise(self, promise: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Fetch the actual evidence items linked to a promise."""
        linked_evidence = promise.get('linked_evidence', [])
        if not linked_evidence:
            return []
        
        # Extract evidence IDs from the linked_evidence array
        evidence_ids = []
        for link in linked_evidence:
            if isinstance(link, dict) and link.get('evidence_id'):
                evidence_ids.append(link['evidence_id'])
        
        if not evidence_ids:
            return []
        
        try:
            # Fetch evidence items individually (simpler approach)
            evidence_items = []
            
            for evidence_id in evidence_ids:
                try:
                    evidence_doc = await asyncio.to_thread(
                        db.collection(EVIDENCE_COLLECTION_ROOT).document(evidence_id).get
                    )
                    
                    if evidence_doc.exists:
                        data = evidence_doc.to_dict()
                        if data:
                            evidence_items.append({
                                "id": evidence_doc.id,
                                "data": data
                            })
                except Exception as e:
                    logger.warning(f"Error fetching evidence {evidence_id}: {e}")
                    continue
            
            logger.debug(f"Fetched {len(evidence_items)} evidence items for promise {promise['id']}")
            return evidence_items
            
        except Exception as e:
            logger.error(f"Error fetching evidence for promise {promise['id']}: {e}")
            return []
    
    async def generate_progress_score_with_llm(self, promise: Dict[str, Any], 
                                             evidence_items: List[Dict[str, Any]], 
                                             base_prompt: str) -> Dict[str, Any]:
        """Generate progress score and summary using LLM based on promise and evidence."""
        try:
            logger.debug(f"Generating progress score for promise {promise['id']}")
            
            # Extract promise information according to the specified fields
            promise_data = promise.get('data', {})
            promise_info = {
                "canonical_commitment_text": promise_data.get('canonical_commitment_text', promise_data.get('text', '')),
                "background_and_context": promise_data.get('background_and_context', ''),
                "intended_impact_and_objectives": promise_data.get('intended_impact_and_objectives', ''),
                "responsible_department_lead": promise_data.get('responsible_department_lead', '')
            }
            
            # Extract evidence information according to the specified fields
            evidence_data = []
            for evidence in evidence_items:
                evidence_item_data = evidence['data']
                
                evidence_entry = {
                    "title_or_summary": evidence_item_data.get('title_or_summary', ''),
                    "evidence_source_type": evidence_item_data.get('evidence_source_type', ''),
                    "evidence_date": self._format_evidence_date(evidence_item_data.get('evidence_date')),
                    "description_or_details": evidence_item_data.get('description_or_details', ''),
                    "source_url": evidence_item_data.get('source_url', '')
                }
                
                # Add bill description for bills only
                if evidence_item_data.get('evidence_source_type') == 'Bill Event (LEGISinfo)':
                    bill_description = evidence_item_data.get('bill_one_sentence_description_llm', '')
                    if bill_description:
                        evidence_entry["bill_one_sentence_description_llm"] = bill_description
                
                evidence_data.append(evidence_entry)
            
            # Construct the full prompt with structured data
            data_section = f"""
**PROMISE INFORMATION:**
- Canonical Commitment Text: {promise_info['canonical_commitment_text']}
- Background and Context: {promise_info['background_and_context']}
- Intended Impact and Objectives: {promise_info['intended_impact_and_objectives']}
- Responsible Department Lead: {promise_info['responsible_department_lead']}

**EVIDENCE ITEMS ({len(evidence_data)} items):**
"""
            
            for i, evidence in enumerate(evidence_data, 1):
                data_section += f"""
{i}. **{evidence['title_or_summary']}**
   - Source Type: {evidence['evidence_source_type']}
   - Date: {evidence['evidence_date']}
   - Description: {evidence['description_or_details']}
   - Source URL: {evidence['source_url']}"""
                
                if 'bill_one_sentence_description_llm' in evidence:
                    data_section += f"""
   - Bill Description: {evidence['bill_one_sentence_description_llm']}"""
                
                data_section += "\n"
            
            full_prompt = base_prompt + "\n\n" + data_section + "\n\nPlease provide your progress assessment:"
            
            # Use langchain LLM directly for the progress scoring
            response = await asyncio.to_thread(
                self.langchain.llm.invoke,
                full_prompt
            )
            
            # Parse JSON response
            import json
            import re
            
            # Get the content from the langchain response
            response_text = response.content if hasattr(response, 'content') else str(response)
            
            # Clean JSON from markdown if present
            match = re.search(r"```(?:json)?\s*([\s\S]+?)\s*```", response_text)
            if match:
                json_text = match.group(1).strip()
            else:
                json_text = response_text.strip()
            
            try:
                result = json.loads(json_text)
            except json.JSONDecodeError:
                # Try to extract JSON from the response if it's embedded in text
                json_match = re.search(r'\{[^{}]*"progress_score"[^{}]*\}', response_text)
                if json_match:
                    result = json.loads(json_match.group())
                else:
                    logger.error(f"Could not parse JSON from LLM response: {response_text}")
                    return {"error": "Could not parse JSON response"}
            
            # Extract progress score and summary
            progress_score = result.get("progress_score")
            progress_summary = result.get("progress_summary", "")
            
            if progress_score is None:
                logger.error(f"No progress_score in LLM response: {result}")
                return {"error": "No progress_score in response"}
            
            # Validate progress score is in valid range
            if not isinstance(progress_score, (int, float)) or progress_score < 1 or progress_score > 5:
                logger.error(f"Invalid progress_score: {progress_score}. Must be 1-5.")
                return {"error": f"Invalid progress_score: {progress_score}"}
            
            return {
                "progress_score": int(progress_score),  # Ensure it's an integer
                "progress_summary": progress_summary,
                "progress_scoring_model": self.langchain.model_name,
                "evidence_items_count": len(evidence_data)
            }
                
        except Exception as e:
            logger.error(f"Error generating progress score for promise {promise['id']}: {e}")
            return {"error": str(e)}
    
    def _format_evidence_date(self, evidence_date) -> str:
        """Format evidence date for LLM prompt."""
        if not evidence_date:
            return "Unknown"
        
        try:
            if hasattr(evidence_date, 'seconds'):  # Firestore Timestamp
                date_obj = datetime.fromtimestamp(evidence_date.seconds, tz=timezone.utc)
            elif isinstance(evidence_date, datetime):
                date_obj = evidence_date
            elif isinstance(evidence_date, str):
                # Try to parse string date
                if 'T' in evidence_date:
                    date_obj = datetime.fromisoformat(evidence_date.replace('Z', '+00:00'))
                else:
                    date_obj = datetime.strptime(evidence_date, '%Y-%m-%d')
            else:
                return "Unknown"
            
            return date_obj.strftime('%Y-%m-%d')
        except Exception:
            return "Unknown"
    
    async def update_promise_progress_score(self, promise: Dict[str, Any], 
                                          progress_data: Dict[str, Any], 
                                          dry_run: bool = False) -> bool:
        """Update the progress score for a promise."""
        try:
            if 'error' in progress_data:
                logger.error(f"Cannot update progress score for promise {promise['id']}: {progress_data['error']}")
                return False
            
            update_data = {
                "progress_score": progress_data["progress_score"],
                "progress_summary": progress_data["progress_summary"],
                "progress_scoring_model": progress_data["progress_scoring_model"],
                "last_progress_update_at": firestore.SERVER_TIMESTAMP
            }
            
            if not dry_run:
                await asyncio.to_thread(promise['doc_ref'].update, update_data)
                logger.info(f"✅ Updated progress score for promise {promise['id']}: {progress_data['progress_score']}")
            else:
                logger.info(f"[DRY RUN] Would update progress score for promise {promise['id']}: {progress_data['progress_score']}")
            
            self.stats['progress_scores_updated'] += 1
            return True
            
        except Exception as e:
            logger.error(f"Error updating progress score for promise {promise['id']}: {e}")
            self.stats['errors'] += 1
            return False
    
    async def run_progress_score_update_pipeline(self, parliament_session_id: str,
                                                since_hours: int = 24,
                                                limit: int = None,
                                                force_all: bool = False,
                                                dry_run: bool = False) -> Dict[str, Any]:
        """Run the complete progress score update pipeline."""
        logger.info("=== Starting Promise Progress Score Update Pipeline ===")
        logger.info(f"Parliament Session: {parliament_session_id}")
        logger.info(f"Since Hours: {since_hours}")
        logger.info(f"Limit: {limit or 'None'}")
        logger.info(f"Force All: {force_all}")
        logger.info(f"Dry Run: {dry_run}")
        
        if dry_run:
            logger.warning("*** DRY RUN MODE: No changes will be written to Firestore ***")
        
        # Load the progress scoring prompt
        base_prompt = await self.load_progress_scoring_prompt()
        
        # Query promises with recent evidence links
        promises = await self.query_promises_with_recent_evidence_links(
            parliament_session_id=parliament_session_id,
            since_hours=since_hours,
            limit=limit,
            force_all=force_all
        )
        
        if not promises:
            logger.info("No promises found with recent evidence links. Exiting.")
            return self.stats
        
        logger.info(f"Processing {len(promises)} promises for progress score updates...")
        
        # Process each promise
        for i, promise in enumerate(promises):
            logger.info(f"--- Processing promise {i+1}/{len(promises)}: {promise['id']} ---")
            
            self.stats['promises_checked'] += 1
            
            # Fetch evidence items for this promise
            evidence_items = await self.fetch_evidence_for_promise(promise)
            
            if not evidence_items:
                logger.info(f"No evidence items found for promise {promise['id']}, skipping.")
                continue
            
            self.stats['promises_with_new_evidence'] += 1
            logger.info(f"Found {len(evidence_items)} evidence items for promise {promise['id']}")
            
            # Generate progress score using LLM
            progress_data = await self.generate_progress_score_with_llm(
                promise=promise,
                evidence_items=evidence_items,
                base_prompt=base_prompt
            )
            
            # Update the promise with new progress score
            success = await self.update_promise_progress_score(
                promise=promise,
                progress_data=progress_data,
                dry_run=dry_run
            )
            
            if not success:
                logger.warning(f"Failed to update progress score for promise {promise['id']}")
            
            # Rate limiting between promises
            if i < len(promises) - 1:
                await asyncio.sleep(RATE_LIMIT_DELAY_SECONDS)
        
        # Log final statistics
        logger.info("=== Progress Score Update Pipeline Complete ===")
        logger.info(f"Promises checked: {self.stats['promises_checked']}")
        logger.info(f"Promises with new evidence: {self.stats['promises_with_new_evidence']}")
        logger.info(f"Progress scores updated: {self.stats['progress_scores_updated']}")
        logger.info(f"Errors encountered: {self.stats['errors']}")
        
        # Get cost summary
        cost_summary = self.langchain.get_cost_summary()
        logger.info(f"LLM Usage Summary:")
        logger.info(f"  Total estimated cost: ${cost_summary['total_cost_usd']:.4f}")
        logger.info(f"  Total tokens: {cost_summary['total_tokens']}")
        logger.info(f"  Total LLM calls: {cost_summary['total_calls']}")
        
        return self.stats

async def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(description='Update Promise Progress Scores After Evidence Linking')
    parser.add_argument(
        '--parliament_session_id',
        type=str,
        default="45",
        help='Parliament session ID (default: "45")'
    )
    parser.add_argument(
        '--since_hours',
        type=int,
        default=24,
        help='Look for evidence linked in the last N hours (default: 24)'
    )
    parser.add_argument(
        '--limit',
        type=int,
        help='Limit number of promises to process'
    )
    parser.add_argument(
        '--force_all',
        action='store_true',
        help='Process all promises regardless of recent evidence linking timestamps'
    )
    parser.add_argument(
        '--dry_run',
        action='store_true',
        help='Run without making changes to Firestore'
    )
    
    args = parser.parse_args()
    
    # Run progress score update pipeline
    updater = PromiseProgressScoreUpdater()
    stats = await updater.run_progress_score_update_pipeline(
        parliament_session_id=args.parliament_session_id,
        since_hours=args.since_hours,
        limit=args.limit,
        force_all=args.force_all,
        dry_run=args.dry_run
    )
    
    logger.info("Progress score update pipeline completed successfully!")

if __name__ == "__main__":
    asyncio.run(main()) 