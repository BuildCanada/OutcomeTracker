# 🚀 Promise Tracker Pipeline - Cloud Run Quick Start

Get your Promise Tracker pipeline running on Google Cloud Run in 3 simple steps.

## Prerequisites

- Google Cloud account with billing enabled
- `gcloud` CLI installed and authenticated
- Docker installed (for local testing)

## 🚀 Option 1: Manual Deployment (Quick Start)

### Step 1: Deploy the Pipeline
```bash
./deploy_to_cloud_run.sh
```

### Step 2: Test the Deployment
```bash
./test_cloud_run.sh
```

### Step 3: Set Up Scheduling (Optional)
```bash
./setup_cloud_scheduler.sh
```

## 🔄 Option 2: Automatic GitHub Deployment (Recommended)

For automatic deployments when you make code changes:

### Step 1: Set Up GitHub Integration
```bash
export GITHUB_OWNER="your-github-username"
export GITHUB_REPO="promise-tracker"
./setup_github_integration_workload_identity.sh
```

### Step 2: Add GitHub Secrets
Follow the instructions in [GITHUB_INTEGRATION.md](./GITHUB_INTEGRATION.md)

### Step 3: Set Up Scheduling
```bash
./setup_cloud_scheduler.sh
```

**Benefits of GitHub Integration:**
- ✅ Automatic deployment on code changes
- ✅ Version tracking with Git SHA
- ✅ Zero-downtime rolling updates
- ✅ Easy rollback to previous versions
- ✅ Keyless authentication (no service account keys)

## 📊 Monitor Your Pipeline

Access your monitoring dashboard at:
```
https://your-nextjs-app.com/admin/monitoring
```

The dashboard shows:
- Pipeline job status and health
- Recent executions and triggers
- Cloud Run service status
- RSS feed monitoring
- Active alerts

## 🎯 What Happens Next

### Scheduled Jobs (Every Day)
- **Canada News**: Every 2 hours → triggers News Processor → triggers Evidence Linker
- **LEGISinfo Bills**: Every 4 hours → triggers Bill Processor → triggers Evidence Linker  
- **Orders in Council**: Daily 6 AM → triggers OIC Processor → triggers Evidence Linker
- **Canada Gazette**: Daily 7 AM → triggers Gazette Processor → triggers Evidence Linker

### Automatic Trigger Chain
```
Ingestion → Processing → Evidence Linking → Progress Scoring
```

No manual intervention needed - the pipeline runs automatically!

## 🛠️ Manual Job Triggers

You can also trigger jobs manually from your monitoring dashboard or via API:

```bash
# Trigger a specific job
curl -X POST https://your-cloud-run-url/jobs/ingestion/canada_news

# Check job status
curl https://your-cloud-run-url/jobs
```

## 📈 Cost Estimate

**Typical monthly cost: $16-45**
- Cloud Run: $10-30 (based on usage)
- Cloud Scheduler: $0.10 (6 jobs)
- Artifact Registry: $0.10 (storage)
- Cloud Build: $5-15 (deployments)

## 🚨 Troubleshooting

### Deployment Issues
```bash
# Check service status
gcloud run services describe promise-tracker-pipeline --region=us-central1

# View logs
gcloud logs read "resource.type=cloud_run_revision" --limit=50
```

### Job Issues
```bash
# Test individual endpoints
./test_cloud_run.sh

# Check monitoring dashboard
# Visit /admin/monitoring in your Next.js app
```

## 📚 Additional Resources

- [Complete Deployment Guide](./CLOUD_RUN_DEPLOYMENT_GUIDE.md)
- [GitHub Integration Setup](./GITHUB_INTEGRATION.md)
- [Pipeline Architecture](./pipeline/README.md)
- [Monitoring Dashboard](./components/admin/README.md)

## 🎉 You're Done!

Your Promise Tracker pipeline is now running automatically on Google Cloud Run. The system will:

1. **Ingest data** from government sources on schedule
2. **Process** raw data into evidence items automatically  
3. **Link evidence** to promises using AI
4. **Update progress scores** based on new evidence
5. **Log everything** to your monitoring dashboard

Choose **Option 1** for quick manual deployment, or **Option 2** for automatic GitHub-based deployment with continuous integration.

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