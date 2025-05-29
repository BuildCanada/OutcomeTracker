"""
Evidence Linker Job for Promise Tracker Pipeline

Links evidence items to promises and creates promise-evidence relationships.
This replaces the existing evidence linking scripts with a more robust,
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


class EvidenceLinker(BaseJob):
    """
    Job for linking evidence items to promises.
    
    Analyzes evidence items and creates relationships with relevant promises
    based on content similarity and semantic matching.
    """
    
    def __init__(self, job_name: str, config: Dict[str, Any] = None):
        """Initialize the Evidence Linker job"""
        super().__init__(job_name, config)
        
        # Processing settings
        self.batch_size = self.config.get('batch_size', 20)
        self.max_items_per_run = self.config.get('max_items_per_run', 200)
        self.min_confidence_threshold = self.config.get('min_confidence_threshold', 0.3)
        
        # Collections
        self.evidence_collection = 'evidence_items'
        self.promises_collection = 'promises'
        self.links_collection = 'promise_evidence_links'
        
        # Cache for promises to avoid repeated queries
        self._promises_cache = None
    
    def _execute_job(self, **kwargs) -> Dict[str, Any]:
        """
        Execute the evidence linking job.
        
        Args:
            **kwargs: Additional job arguments
            
        Returns:
            Job execution statistics
        """
        self.logger.info("Starting evidence linking process")
        
        stats = {
            'items_processed': 0,
            'items_created': 0,
            'items_updated': 0,
            'items_skipped': 0,
            'errors': 0,
            'metadata': {
                'evidence_collection': self.evidence_collection,
                'promises_collection': self.promises_collection,
                'links_collection': self.links_collection
            }
        }
        
        try:
            # Load promises cache
            self._load_promises_cache()
            
            if not self._promises_cache:
                self.logger.warning("No promises found for linking")
                return stats
            
            # Get evidence items to process
            evidence_items = self._get_evidence_items_to_process()
            
            if not evidence_items:
                self.logger.info("No evidence items found for linking")
                return stats
            
            # Limit items if configured
            if self.max_items_per_run:
                evidence_items = evidence_items[:self.max_items_per_run]
            
            self.logger.info(f"Processing {len(evidence_items)} evidence items against {len(self._promises_cache)} promises")
            
            # Process evidence items in batches
            for i in range(0, len(evidence_items), self.batch_size):
                batch = evidence_items[i:i + self.batch_size]
                batch_stats = self._process_evidence_batch(batch)
                
                # Update overall stats
                for key in ['items_processed', 'items_created', 'items_updated', 'items_skipped', 'errors']:
                    stats[key] += batch_stats.get(key, 0)
                
                self.logger.info(f"Processed batch {i//self.batch_size + 1}: "
                               f"{batch_stats['items_created']} links created, "
                               f"{batch_stats['items_updated']} updated, "
                               f"{batch_stats['items_skipped']} skipped, "
                               f"{batch_stats['errors']} errors")
            
            self.logger.info(f"Evidence linking completed: {stats['items_created']} links created, "
                           f"{stats['items_updated']} updated, {stats['items_skipped']} skipped, "
                           f"{stats['errors']} errors")
            
        except Exception as e:
            self.logger.error(f"Fatal error in evidence linking: {e}", exc_info=True)
            stats['errors'] += 1
            raise
        
        return stats
    
    def _load_promises_cache(self):
        """Load all active promises into memory for linking"""
        try:
            self._promises_cache = []
            
            # Query for active promises
            promises_ref = self.db.collection(self.promises_collection).where('status', '==', 'active')
            
            for doc in promises_ref.stream():
                promise_data = doc.to_dict()
                promise_data['_doc_id'] = doc.id
                self._promises_cache.append(promise_data)
            
            self.logger.info(f"Loaded {len(self._promises_cache)} active promises for linking")
            
        except Exception as e:
            self.logger.error(f"Error loading promises cache: {e}")
            self._promises_cache = []
    
    def _get_evidence_items_to_process(self) -> List[Dict[str, Any]]:
        """Get evidence items that need linking"""
        try:
            # Query for evidence items that haven't been processed for linking
            # or have been updated since last linking
            query = (self.db.collection(self.evidence_collection)
                    .where('linking_status', 'in', ['pending', 'needs_relinking'])
                    .order_by('last_updated_at')
                    .limit(self.max_items_per_run * 2))
            
            items = []
            for doc in query.stream():
                item_data = doc.to_dict()
                item_data['_doc_id'] = doc.id
                items.append(item_data)
            
            self.logger.info(f"Found {len(items)} evidence items for linking")
            return items
            
        except Exception as e:
            self.logger.error(f"Error querying evidence items: {e}")
            return []
    
    def _process_evidence_batch(self, batch: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Process a batch of evidence items for linking"""
        batch_stats = {
            'items_processed': 0,
            'items_created': 0,
            'items_updated': 0,
            'items_skipped': 0,
            'errors': 0
        }
        
        for evidence_item in batch:
            try:
                batch_stats['items_processed'] += 1
                
                # Find matching promises for this evidence item
                matches = self._find_promise_matches(evidence_item)
                
                if matches:
                    # Create or update links
                    links_created = self._create_evidence_links(evidence_item, matches)
                    batch_stats['items_created'] += links_created
                    
                    # Update evidence item linking status
                    self._update_evidence_linking_status(evidence_item['_doc_id'], 'linked', len(matches))
                else:
                    # No matches found
                    self._update_evidence_linking_status(evidence_item['_doc_id'], 'no_matches', 0)
                    batch_stats['items_skipped'] += 1
                    
            except Exception as e:
                self.logger.error(f"Error processing evidence item {evidence_item.get('_doc_id', 'unknown')}: {e}")
                batch_stats['errors'] += 1
                
                # Mark as linking error
                try:
                    self._update_evidence_linking_status(evidence_item['_doc_id'], 'error', 0)
                except Exception:
                    pass
        
        return batch_stats
    
    def _find_promise_matches(self, evidence_item: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Find promises that match the evidence item.
        
        Args:
            evidence_item: Evidence item to match
            
        Returns:
            List of matching promises with confidence scores
        """
        matches = []
        
        # Extract evidence content for matching
        evidence_text = self._extract_evidence_text(evidence_item)
        if not evidence_text:
            return matches
        
        # Simple keyword-based matching (can be enhanced with semantic similarity)
        for promise in self._promises_cache:
            confidence = self._calculate_match_confidence(evidence_item, promise, evidence_text)
            
            if confidence >= self.min_confidence_threshold:
                matches.append({
                    'promise': promise,
                    'confidence': confidence,
                    'match_reasons': self._get_match_reasons(evidence_item, promise, evidence_text)
                })
        
        # Sort by confidence (highest first)
        matches.sort(key=lambda x: x['confidence'], reverse=True)
        
        return matches
    
    def _extract_evidence_text(self, evidence_item: Dict[str, Any]) -> str:
        """Extract searchable text from evidence item"""
        text_parts = []
        
        # Combine various text fields
        for field in ['title', 'description', 'summary', 'full_text']:
            if field in evidence_item and evidence_item[field]:
                text_parts.append(str(evidence_item[field]))
        
        return ' '.join(text_parts).lower()
    
    def _calculate_match_confidence(self, evidence_item: Dict[str, Any], 
                                  promise: Dict[str, Any], evidence_text: str) -> float:
        """
        Calculate confidence score for evidence-promise match.
        
        Args:
            evidence_item: Evidence item
            promise: Promise to match against
            evidence_text: Extracted evidence text
            
        Returns:
            Confidence score between 0 and 1
        """
        confidence = 0.0
        
        # Extract promise text
        promise_text = self._extract_promise_text(promise)
        if not promise_text:
            return confidence
        
        # Simple keyword matching (can be enhanced with NLP/embeddings)
        promise_keywords = set(promise_text.lower().split())
        evidence_keywords = set(evidence_text.split())
        
        # Calculate keyword overlap
        common_keywords = promise_keywords.intersection(evidence_keywords)
        if promise_keywords:
            keyword_overlap = len(common_keywords) / len(promise_keywords)
            confidence += keyword_overlap * 0.5
        
        # Check for specific matches
        # Department/ministry matching
        if self._check_department_match(evidence_item, promise):
            confidence += 0.2
        
        # Date relevance
        if self._check_date_relevance(evidence_item, promise):
            confidence += 0.1
        
        # Policy area matching
        if self._check_policy_area_match(evidence_item, promise):
            confidence += 0.2
        
        return min(confidence, 1.0)  # Cap at 1.0
    
    def _extract_promise_text(self, promise: Dict[str, Any]) -> str:
        """Extract searchable text from promise"""
        text_parts = []
        
        for field in ['title', 'description', 'full_text', 'summary']:
            if field in promise and promise[field]:
                text_parts.append(str(promise[field]))
        
        return ' '.join(text_parts)
    
    def _check_department_match(self, evidence_item: Dict[str, Any], 
                               promise: Dict[str, Any]) -> bool:
        """Check if evidence and promise are from the same department"""
        evidence_dept = evidence_item.get('department', '').lower()
        promise_dept = promise.get('responsible_department', '').lower()
        
        if evidence_dept and promise_dept:
            return evidence_dept in promise_dept or promise_dept in evidence_dept
        
        return False
    
    def _check_date_relevance(self, evidence_item: Dict[str, Any], 
                             promise: Dict[str, Any]) -> bool:
        """Check if evidence date is relevant to promise timeline"""
        evidence_date = evidence_item.get('publication_date')
        promise_date = promise.get('created_at')
        
        if evidence_date and promise_date:
            # Evidence should be after promise was made
            return evidence_date >= promise_date
        
        return False
    
    def _check_policy_area_match(self, evidence_item: Dict[str, Any], 
                                promise: Dict[str, Any]) -> bool:
        """Check if evidence and promise are in the same policy area"""
        evidence_tags = set(evidence_item.get('tags', []))
        promise_tags = set(promise.get('policy_areas', []))
        
        if evidence_tags and promise_tags:
            return bool(evidence_tags.intersection(promise_tags))
        
        return False
    
    def _get_match_reasons(self, evidence_item: Dict[str, Any], 
                          promise: Dict[str, Any], evidence_text: str) -> List[str]:
        """Get human-readable reasons for the match"""
        reasons = []
        
        if self._check_department_match(evidence_item, promise):
            reasons.append("Department match")
        
        if self._check_date_relevance(evidence_item, promise):
            reasons.append("Date relevance")
        
        if self._check_policy_area_match(evidence_item, promise):
            reasons.append("Policy area match")
        
        # Add keyword overlap reason
        promise_text = self._extract_promise_text(promise)
        promise_keywords = set(promise_text.lower().split())
        evidence_keywords = set(evidence_text.split())
        common_keywords = promise_keywords.intersection(evidence_keywords)
        
        if len(common_keywords) > 3:
            reasons.append(f"Keyword overlap ({len(common_keywords)} common terms)")
        
        return reasons
    
    def _create_evidence_links(self, evidence_item: Dict[str, Any], 
                              matches: List[Dict[str, Any]]) -> int:
        """
        Create promise-evidence links for matches.
        
        Args:
            evidence_item: Evidence item
            matches: List of matching promises with confidence scores
            
        Returns:
            Number of links created
        """
        links_created = 0
        
        for match in matches:
            try:
                promise = match['promise']
                
                # Generate link ID
                link_id = f"{promise['_doc_id']}_{evidence_item['_doc_id']}"
                
                # Create link document
                link_data = {
                    'promise_id': promise['_doc_id'],
                    'evidence_id': evidence_item['_doc_id'],
                    'confidence_score': match['confidence'],
                    'match_reasons': match['match_reasons'],
                    'link_type': 'automatic',
                    'created_at': datetime.now(timezone.utc),
                    'created_by_job': self.job_name,
                    'status': 'active'
                }
                
                # Check if link already exists
                link_ref = self.db.collection(self.links_collection).document(link_id)
                existing_link = link_ref.get()
                
                if existing_link.exists:
                    # Update existing link if confidence has changed significantly
                    existing_confidence = existing_link.to_dict().get('confidence_score', 0)
                    if abs(match['confidence'] - existing_confidence) > 0.1:
                        link_data['updated_at'] = datetime.now(timezone.utc)
                        link_data['created_at'] = existing_link.to_dict().get('created_at')
                        link_ref.set(link_data)
                else:
                    # Create new link
                    link_ref.set(link_data)
                    links_created += 1
                
            except Exception as e:
                self.logger.error(f"Error creating link for promise {match['promise']['_doc_id']}: {e}")
                continue
        
        return links_created
    
    def _update_evidence_linking_status(self, evidence_id: str, status: str, links_count: int):
        """Update the linking status of an evidence item"""
        try:
            self.db.collection(self.evidence_collection).document(evidence_id).update({
                'linking_status': status,
                'linking_timestamp': datetime.now(timezone.utc),
                'links_count': links_count
            })
        except Exception as e:
            self.logger.warning(f"Failed to update linking status for {evidence_id}: {e}")
    
    def should_trigger_downstream(self, result) -> bool:
        """
        Trigger downstream progress scoring if new links were created.
        
        Args:
            result: Job execution result
            
        Returns:
            True if downstream jobs should be triggered
        """
        return result.items_created > 0
    
    def get_trigger_metadata(self, result) -> Dict[str, Any]:
        """
        Get metadata for downstream progress scoring jobs.
        
        Args:
            result: Job execution result
            
        Returns:
            Metadata for downstream jobs
        """
        return {
            'triggered_by': self.job_name,
            'links_created': result.items_created,
            'evidence_processed': result.items_processed,
            'trigger_time': datetime.now(timezone.utc).isoformat()
        } 