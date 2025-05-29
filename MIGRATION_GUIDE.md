# Promise Tracker Pipeline Migration Guide

This guide walks you through the safe migration from the existing script-based system to the new class-based pipeline architecture.

## Overview

The migration process is designed to be **safe, reversible, and gradual**. It includes:

- ✅ **Comprehensive testing** before any changes
- 🔄 **Automatic backups** with rollback capability  
- 🧪 **Dry-run mode** for validation
- 📊 **Progress tracking** and status monitoring
- 🔒 **Dependency management** to ensure proper order

## Prerequisites

1. **Python Environment**: Ensure you have the virtual environment activated
2. **Firebase Access**: Verify Firebase credentials are configured
3. **Backup Space**: Ensure sufficient disk space for backups
4. **Testing Data**: Have some test data available for validation

## Migration Steps

### Phase 1: Testing (Recommended First Step)

Before making any changes, test the new pipeline against the old scripts:

```bash
# Navigate to the pipeline testing directory
cd PromiseTracker/pipeline/testing

# Run comprehensive tests (dry-run mode)
python run_migration.py --test-only --verbose

# Review test results
cat migration_test_results_*.json
```

**Expected Output:**
```
🧪 Running migration tests...

📊 Test Results Summary:
   Total Tests: 8
   Passed: 8
   Failed: 0
   Success Rate: 100.0%
   Results saved to: migration_test_results_20250127_143022.json

✅ All tests passed!
```

### Phase 2: Dry-Run Migration

Simulate the migration without making actual changes:

```bash
# Run migration in dry-run mode
python run_migration.py --migrate --dry-run --verbose

# Check what would be changed
python run_migration.py --status
```

### Phase 3: Backup and Migrate

Perform the actual migration with automatic backups:

```bash
# Run full migration with backups
python run_migration.py --migrate --verbose

# Monitor progress
python run_migration.py --status
```

### Phase 4: Validation

After migration, validate the new system:

```bash
# Test the new orchestrator
cd ../../
python -m pipeline.orchestrator

# Test individual jobs
curl -X POST http://localhost:8080/jobs/ingestion/canada_news
curl -X POST http://localhost:8080/jobs/processing/canada_news_processor
```

## Migration Commands Reference

### Basic Commands

```bash
# Show current migration status
python run_migration.py --status

# Run tests only
python run_migration.py --test-only

# Run migration with dry-run
python run_migration.py --migrate --dry-run

# Run full migration
python run_migration.py --migrate

# Rollback to previous state
python run_migration.py --rollback
```

### Advanced Options

```bash
# Skip testing requirements (not recommended)
python run_migration.py --migrate --no-tests

# Skip backups (not recommended)
python run_migration.py --migrate --no-backups

# Limit test items for faster testing
python run_migration.py --test-only --max-test-items 3

# Use custom configuration
python run_migration.py --migrate --config migration_config.json

# Verbose logging
python run_migration.py --migrate --verbose
```

## Migration Process Details

### Step-by-Step Breakdown

1. **backup_existing_system**
   - Creates timestamped backup of all existing scripts
   - Backs up `cloud_run_main.py`, `cloudbuild.yaml`
   - Stores backup metadata for rollback

2. **test_ingestion_jobs**
   - Tests new ingestion jobs against old scripts
   - Compares output and success rates
   - Requires 80% test success to proceed

3. **migrate_ingestion_jobs**
   - Renames old ingestion scripts to `.deprecated`
   - Activates new ingestion pipeline jobs

4. **test_processing_jobs**
   - Tests new processing jobs against old scripts
   - Validates evidence item creation

5. **migrate_processing_jobs**
   - Renames old processing scripts to `.deprecated`
   - Activates new processing pipeline jobs

6. **migrate_orchestration**
   - Replaces `cloud_run_main.py` with new orchestrator
   - Updates Cloud Run configuration

7. **test_linking_jobs**
   - Tests new linking and scoring jobs
   - Validates promise progress calculations

8. **migrate_linking_jobs**
   - Replaces old linking scripts
   - Activates new linking pipeline jobs

9. **cleanup_deprecated_scripts**
   - Removes deprecated script files
   - Cleans up old directories

### Safety Features

- **Automatic Backups**: All files backed up before changes
- **Dependency Checking**: Steps only run when dependencies are met
- **Test Requirements**: 80% test success required to proceed
- **Rollback Capability**: Can restore from any backup
- **Progress Persistence**: Migration state saved between runs

## Troubleshooting

### Common Issues

