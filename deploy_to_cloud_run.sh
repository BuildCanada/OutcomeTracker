#!/bin/bash

# Promise Tracker Pipeline - Cloud Run Deployment Script
# This script builds and deploys the new pipeline orchestrator to Google Cloud Run

set -e

# Configuration
PROJECT_ID=${PROJECT_ID:-"promisetrackerapp"}
SERVICE_NAME=${SERVICE_NAME:-"promise-tracker-pipeline"}
REGION=${REGION:-"us-central1"}
REPOSITORY_NAME=${REPOSITORY_NAME:-"promise-tracker"}
IMAGE_NAME="$REGION-docker.pkg.dev/$PROJECT_ID/$REPOSITORY_NAME/promise-tracker-pipeline"

echo "🚀 Deploying Promise Tracker Pipeline to Cloud Run..."
echo "   Project: $PROJECT_ID"
echo "   Service: $SERVICE_NAME"
echo "   Region: $REGION"
echo "   Repository: $REPOSITORY_NAME"

# Check if gcloud is authenticated
if ! gcloud auth list --filter=status:ACTIVE --format="value(account)" | grep -q .; then
    echo "❌ Error: Not authenticated with gcloud. Run 'gcloud auth login' first."
    exit 1
fi

# Set the project
echo "📋 Setting project to $PROJECT_ID..."
gcloud config set project $PROJECT_ID

# Enable required APIs
echo "🔧 Enabling required APIs..."
gcloud services enable cloudbuild.googleapis.com
gcloud services enable run.googleapis.com
gcloud services enable artifactregistry.googleapis.com

# Create Artifact Registry repository if it doesn't exist
echo "📦 Creating Artifact Registry repository..."
gcloud artifacts repositories create $REPOSITORY_NAME \
    --repository-format=docker \
    --location=$REGION \
    --description="Promise Tracker Pipeline Docker images" \
    2>/dev/null || echo "Repository $REPOSITORY_NAME already exists"

# Configure Docker authentication for Artifact Registry
echo "🔐 Configuring Docker authentication..."
gcloud auth configure-docker $REGION-docker.pkg.dev --quiet

# Build the container image
echo "🏗️  Building container image..."
gcloud builds submit --tag $IMAGE_NAME .

# Deploy to Cloud Run
echo "🚀 Deploying to Cloud Run..."
gcloud run deploy $SERVICE_NAME \
    --image $IMAGE_NAME \
    --platform managed \
    --region $REGION \
    --allow-unauthenticated \
    --memory 2Gi \
    --cpu 2 \
    --timeout 3600 \
    --concurrency 10 \
    --max-instances 5 \
    --set-env-vars "PYTHONPATH=/app" \
    --set-env-vars "ENVIRONMENT=production"

# Get the service URL
SERVICE_URL=$(gcloud run services describe $SERVICE_NAME --platform managed --region $REGION --format 'value(status.url)')

echo "✅ Deployment complete!"
echo "🌐 Service URL: $SERVICE_URL"
echo ""
echo "📋 Test endpoints:"
echo "   Health check: $SERVICE_URL/health"
echo "   Job status:   $SERVICE_URL/jobs/status"
echo "   Run job:      POST $SERVICE_URL/jobs/{stage}/{job_name}"
echo ""
echo "🧪 Test with curl:"
echo "   curl $SERVICE_URL/health"
echo "   curl $SERVICE_URL/jobs/status" 