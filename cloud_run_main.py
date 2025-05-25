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

@app.route('/oic-ingestion', methods=['POST'])
def oic_ingestion():
    """Handle Order in Council (OIC) ingestion requests from Cloud Scheduler"""
    try:
        # Parse request data
        data = request.get_json() or {}
        start_attach_id = data.get('start_attach_id')  # Optional override
        dry_run = data.get('dry_run', False)
        max_consecutive_misses = data.get('max_consecutive_misses', 50)
        
        logger.info(f"Starting OIC ingestion: start_attach_id={start_attach_id}, dry_run={dry_run}, max_misses={max_consecutive_misses}")
        
        # Run OIC ingestion script
        cmd = [
            sys.executable,
            'scripts/ingestion_jobs/ingest_raw_oic.py'
        ]
        
        if start_attach_id:
            cmd.extend(['--start_attach_id', str(start_attach_id)])
        if dry_run:
            cmd.append('--dry_run')
        if max_consecutive_misses:
            cmd.extend(['--max_consecutive_misses', str(max_consecutive_misses)])
        
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=1800)  # 30 minutes
        
        if result.returncode == 0:
            logger.info("OIC ingestion completed successfully")
            return jsonify({
                'status': 'success',
                'message': 'OIC ingestion completed successfully',
                'stdout': result.stdout[-500:] if result.stdout else ''  # Last 500 chars
            })
        else:
            logger.error(f"OIC ingestion failed: {result.stderr}")
            return jsonify({
                'status': 'error',
                'error': result.stderr[-500:] if result.stderr else '',
                'message': 'OIC ingestion failed'
            }), 500
            
    except subprocess.TimeoutExpired:
        logger.error("OIC ingestion timed out")
        return jsonify({
            'status': 'error',
            'error': 'Process timed out after 30 minutes',
            'message': 'OIC ingestion timed out'
        }), 500
    except Exception as e:
        logger.error(f"Error in OIC ingestion: {e}", exc_info=True)
        return jsonify({
            'status': 'error',
            'error': str(e),
            'message': 'Internal server error during OIC ingestion'
        }), 500

@app.route('/gazette-p2-ingestion', methods=['POST'])
def gazette_p2_ingestion():
    """Handle Canada Gazette Part II ingestion requests from Cloud Scheduler"""
    try:
        # Parse request data
        data = request.get_json() or {}
        start_date = data.get('start_date')  # YYYY-MM-DD format
        end_date = data.get('end_date')
        dry_run = data.get('dry_run', False)
        
        logger.info(f"Starting Gazette P2 ingestion: start_date={start_date}, end_date={end_date}, dry_run={dry_run}")
        
        # Run Gazette P2 ingestion script
        cmd = [
            sys.executable,
            'scripts/ingestion_jobs/ingest_canada_gazette_p2.py'
        ]
        
        if start_date:
            cmd.extend(['--start_date', start_date])
        if end_date:
            cmd.extend(['--end_date', end_date])
        if dry_run:
            cmd.append('--dry_run')
        
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=1800)  # 30 minutes
        
        if result.returncode == 0:
            logger.info("Gazette P2 ingestion completed successfully")
            return jsonify({
                'status': 'success',
                'message': 'Gazette P2 ingestion completed successfully',
                'stdout': result.stdout[-500:] if result.stdout else ''  # Last 500 chars
            })
        else:
            logger.error(f"Gazette P2 ingestion failed: {result.stderr}")
            return jsonify({
                'status': 'error',
                'error': result.stderr[-500:] if result.stderr else '',
                'message': 'Gazette P2 ingestion failed'
            }), 500
            
    except subprocess.TimeoutExpired:
        logger.error("Gazette P2 ingestion timed out")
        return jsonify({
            'status': 'error',
            'error': 'Process timed out after 30 minutes',
            'message': 'Gazette P2 ingestion timed out'
        }), 500
    except Exception as e:
        logger.error(f"Error in Gazette P2 ingestion: {e}", exc_info=True)
        return jsonify({
            'status': 'error',
            'error': str(e),
            'message': 'Internal server error during Gazette P2 ingestion'
        }), 500

