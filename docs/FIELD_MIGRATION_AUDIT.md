# Field Migration Audit - Dev Prefix Removal

## Executive Summary
**Objective**: Remove all `dev_` prefixes from field names to prepare for production deployment  
**Files Affected**: 3 Python scripts  
**Fields Identified**: 6 unique dev_ fields  
**Status**: ✅ AUDIT COMPLETE

---

## Fields Identified for Migration

### 1. Promise Enrichment Fields
**File**: `scripts/enrich_promises_with_explanation.py`

| Current Field | New Field | Purpose | Collection |
|---------------|-----------|---------|------------|
| `dev_explanation_enriched_at` | `explanation_enriched_at` | Timestamp when explanation was enriched | promises |
| `dev_explanation_enrichment_model` | `explanation_enrichment_model` | LLM model used for enrichment | promises |
| `dev_explanation_enrichment_status` | `explanation_enrichment_status` | Status of enrichment process | promises |

**Usage Locations**:
- Line 356: `"dev_explanation_enriched_at": firestore.SERVER_TIMESTAMP`
- Line 357: `"dev_explanation_enrichment_model": LLM_MODEL_NAME`
- Line 358: `"dev_explanation_enrichment_status": "processed"`
- Line 492: `"dev_explanation_enrichment_status": "failed_llm_generation"`
- Line 493: `"dev_explanation_enriched_at": firestore.SERVER_TIMESTAMP`

### 2. Evidence Linking Fields  
**File**: `scripts/linking_jobs/link_evidence_to_promises.py`

| Current Field | New Field | Purpose | Collection |
|---------------|-----------|---------|------------|
| `dev_linking_status` | `linking_status` | Status of evidence linking process | evidence_items |
| `dev_linking_processed_at` | `linking_processed_at` | Timestamp when linking was processed | evidence_items |
| `dev_linking_error_message` | `linking_error_message` | Error message if linking fails | evidence_items |

**Usage Locations**:
- Line 175: `filter=firestore.FieldFilter("dev_linking_status", "in", [None, "pending_linking"])`
- Line 491: `'dev_linking_status': status`
- Line 492: `'dev_linking_processed_at': firestore.SERVER_TIMESTAMP`
- Line 496: `update_data['dev_linking_error_message'] = error_message[:500]`

### 3. Promise Processing Fields
**File**: `scripts/link_evidence_to_promises.py`

| Current Field | New Field | Purpose | Collection |
|---------------|-----------|---------|------------|
| `dev_evidence_linking_status` | `evidence_linking_status` | General status for promise linking process | promises |

**Usage Locations**:
- Line 519: `"dev_evidence_linking_status": "processed"`

---

## Migration Strategy

### Phase 1.1: Script Updates (HIGH PRIORITY)
Update all scripts to use standardized field names:

#### File 1: `scripts/enrich_promises_with_explanation.py`
```python
# Changes needed:
- "dev_explanation_enriched_at" → "explanation_enriched_at"
- "dev_explanation_enrichment_model" → "explanation_enrichment_model"  
- "dev_explanation_enrichment_status" → "explanation_enrichment_status"
```

#### File 2: `scripts/linking_jobs/link_evidence_to_promises.py`
```python
# Changes needed:
- "dev_linking_status" → "linking_status"
- "dev_linking_processed_at" → "linking_processed_at"
- "dev_linking_error_message" → "linking_error_message"
```

#### File 3: `scripts/link_evidence_to_promises.py`
```python
# Changes needed:
- "dev_evidence_linking_status" → "evidence_linking_status"
```

### Phase 1.2: Data Migration Script
Create Firestore field renaming script to migrate existing data:

**Collections to update**:
- `promises` collection: 4 fields
- `evidence_items` collection: 3 fields

**Migration approach**:
1. Backup existing data
2. Read all documents in each collection
3. Copy dev_ field values to new field names
4. Remove dev_ fields
5. Validate migration success

### Phase 1.3: Admin Interface Updates
Check if any admin interface components reference these fields:
- Search frontend code for field references
- Update any forms or displays that show these fields

---

## Implementation Plan

### Step 1: Update Scripts (Today)
- [x] **1.1.1** Update `enrich_promises_with_explanation.py`
- [x] **1.1.2** Update `linking_jobs/link_evidence_to_promises.py`  
- [x] **1.1.3** Update `link_evidence_to_promises.py`

### Step 2: Create Migration Script (Today)
- [ ] **1.2.1** Create `migrate_dev_fields.py` script
- [ ] **1.2.2** Add backup functionality
- [ ] **1.2.3** Add rollback capability
- [ ] **1.2.4** Test on small dataset

### Step 3: Frontend Audit (Tomorrow)
- [ ] **1.3.1** Search frontend code for dev_ field references
- [ ] **1.3.2** Update any admin interface components
- [ ] **1.3.3** Test admin interface functionality

### Step 4: Production Migration (After Testing)
- [ ] **1.4.1** Backup production data
- [ ] **1.4.2** Run migration script on production
- [ ] **1.4.3** Validate migration results
- [ ] **1.4.4** Deploy updated scripts

---

## Risk Assessment

### Low Risk ✅
- Script updates: Simple find/replace operations
- Data migration: Non-destructive (creates new fields first)

### Medium Risk ⚠️
- Frontend integration: May need UI updates if fields are displayed
- Admin workflows: May temporarily disrupt linking workflows

### Mitigation Strategies
1. **Backup first**: Complete data backup before any changes
2. **Incremental approach**: Update scripts first, migrate data second
3. **Rollback plan**: Keep dev_ fields during transition period
4. **Testing**: Test on development environment first

---

## Success Criteria
- [x] All dev_ field usages identified and documented
- [ ] All scripts updated to use standard field names
- [ ] Data migration script created and tested
- [ ] All existing data migrated successfully
- [ ] No dev_ fields remain in codebase
- [ ] All functionality working with new field names

**Estimated Completion**: End of day today for scripts + migration script 