#!/bin/bash

# Promise Tracker Pipeline - Cloud Run Testing Script
# This script tests the deployed Cloud Run service to ensure it's working correctly

set -e

# Configuration
PROJECT_ID=${PROJECT_ID:-"promisetrackerapp"}
SERVICE_NAME=${SERVICE_NAME:-"promise-tracker-pipeline"}
REGION=${REGION:-"us-central1"}

# Get the service URL
SERVICE_URL=$(gcloud run services describe $SERVICE_NAME --platform managed --region $REGION --format 'value(status.url)' 2>/dev/null)

if [ -z "$SERVICE_URL" ]; then
    echo "❌ Could not find Cloud Run service $SERVICE_NAME in region $REGION"
    exit 1
fi

echo "🧪 Testing Promise Tracker Pipeline on Cloud Run..."
echo "🌐 Testing service at: $SERVICE_URL"
echo ""

# Test counters
PASSED=0
TOTAL=0

# Helper function to test endpoint
test_endpoint() {
    local name="$1"
    local method="$2"
    local endpoint="$3"
    local data="$4"
    local expected_status="$5"
    
    TOTAL=$((TOTAL + 1))
    echo "${TOTAL}️⃣  Testing $name..."
    
    # Create temporary files for response
    local temp_response="/tmp/response_$$"
    local temp_status="/tmp/status_$$"
    
    if [ "$method" = "GET" ]; then
        curl -s -w "%{http_code}" -o "$temp_response" "$SERVICE_URL$endpoint" > "$temp_status"
    else
        curl -s -w "%{http_code}" -o "$temp_response" -X "$method" -H "Content-Type: application/json" -d "$data" "$SERVICE_URL$endpoint" > "$temp_status"
    fi
    
    # Read response and status code
    status_code=$(cat "$temp_status")
    body=$(cat "$temp_response")
    
    if [ "$status_code" = "$expected_status" ]; then
        echo "   ✅ $name test passed (HTTP $status_code)"
        PASSED=$((PASSED + 1))
    else
        echo "   ❌ $name test failed (HTTP $status_code)"
    fi
    
    echo "   📄 Response: $body"
    echo ""
    
    # Cleanup temp files
    rm -f "$temp_response" "$temp_status"
}

# 1. Test health check
test_endpoint "Health check" "GET" "/" "" "200"

# 2. Test job status endpoint
test_endpoint "Job status endpoint" "GET" "/jobs" "" "200"

# 3. Test Canada News ingestion job
test_endpoint "Canada News ingestion" "POST" "/jobs/ingestion/canada_news" '{}' "200"

# 4. Test LEGISinfo Bills ingestion job
test_endpoint "LEGISinfo Bills ingestion" "POST" "/jobs/ingestion/legisinfo_bills" '{}' "200"

# 5. Test batch processing endpoint (this should fail as expected since batch.processing doesn't exist)
test_endpoint "Batch processing" "POST" "/jobs/batch" '{"jobs": [{"stage": "processing", "job": "news_processor"}]}' "200"

# 6. Check recent service logs
echo "6️⃣  Checking recent service logs..."
echo "   📋 Last 10 log entries:"
gcloud logging read "resource.type=cloud_run_revision AND resource.labels.service_name=$SERVICE_NAME" \
    --limit=10 \
    --format="table(timestamp,severity,textPayload)" \
    --project=$PROJECT_ID 2>/dev/null || echo "   ⚠️  Could not fetch logs (check permissions)"

echo ""
echo "📊 Test Summary:"
echo "   ✅ Passed: $PASSED/$TOTAL tests"
echo "   🌐 Service URL: $SERVICE_URL"

if [ $PASSED -eq $TOTAL ]; then
    echo ""
    echo "🎉 All tests passed! Your Cloud Run service is working correctly."
    exit 0
else
    echo ""
    echo "⚠️  Some tests failed. Check the responses above for details."
    exit 1
fi 