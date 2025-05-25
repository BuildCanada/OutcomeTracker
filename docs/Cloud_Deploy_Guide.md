# RSS Monitoring System - Cloud Deployment Guide

## Current Status ✅

**Your RSS monitoring system is already working locally!** 

- ✅ Monitoring system connected to Firestore (`promisetrackerapp`)
- ✅ RSS checks working with automatic logging
- ✅ Admin dashboard available at `/admin/monitoring`
- ✅ All monitoring scripts tested and functional

## Deployment Options

### Option 1: Simple Local/Scheduled Deployment (Recommended for now)

Since the system works locally, you can run it on your development machine or a server:

```bash
# 1. Run RSS checks every 30 minutes (add to crontab)
*/30 * * * * cd /Users/tscheidt/promise-tracker/PromiseTracker && python scripts/ingestion_jobs/check_legisinfo_rss_updates.py --hours_threshold 1

# 2. Run full ingestion daily at 6 AM
0 6 * * * cd /Users/tscheidt/promise-tracker/PromiseTracker && python scripts/ingestion_jobs/rss_driven_bill_ingestion.py --hours_threshold 24 --fallback_full_run
```

### Option 2: Cloud Run Deployment (In Progress)

We've prepared everything for Cloud Run but hit some build permission issues:

1. **Files Ready:**
   - `cloud_run_main.py` - Flask service with RSS and ingestion endpoints
   - `Dockerfile` - Container configuration
   - `requirements.txt` - Updated with Flask dependencies

2. **Issue:** Cloud Build permission errors with storage access

3. **Solution Attempts:**
   - ✅ Added storage.admin role to compute service account
   - ✅ Enabled all necessary APIs
   - ❌ Still getting build failures

### Option 3: Alternative Cloud Solutions

**A. Cloud Functions** (Simpler than Cloud Run):
```bash
# Deploy RSS check function
gcloud functions deploy rss-check \
  --runtime python311 \
  --trigger-http \
  --entry-point rss_check \
  --source . \
  --region northamerica-northeast2

# Deploy ingestion function  
gcloud functions deploy full-ingestion \
  --runtime python311 \
  --trigger-http \
  --entry-point full_ingestion \
  --source . \
  --region northamerica-northeast2
```

**B. VM with Scheduled Tasks:**
- Create a small VM instance
- Install your code and dependencies
- Use cron jobs for scheduling

## Current Monitoring Features Working

1. **Automatic Tracking:** Every RSS check is logged with:
   - Start/completion times
   - Response times  
   - Bills found count
   - Success/failure status

2. **Alert System:** 
   - Tracks consecutive failures
   - Generates alerts after 3+ failures
   - Stores in `rss_feed_alerts` collection

3. **Metrics Dashboard:**
   - Real-time status indicators
   - 7-day trend analysis  
   - Recent activity logs
   - Performance metrics

4. **Admin Interface:**
   - Available at `http://localhost:3000/admin/monitoring`
   - Live updates every 30 seconds
   - Alert management
   - Manual trigger options

## Immediate Next Steps

1. **Start Using the System:**
   ```bash
   # Test RSS check with monitoring
   cd /Users/tscheidt/promise-tracker/PromiseTracker
   python scripts/ingestion_jobs/check_legisinfo_rss_updates.py --hours_threshold 1
   
   # View results in admin dashboard
   # Go to http://localhost:3000/admin/monitoring
   ```

2. **Set Up Local Scheduling:**
   ```bash
   # Add to crontab for automatic runs
   crontab -e
   # Add the cron jobs mentioned in Option 1
   ```

3. **Monitor Performance:**
   - Check the admin dashboard regularly
   - Review alerts in Firestore
   - Monitor response times and success rates

## Troubleshooting Cloud Run

If you want to continue with Cloud Run deployment:

1. **Check Build Logs:**
   ```bash
   gcloud logging read "resource.type=build" --limit=50 --format="value(textPayload)"
   ```

2. **Try Artifact Registry:**
   ```bash
   # Enable Artifact Registry
   gcloud services enable artifactregistry.googleapis.com
   
   # Create repository
   gcloud artifacts repositories create quickstart-docker-repo \
     --repository-format=docker \
     --location=northamerica-northeast2
   ```

3. **Alternative Build Method:**
   ```bash
   # Build locally and push (if Docker is available)
   docker build -t gcr.io/promisetrackerapp/rss-monitor .
   docker push gcr.io/promisetrackerapp/rss-monitor
   gcloud run deploy rss-monitor --image gcr.io/promisetrackerapp/rss-monitor
   ```

## Success Metrics

Your system will provide:
- 📊 **Bill Discovery Rate:** How many new bills found per check
- ⏱️ **Response Time:** How quickly RSS feeds respond  
- 🎯 **Success Rate:** Percentage of successful checks
- 🚨 **Alert Frequency:** How often issues occur
- 📈 **Trend Analysis:** Performance over time

The monitoring system is designed to be robust and provide early warning of any issues with the RSS feeds or processing pipeline. 