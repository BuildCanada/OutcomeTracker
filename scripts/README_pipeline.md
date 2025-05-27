# Promise Processing Pipeline

## Overview

The Promise Processing Pipeline is a comprehensive, production-ready system for ingesting, processing, and enriching Canadian government promises. It uses the **`gemini-2.5-flash-preview-05-20`** model with Langchain orchestration and incorporates tested prompts from the existing enrichment scripts.

## Key Features

### 🚀 **Complete Pipeline Integration**
- **Document Ingestion**: Extract promises from raw documents using LLM
- **Promise Creation**: Store structured promises in Firestore
- **Multi-Stage Enrichment**: Add explanations, keywords, action types, and history
- **Priority Ranking**: Score promises using BC economic criteria
- **Cost Tracking**: Monitor LLM usage and costs

### 🧠 **Tested LLM Prompts**
Uses proven prompts from:
- `enrich_promises_with_explanation.py` - For concise titles, descriptions, impacts
- `enrich_tag_new_promise.py` - For keywords, action types, commitment history
- `rank_promise_priority.py` - For economic priority scoring

### 🔧 **Langchain Orchestration**
- Centralized configuration in `lib/langchain_config.py`
- Chain-based processing with error handling
- Rate limiting and retry logic
- JSON output parsing and validation

### 🧪 **Safe Testing**
- Uses `promises_test` collection for development
- Demo scripts with sample data
- Cost estimation and monitoring
- Comprehensive logging

## Architecture

```
Raw Document → LLM Extraction → Promise Creation → Enrichment Pipeline → Priority Ranking
     ↓              ↓                 ↓                    ↓                 ↓
  .txt/.md      JSON Array      Firestore Storage    Enhanced Metadata   BC Score
```

## File Structure

```
PromiseTracker/
├── lib/
│   ├── langchain_config.py      # Enhanced Langchain configuration
│   └── priority_ranking.py      # Priority ranking wrapper
├── scripts/
│   ├── promise_pipeline.py      # Main pipeline orchestrator
│   ├── demo_pipeline.py         # Demo script
│   └── README_pipeline.md       # This documentation
└── sample_documents/
    └── test_mandate_2025.txt       # Sample document for testing
```

## Usage

### 1. Document Ingestion

Extract promises from a raw document:

```bash
python promise_pipeline.py ingest sample_documents/test_mandate_2025.txt \
  --source-type "2025 LPC Platform" \
  --source-url "https://example.com/platform" \
  --date-issued "2025-01-01" \
  --entity "Liberal Party of Canada" \
  --parliament-session "44" \
  --party-code "LPC" \
  --test-collection
```

### 2. Promise Enrichment

Enrich a specific promise:

```bash
python promise_pipeline.py enrich \
  --promise-id "PROMISE_DOC_ID" \
  --test-collection
```

Batch enrich multiple promises:

```bash
python promise_pipeline.py enrich \
  --batch \
  --limit 10 \
  --test-collection
```

### 3. Cost Monitoring

Check LLM usage costs:

```bash
python promise_pipeline.py cost
```

### 4. Complete Demo

Run the full demonstration:

```bash
python demo_pipeline.py
```

## Enrichment Fields

The pipeline adds these fields to each promise:

### **Explanation Fields** (from `enrich_promises_with_explanation.py`)
- `concise_title` - Short descriptive title (5-8 words)
- `what_it_means_for_canadians` - List of 3-5 citizen impacts
- `description` - Brief summary (1-2 sentences)
- `background_and_context` - Policy background (2-3 sentences)

### **Preprocessing Fields** (from `enrich_tag_new_promise.py`)
- `extracted_keywords_concepts` - List of 5-10 key terms
- `implied_action_type` - One of: legislative, funding_allocation, policy_development, program_launch, consultation, international_agreement, appointment, other
- `commitment_history_rationale` - Array of 0-4 preceding events with dates, actions, and source URLs

### **Priority Fields** (from `rank_promise_priority.py`)
- `bc_promise_rank` - Priority rank: 'strong', 'medium', or 'weak'
- `bc_promise_direction` - Direction: 'positive', 'negative', or 'neutral'
- `bc_promise_rank_rationale` - Brief fact-based explanation (<40 words)

