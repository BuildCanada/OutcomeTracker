"""
Progress Scorer Job for Promise Tracker Pipeline

Calculates and updates promise progress scores based on evidence links.
This replaces the existing progress scoring scripts with a more robust,
class-based implementation.
"""

import logging
import sys
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional
from pathlib import Path

# Handle imports for both module execution and testing
try:
    from ...core.base_job import BaseJob
except ImportError:
    # Add pipeline directory to path for testing
    pipeline_dir = Path(__file__).parent.parent.parent
    sys.path.insert(0, str(pipeline_dir))
    from core.base_job import BaseJob


class ProgressScorer(BaseJob):
    """
    Job for calculating promise progress scores.
    
    Analyzes promise-evidence links to calculate fulfillment scores
    and update promise progress status.
    """
    
    def __init__(self, job_name: str, config: Dict[str, Any] = None):
        """Initialize the Progress Scorer job"""
        super().__init__(job_name, config)
        
        # Processing settings
        self.batch_size = self.config.get('batch_size', 50)
        self.max_promises_per_run = self.config.get('max_promises_per_run', 500)
        
        # Scoring thresholds
        self.fulfillment_thresholds = self.config.get('fulfillment_thresholds', {
            'not_started': 0.0,
            'in_progress': 0.1,
            'substantial_progress': 0.5,
            'completed': 0.8
        })
        
        # Collections
        self.promises_collection = 'promises'
        self.links_collection = 'promise_evidence_links'
        self.evidence_collection = 'evidence_items'
        self.scores_collection = 'promise_progress_scores'
    
    def _execute_job(self, **kwargs) -> Dict[str, Any]:
        """
        Execute the progress scoring job.
        
        Args:
            **kwargs: Additional job arguments
            
        Returns:
            Job execution statistics
        """
        self.logger.info("Starting promise progress scoring")
        
        stats = {
            'promises_processed': 0,
            'scores_updated': 0,
            'status_changes': 0,
            'errors': 0,
            'metadata': {
                'promises_collection': self.promises_collection,
                'links_collection': self.links_collection,
                'scores_collection': self.scores_collection
            }
        }
        
        try:
            # Get promises to score
            promises_to_score = self._get_promises_to_score()
            
            if not promises_to_score:
                self.logger.info("No promises found for scoring")
                return stats
            
            # Limit promises if configured
            if self.max_promises_per_run:
                promises_to_score = promises_to_score[:self.max_promises_per_run]
            
            self.logger.info(f"Scoring {len(promises_to_score)} promises")
            
            # Process promises in batches
            for i in range(0, len(promises_to_score), self.batch_size):
                batch = promises_to_score[i:i + self.batch_size]
                batch_stats = self._score_promise_batch(batch)
                
                # Update overall stats
                for key in ['promises_processed', 'scores_updated', 'status_changes', 'errors']:
                    stats[key] += batch_stats.get(key, 0)
                
                self.logger.info(f"Scored batch {i//self.batch_size + 1}: "
                               f"{batch_stats['scores_updated']} scores updated, "
                               f"{batch_stats['status_changes']} status changes, "
                               f"{batch_stats['errors']} errors")
            
            self.logger.info(f"Progress scoring completed: {stats['scores_updated']} scores updated, "
                           f"{stats['status_changes']} status changes, {stats['errors']} errors")
            
        except Exception as e:
            self.logger.error(f"Fatal error in progress scoring: {e}", exc_info=True)
            stats['errors'] += 1
            raise
        
        return stats
    
    def _get_promises_to_score(self) -> List[Dict[str, Any]]:
        """Get promises that need progress scoring"""
        try:
            # Get all active promises (we'll check which need scoring)
            query = (self.db.collection(self.promises_collection)
                    .where('status', '==', 'active')
                    .order_by('last_updated_at'))
            
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
    
    def _score_promise_batch(self, batch: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Score a batch of promises"""
        batch_stats = {
            'promises_processed': 0,
            'scores_updated': 0,
            'status_changes': 0,
            'errors': 0
        }
        
        for promise in batch:
            try:
                batch_stats['promises_processed'] += 1
                
                # Calculate progress score
                score_data = self._calculate_promise_score(promise)
                
                if score_data:
                    # Save score and check for status changes
                    status_changed = self._save_promise_score(promise, score_data)
                    batch_stats['scores_updated'] += 1
                    
                    if status_changed:
                        batch_stats['status_changes'] += 1
                        
            except Exception as e:
                self.logger.error(f"Error scoring promise {promise.get('_doc_id', 'unknown')}: {e}")
                batch_stats['errors'] += 1
        
        return batch_stats
    
    def _calculate_promise_score(self, promise: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        Calculate progress score for a promise.
        
        Args:
            promise: Promise document
            
        Returns:
            Score data dictionary or None if calculation failed
        """
        promise_id = promise['_doc_id']
        
        try:
            # Get all evidence links for this promise
            links = self._get_promise_evidence_links(promise_id)
            
            if not links:
                # No evidence found
                return {
                    'promise_id': promise_id,
                    'overall_score': 0.0,
                    'evidence_count': 0,
                    'high_confidence_count': 0,
                    'medium_confidence_count': 0,
                    'low_confidence_count': 0,
                    'fulfillment_status': 'not_started',
                    'score_breakdown': {},
                    'last_evidence_date': None
                }
            
            # Analyze evidence links
            score_breakdown = self._analyze_evidence_links(links)
            
            # Calculate overall score
            overall_score = self._calculate_overall_score(score_breakdown)
            
            # Determine fulfillment status
            fulfillment_status = self._determine_fulfillment_status(overall_score)
            
            # Get latest evidence date
            last_evidence_date = self._get_latest_evidence_date(links)
            
            return {
                'promise_id': promise_id,
                'overall_score': overall_score,
                'evidence_count': len(links),
                'high_confidence_count': score_breakdown.get('high_confidence_count', 0),
                'medium_confidence_count': score_breakdown.get('medium_confidence_count', 0),
                'low_confidence_count': score_breakdown.get('low_confidence_count', 0),
                'fulfillment_status': fulfillment_status,
                'score_breakdown': score_breakdown,
                'last_evidence_date': last_evidence_date,
                'calculated_at': datetime.now(timezone.utc)
            }
            
        except Exception as e:
            self.logger.error(f"Error calculating score for promise {promise_id}: {e}")
            return None
    
    def _get_promise_evidence_links(self, promise_id: str) -> List[Dict[str, Any]]:
        """Get all evidence links for a promise"""
        try:
            links = []
            query = (self.db.collection(self.links_collection)
                    .where('promise_id', '==', promise_id)
                    .where('status', '==', 'active'))
            
            for doc in query.stream():
                link_data = doc.to_dict()
                link_data['_doc_id'] = doc.id
                links.append(link_data)
            
            return links
            
        except Exception as e:
            self.logger.error(f"Error getting evidence links for promise {promise_id}: {e}")
            return []
    
    def _analyze_evidence_links(self, links: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Analyze evidence links to create score breakdown"""
        breakdown = {
            'total_links': len(links),
            'high_confidence_count': 0,
            'medium_confidence_count': 0,
            'low_confidence_count': 0,
            'confidence_weighted_score': 0.0,
            'evidence_types': {},
            'date_distribution': {}
        }
        
        total_confidence = 0.0
        
        for link in links:
            confidence = link.get('confidence_score', 0.0)
            total_confidence += confidence
            
            # Categorize by confidence
            if confidence >= 0.7:
                breakdown['high_confidence_count'] += 1
            elif confidence >= 0.4:
                breakdown['medium_confidence_count'] += 1
            else:
                breakdown['low_confidence_count'] += 1
            
            # Track evidence types (if available)
            evidence_type = link.get('evidence_type', 'unknown')
            breakdown['evidence_types'][evidence_type] = breakdown['evidence_types'].get(evidence_type, 0) + 1
        
        # Calculate confidence-weighted score
        if links:
            breakdown['confidence_weighted_score'] = total_confidence / len(links)
        
        return breakdown
    
    def _calculate_overall_score(self, score_breakdown: Dict[str, Any]) -> float:
        """Calculate overall progress score from breakdown"""
        # Base score from confidence-weighted average
        base_score = score_breakdown.get('confidence_weighted_score', 0.0)
        
        # Boost score based on evidence quantity and quality
        evidence_count = score_breakdown.get('total_links', 0)
        high_confidence_count = score_breakdown.get('high_confidence_count', 0)
        
        # Quantity bonus (diminishing returns)
        quantity_bonus = min(evidence_count * 0.05, 0.2)
        
        # Quality bonus for high-confidence evidence
        quality_bonus = min(high_confidence_count * 0.1, 0.3)
        
        # Combine scores
        overall_score = min(base_score + quantity_bonus + quality_bonus, 1.0)
        
        return round(overall_score, 3)
    
    def _determine_fulfillment_status(self, overall_score: float) -> str:
        """Determine fulfillment status based on score"""
        thresholds = self.fulfillment_thresholds
        
        if overall_score >= thresholds['completed']:
            return 'completed'
        elif overall_score >= thresholds['substantial_progress']:
            return 'substantial_progress'
        elif overall_score >= thresholds['in_progress']:
            return 'in_progress'
        else:
            return 'not_started'
    
    def _get_latest_evidence_date(self, links: List[Dict[str, Any]]) -> Optional[datetime]:
        """Get the date of the most recent evidence"""
        latest_date = None
        
        for link in links:
            # Try to get evidence date from the link or fetch from evidence collection
            evidence_date = link.get('evidence_date')
            
            if not evidence_date:
                # Fetch evidence document to get date
                try:
                    evidence_id = link.get('evidence_id')
                    if evidence_id:
                        evidence_doc = self.db.collection(self.evidence_collection).document(evidence_id).get()
                        if evidence_doc.exists:
                            evidence_data = evidence_doc.to_dict()
                            evidence_date = evidence_data.get('publication_date') or evidence_data.get('created_at')
                except Exception:
                    continue
            
            if evidence_date:
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
            # Save score to scores collection
            score_doc_id = f"{promise_id}_{datetime.now(timezone.utc).strftime('%Y%m%d')}"
            self.db.collection(self.scores_collection).document(score_doc_id).set(score_data)
            
            # Check if promise status needs updating
            current_status = promise.get('progress_status', 'not_started')
            new_status = score_data['fulfillment_status']
            
            if current_status != new_status:
                # Update promise document
                self.db.collection(self.promises_collection).document(promise_id).update({
                    'progress_status': new_status,
                    'progress_score': score_data['overall_score'],
                    'last_scored_at': score_data['calculated_at'],
                    'evidence_count': score_data['evidence_count'],
                    'last_evidence_date': score_data['last_evidence_date']
                })
                
                self.logger.info(f"Promise {promise_id} status changed: {current_status} -> {new_status}")
                status_changed = True
            else:
                # Update score even if status didn't change
                self.db.collection(self.promises_collection).document(promise_id).update({
                    'progress_score': score_data['overall_score'],
                    'last_scored_at': score_data['calculated_at'],
                    'evidence_count': score_data['evidence_count'],
                    'last_evidence_date': score_data['last_evidence_date']
                })
            
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
            'promises_scored': result.promises_processed,
            'status_changes': result.status_changes,
            'trigger_time': datetime.now(timezone.utc).isoformat()
        } 