# Promise Tracker Pipeline - Google Cloud Run Deployment Guide

This guide walks you through deploying your migrated Promise Tracker pipeline to Google Cloud Run for production use.

## 🚀 Quick Start

### Prerequisites

1. **Google Cloud SDK installed and authenticated**
   ```bash
   # Install gcloud CLI (if not already installed)
   curl https://sdk.cloud.google.com | bash
   exec -l $SHELL
   
   # Authenticate
   gcloud auth login
   gcloud auth application-default login
   ```

2. **Set your project ID**
   ```bash
   export PROJECT_ID="your-project-id"
   gcloud config set project $PROJECT_ID
   ```

3. **Enable billing** on your Google Cloud project

### Step-by-Step Deployment

#### 1. Deploy to Cloud Run
```bash
./deploy_to_cloud_run.sh
```

This script will:
- Enable required APIs (Cloud Build, Cloud Run, Container Registry)
- Build your container image using Cloud Build
- Deploy to Cloud Run with optimized settings
- Output the service URL for testing

#### 2. Test the Deployment
```bash
./test_cloud_run.sh
```

This will run comprehensive tests including:
- Health check endpoint
- Job status endpoint
- Sample ingestion jobs
- Batch processing
- Service logs review

#### 3. Set Up Automated Scheduling (Optional)
```bash
./setup_cloud_scheduler.sh
```

This creates Cloud Scheduler jobs for:
- **Canada News**: Every 2 hours
- **LEGISinfo Bills**: Every 4 hours  
- **Orders in Council**: Daily at 6 AM
- **Canada Gazette**: Daily at 7 AM
- **Evidence Processing**: Every 6 hours
- **Evidence Linking**: Daily at 10 PM

## 📋 Manual Deployment Steps

If you prefer manual control, here are the individual steps:

### 1. Build Container Image
```bash
gcloud builds submit --tag gcr.io/$PROJECT_ID/promise-tracker-pipeline .
```

### 2. Deploy to Cloud Run
```bash
gcloud run deploy promise-tracker-pipeline \
    --image gcr.io/$PROJECT_ID/promise-tracker-pipeline \
    --platform managed \
    --region us-central1 \
    --allow-unauthenticated \
    --memory 2Gi \
    --cpu 2 \
    --timeout 3600 \
    --concurrency 10 \
    --max-instances 5 \
    --set-env-vars "PYTHONPATH=/app,ENVIRONMENT=production"
```

### 3. Get Service URL
```bash
SERVICE_URL=$(gcloud run services describe promise-tracker-pipeline \
    --platform managed --region us-central1 \
    --format 'value(status.url)')
echo "Service URL: $SERVICE_URL"
```

## 🧪 Testing Your Deployment

### Health Check
```bash
curl $SERVICE_URL/health
```
Expected response: `{"status": "healthy", "timestamp": "..."}`

### Job Status
```bash
curl $SERVICE_URL/jobs/status
```
Expected response: JSON with current job statuses

### Run a Test Job
```bash
curl -X POST \
  -H "Content-Type: application/json" \
  -d '{"config": {"dry_run": true, "max_items": 1}}' \
  $SERVICE_URL/jobs/ingestion/canada_news
```

### Batch Processing Test
```bash
curl -X POST \
  -H "Content-Type: application/json" \
  -d '{"config": {"dry_run": true, "max_items_per_job": 1}}' \
  $SERVICE_URL/jobs/batch/processing
```

## 📊 Monitoring and Logging

### View Logs
```bash
gcloud logging read "resource.type=cloud_run_revision AND resource.labels.service_name=promise-tracker-pipeline" \
    --limit=50 \
    --format="table(timestamp,severity,textPayload)"
```

### Monitor in Console
- **Service Overview**: https://console.cloud.google.com/run/detail/us-central1/promise-tracker-pipeline
- **Logs**: https://console.cloud.google.com/logs/query
- **Metrics**: https://console.cloud.google.com/monitoring

### Set Up Alerts (Recommended)
```bash
# Create alerting policy for errors
gcloud alpha monitoring policies create --policy-from-file=monitoring-policy.yaml
```

## 🔧 Configuration

### Environment Variables
The service uses these environment variables:
- `PYTHONPATH=/app` - Python module path
- `ENVIRONMENT=production` - Runtime environment
- `PORT=8080` - Service port (set by Cloud Run)

