# RSS Feed Monitoring Best Practices

## Overview

This document outlines best practices for monitoring the LEGISinfo RSS feed integration in your Promise Tracker application, covering infrastructure monitoring, application-level tracking, alerting strategies, and operational procedures.

## Architecture Overview

```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   Cloud         │    │   Application   │    │   Frontend      │
│   Infrastructure│    │   Monitoring    │    │   Dashboard     │
├─────────────────┤    ├─────────────────┤    ├─────────────────┤
│ • Cloud Monitor │    │ • Firestore     │    │ • Admin UI      │
│ • Cloud Logging │    │   Collections   │    │ • Real-time     │
│ • Uptime Checks │    │ • Custom Metrics│    │   Status        │
│ • Alert Policies│    │ • Error Tracking│    │ • Historical    │
│ • Pub/Sub       │    │ • Performance   │    │   Trends        │
└─────────────────┘    └─────────────────┘    └─────────────────┘
```

## 1. Infrastructure Monitoring (Google Cloud)

### Cloud Monitoring Setup

**Key Metrics to Track:**
- RSS feed response time and availability
- Cloud Run service performance
- Firestore read/write operations
- Memory and CPU utilization

**Uptime Checks:**
```bash
# Create uptime check for RSS feed
gcloud monitoring uptime-checks create \
  --display-name="LEGISinfo RSS Feed" \
  --resource-type=HTTP \
  --uri="https://www.parl.ca/legisinfo/en/bills/rss" \
  --check-interval=300s \
  --timeout=10s
```

**Custom Metrics:**
- `rss_feed_availability` (availability percentage)
- `rss_bills_discovered_rate` (bills per hour)
- `ingestion_success_rate` (successful ingestions/total)
- `processing_latency` (end-to-end processing time)

### Alert Policies

**Critical Alerts:**
- RSS feed down for >5 minutes
- 3+ consecutive ingestion failures
- Processing backlog >24 hours
- Firestore errors >5% rate

**Warning Alerts:**
- RSS response time >5 seconds
- 1-2 ingestion failures
- Processing latency >2x normal
- Memory usage >80%

### Example Alert Policy:
```yaml
displayName: "RSS Feed Critical Failure"
conditions:
  - displayName: "RSS Uptime Check Failure"
    conditionThreshold:
      filter: 'resource.type="uptime_url"'
      comparison: COMPARISON_GREATER_THAN
      thresholdValue: 0
      duration: "300s"
notificationChannels:
  - projects/[PROJECT-ID]/notificationChannels/[CHANNEL-ID]
```

## 2. Application-Level Monitoring

### Firestore Collections

Your application uses three monitoring collections:

#### `rss_feed_monitoring`
**Purpose:** Track individual RSS check and ingestion operations
```javascript
{
  session_id: "rss_session_20240115_143022",
  operation: "rss_check" | "bill_ingestion",
  status: "started" | "completed" | "failed",
  start_time: Timestamp,
  end_time: Timestamp,
  bills_found: 5,
  parliament_filter: 44,
  error_message: "Connection timeout",
  response_time_ms: 2500
}
```

#### `rss_feed_metrics`
**Purpose:** Daily aggregated metrics for trending
```javascript
{
  date: "2024-01-15",
  total_checks: 48,
  successful_checks: 47,
  total_bills_found: 23,
  avg_response_time_ms: 1850,
  last_check: Timestamp,
  created_at: Timestamp
}
```

#### `rss_feed_alerts`
**Purpose:** Application-generated alerts for business logic issues
```javascript
{
  alert_type: "consecutive_failures",
  severity: "critical" | "warning",
  message: "RSS feed has failed 3 consecutive times",
  error_message: "HTTP 503 Service Unavailable",
  failure_count: 3,
  created_at: Timestamp,
  resolved: false
}
```

### Monitoring Integration

The `rss_monitoring_logger.py` automatically tracks:
- RSS check start/completion
- Response times and error rates
- Bill discovery rates
- Ingestion success/failure counts
- Automatic alert generation

