# Promise Tracker Pipeline Restructuring Plan

## Executive Summary

This document outlines a comprehensive restructuring of the Promise Tracker data pipeline to improve maintainability, reliability, and orchestration capabilities. The new architecture replaces the current subprocess-based approach with a robust, class-based system that provides better error handling, monitoring, and modularity.

## Current State Analysis

### Existing Structure Issues
- **Scattered Organization**: Scripts spread across multiple directories (`scripts/`, `processing_jobs/`, `ingestion_jobs/`, `utilities/`)
- **Subprocess Fragility**: Current Cloud Run implementation uses subprocess calls, making error handling and monitoring difficult
- **Manual Coordination**: No automatic triggering between pipeline stages
- **Inconsistent Patterns**: Each script follows different patterns for error handling, logging, and configuration
- **Mixed Responsibilities**: Some scripts handle multiple concerns (ingestion + processing)

### Current Data Flow
1. **Ingestion**: 4 sources (Canada News, LEGISinfo, OIC, Gazette) → Raw collections
2. **Processing**: Raw data → Evidence items (with LLM enrichment)
3. **Linking**: Evidence items → Promise links + Progress scoring

## Proposed New Architecture

### Directory Structure
```
PromiseTracker/
├── pipeline/                          # New: Core pipeline orchestration
│   ├── __init__.py
│   ├── orchestrator.py               # Main Cloud Run entry point
│   ├── config/
│   │   ├── jobs.yaml                 # Job definitions and dependencies
│   │   └── environments.yaml        # Environment-specific configs
│   ├── core/
│   │   ├── base_job.py              # Abstract base class for all jobs
│   │   ├── job_runner.py            # Job execution engine
│   │   ├── error_handler.py         # Centralized error handling
│   │   └── monitoring.py            # Logging and metrics
│   └── stages/
│       ├── ingestion/               # Stage 1: Data ingestion
│       │   ├── base_ingestion.py    # Base class for ingestion jobs
│       │   ├── canada_news.py
│       │   ├── legisinfo_bills.py
│       │   ├── orders_in_council.py
│       │   └── canada_gazette.py
│       ├── processing/              # Stage 2: Raw data processing
│       │   ├── base_processor.py    # Base class for processing jobs
│       │   ├── news_processor.py
│       │   ├── bill_processor.py
│       │   ├── oic_processor.py
│       │   └── gazette_processor.py
│       └── linking/                 # Stage 3: Evidence linking & scoring
│           ├── evidence_linker.py
│           ├── progress_scorer.py
│           └── promise_enricher.py
├── lib/                             # Shared libraries (existing)
├── prompts/                         # Existing prompts directory
├── utilities/                       # Standalone utility scripts
└── legacy/                          # Deprecated scripts (to be removed)
```

## Key Design Principles

### 1. **Resilience First**
- Each job is isolated and can fail independently
- Automatic retry logic with exponential backoff
- Comprehensive error handling and logging
- Graceful degradation when dependencies fail

### 2. **Clear Separation of Concerns**
- **Ingestion**: Only responsible for fetching and storing raw data
- **Processing**: Only responsible for transforming raw data to evidence items
- **Linking**: Only responsible for connecting evidence to promises and scoring

### 3. **Configuration-Driven**
- All job definitions, dependencies, and schedules in YAML
- Environment-specific configurations
- Easy to modify without code changes

### 4. **Automatic Orchestration**
- Jobs automatically trigger downstream dependencies
- Conditional triggering based on results (e.g., only if new items found)
- Parallel execution where possible

### 5. **Comprehensive Monitoring**
- Standardized job result tracking
- Execution history in Firestore
- Detailed logging and metrics
- Health check endpoints

## Implementation Phases

### Phase 1: Core Infrastructure (Week 1) ✅ STARTED
- [x] Create base job classes and interfaces
- [x] Implement job runner with timeout/retry logic
- [x] Create pipeline orchestrator
- [x] Set up configuration system
- [ ] Implement monitoring and logging framework
- [ ] Create error handling utilities

### Phase 2: Ingestion Layer (Week 2)
- [ ] Migrate Canada News ingestion
- [ ] Migrate LEGISinfo Bills ingestion  
- [ ] Migrate Orders in Council ingestion
- [ ] Migrate Canada Gazette ingestion
- [ ] Add RSS monitoring capabilities
- [ ] Implement duplicate detection

### Phase 3: Processing Layer (Week 3)
- [ ] Create base processor class
- [ ] Migrate news processing (LLM analysis)
- [ ] Migrate bill processing
- [ ] Migrate OIC processing
- [ ] Migrate gazette processing
- [ ] Integrate with existing langchain framework

### Phase 4: Linking Layer (Week 4)
- [ ] Migrate evidence linking logic
- [ ] Migrate progress scoring
- [ ] Migrate promise enrichment
- [ ] Implement batch processing optimizations

### Phase 5: Cloud Run Integration (Week 5)
- [ ] Update Dockerfile for new structure
- [ ] Update cloudbuild.yaml
- [ ] Create Cloud Scheduler configurations
- [ ] Set up monitoring dashboards
- [ ] Performance testing and optimization

