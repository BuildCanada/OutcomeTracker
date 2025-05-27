# Promise Tracker Production Readiness PRD

## Executive Summary
Transform the current development system into a production-ready platform by consolidating ingestion logic, implementing comprehensive evidence-to-promise linking with rationales, migrating to Langchain framework, and creating a robust testing pipeline using Parliament 44 real data.

## Project Scope & Objectives

### Primary Goals
1. **Consolidated Promise Pipeline**: Merge all promise ingestion and enrichment logic into a unified, production-ready pipeline
2. **Comprehensive Evidence Processing**: Implement full evidence ingestion and processing for all source types
3. **Intelligent Evidence-Promise Linking**: Deploy LLM-powered linking with detailed rationales
4. **Real-time Status Updates**: Automatically update promise status based on evidence
5. **Enhanced Admin Interface**: Create user-friendly bulk linking capabilities
6. **Langchain Migration**: Standardize LLM coordination and prompt management
7. **Production Testing**: Validate system with complete Parliament 44 dataset

### Success Criteria
- ✅ Single command promise ingestion with all enrichments
- ✅ Evidence linking accuracy >85% with human-readable rationales  
- ✅ Real-time promise status updates based on evidence
- ✅ Admin interface supporting bulk operations
- ✅ All prompts managed through Langchain
- ✅ Complete Parliament 44 test run successful

---

## Phase Breakdown

### **Phase 1: System Architecture & Data Model Cleanup** 
**Duration: 2-3 days**

#### 1.1 Field Naming Standardization
- [ ] Remove all `dev_` prefixes from field names
- [ ] Update field mappings: `dev_explanation_enriched_at` → `explanation_enriched_at`
- [ ] Update all scripts to use standardized field names
- [ ] Create migration script for existing data

#### 1.2 Consolidated Promise Pipeline Design
- [ ] Design unified promise ingestion flow
- [ ] Define enrichment stage dependencies
- [ ] Create promise processing state machine
- [ ] Document field requirements for each stage

#### 1.3 Evidence-Promise Linking Data Model
- [ ] Design evidence-level rationale storage
- [ ] Define linking confidence scores
- [ ] Create bill-stage consolidation logic
- [ ] Design promise status update triggers

**Deliverables:**
- [ ] Updated data model documentation
- [ ] Field migration plan
- [ ] Consolidated pipeline architecture diagram

---

### **Phase 2: Langchain Framework Migration**
**Duration: 3-4 days**

#### 2.1 Langchain Setup & Configuration
- [ ] Install Langchain dependencies
- [ ] Configure LLM providers (Gemini integration)
- [ ] Set up prompt template management
- [ ] Create shared LLM chain configurations

#### 2.2 Prompt Management Migration
- [ ] Convert existing prompts to Langchain templates
- [ ] Implement prompt version control
- [ ] Create prompt validation system
- [ ] Set up prompt performance tracking

#### 2.3 LLM Chain Development
- [ ] Promise enrichment chains (history, keywords, action types)
- [ ] Evidence processing chains (by source type)
- [ ] Evidence-promise linking chains
- [ ] Promise status update chains

**Deliverables:**
- [ ] Langchain configuration framework
- [ ] All prompts migrated to Langchain templates
- [ ] Standardized LLM chain library

---

### **Phase 3: Consolidated Promise Pipeline**
**Duration: 4-5 days**

#### 3.1 Unified Promise Ingestion Script
- [ ] Merge logic from `ingest_2021_mandate_commitments.py`
- [ ] Integrate `rank_promise_priority.py` logic
- [ ] Incorporate `enrich_tag_new_promise.py` enrichments
- [ ] Add `enrich_promises_with_explanation.py` functionality
- [ ] Implement standardized field names

#### 3.2 Promise Processing Orchestration
- [ ] Create promise processing state machine
- [ ] Implement dependency management between enrichment stages
- [ ] Add error handling and retry logic
- [ ] Create progress tracking and logging

#### 3.3 Promise Status Management
- [ ] Define promise status taxonomy
- [ ] Implement status update triggers
- [ ] Create status change audit trail
- [ ] Add status-based filtering capabilities

**Deliverables:**
- [ ] Single consolidated promise ingestion script
- [ ] Promise processing orchestrator
- [ ] Promise status management system

---

### **Phase 4: Evidence Pipeline Enhancement**
**Duration: 3-4 days**

