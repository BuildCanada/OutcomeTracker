#!/usr/bin/env python3
"""
Simplified Promise Tracker Cloud Run deployment.
Uses Cloud Build directly without local Docker setup.
"""

import os
import subprocess
import sys

# Configuration
PROJECT_ID = "promisetrackerapp"
SERVICE_NAME = "promise-tracker-ingestion"
REGION = "northamerica-northeast2"

def run_cmd(cmd, description):
    """Run a command and show progress."""
    print(f"\n🔧 {description}")
    print(f"💭 Running: {' '.join(cmd)}")
    
    result = subprocess.run(cmd)
    
    if result.returncode != 0:
        print(f"❌ Failed: {description}")
        sys.exit(1)
    
    print(f"✅ Success: {description}")
    return result

def main():
    """Deploy directly using Cloud Build and Cloud Run."""
    print("🚀 Quick Promise Tracker Cloud Run Deployment")
    print("=" * 50)
    
    # Set project
    run_cmd([
        'gcloud', 'config', 'set', 'project', PROJECT_ID
    ], "Setting project")
    
    # Enable APIs
    run_cmd([
        'gcloud', 'services', 'enable', 
        'cloudbuild.googleapis.com',
        'run.googleapis.com'
    ], "Enabling APIs")
    
    # Build and deploy in one step using Cloud Build
    print(f"\n🏗️ Building and deploying to Cloud Run...")
    print("This will take 3-5 minutes...")
    
    deploy_cmd = [
        'gcloud', 'run', 'deploy', SERVICE_NAME,
        '--source', '.',  # Deploy from source (Cloud Build automatically)
        '--region', REGION,
        '--allow-unauthenticated',
        '--memory', '2Gi',
        '--cpu', '2',
        '--timeout', '3600',
        '--max-instances', '10',
        '--set-env-vars', f'FIREBASE_PROJECT_ID={PROJECT_ID}',
        '--platform', 'managed'
    ]
    
    result = subprocess.run(deploy_cmd)
    
    if result.returncode == 0:
        print("\n✅ Deployment successful!")
        
        # Get service URL
        url_result = subprocess.run([
            'gcloud', 'run', 'services', 'describe', SERVICE_NAME,
            '--region', REGION,
            '--format', 'value(status.url)'
        ], capture_output=True, text=True)
        
        if url_result.returncode == 0:
            service_url = url_result.stdout.strip()
            print(f"🌐 Service URL: {service_url}")
            print(f"\n🔗 Test endpoints:")
            print(f"  Health: {service_url}/")
            print(f"  Jobs: {service_url}/jobs")
            print(f"  RSS Check: curl -X POST {service_url}/jobs/check_legisinfo_rss")
        
        print(f"\n📊 Monitor at: https://console.cloud.google.com/run/detail/{REGION}/{SERVICE_NAME}")
        
    else:
        print("❌ Deployment failed!")
        sys.exit(1)

if __name__ == '__main__':
    main() 