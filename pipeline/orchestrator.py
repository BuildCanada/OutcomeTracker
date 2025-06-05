"""
Pipeline Orchestrator for Promise Tracker

This module provides the main orchestration logic for the Promise Tracker pipeline,
replacing the previous subprocess-based approach with a more robust, class-based system.
"""

import os
import sys
import logging
import yaml
import importlib
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional
from flask import Flask, request, jsonify
from concurrent.futures import ThreadPoolExecutor, as_completed
import threading

# Firebase imports
try:
    import firebase_admin
    from firebase_admin import credentials, firestore
    FIREBASE_AVAILABLE = True
except ImportError:
    FIREBASE_AVAILABLE = False

from .core.base_job import BaseJob, JobResult, JobStatus
from .core.job_runner import JobRunner


class PipelineOrchestrator:
    """
    Main orchestrator for the Promise Tracker pipeline.
    
    Handles:
    - Job configuration loading
    - Job execution and monitoring
    - Dependency management
    - Trigger coordination
    - Error handling and resilience
    - Firestore logging for monitoring
    """
    
    def __init__(self, config_path: str = None):
        """
        Initialize the orchestrator.
        
        Args:
            config_path: Path to jobs configuration file
        """
        self.logger = logging.getLogger("pipeline.orchestrator")
        self.config_path = config_path or os.path.join(
            os.path.dirname(__file__), "config", "jobs.yaml"
        )
        self.job_config = self._load_job_config()
        self.job_runner = JobRunner()
        self.active_jobs = {}  # Track currently running jobs
        self.job_lock = threading.Lock()
        
        # Initialize Firestore for monitoring
        self.firestore_db = self._init_firestore()
        
    def _init_firestore(self):
        """Initialize Firestore connection for monitoring"""
        if not FIREBASE_AVAILABLE:
            self.logger.warning("Firebase not available - monitoring data will not be logged")
            return None
            
        try:
            # Check if Firebase is already initialized
            if not firebase_admin._apps:
                # Initialize Firebase Admin SDK
                cred = credentials.ApplicationDefault()
                firebase_admin.initialize_app(cred)
            
            db = firestore.client()
            self.logger.info("Firestore initialized for monitoring")
            return db
        except Exception as e:
            self.logger.warning(f"Failed to initialize Firestore: {e}")
            return None
    
    def _log_job_execution(self, job_id: str, stage: str, job_name: str, result: JobResult, triggered_by: str = None):
        """Log job execution to Firestore for monitoring"""
        if not self.firestore_db:
            return
            
        try:
            execution_data = {
                'job_name': job_name,
                'stage': stage,
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
                'triggered_by': triggered_by,
                'metadata': result.metadata or {}
            }
            
            # Add to pipeline_job_executions collection
            self.firestore_db.collection('pipeline_job_executions').add(execution_data)
            
            # Create alert if job failed
            if result.status == JobStatus.FAILED:
                self._create_pipeline_alert(job_id, result.error_message)
                
        except Exception as e:
            self.logger.error(f"Failed to log job execution to Firestore: {e}")
    
    def _create_pipeline_alert(self, job_id: str, error_message: str):
        """Create a pipeline alert in Firestore"""
        if not self.firestore_db:
            return
            
        try:
            alert_data = {
                'alert_type': 'pipeline_job_failure',
                'severity': 'critical',
                'message': f'Pipeline job {job_id} failed',
                'error_message': error_message,
                'failure_count': 1,
                'created_at': datetime.now(timezone.utc),
                'resolved': False,
                'source': 'pipeline'
            }
            
            self.firestore_db.collection('pipeline_alerts').add(alert_data)
            
        except Exception as e:
            self.logger.error(f"Failed to create pipeline alert: {e}")
    
    def _load_job_config(self) -> Dict[str, Any]:
        """Load job configuration from YAML file"""
        try:
            with open(self.config_path, 'r') as f:
                config = yaml.safe_load(f)
            self.logger.info(f"Loaded job configuration from {self.config_path}")
            return config
        except Exception as e:
            self.logger.error(f"Failed to load job configuration: {e}")
            raise
    
    def get_job_class(self, job_config: Dict[str, Any]) -> type:
        """
        Dynamically import and return job class.
        
        Args:
            job_config: Job configuration containing class path
            
        Returns:
            Job class
        """
        class_path = job_config['class']
        module_path, class_name = class_path.rsplit('.', 1)
        
        try:
            module = importlib.import_module(module_path)
            job_class = getattr(module, class_name)
            
            if not issubclass(job_class, BaseJob):
                raise ValueError(f"Job class {class_path} must inherit from BaseJob")
                
            return job_class
            
        except Exception as e:
            self.logger.error(f"Failed to import job class {class_path}: {e}")
            raise
    
    def execute_job(self, stage: str, job_name: str, **kwargs) -> JobResult:
        """
        Execute a specific job.
        
        Args:
            stage: Pipeline stage (ingestion, processing, linking)
            job_name: Name of the job to execute
            **kwargs: Job-specific arguments
            
        Returns:
            JobResult with execution details
        """
        job_id = f"{stage}.{job_name}"
        
        # Check if job is already running
        with self.job_lock:
            if job_id in self.active_jobs:
                self.logger.warning(f"Job {job_id} is already running")
                return JobResult(
                    job_name=job_id,
                    status=JobStatus.FAILED,
                    start_time=datetime.now(timezone.utc),
                    error_message="Job already running"
                )
        
        try:
            # Get job configuration
            job_config = self.job_config['stages'][stage]['jobs'][job_name]
            
            # Create job instance
            job_class = self.get_job_class(job_config)
            job_instance = job_class(job_name=job_id, config=job_config)
            
            # Mark job as active
            with self.job_lock:
                self.active_jobs[job_id] = job_instance
            
            # Execute job
            self.logger.info(f"Executing job: {job_id}")
            result = self.job_runner.run_job(job_instance, **kwargs)
            
            # Handle downstream triggers
            if job_instance.should_trigger_downstream(result):
                self._trigger_downstream_jobs(stage, job_name, job_config, result)
            
            # Log job execution to Firestore
            self._log_job_execution(job_id, stage, job_name, result)
            
            return result
            
        except KeyError:
            error_msg = f"Job {job_id} not found in configuration"
            self.logger.error(error_msg)
            result = JobResult(
                job_name=job_id,
                status=JobStatus.FAILED,
                start_time=datetime.now(timezone.utc),
                error_message=error_msg
            )
            # Log failed job execution to Firestore
            self._log_job_execution(job_id, stage, job_name, result)
            return result
        except Exception as e:
            error_msg = f"Failed to execute job {job_id}: {e}"
            self.logger.error(error_msg, exc_info=True)
            result = JobResult(
                job_name=job_id,
                status=JobStatus.FAILED,
                start_time=datetime.now(timezone.utc),
                error_message=error_msg
            )
            # Log failed job execution to Firestore
            self._log_job_execution(job_id, stage, job_name, result)
            return result
        finally:
            # Remove job from active jobs
            with self.job_lock:
                self.active_jobs.pop(job_id, None)
    
    def _trigger_downstream_jobs(self, stage: str, job_name: str, 
                                job_config: Dict[str, Any], result: JobResult):
        """
        Trigger downstream jobs based on job configuration.
        
        Args:
            stage: Current stage
            job_name: Current job name
            job_config: Current job configuration
            result: Job execution result
        """
        triggers = job_config.get('triggers', [])
        
        for trigger in triggers:
            trigger_stage = trigger['stage']
            trigger_job = trigger['job']
            condition = trigger.get('condition', 'always')
            
            # Check trigger condition
            should_trigger = False
            if condition == 'always':
                should_trigger = True
            elif condition == 'new_items_found' and result.items_created > 0:
                should_trigger = True
            elif condition == 'new_evidence_created' and result.items_created > 0:
                should_trigger = True
            elif condition == 'new_links_created' and result.items_created > 0:
                should_trigger = True
            
            if should_trigger:
                self.logger.info(f"Triggering downstream job: {trigger_stage}.{trigger_job}")
                
                # Execute downstream job asynchronously
                threading.Thread(
                    target=self._execute_triggered_job,
                    args=(trigger_stage, trigger_job, result),
                    daemon=True
                ).start()
    
    def _execute_triggered_job(self, stage: str, job_name: str, trigger_result: JobResult):
        """Execute a triggered downstream job"""
        try:
            # Add trigger metadata to job execution
            trigger_metadata = {
                'triggered_by': trigger_result.job_name,
                'trigger_time': datetime.now(timezone.utc).isoformat(),
                'trigger_items_created': trigger_result.items_created
            }
            
            result = self.execute_job(stage, job_name, trigger_metadata=trigger_metadata)
            self.logger.info(f"Triggered job completed: {stage}.{job_name} - {result.status.value}")
            
            # Log job execution to Firestore
            self._log_job_execution(f"{stage}.{job_name}", stage, job_name, result, triggered_by=trigger_result.job_name)
            
        except Exception as e:
            self.logger.error(f"Failed to execute triggered job {stage}.{job_name}: {e}")
    
    def execute_batch(self, jobs: List[Dict[str, Any]]) -> List[JobResult]:
        """
        Execute multiple jobs in batch.
        
        Args:
            jobs: List of job specifications with 'stage' and 'job' keys
            
        Returns:
            List of JobResult objects
        """
        results = []
        max_workers = self.job_config.get('global', {}).get('max_concurrent_jobs', 3)
        
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            # Submit all jobs
            future_to_job = {}
            for job_spec in jobs:
                stage = job_spec['stage']
                job_name = job_spec['job']
                job_args = job_spec.get('args', {})
                
                future = executor.submit(self.execute_job, stage, job_name, **job_args)
                future_to_job[future] = f"{stage}.{job_name}"
            
            # Collect results
            for future in as_completed(future_to_job):
                job_id = future_to_job[future]
                try:
                    result = future.result()
                    results.append(result)
                    self.logger.info(f"Batch job completed: {job_id} - {result.status.value}")
                except Exception as e:
                    self.logger.error(f"Batch job failed: {job_id} - {e}")
                    results.append(JobResult(
                        job_name=job_id,
                        status=JobStatus.FAILED,
                        start_time=datetime.now(timezone.utc),
                        error_message=str(e)
                    ))
        
        return results
    
    def get_job_status(self, stage: str = None, job_name: str = None) -> Dict[str, Any]:
        """
        Get status of jobs.
        
        Args:
            stage: Optional stage filter
            job_name: Optional job name filter
            
        Returns:
            Job status information
        """
        with self.job_lock:
            active_jobs = list(self.active_jobs.keys())
        
        status = {
            'active_jobs': active_jobs,
            'total_active': len(active_jobs),
            'available_jobs': {}
        }
        
        # Add available jobs from configuration
        for stage_name, stage_config in self.job_config['stages'].items():
            if stage and stage != stage_name:
                continue
                
            status['available_jobs'][stage_name] = {}
            for job_name_config, job_config in stage_config['jobs'].items():
                if job_name and job_name != job_name_config:
                    continue
                    
                status['available_jobs'][stage_name][job_name_config] = {
                    'description': job_config.get('description', ''),
                    'timeout_minutes': job_config.get('timeout_minutes', 30),
                    'retry_attempts': job_config.get('retry_attempts', 2)
                }
        
        return status


