# Cloud Run Manual Deployment Guide

This guide provides step-by-step instructions to manually create and deploy the RSS monitoring service to Google Cloud Run with proper permissions.

## Prerequisites

- Google Cloud SDK (`gcloud`) installed and authenticated
- Project: `promisetrackerapp`
- Region: `northamerica-northeast2`

## Step 1: Enable Required APIs

```bash
gcloud services enable cloudbuild.googleapis.com \
  run.googleapis.com \
  storage.googleapis.com \
  cloudscheduler.googleapis.com \
  monitoring.googleapis.com \
  artifactregistry.googleapis.com
```

## Step 2: Create Artifact Registry Repository

```bash
# Create repository for Docker images
gcloud artifacts repositories create rss-monitor-repo \
  --repository-format=docker \
  --location=northamerica-northeast2 \
  --description="RSS monitoring service images"
```

## Step 3: Configure IAM Permissions

```bash
# Get your project number
PROJECT_NUMBER=$(gcloud projects describe promisetrackerapp --format="value(projectNumber)")

# Grant necessary permissions to Cloud Build service account
gcloud projects add-iam-policy-binding promisetrackerapp \
  --member="serviceAccount:${PROJECT_NUMBER}@cloudbuild.gserviceaccount.com" \
  --role="roles/run.developer"

gcloud projects add-iam-policy-binding promisetrackerapp \
  --member="serviceAccount:${PROJECT_NUMBER}@cloudbuild.gserviceaccount.com" \
  --role="roles/artifactregistry.writer"

gcloud projects add-iam-policy-binding promisetrackerapp \
  --member="serviceAccount:${PROJECT_NUMBER}@cloudbuild.gserviceaccount.com" \
  --role="roles/storage.admin"

# Grant permissions to Cloud Run service account for Firestore access
gcloud projects add-iam-policy-binding promisetrackerapp \
  --member="serviceAccount:${PROJECT_NUMBER}-compute@developer.gserviceaccount.com" \
  --role="roles/datastore.user"

gcloud projects add-iam-policy-binding promisetrackerapp \
  --member="serviceAccount:${PROJECT_NUMBER}-compute@developer.gserviceaccount.com" \
  --role="roles/firebase.admin"
```

## Step 4: Build and Push Container Image

```bash
# Navigate to your project directory
cd /Users/tscheidt/promise-tracker/PromiseTracker

# Build the image using Cloud Build
gcloud builds submit \
  --tag northamerica-northeast2-docker.pkg.dev/promisetrackerapp/rss-monitor-repo/rss-monitor:latest \
  --region=northamerica-northeast2
```

## Step 5: Deploy to Cloud Run

```bash
# Deploy the service
gcloud run deploy rss-monitor \
  --image northamerica-northeast2-docker.pkg.dev/promisetrackerapp/rss-monitor-repo/rss-monitor:latest \
  --region northamerica-northeast2 \
  --platform managed \
  --memory 2Gi \
  --cpu 1 \
  --timeout 1800 \
  --max-instances 10 \
  --allow-unauthenticated \
  --set-env-vars="FIREBASE_PROJECT_ID=promisetrackerapp"
```

## Step 6: Create Cloud Scheduler Jobs

### RSS Check Job (Every 30 minutes)
```bash
gcloud scheduler jobs create http rss-check-job \
  --location=northamerica-northeast2 \
  --schedule="*/30 * * * *" \
  --uri="https://rss-monitor-[HASH]-nn.a.run.app/rss-check" \
  --http-method=POST \
  --headers="Content-Type=application/json" \
  --message-body='{"hours_threshold": 1, "parliament_filter": 44}' \
  --description="Check RSS feeds for new bills every 30 minutes"
```

### Full Ingestion Job (Daily at 6 AM)
```bash
gcloud scheduler jobs create http full-ingestion-job \
  --location=northamerica-northeast2 \
  --schedule="0 6 * * *" \
  --uri="https://rss-monitor-[HASH]-nn.a.run.app/full-ingestion" \
  --http-method=POST \
  --headers="Content-Type=application/json" \
  --message-body='{"hours_threshold": 24, "parliament_filter": 44, "fallback_full_run": true}' \
  --description="Full bill ingestion daily at 6 AM"
```

