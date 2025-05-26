#!/usr/bin/env python3
"""
Deploy Promise Tracker ingestion service to Google Cloud Run.
This script builds the container and deploys it with proper configuration.
"""

import os
import subprocess
import sys
import json
from datetime import datetime

# Configuration
PROJECT_ID = "promisetrackerapp"  # Your Firebase project ID
SERVICE_NAME = "promise-tracker-ingestion"
REGION = "northamerica-northeast2"  # Montreal region to match Firebase
IMAGE_NAME = f"gcr.io/{PROJECT_ID}/{SERVICE_NAME}"

def run_command(cmd, description):
    """Run a command and handle errors."""
    print(f"\n🔧 {description}")
    print(f"Running: {' '.join(cmd)}")
    
    result = subprocess.run(cmd, capture_output=True, text=True)
    
    if result.returncode != 0:
        print(f"❌ Error: {description} failed")
        print(f"STDOUT: {result.stdout}")
        print(f"STDERR: {result.stderr}")
        sys.exit(1)
    
    print(f"✅ {description} completed successfully")
    if result.stdout.strip():
        print(f"Output: {result.stdout.strip()}")
    
    return result

def check_prerequisites():
    """Check if required tools are installed."""
    print("🔍 Checking prerequisites...")
    
    # Check if gcloud is installed and authenticated
    try:
        result = subprocess.run(['gcloud', 'auth', 'list'], capture_output=True, text=True)
        if result.returncode != 0 or 'ACTIVE' not in result.stdout:
            print("❌ Please authenticate with gcloud: gcloud auth login")
            sys.exit(1)
        print("✅ gcloud authentication OK")
    except FileNotFoundError:
        print("❌ gcloud CLI not found. Please install Google Cloud SDK")
        sys.exit(1)
    
    # Check if Docker is running
    try:
        subprocess.run(['docker', 'info'], capture_output=True, check=True)
        print("✅ Docker is running")
    except (FileNotFoundError, subprocess.CalledProcessError):
        print("❌ Docker not found or not running. Please install and start Docker")
        sys.exit(1)

def configure_project():
    """Set the GCP project."""
    run_command(
        ['gcloud', 'config', 'set', 'project', PROJECT_ID],
        f"Setting GCP project to {PROJECT_ID}"
    )

def enable_apis():
    """Enable required Google Cloud APIs."""
    apis = [
        'cloudbuild.googleapis.com',
        'run.googleapis.com',
        'cloudscheduler.googleapis.com'
    ]
    
    for api in apis:
        run_command(
            ['gcloud', 'services', 'enable', api],
            f"Enabling {api}"
        )

def build_container():
    """Build and push the container image."""
    # Configure Docker to use gcloud as credential helper
    run_command(
        ['gcloud', 'auth', 'configure-docker'],
        "Configuring Docker for GCR"
    )
    
    # Build the container using Cloud Build
    run_command([
        'gcloud', 'builds', 'submit',
        '--tag', IMAGE_NAME,
        '.'
    ], f"Building container image {IMAGE_NAME}")

def deploy_service():
    """Deploy the service to Cloud Run."""
    deploy_cmd = [
        'gcloud', 'run', 'deploy', SERVICE_NAME,
        '--image', IMAGE_NAME,
        '--platform', 'managed',
        '--region', REGION,
        '--allow-unauthenticated',  # For Cloud Scheduler
        '--memory', '2Gi',
        '--cpu', '2',
        '--timeout', '3600',  # 1 hour timeout for long-running jobs
        '--max-instances', '10',
        '--set-env-vars', f'FIREBASE_PROJECT_ID={PROJECT_ID}',
        '--service-account', f'firebase-adminsdk@{PROJECT_ID}.iam.gserviceaccount.com'
    ]
    
    run_command(deploy_cmd, f"Deploying {SERVICE_NAME} to Cloud Run")

def get_service_url():
    """Get the deployed service URL."""
    result = run_command([
        'gcloud', 'run', 'services', 'describe', SERVICE_NAME,
        '--region', REGION,
        '--format', 'value(status.url)'
    ], "Getting service URL")
    
    return result.stdout.strip()

def create_scheduler_jobs(service_url):
    """Create Cloud Scheduler jobs for automated execution."""
    print("\n📅 Creating Cloud Scheduler jobs...")
    
    # Enable Cloud Scheduler API
    run_command(
        ['gcloud', 'services', 'enable', 'cloudscheduler.googleapis.com'],
        "Enabling Cloud Scheduler API"
    )
    
    # Create or update scheduler jobs
    scheduler_jobs = [
        {
            'name': 'rss-monitoring-hourly',
            'description': 'Run RSS monitoring every hour',
            'schedule': '0 * * * *',  # Every hour
            'url': f'{service_url}/schedule/rss-monitoring',
            'method': 'POST'
        },
        {
            'name': 'canada-news-daily',
            'description': 'Run Canada News RSS ingestion daily',
            'schedule': '0 6 * * *',  # 6 AM daily
            'url': f'{service_url}/jobs/ingest_canada_news_rss',
            'method': 'POST'
        },
        {
            'name': 'full-bill-ingestion-weekly',
            'description': 'Run full bill ingestion weekly',
            'schedule': '0 2 * * 0',  # 2 AM every Sunday
            'url': f'{service_url}/jobs/ingest_legisinfo_raw_bills',
            'method': 'POST'
        }
    ]
    
    for job in scheduler_jobs:
        # Delete existing job if it exists (ignore errors)
        subprocess.run([
            'gcloud', 'scheduler', 'jobs', 'delete', job['name'],
            '--location', REGION,
            '--quiet'
        ], capture_output=True)
        
        # Create new job
        create_cmd = [
            'gcloud', 'scheduler', 'jobs', 'create', 'http', job['name'],
            '--location', REGION,
            '--schedule', job['schedule'],
            '--uri', job['url'],
            '--http-method', job['method'],
            '--headers', 'Content-Type=application/json',
            '--body', '{}',
            '--description', job['description']
        ]
        
        run_command(create_cmd, f"Creating scheduler job: {job['name']}")

def main():
    """Main deployment workflow."""
    print("🚀 Promise Tracker Cloud Run Deployment")
    print("=" * 50)
    
    # Check prerequisites
    check_prerequisites()
    
    # Configure project
    configure_project()
    
    # Enable APIs
    enable_apis()
    
    # Build container
    build_container()
    
    # Deploy service
    deploy_service()
    
    # Get service URL
    service_url = get_service_url()
    print(f"\n🌐 Service deployed at: {service_url}")
    
    # Create scheduler jobs
    create_scheduler_jobs(service_url)
    
    print("\n✅ Deployment completed successfully!")
    print(f"📊 Monitor your service at: https://console.cloud.google.com/run/detail/{REGION}/{SERVICE_NAME}")
    print(f"⏰ View scheduled jobs at: https://console.cloud.google.com/cloudscheduler")
    print(f"\n🔗 Service endpoints:")
    print(f"  Health check: {service_url}/")
    print(f"  List jobs: {service_url}/jobs")
    print(f"  Execute job: {service_url}/jobs/<job_name>")
    print(f"  RSS monitoring: {service_url}/schedule/rss-monitoring")

if __name__ == '__main__':
    main() 