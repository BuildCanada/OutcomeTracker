# LEGISinfo Two-Stage Ingestion System

## Overview

This document describes the new two-stage ingestion system for LEGISinfo bill data, which replaces the previous single-stage approach. The system now uses JSON data sources instead of XML and follows the established pattern used by other ingestion systems in the project.

## Architecture

### Stage 1: Raw Data Ingestion
**Script:** `scripts/ingestion_jobs/ingest_legisinfo_raw_bills.py`

- Fetches the main bill list from LEGISinfo JSON API
- For each bill, fetches detailed JSON data
- Stores raw JSON content in Firestore collection `raw_legisinfo_bill_details`
- Implements idempotency checks based on `LatestActivityDateTime`
- Supports filtering by parliament session

### Stage 2: Processing into Evidence Items
**Script:** `scripts/processing_jobs/process_raw_legisinfo_to_evidence.py`

- Processes raw JSON data from Stage 1
- Uses Gemini LLM for bill analysis and keyword extraction
- Creates evidence items for each legislative event
- Stores results in `evidence_items_test` collection
- Supports date filtering for events

## New Firestore Collections

### raw_legisinfo_bill_details
Document ID: Human-readable format (e.g., "44-1_C-69", "44-1_S-228")

Key Fields:
- `parl_id`: Original LEGISinfo BillId for reference
- `bill_number_code_feed`: Bill number (e.g., "C-22", "S-1")
- `parliament_session_id`: Consolidated parliament-session (e.g., "44-1")
- `source_detailed_json_url`: URL of the detailed JSON endpoint
- `raw_json_content`: Full JSON content as string
- `feed_last_major_activity_date`: Latest activity date from feed
- `ingested_at`: Timestamp of ingestion
- `processing_status`: "pending_processing", "processed", "error_*"

### evidence_items_test (Enhanced)
New fields added for bill evidence:
- `bill_parl_id`: Reference to raw bill document (human-readable format)
- `bill_extracted_keywords_concepts`: Keywords from LLM analysis
- `bill_timeline_summary_llm`: LLM-generated timeline summary
- `bill_one_sentence_description_llm`: LLM-generated description
- `promise_linking_status`: Status for linking to promises ("pending", etc.)
- `additional_information.event_specific_details`: Event metadata including terminal status flags

**Terminal Status Handling:**
- Bills with final statuses (defeated, royal assent, not proceeded with, etc.) automatically get terminal status evidence items
- Terminal events are marked with `evidence_source_type: "Bill Final Status (LEGISinfo)"`
- Terminal events include `is_terminal_status: true` in event metadata for frontend timeline display

## LLM Integration

### Prompt Template
**File:** `prompts/prompt_bill_evidence.md`

The LLM analyzes bills and extracts:
- `timeline_summary_llm`: Concise summary for timeline (max 30 words)
- `one_sentence_description_llm`: Detailed explanation (30-50 words)
- `key_concepts_llm`: 5-10 keywords/phrases for matching
- `sponsoring_department_standardized_llm`: Standardized department name

## Daily Scheduled Ingestion

For production use, the system now supports RSS-driven ingestion for optimal efficiency:

### RSS-Enhanced Daily Runs (Recommended)
```bash
# RSS-driven ingestion (most efficient for daily runs)
python scripts/ingestion_jobs/rss_driven_bill_ingestion.py

# Optional: Manual RSS check first to see what's updated
python scripts/ingestion_jobs/check_legisinfo_rss_updates.py --hours_threshold 24 --parliament_filter 44
```

### Traditional Full Ingestion (Fallback)
```bash
python scripts/ingestion_jobs/ingest_legisinfo_raw_bills.py
python scripts/processing_jobs/process_raw_legisinfo_to_evidence.py
```

**RSS-Enhanced Benefits:**
1. **Real-time Change Detection**: RSS feed shows actual legislative activity, not just API timestamps
2. **Maximum Efficiency**: Only processes bills that actually had recent activity (from RSS feed)
3. **Automatic Fallback**: Can fallback to full ingestion if RSS has issues
4. **Parliament Filtering**: RSS checking respects parliament filters (default: Parliament 44+)
5. **Flexible Scheduling**: Can check for updates over any time period (hours, days, weeks)

**How RSS-Enhanced System Works:**
1. **RSS Check**: Fetches LEGISinfo RSS feed for recent bill activity
2. **Targeted Stage 1**: Only runs raw ingestion on bills appearing in RSS updates
3. **Normal Stage 2**: Processes all pending bills (RSS-updated + any previous pending)
4. **Comprehensive Logs**: Full tracking of RSS hits, ingestion counts, and processing results

**Performance Improvements:**
- RSS feed provides real-time bill activity notifications
- Skips API polling for bills with no recent legislative events
- Reduces ingestion from ~412 bills to only bills with actual activity
- Maintains full coverage through idempotency and optional fallback

## Usage Examples

