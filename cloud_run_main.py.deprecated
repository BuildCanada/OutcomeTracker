#!/usr/bin/env python3
"""
Cloud Run main entry point for Promise Tracker ingestion jobs.
This script acts as a unified entry point for all RSS monitoring and data ingestion jobs.
"""

import os
import sys
import logging
import subprocess
from datetime import datetime, timedelta
from flask import Flask, request, jsonify
from typing import Dict, Any, Optional
import json

# Add scripts directories to path
ingestion_dir = os.path.join(os.path.dirname(__file__), 'scripts', 'ingestion_jobs')
utilities_dir = os.path.join(os.path.dirname(__file__), 'scripts', 'utilities')
sys.path.insert(0, ingestion_dir)
sys.path.insert(0, utilities_dir)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(name)s - %(message)s'
)
logger = logging.getLogger(__name__)

app = Flask(__name__)

# Job configurations - Clean 4-job structure
AVAILABLE_JOBS = {
    'check_legisinfo_rss': {
        'script': 'check_legisinfo_rss_updates.py',
        'script_dir': 'utilities',
        'description': 'Check LEGISinfo RSS for bill updates',
        'default_args': ['--hours_threshold', '24']
    },
    'ingest_canada_news': {
        'script': 'ingest_canada_news.py',
        'script_dir': 'ingestion_jobs',
        'description': 'Ingest Canada News RSS feed',
        'default_args': []
    },
    'ingest_legisinfo_bills': {
        'script': 'ingest_legisinfo_bills.py',
        'script_dir': 'ingestion_jobs',
        'description': 'Ingest LEGISinfo bills',
        'default_args': []
    },
    'ingest_oic': {
        'script': 'ingest_oic.py',
        'script_dir': 'ingestion_jobs',
        'description': 'Ingest Orders in Council',
        'default_args': []
    },
    'ingest_canada_gazette_p2': {
        'script': 'ingest_canada_gazette_p2.py',
        'script_dir': 'ingestion_jobs',
        'description': 'Ingest Canada Gazette Part 2',
        'default_args': []
    }
}

def run_job(job_name: str, args: list = None) -> Dict[str, Any]:
    """Execute a specific ingestion job."""
    if job_name not in AVAILABLE_JOBS:
        raise ValueError(f"Unknown job: {job_name}")
    
    job_config = AVAILABLE_JOBS[job_name]
    
    # Determine script directory
    script_subdir = job_config.get('script_dir', 'ingestion_jobs')
    if script_subdir == 'utilities':
        script_dir = utilities_dir
    else:
        script_dir = ingestion_dir
    
    script_path = os.path.join(script_dir, job_config['script'])
    
    if not os.path.exists(script_path):
        raise FileNotFoundError(f"Script not found: {script_path}")
    
    # Build command
    cmd = ['python', script_path]
    if args:
        cmd.extend(args)
    else:
        cmd.extend(job_config['default_args'])
    
    logger.info(f"Executing job '{job_name}': {' '.join(cmd)}")
    
    start_time = datetime.now()
    
    try:
        # Execute the script
        result = subprocess.run(
            cmd,
            cwd=script_dir,
            capture_output=True,
            text=True,
            timeout=1800  # 30 minute timeout
        )
        
        end_time = datetime.now()
        duration = (end_time - start_time).total_seconds()
        
        return {
            'job_name': job_name,
            'status': 'success' if result.returncode == 0 else 'failed',
            'return_code': result.returncode,
            'duration_seconds': duration,
            'stdout': result.stdout,
            'stderr': result.stderr,
            'start_time': start_time.isoformat(),
            'end_time': end_time.isoformat()
        }
        
    except subprocess.TimeoutExpired:
        return {
            'job_name': job_name,
            'status': 'timeout',
            'duration_seconds': 1800,
            'error': 'Job exceeded 30 minute timeout',
            'start_time': start_time.isoformat(),
            'end_time': datetime.now().isoformat()
        }
    except Exception as e:
        return {
            'job_name': job_name,
            'status': 'error',
            'error': str(e),
            'start_time': start_time.isoformat(),
            'end_time': datetime.now().isoformat()
        }

@app.route('/', methods=['GET'])
def health_check():
    """Health check endpoint."""
    return jsonify({
        'status': 'healthy',
        'service': 'promise-tracker-ingestion',
        'timestamp': datetime.now().isoformat(),
        'available_jobs': list(AVAILABLE_JOBS.keys())
    })

@app.route('/jobs', methods=['GET'])
def list_jobs():
    """List all available jobs."""
    return jsonify({
        'available_jobs': {
            name: {
                'description': config['description'],
                'default_args': config['default_args']
            }
            for name, config in AVAILABLE_JOBS.items()
        }
    })

@app.route('/jobs/<job_name>', methods=['POST'])
def execute_job(job_name: str):
    """Execute a specific job."""
    try:
        # Get job arguments from request
        request_data = request.get_json() or {}
        job_args = request_data.get('args', [])
        
        # Validate job exists
        if job_name not in AVAILABLE_JOBS:
            return jsonify({
                'error': f'Unknown job: {job_name}',
                'available_jobs': list(AVAILABLE_JOBS.keys())
            }), 400
        
        # Execute job
        result = run_job(job_name, job_args)
        
        # Return result
        status_code = 200 if result['status'] == 'success' else 500
        return jsonify(result), status_code
        
    except Exception as e:
        logger.error(f"Error executing job {job_name}: {e}", exc_info=True)
        return jsonify({
            'error': str(e),
            'job_name': job_name,
            'status': 'error'
        }), 500

