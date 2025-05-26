#!/usr/bin/env python3
"""
Schedule configuration for Promise Tracker ingestion and processing jobs.
Defines when jobs run and their dependencies.
"""

from typing import Dict, List, Optional
from dataclasses import dataclass

@dataclass
class JobConfig:
    """Configuration for a single job."""
    name: str
    schedule: str  # Cron format
    args: List[str]
    timeout_minutes: int = 30
    retry_attempts: int = 3
    depends_on: Optional[List[str]] = None  # Job dependencies

# =============================================================================
# JOB SCHEDULES
# =============================================================================

# Frequent RSS monitoring with conditional processing
RSS_MONITORING_JOBS = [
    JobConfig(
        name="check_legisinfo_rss",
        schedule="0 * * * *",  # Every hour
        args=["--hours_threshold", "2"],  # Check last 2 hours for overlap
        timeout_minutes=10
    ),
    JobConfig(
        name="ingest_canada_news", 
        schedule="*/30 * * * *",  # Every 30 minutes
        args=["--start_date", "2025-05-25"],  # Recent start date for ongoing monitoring
        timeout_minutes=20
    )
]

# Daily ingestion jobs  
DAILY_INGESTION_JOBS = [
    JobConfig(
        name="ingest_canada_gazette_p2",
        schedule="30 9 * * *",  # 9:30 AM EST daily
        args=["--start_date", "2025-01-01"],
        timeout_minutes=30  # Max 30 minutes for Cloud Scheduler
    ),
    JobConfig(
        name="ingest_oic",
        schedule="0 6,18 * * *",  # 6:00 AM and 6:00 PM EST daily
        args=["--start_date", "2025-01-01"], 
        timeout_minutes=30
    )
]

# Processing jobs (triggered after ingestion or run daily for cleanup)
PROCESSING_JOBS = [
    JobConfig(
        name="process_gazette_p2_to_evidence",
        schedule="45 9 * * *",  # 9:45 AM EST (15 min after Gazette ingestion)
        args=["--days_back", "2"], 
        timeout_minutes=30,  # Max 30 minutes for Cloud Scheduler
        depends_on=["ingest_canada_gazette_p2"]
    ),
    JobConfig(
        name="process_oic_to_evidence",
        schedule="30 6,18 * * *",  # 6:30 AM and 6:30 PM EST (30 min after OIC ingestion)
        args=["--days_back", "2"],
        timeout_minutes=30,
        depends_on=["ingest_oic"]
    )
]

# Note: LegisInfo and Canada News processing will be triggered automatically 
# by RSS monitoring jobs when new items are found (see cloud_run_main.py)

# =============================================================================
# SCHEDULE GROUPS
# =============================================================================

ALL_SCHEDULES = {
    "rss_monitoring": RSS_MONITORING_JOBS,
    "daily_ingestion": DAILY_INGESTION_JOBS, 
    "processing": PROCESSING_JOBS
}

# =============================================================================
# DEPLOYMENT CONFIGURATION
# =============================================================================

CLOUD_RUN_CONFIG = {
    "service_name": "promise-tracker-ingestion",
    "region": "northamerica-northeast2",  # Toronto
    "memory": "2Gi",
    "cpu": "1000m",
    "max_instances": 10,
    "timeout": "3600s"  # 1 hour max
}

CLOUD_SCHEDULER_CONFIG = {
    "time_zone": "America/Toronto",  # Eastern Time
    "region": "northamerica-northeast1"  # Toronto (closest to Montreal for scheduling)
} 