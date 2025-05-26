#!/usr/bin/env python3
"""
Monitor Promise Tracker scheduled jobs and their execution status.
Provides insights into job success rates, timing, and failures.
"""

import subprocess
import json
import sys
from datetime import datetime, timedelta
from schedule_config import CLOUD_SCHEDULER_CONFIG

def run_command(cmd, check=False):
    """Run a shell command and return the result."""
    result = subprocess.run(cmd, capture_output=True, text=True, check=False)
    if check and result.returncode != 0:
        print(f"ERROR: {' '.join(cmd)}")
        print(f"STDERR: {result.stderr}")
        sys.exit(1)
    return result

def get_scheduler_jobs():
    """Get all Promise Tracker scheduler jobs."""
    cmd = [
        "gcloud", "scheduler", "jobs", "list",
        "--location", CLOUD_SCHEDULER_CONFIG["region"],
        "--format", "json"
    ]
    
    result = run_command(cmd, check=True)
    all_jobs = json.loads(result.stdout) if result.stdout.strip() else []
    
    # Filter for Promise Tracker jobs (those starting with 'pt-')
    pt_jobs = [job for job in all_jobs if job['name'].split('/')[-1].startswith('pt-')]
    return pt_jobs

def get_job_executions(job_name, hours_back=24):
    """Get recent executions for a job."""
    since_time = datetime.utcnow() - timedelta(hours=hours_back)
    since_str = since_time.strftime('%Y-%m-%dT%H:%M:%SZ')
    
    cmd = [
        "gcloud", "logging", "read",
        f'resource.type="cloud_scheduler_job" AND resource.labels.job_id="{job_name}" AND timestamp>="{since_str}"',
        "--limit", "50",
        "--format", "json"
    ]
    
    result = run_command(cmd, check=False)
    return json.loads(result.stdout) if result.stdout.strip() else []

def analyze_job_performance(jobs, hours_back=24):
    """Analyze job performance metrics."""
    print(f"📊 Job Performance Analysis (Last {hours_back} hours)")
    print("=" * 80)
    
    total_jobs = len(jobs)
    active_jobs = 0
    
    for job in jobs:
        job_name = job['name'].split('/')[-1]
        state = job.get('state', 'UNKNOWN')
        schedule = job.get('schedule', 'N/A')
        
        print(f"\n🔧 Job: {job_name}")
        print(f"   State: {state}")
        print(f"   Schedule: {schedule}")
        
        if state == 'ENABLED':
            active_jobs += 1
        
        # Get recent executions
        executions = get_job_executions(job_name, hours_back)
        
        if executions:
            success_count = 0
            failure_count = 0
            latest_execution = None
            
            for execution in executions:
                severity = execution.get('severity', 'INFO')
                timestamp = execution.get('timestamp', '')
                
                if not latest_execution:
                    latest_execution = timestamp
                
                if severity == 'ERROR':
                    failure_count += 1
                else:
                    success_count += 1
            
            total_executions = success_count + failure_count
            success_rate = (success_count / total_executions * 100) if total_executions > 0 else 0
            
            print(f"   Executions: {total_executions} (Success: {success_count}, Failures: {failure_count})")
            print(f"   Success Rate: {success_rate:.1f}%")
            print(f"   Latest Execution: {latest_execution or 'Never'}")
            
            if failure_count > 0:
                print(f"   ⚠️  {failure_count} failures detected!")
        else:
            print(f"   📝 No execution logs found in last {hours_back} hours")
    
    print(f"\n📈 Summary:")
    print(f"   Total Jobs: {total_jobs}")
    print(f"   Active Jobs: {active_jobs}")
    print(f"   Inactive Jobs: {total_jobs - active_jobs}")

