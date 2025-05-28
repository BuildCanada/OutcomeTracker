
# Data Structure Exploration Report
Generated: 2025-05-28T14:52:49.054077+00:00

## Executive Summary

This report explores the actual data structure and field contents of promises and evidence collections to identify usable content for linking algorithms.

### Key Findings

**Promises Collection**:
- Sample size: 20 documents
- Total fields: 47 unique fields
- Primary content fields: 4
- Secondary content fields: 7

**Evidence Collection**:
- Sample size: 20 documents  
- Total fields: 23 unique fields
- Primary content fields: 3
- Secondary content fields: 3

## Promises Data Structure

### Field Usage Statistics


**policy_areas**:
- Usage: 100.0% (20 documents)
- Data types: list

**explanation_enrichment_model**:
- Usage: 100.0% (20 documents)
- Data types: str
- Sample content: "gemini-2.5-flash-preview-05-20..."

**commitment_history_rationale**:
- Usage: 100.0% (20 documents)
- Data types: list

**last_enrichment_at**:
- Usage: 100.0% (20 documents)
- Data types: DatetimeWithNanoseconds

**text**:
- Usage: 100.0% (20 documents)
- Data types: str
- Sample content: "Strengthen Canada's partnerhips with the United States...."

**last_updated_at**:
- Usage: 100.0% (20 documents)
- Data types: DatetimeWithNanoseconds

**bc_promise_direction**:
- Usage: 100.0% (20 documents)
- Data types: str
- Sample content: "positive..."

**party**:
- Usage: 100.0% (20 documents)
- Data types: str
- Sample content: "Liberal Party of Canada..."

**implied_action_type**:
- Usage: 100.0% (20 documents)
- Data types: str
- Sample content: "policy_development..."

**party_code**:
- Usage: 100.0% (20 documents)
- Data types: str
- Sample content: "LPC..."

**keywords_extracted_at**:
- Usage: 100.0% (20 documents)
- Data types: DatetimeWithNanoseconds

**concise_title**:
- Usage: 100.0% (20 documents)
- Data types: str
- Sample content: "Strengthening Canada-US Partnerships..."

**explanation_enriched_at**:
- Usage: 100.0% (20 documents)
- Data types: DatetimeWithNanoseconds

**source_type**:
- Usage: 100.0% (20 documents)
- Data types: str
- Sample content: "2021 LPC Mandate Letters..."

**description**:
- Usage: 100.0% (20 documents)
- Data types: str
- Sample content: "This commitment aims to enhance the multifaceted bilateral relationship between Canada and the Unite..."


### Usable Content Fields

#### Primary Content Fields (>50 chars, >80% usage)

- **text**: 100.0% usage, 75 avg chars
  - Sample: "Strengthen Canada's partnerhips with the United States...."

- **description**: 100.0% usage, 103 avg chars
  - Sample: "This commitment aims to enhance the multifaceted bilateral relationship between ..."

- **background_and_context**: 100.0% usage, 103 avg chars
  - Sample: "The commitment to strengthen Canada's partnership with the United States is root..."

- **bc_promise_rank_rationale**: 100.0% usage, 103 avg chars
  - Sample: "Strengthening ties with Canada's largest partner directly impacts trade, investm..."


#### Secondary Content Fields (>20 chars, >50% usage)

- **explanation_enrichment_model**: 100.0% usage, 30 avg chars
  - Sample: "gemini-2.5-flash-preview-05-20..."

- **party**: 100.0% usage, 23 avg chars
  - Sample: "Liberal Party of Canada..."

- **concise_title**: 100.0% usage, 38 avg chars
  - Sample: "Strengthening Canada-US Partnerships..."

- **source_type**: 100.0% usage, 24 avg chars
  - Sample: "2021 LPC Mandate Letters..."

- **candidate_or_government**: 100.0% usage, 39 avg chars
  - Sample: "Liberal Party of Canada (2021 Platform)..."

- **responsible_department_lead**: 100.0% usage, 23 avg chars
  - Sample: "Global Affairs Canada..."

- **id**: 100.0% usage, 27 avg chars
  - Sample: "LPC_20211216_MANDL_002f9cde..."


## Evidence Data Structure

### Field Usage Statistics


**source_url**:
- Usage: 100.0% (20 documents)
- Data types: str
- Sample content: "https://gazette.gc.ca/rp-pr/p2/2021/2021-10-13/html/sor-dors215-eng.html..."

**description_or_details**:
- Usage: 100.0% (20 documents)
- Data types: str
- Sample content: "These Regulations amend the Canadian Chicken Marketing Quota Regulations under the Farm Products Age..."

**evidence_source_type**:
- Usage: 100.0% (20 documents)
- Data types: str
- Sample content: "Regulation (Canada Gazette P2)..."

**promise_ids**:
- Usage: 100.0% (20 documents)
- Data types: list

