
# Evidence Structure Investigation Report
Generated: 2025-05-28T14:43:46.570920+00:00

## Executive Summary

This investigation analyzes the fundamental differences between LLM-generated evidence (backup data) and real government evidence (current data) to understand why the linking algorithms aren't working effectively.

### Key Findings

**Data Volume**:
- **Backup Evidence**: 500 items (LLM-generated)
- **Current Evidence**: 500 items (real government data)

**Linking Status**:
- **Backup Links**: 500 items with promise links (1.00 avg links per item)
- **Current Links**: 0 items with promise links (0.00 avg links per item)

**Critical Issue**: Current evidence has 0 links vs. backup's 500 links, indicating the linking system needs fundamental redesign for real evidence.

## Structural Analysis

### Field Usage Comparison

**Fields Only in Backup**:
- `promise_ids`: 100.0% usage in backup
- `linking_status`: 100.0% usage in backup
- `linking_processed_at`: 100.0% usage in backup


**Fields Only in Current**:
- `bill_parl_id`: 46.0% usage in current
- `bill_one_sentence_description_llm`: 46.0% usage in current
- `additional_information`: 46.0% usage in current
- `llm_analysis_raw`: 10.4% usage in current
- `promise_linking_status`: 100.0% usage in current
- `bill_extracted_keywords_concepts`: 46.0% usage in current
- `description_or_details`: 100.0% usage in current
- `additional_metadata`: 54.0% usage in current
- `potential_relevance_score`: 54.0% usage in current
- `promise_linking_processed_at`: 12.0% usage in current


### Evidence Type Distribution

**Backup Evidence Types**:
- **Bill Event (LEGISinfo)**: 1 (0.2%)
- **Canada Gazette**: 27 (5.4%)
- **Canada News Centre**: 472 (94.4%)


**Current Evidence Types**:
- **Regulation (Canada Gazette P2)**: 52 (10.4%)
- **News Release (Canada.ca)**: 183 (36.6%)
- **Bill Event (LEGISinfo)**: 206 (41.2%)
- **Bill Final Status (LEGISinfo)**: 24 (4.8%)
- **OrderInCouncil (PCO)**: 35 (7.0%)


### Data Sources

**Current Evidence Sources**:
- **Unknown**: 500 (100.0%)


## Content Pattern Analysis

### Title Characteristics

**Backup Evidence Titles**:
- Average length: 213 characters
- Average words: 31.0 words
- With dates: 32.0%
- With departments: 96.0%


**Current Evidence Titles**:
- Average length: 87 characters
- Average words: 12.2 words
- With dates: 2.0%
- With departments: 26.0%


### Content Quality

**Backup Content**:


**Current Content**:


## Linkability Analysis

### Keyword Extraction Potential

- **Backup**: 0.0 avg keywords per item, 0 unique keywords
- **Current**: 2.8 avg keywords per item, 129 unique keywords
- **Keyword Overlap**: 0 keywords in common


### Department Alignment

- **Backup Departments**: 7 unique departments
- **Current Departments**: 11 unique departments
- **Department Overlap**: 3 departments (20.0%)


## Key Insights

1. Current evidence has no promise links, indicating linking system needs activation
2. Title length difference: backup avg 213 vs current avg 87
3. Department overlap only 20.0%
4. Low department overlap between backup and current evidence
5. Many current evidence items lack sufficient content for analysis


## Algorithm Recommendations

1. Implement initial linking run with relaxed parameters to establish baseline
2. Adjust text similarity algorithms to account for title length differences
3. Review department name standardization and mapping
4. Create department mapping and standardization system
5. Improve content scraping and processing for evidence items


## Critical Differences: LLM vs. Real Evidence

### LLM-Generated Evidence (Backup)
- **Purpose-built**: Created specifically to match existing promises
- **Consistent structure**: Uniform field usage and content patterns
- **High linkability**: Designed with promise alignment in mind
- **Artificial keywords**: Keywords extracted or generated to match promise concepts

### Real Government Evidence (Current)
- **Authentic documents**: Actual government announcements, bills, regulations
- **Variable structure**: Different formats based on source (news, bills, OICs)
- **Natural language**: Real-world government communication patterns
- **Organic content**: Keywords and concepts emerge naturally from content

### Implications for Linking Algorithms

1. **Lower Match Rates Expected**: Real evidence won't have the artificial alignment of LLM-generated content
2. **Enhanced Preprocessing Needed**: Real evidence requires more sophisticated content extraction and normalization
3. **Semantic Understanding Required**: Simple keyword matching insufficient for real government language
4. **Temporal Considerations**: Real evidence may precede or follow promises by significant time periods
5. **Domain Expertise**: Understanding government processes and terminology becomes critical

## Next Steps

### Immediate Actions
1. **Manual Link Testing**: Create 5-10 manual links to verify system functionality
2. **Algorithm Parameter Adjustment**: Lower similarity thresholds for real evidence
3. **Content Enhancement**: Improve keyword extraction for government documents

### Medium-term Improvements
1. **Semantic Similarity**: Implement embedding-based matching
2. **Domain-specific Processing**: Government document type-specific algorithms
3. **Temporal Correlation**: Time-based relevance scoring

### Long-term Strategy
1. **Hybrid Approach**: Combine automated suggestions with human review
2. **Continuous Learning**: Algorithm improvement based on validated links
3. **Quality over Quantity**: Focus on high-confidence, high-value links

## Files Generated
- `evidence_structure_investigation.json`: Complete analysis data
- `evidence_structure_report.md`: This comprehensive report