### Phase 6: Migration and Cleanup (Week 6)
- [ ] Gradual migration from old to new system
- [ ] Data validation and testing
- [ ] Remove deprecated scripts
- [ ] Update documentation
- [ ] Team training

## Job Configuration Example

```yaml
# From pipeline/config/jobs.yaml
stages:
  ingestion:
    jobs:
      canada_news:
        class: "pipeline.stages.ingestion.canada_news.CanadaNewsIngestion"
        schedule: "0 */2 * * *"  # Every 2 hours
        timeout_minutes: 30
        retry_attempts: 3
        triggers:
          - stage: "processing"
            job: "news_processor"
            condition: "new_items_found"
```

## API Endpoints

### New Cloud Run Endpoints
- `GET /` - Health check
- `GET /jobs` - List all available jobs
- `POST /jobs/{stage}/{job_name}` - Execute specific job
- `POST /jobs/batch` - Execute multiple jobs
- `GET /jobs/status` - Get job execution status

### Example Usage
```bash
# Execute Canada News ingestion
curl -X POST https://your-service.run.app/jobs/ingestion/canada_news \
  -H "Content-Type: application/json" \
  -d '{"since_hours": 6}'

# Execute batch of jobs
curl -X POST https://your-service.run.app/jobs/batch \
  -H "Content-Type: application/json" \
  -d '{
    "jobs": [
      {"stage": "ingestion", "job": "canada_news"},
      {"stage": "ingestion", "job": "legisinfo_bills"}
    ]
  }'
```

## Benefits of New Architecture

### 1. **Improved Reliability**
- Jobs can't crash the entire system
- Automatic retries with intelligent backoff
- Better error isolation and recovery

### 2. **Enhanced Monitoring**
- Real-time job status tracking
- Detailed execution history
- Performance metrics and alerting

### 3. **Easier Maintenance**
- Clear separation of concerns
- Consistent patterns across all jobs
- Configuration-driven behavior

### 4. **Better Orchestration**
- Automatic dependency management
- Conditional job triggering
- Parallel execution optimization

### 5. **Improved Testing**
- Each job can be tested in isolation
- Mock dependencies for unit testing
- Integration testing with real data

## Migration Strategy

### 1. **Parallel Development**
- Build new system alongside existing one
- Gradual migration of individual jobs
- Maintain backward compatibility during transition

### 2. **Data Validation**
- Compare outputs between old and new systems
- Validate data integrity during migration
- Rollback capability if issues arise

### 3. **Phased Rollout**
- Start with least critical jobs
- Monitor performance and reliability
- Gradually migrate more critical components

## Scripts to be Deprecated/Removed

### Immediate Removal (Duplicates/Obsolete)
- `scripts/processing_jobs/` - All files (migrated to new structure)
- `scripts/ingestion_jobs/bulk_*.py` - Bulk ingestion scripts
- `scripts/enrich_*.py` - Individual enrichment scripts (consolidated)
- `scripts/link_evidence_to_promises.py` - Replaced by new linking system
- `cloud_run_main.py` - Replaced by pipeline orchestrator

### Move to Utilities
- `scripts/utilities/one-time/` - Keep for historical migrations
- `scripts/migration/` - Keep for data migrations
- Analysis and query scripts - Move to `utilities/analysis/`

### Consolidate
- Multiple promise enrichment scripts → Single `promise_enricher.py`
- Individual processing scripts → Unified processing framework

## Risk Mitigation

### 1. **Rollback Plan**
- Keep existing system running during migration
- Feature flags to switch between old/new systems
- Database backup before major changes

### 2. **Testing Strategy**
- Comprehensive unit tests for all new components
- Integration tests with real data
- Load testing for Cloud Run performance

### 3. **Monitoring**
- Set up alerts for job failures
- Monitor resource usage and performance
- Track data quality metrics

## Success Metrics

### 1. **Reliability**
- Reduce job failure rate by 80%
- Achieve 99.5% uptime for critical jobs
- Decrease manual intervention by 90%

### 2. **Performance**
- Reduce average job execution time by 30%
- Improve resource utilization by 40%
- Enable parallel processing for 50% faster pipeline completion

### 3. **Maintainability**
- Reduce time to add new data sources by 70%
- Decrease debugging time by 60%
- Improve code coverage to 90%

## Next Steps

1. **Complete Phase 1** - Finish core infrastructure components
2. **Create Migration Scripts** - Tools to help transition existing data
3. **Set up Testing Environment** - Isolated environment for validation
4. **Begin Phase 2** - Start migrating ingestion jobs
5. **Stakeholder Review** - Get feedback on new architecture

## Questions for Discussion

1. **Scheduling**: Should we use Cloud Scheduler or implement internal scheduling?
2. **Monitoring**: What level of monitoring detail do we need?
3. **Error Handling**: How should we handle partial failures in batch operations?
4. **Performance**: What are the acceptable timeout limits for each job type?
5. **Security**: Any additional security considerations for the new architecture?

---

*This plan represents a significant improvement in our data pipeline architecture. The modular, resilient design will make the system much easier to maintain and extend while providing better reliability and monitoring capabilities.* 