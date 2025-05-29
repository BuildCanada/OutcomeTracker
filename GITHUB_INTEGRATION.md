# GitHub Integration for Promise Tracker Pipeline

This guide explains how to set up automatic deployment from GitHub to Google Cloud Run using **Workload Identity Federation** (keyless authentication), so your pipeline jobs stay up-to-date automatically when you make code changes.

## 🎯 Overview

Once set up, the system will:
- ✅ **Automatically deploy** when you push changes to `main`/`master` branch
- ✅ **Only deploy** when relevant files change (pipeline code, Dockerfile, requirements.txt)
- ✅ **Run tests** and health checks before completing deployment
- ✅ **Tag images** with Git SHA for version tracking
- ✅ **Provide deployment status** and rollback capability
- ✅ **Use keyless authentication** (no service account keys needed)

## 🚀 Quick Setup (One-time)

### Step 1: Run the Setup Script

First, you need to specify your GitHub repository details:

```bash
export GITHUB_OWNER="your-github-username"
export GITHUB_REPO="promise-tracker"
./setup_github_integration_workload_identity.sh
```

This will:
- Create a service account for GitHub Actions
- Grant necessary permissions
- Set up Workload Identity Federation (keyless authentication)
- Configure the trust relationship between GitHub and Google Cloud

### Step 2: Add GitHub Secrets

The setup script will provide you with two values to add as GitHub secrets:

1. **Go to your GitHub repository:**
   - Navigate to **Settings** → **Secrets and variables** → **Actions**

2. **Add the first secret:**
   - Click **"New repository secret"**
   - Name: `WIF_PROVIDER`
   - Value: (the provider value from the setup script output)

3. **Add the second secret:**
   - Click **"New repository secret"**
   - Name: `WIF_SERVICE_ACCOUNT`
   - Value: (the service account email from the setup script output)

### Step 3: Test the Integration

1. **Make a small change** to any file in the `pipeline/` directory
2. **Commit and push** to your main branch:
   ```bash
   git add .
   git commit -m "Test automatic deployment with Workload Identity"
   git push origin main
   ```
3. **Check the deployment** in GitHub Actions tab

## 🔄 How It Works

### Workload Identity Federation

Instead of using service account keys (which can be a security risk), this setup uses **Workload Identity Federation**:

- ✅ **No secrets stored** - GitHub authenticates directly with Google Cloud
- ✅ **Temporary credentials** - Each workflow run gets fresh, short-lived tokens
- ✅ **Repository-specific** - Only your specific GitHub repository can deploy
- ✅ **Audit trail** - All authentication is logged and traceable

### Automatic Triggers

The deployment will automatically run when you push changes to:
- `pipeline/**` - Any pipeline code changes
- `Dockerfile` - Container configuration changes  
- `requirements.txt` - Python dependency changes
- `.github/workflows/deploy-cloud-run.yml` - Workflow changes

### Manual Triggers

You can also trigger deployments manually:
1. Go to **Actions** tab in GitHub
2. Select **"Deploy to Cloud Run"** workflow
3. Click **"Run workflow"**

### Deployment Process

1. **Authenticate** - GitHub gets temporary credentials from Google Cloud
2. **Build** - Creates Docker image with your latest code
3. **Push** - Uploads image to Google Artifact Registry
4. **Deploy** - Updates Cloud Run service with new image
5. **Verify** - Runs health checks to ensure deployment succeeded
6. **Report** - Shows deployment status and service URL

## 📊 Monitoring Deployments

### GitHub Actions

- **View logs:** Go to Actions tab → Select workflow run
- **Check status:** Green ✅ = success, Red ❌ = failed
- **See details:** Click on any step to view detailed logs

### Cloud Run Console

