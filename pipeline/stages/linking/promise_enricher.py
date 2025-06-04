"""
Promise Enricher Job for Promise Tracker Pipeline

Enriches newly created promises with explanations, keywords, action types, 
history, and priority rankings using the consolidated enrichment system.
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

# Import the consolidated enrichment functionality
sys.path.append(str(Path(__file__).parent.parent.parent.parent / "scripts"))
from consolidated_promise_enrichment import ConsolidatedPromiseEnricher

from google.cloud import firestore


class PromiseEnricher(BaseJob):
    """
    Job to enrich newly created promises with explanations, keywords, action types,
    history, and priority rankings.
    """
    
    def __init__(self, job_name: str, config: Dict[str, Any] = None):
        super().__init__(job_name, config)
        
        # Configuration with defaults
        self.batch_size = config.get('batch_size', 10)
        self.max_items_per_run = config.get('max_items_per_run', 50)
        self.enrichment_types = config.get('enrichment_types', ['explanation', 'keywords', 'action_type'])
        self.parliament_session_id = config.get('parliament_session_id', '44')
        self.force_reprocessing = config.get('force_reprocessing', False)
        
        # Collections
        self.promises_collection = config.get('promises_collection', 'promises')
        
        # Initialize enricher
        self.enricher = None
        
    def _execute_job(self, **kwargs) -> Dict[str, Any]:
        """
        Execute the promise enrichment job.
        
        Args:
            **kwargs: Additional job arguments including:
                parliament_session_id: Session to process (default: 44)
                enrichment_types: Types of enrichment to perform
                limit: Max promises to process
                force_reprocessing: Force reprocessing existing promises
                
        Returns:
            Job execution statistics
        """
        self.logger.info("Starting promise enrichment process")
        
        # Extract parameters
        parliament_session_id = str(kwargs.get('parliament_session_id', self.parliament_session_id))
        enrichment_types = kwargs.get('enrichment_types', self.enrichment_types)
        limit = kwargs.get('limit', self.max_items_per_run)
        force_reprocessing = kwargs.get('force_reprocessing', self.force_reprocessing)
        
        stats = {
            'items_processed': 0,
            'items_created': 0,
            'items_updated': 0,
            'items_skipped': 0,
            'errors': 0,
            'metadata': {
                'parliament_session_id': parliament_session_id,
                'promises_collection': self.promises_collection,
                'enrichment_types': enrichment_types,
                'force_reprocessing': force_reprocessing
            }
        }
        
        try:
            # Initialize the consolidated enricher
            self.enricher = ConsolidatedPromiseEnricher()
            
            # Get promises that need enrichment
            promises = self._get_promises_needing_enrichment(
                parliament_session_id, limit, force_reprocessing, enrichment_types
            )
            
            if not promises:
                self.logger.info("No promises found needing enrichment")
                return stats
            
            self.logger.info(f"Processing {len(promises)} promises for enrichment")
            
            # Process promises in batches
            for i in range(0, len(promises), self.batch_size):
                batch = promises[i:i + self.batch_size]
                batch_stats = self._process_promise_batch(batch, enrichment_types)
                
                # Update overall stats
                for key in ['items_processed', 'items_updated', 'items_skipped', 'errors']:
                    stats[key] += batch_stats.get(key, 0)
                
                self.logger.info(f"Processed batch {i//self.batch_size + 1}: "
                               f"{batch_stats['items_updated']} promises enriched, "
                               f"{batch_stats['items_skipped']} skipped, "
                               f"{batch_stats['errors']} errors")
            
            # Add enricher stats
            if self.enricher:
                stats['metadata']['enricher_stats'] = self.enricher.stats
            
            self.logger.info(f"Promise enrichment completed: {stats['items_updated']} promises enriched, "
                           f"{stats['items_skipped']} skipped, {stats['errors']} errors")
            
        except Exception as e:
            self.logger.error(f"Fatal error in promise enrichment: {e}", exc_info=True)
            stats['errors'] += 1
            raise
        
        return stats
    
    def _get_promises_needing_enrichment(
        self, 
        parliament_session_id: str, 
        limit: Optional[int],
        force_reprocessing: bool,
        enrichment_types: List[str]
    ) -> List[Dict[str, Any]]:
        """Get promises that need enrichment."""
        try:
            query = self.db.collection(self.promises_collection)
            
            # Filter by parliament session
            query = query.where(
                filter=firestore.FieldFilter("parliament_session_id", "==", parliament_session_id)
            )
            
            # Filter by party (focus on LPC promises for enrichment)
            query = query.where(
                filter=firestore.FieldFilter("party_code", "==", "LPC")
            )
            
            # Apply limit if specified
            if limit:
                query = query.limit(limit)
            
            # Execute query
            promise_docs = list(query.stream())
            
            promises = []
            for doc in promise_docs:
                data = doc.to_dict()
                if not data or not data.get("text"):
                    continue
                
                # Check if enrichment is needed
                needs_enrichment = force_reprocessing
                
                if not needs_enrichment:
                    # Check specific enrichment types
                    if 'explanation' in enrichment_types:
                        needs_enrichment = (
                            data.get('what_it_means_for_canadians') is None or
                            data.get('background_and_context') is None or
                            data.get('description') is None
                        )
                    
                    if not needs_enrichment and 'keywords' in enrichment_types:
                        needs_enrichment = data.get('extracted_keywords_concepts') is None
                    
                    if not needs_enrichment and 'action_type' in enrichment_types:
                        needs_enrichment = data.get('implied_action_type') is None
                    
                    if not needs_enrichment and 'history' in enrichment_types:
                        needs_enrichment = data.get('commitment_history_rationale') is None
                    
                    if not needs_enrichment and 'priority' in enrichment_types:
                        needs_enrichment = data.get('bc_priority_score') is None
                
                if needs_enrichment:
                    promises.append({
                        "id": doc.id,
                        "text": data["text"],
                        "responsible_department_lead": data.get("responsible_department_lead"),
                        "source_type": data.get("source_type"),
                        "party_code": data.get("party_code"),
                        "doc_ref": doc.reference,
                        "data": data
                    })
            
            return promises
            
        except Exception as e:
            self.logger.error(f"Error getting promises needing enrichment: {e}")
            return []
    
    def _process_promise_batch(self, batch: List[Dict[str, Any]], enrichment_types: List[str]) -> Dict[str, Any]:
        """Process a batch of promises for enrichment."""
        batch_stats = {
            'items_processed': 0,
            'items_updated': 0,
            'items_skipped': 0,
            'errors': 0
        }
        
        for promise in batch:
            try:
                batch_stats['items_processed'] += 1
                
                # Use the consolidated enricher to enrich the promise
                import asyncio
                
                async def enrich_promise():
                    return await self.enricher.enrich_single_promise(
                        promise, enrichment_types, dry_run=False
                    )
                
                # Run the async enrichment
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                try:
                    success = loop.run_until_complete(enrich_promise())
                finally:
                    loop.close()
                
                if success:
                    batch_stats['items_updated'] += 1
                    self.logger.info(f"Successfully enriched promise {promise['id']}")
                else:
                    batch_stats['items_skipped'] += 1
                    self.logger.warning(f"Failed to enrich promise {promise['id']}")
                    
            except Exception as e:
                self.logger.error(f"Error processing promise {promise.get('id', 'unknown')}: {e}")
                batch_stats['errors'] += 1
        
        return batch_stats
    
    def should_trigger_downstream(self, result) -> bool:
        """
        Promise enrichment typically doesn't trigger downstream jobs.
        This is a terminal enrichment step.
        
        Args:
            result: Job execution result
            
        Returns:
            False - no downstream triggers needed
        """
        return False
    
    def get_trigger_metadata(self, result) -> Dict[str, Any]:
        """
        Get metadata for any potential downstream jobs.
        
        Args:
            result: Job execution result
            
        Returns:
            Metadata for downstream jobs
        """
        return {
            'triggered_by': self.job_name,
            'promises_enriched': result.items_updated,
            'promises_processed': result.items_processed,
            'trigger_time': datetime.now(timezone.utc).isoformat(),
            'enrichment_types': result.metadata.get('enrichment_types', [])
        } 