**Usage in existing scripts:**
```python
from .rss_monitoring_logger import rss_monitor

# In RSS check script
monitor_id = rss_monitor.log_rss_check_start(24, 44)
# ... perform RSS check ...
rss_monitor.log_rss_check_result(monitor_id, True, 5, None, 2500)

# In ingestion script  
ingestion_id = rss_monitor.log_ingestion_start("rss_driven", 5, "scheduled")
# ... perform ingestion ...
rss_monitor.log_ingestion_result(ingestion_id, True, 5, 12, 0)
```

## 3. Frontend Monitoring Dashboard

### Admin Interface

Access via: `/admin/monitoring`

**Dashboard Sections:**
1. **Health Overview:** Current status, success rates, response times
2. **Active Alerts:** Unresolved issues requiring attention  
3. **7-Day Trend:** Historical performance for pattern analysis
4. **Recent Activity:** Last 24 hours of operations with detailed logs

**Key Features:**
- Real-time status indicators
- Color-coded health metrics
- Filterable activity logs
- One-click alert resolution
- Export capabilities for deeper analysis

### Status Indicators

- 🟢 **Healthy:** >95% success rate, no active alerts
- 🟡 **Warning:** 80-95% success rate or minor issues
- 🔴 **Critical:** <80% success rate or major failures
- ⚫ **Unknown:** No recent data available

## 4. Deployment and Scheduling

### Cloud Scheduler Jobs

**RSS Checks (Every 30 minutes):**
```bash
gcloud scheduler jobs create http rss-feed-check \
  --schedule="*/30 * * * *" \
  --uri="https://rss-monitor-[HASH]-uc.a.run.app" \
  --http-method=POST \
  --headers="Content-Type=application/json" \
  --message-body='{"action":"rss_check","hours_threshold":1,"parliament_filter":44}'
```

**Daily Ingestion (6 AM EST):**
```bash
gcloud scheduler jobs create http daily-bill-ingestion \
  --schedule="0 6 * * *" \
  --time-zone="America/Toronto" \
  --uri="https://rss-monitor-[HASH]-uc.a.run.app" \
  --http-method=POST \
  --message-body='{"action":"full_ingestion","hours_threshold":24,"fallback_full_run":true}'
```

### Infrastructure as Code

Use the provided `infrastructure/rss-monitoring.tf` for:
- Cloud Run services
- Cloud Scheduler jobs
- Service accounts and IAM
- Monitoring and alerting
- Storage buckets for data retention

**Deployment:**
```bash
terraform init
terraform plan -var="project_id=[YOUR-PROJECT-ID]"
terraform apply
```

## 5. Operational Procedures

### Daily Monitoring Checklist

**Morning Review (10 minutes):**
1. Check admin dashboard health status
2. Review any overnight alerts
3. Verify daily ingestion completed successfully
4. Check for any processing backlogs

**Weekly Review (30 minutes):**
1. Analyze 7-day trends for patterns
2. Review alert frequency and causes
3. Check storage usage and retention
4. Update monitoring thresholds if needed

### Incident Response

**RSS Feed Down:**
1. Check external feed availability manually
2. Review error logs in Cloud Logging
3. If feed is down: Monitor for recovery, no action needed
4. If application issue: Investigate Cloud Run logs
5. Consider manual ingestion if downtime >2 hours

**Processing Failures:**
1. Check Firestore quotas and limits
2. Review LLM API quotas and usage
3. Verify service account permissions
4. Run manual processing with `--dry_run` first

**High Error Rate:**
1. Check Cloud Run resource limits
2. Review network connectivity
3. Verify external API rate limits
4. Consider scaling up Cloud Run instances

### Performance Optimization

**RSS Check Frequency:**
- Normal: Every 30 minutes
- High activity periods: Every 15 minutes  
- Maintenance windows: Every 2 hours

**Processing Optimization:**
- Batch size: 50-100 bills per run
- Parallel processing: 5 concurrent workers
- Rate limiting: 1.2 seconds between API calls
- Timeout settings: 45 seconds per bill

**Storage Management:**
- Metrics retention: 90 days in Firestore
- Log retention: 30 days in Cloud Logging
- Archive to Cloud Storage for long-term trends
- Regular cleanup of resolved alerts

## 6. Integration with Existing Systems

### Firestore Security Rules