def show_next_executions(jobs):
    """Show upcoming job executions."""
    print(f"\n⏰ Next Scheduled Executions")
    print("=" * 50)
    
    for job in jobs:
        job_name = job['name'].split('/')[-1]
        schedule = job.get('schedule', 'N/A')
        state = job.get('state', 'UNKNOWN')
        
        if state == 'ENABLED':
            # Note: This is a simplified display. Actual next execution time 
            # calculation from cron would require a cron parsing library
            print(f"🕐 {job_name}")
            print(f"   Schedule: {schedule}")
            print(f"   State: {state}")
            print()

def pause_job(job_name):
    """Pause a specific job."""
    cmd = [
        "gcloud", "scheduler", "jobs", "pause", job_name,
        "--location", CLOUD_SCHEDULER_CONFIG["region"]
    ]
    
    result = run_command(cmd, check=False)
    if result.returncode == 0:
        print(f"✅ Paused job: {job_name}")
    else:
        print(f"❌ Failed to pause job: {job_name}")
        print(f"Error: {result.stderr}")

def resume_job(job_name):
    """Resume a specific job."""
    cmd = [
        "gcloud", "scheduler", "jobs", "resume", job_name,
        "--location", CLOUD_SCHEDULER_CONFIG["region"]
    ]
    
    result = run_command(cmd, check=False)
    if result.returncode == 0:
        print(f"✅ Resumed job: {job_name}")
    else:
        print(f"❌ Failed to resume job: {job_name}")
        print(f"Error: {result.stderr}")

def trigger_job_now(job_name):
    """Manually trigger a job execution."""
    cmd = [
        "gcloud", "scheduler", "jobs", "run", job_name,
        "--location", CLOUD_SCHEDULER_CONFIG["region"]
    ]
    
    result = run_command(cmd, check=False)
    if result.returncode == 0:
        print(f"✅ Triggered job: {job_name}")
    else:
        print(f"❌ Failed to trigger job: {job_name}")
        print(f"Error: {result.stderr}")

def main():
    if len(sys.argv) < 2:
        print("📊 Promise Tracker Job Monitor")
        print("=" * 40)
        print("Usage:")
        print("  python monitor_schedules.py status [hours_back]")
        print("  python monitor_schedules.py list")
        print("  python monitor_schedules.py pause <job_name>") 
        print("  python monitor_schedules.py resume <job_name>")
        print("  python monitor_schedules.py trigger <job_name>")
        print("  python monitor_schedules.py next")
        return
    
    command = sys.argv[1]
    
    jobs = get_scheduler_jobs()
    
    if not jobs:
        print("❌ No Promise Tracker scheduler jobs found.")
        print("Run 'python deploy_scheduler.py' to create jobs.")
        return
    
    if command == "status":
        hours_back = int(sys.argv[2]) if len(sys.argv) > 2 else 24
        analyze_job_performance(jobs, hours_back)
    
    elif command == "list":
        print("📋 Promise Tracker Scheduled Jobs")
        print("=" * 50)
        for job in jobs:
            job_name = job['name'].split('/')[-1]
            state = job.get('state', 'UNKNOWN')
            schedule = job.get('schedule', 'N/A')
            description = job.get('description', 'N/A')
            
            status_emoji = "✅" if state == "ENABLED" else "⏸️"
            print(f"{status_emoji} {job_name}")
            print(f"   Schedule: {schedule}")
            print(f"   State: {state}")
            print(f"   Description: {description}")
            print()
    
    elif command == "next":
        show_next_executions(jobs)
    
    elif command == "pause":
        if len(sys.argv) < 3:
            print("❌ Please specify job name to pause")
            return
        job_name = sys.argv[2]
        pause_job(job_name)
    
    elif command == "resume":
        if len(sys.argv) < 3:
            print("❌ Please specify job name to resume")
            return
        job_name = sys.argv[2]
        resume_job(job_name)
    
    elif command == "trigger":
        if len(sys.argv) < 3:
            print("❌ Please specify job name to trigger")
            return
        job_name = sys.argv[2]
        trigger_job_now(job_name)
    
    else:
        print(f"❌ Unknown command: {command}")

if __name__ == "__main__":
    main() 