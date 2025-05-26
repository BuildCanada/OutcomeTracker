# New Ingestion Endpoints Added to Cloud Run Service

## 🎉 Overview

Your Cloud Run RSS monitoring service has been expanded with **4 new endpoints** to handle additional data ingestion and processing tasks:

1. **`/oic-ingestion`** - Order in Council (OIC) data ingestion
2. **`/gazette-p2-ingestion`** - Canada Gazette Part II ingestion
3. **`/gazette-p2-processing`** - Gazette P2 evidence processing with LLM
4. **`/gazette-p2-pipeline`** - Complete pipeline (ingestion + processing)

## 📋 Endpoint Details

### 1. `/oic-ingestion` - Order in Council Ingestion

**Purpose**: Scrapes Orders in Council from orders-in-council.canada.ca by iterating through attachment IDs.

**Request Parameters**:
```json
{
  "start_attach_id": 47204,      // Optional: Override starting attach ID
  "dry_run": false,              // Optional: Test mode
  "max_consecutive_misses": 50   // Optional: Stop after N consecutive 404s
}
```

**What it does**:
- Iteratively scrapes OIC attachment pages
- Extracts PC numbers, dates, full text content
- Stores raw OIC data in `raw_orders_in_council` collection
- Maintains state to resume from last successful ID
- Timeout: 30 minutes

### 2. `/gazette-p2-ingestion` - Gazette Part II Ingestion

**Purpose**: Ingests Canada Gazette Part II regulations from RSS feed and scrapes full content.

**Request Parameters**:
```json
{
  "start_date": "2025-05-01",    // Optional: YYYY-MM-DD format
  "end_date": "2025-05-24",      // Optional: YYYY-MM-DD format
  "dry_run": false               // Optional: Test mode
}
```

**What it does**:
- Fetches Gazette P2 RSS feed
- Scrapes individual regulation pages for full text
- Stores raw notices in `raw_gazette_p2_notices` collection
- Extracts regulation titles, SOR/SI numbers, HTML/PDF links
- Timeout: 30 minutes

### 3. `/gazette-p2-processing` - Gazette Evidence Processing

**Purpose**: Processes raw Gazette P2 notices into evidence items using Gemini LLM.

**Request Parameters**:
```json
{
  "start_date": "2025-05-01",     // Optional: YYYY-MM-DD format
  "end_date": "2025-05-24",       // Optional: YYYY-MM-DD format
  "dry_run": false,               // Optional: Test mode
  "force_reprocessing": false     // Optional: Reprocess existing items
}
```

**What it does**:
- Queries `raw_gazette_p2_notices` with status `pending_evidence_creation`
- Extracts RIAS and other key sections from full text
- Sends to Gemini LLM for structured analysis
- Creates evidence items in `evidence_items_test` collection
- Timeout: 60 minutes (for LLM processing)

### 4. `/gazette-p2-pipeline` - Complete Pipeline

**Purpose**: Orchestrates complete Gazette P2 workflow: ingestion followed by processing.

**Request Parameters**:
```json
{
  "start_date": "2025-05-01",     // Optional: YYYY-MM-DD format
  "end_date": "2025-05-24",       // Optional: YYYY-MM-DD format
  "dry_run": false,               // Optional: Test mode
  "force_reprocessing": false     // Optional: Reprocess existing items
}
```

**What it does**:
- Step 1: Runs Gazette P2 ingestion
- Step 2: If ingestion succeeds, runs evidence processing
- Returns detailed pipeline results
- Stops on ingestion failure to prevent wasted LLM calls

## 🔄 Manual Trigger Integration

All new endpoints are accessible via the `/manual-trigger` endpoint:

```bash
# Trigger OIC ingestion
curl -X POST "https://your-service/manual-trigger" \
  -H "Content-Type: application/json" \
  -d '{"action": "oic_ingestion"}'

# Trigger Gazette P2 ingestion
curl -X POST "https://your-service/manual-trigger" \
  -H "Content-Type: application/json" \
  -d '{"action": "gazette_p2_ingestion"}'

# Trigger Gazette P2 processing
curl -X POST "https://your-service/manual-trigger" \
  -H "Content-Type: application/json" \
  -d '{"action": "gazette_p2_processing"}'

# Trigger complete Gazette P2 pipeline
curl -X POST "https://your-service/manual-trigger" \
  -H "Content-Type: application/json" \
  -d '{"action": "gazette_p2_pipeline"}'
```

