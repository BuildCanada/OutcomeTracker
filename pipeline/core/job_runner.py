"""
Job Runner for Promise Tracker Pipeline

Handles job execution with timeout, retry logic, and error handling.
"""

import logging
import signal
import time
from typing import Dict, Any, Optional
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FutureTimeoutError

from .base_job import BaseJob, JobResult, JobStatus


class TimeoutException(Exception):
    """Exception raised when job execution times out"""
    pass


class JobRunner:
    """
    Handles execution of pipeline jobs with robust error handling,
    timeout management, and retry logic.
    """
    
    def __init__(self):
        """Initialize the job runner"""
        self.logger = logging.getLogger("pipeline.job_runner")
    
    def run_job(self, job: BaseJob, timeout_minutes: int = None, 
                retry_attempts: int = None, **kwargs) -> JobResult:
        """
        Run a job with timeout and retry logic.
        
        Args:
            job: Job instance to execute
            timeout_minutes: Timeout in minutes (overrides job config)
            retry_attempts: Number of retry attempts (overrides job config)
            **kwargs: Arguments to pass to job execution
            
        Returns:
            JobResult with execution details
        """
        # Get timeout and retry settings
        timeout_minutes = timeout_minutes or job.config.get('timeout_minutes', 30)
        retry_attempts = retry_attempts or job.config.get('retry_attempts', 2)
        timeout_seconds = timeout_minutes * 60
        
        self.logger.info(f"Running job {job.job_name} with {timeout_minutes}m timeout, {retry_attempts} retries")
        
        last_result = None
        
        for attempt in range(retry_attempts + 1):  # +1 for initial attempt
            if attempt > 0:
                self.logger.info(f"Retry attempt {attempt}/{retry_attempts} for job {job.job_name}")
                # Add exponential backoff
                backoff_seconds = min(60, 2 ** attempt)
                time.sleep(backoff_seconds)
            
            try:
                # Execute job with timeout
                result = self._execute_with_timeout(job, timeout_seconds, **kwargs)
                
                # If successful, return immediately
                if result.status == JobStatus.SUCCESS:
                    if attempt > 0:
                        self.logger.info(f"Job {job.job_name} succeeded on retry attempt {attempt}")
                    return result
                
                # If failed but not due to timeout, check if we should retry
                last_result = result
                if not self._should_retry(result):
                    self.logger.info(f"Job {job.job_name} failed with non-retryable error: {result.error_message}")
                    break
                    
            except TimeoutException:
                last_result = JobResult(
                    job_name=job.job_name,
                    status=JobStatus.TIMEOUT,
                    start_time=result.start_time if 'result' in locals() else None,
                    error_message=f"Job timed out after {timeout_minutes} minutes"
                )
                self.logger.warning(f"Job {job.job_name} timed out on attempt {attempt + 1}")
                
            except Exception as e:
                last_result = JobResult(
                    job_name=job.job_name,
                    status=JobStatus.FAILED,
                    start_time=result.start_time if 'result' in locals() else None,
                    error_message=f"Unexpected error: {str(e)}"
                )
                self.logger.error(f"Unexpected error in job {job.job_name}: {e}", exc_info=True)
        
        # All attempts failed
        self.logger.error(f"Job {job.job_name} failed after {retry_attempts + 1} attempts")
        return last_result
    
    def _execute_with_timeout(self, job: BaseJob, timeout_seconds: int, **kwargs) -> JobResult:
        """
        Execute job with timeout using ThreadPoolExecutor.
        
        Args:
            job: Job to execute
            timeout_seconds: Timeout in seconds
            **kwargs: Job arguments
            
        Returns:
            JobResult
            
        Raises:
            TimeoutException: If job times out
        """
        with ThreadPoolExecutor(max_workers=1) as executor:
            future = executor.submit(job.execute, **kwargs)
            
            try:
                result = future.result(timeout=timeout_seconds)
                return result
                
            except FutureTimeoutError:
                # Cancel the future (though it may not stop the actual execution)
                future.cancel()
                raise TimeoutException(f"Job timed out after {timeout_seconds} seconds")
    
    def _should_retry(self, result: JobResult) -> bool:
        """
        Determine if a job should be retried based on the result.
        
        Args:
            result: Job execution result
            
        Returns:
            True if job should be retried
        """
        # Don't retry successful jobs
        if result.status == JobStatus.SUCCESS:
            return False
        
        # Don't retry cancelled jobs
        if result.status == JobStatus.CANCELLED:
            return False
        
        # Retry timeouts and most failures
        if result.status in [JobStatus.TIMEOUT, JobStatus.FAILED]:
            # Check for specific non-retryable errors
            if result.error_message:
                non_retryable_errors = [
                    'authentication failed',
                    'invalid configuration',
                    'permission denied',
                    'not found',
                    'already exists'
                ]
                
                error_lower = result.error_message.lower()
                for non_retryable in non_retryable_errors:
                    if non_retryable in error_lower:
                        return False
            
            return True
        
        return False
    
    def run_batch(self, jobs: list[BaseJob], max_concurrent: int = 3) -> list[JobResult]:
        """
        Run multiple jobs concurrently.
        
        Args:
            jobs: List of jobs to execute
            max_concurrent: Maximum number of concurrent jobs
            
        Returns:
            List of JobResult objects
        """
        results = []
        
        with ThreadPoolExecutor(max_workers=max_concurrent) as executor:
            # Submit all jobs
            future_to_job = {
                executor.submit(self.run_job, job): job 
                for job in jobs
            }
            
            # Collect results as they complete
            for future in future_to_job:
                job = future_to_job[future]
                try:
                    result = future.result()
                    results.append(result)
                except Exception as e:
                    # Create error result for jobs that failed to submit
                    error_result = JobResult(
                        job_name=job.job_name,
                        status=JobStatus.FAILED,
                        start_time=None,
                        error_message=f"Failed to execute job: {str(e)}"
                    )
                    results.append(error_result)
                    self.logger.error(f"Failed to execute job {job.job_name}: {e}")
        
        return results 