# LLM Evidence Linking Development Task List

## Project Overview
Rework the current evidence_linker.py into an LLM-first approach that provides much higher semantic matching quality for linking evidence items to promises. This approach will use large-context LLM calls to identify direct relationships between evidence and multiple promises simultaneously.

## Goal
Evaluate the feasibility and quality of using a large-context LLM call to identify direct links between one evidence item and multiple promises, updating both promises.linked_evidence and evidence_items.promise_ids fields with the best match linkages.

---

## 🏗️ **Phase 1: Infrastructure Setup** ✅
- [x] Create main testing script: `scripts/linking_jobs/test_llm_multi_promise_linking.py`
- [x] Set up standard imports (dotenv, logging, argparse, Firebase, asyncio)
- [x] Initialize Gemini client using proven langchain_config approaches
- [x] Define collection constants (test vs production modes)
- [x] Implement CLI argument parsing (--parliament_session_id, --evidence_id_to_test, --dry_run, --log_level)
- [x] **NEW**: Added --limit CLI argument for batch processing control
- [x] **NEW**: Added --update_evidence_status flag for status management

## 🗄️ **Phase 2: Data Management** ✅
- [x] Create function to fetch target evidence_item by evidence_id
- [x] Create function to fetch all promises for parliament session with required fields:
  - canonical_commitment_text, description, background_and_context
  - reporting_lead_title, relevant_departments, commitment_history_rationale
  - what_it_means_for_canadians
- [x] Create test collection copies (promises_test, evidence_items_test) for safe testing
- [x] Validate data extraction and field mapping
- [x] **NEW**: Function to update all evidence items to promise_linking_status = 'pending'
- [x] **NEW**: Function to fetch evidence items ready for processing (status = 'pending')

## 📝 **Phase 3: Prompt Template Enhancement** ✅
- [x] Update `prompt_link_evidence_to_promise.md` structure to match `prompt_progress_scoring.md` format
- [x] Integrate with `langchain_config.py` for consistency and model management
- [x] Create large context prompt construction function that combines:
  - Single evidence item details
  - Complete list of session promises as JSON
  - Clear linking instructions and output format
- [x] Test prompt template with sample data

## 🤖 **Phase 4: LLM Processing Engine** ✅
- [x] Implement LLM call function using langchain_config patterns
- [x] Create JSON response parser with error handling
- [x] Implement retry logic and rate limiting
- [x] Add extensive logging for prompt content and raw LLM responses
- [x] Validate LLM output structure matches expected link format

## 🔗 **Phase 5: Database Linking Operations** ✅
- [x] Create function to parse LLM JSON response into link objects
- [x] Implement promise collection updates (add linked evidence references)
- [x] Implement evidence_items collection updates (add promise_ids and rationale)
- [x] Update evidence linking status fields (promise_linking_status = "processed")
- [x] Handle both test and production collection writes
- [x] **NEW**: Batch processing capability for multiple evidence items
- [x] **NEW**: Status management for evidence items in test collections

## 🧪 **Phase 6: Testing & Validation** 🔄
- [x] Implement comprehensive logging system for debugging
- [x] Create dry-run mode to preview changes without writing
- [x] Add validation for LLM output quality and completeness
- [x] **NEW**: Support for both single evidence item and batch processing modes
- [x] **NEW**: Rate limiting between LLM calls in batch mode
- [ ] Test with sample evidence items across different types
- [ ] Performance testing with full promise datasets

## 📊 **Phase 7: Quality Assurance**
- [ ] Compare semantic matching quality vs current keyword-based approach
- [ ] Implement confidence scoring and thresholds
- [ ] Create evaluation metrics for link quality
- [ ] Test edge cases (no matches, multiple strong matches, unclear evidence)

## 🚀 **Phase 8: Integration Planning**
- [ ] Document integration path to replace existing evidence_linker.py
- [ ] Create migration strategy for existing links
- [ ] Performance optimization for production-scale processing
- [ ] Integration with existing pipeline scheduling

---

## Key Technical Components

### Collections
- **Testing**: `promises_test`, `evidence_items_test` (pre-created by user)
- **Production**: `promises`, `evidence_items`

### Required Evidence Fields
- evidence_id, evidence_source_type, title_or_summary
- description_or_details, key_concepts, parliament_session_id
- **Status Field**: promise_linking_status ('pending' → 'processed')

### Required Promise Fields
- canonical_commitment_text, description, background_and_context
- reporting_lead_title, relevant_departments
- commitment_history_rationale, what_it_means_for_canadians

### LLM Output Schema
```json
{
  "promise_id": "ID_of_the_matched_promise_from_the_list",
  "llm_relevance_score": 8,
  "llm_ranking_score": "High",
  "llm_explanation": "Your concise explanation here.",
  "llm_link_type_suggestion": "Suggested link type",
  "llm_status_impact_suggestion": "Suggested status impact"
}
```

### Processing Consistency
**Evidence Status Management**: New evidence items are created with `promise_linking_status = 'pending'` (verified in `legisinfo_processor.py` line 825), ensuring consistency across processing scripts.

## Progress Tracking

**Current Phase**: Phase 6 - Testing & Validation (in progress)  
**Started**: January 2025  
**Last Updated**: January 2025  

### Completed Tasks
- [x] Task tracking document created
- [x] Main testing script infrastructure complete
- [x] Data fetching functions implemented
- [x] Test collection creation functionality
- [x] Enhanced prompt template with semantic focus
- [x] Langchain integration for LLM processing
- [x] Database linking operations implementation
- [x] Evidence status updating functionality
- [x] **NEW**: Batch processing mode with --limit control
- [x] **NEW**: Evidence status management (--update_evidence_status)
- [x] **NEW**: CLI enhancements for flexible operation modes

### In Progress
- [ ] Real data testing with batch processing
- [ ] Performance evaluation against existing keyword approach

### New Usage Modes

**Single Evidence Item Testing:**
```bash
python scripts/linking_jobs/test_llm_multi_promise_linking.py \
  --parliament_session_id 44 \
  --evidence_id_to_test <specific_evidence_id> \
  --dry_run
```

**Batch Processing (Limited):**
```bash
python scripts/linking_jobs/test_llm_multi_promise_linking.py \
  --parliament_session_id 44 \
  --limit 10 \
  --dry_run
```

**Status Update:**
```bash
python scripts/linking_jobs/test_llm_multi_promise_linking.py \
  --parliament_session_id 44 \
  --update_evidence_status
```

### Blocked/Issues
- [ ] None currently

---

## Notes
- Use langchain_config.py patterns for consistency
- Extensive logging for debugging LLM responses
- Follow existing proven script patterns from consolidated_promise_enrichment.py
- Test mode uses separate collections for safety
- Test collections (promises_test, evidence_items_test) are pre-created by user
- Phase 1-5 infrastructure is complete and enhanced with batch processing
- Enhanced semantic matching approach vs keyword-based approach 
- Evidence status management ensures consistency with processing pipeline 