@app.route('/gazette-p2-processing', methods=['POST'])
def gazette_p2_processing():
    """Handle Gazette P2 evidence processing requests from Cloud Scheduler"""
    try:
        # Parse request data
        data = request.get_json() or {}
        start_date = data.get('start_date')  # YYYY-MM-DD format
        end_date = data.get('end_date')
        dry_run = data.get('dry_run', False)
        force_reprocessing = data.get('force_reprocessing', False)
        
        logger.info(f"Starting Gazette P2 processing: start_date={start_date}, end_date={end_date}, dry_run={dry_run}, force_reprocessing={force_reprocessing}")
        
        # Run Gazette P2 processing script
        cmd = [
            sys.executable,
            'scripts/processing_jobs/process_raw_gazette2_to_evidence.py'
        ]
        
        if start_date:
            cmd.extend(['--start_date', start_date])
        if end_date:
            cmd.extend(['--end_date', end_date])
        if dry_run:
            cmd.append('--dry_run')
        if force_reprocessing:
            cmd.append('--force_reprocessing')
        
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=3600)  # 60 minutes for LLM processing
        
        if result.returncode == 0:
            logger.info("Gazette P2 processing completed successfully")
            return jsonify({
                'status': 'success',
                'message': 'Gazette P2 processing completed successfully',
                'stdout': result.stdout[-500:] if result.stdout else ''  # Last 500 chars
            })
        else:
            logger.error(f"Gazette P2 processing failed: {result.stderr}")
            return jsonify({
                'status': 'error',
                'error': result.stderr[-500:] if result.stderr else '',
                'message': 'Gazette P2 processing failed'
            }), 500
            
    except subprocess.TimeoutExpired:
        logger.error("Gazette P2 processing timed out")
        return jsonify({
            'status': 'error',
            'error': 'Process timed out after 60 minutes',
            'message': 'Gazette P2 processing timed out'
        }), 500
    except Exception as e:
        logger.error(f"Error in Gazette P2 processing: {e}", exc_info=True)
        return jsonify({
            'status': 'error',
            'error': str(e),
            'message': 'Internal server error during Gazette P2 processing'
        }), 500

@app.route('/gazette-p2-pipeline', methods=['POST'])
def gazette_p2_pipeline():
    """Handle complete Gazette P2 pipeline: ingestion followed by processing"""
    try:
        # Parse request data
        data = request.get_json() or {}
        start_date = data.get('start_date')
        end_date = data.get('end_date')
        dry_run = data.get('dry_run', False)
        force_reprocessing = data.get('force_reprocessing', False)
        
        logger.info(f"Starting Gazette P2 pipeline: start_date={start_date}, end_date={end_date}, dry_run={dry_run}")
        
        pipeline_results = []
        
        # Step 1: Run ingestion
        logger.info("Pipeline Step 1: Running Gazette P2 ingestion...")
        ingestion_data = {
            'start_date': start_date,
            'end_date': end_date,
            'dry_run': dry_run
        }
        
        with app.test_request_context('/gazette-p2-ingestion', method='POST', json=ingestion_data):
            ingestion_response = gazette_p2_ingestion()
            ingestion_result = ingestion_response.get_json()
            pipeline_results.append({
                'step': 'ingestion',
                'status': ingestion_result.get('status'),
                'message': ingestion_result.get('message')
            })
        
        # Only proceed to processing if ingestion was successful
        if ingestion_result.get('status') == 'success':
            logger.info("Pipeline Step 2: Running Gazette P2 processing...")
            processing_data = {
                'start_date': start_date,
                'end_date': end_date,
                'dry_run': dry_run,
                'force_reprocessing': force_reprocessing
            }
            
            with app.test_request_context('/gazette-p2-processing', method='POST', json=processing_data):
                processing_response = gazette_p2_processing()
                processing_result = processing_response.get_json()
                pipeline_results.append({
                    'step': 'processing',
                    'status': processing_result.get('status'),
                    'message': processing_result.get('message')
                })
        else:
            logger.error("Pipeline stopped: Ingestion failed")
            pipeline_results.append({
                'step': 'processing',
                'status': 'skipped',
                'message': 'Skipped due to ingestion failure'
            })
        
        # Determine overall pipeline status
        overall_status = 'success' if all(r['status'] == 'success' for r in pipeline_results if r['status'] != 'skipped') else 'error'
        
        return jsonify({
            'status': overall_status,
            'message': f'Gazette P2 pipeline completed with status: {overall_status}',
            'pipeline_results': pipeline_results
        })
        
    except Exception as e:
        logger.error(f"Error in Gazette P2 pipeline: {e}", exc_info=True)
        return jsonify({
            'status': 'error',
            'error': str(e),
            'message': 'Internal server error during Gazette P2 pipeline'
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
        elif action == 'oic_ingestion':
            return oic_ingestion()
        elif action == 'gazette_p2_ingestion':
            return gazette_p2_ingestion()
        elif action == 'gazette_p2_processing':
            return gazette_p2_processing()
        elif action == 'gazette_p2_pipeline':
            return gazette_p2_pipeline()
        else:
            return jsonify({
                'status': 'error',
                'message': f'Unknown action: {action}. Available: rss_check, full_ingestion, canada_news_ingestion, oic_ingestion, gazette_p2_ingestion, gazette_p2_processing, gazette_p2_pipeline'
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