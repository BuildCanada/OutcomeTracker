#!/bin/bash

# Promise Tracker Pipeline - GitHub Integration Setup
# This script sets up automatic deployment from GitHub to Cloud Run

set -e

# Configuration
PROJECT_ID=${PROJECT_ID:-"promisetrackerapp"}
SERVICE_ACCOUNT_NAME="github-actions-deployer"
SERVICE_ACCOUNT_EMAIL="$SERVICE_ACCOUNT_NAME@$PROJECT_ID.iam.gserviceaccount.com"

echo "🔧 Setting up GitHub Actions integration for Promise Tracker Pipeline..."
echo "   Project: $PROJECT_ID"

# Set the project
gcloud config set project $PROJECT_ID

# Create service account for GitHub Actions
echo "👤 Creating service account for GitHub Actions..."
gcloud iam service-accounts create $SERVICE_ACCOUNT_NAME \
    --display-name="GitHub Actions Deployer" \
    --description="Service account for GitHub Actions to deploy Promise Tracker pipeline" \
    || echo "Service account already exists"

# Grant necessary roles to the service account
echo "🔐 Granting permissions to service account..."

# Cloud Run Admin (to deploy services)
gcloud projects add-iam-policy-binding $PROJECT_ID \
    --member="serviceAccount:$SERVICE_ACCOUNT_EMAIL" \
    --role="roles/run.admin"

# Artifact Registry Admin (to push images)
gcloud projects add-iam-policy-binding $PROJECT_ID \
    --member="serviceAccount:$SERVICE_ACCOUNT_EMAIL" \
    --role="roles/artifactregistry.admin"

# Cloud Build Editor (to build images)
gcloud projects add-iam-policy-binding $PROJECT_ID \
    --member="serviceAccount:$SERVICE_ACCOUNT_EMAIL" \
    --role="roles/cloudbuild.builds.editor"

# Service Account User (to act as other service accounts)
gcloud projects add-iam-policy-binding $PROJECT_ID \
    --member="serviceAccount:$SERVICE_ACCOUNT_EMAIL" \
    --role="roles/iam.serviceAccountUser"

# Storage Admin (for Cloud Build artifacts)
gcloud projects add-iam-policy-binding $PROJECT_ID \
    --member="serviceAccount:$SERVICE_ACCOUNT_EMAIL" \
    --role="roles/storage.admin"

# Create and download service account key
echo "🔑 Creating service account key..."
KEY_FILE="github-actions-key.json"
gcloud iam service-accounts keys create $KEY_FILE \
    --iam-account=$SERVICE_ACCOUNT_EMAIL

echo "✅ GitHub Actions setup complete!"
echo ""
echo "📋 Next Steps:"
echo ""
echo "1. 🔐 Add the following secret to your GitHub repository:"
echo "   Secret name: GCP_SA_KEY"
echo "   Secret value: (contents of $KEY_FILE)"
echo ""
echo "2. 📁 To add the secret:"
echo "   - Go to your GitHub repository"
echo "   - Click Settings → Secrets and variables → Actions"
echo "   - Click 'New repository secret'"
echo "   - Name: GCP_SA_KEY"
echo "   - Value: Copy and paste the entire contents of $KEY_FILE"
echo ""
echo "3. 🗑️  After adding the secret, delete the key file for security:"
echo "   rm $KEY_FILE"
echo ""
echo "4. 🚀 Test the integration:"
echo "   - Make a change to the pipeline code"
echo "   - Push to main/master branch"
echo "   - Check the Actions tab in GitHub to see the deployment"
echo ""
echo "📄 Service account key file created: $KEY_FILE"
echo "⚠️  IMPORTANT: Keep this file secure and delete it after adding to GitHub!"
echo ""
echo "🔄 Automatic deployment will trigger on:"
echo "   - Changes to pipeline/** files"
echo "   - Changes to Dockerfile or requirements.txt"
echo "   - Manual workflow dispatch from GitHub Actions tab" 