Ensure monitoring collections have appropriate access:
```javascript
rules_version = '2';
service cloud.firestore {
  match /databases/{database}/documents {
    // RSS monitoring collections - admin only
    match /rss_feed_monitoring/{document} {
      allow read, write: if request.auth != null && 
        get(/databases/$(database)/documents/users/$(request.auth.uid)).data.role == 'admin';
    }
    
    match /rss_feed_metrics/{document} {
      allow read: if request.auth != null;
      allow write: if request.auth != null && 
        get(/databases/$(database)/documents/users/$(request.auth.uid)).data.role == 'admin';
    }
  }
}
```

### Backup and Recovery

**Automated Backups:**
```bash
# Daily Firestore export (via Cloud Scheduler)
gcloud firestore export gs://[PROJECT-ID]-backups/$(date +%Y%m%d) \
  --collection-ids=rss_feed_monitoring,rss_feed_metrics,rss_feed_alerts
```

**Recovery Procedures:**
- Monitoring data can be recreated from logs
- Historical metrics may be lost but system continues functioning
- RSS checks resume automatically after restoration

## 7. Cost Optimization

### Resource Usage

**Typical Daily Costs (estimated):**
- Cloud Run: $0.50-2.00/day (depends on frequency)
- Cloud Scheduler: $0.10/day (fixed)
- Firestore: $0.20-1.00/day (depends on operations)
- Cloud Monitoring: $0.25/day (metrics and alerting)

**Optimization Strategies:**
- Use minimum Cloud Run instances during low activity
- Implement intelligent scaling based on RSS activity
- Archive old monitoring data to cheaper storage
- Tune alert thresholds to reduce noise

### Monitoring Budget Alerts

```bash
gcloud billing budgets create \
  --display-name="RSS Monitoring Budget" \
  --budget-amount=50 \
  --threshold-rule=50,80,90,100 \
  --notification-channel-ids=[CHANNEL-ID]
```

## 8. Security Considerations

### Service Account Permissions

**Principle of Least Privilege:**
- RSS monitor service account: Only Firestore and Cloud Run access
- No unnecessary project-level permissions
- Regular audit of granted roles

### Network Security

- Cloud Run services: Internal ingress only
- Cloud Scheduler: Uses OIDC tokens for authentication
- Firestore: Private network access when possible

### API Security

- User-Agent headers for external RSS requests
- Rate limiting to respect external API limits
- Timeout and retry configurations
- Input validation for all external data

## 9. Troubleshooting Guide

### Common Issues

**"RSS feed returns empty results":**
- Check if LEGISinfo RSS is temporarily down
- Verify time threshold settings
- Check parliament filter values

**"High response times":**
- Monitor external RSS feed performance
- Check Cloud Run resource allocation
- Review network latency to external APIs

**"Ingestion failures":**
- Check Firestore quotas
- Verify LLM API availability
- Review service account permissions

**"Missing monitoring data":**
- Check if monitoring logger is imported correctly
- Verify Firestore write permissions
- Review error logs for import issues

### Debug Commands

```bash
# Check RSS feed manually
curl -I "https://www.parl.ca/legisinfo/en/bills/rss"

# Test monitoring integration
python scripts/ingestion_jobs/check_legisinfo_rss_updates.py --dry_run --limit 5

# Review Cloud Run logs
gcloud logging read 'resource.type="cloud_run_revision"' --limit=50

# Check Firestore operations
gcloud logging read 'protoPayload.serviceName="firestore.googleapis.com"' --limit=20
```

## 10. Future Enhancements

### Planned Improvements

1. **Machine Learning Integration:** Predict peak RSS activity periods
2. **Advanced Analytics:** Trend analysis and anomaly detection  
3. **Multi-Region Deployment:** Improve reliability and latency
4. **Real-time Webhooks:** Instant notifications for critical events
5. **Integration Testing:** Automated testing of RSS feed changes

### Metrics to Consider Adding

- **Bill content similarity analysis:** Detect duplicate or similar bills
- **Processing efficiency trends:** Time per bill over different periods
- **External API dependency mapping:** Track all external service dependencies
- **Cost per bill processed:** Economic efficiency metrics

---

This monitoring strategy ensures reliable, observable, and maintainable RSS feed integration while providing the visibility needed for proactive system management. 