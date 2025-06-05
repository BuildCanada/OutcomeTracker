"""
RSS feed monitoring and logging utilities for tracking feed health and performance.
Integrates with existing Firestore setup to provide comprehensive monitoring data.
"""

import os
import logging
import json
from datetime import datetime, timezone
from typing import Dict, List, Optional, Any
from dotenv import load_dotenv
import firebase_admin
from firebase_admin import credentials, firestore

# --- Configuration ---
load_dotenv()

# --- Logger Setup ---
logging.basicConfig(level=logging.INFO,
                    format='%(asctime)s - %(levelname)s - %(filename)s:%(lineno)d - %(message)s',
                    datefmt='%Y-%m-%d %H:%M:%S')
logger = logging.getLogger("rss_monitoring_logger")
# --- End Logger Setup ---

# --- Constants ---
RSS_MONITORING_COLLECTION = "rss_feed_monitoring"
RSS_METRICS_COLLECTION = "rss_feed_metrics"
RSS_ALERTS_COLLECTION = "rss_feed_alerts"
# --- End Constants ---

# --- Firebase Configuration ---
db = None
if not firebase_admin._apps:
    try:
        firebase_admin.initialize_app()
        db = firestore.client()
        project_id = os.getenv('FIREBASE_PROJECT_ID', 'Default')
        logger.info(f"RSS Monitoring: Connected to Firestore (Project: {project_id})")
    except Exception as e:
        logger.critical(f"Firebase init failed: {e}", exc_info=True)
        exit("Exiting: Firestore client not available.")
else:
    db = firestore.client()

if db is None:
    logger.critical("CRITICAL: Failed to obtain Firestore client.")
    exit("Exiting: Firestore client not available.")
# --- End Firebase Configuration ---

