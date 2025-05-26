# Promise Tracker Scheduling Configuration Summary

## Overview
The Promise Tracker scheduling system has been cleaned up and optimized for efficient, responsive data ingestion and processing.

## Current Schedule Configuration

### RSS Monitoring Jobs (Frequent, with Conditional Processing)

#### 1. LegisInfo RSS Monitoring
- **Schedule**: Every hour (`0 * * * *`)
- **Job**: `pt-rss_monitoring-check-legisinfo-rss`
- **Function**: Checks LegisInfo RSS feed for bill updates
- **Processing**: Automatically triggers bill ingestion + processing when updates found
- **Endpoint**: `/jobs/check_legisinfo_rss/with-processing`

#### 2. Canada News RSS Monitoring  
- **Schedule**: Every 30 minutes (`*/30 * * * *`)
- **Job**: `pt-rss_monitoring-ingest-canada-news`
- **Function**: Ingests Canada News RSS feed
- **Processing**: Automatically triggers news processing when new items found
- **Endpoint**: `/jobs/ingest_canada_news/with-processing`

### Daily Ingestion Jobs

#### 3. Canada Gazette Part 2
- **Schedule**: Daily at 9:30 AM EST (`30 9 * * *`)
- **Job**: `pt-daily_ingestion-ingest-canada-gazette-p2`
- **Processing**: Runs at 9:45 AM EST (15 minutes later)

#### 4. Orders in Council (OIC)
- **Schedule**: Daily at 6:00 AM and 6:00 PM EST (`0 6,18 * * *`)
- **Job**: `pt-daily_ingestion-ingest-oic`
- **Processing**: Runs at 6:30 AM and 6:30 PM EST (30 minutes later)

### Processing Jobs

#### Sequential Processing Batch
- **Schedule**: Daily at 9:45 AM EST (`45 9 * * *`)
- **Job**: `pt-processing-sequence`
- **Function**: Runs Gazette P2 and OIC processing in sequence
- **Jobs**: 
  - `process_gazette_p2_to_evidence`
  - `process_oic_to_evidence`

## Key Improvements Made

### 1. Eliminated Redundancy
- ❌ Removed daily LegisInfo ingestion (replaced by RSS monitoring)
- ❌ Removed weekly LegisInfo refresh (RSS monitoring is more efficient)
- ❌ Removed separate daily processing jobs for RSS-monitored sources

### 2. Responsive Processing
- ✅ RSS monitoring jobs automatically trigger processing when new items found
- ✅ LegisInfo: RSS check → Bill ingestion → Evidence processing (when updates detected)
- ✅ Canada News: RSS ingestion → Evidence processing (when new items found)

### 3. Optimized Timing
- ✅ Canada News: Every 30 minutes (high frequency for news)
- ✅ LegisInfo: Every hour (appropriate for legislative updates)
- ✅ Gazette P2: Daily at 9:30 AM (business hours)
- ✅ OIC: Twice daily at 6 AM and 6 PM (morning and evening)

### 4. Efficient Sequencing
- ✅ Processing jobs run 15-30 minutes after ingestion
- ✅ Batch processing for related jobs (Gazette + OIC)
- ✅ Conditional processing only when new data is available

## Technical Configuration

### Cloud Run Service
- **Service**: `promise-tracker-ingestion`
- **Region**: `northamerica-northeast2` (Montreal)
- **URL**: `https://promise-tracker-ingestion-2gbdayf7rq-pd.a.run.app`

### Cloud Scheduler
- **Region**: `northamerica-northeast1` (Toronto)
- **Timezone**: `America/Toronto` (Eastern Time)
- **Max Timeout**: 30 minutes per job

### Endpoints
- **Individual Jobs**: `/jobs/{job_name}`
- **RSS with Processing**: `/jobs/{job_name}/with-processing`
- **Batch Jobs**: `/jobs/batch`

## Management Commands

### Deploy Schedules
```bash
python deploy_scheduler.py
```

### Monitor Jobs
```bash
python monitor_schedules.py list          # List all jobs
python monitor_schedules.py status        # Performance analysis
python monitor_schedules.py trigger <job> # Manual trigger
python monitor_schedules.py pause <job>   # Pause job
python monitor_schedules.py resume <job>  # Resume job
```

### Test Service
```bash
python test_scheduling.py  # Test Cloud Run service
```

## Current Status
- ✅ 5 scheduler jobs deployed and active
- ✅ RSS monitoring with conditional processing working
- ✅ All jobs properly sequenced and timed
- ✅ Cloud Run service deployed and healthy
- ✅ Monitoring and management tools operational

## Next Steps
1. Monitor job execution logs for the first few days
2. Adjust timing if needed based on actual data volumes
3. Consider adding alerting for job failures
4. Optimize processing job arguments based on performance 