### RSS-Driven Ingestion (Recommended)
```bash
# Daily RSS-driven ingestion (most efficient)
python scripts/ingestion_jobs/rss_driven_bill_ingestion.py

# Check RSS for recent updates (6 hours)
python scripts/ingestion_jobs/rss_driven_bill_ingestion.py --hours_threshold 6

# RSS-driven with fallback to full ingestion if no RSS updates
python scripts/ingestion_jobs/rss_driven_bill_ingestion.py --fallback_full_run

# Dry run RSS-driven ingestion for testing
python scripts/ingestion_jobs/rss_driven_bill_ingestion.py --dry_run --limit 5

# Only run Stage 1 (skip evidence processing)
python scripts/ingestion_jobs/rss_driven_bill_ingestion.py --skip_stage2
```

### RSS Update Checking (Standalone)
```bash
# Check bills updated in last 24 hours
python scripts/ingestion_jobs/check_legisinfo_rss_updates.py

# Check last 6 hours, Parliament 44 only
python scripts/ingestion_jobs/check_legisinfo_rss_updates.py --hours_threshold 6 --parliament_filter 44

# Output as CSV file
python scripts/ingestion_jobs/check_legisinfo_rss_updates.py --output_format csv --output_file recent_bills.csv

# Get simple list of bill IDs
python scripts/ingestion_jobs/check_legisinfo_rss_updates.py --output_format list
```

### Stage 1: Ingest Raw Data (Direct)
```bash
# Daily scheduled run (traditional approach)
python scripts/ingestion_jobs/ingest_legisinfo_raw_bills.py

# RSS-filtered ingestion (use bills from RSS check)
python scripts/ingestion_jobs/check_legisinfo_rss_updates.py --hours_threshold 12 --output_file bills_to_update.json
python scripts/ingestion_jobs/ingest_legisinfo_raw_bills.py --rss_filter_file bills_to_update.json

# Ingest all bills from Parliament 44+ (dry run)
python scripts/ingestion_jobs/ingest_legisinfo_raw_bills.py --dry_run

# Ingest specific parliament session with limit
python scripts/ingestion_jobs/ingest_legisinfo_raw_bills.py --parliament_session_target "44-1" --limit 50

# Force reprocessing of all bills from Parliament 44+
python scripts/ingestion_jobs/ingest_legisinfo_raw_bills.py --force_reprocessing

# Change minimum parliament number (e.g., include Parliament 43+)
python scripts/ingestion_jobs/ingest_legisinfo_raw_bills.py --min_parliament 43

# Output to JSON instead of Firestore for testing/optimization
python scripts/ingestion_jobs/ingest_legisinfo_raw_bills.py --JSON --limit 10 --parliament_session_target "44-1"

# Custom JSON output directory
python scripts/ingestion_jobs/ingest_legisinfo_raw_bills.py --JSON --json_output_dir ./my_outputs --limit 5
```

### Stage 2: Process into Evidence (Direct)
```bash
# Process pending bills (dry run)
python scripts/processing_jobs/process_raw_legisinfo_to_evidence.py --dry_run

# Process with date filtering
python scripts/processing_jobs/process_raw_legisinfo_to_evidence.py --start_date 2024-01-01 --end_date 2024-12-31

# Output to JSON instead of Firestore for testing/optimization
python scripts/processing_jobs/process_raw_legisinfo_to_evidence.py --JSON --limit 5

# Custom JSON output directory
python scripts/processing_jobs/process_raw_legisinfo_to_evidence.py --JSON --json_output_dir ./my_evidence_outputs

# Force reprocessing with limit
python scripts/processing_jobs/process_raw_legisinfo_to_evidence.py --force_reprocessing --limit 10
```

## Key Improvements

1. **RSS-Driven Efficiency**: Real-time bill activity detection through RSS feeds for optimal daily scheduling
2. **Two-Stage Architecture**: Separates data fetching from processing, improving reliability and debugging
3. **JSON Data Sources**: More reliable than XML parsing
4. **Event-Based Evidence**: Creates evidence items for each legislative event, not just bills
5. **LLM Enhancement**: Uses Gemini for intelligent analysis and keyword extraction
6. **Better Error Handling**: Comprehensive error tracking and status management
7. **Idempotency**: Avoids re-fetching unchanged data
8. **Flexible Filtering**: Supports RSS filtering, parliament session, and date range filtering
9. **JSON Output Support**: All scripts support outputting to JSON files for testing and optimization before committing to Firestore
10. **Orchestrated Scheduling**: Single command for complete RSS-driven ingestion with automatic fallback

## Migration Notes

- The old single-stage script has been renamed to `ingest_legisinfo_evidence_DEPRECATED_SINGLE_STAGE.py`
- The new system skips the `bills_data` collection and goes directly to evidence items
- Department standardization uses both script logic and LLM fallback
- Evidence items include richer metadata about legislative events

## Environment Variables

Required:
- `GEMINI_API_KEY`: For LLM analysis
- `FIREBASE_PROJECT_ID`: Firestore project ID

Optional:
- `GEMINI_MODEL_BILL_PROCESSING`: Override default model (default: "models/gemini-2.5-flash-preview-05-20")

## Dependencies

The scripts use the established patterns from other processing jobs:
- Firebase Admin SDK for Firestore
- Google Gemini for LLM analysis
- Common utilities for department standardization
- Standard logging and CLI argument patterns 