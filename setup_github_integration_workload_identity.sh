#!/bin/bash

# Promise Tracker Pipeline - GitHub Integration Setup (Workload Identity)
# This script sets up automatic deployment from GitHub to Cloud Run using Workload Identity Federation

set -e

# Configuration
PROJECT_ID=${PROJECT_ID:-"promisetrackerapp"}
SERVICE_ACCOUNT_NAME="github-actions-deployer"
SERVICE_ACCOUNT_EMAIL="$SERVICE_ACCOUNT_NAME@$PROJECT_ID.iam.gserviceaccount.com"
WORKLOAD_IDENTITY_POOL="github-actions-pool"
WORKLOAD_IDENTITY_PROVIDER="github-actions-provider"

# GitHub repository info (update these for your repo)
GITHUB_OWNER=${GITHUB_OWNER:-"your-github-username"}
GITHUB_REPO=${GITHUB_REPO:-"promise-tracker"}

echo "🔧 Setting up GitHub Actions integration with Workload Identity Federation..."
echo "   Project: $PROJECT_ID"
echo "   GitHub: $GITHUB_OWNER/$GITHUB_REPO"
echo ""

# Set the project
gcloud config set project $PROJECT_ID

# Enable required APIs
echo "🔌 Enabling required APIs..."
gcloud services enable iamcredentials.googleapis.com
gcloud services enable sts.googleapis.com

# Create service account for GitHub Actions (if it doesn't exist)
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
    --role="roles/run.admin" \
    --quiet

# Artifact Registry Admin (to push images)
gcloud projects add-iam-policy-binding $PROJECT_ID \
    --member="serviceAccount:$SERVICE_ACCOUNT_EMAIL" \
    --role="roles/artifactregistry.admin" \
    --quiet

# Cloud Build Editor (to build images)
gcloud projects add-iam-policy-binding $PROJECT_ID \
    --member="serviceAccount:$SERVICE_ACCOUNT_EMAIL" \
    --role="roles/cloudbuild.builds.editor" \
    --quiet

# Service Account User (to act as other service accounts)
gcloud projects add-iam-policy-binding $PROJECT_ID \
    --member="serviceAccount:$SERVICE_ACCOUNT_EMAIL" \
    --role="roles/iam.serviceAccountUser" \
    --quiet

# Storage Admin (for Cloud Build artifacts)
gcloud projects add-iam-policy-binding $PROJECT_ID \
    --member="serviceAccount:$SERVICE_ACCOUNT_EMAIL" \
    --role="roles/storage.admin" \
    --quiet

# Create Workload Identity Pool
echo "🏊 Creating Workload Identity Pool..."
gcloud iam workload-identity-pools create $WORKLOAD_IDENTITY_POOL \
    --location="global" \
    --description="Pool for GitHub Actions" \
    --display-name="GitHub Actions Pool" \
    || echo "Pool already exists"

# Create Workload Identity Provider
echo "🔗 Creating Workload Identity Provider..."
gcloud iam workload-identity-pools providers create-oidc $WORKLOAD_IDENTITY_PROVIDER \
    --location="global" \
    --workload-identity-pool=$WORKLOAD_IDENTITY_POOL \
    --issuer-uri="https://token.actions.githubusercontent.com" \
    --attribute-mapping="google.subject=assertion.sub,attribute.actor=assertion.actor,attribute.repository=assertion.repository,attribute.repository_owner=assertion.repository_owner" \
    --description="Provider for GitHub Actions" \
    --display-name="GitHub Actions Provider" \
    || echo "Provider already exists"

# Get the full provider name
PROVIDER_NAME="projects/$PROJECT_ID/locations/global/workloadIdentityPools/$WORKLOAD_IDENTITY_POOL/providers/$WORKLOAD_IDENTITY_PROVIDER"

# Allow the GitHub repository to impersonate the service account
echo "🤝 Allowing GitHub repository to impersonate service account..."
gcloud iam service-accounts add-iam-policy-binding $SERVICE_ACCOUNT_EMAIL \
    --role="roles/iam.workloadIdentityUser" \
    --member="principalSet://iam.googleapis.com/projects/$PROJECT_ID/locations/global/workloadIdentityPools/$WORKLOAD_IDENTITY_POOL/providers/$WORKLOAD_IDENTITY_PROVIDER/attribute.repository/$GITHUB_OWNER/$GITHUB_REPO"

echo "✅ GitHub Actions Workload Identity setup complete!"
echo ""
echo "📋 Next Steps:"
echo ""
echo "1. 🔐 Add the following secrets to your GitHub repository:"
echo "   Go to: https://github.com/$GITHUB_OWNER/$GITHUB_REPO/settings/secrets/actions"
echo ""
echo "   Secret name: WIF_PROVIDER"
echo "   Secret value: $PROVIDER_NAME"
echo ""
echo "   Secret name: WIF_SERVICE_ACCOUNT"
echo "   Secret value: $SERVICE_ACCOUNT_EMAIL"
echo ""
echo "2. 📁 Update your GitHub workflow file (.github/workflows/deploy-cloud-run.yml)"
echo "   The workflow needs to be updated to use Workload Identity instead of service account keys."
echo ""
echo "3. 🚀 Test the integration:"
echo "   - Make a change to the pipeline code"
echo "   - Push to main/master branch"
echo "   - Check the Actions tab in GitHub to see the deployment"
echo ""
echo "🔄 Automatic deployment will trigger on:"
echo "   - Changes to pipeline/** files"
echo "   - Changes to Dockerfile or requirements.txt"
echo "   - Manual workflow dispatch from GitHub Actions tab"
echo ""
echo "🎉 No service account keys needed - much more secure!" 