## ⏰ Recommended Cloud Scheduler Jobs

When you deploy to Cloud Run, add these scheduled jobs:

### OIC Ingestion (Daily at 9 AM)
```bash
gcloud scheduler jobs create http oic-ingestion-job \
  --location=northamerica-northeast2 \
  --schedule="0 9 * * *" \
  --uri="https://your-service/oic-ingestion" \
  --http-method=POST \
  --headers="Content-Type=application/json" \
  --message-body='{"dry_run": false, "max_consecutive_misses": 50}'
```

### Gazette P2 Pipeline (Daily at 10 AM)
```bash
gcloud scheduler jobs create http gazette-p2-pipeline-job \
  --location=northamerica-northeast2 \
  --schedule="0 10 * * *" \
  --uri="https://your-service/gazette-p2-pipeline" \
  --http-method=POST \
  --headers="Content-Type=application/json" \
  --message-body='{"dry_run": false, "force_reprocessing": false}'
```

## 📊 Response Formats

All endpoints return JSON with consistent structure:

**Success Response**:
```json
{
  "status": "success",
  "message": "Operation completed successfully",
  "stdout": "... last 500 characters of output ..."
}
```

**Error Response**:
```json
{
  "status": "error", 
  "error": "Error details...",
  "message": "Human-readable error description"
}
```

**Pipeline Response** (for `/gazette-p2-pipeline`):
```json
{
  "status": "success",
  "message": "Gazette P2 pipeline completed with status: success",
  "pipeline_results": [
    {
      "step": "ingestion",
      "status": "success", 
      "message": "Gazette P2 ingestion completed successfully"
    },
    {
      "step": "processing",
      "status": "success",
      "message": "Gazette P2 processing completed successfully"
    }
  ]
}
```

## 🧪 Testing the New Endpoints

Local testing (with Flask app running on port 8080):

```bash
# Test OIC ingestion (dry run)
curl -X POST http://localhost:8080/oic-ingestion \
  -H "Content-Type: application/json" \
  -d '{"dry_run": true, "max_consecutive_misses": 5}'

# Test Gazette P2 ingestion (dry run)
curl -X POST http://localhost:8080/gazette-p2-ingestion \
  -H "Content-Type: application/json" \
  -d '{"dry_run": true, "start_date": "2025-05-01"}'

# Test complete Gazette P2 pipeline (dry run)
curl -X POST http://localhost:8080/gazette-p2-pipeline \
  -H "Content-Type: application/json" \
  -d '{"dry_run": true, "start_date": "2025-05-01"}'
```

## 💡 Key Benefits

1. **Orchestration**: Pipeline endpoint ensures processing only runs after successful ingestion
2. **Error Handling**: Comprehensive error tracking and timeout management
3. **Flexibility**: Each step can be run independently or as part of a pipeline
4. **Monitoring**: All operations logged through existing RSS monitoring system
5. **Scalability**: Cloud Run automatically scales based on demand

## 🔄 Integration with Existing System

- **RSS Monitoring**: All new endpoints integrate with existing monitoring logger
- **Firestore**: Uses same database and collections structure
- **Authentication**: Same IAM and security model
- **Scheduling**: Fits into existing Cloud Scheduler workflow
- **Admin Dashboard**: New operations visible in `/admin/monitoring`

## 📋 Next Steps

1. **Deploy Updated Service**: Push changes and redeploy to Cloud Run
2. **Add Scheduler Jobs**: Create the new scheduled jobs shown above
3. **Monitor Operations**: Watch admin dashboard for new data ingestion
4. **Optimize Timing**: Adjust schedules based on actual processing times

Your RSS monitoring service is now a comprehensive **multi-source ingestion platform** that can handle bills, news, Orders in Council, and Gazette regulations with full automation and monitoring! 🚀 