### Resource Limits
- **Memory**: 2Gi (adjustable based on workload)
- **CPU**: 2 vCPU (adjustable based on workload)
- **Timeout**: 3600s (1 hour for long-running jobs)
- **Concurrency**: 10 (number of concurrent requests)
- **Max Instances**: 5 (auto-scaling limit)

### Scaling Configuration
```bash
# Update scaling settings
gcloud run services update promise-tracker-pipeline \
    --min-instances=1 \
    --max-instances=10 \
    --concurrency=20 \
    --region=us-central1
```

## 🔐 Security

### Service Account (Recommended)
Create a dedicated service account:
```bash
gcloud iam service-accounts create promise-tracker-service \
    --display-name="Promise Tracker Service Account"

# Grant necessary permissions
gcloud projects add-iam-policy-binding $PROJECT_ID \
    --member="serviceAccount:promise-tracker-service@$PROJECT_ID.iam.gserviceaccount.com" \
    --role="roles/cloudsql.client"

# Update service to use service account
gcloud run services update promise-tracker-pipeline \
    --service-account=promise-tracker-service@$PROJECT_ID.iam.gserviceaccount.com \
    --region=us-central1
```

### Authentication
For production, consider enabling authentication:
```bash
gcloud run services update promise-tracker-pipeline \
    --no-allow-unauthenticated \
    --region=us-central1
```

## 🚨 Troubleshooting

### Common Issues

#### 1. Build Failures
```bash
# Check build logs
gcloud builds log $(gcloud builds list --limit=1 --format="value(id)")
```

#### 2. Service Won't Start
```bash
# Check service logs
gcloud logging read "resource.type=cloud_run_revision" --limit=20
```

#### 3. Memory/CPU Issues
```bash
# Increase resources
gcloud run services update promise-tracker-pipeline \
    --memory=4Gi \
    --cpu=4 \
    --region=us-central1
```

#### 4. Timeout Issues
```bash
# Increase timeout
gcloud run services update promise-tracker-pipeline \
    --timeout=3600 \
    --region=us-central1
```

### Debug Mode
Enable verbose logging:
```bash
gcloud run services update promise-tracker-pipeline \
    --set-env-vars="LOG_LEVEL=DEBUG" \
    --region=us-central1
```

## 💰 Cost Optimization

### Pricing Factors
- **CPU allocation**: Billed per vCPU-second
- **Memory allocation**: Billed per GiB-second  
- **Requests**: Billed per million requests
- **Networking**: Egress charges apply

### Optimization Tips
1. **Right-size resources** based on actual usage
2. **Use min-instances=0** for cost savings (cold starts acceptable)
3. **Optimize container image size** for faster deployments
4. **Monitor usage** with Cloud Monitoring

### Estimated Costs
For typical usage (assuming 100 jobs/day):
- **Compute**: ~$10-30/month
- **Storage**: ~$5-10/month  
- **Networking**: ~$1-5/month
- **Total**: ~$16-45/month

## 🔄 CI/CD Integration

### GitHub Actions Example
```yaml
name: Deploy to Cloud Run
on:
  push:
    branches: [main]
jobs:
  deploy:
    runs-on: ubuntu-latest
    steps:
    - uses: actions/checkout@v2
    - uses: google-github-actions/setup-gcloud@v0
      with:
        service_account_key: ${{ secrets.GCP_SA_KEY }}
        project_id: ${{ secrets.GCP_PROJECT_ID }}
    - run: gcloud builds submit --tag gcr.io/${{ secrets.GCP_PROJECT_ID }}/promise-tracker-pipeline
    - run: gcloud run deploy promise-tracker-pipeline --image gcr.io/${{ secrets.GCP_PROJECT_ID }}/promise-tracker-pipeline --region us-central1
```

## 📚 Additional Resources

- [Cloud Run Documentation](https://cloud.google.com/run/docs)
- [Cloud Scheduler Documentation](https://cloud.google.com/scheduler/docs)
- [Cloud Build Documentation](https://cloud.google.com/build/docs)
- [Cloud Monitoring Documentation](https://cloud.google.com/monitoring/docs)

## 🆘 Support

If you encounter issues:
1. Check the troubleshooting section above
2. Review service logs in Cloud Console
3. Test locally with the migration testing tools
4. Check Cloud Run service status and metrics

---

**Next Steps**: After successful deployment, consider setting up monitoring alerts, backup strategies, and disaster recovery procedures for production use. 