# Promises Collection Flattening Migration Plan

## Overview
This document outlines the comprehensive plan to migrate from the current nested subcollection structure `promises/{region}/{party}/promise_docs` to a flat structure `promises/promise_docs` with region and party stored as document fields.

## Current Structure Analysis

### Current Structure
```
promises/
├── Canada/
│   ├── LPC/
│   │   ├── promise_doc_1
│   │   ├── promise_doc_2
│   │   └── ...
│   ├── CPC/
│   │   ├── promise_doc_3
│   │   └── ...
│   └── NDP/
│       └── ...
└── [other regions if any]
```

### Target Structure
```
promises/
├── promise_doc_1    (with region_code: "Canada", party: "LPC" fields)
├── promise_doc_2    (with region_code: "Canada", party: "LPC" fields) 
├── promise_doc_3    (with region_code: "Canada", party: "CPC" fields)
└── ...
```

## Migration Strategy

### Phase 1: Pre-Migration Preparation

#### 1.1 Backup Current Data
- **Priority**: CRITICAL
- **Action**: Export all promises data from current structure
- **Script**: Create `backup_promises_data.py`
- **Timeline**: Before any migration begins

#### 1.2 Create Migration Tracking
- **Collection**: `migration_tracking`
- **Purpose**: Track migration progress and status
- **Fields**: 
  - `source_path`: Original document path
  - `target_id`: New flat document ID  
  - `migration_status`: 'pending', 'completed', 'failed'
  - `migration_timestamp`: When migration occurred
  - `error_message`: If failed

#### 1.3 Update Document Schema
- **New Required Fields**:
  - `region_code`: String (e.g., "Canada")
  - `party_code`: String (e.g., "LPC", "CPC", "NDP", "BQ")
- **Document ID Strategy**: Keep existing document IDs or generate new deterministic ones
- **Conflict Resolution**: Handle potential ID conflicts

### Phase 2: Code Updates (Parallel Development)

#### 2.1 Backend Scripts Updates

**Files requiring updates:**

1. **`scripts/common_utils.py`**
   - ✅ Update `get_promise_document_path()` to return flat path
   - ✅ Add `get_legacy_promise_document_path()` for backward compatibility
   - ✅ Update constants and path generation logic

2. **`scripts/link_bills_to_promises.py`**
   - ✅ Replace party loop with single collection query
   - ✅ Add filters for `party_code` and `region_code`
   - ✅ Update promise fetching logic

3. **`scripts/link_evidence_to_promises.py`**
   - ✅ Update promise queries to use flat structure
   - ✅ Add party and region filters to queries

4. **`scripts/rank_promise_priority.py`**
   - ✅ Remove hardcoded party/region path construction
   - ✅ Update base collection reference

5. **`scripts/enrich_tag_new_promise.py`**
   - ✅ Update batch processing to use flat collection
   - ✅ Modify document creation to include region/party fields

6. **`scripts/utilities/update_evidence_references.py`**
   - ✅ Update promise path construction
   - ✅ Modify scanning logic for flat structure

7. **`scripts/utilities/extract_promise_text.py`**
   - ✅ Update collection querying logic

8. **All other scripts** that reference promises collection

#### 2.2 Frontend Updates

**Files requiring updates:**

1. **`lib/data.ts`**
   - ✅ Update `fetchPromisesForDepartment()` function
   - ✅ Replace path construction with direct collection query
   - ✅ Add party and region filters to queries

2. **`app/` components and pages**
   - ✅ Update any direct promises collection references
   - ✅ Modify query logic and filters

3. **Type definitions**
   - ✅ Add `region_code` and `party_code` to PromiseData interface

#### 2.3 Environment Configuration
- **New Environment Variables**:
  - `MIGRATION_MODE`: 'pre', 'during', 'post' migration
  - `PROMISES_FLAT_STRUCTURE`: boolean flag
  - `LEGACY_PROMISES_SUPPORT`: boolean for dual-read support

### Phase 3: Data Migration Execution

#### 3.1 Migration Script Development

**Script**: `migrate_promises_to_flat_structure.py`

**Features**:
- Batch processing (configurable batch size)
- Resume capability (track progress)
- Validation and verification
- Rollback preparation
- Detailed logging and metrics

**Logic**:
```python
for region in regions:
    for party in parties:
        source_collection = f"promises/{region}/{party}"
        for batch in get_documents_in_batches(source_collection):
            for doc in batch:
                new_doc_data = {
                    **doc.data(),
                    'region_code': region,
                    'party_code': party,
                    'migration_metadata': {
                        'migrated_at': firestore.SERVER_TIMESTAMP,
                        'source_path': doc.reference.path,
                        'migration_version': '1.0'
                    }
                }
                # Write to flat collection
                new_doc_ref = db.collection('promises').document(doc.id)
                batch_write.set(new_doc_ref, new_doc_data)
```