**Tests Failing**
```bash
# Check test details
python run_migration.py --test-only --verbose

# Review specific test failures
cat migration_test_results_*.json | jq '.failed_tests'
```

**Migration Stuck**
```bash
# Check current status
python run_migration.py --status

# Review migration logs
tail -f migration.log
```

**Need to Rollback**
```bash
# Rollback to previous state
python run_migration.py --rollback --verbose

# Verify rollback success
python run_migration.py --status
```

### Error Recovery

If migration fails partway through:

1. **Check the logs**: `tail -f migration.log`
2. **Review status**: `python run_migration.py --status`
3. **Fix the issue** (e.g., missing dependencies, permissions)
4. **Resume migration**: `python run_migration.py --migrate`
5. **Or rollback**: `python run_migration.py --rollback`

## Post-Migration Tasks

### 1. Update Cloud Run Deployment

Update your `cloudbuild.yaml` to use the new orchestrator:

```yaml
steps:
  - name: 'gcr.io/cloud-builders/docker'
    args: ['build', '-t', 'gcr.io/$PROJECT_ID/promise-tracker-pipeline', '.']
  - name: 'gcr.io/cloud-builders/docker'
    args: ['push', 'gcr.io/$PROJECT_ID/promise-tracker-pipeline']
  - name: 'gcr.io/cloud-builders/gcloud'
    args: [
      'run', 'deploy', 'promise-tracker-pipeline',
      '--image', 'gcr.io/$PROJECT_ID/promise-tracker-pipeline',
      '--platform', 'managed',
      '--region', 'us-central1',
      '--allow-unauthenticated'
    ]
```

### 2. Update Dockerfile

Ensure your Dockerfile uses the new orchestrator:

```dockerfile
# Set the new entry point
CMD ["python", "-m", "pipeline.orchestrator"]
```

### 3. Test New Endpoints

```bash
# Health check
curl https://your-cloud-run-url/

# List available jobs
curl https://your-cloud-run-url/jobs

# Execute a job
curl -X POST https://your-cloud-run-url/jobs/ingestion/canada_news

# Check pipeline status
curl https://your-cloud-run-url/pipeline/status
```

### 4. Update Monitoring and Alerts

Update any monitoring dashboards or alerts to use the new API endpoints and job names.

### 5. Clean Up (Optional)

After confirming everything works:

```bash
# Remove backup files (optional)
rm -rf migration_backups/

# Remove migration state
rm migration_state.json

# Remove test results
rm migration_test_results_*.json
```

## Configuration Options

### Migration Configuration File

Create `migration_config.json` for custom settings:

```json
{
  "dry_run": false,
  "require_tests": true,
  "create_backups": true,
  "testing": {
    "dry_run": true,
    "max_items_per_test": 5,
    "compare_content": true,
    "compare_metadata": true
  }
}
```

### Environment Variables

Set these environment variables if needed:

```bash
export MIGRATION_DRY_RUN=false
export MIGRATION_REQUIRE_TESTS=true
export MIGRATION_CREATE_BACKUPS=true
export MIGRATION_MAX_TEST_ITEMS=5
```

## Best Practices

1. **Always test first**: Run `--test-only` before migration
2. **Use dry-run**: Validate with `--dry-run` before actual migration
3. **Monitor progress**: Check status regularly during migration
4. **Keep backups**: Don't disable backups unless absolutely necessary
5. **Validate thoroughly**: Test the new system extensively after migration
6. **Have a rollback plan**: Know how to rollback if issues arise

## Support

If you encounter issues during migration:

1. **Check the logs**: `migration.log` contains detailed information
2. **Review test results**: Test output files show specific failures
3. **Use verbose mode**: Add `--verbose` for more detailed output
4. **Check status**: `--status` shows current migration state

## Success Criteria

Migration is successful when:

- ✅ All tests pass (80%+ success rate)
- ✅ New orchestrator responds to health checks
- ✅ Individual jobs execute successfully
- ✅ Data processing produces expected results
- ✅ No errors in application logs
- ✅ Cloud Run deployment works correctly

## Timeline Estimate

- **Testing Phase**: 30-60 minutes
- **Dry-Run Validation**: 15-30 minutes  
- **Actual Migration**: 45-90 minutes
- **Post-Migration Validation**: 30-60 minutes
- **Total**: 2-4 hours (depending on data volume and testing thoroughness)

Remember: **Take your time and validate each step**. The migration tools are designed to be safe and reversible, so there's no rush to complete everything at once. 