# 🕐 Promise Tracker Scheduling & Sequencing Guide

This guide explains how to configure the timing and sequencing of Promise Tracker ingestion and processing jobs.

## 📊 Current Job Structure

### **Ingestion Jobs (4 scripts)**
1. `ingest_legisinfo_bills.py` - Ingest LEGISinfo bills
2. `ingest_canada_news.py` - Ingest Canada News RSS feed  
3. `ingest_canada_gazette_p2.py` - Ingest Canada Gazette Part 2
4. `ingest_oic.py` - Ingest Orders in Council

### **Processing Jobs (4 scripts)**
1. `process_legisinfo_to_evidence.py` - Process LEGISinfo bills to evidence
2. `process_news_to_evidence.py` - Process news to evidence
3. `process_gazette_p2_to_evidence.py` - Process Gazette P2 to evidence  
4. `process_oic_to_evidence.py` - Process OIC to evidence

### **Utilities**
- `check_legisinfo_rss_updates.py` - RSS monitoring utility

---

## ⏰ Default Schedule Configuration

### **RSS Monitoring (Frequent)**
- **LEGISinfo RSS Check**: Every 3 hours (`0 */3 * * *`)
- **Canada News**: Every 4 hours, offset by 30 min (`30 */4 * * *`)

### **Daily Ingestion (Early Morning)**
- **LEGISinfo Bills**: 2:00 AM daily (`0 2 * * *`)
- **Gazette P2**: 3:00 AM daily (`0 3 * * *`)
- **Orders in Council**: 4:00 AM daily (`0 4 * * *`)

### **Processing (After Ingestion)**
- **Process LEGISinfo**: 6:00 AM daily (`0 6 * * *`)
- **Process News**: 6:30 AM daily (`30 6 * * *`)
- **Process Gazette P2**: 7:00 AM daily (`0 7 * * *`)
- **Process OIC**: 7:30 AM daily (`30 7 * * *`)

### **Weekly Jobs**
- **Full LEGISinfo Refresh**: Sunday 1:00 AM (`0 1 * * 0`)

---

## 🚀 Deployment Commands

### **1. Test the Setup**
```bash
# Test Cloud Run service
python test_scheduling.py
```

### **2. Deploy Scheduled Jobs**
```bash
# Deploy all Cloud Scheduler jobs
python deploy_scheduler.py

# Delete all jobs (if needed)
python deploy_scheduler.py --delete
```

### **3. Monitor Jobs**
```bash
# List all scheduled jobs
python monitor_schedules.py list

# Check job performance (last 24 hours)
python monitor_schedules.py status

# Check job performance (last 7 days)
python monitor_schedules.py status 168

# View next scheduled executions
python monitor_schedules.py next
```

### **4. Manual Job Control**
```bash
# Pause a job
python monitor_schedules.py pause pt-rss-monitoring-check-legisinfo-rss

# Resume a job
python monitor_schedules.py resume pt-rss-monitoring-check-legisinfo-rss

# Trigger a job immediately
python monitor_schedules.py trigger pt-rss-monitoring-check-legisinfo-rss
```

---

## 🔧 Configuration Options

### **Option 1: Individual Job Scheduling**
Each job runs on its own schedule. Good for independent data sources.

**Pros**: 
- Simple to understand
- Easy to debug individual failures
- Independent scaling

**Cons**:
- No automatic sequencing
- Processing might run before ingestion finishes

### **Option 2: Sequential Batch Processing**
Multiple jobs run in sequence within a single scheduler.

**Pros**:
- Guaranteed execution order
- Simpler monitoring
- Better resource utilization

**Cons**:
- One failure can stop the whole batch
- Longer total execution time

### **Option 3: Event-Driven Processing**
Processing jobs triggered automatically when ingestion completes.

**Implementation**: Add webhooks or Pub/Sub triggers (not currently implemented).

---

## 📝 Customizing Schedules

### **Edit Schedule Configuration**
Modify `schedule_config.py`:

```python
# Example: Change RSS monitoring to every hour
JobConfig(
    name="check_legisinfo_rss",
    schedule="0 * * * *",  # Every hour instead of every 3 hours
    args=["--hours_threshold", "2"],  # Check last 2 hours
    timeout_minutes=10
)

# Example: Add weekend-only job
JobConfig(
    name="ingest_legisinfo_bills",
    schedule="0 8 * * 6,0",  # 8 AM on weekends only
    args=["--full_refresh"],
    timeout_minutes=180
)
```

