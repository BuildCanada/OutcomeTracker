# Semantic Evidence Linking Analysis & Implementation

## Overview

This document details the development and analysis of semantic evidence linking for the Promise Tracker application, replacing keyword-based matching with embedding-based semantic similarity.

## Problem Statement

The original keyword-based evidence linking system had limitations in finding semantic relationships between evidence items and promises. Manual analysis revealed opportunities for higher-quality matching through semantic understanding rather than simple keyword overlap.

## Methodology

### 1. Field Selection Analysis

**Evidence Items:**
- ✅ `title_or_summary`: 100% of records (primary content)
- ✅ `description_or_details`: 100% of records (detailed content)  
- ✅ `key_concepts`: LLM-extracted concepts
- ✅ `linked_departments`: Department context
- ❌ `title`, `description`: 0% usage (legacy fields)

**Promises:**
- ✅ `text`: Primary promise text
- ✅ `description`: Promise description
- ✅ `background_and_context`: Rich contextual information
- ✅ `intended_impact_and_objectives`: Impact statements
- ✅ `responsible_department_lead`: Department context

### 2. Technical Implementation

**Model:** `all-MiniLM-L6-v2` sentence transformer
- Fast inference (1-2 seconds model load)
- Good semantic understanding for English text
- Balanced performance vs speed

**Similarity Calculation:** Cosine similarity with safety checks
- Handles zero-magnitude vectors
- NaN/infinity validation
- Proper normalization

**Document ID Matching:** Fixed critical bug
- Evidence `promise_ids` use Firestore document IDs (`LPC_20211216_MANDL_*`)
- NOT internal `promise.promise_id` field (`2404`, `3102`)

## Analysis Results

### Comprehensive Testing (100 Evidence Items)

**Similarity Threshold: 0.55**
- 📊 Evidence items analyzed: 100
- 📂 Total existing links: 301 (keyword-based)
- 🎯 Total semantic links: 248 (semantic-based)
- 🔄 Overlapping links: 58 (both systems agree)
- 📈 New semantic links: 190 (semantic finds, keyword missed)
- ⚠️ Lost existing links: 243 (keyword found, semantic missed)
- 📊 **Overlap rate: 19.3%**

### Key Findings

1. **Significant Differences:** Only 19.3% overlap suggests the approaches find fundamentally different types of relationships
2. **Semantic Discoveries:** 190 new high-quality semantic matches (similarity > 0.55)
3. **Coverage Trade-offs:** 243 existing links not found semantically (may indicate over-linking in keyword system)
4. **Quality Focus:** Higher threshold (0.55) produces more confident matches

## File Structure

```
PromiseTracker/
├── scripts/testing/
│   ├── semantic_comparison_analysis.py     # Main comparison tool
│   └── analyze_title_field_usage.py       # Field usage validator
├── pipeline/stages/linking/
│   └── semantic_evidence_linker.py        # Production semantic linker
└── docs/
    └── semantic_evidence_linking_analysis.md  # This document
```

## Usage Examples

### Comparison Analysis
```bash
# Default analysis (threshold 0.55, test collections)
python scripts/testing/semantic_comparison_analysis.py --parliament_session_id 44 --limit 100

# Custom threshold
python scripts/testing/semantic_comparison_analysis.py --parliament_session_id 44 --limit 50 --similarity_threshold 0.6

# Production collections (careful!)
python scripts/testing/semantic_comparison_analysis.py --parliament_session_id 44 --limit 20 --use_production
```

### Production Semantic Linking
```python
from pipeline.stages.linking.semantic_evidence_linker import link_evidence_semantically

# Basic usage
result = link_evidence_semantically(
    parliament_session_id='44',
    evidence_collection='evidence_items_test',
    promise_collection='promises_test',
    limit=10,
    dry_run=True
)

# With debug output
result = link_evidence_semantically(
    parliament_session_id='44',
    similarity_threshold=0.6,
    generate_debug_files=True
)
```

## Performance Characteristics

**Speed:**
- Model loading: ~1 second
- Embedding generation: ~2 seconds for 759 promises
- Similarity calculation: ~1 second per evidence item
- Total: ~3-4 seconds per evidence item (first run), <1 second subsequent

**Memory:**
- Model: ~100MB
- Embeddings: ~10MB for 759 promises
- Scalable to thousands of promises

**Quality:**
- No sklearn warnings with proper validation
- Handles edge cases (empty text, zero vectors)
- Deterministic results (no randomness)

## Configuration

**Default Parameters:**
```python
SIMILARITY_THRESHOLD = 0.55    # Based on analysis results
MAX_LINKS_PER_EVIDENCE = 50    # Prevent over-linking
MODEL_NAME = 'all-MiniLM-L6-v2'  # Fast, reliable model
BATCH_SIZE = 32                # Efficient embedding generation
```