- **Service status:** [Cloud Run Console](https://console.cloud.google.com/run)
- **Revision history:** See all deployed versions
- **Traffic allocation:** Control which version receives traffic

### Your Monitoring Dashboard

- **Pipeline status:** Your monitoring dashboard will show the new jobs
- **Job execution:** Triggered jobs will appear in recent activity
- **Version tracking:** Each deployment includes Git SHA in environment

## 🛠️ Advanced Configuration

### Environment Variables

The deployment automatically sets:
- `PYTHONPATH=/app` - Python path configuration
- `ENVIRONMENT=production` - Environment indicator
- `GITHUB_SHA=<commit-sha>` - Git commit for version tracking

### Resource Configuration

Current settings (can be modified in `.github/workflows/deploy-cloud-run.yml`):
- **Memory:** 2Gi
- **CPU:** 2 vCPU
- **Timeout:** 3600 seconds (1 hour)
- **Concurrency:** 10 requests per instance
- **Max instances:** 5

### Customizing Triggers

To change when deployments trigger, edit the `paths` section in the workflow:

```yaml
on:
  push:
    branches: [ main, master ]
    paths:
      - 'pipeline/**'           # Pipeline code
      - 'Dockerfile'            # Container config
      - 'requirements.txt'      # Dependencies
      - 'your-custom-path/**'   # Add custom paths
```

## 🔒 Security Best Practices

### Workload Identity Federation Benefits

- ✅ **No service account keys** - Eliminates key management and rotation
- ✅ **Short-lived tokens** - Credentials expire automatically
- ✅ **Repository-scoped** - Only your specific repo can authenticate
- ✅ **Conditional access** - Can restrict by branch, environment, etc.
- ✅ **Full audit trail** - All authentication events are logged

### Service Account Permissions

The GitHub Actions service account has minimal required permissions:
- `roles/run.admin` - Deploy Cloud Run services
- `roles/artifactregistry.admin` - Push Docker images
- `roles/cloudbuild.builds.editor` - Build images
- `roles/iam.serviceAccountUser` - Act as service accounts
- `roles/storage.admin` - Access build artifacts

## 🚨 Troubleshooting

### Deployment Fails

1. **Check GitHub Actions logs** for specific error
2. **Verify Workload Identity setup** - run setup script again
3. **Check GitHub secrets** - ensure WIF_PROVIDER and WIF_SERVICE_ACCOUNT are set correctly
4. **Validate Dockerfile** - ensure it builds locally

### Authentication Errors

```bash
# Re-run setup to fix Workload Identity configuration
export GITHUB_OWNER="your-username"
export GITHUB_REPO="your-repo"
./setup_github_integration_workload_identity.sh

# Check Workload Identity pools
gcloud iam workload-identity-pools list --location=global
```

### Jobs Not Updating

1. **Check deployment succeeded** in GitHub Actions
2. **Verify Cloud Run service** is running new revision
3. **Check Cloud Scheduler** jobs are pointing to correct service URL
4. **Test manually** with `./test_cloud_run.sh`

### Permission Errors

```bash
# Check service account permissions
gcloud projects get-iam-policy promisetrackerapp --flatten="bindings[].members" --filter="bindings.members:github-actions-deployer"
```

## 📈 Benefits

### For Development
- 🚀 **Instant deployment** - Push code, get live updates
- 🔄 **Consistent process** - Same deployment every time
- 🐛 **Easy rollback** - Revert to previous Git commit
- 📊 **Version tracking** - Know exactly what's deployed
- 🔐 **Keyless security** - No secrets to manage

### For Operations  
- ⚡ **Zero downtime** - Cloud Run handles rolling updates
- 🔍 **Full visibility** - Logs and monitoring for every deployment
- 🛡️ **Enhanced security** - No long-lived credentials
- 📈 **Scalable** - Handles multiple developers and deployments
- 🔒 **Compliance-ready** - Meets enterprise security requirements

## 🎉 You're All Set!

Your Promise Tracker pipeline is now connected to GitHub for automatic deployments using secure, keyless authentication. Every time you improve the code and push to main, your Cloud Run jobs will automatically update to use the latest version.

**Next time you make changes:**
1. Edit pipeline code
2. Commit and push to main
3. Watch GitHub Actions deploy automatically (with keyless auth!)
4. See updated jobs in your monitoring dashboard

The scheduled ingestion jobs will continue running on their schedule, but now they'll always use your latest code improvements with enterprise-grade security! 