#### 4.1 Evidence Ingestion Consolidation
- [ ] Review and standardize all ingestion scripts in `@ingestion_jobs`
- [ ] Ensure consistent data models across evidence types
- [ ] Add evidence quality validation
- [ ] Implement duplicate detection

#### 4.2 Evidence Processing Pipeline
- [ ] Consolidate processing scripts from `@processing_jobs`
- [ ] Standardize evidence item structure
- [ ] Add evidence enrichment capabilities
- [ ] Implement evidence categorization

#### 4.3 Evidence-Promise Linking Enhancement
- [ ] Enhance `@link_evidence_to_promises.py` with rationale generation
- [ ] Implement bill-stage consolidation
- [ ] Add linking confidence scoring
- [ ] Create evidence-level rationale storage

**Deliverables:**
- [ ] Consolidated evidence ingestion pipeline
- [ ] Enhanced evidence-promise linking with rationales
- [ ] Evidence quality validation system

---

### **Phase 5: Admin Interface Enhancement**
**Duration: 2-3 days**

#### 5.1 Enhanced Promise-Evidence Interface
- [ ] Redesign `@page.tsx` for better UX
- [ ] Add linking rationale display
- [ ] Implement bulk linking capabilities
- [ ] Add evidence preview and context

#### 5.2 Linking Management Features
- [ ] Confidence score visualization
- [ ] Batch approval/rejection workflow
- [ ] Linking audit trail
- [ ] Performance analytics dashboard

**Deliverables:**
- [ ] Enhanced admin interface
- [ ] Bulk linking capabilities
- [ ] Linking analytics dashboard

---

### **Phase 6: Parliament 44 Full Test Run**
**Duration: 2-3 days**

#### 6.1 Data Preparation
- [ ] Clean existing Parliament 44 data
- [ ] Prepare test datasets
- [ ] Set up monitoring and logging

#### 6.2 End-to-End Testing
- [ ] Run complete promise ingestion and enrichment
- [ ] Process all evidence types for Parliament 44
- [ ] Execute evidence-promise linking
- [ ] Validate promise status updates
- [ ] Test admin interface functionality

#### 6.3 Performance Validation
- [ ] Measure processing times and costs
- [ ] Validate linking accuracy
- [ ] Test system scalability
- [ ] Generate comprehensive test report

**Deliverables:**
- [ ] Complete Parliament 44 test dataset
- [ ] Performance validation report
- [ ] Production readiness assessment

---

## Technical Specifications

### Technology Stack Updates
- **LLM Framework**: Langchain
- **LLM Provider**: Google Gemini
- **Database**: Firebase Firestore
- **Frontend**: Next.js with TypeScript
- **Processing**: Python with asyncio

### Data Model Changes
```typescript
// Promise Document (standardized fields)
interface Promise {
  explanation_enriched_at: Timestamp;  // Removed 'dev_' prefix
  linking_rationale?: string;
  status: 'identified' | 'in_progress' | 'completed' | 'stalled';
  linked_evidence_ids: string[];
  // ... other fields
}

// Evidence Document (enhanced)
interface Evidence {
  promise_linking_rationale?: string;  // New field
  linking_confidence_score?: number;   // New field
  linked_promise_ids: string[];
  // ... other fields
}
```

### Performance Requirements
- Promise ingestion: <2s per promise (including enrichments)
- Evidence processing: <5s per evidence item
- Evidence-promise linking: >85% accuracy
- Admin interface: <3s page load times
- Bulk operations: Support 100+ items

---

## Risk Assessment & Mitigation

### High Risk Items
1. **Data Migration**: Field renaming may break existing functionality
   - *Mitigation*: Create comprehensive migration scripts and backup strategy

2. **LLM Cost Escalation**: Comprehensive processing may increase costs
   - *Mitigation*: Implement cost monitoring and optimization strategies

3. **Performance Degradation**: Consolidated pipeline may slow processing
   - *Mitigation*: Implement async processing and progress tracking

### Medium Risk Items
1. **Langchain Learning Curve**: Team familiarization needed
2. **Interface Redesign**: User workflow disruption
3. **Testing Data Quality**: Parliament 44 data may have inconsistencies

---

## Next Steps

**Immediate Actions:**
1. Review and approve this PRD
2. Set up development environment for Langchain
3. Begin Phase 1: Field naming standardization
4. Create backup of current Parliament 44 data

**Phase 1 Kickoff Tasks:**
1. Audit all current field names with `dev_` prefixes
2. Create field mapping documentation
3. Design migration strategy
4. Set up Langchain development environment 