## Next Steps: LLM Enhancement Strategy

### Recommended Hybrid Approach

The semantic analysis shows strong potential but could benefit from LLM validation for optimal results. See **LLM Enhancement Recommendations** section below.

---

# LLM Enhancement Recommendations

## Strategy: Two-Stage Hybrid Approach

Based on the semantic analysis results, here's the recommended approach for using LLM to further improve matching quality:

### Stage 1: Semantic Pre-filtering
- Use semantic similarity with **lower threshold (0.4-0.45)**
- Cast a wider net to capture potential matches
- Fast, scalable first pass

### Stage 2: LLM Validation & Ranking
- Feed semantic candidates to LLM for intelligent evaluation
- LLM assesses contextual relevance, intent alignment
- Produces final ranked list with confidence scores

## Implementation Architecture

```python
def hybrid_evidence_linking(evidence_item, promises, semantic_threshold=0.4, llm_threshold=0.7):
    # Stage 1: Semantic pre-filtering
    semantic_candidates = semantic_similarity_search(
        evidence_item, 
        promises, 
        threshold=semantic_threshold,
        max_candidates=20  # Manageable for LLM
    )
    
    # Stage 2: LLM validation
    if semantic_candidates:
        llm_results = llm_validate_matches(
            evidence_item,
            semantic_candidates,
            threshold=llm_threshold
        )
        return llm_results
    
    return []
```

## LLM Prompt Strategy

### Context-Aware Evaluation
```
You are evaluating whether government evidence items relate to specific political promises.

EVIDENCE ITEM:
Title: {evidence_title}
Description: {evidence_description}
Department: {evidence_department}
Date: {evidence_date}

POTENTIAL PROMISE MATCH:
Promise: {promise_text}
Context: {promise_context}
Department: {promise_department}
Impact: {promise_impact}

TASK: Evaluate if this evidence item represents progress toward fulfilling this promise.

Consider:
1. Thematic alignment (policy areas, subject matter)
2. Department/ministerial responsibility overlap
3. Timeline relevance (evidence after promise)
4. Concrete vs aspirational connection
5. Direct implementation vs indirect support

Respond with:
- Score: 0.0-1.0 (confidence of match)
- Reasoning: Brief explanation
- Category: "Direct Implementation" | "Supporting Action" | "Related Policy" | "Not Related"
```

## Benefits of Hybrid Approach

### 1. **Efficiency**
- Semantic stage filters 759 promises → ~20 candidates
- LLM only processes high-potential matches
- Scalable to large datasets

### 2. **Quality**
- Semantic captures broad thematic similarity
- LLM provides nuanced contextual understanding
- Handles complex policy relationships

### 3. **Transparency**
- Semantic similarity scores (objective)
- LLM reasoning (interpretable)
- Combined confidence metrics

### 4. **Flexibility**
- Adjustable thresholds for precision/recall trade-offs
- Different prompts for different evidence types
- A/B testing capability

## Expected Improvements

Based on analysis results:
- **Higher Precision:** LLM filters out semantic false positives
- **Better Recall:** Lower semantic threshold captures more candidates
- **Contextual Understanding:** Political intent, timing, departmental responsibility
- **Relationship Types:** Direct implementation vs supporting evidence vs related policy

## Implementation Timeline

1. **Phase 1:** Implement basic LLM validation (1-2 weeks)
2. **Phase 2:** Optimize prompts and thresholds (1 week)
3. **Phase 3:** A/B test against current system (1 week)
4. **Phase 4:** Production deployment with monitoring (1 week)

## Cost Considerations

**Token Usage per Evidence Item:**
- Evidence context: ~200 tokens
- 20 promise candidates: ~400 tokens each = 8,000 tokens
- Response: ~100 tokens
- **Total: ~8,300 tokens per evidence item**

**Estimated Costs (100 evidence items):**
- GPT-4: ~$8.30 (830k tokens)
- GPT-3.5-turbo: ~$1.25 (830k tokens)
- Gemini Pro: ~$0.83 (830k tokens)

## Monitoring & Evaluation

**Quality Metrics:**
- Precision/Recall vs existing system
- Human evaluation of LLM match quality
- Processing time and cost tracking

**A/B Testing Framework:**
- 50% semantic-only, 50% hybrid approach
- Track link quality and user feedback
- Measure promise fulfillment tracking accuracy

---

This hybrid approach leverages the speed and broad coverage of semantic search with the nuanced understanding of LLMs, providing the best balance of quality, efficiency, and cost for promise-evidence linking. 