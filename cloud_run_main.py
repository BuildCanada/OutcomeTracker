"""
Cloud Run service for RSS monitoring and bill ingestion.
Handles HTTP requests from Cloud Scheduler to perform RSS checks and bill ingestion.
"""

import os
import sys
import json
import logging
import subprocess
from flask import Flask, request, jsonify
from datetime import datetime
import tempfile

# Add scripts to path
sys.path.append(os.path.join(os.path.dirname(__file__), 'scripts'))

# Configure logging
logging.basicConfig(level=logging.INFO,
                    format='%(asctime)s - %(levelname)s - %(filename)s:%(lineno)d - %(message)s')
logger = logging.getLogger(__name__)

app = Flask(__name__)

@app.route('/', methods=['GET'])
def health_check():
    """Health check endpoint for Cloud Run"""
    return jsonify({
        'status': 'healthy',
        'service': 'rss-monitor',
        'timestamp': datetime.now().isoformat()
    })

@app.route('/rss-check', methods=['POST'])
def rss_check():
    """Handle RSS check requests from Cloud Scheduler"""
    try:
        # Parse request data
        data = request.get_json() or {}
        hours_threshold = data.get('hours_threshold', 1)
        parliament_filter = data.get('parliament_filter', 44)
        
        logger.info(f"Starting RSS check: threshold={hours_threshold}h, parliament={parliament_filter}")
        
        # Run RSS check script
        cmd = [
            sys.executable,
            'scripts/ingestion_jobs/check_legisinfo_rss_updates.py',
            '--hours_threshold', str(hours_threshold),
            '--parliament_filter', str(parliament_filter),
            '--output_format', 'json'
        ]
        
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
        
        if result.returncode == 0:
            # Parse the output to count bills
            try:
                bills_data = json.loads(result.stdout)
                bills_count = len(bills_data) if isinstance(bills_data, list) else 0
            except:
                bills_count = 0
            
            logger.info(f"RSS check completed successfully: {bills_count} bills found")
            return jsonify({
                'status': 'success',
                'bills_found': bills_count,
                'message': f'RSS check completed, found {bills_count} recent bills'
            })
        else:
            logger.error(f"RSS check failed: {result.stderr}")
            return jsonify({
                'status': 'error',
                'error': result.stderr,
                'message': 'RSS check failed'
            }), 500
            
    except Exception as e:
        logger.error(f"Error in RSS check: {e}", exc_info=True)
        return jsonify({
            'status': 'error',
            'error': str(e),
            'message': 'Internal server error during RSS check'
        }), 500

@app.route('/full-ingestion', methods=['POST'])
def full_ingestion():
    """Handle full ingestion requests from Cloud Scheduler"""
    try:
        # Parse request data
        data = request.get_json() or {}
        hours_threshold = data.get('hours_threshold', 24)
        parliament_filter = data.get('parliament_filter', 44)
        fallback_full_run = data.get('fallback_full_run', True)
        
        logger.info(f"Starting full ingestion: threshold={hours_threshold}h, parliament={parliament_filter}, fallback={fallback_full_run}")
        
        # Run RSS-driven ingestion
        cmd = [
            sys.executable,
            'scripts/ingestion_jobs/rss_driven_bill_ingestion.py',
            '--hours_threshold', str(hours_threshold),
            '--parliament_filter', str(parliament_filter)
        ]
        
        if fallback_full_run:
            cmd.append('--fallback_full_run')
        
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=1800)  # 30 minutes
        
        if result.returncode == 0:
            logger.info("Full ingestion completed successfully")
            return jsonify({
                'status': 'success',
                'message': 'Full ingestion completed successfully',
                'stdout': result.stdout[-500:] if result.stdout else ''  # Last 500 chars
            })
        else:
            logger.error(f"Full ingestion failed: {result.stderr}")
            return jsonify({
                'status': 'error',
                'error': result.stderr[-500:] if result.stderr else '',
                'message': 'Full ingestion failed'
            }), 500
            
    except subprocess.TimeoutExpired:
        logger.error("Full ingestion timed out")
        return jsonify({
            'status': 'error',
            'error': 'Process timed out after 30 minutes',
            'message': 'Full ingestion timed out'
        }), 500
    except Exception as e:
        logger.error(f"Error in full ingestion: {e}", exc_info=True)
        return jsonify({
            'status': 'error',
            'error': str(e),
            'message': 'Internal server error during full ingestion'
        }), 500

@app.route('/canada-news-ingestion', methods=['POST'])
def canada_news_ingestion():
    """Handle Canada news RSS ingestion requests from Cloud Scheduler"""
    try:
        # Parse request data
        data = request.get_json() or {}
        start_date = data.get('start_date')  # YYYY-MM-DD format
        end_date = data.get('end_date')
        dry_run = data.get('dry_run', False)
        
        logger.info(f"Starting Canada news ingestion: start_date={start_date}, end_date={end_date}, dry_run={dry_run}")
        
        # Run Canada news RSS ingestion
        cmd = [
            sys.executable,
            'scripts/ingestion_jobs/ingest_canada_news_rss.py'
        ]
        
        if start_date:
            cmd.extend(['--start_date', start_date])
        if end_date:
            cmd.extend(['--end_date', end_date])
        if dry_run:
            cmd.append('--dry_run')
        
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=1800)  # 30 minutes
        
        if result.returncode == 0:
            logger.info("Canada news ingestion completed successfully")
            return jsonify({
                'status': 'success',
                'message': 'Canada news ingestion completed successfully',
                'stdout': result.stdout[-500:] if result.stdout else ''  # Last 500 chars
            })
        else:
            logger.error(f"Canada news ingestion failed: {result.stderr}")
            return jsonify({
                'status': 'error',
                'error': result.stderr[-500:] if result.stderr else '',
                'message': 'Canada news ingestion failed'
            }), 500
            
    except subprocess.TimeoutExpired:
        logger.error("Canada news ingestion timed out")
        return jsonify({
            'status': 'error',
            'error': 'Process timed out after 30 minutes',
            'message': 'Canada news ingestion timed out'
        }), 500
    except Exception as e:
        logger.error(f"Error in Canada news ingestion: {e}", exc_info=True)
        return jsonify({
            'status': 'error',
            'error': str(e),
            'message': 'Internal server error during Canada news ingestion'
        }), 500

@app.route('/manual-trigger', methods=['POST'])
def manual_trigger():
    """Handle manual trigger requests"""
    try:
        data = request.get_json() or {}
        action = data.get('action', 'rss_check')
        
        if action == 'rss_check':
            return rss_check()
        elif action == 'full_ingestion':
            return full_ingestion()
        elif action == 'canada_news_ingestion':
            return canada_news_ingestion()
        else:
            return jsonify({
                'status': 'error',
                'message': f'Unknown action: {action}. Available: rss_check, full_ingestion, canada_news_ingestion'
            }), 400
            
    except Exception as e:
        logger.error(f"Error in manual trigger: {e}", exc_info=True)
        return jsonify({
            'status': 'error',
            'error': str(e),
            'message': 'Internal server error during manual trigger'
        }), 500

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 8080))
    app.run(host='0.0.0.0', port=port, debug=False) 