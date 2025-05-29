"""
Base Ingestion Job for Promise Tracker Pipeline

All ingestion jobs inherit from this base class to ensure consistent
data collection patterns and error handling.
"""

import logging
import sys
from abc import abstractmethod
from datetime import datetime, timezone, timedelta
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


class BaseIngestionJob(BaseJob):
    """
    Base class for all data ingestion jobs.
    
    Provides common functionality for:
    - RSS feed monitoring
    - Data source polling
    - Duplicate detection
    - Status tracking
    """
    
    def __init__(self, job_name: str, config: Dict[str, Any] = None):
        """
        Initialize the ingestion job.
        
        Args:
            job_name: Unique name for this job
            config: Job-specific configuration
        """
        super().__init__(job_name, config)
        self.source_name = self._get_source_name()
        self.collection_name = self._get_collection_name()
        
    @abstractmethod
    def _get_source_name(self) -> str:
        """Return the human-readable name of the data source"""
        pass
    
    @abstractmethod
    def _get_collection_name(self) -> str:
        """Return the Firestore collection name for raw data"""
        pass
    
    @abstractmethod
    def _fetch_new_items(self, since_date: datetime = None) -> List[Dict[str, Any]]:
        """
        Fetch new items from the data source.
        
        Args:
            since_date: Only fetch items newer than this date
            
        Returns:
            List of raw data items
        """
        pass
    
    @abstractmethod
    def _process_raw_item(self, raw_item: Dict[str, Any]) -> Dict[str, Any]:
        """
        Process a single raw item into standardized format.
        
        Args:
            raw_item: Raw item from data source
            
        Returns:
            Processed item ready for Firestore storage
        """
        pass
    
    def _execute_job(self, since_hours: int = 24, **kwargs) -> Dict[str, Any]:
        """
        Execute the ingestion job.
        
        Args:
            since_hours: Only fetch items from the last N hours
            **kwargs: Additional job arguments
            
        Returns:
            Job execution statistics
        """
        self.logger.info(f"Starting {self.source_name} ingestion")
        
        # Calculate since date
        since_date = datetime.now(timezone.utc) - timedelta(hours=since_hours)
        
        stats = {
            'items_processed': 0,
            'items_created': 0,
            'items_updated': 0,
            'items_skipped': 0,
            'errors': 0,
            'metadata': {
                'source_name': self.source_name,
                'since_date': since_date.isoformat(),
                'collection_name': self.collection_name
            }
        }
        
        try:
            # Fetch new items from source
            self.logger.info(f"Fetching items since {since_date}")
            raw_items = self._fetch_new_items(since_date)
            self.logger.info(f"Found {len(raw_items)} items to process")
            
            # Process each item
            for raw_item in raw_items:
                try:
                    stats['items_processed'] += 1
                    
                    # Process the raw item
                    processed_item = self._process_raw_item(raw_item)
                    
                    # Check if item already exists
                    item_id = self._generate_item_id(processed_item)
                    existing_doc = self.db.collection(self.collection_name).document(item_id).get()
                    
                    if existing_doc.exists:
                        # Check if update is needed
                        if self._should_update_item(existing_doc.to_dict(), processed_item):
                            self.db.collection(self.collection_name).document(item_id).update(processed_item)
                            stats['items_updated'] += 1
                            self.logger.debug(f"Updated item: {item_id}")
                        else:
                            stats['items_skipped'] += 1
                            self.logger.debug(f"Skipped unchanged item: {item_id}")
                    else:
                        # Create new item
                        processed_item['ingested_at'] = datetime.now(timezone.utc)
                        processed_item['ingestion_job'] = self.job_name
                        self.db.collection(self.collection_name).document(item_id).set(processed_item)
                        stats['items_created'] += 1
                        self.logger.debug(f"Created new item: {item_id}")
                        
                except Exception as e:
                    stats['errors'] += 1
                    self.logger.error(f"Error processing item: {e}", exc_info=True)
                    continue
            
            self.logger.info(f"Ingestion completed: {stats['items_created']} created, "
                           f"{stats['items_updated']} updated, {stats['items_skipped']} skipped, "
                           f"{stats['errors']} errors")
            
        except Exception as e:
            self.logger.error(f"Fatal error in {self.source_name} ingestion: {e}", exc_info=True)
            stats['errors'] += 1
            raise
        
        return stats
    
    def _generate_item_id(self, item: Dict[str, Any]) -> str:
        """
        Generate a unique ID for the item.
        Override in subclasses for source-specific ID generation.
        
        Args:
            item: Processed item
            
        Returns:
            Unique item ID
        """
        # Default implementation - override in subclasses
        import hashlib
        
        # Use URL or title + date for ID generation
        id_source = item.get('source_url', '') + str(item.get('publication_date', ''))
        return hashlib.sha256(id_source.encode()).hexdigest()[:16]
    
    def _should_update_item(self, existing_item: Dict[str, Any], 
                           new_item: Dict[str, Any]) -> bool:
        """
        Determine if an existing item should be updated.
        Override in subclasses for source-specific update logic.
        
        Args:
            existing_item: Current item in database
            new_item: New item from source
            
        Returns:
            True if item should be updated
        """
        # Default implementation - check if content has changed
        content_fields = ['title', 'description', 'content', 'full_text']
        
        for field in content_fields:
            if field in new_item and field in existing_item:
                if new_item[field] != existing_item[field]:
                    return True
        
        return False
    
    def should_trigger_downstream(self, result) -> bool:
        """
        Trigger downstream processing if new items were created.
        
        Args:
            result: Job execution result
            
        Returns:
            True if downstream jobs should be triggered
        """
        return result.items_created > 0
    
    def get_trigger_metadata(self, result) -> Dict[str, Any]:
        """
        Get metadata for downstream processing jobs.
        
        Args:
            result: Job execution result
            
        Returns:
            Metadata for downstream jobs
        """
        return {
            'triggered_by': self.job_name,
            'source_name': self.source_name,
            'collection_name': self.collection_name,
            'items_created': result.items_created,
            'items_updated': result.items_updated,
            'trigger_time': datetime.now(timezone.utc).isoformat()
        } 