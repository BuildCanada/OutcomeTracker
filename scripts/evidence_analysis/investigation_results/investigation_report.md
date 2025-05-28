
# Backup Data Investigation Report
Generated: 2025-05-28T14:21:33.324398+00:00

## Executive Summary

### Backup Data Analysis
- **Backup Promises**: 1,374 total, 142 with links
- **Backup Evidence**: 2,992 total, 1,688 with links
- **Successful Links**: 2,916 total links found

### Current Data Analysis
- **Current Promises**: 1,110 total, 0 with links
- **Current Evidence**: 6,671 total, 0 with links

### Key Findings

🚨 **CRITICAL ISSUE**: Backup data shows {backup_promise_links:,} promises with links, but current data shows 0 links.
This indicates a significant regression in the linking system.

🚨 **CRITICAL ISSUE**: Backup data shows 1,688 evidence items with links, but current data shows 0 links.


## Detailed Analysis

### Successful Links in Backup
- **Total Links**: 2,916
- **Bidirectional Links**: 2,832
- **Bill Links**: 1,528

### Links by Evidence Type
- **Bill Event (LEGISinfo)**: 1,528 links
- **Canada Gazette**: 27 links
- **Canada News Centre**: 727 links
- **Committee Reports**: 14 links
- **Departmental Publications**: 94 links
- **Finance Canada**: 487 links
- **Orders in Council**: 24 links
- **Other**: 15 links


### Links by Parliament Session
- **Session 44**: 2,212 links
- **Session 45**: 704 links


## Data Structure Comparison

### Promise Fields
- **Backup Only**: 6 fields
- **Current Only**: 15 fields
- **Common**: 32 fields

### Evidence Fields
- **Backup Only**: 3 fields
- **Current Only**: 7 fields
- **Common**: 10 fields

## Test Cases Generated

**Total Test Cases**: 0

### High Priority Test Cases (Bill Links)


## Recommendations

1. No matching test cases found - data structure may have changed significantly
2. Current promises have no links - linking system may not be working
3. Current evidence has no links - check promise_ids field population
4. Backup had 2916 successful links - investigate why current system isn't creating links


## Next Steps

### Immediate Actions
1. **Run Test Cases**: Use the generated test cases to verify linking algorithms
2. **Data Migration Check**: Verify if data migration preserved linking fields
3. **Algorithm Testing**: Test both consolidated_evidence_linking.py and link_evidence_to_promises.py with known good cases

### Investigation Actions
1. **Field Mapping**: Check if linking fields were renamed or restructured during migration
2. **Data Integrity**: Verify that promise and evidence IDs are consistent between backup and current
3. **Algorithm Parameters**: Test if similarity thresholds or other parameters need adjustment

### Testing Protocol
1. Select 5-10 high-priority test cases
2. Run linking algorithms on these specific promise-evidence pairs
3. Compare results with expected outcomes from backup data
4. Adjust algorithm parameters based on results
5. Validate with broader dataset

## Files Generated
- `backup_investigation.json`: Complete investigation data
- `test_cases.csv`: Test cases for algorithm validation
- `investigation_report.md`: This report
