#!/bin/bash

# Promise Tracker Pipeline - Cloud Scheduler Setup
# This script creates Cloud Scheduler jobs for automated pipeline execution

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

# Create Cloud Scheduler jobs
echo "📅 Creating scheduled jobs..."

# 1. Canada News Ingestion - Every 2 hours
gcloud scheduler jobs create http canada-news-ingestion \
    --schedule="0 */2 * * *" \
    --uri="$SERVICE_URL/jobs/ingestion/canada_news" \
    --http-method=POST \
    --oidc-service-account-email="promise-tracker-scheduler@$PROJECT_ID.iam.gserviceaccount.com" \
    --location=$SCHEDULER_REGION \
    --description="Ingest Canada News every 2 hours" \
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
    --description="Ingest LEGISinfo Bills every 4 hours" \
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
    --description="Ingest Orders in Council daily at 6 AM" \
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
    --description="Ingest Canada Gazette daily at 7 AM" \
    --headers="Content-Type=application/json" \
    --message-body='{"config": {"max_items": 20}}' \
    || echo "Job canada-gazette-ingestion already exists"

# 5. Processing Jobs - Every 6 hours
gcloud scheduler jobs create http evidence-processing \
    --schedule="0 */6 * * *" \
    --uri="$SERVICE_URL/jobs/batch/processing" \
    --http-method=POST \
    --oidc-service-account-email="promise-tracker-scheduler@$PROJECT_ID.iam.gserviceaccount.com" \
    --location=$SCHEDULER_REGION \
    --description="Process raw data to evidence items every 6 hours" \
    --headers="Content-Type=application/json" \
    --message-body='{"config": {"max_items_per_job": 50}}' \
    || echo "Job evidence-processing already exists"

# 6. Evidence Linking - Daily at 10 PM
gcloud scheduler jobs create http evidence-linking \
    --schedule="0 22 * * *" \
    --uri="$SERVICE_URL/jobs/linking/evidence_linker" \
    --http-method=POST \
    --oidc-service-account-email="promise-tracker-scheduler@$PROJECT_ID.iam.gserviceaccount.com" \
    --location=$SCHEDULER_REGION \
    --description="Link evidence to promises daily at 10 PM" \
    --headers="Content-Type=application/json" \
    --message-body='{"config": {"max_items": 100}}' \
    || echo "Job evidence-linking already exists"

echo "✅ Cloud Scheduler setup complete!"
echo ""
echo "📅 Scheduled Jobs Created:"
echo "   🗞️  Canada News:        Every 2 hours"
echo "   🏛️  LEGISinfo Bills:    Every 4 hours"
echo "   📋 Orders in Council:   Daily at 6 AM"
echo "   📰 Canada Gazette:      Daily at 7 AM"
echo "   🔄 Evidence Processing: Every 6 hours"
echo "   🔗 Evidence Linking:    Daily at 10 PM"
echo ""
echo "🎛️  Manage jobs at: https://console.cloud.google.com/cloudscheduler?project=$PROJECT_ID" 