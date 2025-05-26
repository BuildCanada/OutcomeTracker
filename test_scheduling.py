#!/usr/bin/env python3
"""
Test script to verify Promise Tracker Cloud Run service and scheduling setup.
"""

import requests
import json
import time
import sys

# Your Cloud Run service URL (update this)
CLOUD_RUN_URL = "https://promise-tracker-ingestion-2gbdayf7rq-pd.a.run.app"

def test_health_check():
    """Test the health check endpoint."""
    print("🏥 Testing health check...")
    
    try:
        response = requests.get(f"{CLOUD_RUN_URL}/", timeout=30)
        response.raise_for_status()
        
        data = response.json()
        print(f"✅ Health check passed")
        print(f"   Service: {data.get('service')}")
        print(f"   Available jobs: {data.get('available_jobs')}")
        return True
        
    except Exception as e:
        print(f"❌ Health check failed: {e}")
        return False

def test_job_list():
    """Test the jobs list endpoint."""
    print("\n📋 Testing job list...")
    
    try:
        response = requests.get(f"{CLOUD_RUN_URL}/jobs", timeout=30)
        response.raise_for_status()
        
        data = response.json()
        available_jobs = data.get('available_jobs', {})
        
        print(f"✅ Found {len(available_jobs)} available jobs:")
        for job_name, job_info in available_jobs.items():
            print(f"   - {job_name}: {job_info.get('description')}")
        
        return True
        
    except Exception as e:
        print(f"❌ Job list test failed: {e}")
        return False

def test_individual_job(job_name, args=None):
    """Test executing an individual job."""
    print(f"\n🔧 Testing job: {job_name}")
    
    try:
        payload = {"args": args or []}
        
        response = requests.post(
            f"{CLOUD_RUN_URL}/jobs/{job_name}",
            json=payload,
            timeout=300  # 5 minutes
        )
        
        if response.status_code == 200:
            data = response.json()
            print(f"✅ Job {job_name} executed successfully")
            print(f"   Duration: {data.get('duration_seconds', 0):.1f}s")
            print(f"   Status: {data.get('status')}")
            
            # Show stdout summary
            stdout = data.get('stdout', '')
            if stdout:
                lines = stdout.split('\n')
                summary_lines = [line for line in lines if 'INFO' in line or 'ERROR' in line][-5:]
                print("   Recent output:")
                for line in summary_lines:
                    print(f"     {line}")
            
            return True
        else:
            print(f"❌ Job {job_name} failed with status {response.status_code}")
            try:
                error_data = response.json()
                print(f"   Error: {error_data.get('error', 'Unknown error')}")
            except:
                print(f"   Response: {response.text}")
            return False
            
    except Exception as e:
        print(f"❌ Job {job_name} test failed: {e}")
        return False

def test_batch_job():
    """Test batch job execution."""
    print(f"\n📦 Testing batch job execution...")
    
    try:
        # Test with two quick jobs
        payload = {
            "jobs": [
                {"name": "check_legisinfo_rss", "args": ["--hours_threshold", "1", "--max_items", "3"]},
                {"name": "ingest_canada_news", "args": ["--dry_run", "--start_date", "2025-05-25"]}
            ]
        }
        
        response = requests.post(
            f"{CLOUD_RUN_URL}/jobs/batch",
            json=payload,
            timeout=600  # 10 minutes
        )
        
        if response.status_code == 200:
            data = response.json()
            print(f"✅ Batch job executed successfully")
            print(f"   Batch status: {data.get('batch_status')}")
            
            summary = data.get('summary', {})
            print(f"   Total jobs: {summary.get('total_jobs')}")
            print(f"   Successful: {summary.get('successful')}")
            print(f"   Failed: {summary.get('failed')}")
            
            return True
        else:
            print(f"❌ Batch job failed with status {response.status_code}")
            return False
            
    except Exception as e:
        print(f"❌ Batch job test failed: {e}")
        return False

def main():
    print("🚀 Promise Tracker Scheduling Test Suite")
    print("=" * 50)
    
    # Test basic connectivity
    if not test_health_check():
        print("\n❌ Basic connectivity failed. Check your Cloud Run service.")
        sys.exit(1)
    
    # Test job listing
    if not test_job_list():
        print("\n❌ Job listing failed.")
        sys.exit(1)
    
    # Test individual jobs (quick tests only)
    test_jobs = [
        ("check_legisinfo_rss", ["--hours_threshold", "1", "--max_items", "3"]),
        ("ingest_canada_news", ["--dry_run", "--start_date", "2025-05-25"])
    ]
    
    success_count = 0
    for job_name, args in test_jobs:
        if test_individual_job(job_name, args):
            success_count += 1
    
    print(f"\n📊 Individual Job Test Results: {success_count}/{len(test_jobs)} passed")
    
    # Test batch execution
    if test_batch_job():
        print("\n✅ Batch job test passed")
    else:
        print("\n❌ Batch job test failed")
    
    print("\n🎉 Testing complete!")
    print("\nNext steps:")
    print("1. Deploy schedulers: python deploy_scheduler.py")
    print("2. Monitor jobs: python monitor_schedules.py list")
    print("3. Check status: python monitor_schedules.py status")

if __name__ == "__main__":
    main() 