### **Metadata Fields**
- `explanation_enriched_at` - Timestamp
- `linking_preprocessing_done_at` - Timestamp
- `ingested_at` - Timestamp

## Data Structure

Each promise follows this structure:

```python
@dataclass
class PromiseData:
    # Core fields
    promise_id: str
    text: str
    source_document_url: str
    source_type: str
    
    # Metadata
    date_issued: str
    parliament_session_id: str
    candidate_or_government: str
    party_code: str
    region_code: str = "Canada"
    
    # Department info
    responsible_department_lead: Optional[str] = None
    relevant_departments: List[str] = None
    
    # All enrichment fields...
```

## Configuration

### Environment Variables

```bash
# Required
GEMINI_API_KEY=your_gemini_api_key
FIREBASE_PROJECT_ID=your_project_id

# Optional
FIREBASE_SERVICE_ACCOUNT_KEY_PATH=path/to/service-account.json
GEMINI_MODEL_NAME=models/gemini-2.5-flash-preview-05-20
```

### Langchain Configuration

The system uses these models and settings:

```python
MODEL_NAME = "gemini-2.5-flash-preview-05-20"  # Balanced capability/speed/cost
TEMPERATURE = 0.1  # Low for consistent results
MAX_OUTPUT_TOKENS = 65536  # Large for complex outputs
RESPONSE_MIME_TYPE = "application/json"  # Structured output
```

## Testing Strategy

### 1. **Safe Development**
- Uses `promises_test` collection by default
- Never modifies production data during development
- Demo script with sample data

### 2. **Cost Control**
- Rate limiting between LLM calls
- Batch processing with configurable limits
- Cost estimation and tracking
- Preview mode for testing prompts

### 3. **Quality Assurance**
- JSON validation for all LLM outputs
- Confidence scoring for extracted promises
- Comprehensive error handling and logging
- Field validation before storage

## Integration Points

### **Admin Frontend Integration**
The pipeline is designed to integrate with the admin frontend:

```python
# Create promises from frontend
pipeline = PromisePipeline(use_test_collection=False)
promise_ids = await pipeline.ingest_document(...)

# Enrich specific promises
success = await pipeline.enrich_promise(promise_id, force=True)

# Get cost summary
costs = pipeline.get_cost_summary()
```

### **Existing Script Integration**
- Compatible with existing `enrich_promises_with_explanation.py` prompts
- Uses same field names as `enrich_tag_new_promise.py`
- Integrates priority logic from `rank_promise_priority.py`

## Performance Considerations

### **LLM Usage Optimization**
- Batch processing reduces API calls
- Caching of department priorities
- Smart rate limiting (2-5 seconds between calls)
- JSON-only output format reduces parsing overhead

### **Firestore Optimization**
- Batch writes for multiple updates
- Selective field queries to reduce reads
- Indexed queries on common fields
- Document size management

### **Cost Management**
- **Estimated costs**: ~$0.01-0.05 per promise for complete enrichment
- **Token efficiency**: Focused prompts reduce input/output tokens
- **Model choice**: `gemini-2.5-flash-preview-05-20` offers best cost/performance ratio

## Error Handling

The system includes comprehensive error handling:

- **LLM Failures**: Retry logic with exponential backoff
- **JSON Parsing**: Fallback extraction from markdown
- **Firestore Errors**: Transaction rollbacks and retry
- **Validation Errors**: Detailed logging with promise context
- **Cost Overruns**: Early termination with partial results

## Next Steps

### **Immediate Tasks**
1. Test the demo pipeline with your Firebase setup
2. Review enrichment quality on sample promises
3. Adjust prompts based on output quality
4. Integrate with admin frontend

### **Production Readiness**
1. Add monitoring and alerting
2. Implement batch job scheduling
3. Add data quality metrics
4. Create backup and recovery procedures

### **Enhanced Features**
1. Multi-language support
2. Advanced priority algorithms  
3. Evidence-promise linking integration
4. Real-time processing workflows

## Support

For issues or questions:
1. Check logs for detailed error messages
2. Verify environment variables are set correctly
3. Test with demo script first
4. Review Firebase permissions and quotas

---

**Note**: This system uses the `gemini-2.5-flash-preview-05-20` model, providing an excellent balance of capability, speed, and cost for the promise enrichment pipeline. 