### Canada News Job (Daily at 8 AM)
```bash
gcloud scheduler jobs create http canada-news-job \
  --location=northamerica-northeast2 \
  --schedule="0 8 * * *" \
  --uri="https://rss-monitor-[HASH]-nn.a.run.app/canada-news-ingestion" \
  --http-method=POST \
  --headers="Content-Type=application/json" \
  --message-body='{"dry_run": false}' \
  --description="Canada news RSS ingestion daily at 8 AM"
```

**Note:** Replace `[HASH]` with the actual hash from your deployed Cloud Run service URL.

## Step 7: Get Service URL

```bash
# Get the service URL
gcloud run services describe rss-monitor \
  --region=northamerica-northeast2 \
  --format="value(status.url)"
```

## Step 8: Test the Deployment

```bash
# Test health check
curl "https://rss-monitor-[HASH]-nn.a.run.app/"

# Test RSS check endpoint
curl -X POST "https://rss-monitor-[HASH]-nn.a.run.app/rss-check" \
  -H "Content-Type: application/json" \
  -d '{"hours_threshold": 1, "parliament_filter": 44}'

# Test manual trigger
curl -X POST "https://rss-monitor-[HASH]-nn.a.run.app/manual-trigger" \
  -H "Content-Type: application/json" \
  -d '{"action": "rss_check"}'
```

## Step 9: Monitor the Service

```bash
# View logs
gcloud logs read "resource.type=cloud_run_revision AND resource.labels.service_name=rss-monitor" \
  --limit=50 \
  --format="table(timestamp,severity,textPayload)"

# Check service status
gcloud run services describe rss-monitor \
  --region=northamerica-northeast2
```

## Troubleshooting

### Common Issues and Solutions

1. **Build Permission Errors:**
   ```bash
   # Ensure Cloud Build has proper permissions
   gcloud projects add-iam-policy-binding promisetrackerapp \
     --member="serviceAccount:${PROJECT_NUMBER}@cloudbuild.gserviceaccount.com" \
     --role="roles/owner"
   ```

2. **Firestore Access Issues:**
   ```bash
   # Verify service account has Firestore permissions
   gcloud run services update rss-monitor \
     --region=northamerica-northeast2 \
     --service-account="${PROJECT_NUMBER}-compute@developer.gserviceaccount.com"
   ```

3. **Container Not Starting:**
   ```bash
   # Check the logs for startup issues
   gcloud logs read "resource.type=cloud_run_revision" --limit=20
   ```

4. **Memory/Timeout Issues:**
   ```bash
   # Update service configuration
   gcloud run services update rss-monitor \
     --region=northamerica-northeast2 \
     --memory=4Gi \
     --cpu=2 \
     --timeout=3600
   ```

## Service Endpoints

Once deployed, your service will provide these endpoints:

- `GET /` - Health check
- `POST /rss-check` - Trigger RSS feed check
- `POST /full-ingestion` - Trigger full bill ingestion
- `POST /canada-news-ingestion` - Trigger Canada news ingestion
- `POST /manual-trigger` - Manual trigger with action parameter

## Monitoring Integration

The service automatically logs all operations to Firestore collections:
- `rss_feed_monitoring` - Individual check logs
- `rss_feed_metrics` - Daily aggregated metrics
- `rss_feed_alerts` - Alert notifications

View monitoring data in your admin dashboard at:
`http://localhost:3000/admin/monitoring`

## Security Considerations

- Service uses IAM-based authentication
- Firestore access is properly scoped
- No sensitive data in environment variables
- Request/response logging for audit trail

## Scaling Configuration

The service is configured to:
- Scale to 0 when not in use (cost-effective)
- Maximum 10 concurrent instances
- 2GB memory per instance
- 30-minute timeout for long-running operations

## Cost Optimization

- Service scales to zero when idle
- Scheduled jobs only run when needed
- Memory and CPU optimized for workload
- Regional deployment reduces latency and cost 