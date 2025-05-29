#!/bin/bash

# Promise Tracker Pipeline - Cloud Build Trigger Setup
# This script sets up automatic deployment from GitHub using Cloud Build triggers

set -e

# Configuration
PROJECT_ID=${PROJECT_ID:-"promisetrackerapp"}
REPO_OWNER="BuildCanada"
REPO_NAME="PromiseTracker"
TRIGGER_NAME="promise-tracker-auto-deploy"

echo "🔧 Setting up Cloud Build trigger for automatic deployment..."
echo "   Project: $PROJECT_ID"
echo "   GitHub: $REPO_OWNER/$REPO_NAME"
echo ""

# Set the project
gcloud config set project $PROJECT_ID

# Enable required APIs
echo "🔌 Enabling required APIs..."
gcloud services enable cloudbuild.googleapis.com
gcloud services enable run.googleapis.com
gcloud services enable artifactregistry.googleapis.com

# Check if GitHub repository is connected
echo "🔗 Checking GitHub repository connection..."
CONNECTED_REPOS=$(gcloud builds triggers list --format="value(github.name)" 2>/dev/null || echo "")

if [[ $CONNECTED_REPOS == *"$REPO_NAME"* ]]; then
    echo "✅ GitHub repository already connected"
else
    echo "❌ GitHub repository not connected"
    echo ""
    echo "📋 To connect your GitHub repository:"
    echo "1. Go to: https://console.cloud.google.com/cloud-build/triggers"
    echo "2. Click 'Connect Repository'"
    echo "3. Select 'GitHub (Cloud Build GitHub App)'"
    echo "4. Install the app for BuildCanada organization"
    echo "5. Select the PromiseTracker repository"
    echo "6. Click 'Connect'"
    echo ""
    echo "After connecting, run this script again."
    exit 1
fi

# Create the Cloud Build trigger
echo "🚀 Creating Cloud Build trigger..."
gcloud builds triggers create github \
    --repo-name="$REPO_NAME" \
    --repo-owner="$REPO_OWNER" \
    --branch-pattern="^main$" \
    --build-config="PromiseTracker/cloudbuild.yaml" \
    --name="$TRIGGER_NAME" \
    --description="Auto-deploy Promise Tracker Pipeline on main branch changes" \
    --include-logs-with-status \
    || echo "Trigger may already exist"

# Get trigger information
echo "📊 Trigger information:"
gcloud builds triggers describe $TRIGGER_NAME --format="table(
    name,
    github.owner,
    github.name,
    github.push.branch,
    filename,
    disabled
)"

echo ""
echo "✅ Cloud Build trigger setup complete!"
echo ""
echo "🎯 What happens now:"
echo "   • When you push changes to the main branch"
echo "   • Cloud Build will automatically:"
echo "     1. Build the Docker image"
echo "     2. Push to Artifact Registry"
echo "     3. Deploy to Cloud Run"
echo "     4. Run health checks"
echo ""
echo "📊 Monitor builds at:"
echo "   https://console.cloud.google.com/cloud-build/builds"
echo ""
echo "🔧 Trigger management:"
echo "   https://console.cloud.google.com/cloud-build/triggers"
echo ""
echo "🚀 Test the trigger:"
echo "   1. Make a change to pipeline code"
echo "   2. Commit and push to main branch"
echo "   3. Watch the build at the URL above"
echo ""
echo "🎉 Your pipeline will now auto-deploy on every push to main!" 