### **Cron Schedule Examples**
```bash
"0 */3 * * *"     # Every 3 hours
"30 */4 * * *"    # Every 4 hours at 30 minutes past
"0 2 * * *"       # Daily at 2:00 AM
"0 9 * * 1-5"     # Weekdays at 9:00 AM
"0 1 * * 0"       # Sundays at 1:00 AM
"0 0 1 * *"       # First day of month at midnight
```

### **Add New Jobs**
1. Add to `schedule_config.py`
2. Update `cloud_run_main.py` if needed
3. Redeploy: `python deploy_scheduler.py`

---

## 🎯 Recommended Sequences

### **For Development/Testing**
```bash
# Quick test sequence (run manually)
python scripts/utilities/check_legisinfo_rss_updates.py --hours_threshold 24
python scripts/ingestion_jobs/ingest_canada_news.py --dry_run --start_date 2025-05-25
```

### **For Production**
The default schedule handles this automatically:

**Morning Data Pipeline (2 AM - 8 AM)**:
1. `ingest_legisinfo_bills` (2 AM)
2. `ingest_canada_gazette_p2` (3 AM) 
3. `ingest_oic` (4 AM)
4. `process_legisinfo_to_evidence` (6 AM)
5. `process_news_to_evidence` (6:30 AM)
6. `process_gazette_p2_to_evidence` (7 AM)
7. `process_oic_to_evidence` (7:30 AM)

**Continuous RSS Monitoring**:
- LEGISinfo RSS check every 3 hours
- Canada News every 4 hours

---

## 🔍 Monitoring & Debugging

### **Check Job Status**
```bash
# View all jobs and their states
gcloud scheduler jobs list --location=northamerica-northeast2 --filter="name:pt-*"

# View specific job details
gcloud scheduler jobs describe pt-rss-monitoring-check-legisinfo-rss --location=northamerica-northeast2
```

### **View Logs**
```bash
# Cloud Run logs
gcloud logs read "resource.type=cloud_run_revision AND resource.labels.service_name=promise-tracker-ingestion" --limit=50

# Scheduler logs
gcloud logs read "resource.type=cloud_scheduler_job" --limit=20

# View logs for specific job
gcloud logs read 'resource.type="cloud_scheduler_job" AND resource.labels.job_id="pt-rss-monitoring-check-legisinfo-rss"' --limit=10
```

### **Common Issues**

**Job timeouts**: Increase `timeout_minutes` in schedule config
**Memory issues**: Increase Cloud Run memory allocation
**Rate limiting**: Spread job schedules further apart
**Dependency failures**: Check processing job schedules run after ingestion

---

## 🎛️ Advanced Configuration

### **Environment-Specific Schedules**
```python
# In schedule_config.py
import os

if os.getenv('ENVIRONMENT') == 'development':
    # More frequent testing schedule
    RSS_MONITORING_JOBS[0].schedule = "*/15 * * * *"  # Every 15 minutes
elif os.getenv('ENVIRONMENT') == 'production':
    # Standard production schedule
    pass
```

### **Conditional Job Execution**
```python
# In cloud_run_main.py - add environment checks
if os.getenv('ENABLE_FULL_REFRESH', 'false').lower() == 'true':
    # Only run full refresh jobs
    pass
```

### **Scaling Configuration**
Update Cloud Run configuration in `schedule_config.py`:
```python
CLOUD_RUN_CONFIG = {
    "memory": "4Gi",          # Increase for large jobs
    "cpu": "2000m",          # Increase for CPU-intensive jobs  
    "max_instances": 5,       # Limit concurrent executions
    "timeout": "7200s"        # 2 hours for long-running jobs
}
```

---

## 📚 Additional Resources

- **Cloud Scheduler Documentation**: https://cloud.google.com/scheduler/docs
- **Cloud Run Documentation**: https://cloud.google.com/run/docs
- **Cron Expression Guide**: https://crontab.guru/
- **Promise Tracker Architecture**: See main README.md

---

## 🚨 Emergency Procedures

### **Stop All Jobs**
```bash
# Pause all jobs quickly
python monitor_schedules.py list | grep "pt-" | awk '{print $2}' | xargs -I {} python monitor_schedules.py pause {}
```

### **Emergency Data Recovery**
```bash
# Run emergency ingestion (last 7 days)
curl -X POST "https://promise-tracker-ingestion-2gbdayf7rq-pd.a.run.app/jobs/ingest_canada_news" \
  -H "Content-Type: application/json" \
  -d '{"args": ["--start_date", "2025-05-18"]}'
```

### **Health Check**
```bash
# Quick health check
curl https://promise-tracker-ingestion-2gbdayf7rq-pd.a.run.app/
``` 