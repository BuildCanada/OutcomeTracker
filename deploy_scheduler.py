#!/usr/bin/env python3
"""
Deploy Cloud Scheduler jobs for Promise Tracker ingestion and processing.
Sets up all scheduled jobs based on schedule_config.py.
"""

import subprocess
import json
import sys
from schedule_config import ALL_SCHEDULES, CLOUD_SCHEDULER_CONFIG, CLOUD_RUN_CONFIG

def run_command(cmd, check=True):
    """Run a shell command and return the result."""
    print(f"Running: {' '.join(cmd)}")
    result = subprocess.run(cmd, capture_output=True, text=True, check=False)
    
    if check and result.returncode != 0:
        print(f"ERROR: Command failed with return code {result.returncode}")
        print(f"STDOUT: {result.stdout}")
        print(f"STDERR: {result.stderr}")
        sys.exit(1)
    
    return result

def create_scheduler_job(job_config, group_name):
    """Create a Cloud Scheduler job."""
    job_name = f"pt-{group_name}-{job_config.name.replace('_', '-')}"
    
    # Cloud Run target URL
    cloud_run_url = f"https://{CLOUD_RUN_CONFIG['service_name']}-2gbdayf7rq-pd.a.run.app"
    
    # Use with-processing endpoint for RSS monitoring jobs that should trigger processing
    if group_name == "rss_monitoring":
        target_url = f"{cloud_run_url}/jobs/{job_config.name}/with-processing"
    else:
        target_url = f"{cloud_run_url}/jobs/{job_config.name}"
    
    # Prepare request body
    request_body = {
        "args": job_config.args
    }
    
    # Create Cloud Scheduler job
    cmd = [
        "gcloud", "scheduler", "jobs", "create", "http", job_name,
        "--location", CLOUD_SCHEDULER_CONFIG["region"],
        "--schedule", job_config.schedule,
        "--time-zone", CLOUD_SCHEDULER_CONFIG["time_zone"], 
        "--uri", target_url,
        "--http-method", "POST",
        "--headers", "Content-Type=application/json",
        "--message-body", json.dumps(request_body),
        "--attempt-deadline", f"{job_config.timeout_minutes * 60}s",
        "--max-retry-attempts", str(job_config.retry_attempts),
        "--description", f"Promise Tracker {group_name}: {job_config.name}"
    ]
    
    # Check if job already exists
    check_cmd = [
        "gcloud", "scheduler", "jobs", "describe", job_name,
        "--location", CLOUD_SCHEDULER_CONFIG["region"]
    ]
    
    result = run_command(check_cmd, check=False)
    
    if result.returncode == 0:
        print(f"Job {job_name} already exists. Updating...")
        # Delete and recreate for updates
        delete_cmd = [
            "gcloud", "scheduler", "jobs", "delete", job_name,
            "--location", CLOUD_SCHEDULER_CONFIG["region"],
            "--quiet"
        ]
        run_command(delete_cmd)
    
    # Create the job
    run_command(cmd)
    print(f"✅ Created scheduler job: {job_name}")
    print(f"   Schedule: {job_config.schedule}")
    print(f"   Target: {target_url}")
    print()