# Flask application for Cloud Run
def create_app(orchestrator: PipelineOrchestrator = None) -> Flask:
    """Create Flask application for Cloud Run deployment"""
    
    app = Flask(__name__)
    
    if orchestrator is None:
        orchestrator = PipelineOrchestrator()
    
    @app.route('/', methods=['GET'])
    def health_check():
        """Health check endpoint"""
        return jsonify({
            'status': 'healthy',
            'service': 'promise-tracker-pipeline',
            'timestamp': datetime.now(timezone.utc).isoformat(),
            'version': '2.0.0'
        })
    
    @app.route('/jobs', methods=['GET'])
    def list_jobs():
        """List all available jobs"""
        return jsonify(orchestrator.get_job_status())
    
    @app.route('/jobs/<stage>/<job_name>', methods=['POST'])
    def execute_job_endpoint(stage: str, job_name: str):
        """Execute a specific job"""
        try:
            request_data = request.get_json() or {}
            result = orchestrator.execute_job(stage, job_name, **request_data)
            
            return jsonify({
                'job_name': result.job_name,
                'status': result.status.value,
                'duration_seconds': result.duration_seconds,
                'items_processed': result.items_processed,
                'items_created': result.items_created,
                'items_updated': result.items_updated,
                'items_skipped': result.items_skipped,
                'errors': result.errors,
                'error_message': result.error_message,
                'metadata': result.metadata
            }), 200 if result.status == JobStatus.SUCCESS else 500
            
        except Exception as e:
            return jsonify({
                'error': str(e),
                'job_name': f"{stage}.{job_name}",
                'status': 'error'
            }), 500
    
    @app.route('/jobs/batch', methods=['POST'])
    def execute_batch_endpoint():
        """Execute multiple jobs in batch"""
        try:
            request_data = request.get_json() or {}
            jobs = request_data.get('jobs', [])
            
            if not jobs:
                return jsonify({'error': 'No jobs specified'}), 400
            
            results = orchestrator.execute_batch(jobs)
            
            # Convert results to JSON-serializable format
            results_json = []
            for result in results:
                results_json.append({
                    'job_name': result.job_name,
                    'status': result.status.value,
                    'duration_seconds': result.duration_seconds,
                    'items_processed': result.items_processed,
                    'items_created': result.items_created,
                    'items_updated': result.items_updated,
                    'items_skipped': result.items_skipped,
                    'errors': result.errors,
                    'error_message': result.error_message
                })
            
            # Overall success if all jobs succeeded
            overall_success = all(r.status == JobStatus.SUCCESS for r in results)
            
            return jsonify({
                'batch_status': 'success' if overall_success else 'partial_failure',
                'results': results_json,
                'summary': {
                    'total_jobs': len(results),
                    'successful': sum(1 for r in results if r.status == JobStatus.SUCCESS),
                    'failed': sum(1 for r in results if r.status != JobStatus.SUCCESS)
                }
            }), 200 if overall_success else 500
            
        except Exception as e:
            return jsonify({
                'error': str(e),
                'status': 'error'
            }), 500
    
    return app


def main():
    """Main entry point for development mode."""
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(name)s - %(message)s'
    )
    
    orchestrator = PipelineOrchestrator()
    app = create_app(orchestrator)
    
    port = int(os.environ.get('PORT', 8080))
    app.run(host='0.0.0.0', port=port, debug=False)


if __name__ == '__main__':
    main() 