#### 3.2 Migration Execution Plan

**Step 1: Dry Run**
- Run migration script in dry-run mode
- Validate data consistency
- Check for ID conflicts
- Estimate migration time

**Step 2: Staged Migration**
- Migrate one party at a time (start with smallest dataset)
- Verify data integrity after each party
- Run validation scripts

**Step 3: Full Migration**
- Migrate remaining parties
- Run comprehensive validation
- Update migration tracking

#### 3.3 Validation Scripts

**Script**: `validate_migration.py`

**Validations**:
- Document count matches (source vs target)
- All required fields present
- No data corruption
- Index compatibility
- Query performance validation

### Phase 4: Deployment and Cleanup

#### 4.1 Deployment Strategy

**Option A: Blue-Green Deployment**
- Deploy new code with feature flag disabled
- Run migration
- Enable feature flag
- Verify functionality
- Clean up old data

**Option B: Gradual Migration**
- Deploy dual-read capability
- Migrate data gradually
- Switch to write-to-new mode
- Switch to read-from-new mode
- Clean up old data

#### 4.2 Firestore Security Rules Update

**Current Rules** (assumed):
```javascript
match /promises/{region}/{party}/{promiseId} {
  allow read, write: if /* conditions */;
}
```

**New Rules**:
```javascript
match /promises/{promiseId} {
  allow read, write: if /* conditions */;
}
```

#### 4.3 Index Management

**Required New Indexes**:
- `party_code`, `region_code`, `parliament_session_id`
- `responsible_department_lead`, `party_code`, `bc_promise_rank`
- `region_code`, `party_code`, `date_issued`

**Cleanup Old Indexes**:
- Remove subcollection-specific indexes

### Phase 5: Testing and Validation

#### 5.1 Testing Strategy

**Unit Tests**:
- New query functions
- Migration logic
- Data validation functions

**Integration Tests**:
- End-to-end promise fetching
- Evidence linking
- Frontend functionality

**Performance Tests**:
- Query performance comparison
- Index effectiveness
- Batch operation efficiency

#### 5.2 Rollback Plan

**Preparation**:
- Keep original data until validation complete
- Document rollback procedures
- Test rollback scripts

**Rollback Triggers**:
- Data integrity issues
- Performance degradation
- Critical functionality failures

### Phase 6: Post-Migration Cleanup

#### 6.1 Data Cleanup
- Archive or delete old subcollection data
- Clean up migration tracking data
- Remove backup collections

#### 6.2 Code Cleanup
- Remove legacy code paths
- Clean up feature flags
- Update documentation

#### 6.3 Monitoring Setup
- Query performance monitoring
- Error rate monitoring
- Data consistency checks

## Implementation Timeline

### Week 1: Preparation
- [ ] Create backup scripts
- [ ] Set up migration tracking
- [ ] Create validation scripts

### Week 2: Code Updates
- [ ] Update backend scripts
- [ ] Update frontend code
- [ ] Update security rules (prepare)

### Week 3: Migration Development
- [ ] Develop migration scripts
- [ ] Create rollback procedures
- [ ] Test migration in dev environment

### Week 4: Testing
- [ ] Run comprehensive tests
- [ ] Performance validation
- [ ] Dry-run migration

### Week 5: Production Migration
- [ ] Execute migration
- [ ] Validate results
- [ ] Deploy updated code

### Week 6: Cleanup
- [ ] Clean up old data
- [ ] Remove temporary code
- [ ] Update documentation

## Risk Mitigation

### High Risks
1. **Data Loss**: Comprehensive backups and validation
2. **Downtime**: Blue-green deployment or feature flags
3. **Performance Issues**: Index optimization and testing
4. **ID Conflicts**: Conflict detection and resolution logic

### Medium Risks
1. **Migration Failures**: Resume capability and batch processing
2. **Query Incompatibility**: Thorough testing and gradual rollout
3. **Code Bugs**: Comprehensive testing and rollback plan

## Success Criteria

### Technical Success
- [ ] All promises migrated successfully
- [ ] No data loss or corruption
- [ ] Query performance maintained or improved
- [ ] All functionality working correctly

### Business Success
- [ ] Improved code maintainability
- [ ] Simplified query logic
- [ ] Better scalability
- [ ] Reduced development complexity

## Notes and Considerations

### Document ID Strategy
- **Option 1**: Keep existing document IDs (may have conflicts)
- **Option 2**: Generate new deterministic IDs based on content
- **Option 3**: Use migration mapping for ID translation

### Backward Compatibility
- Consider maintaining read access to old structure during transition
- Use feature flags for gradual rollout
- Keep migration metadata for traceability

### Performance Considerations
- New queries may require different indexes
- Consider query patterns and optimization
- Monitor performance impact during migration 