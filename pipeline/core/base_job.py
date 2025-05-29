"""
Base Job Class for Promise Tracker Pipeline

All pipeline jobs inherit from this base class to ensure consistent
interface, error handling, and monitoring.
"""

import logging
import time
from abc import ABC, abstractmethod
from datetime import datetime, timezone
from typing import Dict, Any, Optional, List
from dataclasses import dataclass
from enum import Enum

import firebase_admin
from firebase_admin import firestore


class JobStatus(Enum):
    """Job execution status"""
    PENDING = "pending"
    RUNNING = "running"
    SUCCESS = "success"
    FAILED = "failed"
    TIMEOUT = "timeout"
    CANCELLED = "cancelled"


@dataclass
class JobResult:
    """Standardized job result"""
    job_name: str
    status: JobStatus
    start_time: datetime
    end_time: Optional[datetime] = None
    duration_seconds: Optional[float] = None
    items_processed: int = 0
    items_created: int = 0
    items_updated: int = 0
    items_skipped: int = 0
    errors: int = 0
    error_message: Optional[str] = None
    metadata: Dict[str, Any] = None
    
    def __post_init__(self):
        if self.metadata is None:
            self.metadata = {}
        
        if self.end_time and self.start_time:
            self.duration_seconds = (self.end_time - self.start_time).total_seconds()
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert JobResult to dictionary for serialization"""
        return {
            'job_name': self.job_name,
            'status': self.status.value,
            'start_time': self.start_time.isoformat() if self.start_time else None,
            'end_time': self.end_time.isoformat() if self.end_time else None,
            'duration_seconds': self.duration_seconds,
            'items_processed': self.items_processed,
            'items_created': self.items_created,
            'items_updated': self.items_updated,
            'items_skipped': self.items_skipped,
            'errors': self.errors,
            'error_message': self.error_message,
            'metadata': self.metadata,
            'success': self.status == JobStatus.SUCCESS
        }


class BaseJob(ABC):
    """
    Abstract base class for all pipeline jobs.
    
    Provides:
    - Consistent logging and error handling
    - Firestore connection management
    - Job execution tracking
    - Result standardization
    """
    
    def __init__(self, job_name: str, config: Dict[str, Any] = None):
        """
        Initialize the job.
        
        Args:
            job_name: Unique name for this job
            config: Job-specific configuration
        """
        self.job_name = job_name
        self.config = config or {}
        self.logger = logging.getLogger(f"pipeline.{job_name}")
        self.db = None
        self._setup_firestore()
        
    def _setup_firestore(self):
        """Initialize Firestore connection"""
        try:
            if not firebase_admin._apps:
                firebase_admin.initialize_app()
            self.db = firestore.client()
            self.logger.info("Firestore connection established")
        except Exception as e:
            self.logger.error(f"Failed to initialize Firestore: {e}")
            raise
    
    def execute(self, **kwargs) -> JobResult:
        """
        Execute the job with error handling and monitoring.
        
        Args:
            **kwargs: Job-specific arguments
            
        Returns:
            JobResult with execution details
        """
        start_time = datetime.now(timezone.utc)
        result = JobResult(
            job_name=self.job_name,
            status=JobStatus.RUNNING,
            start_time=start_time
        )
        
        self.logger.info(f"Starting job: {self.job_name}")
        
        try:
            # Pre-execution validation
            self._validate_prerequisites()
            
            # Execute the main job logic
            job_data = self._execute_job(**kwargs)
            
            # Update result with job data
            result.status = JobStatus.SUCCESS
            result.items_processed = job_data.get('items_processed', 0)
            result.items_created = job_data.get('items_created', 0)
            result.items_updated = job_data.get('items_updated', 0)
            result.items_skipped = job_data.get('items_skipped', 0)
            result.errors = job_data.get('errors', 0)
            result.metadata = job_data.get('metadata', {})
            
            self.logger.info(f"Job completed successfully: {self.job_name}")
            
        except Exception as e:
            result.status = JobStatus.FAILED
            result.error_message = str(e)
            self.logger.error(f"Job failed: {self.job_name} - {e}", exc_info=True)
            
        finally:
            result.end_time = datetime.now(timezone.utc)
            result.duration_seconds = (result.end_time - result.start_time).total_seconds()
            
            # Log execution summary
            self._log_execution_summary(result)
            
            # Record job execution in Firestore
            self._record_job_execution(result)
        
        return result
    
    @abstractmethod
    def _execute_job(self, **kwargs) -> Dict[str, Any]:
        """
        Main job execution logic - must be implemented by subclasses.
        
        Returns:
            Dict containing:
            - items_processed: Number of items processed
            - items_created: Number of new items created
            - items_updated: Number of items updated
            - items_skipped: Number of items skipped
            - errors: Number of errors encountered
            - metadata: Additional job-specific data
        """
        pass
    
    def _validate_prerequisites(self):
        """
        Validate job prerequisites before execution.
        Override in subclasses for job-specific validation.
        """
        if not self.db:
            raise RuntimeError("Firestore connection not available")
    
    def _log_execution_summary(self, result: JobResult):
        """Log a summary of job execution"""
        self.logger.info(f"Job Summary - {self.job_name}:")
        self.logger.info(f"  Status: {result.status.value}")
        self.logger.info(f"  Duration: {result.duration_seconds:.2f}s")
        self.logger.info(f"  Processed: {result.items_processed}")
        self.logger.info(f"  Created: {result.items_created}")
        self.logger.info(f"  Updated: {result.items_updated}")
        self.logger.info(f"  Skipped: {result.items_skipped}")
        self.logger.info(f"  Errors: {result.errors}")
        
        if result.error_message:
            self.logger.error(f"  Error: {result.error_message}")
    
    def _record_job_execution(self, result: JobResult):
        """Record job execution in Firestore for monitoring"""
        try:
            execution_record = {
                'job_name': result.job_name,
                'status': result.status.value,
                'start_time': result.start_time,
                'end_time': result.end_time,
                'duration_seconds': result.duration_seconds,
                'items_processed': result.items_processed,
                'items_created': result.items_created,
                'items_updated': result.items_updated,
                'items_skipped': result.items_skipped,
                'errors': result.errors,
                'error_message': result.error_message,
                'metadata': result.metadata
            }
            
            # Store in job_executions collection
            self.db.collection('job_executions').add(execution_record)
            
        except Exception as e:
            self.logger.warning(f"Failed to record job execution: {e}")
    
    def should_trigger_downstream(self, result: JobResult) -> bool:
        """
        Determine if downstream jobs should be triggered based on result.
        Override in subclasses for job-specific logic.
        
        Args:
            result: Job execution result
            
        Returns:
            True if downstream jobs should be triggered
        """
        return (result.status == JobStatus.SUCCESS and 
                (result.items_created > 0 or result.items_updated > 0))
    
    def get_trigger_metadata(self, result: JobResult) -> Dict[str, Any]:
        """
        Get metadata to pass to triggered downstream jobs.
        Override in subclasses for job-specific metadata.
        
        Args:
            result: Job execution result
            
        Returns:
            Metadata dictionary for downstream jobs
        """
        return {
            'triggered_by': self.job_name,
            'trigger_time': datetime.now(timezone.utc).isoformat(),
            'items_created': result.items_created,
            'items_updated': result.items_updated
        } 