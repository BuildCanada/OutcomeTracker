# 🚀 Promise Tracker Pipeline - Cloud Run Quick Start

Your pipeline migration is complete! Here's how to deploy it to Google Cloud Run in 3 simple steps.

## Prerequisites ✅

1. **Google Cloud SDK installed**
   ```bash
   gcloud auth login
   export PROJECT_ID="your-project-id"
   gcloud config set project $PROJECT_ID
   ```

2. **Billing enabled** on your Google Cloud project

## 3-Step Deployment 🎯

### Step 1: Deploy to Cloud Run
```bash
./deploy_to_cloud_run.sh
```
**What it does**: Builds container, deploys to Cloud Run, outputs service URL

### Step 2: Test the Deployment  
```bash
./test_cloud_run.sh
```
**What it does**: Runs 5 comprehensive tests to verify everything works

### Step 3: Set Up Automation (Optional)
```bash
./setup_cloud_scheduler.sh
```
**What it does**: Creates scheduled jobs for automatic pipeline execution

## 🧪 Manual Testing

If you want to test manually, get your service URL first:
```bash
SERVICE_URL=$(gcloud run services describe promise-tracker-pipeline \
    --platform managed --region us-central1 \
    --format 'value(status.url)')
echo "Service URL: $SERVICE_URL"
```

Then test endpoints:
```bash
# Health check
curl $SERVICE_URL/health

# Run Canada News ingestion (dry run)
curl -X POST \
  -H "Content-Type: application/json" \
  -d '{"config": {"dry_run": true, "max_items": 1}}' \
  $SERVICE_URL/jobs/ingestion/canada_news

# Check job status
curl $SERVICE_URL/jobs/status
```

## 📊 What You Get

### **New Pipeline Architecture**
- ✅ **Resilient**: Individual job failures don't crash the system
- ✅ **Scalable**: Auto-scaling based on demand  
- ✅ **Monitored**: Comprehensive logging and metrics
- ✅ **Automated**: Scheduled execution with Cloud Scheduler

### **API Endpoints**
- `GET /health` - Health check
- `GET /jobs/status` - Current job statuses
- `POST /jobs/{stage}/{job_name}` - Run specific job
- `POST /jobs/batch/{stage}` - Run all jobs in a stage

### **Scheduled Jobs** (if you run step 3)
- 🗞️ **Canada News**: Every 2 hours
- 🏛️ **LEGISinfo Bills**: Every 4 hours  
- 📋 **Orders in Council**: Daily at 6 AM
- 📰 **Canada Gazette**: Daily at 7 AM
- 🔄 **Evidence Processing**: Every 6 hours
- 🔗 **Evidence Linking**: Daily at 10 PM

## 🎛️ Management

### Monitor Your Service
- **Cloud Console**: https://console.cloud.google.com/run
- **Logs**: https://console.cloud.google.com/logs
- **Scheduler**: https://console.cloud.google.com/cloudscheduler

### Update Your Service
```bash
# Redeploy after code changes
./deploy_to_cloud_run.sh

# Scale resources if needed
gcloud run services update promise-tracker-pipeline \
    --memory=4Gi --cpu=4 --region=us-central1
```

## 💰 Cost Estimate

For typical usage (~100 jobs/day):
- **Monthly Cost**: ~$16-45
- **Pay-per-use**: Only charged when jobs are running
- **Auto-scaling**: Scales to zero when idle

## 🆘 Need Help?

1. **Check logs**: `gcloud logging read "resource.type=cloud_run_revision" --limit=20`
2. **Re-run tests**: `./test_cloud_run.sh`
3. **View full guide**: See `CLOUD_RUN_DEPLOYMENT_GUIDE.md`

---

**🎉 That's it!** Your Promise Tracker pipeline is now running on Google Cloud Run with enterprise-grade reliability and automatic scaling. 