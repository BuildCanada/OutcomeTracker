"""
Base Processor Job for Promise Tracker Pipeline

All processing jobs inherit from this base class to ensure consistent
data transformation patterns and LLM integration.
"""

import logging
import sys
from abc import abstractmethod
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


class BaseProcessorJob(BaseJob):
    """
    Base class for all data processing jobs.
    
    Provides common functionality for:
    - Raw data retrieval
    - LLM-based analysis
    - Evidence item creation
    - Status tracking
    """
    
    def __init__(self, job_name: str, config: Dict[str, Any] = None):
        """
        Initialize the processing job.
        
        Args:
            job_name: Unique name for this job
            config: Job-specific configuration
        """
        super().__init__(job_name, config)
        self.source_collection = self._get_source_collection()
        self.target_collection = self._get_target_collection()
        
        # Processing settings
        self.batch_size = self.config.get('batch_size', 10)
        self.max_items_per_run = self.config.get('max_items_per_run', 100)
        
    @abstractmethod
    def _get_source_collection(self) -> str:
        """Return the Firestore collection name for raw data"""
        pass
    
    @abstractmethod
    def _get_target_collection(self) -> str:
        """Return the Firestore collection name for evidence items"""
        pass
    
    @abstractmethod
    def _process_raw_item(self, raw_item: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        Process a single raw item into an evidence item.
        
        Args:
            raw_item: Raw data item from source collection
            
        Returns:
            Evidence item ready for storage or None if processing failed
        """
        pass
    
    def _execute_job(self, **kwargs) -> Dict[str, Any]:
        """
        Execute the processing job.
        
        Args:
            **kwargs: Additional job arguments
            
        Returns:
            Job execution statistics
        """
        self.logger.info(f"Starting processing from {self.source_collection} to {self.target_collection}")
        
        stats = {
            'items_processed': 0,
            'items_created': 0,
            'items_updated': 0,
            'items_skipped': 0,
            'errors': 0,
            'metadata': {
                'source_collection': self.source_collection,
                'target_collection': self.target_collection
            }
        }
        
        try:
            # Get items to process
            items_to_process = self._get_items_to_process()
            
            if not items_to_process:
                self.logger.info("No items found for processing")
                return stats
            
            # Limit items if configured
            if self.max_items_per_run:
                items_to_process = items_to_process[:self.max_items_per_run]
            
            self.logger.info(f"Processing {len(items_to_process)} items")
            
            # Process items in batches
            for i in range(0, len(items_to_process), self.batch_size):
                batch = items_to_process[i:i + self.batch_size]
                batch_stats = self._process_batch(batch)
                
                # Update overall stats
                for key in ['items_processed', 'items_created', 'items_updated', 'items_skipped', 'errors']:
                    stats[key] += batch_stats.get(key, 0)
                
                self.logger.info(f"Processed batch {i//self.batch_size + 1}: "
                               f"{batch_stats['items_created']} created, "
                               f"{batch_stats['items_updated']} updated, "
                               f"{batch_stats['items_skipped']} skipped, "
                               f"{batch_stats['errors']} errors")
            
            self.logger.info(f"Processing completed: {stats['items_created']} created, "
                           f"{stats['items_updated']} updated, {stats['items_skipped']} skipped, "
                           f"{stats['errors']} errors")
            
        except Exception as e:
            self.logger.error(f"Fatal error in processing: {e}", exc_info=True)
            stats['errors'] += 1
            raise
        
        return stats
    
    def _get_items_to_process(self) -> List[Dict[str, Any]]:
        """Get raw items that need processing"""
        try:
            # Query for items with pending status
            query = (self.db.collection(self.source_collection)
                    .where('evidence_processing_status', '==', 'pending_evidence_creation')
                    .order_by('last_updated_at')
                    .limit(self.max_items_per_run * 2))  # Get extra to account for filtering
            
            items = []
            for doc in query.stream():
                item_data = doc.to_dict()
                item_data['_doc_id'] = doc.id
                items.append(item_data)
            
            self.logger.info(f"Found {len(items)} items with pending status")
            return items
            
        except Exception as e:
            self.logger.error(f"Error querying items to process: {e}")
            return []
    
    def _process_batch(self, batch: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Process a batch of raw items"""
        batch_stats = {
            'items_processed': 0,
            'items_created': 0,
            'items_updated': 0,
            'items_skipped': 0,
            'errors': 0
        }
        
        for raw_item in batch:
            try:
                batch_stats['items_processed'] += 1
                
                # Process the raw item
                evidence_item = self._process_raw_item(raw_item)
                
                if evidence_item:
                    # Save evidence item and update status
                    result = self._save_evidence_item(evidence_item, raw_item)
                    
                    if result == 'created':
                        batch_stats['items_created'] += 1
                    elif result == 'updated':
                        batch_stats['items_updated'] += 1
                    else:
                        batch_stats['items_skipped'] += 1
                else:
                    # Mark as processing error
                    self._update_processing_status(raw_item['_doc_id'], 'error_processing_script')
                    batch_stats['errors'] += 1
                    
            except Exception as e:
                self.logger.error(f"Error processing item {raw_item.get('_doc_id', 'unknown')}: {e}")
                batch_stats['errors'] += 1
                
                # Mark as processing error
                try:
                    self._update_processing_status(raw_item['_doc_id'], 'error_processing_script')
                except Exception:
                    pass  # Don't fail the batch if status update fails
        
        return batch_stats
    
    def _save_evidence_item(self, evidence_item: Dict[str, Any], 
                           raw_item: Dict[str, Any]) -> str:
        """
        Save evidence item to target collection and update source status.
        
        Args:
            evidence_item: Processed evidence item
            raw_item: Original raw item
            
        Returns:
            'created', 'updated', or 'skipped'
        """
        try:
            # Generate evidence item ID
            evidence_id = self._generate_evidence_id(evidence_item, raw_item)
            
            # Check if evidence item already exists
            evidence_ref = self.db.collection(self.target_collection).document(evidence_id)
            existing_doc = evidence_ref.get()
            
            # Add metadata
            evidence_item.update({
                'created_at': datetime.now(timezone.utc),
                'last_updated_at': datetime.now(timezone.utc),
                'source_collection': self.source_collection,
                'source_document_id': raw_item['_doc_id'],
                'processing_job': self.job_name
            })
            
            if existing_doc.exists:
                # Check if update is needed
                if self._should_update_evidence(existing_doc.to_dict(), evidence_item):
                    evidence_item['created_at'] = existing_doc.to_dict().get('created_at')
                    evidence_ref.set(evidence_item)
                    self._update_processing_status(raw_item['_doc_id'], 'evidence_created')
                    return 'updated'
                else:
                    self._update_processing_status(raw_item['_doc_id'], 'evidence_created')
                    return 'skipped'
            else:
                # Create new evidence item
                evidence_ref.set(evidence_item)
                self._update_processing_status(raw_item['_doc_id'], 'evidence_created')
                return 'created'
                
        except Exception as e:
            self.logger.error(f"Error saving evidence item: {e}")
            raise
    
    def _generate_evidence_id(self, evidence_item: Dict[str, Any], 
                             raw_item: Dict[str, Any]) -> str:
        """
        Generate a unique ID for the evidence item using standardized pattern.
        All processors should use this centralized method for consistency.
        
        Args:
            evidence_item: Processed evidence item
            raw_item: Original raw item
            
        Returns:
            Unique evidence ID in format: YYYYMMDD_{session}_{source_type}_{hash}
        """
        import hashlib
        
        # Get date for ID (prefer evidence date, fallback to current date)
        evidence_date = evidence_item.get('evidence_date') or evidence_item.get('publication_date')
        if evidence_date:
            if hasattr(evidence_date, 'strftime'):
                date_str = evidence_date.strftime('%Y%m%d')
            else:
                # Handle string dates
                try:
                    from datetime import datetime
                    if isinstance(evidence_date, str):
                        # Try parsing common date formats
                        for fmt in ['%Y-%m-%d', '%Y-%m-%dT%H:%M:%S', '%Y-%m-%dT%H:%M:%SZ']:
                            try:
                                parsed_date = datetime.strptime(evidence_date.split('T')[0], '%Y-%m-%d')
                                date_str = parsed_date.strftime('%Y%m%d')
                                break
                            except ValueError:
                                continue
                        else:
                            date_str = datetime.now().strftime('%Y%m%d')
                    else:
                        date_str = datetime.now().strftime('%Y%m%d')
                except:
                    date_str = datetime.now().strftime('%Y%m%d')
        else:
            date_str = datetime.now().strftime('%Y%m%d')
        
        # Get parliament session
        session_id = evidence_item.get('parliament_session_id', 'unknown')
        
        # Determine source type for ID
        source_type = self._get_evidence_id_source_type()
        
        # Create hash from key content for uniqueness
        content_for_hash = f"{evidence_item.get('title_or_summary', '')}{evidence_item.get('source_url', '')}{raw_item.get('_doc_id', '')}"
        short_hash = hashlib.md5(content_for_hash.encode()).hexdigest()[:8]
        
        return f"{date_str}_{session_id}_{source_type}_{short_hash}"
    
    def _get_evidence_id_source_type(self) -> str:
        """
        Get the source type identifier for evidence ID generation.
        Override in subclasses to provide source-specific identifiers.
        
        Returns:
            Source type string for evidence ID
        """
        # Default implementation - derive from class name
        class_name = self.__class__.__name__
        if 'CanadaNews' in class_name:
            return 'CanadaNews'
        elif 'LegisInfo' in class_name:
            return 'LegisInfo'
        elif 'OrdersInCouncil' in class_name:
            return 'OrdersInCouncil'
        elif 'CanadaGazette' in class_name:
            return 'CanadaGazette'
        elif 'Manual' in class_name:
            return 'Manual'
        else:
            return 'Unknown'
    
    def _should_update_evidence(self, existing_evidence: Dict[str, Any], 
                               new_evidence: Dict[str, Any]) -> bool:
        """
        Determine if an existing evidence item should be updated.
        Override in subclasses for source-specific update logic.
        
        Args:
            existing_evidence: Current evidence item in database
            new_evidence: New evidence item from processing
            
        Returns:
            True if evidence should be updated
        """
        # Default implementation - check if content has changed
        content_fields = ['title', 'description', 'full_text', 'summary']
        
        for field in content_fields:
            if field in new_evidence and field in existing_evidence:
                if new_evidence[field] != existing_evidence[field]:
                    return True
        
        return False
    
    def _update_processing_status(self, doc_id: str, status: str):
        """Update the processing status of a raw item"""
        try:
            self.db.collection(self.source_collection).document(doc_id).update({
                'evidence_processing_status': status,
                'evidence_processing_timestamp': datetime.now(timezone.utc)
            })
        except Exception as e:
            self.logger.warning(f"Failed to update processing status for {doc_id}: {e}")
    
    def should_trigger_downstream(self, result) -> bool:
        """
        Trigger downstream linking if new evidence was created.
        
        Args:
            result: Job execution result
            
        Returns:
            True if downstream jobs should be triggered
        """
        return result.items_created > 0
    
    def get_trigger_metadata(self, result) -> Dict[str, Any]:
        """
        Get metadata for downstream linking jobs.
        
        Args:
            result: Job execution result
            
        Returns:
            Metadata for downstream jobs
        """
        return {
            'triggered_by': self.job_name,
            'source_collection': self.source_collection,
            'target_collection': self.target_collection,
            'items_created': result.items_created,
            'items_updated': result.items_updated,
            'trigger_time': datetime.now(timezone.utc).isoformat()
        } 