class RSSMonitoringLogger:
    """Handles logging and monitoring of RSS feed activities."""
    
    def __init__(self):
        self.db = db
        self.session_id = f"rss_session_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    
    def log_rss_check_start(self, hours_threshold: int, parliament_filter: Optional[int] = None, check_type: str = "legisinfo_bills") -> str:
        """Log the start of an RSS check operation."""
        rss_urls = {
            "legisinfo_bills": "https://www.parl.ca/legisinfo/en/bills/rss",
            "canada_news_rss": "https://api.io.canada.ca/io-server/gc/news/en/v2"
        }
        
        doc_data = {
            'session_id': self.session_id,
            'operation': 'rss_check',
            'check_type': check_type,
            'status': 'started',
            'start_time': firestore.SERVER_TIMESTAMP,
            'hours_threshold': hours_threshold,
            'parliament_filter': parliament_filter,
            'rss_url': rss_urls.get(check_type, 'unknown')
        }
        
        doc_ref = self.db.collection(RSS_MONITORING_COLLECTION).add(doc_data)
        monitor_id = doc_ref[1].id
        logger.info(f"RSS check started - Monitor ID: {monitor_id}")
        return monitor_id
    
    def log_rss_check_result(self, monitor_id: str, success: bool, bills_found: int, 
                            error_message: Optional[str] = None, response_time_ms: Optional[int] = None):
        """Log the result of an RSS check operation."""
        update_data = {
            'status': 'completed' if success else 'failed',
            'end_time': firestore.SERVER_TIMESTAMP,
            'bills_found': bills_found,
            'success': success
        }
        
        if error_message:
            update_data['error_message'] = error_message
        if response_time_ms:
            update_data['response_time_ms'] = response_time_ms
        
        self.db.collection(RSS_MONITORING_COLLECTION).document(monitor_id).update(update_data)
        
        # Update metrics
        self._update_metrics(success, bills_found, response_time_ms)
        
        # Check for alerts
        if not success:
            self._check_failure_alerts(error_message)
        
        status = "SUCCESS" if success else "FAILED"
        logger.info(f"RSS check {status} - Monitor ID: {monitor_id}, Bills: {bills_found}")
    
    def log_ingestion_start(self, ingestion_type: str, bill_count: int, triggered_by: str = "manual") -> str:
        """Log the start of a bill ingestion operation."""
        doc_data = {
            'session_id': self.session_id,
            'operation': 'bill_ingestion',
            'ingestion_type': ingestion_type,  # 'rss_driven', 'full', 'fallback'
            'status': 'started',
            'start_time': firestore.SERVER_TIMESTAMP,
            'bill_count': bill_count,
            'triggered_by': triggered_by  # 'rss', 'manual', 'scheduled'
        }
        
        doc_ref = self.db.collection(RSS_MONITORING_COLLECTION).add(doc_data)
        monitor_id = doc_ref[1].id
        logger.info(f"Ingestion started - Type: {ingestion_type}, Monitor ID: {monitor_id}")
        return monitor_id
    
    def log_ingestion_result(self, monitor_id: str, success: bool, bills_processed: int, 
                            evidence_created: int, errors: int):
        """Log the result of a bill ingestion operation."""
        update_data = {
            'status': 'completed' if success else 'failed',
            'end_time': firestore.SERVER_TIMESTAMP,
            'bills_processed': bills_processed,
            'evidence_created': evidence_created,
            'error_count': errors,
            'success': success
        }
        
        self.db.collection(RSS_MONITORING_COLLECTION).document(monitor_id).update(update_data)
        
        status = "SUCCESS" if success else "FAILED"
        logger.info(f"Ingestion {status} - Monitor ID: {monitor_id}, Processed: {bills_processed}, Evidence: {evidence_created}")
    
    def _update_metrics(self, success: bool, bills_found: int, response_time_ms: Optional[int]):
        """Update RSS feed metrics for dashboard display."""
        today = datetime.now().strftime('%Y-%m-%d')
        metric_id = f"daily_metrics_{today}"
        
        # Get or create daily metrics
        metric_ref = self.db.collection(RSS_METRICS_COLLECTION).document(metric_id)
        metric_doc = metric_ref.get()
        
        if metric_doc.exists:
            data = metric_doc.to_dict()
            data['total_checks'] = data.get('total_checks', 0) + 1
            data['successful_checks'] = data.get('successful_checks', 0) + (1 if success else 0)
            data['total_bills_found'] = data.get('total_bills_found', 0) + bills_found
            data['last_check'] = firestore.SERVER_TIMESTAMP
            
            if response_time_ms:
                data['avg_response_time_ms'] = (
                    (data.get('avg_response_time_ms', 0) * (data['total_checks'] - 1) + response_time_ms) 
                    / data['total_checks']
                )
        else:
            data = {
                'date': today,
                'total_checks': 1,
                'successful_checks': 1 if success else 0,
                'total_bills_found': bills_found,
                'avg_response_time_ms': response_time_ms or 0,
                'last_check': firestore.SERVER_TIMESTAMP,
                'created_at': firestore.SERVER_TIMESTAMP
            }
        
        metric_ref.set(data, merge=True)
    
    def _check_failure_alerts(self, error_message: Optional[str]):
        """Check if we should trigger failure alerts."""
        # Query recent failures
        recent_failures = self.db.collection(RSS_MONITORING_COLLECTION)\
            .where(filter=firestore.FieldFilter('operation', '==', 'rss_check'))\
            .where(filter=firestore.FieldFilter('success', '==', False))\
            .order_by('start_time', direction=firestore.Query.DESCENDING)\
            .limit(5)\
            .stream()
        
        failure_count = len(list(recent_failures))
        
        if failure_count >= 3:  # 3 consecutive failures
            alert_data = {
                'alert_type': 'consecutive_failures',
                'severity': 'critical' if failure_count >= 5 else 'warning',
                'message': f"RSS feed has failed {failure_count} consecutive times",
                'error_message': error_message,
                'failure_count': failure_count,
                'created_at': firestore.SERVER_TIMESTAMP,
                'resolved': False
            }
            
            self.db.collection(RSS_ALERTS_COLLECTION).add(alert_data)
            logger.error(f"ALERT: {failure_count} consecutive RSS failures detected")
    
    def get_health_status(self) -> Dict[str, Any]:
        """Get current RSS feed health status."""
        # Get today's metrics
        today = datetime.now().strftime('%Y-%m-%d')
        metric_ref = self.db.collection(RSS_METRICS_COLLECTION).document(f"daily_metrics_{today}")
        metric_doc = metric_ref.get()
        
        if not metric_doc.exists:
            return {
                'status': 'unknown',
                'message': 'No data available for today'
            }
        
        metrics = metric_doc.to_dict()
        success_rate = (metrics.get('successful_checks', 0) / max(metrics.get('total_checks', 1), 1)) * 100
        
        # Check for active alerts
        active_alerts = self.db.collection(RSS_ALERTS_COLLECTION)\
            .where(filter=firestore.FieldFilter('resolved', '==', False))\
            .limit(1)\
            .stream()
        
        has_alerts = len(list(active_alerts)) > 0
        
        if success_rate >= 95 and not has_alerts:
            status = 'healthy'
        elif success_rate >= 80:
            status = 'warning'
        else:
            status = 'critical'
        
        return {
            'status': status,
            'success_rate': success_rate,
            'total_checks_today': metrics.get('total_checks', 0),
            'bills_found_today': metrics.get('total_bills_found', 0),
            'avg_response_time_ms': metrics.get('avg_response_time_ms', 0),
            'last_check': metrics.get('last_check'),
            'has_active_alerts': has_alerts
        }

# Global instance for easy import
rss_monitor = RSSMonitoringLogger() 