@app.route('/jobs/batch', methods=['POST'])
def execute_batch():
    """Execute multiple jobs in sequence."""
    try:
        request_data = request.get_json() or {}
        jobs_to_run = request_data.get('jobs', [])
        
        if not jobs_to_run:
            return jsonify({'error': 'No jobs specified'}), 400
        
        results = []
        for job_spec in jobs_to_run:
            if isinstance(job_spec, str):
                job_name = job_spec
                job_args = []
            elif isinstance(job_spec, dict):
                job_name = job_spec.get('name')
                job_args = job_spec.get('args', [])
            else:
                results.append({
                    'error': f'Invalid job specification: {job_spec}',
                    'status': 'error'
                })
                continue
            
            if job_name not in AVAILABLE_JOBS:
                results.append({
                    'job_name': job_name,
                    'error': f'Unknown job: {job_name}',
                    'status': 'error'
                })
                continue
            
            result = run_job(job_name, job_args)
            results.append(result)
        
        # Overall success if all jobs succeeded
        overall_success = all(r.get('status') == 'success' for r in results)
        status_code = 200 if overall_success else 500
        
        return jsonify({
            'batch_status': 'success' if overall_success else 'partial_failure',
            'results': results,
            'summary': {
                'total_jobs': len(results),
                'successful': sum(1 for r in results if r.get('status') == 'success'),
                'failed': sum(1 for r in results if r.get('status') != 'success')
            }
        }), status_code
        
    except Exception as e:
        logger.error(f"Error executing batch job: {e}", exc_info=True)
        return jsonify({
            'error': str(e),
            'status': 'error'
        }), 500

@app.route('/schedule/rss-monitoring', methods=['POST'])
def scheduled_rss_monitoring():
    """Endpoint for scheduled RSS monitoring (called by Cloud Scheduler)."""
    try:
        # This endpoint is no longer used - individual RSS jobs now handle their own processing
        # Keeping for backward compatibility
        return jsonify({
            'message': 'RSS monitoring now handled by individual job schedules',
            'status': 'deprecated'
        }), 200
        
    except Exception as e:
        logger.error(f"Error in scheduled RSS monitoring: {e}", exc_info=True)
        return jsonify({
            'error': str(e),
            'scheduled_job': 'rss-monitoring',
            'status': 'error'
        }), 500

@app.route('/jobs/<job_name>/with-processing', methods=['POST'])
def execute_job_with_processing(job_name: str):
    """Execute a job and trigger its processing if new items are found."""
    try:
        # Get job arguments from request
        request_data = request.get_json() or {}
        job_args = request_data.get('args', [])
        
        # Validate job exists
        if job_name not in AVAILABLE_JOBS:
            return jsonify({
                'error': f'Unknown job: {job_name}',
                'available_jobs': list(AVAILABLE_JOBS.keys())
            }), 400
        
        # Execute main job
        result = run_job(job_name, job_args)
        
        # Check if we should trigger processing
        should_process = False
        processing_job = None
        
        if job_name == 'check_legisinfo_rss':
            # Check if LegisInfo RSS found updates
            stdout = result.get('stdout', '')
            if 'Found' in stdout and 'recent update' in stdout and result.get('status') == 'success':
                should_process = True
                processing_job = 'ingest_legisinfo_bills'
                
        elif job_name == 'ingest_canada_news':
            # Check if Canada News ingestion found new items
            stdout = result.get('stdout', '')
            if ('newly ingested' in stdout or 'Items newly ingested' in stdout) and result.get('status') == 'success':
                # Extract number of new items
                import re
                match = re.search(r'(\d+).*newly ingested', stdout)
                if match and int(match.group(1)) > 0:
                    should_process = True
                    processing_job = 'process_news_to_evidence'
        
        results = [result]
        
        # Trigger processing if needed
        if should_process and processing_job:
            logger.info(f"Job {job_name} found new items, triggering {processing_job}")
            
            # Set appropriate args for processing jobs
            processing_args = ['--days_back', '1']  # Process last day for fresh data
            
            if processing_job == 'ingest_legisinfo_bills':
                # For LegisInfo, we ingest bills then process them
                ingestion_result = run_job('ingest_legisinfo_bills', ['--parliament_session', '44-1'])
                results.append(ingestion_result)
                
                if ingestion_result.get('status') == 'success':
                    processing_result = run_job('process_legisinfo_to_evidence', processing_args)
                    results.append(processing_result)
            else:
                # For Canada News, just process the ingested data
                processing_result = run_job(processing_job, processing_args)
                results.append(processing_result)
        
        # Overall status
        overall_success = all(r.get('status') == 'success' for r in results)
        status_code = 200 if overall_success else 500
        
        return jsonify({
            'job_name': job_name,
            'status': 'success' if overall_success else 'partial_failure',
            'triggered_processing': should_process,
            'processing_job': processing_job if should_process else None,
            'results': results
        }), status_code
        
    except Exception as e:
        logger.error(f"Error executing job with processing {job_name}: {e}", exc_info=True)
        return jsonify({
            'error': str(e),
            'job_name': job_name,
            'status': 'error'
        }), 500

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 8080))
    app.run(host='0.0.0.0', port=port, debug=False) 