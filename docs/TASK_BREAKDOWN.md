# Promise Tracker Production Readiness - Detailed Task Breakdown

## Current Status: Planning Phase
**Last Updated**: 2025-01-26

---

## **PHASE 1: System Architecture & Data Model Cleanup** ✅
**Status**: ✅ **COMPLETED**  
**Estimated Duration**: 2-3 days

### 1.1 Field Naming Audit & Standardization ✅
**Priority**: HIGH - Blocking for all other phases

#### Tasks:
- [x] **1.1.1** Audit current codebase for `dev_` prefixed fields
  - Search all `.py` files for `dev_` field references
  - Document current field mappings
  - Identify dependencies
  
- [x] **1.1.2** Create field migration mapping
  - `dev_explanation_enriched_at` → `explanation_enriched_at`
  - `dev_*` → standardized names
  - Document breaking changes
  
- [x] **1.1.3** Update scripts with standardized field names
  - Update `enrich_promises_with_explanation.py`
  - Update `enrich_tag_new_promise.py`
  - Update admin interface components
  
- [x] **1.1.4** Create data migration script
  - Backup existing data
  - Field renaming Firestore update script
  - Rollback capability

**Dependencies**: None  
**Deliverable**: Field migration completed, all scripts use standard names ✅

### 1.2 System Architecture Design
**Priority**: HIGH - Required for Phase 2 & 3

#### Tasks:
- [ ] **1.2.1** Design unified promise pipeline flow
  - Document current ingestion → enrichment → linking flow
  - Identify consolidation opportunities
  - Define state transitions
  
- [ ] **1.2.2** Create promise processing state machine
  - States: `raw` → `ingested` → `enriched` → `linked` → `completed`
  - Define triggers and dependencies
  - Error handling states
  
- [ ] **1.2.3** Document enrichment stage dependencies
  - Which enrichments can run in parallel?
  - Which require previous stages to complete?
  - Resource requirements per stage

**Dependencies**: None  
**Deliverable**: System architecture documentation

### 1.3 Evidence-Promise Linking Data Model
**Priority**: MEDIUM - Required for Phase 4

#### Tasks:
- [ ] **1.3.1** Design evidence rationale storage
  - Field: `promise_linking_rationale` at evidence level
  - Confidence scoring system
  - Audit trail requirements
  
- [ ] **1.3.2** Bill-stage consolidation logic
  - Single rationale for all bill stages
  - Bill lifecycle tracking
  - Duplicate prevention
  
- [ ] **1.3.3** Promise status update triggers
  - Evidence types that trigger status changes
  - Status calculation logic
  - Update frequency and batching

**Dependencies**: 1.1 completed  
**Deliverable**: Enhanced data model specification

---

## **PHASE 2: Langchain Framework Migration** ✅
**Status**: ✅ **COMPLETED**  
**Estimated Duration**: 3-4 days

### 2.1 Langchain Setup ✅
**Priority**: HIGH - Blocking for LLM work

#### Tasks:
- [x] **2.1.1** Install Langchain dependencies
  ```bash
  pip install langchain langchain-google-genai langchain-community
  ```
  
- [x] **2.1.2** Configure Gemini integration
  - Set up Langchain Gemini provider
  - Test connection and authentication
  - Configure generation parameters
  
- [x] **2.1.3** Create shared configuration
  - Central LLM configuration file (`lib/langchain_config.py`)
  - Environment variable management
  - Error handling setup

**Dependencies**: None  
**Deliverable**: Working Langchain environment ✅

### 2.2 Prompt Template Migration ✅
**Priority**: HIGH - Required for all LLM chains

#### Tasks:
- [x] **2.2.1** Convert existing prompts to Langchain templates
  - Promise enrichment prompts (explanation, keywords, action_type, history)
  - Evidence processing prompts (bills, news, gazette, OIC)
  - Evidence-promise linking prompts
  
- [x] **2.2.2** Implement prompt versioning
  - Template management in Langchain configuration
  - Template validation
  - Cost tracking capability
  
- [x] **2.2.3** Create prompt performance tracking
  - Cost per prompt execution
  - Success/failure rates
  - Response quality metrics via CostTrackingCallback

**Dependencies**: 2.1 completed  
**Deliverable**: All prompts as Langchain templates ✅

### 2.3 LLM Chain Development ✅
**Priority**: MEDIUM - Foundation for Phase 3 & 4

#### Tasks:
- [x] **2.3.1** Promise enrichment chains
  - History generation chain
  - Keyword extraction chain
  - Action type classification chain
  - Explanation generation chain
  
- [x] **2.3.2** Evidence processing chains
  - Bill evidence chain
  - News evidence chain
  - Gazette evidence chain
  - OIC evidence chain
  
- [x] **2.3.3** Evidence-promise linking chain
  - Similarity assessment
  - Rationale generation
  - Confidence scoring

**Dependencies**: 2.1, 2.2 completed  
**Deliverable**: Complete Langchain LLM library ✅

### 2.4 Consolidated Pipeline Scripts ✅
**Priority**: HIGH - Production readiness

#### Tasks:
- [x] **2.4.1** Create consolidated promise enrichment pipeline
  - `scripts/consolidated_promise_enrichment.py`
  - Unified processing for all enrichment types
  - Async processing with rate limiting
  
- [x] **2.4.2** Create consolidated evidence processing pipeline
  - `scripts/consolidated_evidence_processing.py`
  - Support for all evidence types (OIC, Gazette, Bills, News)
  - Integrated LLM analysis
  
