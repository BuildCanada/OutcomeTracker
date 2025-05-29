# Alternative Deployment Approaches for Promise Tracker Pipeline

Since your organization has security policies that prevent service account key creation and we're encountering issues with Workload Identity Federation setup, here are alternative approaches to keep your pipeline updated:

## 🎯 Current Situation

- ✅ **Manual deployment works** - `./deploy_to_cloud_run.sh` successfully deploys
- ✅ **Cloud Run service is running** - Your pipeline is operational
- ✅ **Scheduled jobs are working** - Ingestion runs automatically
- ❌ **GitHub integration blocked** - Organization security policies prevent keyless auth setup

## 🚀 Recommended Approaches

### Option 1: Manual Deployment (Current Working Solution)

**When to use:** For immediate updates and testing

```bash
# Deploy latest changes
./deploy_to_cloud_run.sh

# Test the deployment
./test_cloud_run.sh
```

**Pros:**
- ✅ Works immediately
- ✅ Full control over deployments
- ✅ No security policy conflicts

**Cons:**
- ❌ Manual process
- ❌ Requires local gcloud setup

### Option 2: Cloud Build Triggers (Recommended)

**Setup Cloud Build to automatically deploy from GitHub:**

```bash
# Create a Cloud Build trigger
gcloud builds triggers create github \
    --repo-name="PromiseTracker" \
    --repo-owner="BuildCanada" \
    --branch-pattern="^main$" \
    --build-config="cloudbuild.yaml"
```

**Create `cloudbuild.yaml` in your repo root:**

```yaml
steps:
  # Build the container image
  - name: 'gcr.io/cloud-builders/docker'
    args: ['build', '-t', 'us-central1-docker.pkg.dev/promisetrackerapp/promise-tracker/promise-tracker-pipeline:$COMMIT_SHA', '.']
  
  # Push the container image to Artifact Registry
  - name: 'gcr.io/cloud-builders/docker'
    args: ['push', 'us-central1-docker.pkg.dev/promisetrackerapp/promise-tracker/promise-tracker-pipeline:$COMMIT_SHA']
  
  # Deploy container image to Cloud Run
  - name: 'gcr.io/google.com/cloudsdktool/cloud-sdk'
    entrypoint: gcloud
    args:
    - 'run'
    - 'deploy'
    - 'promise-tracker-pipeline'
    - '--image'
    - 'us-central1-docker.pkg.dev/promisetrackerapp/promise-tracker/promise-tracker-pipeline:$COMMIT_SHA'
    - '--region'
    - 'us-central1'
    - '--platform'
    - 'managed'
    - '--allow-unauthenticated'

options:
  logging: CLOUD_LOGGING_ONLY
```

**Pros:**
- ✅ Automatic deployment on push to main
- ✅ Uses Google Cloud's native build system
- ✅ No external authentication needed
- ✅ Works with organization security policies

**Cons:**
- ❌ Requires GitHub app installation (one-time setup)

### Option 3: Scheduled Deployment

**Set up a Cloud Scheduler job to redeploy periodically:**

```bash
# Create a scheduled deployment job (daily at 2 AM)
gcloud scheduler jobs create http redeploy-pipeline \
    --schedule="0 2 * * *" \
    --uri="https://cloudbuild.googleapis.com/v1/projects/promisetrackerapp/triggers/YOUR_TRIGGER_ID:run" \
    --http-method=POST \
    --headers="Content-Type=application/json" \
    --message-body='{"branchName":"main"}'
```

**Pros:**
- ✅ Automatic updates
- ✅ No manual intervention
- ✅ Works with existing security policies

**Cons:**
- ❌ Not immediate (scheduled)
- ❌ May deploy unnecessary updates

## 🛠️ Quick Setup for Cloud Build Triggers

### Step 1: Connect GitHub Repository

```bash
# List available repositories (first time setup)
gcloud builds triggers list

# If no repos connected, go to Cloud Console:
# https://console.cloud.google.com/cloud-build/triggers
# Click "Connect Repository" and follow the GitHub app installation
```

### Step 2: Create the Trigger

```bash
# Create trigger for automatic deployment
gcloud builds triggers create github \
    --repo-name="PromiseTracker" \
    --repo-owner="BuildCanada" \
    --branch-pattern="^main$" \
    --build-config="cloudbuild.yaml" \
    --description="Auto-deploy Promise Tracker Pipeline"
```

### Step 3: Test the Trigger

```bash
# Manually run the trigger
gcloud builds triggers run YOUR_TRIGGER_NAME --branch=main
```

## 📊 Comparison

| Approach | Automation | Security | Setup Complexity | Immediate Updates |
|----------|------------|----------|------------------|-------------------|
| Manual | ❌ | ✅ | ⭐ | ✅ |
| Cloud Build | ✅ | ✅ | ⭐⭐ | ✅ |
| Scheduled | ✅ | ✅ | ⭐⭐⭐ | ❌ |

## 🎯 Recommendation

**Use Cloud Build Triggers (Option 2)** because:

1. **Automatic deployment** - Push to main = automatic deployment
2. **Security compliant** - Uses Google Cloud's native authentication
3. **Simple setup** - One-time configuration
4. **Immediate updates** - Deploys within minutes of push
5. **Full logging** - Complete build and deployment logs

## 🚀 Next Steps

1. **Immediate:** Continue using manual deployment for urgent updates
2. **This week:** Set up Cloud Build triggers for automatic deployment
3. **Optional:** Add scheduled deployment as backup

Would you like me to help you set up the Cloud Build trigger approach?

## 🔧 Troubleshooting

### If Cloud Build Fails

```bash
# Check build logs
gcloud builds log YOUR_BUILD_ID

# Check Cloud Run deployment
gcloud run services describe promise-tracker-pipeline --region=us-central1
```

### If GitHub Connection Fails

1. Go to [Cloud Build Console](https://console.cloud.google.com/cloud-build/triggers)
2. Click "Connect Repository"
3. Install GitHub app for BuildCanada organization
4. Select PromiseTracker repository

This approach will give you automatic deployment without the complexity of Workload Identity Federation! 