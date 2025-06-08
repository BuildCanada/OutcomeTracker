"""
Progress Scorer Job for Promise Tracker Pipeline

Calculates and updates promise progress scores based on evidence links using LLM-based analysis.
Uses the frontend-compatible data structure with evidence_items.promise_ids arrays
and promises.linked_evidence_ids arrays.

Now features:
- LLM-based progress scoring using official prompt (1-5 scale)
- Integration with existing LangChain infrastructure
- Structured evidence analysis for precise scoring
"""

import logging
import sys
import json
import time
import asyncio
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional
from pathlib import Path
from google.cloud import firestore

# Standard imports for pipeline jobs
sys.path.append(str(Path(__file__).parent.parent.parent))
sys.path.append(str(Path(__file__).parent.parent.parent.parent))

from pipeline.core.base_job import BaseJob
from lib.langchain_config import get_langchain_instance


class ProgressScorer(BaseJob):
    """
    Job for calculating promise progress scores using LLM-based analysis.
    
    Analyzes promise-evidence links using the official progress scoring prompt
    to generate precise 1-5 scale scores with detailed progress summaries.
    """
    
    def __init__(self, job_name: str, config: Dict[str, Any] = None):
        """Initialize the Progress Scorer job"""
        super().__init__(job_name, config)
        
        # Processing settings
        self.batch_size = self.config.get('batch_size', 5)  # Very small batches for LLM processing to avoid API issues
        self.max_promises_per_run = self.config.get('max_promises_per_run', 500)  # Reduced from 200
        
        # LLM settings
        self.use_llm_scoring = self.config.get('use_llm_scoring', True)
        self.max_evidence_per_promise = self.config.get('max_evidence_per_promise', 20)  # Reduced from 50
        
        # Initialize LangChain
        try:
            self.langchain = get_langchain_instance()
            self.logger.info("LangChain initialized for progress scoring")
        except Exception as e:
            self.logger.error(f"Failed to initialize LangChain: {e}")
            self.langchain = None
            if self.use_llm_scoring:
                raise RuntimeError("LLM scoring enabled but LangChain initialization failed")
        
        # Load progress scoring prompt
        self.progress_prompt = self._load_progress_scoring_prompt()
        
        # Collections - using frontend-compatible structure
        self.promises_collection = 'promises'
        self.evidence_collection = 'evidence_items'
    
    def _load_progress_scoring_prompt(self) -> str:
        """Load the official progress scoring prompt"""
        try:
            prompt_path = Path(__file__).parent.parent.parent.parent / 'prompts' / 'prompt_progress_scoring.md'
            if prompt_path.exists():
                return prompt_path.read_text()
            else:
                self.logger.error(f"Progress scoring prompt not found: {prompt_path}")
                return ""
        except Exception as e:
            self.logger.error(f"Error loading progress scoring prompt: {e}")
            return ""
    
    def _execute_job(self, **kwargs) -> Dict[str, Any]:
        """
        Execute the progress scoring job.
        
        Args:
            **kwargs: Additional job arguments including:
                trigger_metadata: Metadata from triggering job (may contain affected_promise_ids)
            
        Returns:
            Job execution statistics
        """
        self.logger.info("Starting LLM-based promise progress scoring")
        
        stats = {
            'promises_processed': 0,
            'scores_updated': 0,
            'status_changes': 0,
            'errors': 0,
            'llm_calls': 0,
            'total_cost_estimate': 0.0,
            'items_processed': 0,  # For BaseJob compatibility
            'items_created': 0,    # For BaseJob compatibility  
            'items_updated': 0,    # For BaseJob compatibility
            'items_skipped': 0,    # For BaseJob compatibility
            'metadata': {
                'promises_collection': self.promises_collection,
                'evidence_collection': self.evidence_collection,
                'scoring_method': 'llm_based' if self.use_llm_scoring else 'rule_based'
            }
        }
        
        try:
            # Check if we have specific promise IDs to score from trigger metadata
            trigger_metadata = kwargs.get('trigger_metadata', {})
            affected_promise_ids = trigger_metadata.get('affected_promise_ids', [])
            force_full_scan = kwargs.get('force_full_scan')
            parliament_session_id = kwargs.get('parliament_session_id')
            
            if not affected_promise_ids and not force_full_scan:
                # No specific promise IDs provided and not forced - exit gracefully
                self.logger.info("No affected promise IDs received. Skipping progress scoring to avoid expensive full scan.")
                self.logger.info("To manually score all promises, use the --force_full_scan flag when running the script directly.")
                stats['metadata']['targeting_mode'] = 'no_promises_specified'
                stats['metadata']['skip_reason'] = 'no_affected_promise_ids'
                return stats
            
            # Score only the promises that were affected by evidence linking or if full scan is forced
            if affected_promise_ids:
                self.logger.info(f"Targeted scoring: {len(affected_promise_ids)} promises affected by evidence linking")
                promises_to_score = self._get_specific_promises_to_score(affected_promise_ids)
                stats['metadata']['targeting_mode'] = 'affected_promises_only'
                stats['metadata']['trigger_source'] = trigger_metadata.get('triggered_by', 'unknown')
                stats['metadata']['requested_promise_count'] = len(affected_promise_ids)
            else: # force_full_scan must be true
                if parliament_session_id:
                    self.logger.info(f"Forcing full scan of active promises for parliament session: {parliament_session_id}")
                    promises_to_score = self._get_promises_to_score(parliament_session_id=parliament_session_id)
                    stats['metadata']['targeting_mode'] = 'forced_session_scan'
                    stats['metadata']['parliament_session_id'] = parliament_session_id
                else:
                    self.logger.info("Forcing full scan of all active promises as requested.")
                    promises_to_score = self._get_promises_to_score()
                    stats['metadata']['targeting_mode'] = 'forced_full_scan'
            
            if not promises_to_score:
                self.logger.warning(f"No promises found to score.")
                stats['metadata']['skip_reason'] = 'no_active_promises_found'
                return stats
            
            self.logger.info(f"Scoring {len(promises_to_score)} promises using {'LLM-based' if self.use_llm_scoring else 'rule-based'} scoring")
            
            # Process promises in batches
            for i in range(0, len(promises_to_score), self.batch_size):
                batch = promises_to_score[i:i + self.batch_size]
                batch_stats = self._score_promise_batch(batch)
                
                # Update overall stats
                for key in ['promises_processed', 'scores_updated', 'status_changes', 'errors', 'llm_calls']:
                    stats[key] += batch_stats.get(key, 0)
                
                # Map progress scorer stats to BaseJob-compatible stats
                stats['items_processed'] = stats['promises_processed']
                stats['items_updated'] = stats['scores_updated']
                
                self.logger.info(f"Scored batch {i//self.batch_size + 1}: "
                               f"{batch_stats['scores_updated']} scores updated, "
                               f"{batch_stats['status_changes']} status changes, "
                               f"{batch_stats['errors']} errors")
            
            # Get cost summary if using LLM
            if self.use_llm_scoring and self.langchain:
                cost_summary = self.langchain.get_cost_summary()
                stats['total_cost_estimate'] = cost_summary.get('total_cost_usd', 0.0)
            
            if stats['metadata']['targeting_mode'] == 'no_promises_specified':
                self.logger.info(f"Progress scoring skipped: No affected promise IDs received from upstream job")
            elif stats['metadata'].get('skip_reason') == 'no_active_promises_found':
                self.logger.info(f"Progress scoring skipped: None of {stats['metadata']['requested_promise_count']} affected promises were active")
            else:
                self.logger.info(f"Progress scoring completed: {stats['scores_updated']} scores updated, "
                               f"{stats['status_changes']} status changes, {stats['errors']} errors, "
                               f"{stats['llm_calls']} LLM calls, ${stats['total_cost_estimate']:.4f} estimated cost")
            
        except Exception as e:
            self.logger.error(f"Fatal error in progress scoring: {e}", exc_info=True)
            stats['errors'] += 1
            raise
        
        return stats
    
    def _get_promises_to_score(self, parliament_session_id: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        Get all active promises that need progress scoring, optionally filtered by parliament session.
        
        WARNING: This method is only for manual/maintenance use. 
        In normal pipeline operation, progress_scorer should only process 
        specific promise IDs passed from evidence_linker.
        """
        try:
            # Get all active promises (simple query to avoid index requirement)
            query = (self.db.collection(self.promises_collection)
                    .where(filter=firestore.FieldFilter('status', '==', 'active')))
            
            # Add session filter if provided
            if parliament_session_id:
                query = query.where(filter=firestore.FieldFilter('parliament_session_id', '==', parliament_session_id))
                self.logger.info(f"Querying for active promises in parliament session {parliament_session_id}")
            else:
                self.logger.info("Querying for all active promises")

            query = query.limit(self.max_promises_per_run or 500)
            
            promises = []
            for doc in query.stream():
                promise_data = doc.to_dict()
                promise_data['_doc_id'] = doc.id
                promises.append(promise_data)
            
            self.logger.info(f"Found {len(promises)} active promises for scoring")
            return promises
            
        except Exception as e:
            self.logger.error(f"Error querying promises: {e}")
            return []
    
    def _get_specific_promises_to_score(self, promise_ids: List[str]) -> List[Dict[str, Any]]:
        """Get specific promises by ID for targeted scoring"""
        try:
            promises = []
            
            # Batch get promises by ID (Firestore has a limit of 10 for 'in' queries)
            batch_size = 10
            for i in range(0, len(promise_ids), batch_size):
                batch_ids = promise_ids[i:i + batch_size]
                
                # Get batch of promises
                batch_promises = []
                for promise_id in batch_ids:
                    try:
                        doc = self.db.collection(self.promises_collection).document(promise_id).get()
                        if doc.exists:
                            promise_data = doc.to_dict()
                            promise_data['_doc_id'] = doc.id
                            # Only include active promises
                            if promise_data.get('status') == 'active':
                                batch_promises.append(promise_data)
                    except Exception as e:
                        self.logger.warning(f"Error getting promise {promise_id}: {e}")
                
                promises.extend(batch_promises)
            
            self.logger.info(f"Found {len(promises)} specific active promises for targeted scoring")
            return promises
            
        except Exception as e:
            self.logger.error(f"Error querying specific promises: {e}")
            return []
    
    def _score_promise_batch(self, batch: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Score a batch of promises"""
        batch_stats = {
            'promises_processed': 0,
            'scores_updated': 0,
            'status_changes': 0,
            'errors': 0,
            'llm_calls': 0
        }
        
        for i, promise in enumerate(batch):
            try:
                batch_stats['promises_processed'] += 1
                
                # Add delay between LLM calls to avoid rate limiting (except for first item)
                if i > 0 and self.use_llm_scoring:
                    time.sleep(2)  # 2 second delay between LLM calls
                
                # Calculate progress score
                score_data = self._calculate_promise_score(promise)
                
                if score_data:
                    # Save score and check for status changes
                    status_changed = self._save_promise_score(promise, score_data)
                    batch_stats['scores_updated'] += 1
                    
                    if status_changed:
                        batch_stats['status_changes'] += 1
                    
                    if score_data.get('used_llm'):
                        batch_stats['llm_calls'] += 1
                        
            except Exception as e:
                self.logger.error(f"Error scoring promise {promise.get('_doc_id', 'unknown')}: {e}")
                batch_stats['errors'] += 1
        
        return batch_stats
    
    def _calculate_promise_score(self, promise: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        Calculate progress score for a promise using LLM-based analysis.
        
        Args:
            promise: Promise document
            
        Returns:
            Score data dictionary or None if calculation failed
        """
        promise_id = promise['_doc_id']
        
        try:
            # Get all evidence items for this promise
            evidence_items = self._get_promise_evidence_items(promise_id)
            
            if not evidence_items:
                # No evidence found - return score of 1 (No Progress)
                return {
                    'promise_id': promise_id,
                    'overall_score': 1,
                    'evidence_count': 0,
                    'fulfillment_status': 'not_started',
                    'progress_summary': 'No evidence of government action found for this commitment.',
                    'last_evidence_date': None,
                    'used_llm': False,
                    'calculated_at': datetime.now(timezone.utc)
                }
            
            # Use LLM-based scoring if enabled and available
            if self.use_llm_scoring and self.langchain and self.progress_prompt:
                return self._llm_based_scoring(promise, evidence_items)
            else:
                # Fallback to simple rule-based scoring (if LLM fails)
                return self._rule_based_scoring(promise, evidence_items)
            
        except Exception as e:
            self.logger.error(f"Error calculating score for promise {promise_id}: {e}")
            return None
    
    def _llm_based_scoring(self, promise: Dict[str, Any], evidence_items: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Use LLM to score promise progress based on evidence.
        
        Args:
            promise: Promise document
            evidence_items: List of evidence items
            
        Returns:
            Score data with LLM analysis
        """
        promise_id = promise['_doc_id']
        max_retries = 3
        retry_delay = 5  # seconds
        
        for attempt in range(max_retries):
            try:
                # Prepare promise information for LLM
                promise_info = {
                    'canonical_commitment_text': promise.get('canonical_text', ''),
                    'background_and_context': promise.get('background_and_context', ''),
                    'intended_impact_and_objectives': promise.get('what_it_means_for_canadians', []),
                    'responsible_department_lead': promise.get('responsible_department_lead', '')
                }
                
                # Limit evidence items to prevent token overflow
                limited_evidence = evidence_items[:self.max_evidence_per_promise]
                if len(evidence_items) > self.max_evidence_per_promise:
                    self.logger.warning(f"Promise {promise_id} has {len(evidence_items)} evidence items, limiting to {self.max_evidence_per_promise}")
                
                # Prepare evidence for LLM
                evidence_for_llm = []
                for evidence in limited_evidence:
                    # Convert datetime objects to strings for JSON serialization
                    evidence_date = evidence.get('evidence_date', '')
                    if hasattr(evidence_date, 'isoformat'):
                        evidence_date = evidence_date.isoformat()
                    elif evidence_date and not isinstance(evidence_date, str):
                        evidence_date = str(evidence_date)
                    
                    evidence_for_llm.append({
                        'title_or_summary': evidence.get('title', ''),
                        'evidence_source_type': evidence.get('evidence_source_type', ''),
                        'evidence_date': evidence_date,
                        'description_or_details': evidence.get('description', ''),
                        'source_url': evidence.get('source_url', ''),
                        'bill_one_sentence_description_llm': evidence.get('bill_one_sentence_description_llm', '')
                    })
                
                # Defensive check for iterable
                objectives = promise_info['intended_impact_and_objectives']
                if not isinstance(objectives, list):
                    objectives = [] # Default to empty list if not iterable

                # Create the full prompt
                full_prompt = f"""{self.progress_prompt}

**Promise Information:**
- Canonical Commitment Text: {promise_info['canonical_commitment_text']}
- Background and Context: {promise_info['background_and_context']}
- Intended Impact and Objectives: {', '.join(objectives)}
- Responsible Department Lead: {promise_info['responsible_department_lead']}

**Evidence Items ({len(evidence_for_llm)} items):**
{json.dumps(evidence_for_llm, indent=2)}

Please analyze this promise and evidence to provide a progress score (1-5) and summary following the exact JSON format specified in the prompt."""
                
                # Call LLM with timeout
                self.logger.debug(f"Attempting LLM call for promise {promise_id} (attempt {attempt + 1}/{max_retries})")
                response = self.langchain.llm.invoke(full_prompt)
                
                # Parse LLM response
                try:
                    # Try to extract JSON from response
                    response_text = response.content if hasattr(response, 'content') else str(response)
                    
                    # Find JSON in response (handle cases where LLM adds explanation text)
                    json_start = response_text.find('{')
                    json_end = response_text.rfind('}') + 1
                    
                    if json_start >= 0 and json_end > json_start:
                        json_text = response_text[json_start:json_end]
                        llm_result = json.loads(json_text)
                    else:
                        raise ValueError("No valid JSON found in LLM response")
                    
                    # Extract score and summary
                    progress_score = llm_result.get('progress_score', 1)
                    progress_summary = llm_result.get('progress_summary', 'Unable to generate summary from LLM response.')
                    
                    # Validate score is in range 1-5
                    if not isinstance(progress_score, int) or progress_score < 1 or progress_score > 5:
                        self.logger.warning(f"Invalid progress score {progress_score} from LLM, defaulting to 1")
                        progress_score = 1
                    
                    # Determine fulfillment status from score
                    fulfillment_status = self._score_to_status(progress_score)
                    
                    # Get latest evidence date
                    last_evidence_date = self._get_latest_evidence_date(evidence_items)
                    
                    self.logger.info(f"LLM scoring successful for promise {promise_id} on attempt {attempt + 1}")
                    return {
                        'promise_id': promise_id,
                        'overall_score': progress_score,
                        'evidence_count': len(evidence_items),
                        'fulfillment_status': fulfillment_status,
                        'progress_summary': progress_summary,
                        'last_evidence_date': last_evidence_date,
                        'used_llm': True,
                        'llm_response_raw': response_text,
                        'calculated_at': datetime.now(timezone.utc)
                    }
                    
                except (json.JSONDecodeError, ValueError) as e:
                    self.logger.error(f"Failed to parse LLM response for promise {promise_id} on attempt {attempt + 1}: {e}")
                    self.logger.debug(f"LLM response was: {response_text}")
                    if attempt == max_retries - 1:
                        # Last attempt failed, fall back to rule-based scoring
                        return self._rule_based_scoring(promise, evidence_items)
                    continue
                
            except Exception as e:
                error_msg = str(e)
                if "500" in error_msg or "Internal" in error_msg or "Rate" in error_msg:
                    # API error - retry with delay
                    self.logger.warning(f"LLM API error for promise {promise_id} on attempt {attempt + 1}: {error_msg}")
                    if attempt < max_retries - 1:
                        self.logger.info(f"Retrying LLM call for promise {promise_id} in {retry_delay} seconds...")
                        time.sleep(retry_delay)
                        retry_delay *= 2  # Exponential backoff
                        continue
                else:
                    # Non-retryable error
                    self.logger.error(f"Non-retryable LLM error for promise {promise_id}: {error_msg}")
                    break
        
        # All retries failed, fall back to rule-based scoring
        self.logger.warning(f"LLM scoring failed for promise {promise_id} after {max_retries} attempts, falling back to rule-based scoring")
        return self._rule_based_scoring(promise, evidence_items)
    
    def _rule_based_scoring(self, promise: Dict[str, Any], evidence_items: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Fallback rule-based scoring when LLM is unavailable.
        
        Args:
            promise: Promise document
            evidence_items: List of evidence items
            
        Returns:
            Score data with rule-based analysis
        """
        promise_id = promise['_doc_id']
        
        # Simple rule-based scoring logic
        evidence_count = len(evidence_items)
        
        # Analyze evidence types for scoring
        high_value_types = ['bill', 'order_in_council', 'gazette']
        medium_value_types = ['news', 'speech']
        
        high_value_count = sum(1 for item in evidence_items 
                              if item.get('evidence_source_type', '').lower() in high_value_types)
        medium_value_count = sum(1 for item in evidence_items 
                                if item.get('evidence_source_type', '').lower() in medium_value_types)
        
        # Calculate score based on evidence quantity and quality
        if high_value_count >= 3:
            score = 4  # Major Progress
        elif high_value_count >= 1:
            score = 3  # Meaningful Action  
        elif medium_value_count >= 3:
            score = 3  # Meaningful Action
        elif evidence_count >= 3:
            score = 2  # Initial Steps
        elif evidence_count >= 1:
            score = 2  # Initial Steps
        else:
            score = 1  # No Progress
        
        fulfillment_status = self._score_to_status(score)
        last_evidence_date = self._get_latest_evidence_date(evidence_items)
        
        return {
            'promise_id': promise_id,
            'overall_score': score,
            'evidence_count': evidence_count,
            'fulfillment_status': fulfillment_status,
            'progress_summary': f'Rule-based analysis found {evidence_count} evidence items including {high_value_count} high-value and {medium_value_count} medium-value evidence types.',
            'last_evidence_date': last_evidence_date,
            'used_llm': False,
            'calculated_at': datetime.now(timezone.utc)
        }
    
    def _score_to_status(self, score: int) -> str:
        """Convert 1-5 score to status string"""
        status_map = {
            1: 'not_started',      # No Progress
            2: 'in_progress',      # Initial Steps  
            3: 'in_progress',      # Meaningful Action
            4: 'substantial_progress',  # Major Progress
            5: 'completed'         # Complete/Fully Implemented
        }
        return status_map.get(score, 'not_started')
    
    def _get_promise_evidence_items(self, promise_id: str) -> List[Dict[str, Any]]:
        """Get all evidence items for a promise"""
        try:
            evidence_items = []
            query = (self.db.collection(self.evidence_collection)
                    .where(filter=firestore.FieldFilter('promise_ids', 'array_contains', promise_id)))
            
            for doc in query.stream():
                evidence_data = doc.to_dict()
                evidence_data['_doc_id'] = doc.id
                evidence_items.append(evidence_data)
            
            return evidence_items
            
        except Exception as e:
            self.logger.error(f"Error getting evidence items for promise {promise_id}: {e}")
            return []
    
    def _get_latest_evidence_date(self, evidence_items: List[Dict[str, Any]]) -> Optional[datetime]:
        """Get the date of the most recent evidence"""
        latest_date = None
        
        for evidence_item in evidence_items:
            # Get evidence date directly from the evidence item
            evidence_date = evidence_item.get('evidence_date')
            
            if evidence_date:
                # Handle different date formats
                if isinstance(evidence_date, str):
                    try:
                        evidence_date = datetime.fromisoformat(evidence_date.replace('Z', '+00:00'))
                    except Exception:
                        continue
                
                if not latest_date or evidence_date > latest_date:
                    latest_date = evidence_date
        
        return latest_date
    
    def _save_promise_score(self, promise: Dict[str, Any], score_data: Dict[str, Any]) -> bool:
        """
        Save promise score and update promise status if needed.
        
        Args:
            promise: Promise document
            score_data: Calculated score data
            
        Returns:
            True if promise status was changed
        """
        promise_id = promise['_doc_id']
        status_changed = False
        
        try:
            # Check if promise status needs updating
            current_status = promise.get('progress_status', 'not_started')
            new_status = score_data['fulfillment_status']
            
            # Always update the promise document with new score data and backend timestamp
            update_data = {
                'progress_score': score_data['overall_score'],
                'progress_summary': score_data['progress_summary'],
                'last_scored_at': score_data['calculated_at'],  # Backend processing timestamp
                'evidence_count': score_data['evidence_count'],
                'last_evidence_date': score_data['last_evidence_date'],
                'scoring_method': 'llm_based' if score_data.get('used_llm') else 'rule_based'
            }
            
            if current_status != new_status:
                update_data['progress_status'] = new_status
                self.logger.info(f"Promise {promise_id} status changed: {current_status} -> {new_status}")
                status_changed = True
            
            # Update promise document
            self.db.collection(self.promises_collection).document(promise_id).update(update_data)
            
        except Exception as e:
            self.logger.error(f"Error saving score for promise {promise_id}: {e}")
            raise
        
        return status_changed
    
    def should_trigger_downstream(self, result) -> bool:
        """
        Progress scoring is typically the final stage, so no downstream triggering.
        
        Args:
            result: Job execution result
            
        Returns:
            False (no downstream jobs)
        """
        return False
    
    def get_trigger_metadata(self, result) -> Dict[str, Any]:
        """
        Get metadata for potential downstream jobs.
        
        Args:
            result: Job execution result
            
        Returns:
            Metadata for downstream jobs
        """
        return {
            'triggered_by': self.job_name,
            'promises_scored': result.get('promises_processed', 0),
            'status_changes': result.get('status_changes', 0),
            'llm_calls': result.get('llm_calls', 0),
            'total_cost': result.get('total_cost_estimate', 0.0),
            'trigger_time': datetime.now(timezone.utc).isoformat()
        }

if __name__ == "__main__":
    import argparse
    import logging
    from pathlib import Path

    # Optionally load environment variables for local development
    # This won't break Cloud Run if python-dotenv isn't available
    try:
        from dotenv import load_dotenv
        # Go up to the PromiseTracker directory (4 levels from pipeline/stages/linking/)
        env_path = Path(__file__).resolve().parent.parent.parent.parent / '.env'
        if env_path.exists():
            load_dotenv(env_path)
            print(f"📋 Loaded environment from: {env_path}")
        else:
            print(f"📋 .env file not found at {env_path}, relying on system environment variables.")
    except ImportError:
        print("📋 python-dotenv not available, skipping .env file loading")
    except Exception as e:
        print(f"📋 Could not load .env file: {e}")

    # Setup logging
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(name)s - %(message)s')

    # Parse command line arguments
    parser = argparse.ArgumentParser(description='Promise Progress Scorer Job')
    parser.add_argument('--limit', type=int, default=50, help='Maximum number of promises to process per run.')
    parser.add_argument('--force_full_scan', action='store_true', help='Force a full scan of all active promises, ignoring triggers.')
    parser.add_argument('--parliament_session_id', type=str, default=None, help='Force a scan for a specific parliament session. Requires --force_full_scan.')
    args = parser.parse_args()

    print(f"🚀 Starting Progress Scorer")
    print(f"Max Promises: {args.limit}")
    print(f"Force Full Scan: {args.force_full_scan}")
    if args.parliament_session_id:
        print(f"Parliament Session: {args.parliament_session_id}")
    print("-" * 60)

    try:
        config = {
            'max_promises_per_run': args.limit,
        }
        scorer = ProgressScorer("progress_scorer_manual_run", config)
        result = scorer.execute(
            force_full_scan=args.force_full_scan,
            parliament_session_id=args.parliament_session_id
        )

        # ... (print results)
    except Exception as e:
        print(f"❌ Error: {e}")
        logging.error("Progress scorer failed", exc_info=True) 