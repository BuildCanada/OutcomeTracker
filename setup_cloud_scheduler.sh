#!/bin/bash

# Promise Tracker Pipeline - Cloud Scheduler Setup
# This script creates Cloud Scheduler jobs for automated pipeline execution
# Note: Only ingestion jobs are scheduled - processing and linking are triggered automatically

set -e

# Configuration
PROJECT_ID=${PROJECT_ID:-"promisetrackerapp"}
SERVICE_NAME=${SERVICE_NAME:-"promise-tracker-pipeline"}
REGION=${REGION:-"us-central1"}
SCHEDULER_REGION=${SCHEDULER_REGION:-"us-central1"}

echo "⏰ Setting up Cloud Scheduler for Promise Tracker Pipeline..."

# Get the Cloud Run service URL
SERVICE_URL=$(gcloud run services describe $SERVICE_NAME --platform managed --region $REGION --format 'value(status.url)')

if [ -z "$SERVICE_URL" ]; then
    echo "❌ Error: Could not find Cloud Run service $SERVICE_NAME in region $REGION"
    echo "   Make sure you've deployed the service first with ./deploy_to_cloud_run.sh"
    exit 1
fi

echo "🌐 Service URL: $SERVICE_URL"

# Enable Cloud Scheduler API
echo "🔧 Enabling Cloud Scheduler API..."
gcloud services enable cloudscheduler.googleapis.com

# Create service account for Cloud Scheduler
echo "👤 Creating service account for Cloud Scheduler..."
gcloud iam service-accounts create promise-tracker-scheduler \
    --display-name="Promise Tracker Scheduler" \
    --description="Service account for Cloud Scheduler to invoke Promise Tracker pipeline" \
    || echo "Service account already exists"

# Grant Cloud Run Invoker role to the service account
echo "🔐 Granting permissions..."
gcloud run services add-iam-policy-binding $SERVICE_NAME \
    --member="serviceAccount:promise-tracker-scheduler@$PROJECT_ID.iam.gserviceaccount.com" \
    --role="roles/run.invoker" \
    --region=$REGION

# Delete any existing processing/linking scheduled jobs (these should be triggered, not scheduled)
echo "🧹 Cleaning up old scheduled processing/linking jobs..."
gcloud scheduler jobs delete evidence-processing --location=$SCHEDULER_REGION --quiet || echo "evidence-processing job doesn't exist"
gcloud scheduler jobs delete evidence-linking --location=$SCHEDULER_REGION --quiet || echo "evidence-linking job doesn't exist"

# Create Cloud Scheduler jobs - ONLY FOR INGESTION
echo "📅 Creating scheduled ingestion jobs..."
echo "ℹ️  Note: Processing and linking jobs will be triggered automatically by ingestion"

# 1. Canada News Ingestion - Every 2 hours
gcloud scheduler jobs create http canada-news-ingestion \
    --schedule="0 */2 * * *" \
    --uri="$SERVICE_URL/jobs/ingestion/canada_news" \
    --http-method=POST \
    --oidc-service-account-email="promise-tracker-scheduler@$PROJECT_ID.iam.gserviceaccount.com" \
    --location=$SCHEDULER_REGION \
    --description="Ingest Canada News every 2 hours (triggers processing automatically)" \
    --headers="Content-Type=application/json" \
    --message-body='{"config": {"max_items": 100}}' \
    || echo "Job canada-news-ingestion already exists"

# 2. LEGISinfo Bills - Every 4 hours
gcloud scheduler jobs create http legisinfo-bills-ingestion \
    --schedule="0 */4 * * *" \
    --uri="$SERVICE_URL/jobs/ingestion/legisinfo_bills" \
    --http-method=POST \
    --oidc-service-account-email="promise-tracker-scheduler@$PROJECT_ID.iam.gserviceaccount.com" \
    --location=$SCHEDULER_REGION \
    --description="Ingest LEGISinfo Bills every 4 hours (triggers processing automatically)" \
    --headers="Content-Type=application/json" \
    --message-body='{"config": {"max_items": 50}}' \
    || echo "Job legisinfo-bills-ingestion already exists"

# 3. Orders in Council - Daily at 6 AM
gcloud scheduler jobs create http orders-in-council-ingestion \
    --schedule="0 6 * * *" \
    --uri="$SERVICE_URL/jobs/ingestion/orders_in_council" \
    --http-method=POST \
    --oidc-service-account-email="promise-tracker-scheduler@$PROJECT_ID.iam.gserviceaccount.com" \
    --location=$SCHEDULER_REGION \
    --description="Ingest Orders in Council daily at 6 AM (triggers processing automatically)" \
    --headers="Content-Type=application/json" \
    --message-body='{"config": {"max_items": 25}}' \
    || echo "Job orders-in-council-ingestion already exists"

# 4. Canada Gazette - Daily at 7 AM
gcloud scheduler jobs create http canada-gazette-ingestion \
    --schedule="0 7 * * *" \
    --uri="$SERVICE_URL/jobs/ingestion/canada_gazette" \
    --http-method=POST \
    --oidc-service-account-email="promise-tracker-scheduler@$PROJECT_ID.iam.gserviceaccount.com" \
    --location=$SCHEDULER_REGION \
    --description="Ingest Canada Gazette daily at 7 AM (triggers processing automatically)" \
    --headers="Content-Type=application/json" \
    --message-body='{"config": {"max_items": 20}}' \
    || echo "Job canada-gazette-ingestion already exists"

echo "✅ Cloud Scheduler setup complete!"
echo ""
echo "📅 Scheduled Jobs Created (Ingestion Only):"
echo "   🗞️  Canada News:        Every 2 hours"
echo "   🏛️  LEGISinfo Bills:    Every 4 hours"
echo "   📋 Orders in Council:   Daily at 6 AM"
echo "   📰 Canada Gazette:      Daily at 7 AM"
echo ""
echo "🔄 Automatic Trigger Flow:"
echo "   Ingestion → Processing → Evidence Linking → Progress Scoring"
echo "   (No manual scheduling needed for processing/linking)"
echo ""
echo "🎛️  Manage jobs at: https://console.cloud.google.com/cloudscheduler?project=$PROJECT_ID" 