- [x] **2.4.3** Create consolidated evidence-promise linking pipeline
  - `scripts/consolidated_evidence_linking.py`
  - LLM-generated rationales
  - Confidence scoring and batch processing

**Dependencies**: 2.1, 2.2, 2.3 completed  
**Deliverable**: Production-ready consolidated scripts ✅

---

## **PHASE 3: Consolidated Promise Pipeline**
**Status**: ⏳ Waiting for Phase 1 & 2  
**Estimated Duration**: 4-5 days

### 3.1 Unified Promise Ingestion
**Priority**: HIGH - Core functionality

#### Tasks:
- [ ] **3.1.1** Merge existing scripts into master pipeline
  - Integrate `ingest_2021_mandate_commitments.py` logic
  - Add `rank_promise_priority.py` functionality
  - Include all enrichment capabilities
  
- [ ] **3.1.2** Implement processing orchestration
  - State machine implementation
  - Dependency management
  - Progress tracking
  
- [ ] **3.1.3** Add comprehensive error handling
  - Retry logic for LLM failures
  - Partial completion handling
  - Error reporting and alerting

**Dependencies**: 1.1, 2.3 completed  
**Deliverable**: Master promise processing script

### 3.2 Promise Status Management
**Priority**: MEDIUM - Required for evidence linking

#### Tasks:
- [ ] **3.2.1** Implement status taxonomy
  - `identified`, `in_progress`, `completed`, `stalled`
  - Status calculation rules
  - Manual override capability
  
- [ ] **3.2.2** Create status update system
  - Automatic updates based on evidence
  - Audit trail for status changes
  - API endpoints for status management

**Dependencies**: 1.2, 3.1 completed  
**Deliverable**: Promise status management system

---

## **PHASE 4: Evidence Pipeline Enhancement**
**Status**: ⏳ Waiting for Phase 2 & 3  
**Estimated Duration**: 3-4 days

### 4.1 Evidence Ingestion Review
**Priority**: MEDIUM - Data quality foundation

#### Tasks:
- [ ] **4.1.1** Audit existing ingestion scripts
  - `ingest_legisinfo_bills.py`
  - `ingest_canada_gazette_p2.py`
  - `ingest_canada_news.py`
  - `ingest_oic.py`
  
- [ ] **4.1.2** Standardize data models
  - Consistent field naming
  - Quality validation rules
  - Duplicate detection

**Dependencies**: None  
**Deliverable**: Standardized evidence ingestion

### 4.2 Evidence-Promise Linking Enhancement
**Priority**: HIGH - Core new functionality

#### Tasks:
- [ ] **4.2.1** Enhance linking with rationales
  - Modify `link_evidence_to_promises.py`
  - Add rationale generation
  - Implement confidence scoring
  
- [ ] **4.2.2** Bill-stage consolidation
  - Single linking per bill across all stages
  - Stage-specific progress tracking
  - Consolidated rationale generation

**Dependencies**: 2.3, 4.1 completed  
**Deliverable**: Enhanced evidence-promise linking

---

## **PHASE 5: Admin Interface Enhancement**
**Status**: ⏳ Waiting for Phase 4  
**Estimated Duration**: 2-3 days

### 5.1 Interface Redesign
**Priority**: MEDIUM - User experience

#### Tasks:
- [ ] **5.1.1** Redesign promises management page
  - Add rationale display
  - Improve evidence preview
  - Enhance filtering capabilities
  
- [ ] **5.1.2** Implement bulk operations
  - Bulk approve/reject linking
  - Batch status updates
  - Export capabilities

**Dependencies**: 4.2 completed  
**Deliverable**: Enhanced admin interface

---

## **PHASE 6: Parliament 44 Full Test Run**
**Status**: ⏳ Waiting for All Phases  
**Estimated Duration**: 2-3 days

### 6.1 End-to-End Testing
**Priority**: HIGH - Validation

#### Tasks:
- [ ] **6.1.1** Clean and prepare Parliament 44 data
- [ ] **6.1.2** Run complete promise pipeline
- [ ] **6.1.3** Process all evidence types
- [ ] **6.1.4** Execute evidence-promise linking
- [ ] **6.1.5** Validate results and performance

**Dependencies**: All previous phases completed  
**Deliverable**: Production readiness validation

---

## **Implementation Schedule**

### Week 1
- **Days 1-2**: Phase 1 (Architecture & Data Model)
- **Days 3-5**: Phase 2 (Langchain Migration)

### Week 2  
- **Days 1-4**: Phase 3 (Promise Pipeline)
- **Day 5**: Phase 4 start (Evidence Pipeline)

### Week 3
- **Days 1-2**: Phase 4 completion
- **Days 3-4**: Phase 5 (Admin Interface)
- **Day 5**: Phase 6 start (Testing)

### Week 4
- **Days 1-2**: Phase 6 completion
- **Days 3-5**: Bug fixes and optimization

---

## **Next Immediate Actions**

### Today's Tasks:
1. **Review and approve this task breakdown**
2. **Start Phase 1.1.1**: Audit codebase for `dev_` fields
3. **Set up development branch**: `feature/production-readiness`
4. **Backup current Parliament 44 data**

### Tomorrow's Tasks (if approved):
1. **Complete field audit**
2. **Create migration script**
3. **Start Langchain setup** 