**linked_departments**:
- Usage: 100.0% (20 documents)
- Data types: NoneType, list

**promise_linking_status**:
- Usage: 100.0% (20 documents)
- Data types: str
- Sample content: "pending..."

**parliament_session_id**:
- Usage: 100.0% (20 documents)
- Data types: str
- Sample content: "44..."

**evidence_date**:
- Usage: 100.0% (20 documents)
- Data types: DatetimeWithNanoseconds

**evidence_id**:
- Usage: 100.0% (20 documents)
- Data types: str
- Sample content: "20211013_44_Gazette2_bd7ed6d0b3..."

**ingested_at**:
- Usage: 100.0% (20 documents)
- Data types: DatetimeWithNanoseconds

**title_or_summary**:
- Usage: 100.0% (20 documents)
- Data types: str
- Sample content: "Regulations amending the Farm Products Agencies Act come into force, impacting Canadian chicken mark..."

**id**:
- Usage: 100.0% (20 documents)
- Data types: str
- Sample content: "20211013_44_Gazette2_bd7ed6d0b3..."

**key_concepts**:
- Usage: 85.0% (17 documents)
- Data types: list

**additional_metadata**:
- Usage: 85.0% (17 documents)
- Data types: dict

**potential_relevance_score**:
- Usage: 85.0% (17 documents)
- Data types: str
- Sample content: "Medium..."


### Usable Content Fields

#### Primary Content Fields (>50 chars, >80% usage)

- **source_url**: 100.0% usage, 71 avg chars
  - Sample: "https://gazette.gc.ca/rp-pr/p2/2021/2021-10-13/html/sor-dors215-eng.html..."

- **description_or_details**: 100.0% usage, 103 avg chars
  - Sample: "These Regulations amend the Canadian Chicken Marketing Quota Regulations under t..."

- **title_or_summary**: 100.0% usage, 103 avg chars
  - Sample: "Regulations amending the Farm Products Agencies Act come into force, impacting C..."


#### Secondary Content Fields (>20 chars, >50% usage)

- **evidence_source_type**: 100.0% usage, 30 avg chars
  - Sample: "Regulation (Canada Gazette P2)..."

- **evidence_id**: 100.0% usage, 31 avg chars
  - Sample: "20211013_44_Gazette2_bd7ed6d0b3..."

- **id**: 100.0% usage, 31 avg chars
  - Sample: "20211013_44_Gazette2_bd7ed6d0b3..."


## Data Quality Assessment

### Content Availability

**Promises**:
- Primary content fields available: ✅ Yes
- Secondary content fields available: ✅ Yes
- Metadata fields available: ✅ Yes

**Evidence**:
- Primary content fields available: ✅ Yes
- Secondary content fields available: ✅ Yes
- Metadata fields available: ✅ Yes

### Linking Feasibility

✅ **Linking Feasible**: Both collections have usable text content


## Recommendations

### Data Extraction Strategy

1. Use primary promise fields: text, description, background_and_context
2. Use primary evidence fields: source_url, description_or_details, title_or_summary
3. Implement multi-field text extraction combining primary and secondary content.
4. Use semantic similarity algorithms due to sufficient text content.
5. Leverage metadata fields for department/category-based pre-filtering.


### Implementation Priorities

1. **Immediate**: Fix data quality issues preventing content extraction
2. **Short-term**: Implement multi-field text extraction strategy
3. **Medium-term**: Develop field-specific processing algorithms
4. **Long-term**: Optimize linking algorithms based on actual content patterns

## Sample Documents

### Promise Sample
```json
{
  "keywords_enrichment_status": "processed",
  "policy_areas": [],
  "explanation_enrichment_model": "gemini-2.5-flash-preview-05-20",
  "commitment_history_rationale": [
    {
      "date": "2020-03-20",
      "source_url": "",
      "action": "Prime Minister Justin Trudeau announced an agreement with the United States to temporarily close the Canada-U.S. border to non-essential travel, an unprecedented measure to curb the spread of COVID-19 that significantly impacted cross-border movement a...
```

### Evidence Sample
```json
{
  "source_document_raw_id": "SOR/2021-215",
  "key_concepts": [
    "Canadian Chicken Marketing Quota",
    "Farm Products Agencies Act",
    "chicken production",
    "chicken marketing",
    "agricultural regulations",
    "quota limits"
  ],
  "source_url": "https://gazette.gc.ca/rp-pr/p2/2021/2021-10-13/html/sor-dors215-eng.html",
  "description_or_details": "These Regulations amend the Canadian Chicken Marketing Quota Regulations under the Farm Products Agencies Act, establishing limits f...
```

## Files Generated
- `data_structure_exploration.json`: Complete exploration data
- `data_structure_exploration_report.md`: This comprehensive report

---
*Report generated by Promise Tracker Data Structure Explorer*