def create_sequential_job(job_configs, group_name):
    """Create a single scheduler job that runs multiple jobs in sequence."""
    job_name = f"pt-{group_name}-sequence"
    
    # Cloud Run batch endpoint
    cloud_run_url = f"https://{CLOUD_RUN_CONFIG['service_name']}-2gbdayf7rq-pd.a.run.app"
    target_url = f"{cloud_run_url}/jobs/batch"
    
    # Prepare batch request
    jobs_list = []
    for job_config in job_configs:
        jobs_list.append({
            "name": job_config.name,
            "args": job_config.args
        })
    
    request_body = {
        "jobs": jobs_list
    }
    
    # Use the schedule from the first job in the sequence
    schedule = job_configs[0].schedule if job_configs else "0 2 * * *"
    max_timeout = max(job.timeout_minutes for job in job_configs) if job_configs else 60
    
    cmd = [
        "gcloud", "scheduler", "jobs", "create", "http", job_name,
        "--location", CLOUD_SCHEDULER_CONFIG["region"],
        "--schedule", schedule,
        "--time-zone", CLOUD_SCHEDULER_CONFIG["time_zone"],
        "--uri", target_url,
        "--http-method", "POST", 
        "--headers", "Content-Type=application/json",
        "--message-body", json.dumps(request_body),
        "--attempt-deadline", f"{max_timeout * 60}s",
        "--max-retry-attempts", "2",
        "--description", f"Promise Tracker {group_name} sequence: {len(jobs_list)} jobs"
    ]
    
    # Check if job exists and delete if so
    check_cmd = [
        "gcloud", "scheduler", "jobs", "describe", job_name,
        "--location", CLOUD_SCHEDULER_CONFIG["region"]
    ]
    
    result = run_command(check_cmd, check=False)
    if result.returncode == 0:
        print(f"Sequential job {job_name} already exists. Updating...")
        delete_cmd = [
            "gcloud", "scheduler", "jobs", "delete", job_name,
            "--location", CLOUD_SCHEDULER_CONFIG["region"],
            "--quiet"
        ]
        run_command(delete_cmd)
    
    run_command(cmd)
    print(f"✅ Created sequential job: {job_name}")
    print(f"   Schedule: {schedule}")
    print(f"   Jobs: {[job.name for job in job_configs]}")
    print()

def deploy_all_schedules():
    """Deploy all scheduled jobs."""
    print("🚀 Deploying Promise Tracker Scheduled Jobs")
    print("=" * 50)
    
    # Check if Cloud Run service exists
    check_service_cmd = [
        "gcloud", "run", "services", "describe", CLOUD_RUN_CONFIG["service_name"],
        "--region", CLOUD_RUN_CONFIG["region"]
    ]
    
    result = run_command(check_service_cmd, check=False)
    if result.returncode != 0:
        print(f"❌ Cloud Run service '{CLOUD_RUN_CONFIG['service_name']}' not found in region '{CLOUD_RUN_CONFIG['region']}'")
        print("Please deploy the Cloud Run service first using deploy_cloud_run.py")
        sys.exit(1)
    
    print(f"✅ Found Cloud Run service: {CLOUD_RUN_CONFIG['service_name']}")
    print()
    
    # Deploy individual jobs
    for group_name, job_configs in ALL_SCHEDULES.items():
        print(f"📅 Deploying {group_name} jobs...")
        
        if group_name == "processing":
            # For processing jobs, create a sequential batch job  
            create_sequential_job(job_configs, group_name)
        else:
            # For other jobs, create individual schedulers
            for job_config in job_configs:
                create_scheduler_job(job_config, group_name)
    
    print("✅ All scheduler jobs deployed successfully!")
    print()
    
    # List all created jobs
    print("📋 Created scheduler jobs:")
    list_cmd = [
        "gcloud", "scheduler", "jobs", "list",
        "--location", CLOUD_SCHEDULER_CONFIG["region"],
        "--filter", "name:pt-*"
    ]
    run_command(list_cmd, check=False)

def main():
    if len(sys.argv) > 1 and sys.argv[1] == "--delete":
        print("🗑️  Deleting all Promise Tracker scheduler jobs...")
        
        # List and delete all PT jobs
        list_cmd = [
            "gcloud", "scheduler", "jobs", "list",
            "--location", CLOUD_SCHEDULER_CONFIG["region"],
            "--filter", "name:pt-*",
            "--format", "value(name)"
        ]
        
        result = run_command(list_cmd, check=False)
        
        if result.stdout.strip():
            job_names = result.stdout.strip().split('\n')
            for job_name in job_names:
                delete_cmd = [
                    "gcloud", "scheduler", "jobs", "delete", job_name,
                    "--location", CLOUD_SCHEDULER_CONFIG["region"],
                    "--quiet"
                ]
                run_command(delete_cmd)
                print(f"🗑️  Deleted: {job_name}")
        else:
            print("No Promise Tracker scheduler jobs found.")
        
        return
    
    deploy_all_schedules()

if __name__ == "__main__":
    main() 