#!/usr/bin/env python3
"""
Data Integrity Check Script
Task 1.2: Data Integrity Assessment

This script validates the integrity of promise-evidence links and identifies
data inconsistencies, orphaned references, and other quality issues.
"""

import asyncio
import json
import os
from datetime import datetime, timezone
from collections import defaultdict, Counter
from typing import Dict, List, Any, Set, Tuple
import pandas as pd

# Firebase imports
import firebase_admin
from firebase_admin import credentials, firestore

# Initialize Firebase Admin if not already done
try:
    firebase_admin.get_app()
except ValueError:
    firebase_admin.initialize_app()

db = firestore.client()

class DataIntegrityChecker:
    """Checks data integrity for promise-evidence linking system."""
    
    def __init__(self):
        self.db = db
        self.issues = {
            'timestamp': datetime.now(timezone.utc).isoformat(),
            'bidirectional_inconsistencies': [],
            'orphaned_references': [],
            'duplicate_links': [],
            'missing_fields': [],
            'date_format_issues': [],
            'department_standardization': [],
            'summary': {}
        }
        self.fixes = []
        
    async def run_integrity_check(self) -> Dict[str, Any]:
        """Run complete data integrity check."""
        print("🔍 Starting Data Integrity Check...")
        print("=" * 60)
        
        # Step 1: Fetch data
        print("📊 Step 1: Fetching data...")
        promises_data = await self.fetch_promises_data()
        evidence_data = await self.fetch_evidence_data()
        
        # Step 2: Check bidirectional consistency
        print("🔗 Step 2: Checking bidirectional link consistency...")
        await self.check_bidirectional_consistency(promises_data, evidence_data)
        
        # Step 3: Check for orphaned references
        print("👻 Step 3: Checking for orphaned references...")
        await self.check_orphaned_references(promises_data, evidence_data)
        
        # Step 4: Check for duplicate links
        print("🔄 Step 4: Checking for duplicate links...")
        await self.check_duplicate_links(promises_data, evidence_data)
        
        # Step 5: Check required fields
        print("📋 Step 5: Checking required fields...")
        await self.check_required_fields(promises_data, evidence_data)
        
        # Step 6: Check date formats
        print("📅 Step 6: Checking date formats...")
        await self.check_date_formats(promises_data, evidence_data)
        
        # Step 7: Check department standardization
        print("🏛️ Step 7: Checking department standardization...")
        await self.check_department_standardization(promises_data, evidence_data)
        
        # Step 8: Generate summary and fixes
        print("📈 Step 8: Generating summary and fixes...")
        await self.generate_summary_and_fixes()
        
        # Step 9: Export results
        print("💾 Step 9: Exporting results...")
        await self.export_results()
        
        print("✅ Integrity check complete!")
        return self.issues
    
    async def fetch_promises_data(self) -> List[Dict[str, Any]]:
        """Fetch all promises from Firestore."""
        promises_ref = self.db.collection('promises')
        promises_docs = promises_ref.stream()
        
        promises_data = []
        for doc in promises_docs:
            data = doc.to_dict()
            data['id'] = doc.id
            promises_data.append(data)
        
        print(f"  ✅ Fetched {len(promises_data)} promises")
        return promises_data
    
    async def fetch_evidence_data(self) -> List[Dict[str, Any]]:
        """Fetch all evidence items from Firestore."""
        evidence_ref = self.db.collection('evidence_items')
        evidence_docs = evidence_ref.stream()
        
        evidence_data = []
        for doc in evidence_docs:
            data = doc.to_dict()
            data['id'] = doc.id
            evidence_data.append(data)
        
        print(f"  ✅ Fetched {len(evidence_data)} evidence items")
        return evidence_data
    
    async def check_bidirectional_consistency(self, promises_data: List[Dict[str, Any]], 
                                            evidence_data: List[Dict[str, Any]]):
        """Check consistency between linked_evidence_ids and promise_ids."""
        print("  🔗 Analyzing bidirectional link consistency...")
        
        # Create lookup sets
        evidence_ids = {item['id'] for item in evidence_data}
        promise_ids = {item['id'] for item in promises_data}
        
        # Collect all links
        promise_to_evidence = {}  # promise_id -> set of evidence_ids
        evidence_to_promise = {}  # evidence_id -> set of promise_ids
        
        # From promises side (linked_evidence_ids)
        for promise in promises_data:
            promise_id = promise['id']
            linked_evidence_ids = promise.get('linked_evidence_ids', [])
            if linked_evidence_ids:
                promise_to_evidence[promise_id] = set(linked_evidence_ids)
        
        # From evidence side (promise_ids)
        for evidence in evidence_data:
            evidence_id = evidence['id']
            promise_ids_list = evidence.get('promise_ids', [])
            if promise_ids_list:
                evidence_to_promise[evidence_id] = set(promise_ids_list)
        
        # Check consistency
        inconsistencies = []
        
        # Check promise -> evidence links
        for promise_id, evidence_ids_set in promise_to_evidence.items():
            for evidence_id in evidence_ids_set:
                # Check if evidence exists
                if evidence_id not in evidence_ids:
                    inconsistencies.append({
                        'type': 'orphaned_evidence_reference',
                        'promise_id': promise_id,
                        'evidence_id': evidence_id,
                        'description': f"Promise {promise_id} references non-existent evidence {evidence_id}"
                    })
                    continue
                
                # Check if evidence links back to promise
                if evidence_id in evidence_to_promise:
                    if promise_id not in evidence_to_promise[evidence_id]:
                        inconsistencies.append({
                            'type': 'missing_reverse_link',
                            'promise_id': promise_id,
                            'evidence_id': evidence_id,
                            'description': f"Promise {promise_id} links to evidence {evidence_id}, but evidence doesn't link back"
                        })
                else:
                    inconsistencies.append({
                        'type': 'missing_reverse_link',
                        'promise_id': promise_id,
                        'evidence_id': evidence_id,
                        'description': f"Promise {promise_id} links to evidence {evidence_id}, but evidence has no promise_ids"
                    })
        
        # Check evidence -> promise links
        for evidence_id, promise_ids_set in evidence_to_promise.items():
            for promise_id in promise_ids_set:
                # Check if promise exists
                if promise_id not in promise_ids:
                    inconsistencies.append({
                        'type': 'orphaned_promise_reference',
                        'evidence_id': evidence_id,
                        'promise_id': promise_id,
                        'description': f"Evidence {evidence_id} references non-existent promise {promise_id}"
                    })
                    continue
                
                # Check if promise links back to evidence
                if promise_id in promise_to_evidence:
                    if evidence_id not in promise_to_evidence[promise_id]:
                        inconsistencies.append({
                            'type': 'missing_forward_link',
                            'evidence_id': evidence_id,
                            'promise_id': promise_id,
                            'description': f"Evidence {evidence_id} links to promise {promise_id}, but promise doesn't link back"
                        })
                else:
                    inconsistencies.append({
                        'type': 'missing_forward_link',
                        'evidence_id': evidence_id,
                        'promise_id': promise_id,
                        'description': f"Evidence {evidence_id} links to promise {promise_id}, but promise has no linked_evidence_ids"
                    })
        
        self.issues['bidirectional_inconsistencies'] = inconsistencies
        print(f"    ⚠️  Found {len(inconsistencies)} bidirectional inconsistencies")
    
    async def check_orphaned_references(self, promises_data: List[Dict[str, Any]], 
                                      evidence_data: List[Dict[str, Any]]):
        """Check for references to non-existent documents."""
        print("  👻 Checking for orphaned references...")
        
        # Create ID sets
        evidence_ids = {item['id'] for item in evidence_data}
        promise_ids = {item['id'] for item in promises_data}
        
        orphaned = []
        
        # Check promise references to evidence
        for promise in promises_data:
            promise_id = promise['id']
            linked_evidence_ids = promise.get('linked_evidence_ids', [])
            
            for evidence_id in linked_evidence_ids:
                if evidence_id not in evidence_ids:
                    orphaned.append({
                        'type': 'orphaned_evidence_in_promise',
                        'promise_id': promise_id,
                        'evidence_id': evidence_id,
                        'field': 'linked_evidence_ids',
                        'description': f"Promise {promise_id} references non-existent evidence {evidence_id}"
                    })
        
        # Check evidence references to promises
        for evidence in evidence_data:
            evidence_id = evidence['id']
            promise_ids_list = evidence.get('promise_ids', [])
            
            for promise_id in promise_ids_list:
                if promise_id not in promise_ids:
                    orphaned.append({
                        'type': 'orphaned_promise_in_evidence',
                        'evidence_id': evidence_id,
                        'promise_id': promise_id,
                        'field': 'promise_ids',
                        'description': f"Evidence {evidence_id} references non-existent promise {promise_id}"
                    })
        
        self.issues['orphaned_references'] = orphaned
        print(f"    👻 Found {len(orphaned)} orphaned references")
    
    async def check_duplicate_links(self, promises_data: List[Dict[str, Any]], 
                                  evidence_data: List[Dict[str, Any]]):
        """Check for duplicate links within arrays."""
        print("  🔄 Checking for duplicate links...")
        
        duplicates = []
        
        # Check duplicates in promise linked_evidence_ids
        for promise in promises_data:
            promise_id = promise['id']
            linked_evidence_ids = promise.get('linked_evidence_ids', [])
            
            if len(linked_evidence_ids) != len(set(linked_evidence_ids)):
                duplicate_ids = [id for id in set(linked_evidence_ids) 
                               if linked_evidence_ids.count(id) > 1]
                duplicates.append({
                    'type': 'duplicate_evidence_in_promise',
                    'promise_id': promise_id,
                    'field': 'linked_evidence_ids',
                    'duplicate_ids': duplicate_ids,
                    'description': f"Promise {promise_id} has duplicate evidence IDs: {duplicate_ids}"
                })
        
        # Check duplicates in evidence promise_ids
        for evidence in evidence_data:
            evidence_id = evidence['id']
            promise_ids_list = evidence.get('promise_ids', [])
            
            if len(promise_ids_list) != len(set(promise_ids_list)):
                duplicate_ids = [id for id in set(promise_ids_list) 
                               if promise_ids_list.count(id) > 1]
                duplicates.append({
                    'type': 'duplicate_promise_in_evidence',
                    'evidence_id': evidence_id,
                    'field': 'promise_ids',
                    'duplicate_ids': duplicate_ids,
                    'description': f"Evidence {evidence_id} has duplicate promise IDs: {duplicate_ids}"
                })
        
        self.issues['duplicate_links'] = duplicates
        print(f"    🔄 Found {len(duplicates)} duplicate link issues")
    
    async def check_required_fields(self, promises_data: List[Dict[str, Any]], 
                                  evidence_data: List[Dict[str, Any]]):
        """Check for missing required fields."""
        print("  📋 Checking required fields...")
        
        missing_fields = []
        
        # Required fields for promises
        promise_required_fields = [
            'title', 'description', 'party_code', 'parliament_session_id',
            'responsible_department_lead', 'date_issued'
        ]
        
        for promise in promises_data:
            promise_id = promise['id']
            for field in promise_required_fields:
                if field not in promise or promise[field] is None or promise[field] == '':
                    missing_fields.append({
                        'type': 'missing_promise_field',
                        'document_id': promise_id,
                        'collection': 'promises',
                        'field': field,
                        'description': f"Promise {promise_id} missing required field: {field}"
                    })
        
        # Required fields for evidence
        evidence_required_fields = [
            'title', 'evidence_source_type', 'evidence_date', 'parliament_session_id'
        ]
        
        for evidence in evidence_data:
            evidence_id = evidence['id']
            for field in evidence_required_fields:
                if field not in evidence or evidence[field] is None or evidence[field] == '':
                    missing_fields.append({
                        'type': 'missing_evidence_field',
                        'document_id': evidence_id,
                        'collection': 'evidence_items',
                        'field': field,
                        'description': f"Evidence {evidence_id} missing required field: {field}"
                    })
        
        self.issues['missing_fields'] = missing_fields
        print(f"    📋 Found {len(missing_fields)} missing field issues")
    
    async def check_date_formats(self, promises_data: List[Dict[str, Any]], 
                               evidence_data: List[Dict[str, Any]]):
        """Check date format consistency and validity."""
        print("  📅 Checking date formats...")
        
        date_issues = []
        
        # Check promise dates
        for promise in promises_data:
            promise_id = promise['id']
            date_fields = ['date_issued', 'date_updated']
            
            for field in date_fields:
                if field in promise and promise[field] is not None:
                    date_value = promise[field]
                    issue = self._validate_date_format(date_value, promise_id, 'promises', field)
                    if issue:
                        date_issues.append(issue)
        
        # Check evidence dates
        for evidence in evidence_data:
            evidence_id = evidence['id']
            date_fields = ['evidence_date', 'date_created', 'date_updated']
            
            for field in date_fields:
                if field in evidence and evidence[field] is not None:
                    date_value = evidence[field]
                    issue = self._validate_date_format(date_value, evidence_id, 'evidence_items', field)
                    if issue:
                        date_issues.append(issue)
        
        self.issues['date_format_issues'] = date_issues
        print(f"    📅 Found {len(date_issues)} date format issues")
    
    def _validate_date_format(self, date_value: Any, doc_id: str, collection: str, field: str) -> Dict[str, Any]:
        """Validate a single date value."""
        try:
            if hasattr(date_value, 'timestamp'):
                # Firestore Timestamp - this is good
                return None
            elif isinstance(date_value, str):
                # Try to parse string date
                datetime.fromisoformat(date_value.replace('Z', '+00:00'))
                return None
            else:
                return {
                    'type': 'invalid_date_type',
                    'document_id': doc_id,
                    'collection': collection,
                    'field': field,
                    'value': str(date_value),
                    'value_type': type(date_value).__name__,
                    'description': f"{collection}/{doc_id}.{field} has invalid date type: {type(date_value).__name__}"
                }
        except Exception as e:
            return {
                'type': 'unparseable_date',
                'document_id': doc_id,
                'collection': collection,
                'field': field,
                'value': str(date_value),
                'error': str(e),
                'description': f"{collection}/{doc_id}.{field} has unparseable date: {date_value}"
            }
    
    async def check_department_standardization(self, promises_data: List[Dict[str, Any]], 
                                             evidence_data: List[Dict[str, Any]]):
        """Check for department name standardization issues."""
        print("  🏛️ Checking department standardization...")
        
        # Collect all department names
        promise_departments = set()
        evidence_departments = set()
        
        for promise in promises_data:
            dept = promise.get('responsible_department_lead')
            if dept:
                promise_departments.add(dept)
        
        for evidence in evidence_data:
            depts = evidence.get('linked_departments', [])
            for dept in depts:
                evidence_departments.add(dept)
        
        # Find potential standardization issues
        all_departments = promise_departments.union(evidence_departments)
        standardization_issues = []
        
        # Simple similarity check for potential duplicates
        dept_list = list(all_departments)
        for i, dept1 in enumerate(dept_list):
            for dept2 in dept_list[i+1:]:
                if self._departments_similar(dept1, dept2):
                    standardization_issues.append({
                        'type': 'similar_department_names',
                        'department1': dept1,
                        'department2': dept2,
                        'in_promises': dept1 in promise_departments and dept2 in promise_departments,
                        'in_evidence': dept1 in evidence_departments and dept2 in evidence_departments,
                        'description': f"Potentially similar department names: '{dept1}' and '{dept2}'"
                    })
        
        self.issues['department_standardization'] = standardization_issues
        print(f"    🏛️ Found {len(standardization_issues)} potential department standardization issues")
    
    def _departments_similar(self, dept1: str, dept2: str) -> bool:
        """Check if two department names are similar (potential duplicates)."""
        # Simple similarity check
        dept1_clean = dept1.lower().replace(' ', '').replace('-', '').replace('&', 'and')
        dept2_clean = dept2.lower().replace(' ', '').replace('-', '').replace('&', 'and')
        
        # Check if one is contained in the other
        if dept1_clean in dept2_clean or dept2_clean in dept1_clean:
            return True
        
        # Check for common abbreviations
        abbreviations = {
            'ministry': 'min',
            'department': 'dept',
            'government': 'gov',
            'british columbia': 'bc',
            'and': '&'
        }
        
        for full, abbrev in abbreviations.items():
            dept1_abbrev = dept1_clean.replace(full, abbrev)
            dept2_abbrev = dept2_clean.replace(full, abbrev)
            if dept1_abbrev == dept2_abbrev:
                return True
        
        return False
    
    async def generate_summary_and_fixes(self):
        """Generate summary statistics and automated fix suggestions."""
        print("  📈 Generating summary and fix suggestions...")
        
        # Count issues by type
        total_issues = (
            len(self.issues['bidirectional_inconsistencies']) +
            len(self.issues['orphaned_references']) +
            len(self.issues['duplicate_links']) +
            len(self.issues['missing_fields']) +
            len(self.issues['date_format_issues']) +
            len(self.issues['department_standardization'])
        )
        
        self.issues['summary'] = {
            'total_issues': total_issues,
            'bidirectional_inconsistencies': len(self.issues['bidirectional_inconsistencies']),
            'orphaned_references': len(self.issues['orphaned_references']),
            'duplicate_links': len(self.issues['duplicate_links']),
            'missing_fields': len(self.issues['missing_fields']),
            'date_format_issues': len(self.issues['date_format_issues']),
            'department_standardization': len(self.issues['department_standardization']),
            'severity_breakdown': self._categorize_issues_by_severity()
        }
        
        # Generate automated fixes
        await self.generate_automated_fixes()
        
        print(f"    📊 Total issues found: {total_issues}")
        print(f"    🔧 Automated fixes available: {len(self.fixes)}")
    
    def _categorize_issues_by_severity(self) -> Dict[str, int]:
        """Categorize issues by severity level."""
        severity_counts = {'critical': 0, 'high': 0, 'medium': 0, 'low': 0}
        
        # Critical: orphaned references, bidirectional inconsistencies
        severity_counts['critical'] = (
            len(self.issues['orphaned_references']) +
            len(self.issues['bidirectional_inconsistencies'])
        )
        
        # High: missing required fields
        severity_counts['high'] = len(self.issues['missing_fields'])
        
        # Medium: duplicate links, date format issues
        severity_counts['medium'] = (
            len(self.issues['duplicate_links']) +
            len(self.issues['date_format_issues'])
        )
        
        # Low: department standardization
        severity_counts['low'] = len(self.issues['department_standardization'])
        
        return severity_counts
    
    async def generate_automated_fixes(self):
        """Generate automated fix scripts for identified issues."""
        print("  🔧 Generating automated fixes...")
        
        # Fix 1: Remove orphaned references
        orphaned_fixes = []
        for issue in self.issues['orphaned_references']:
            if issue['type'] == 'orphaned_evidence_in_promise':
                orphaned_fixes.append({
                    'type': 'remove_orphaned_evidence_reference',
                    'collection': 'promises',
                    'document_id': issue['promise_id'],
                    'field': 'linked_evidence_ids',
                    'value_to_remove': issue['evidence_id'],
                    'description': f"Remove orphaned evidence ID {issue['evidence_id']} from promise {issue['promise_id']}"
                })
            elif issue['type'] == 'orphaned_promise_in_evidence':
                orphaned_fixes.append({
                    'type': 'remove_orphaned_promise_reference',
                    'collection': 'evidence_items',
                    'document_id': issue['evidence_id'],
                    'field': 'promise_ids',
                    'value_to_remove': issue['promise_id'],
                    'description': f"Remove orphaned promise ID {issue['promise_id']} from evidence {issue['evidence_id']}"
                })
        
        # Fix 2: Remove duplicate links
        duplicate_fixes = []
        for issue in self.issues['duplicate_links']:
            duplicate_fixes.append({
                'type': 'remove_duplicates',
                'collection': 'promises' if 'promise' in issue['type'] else 'evidence_items',
                'document_id': issue.get('promise_id') or issue.get('evidence_id'),
                'field': issue['field'],
                'description': f"Remove duplicate IDs from {issue['field']}"
            })
        
        # Fix 3: Bidirectional consistency fixes
        consistency_fixes = []
        for issue in self.issues['bidirectional_inconsistencies']:
            if issue['type'] == 'missing_reverse_link':
                consistency_fixes.append({
                    'type': 'add_reverse_link',
                    'evidence_collection': 'evidence_items',
                    'evidence_id': issue['evidence_id'],
                    'promise_id': issue['promise_id'],
                    'description': f"Add promise {issue['promise_id']} to evidence {issue['evidence_id']} promise_ids"
                })
            elif issue['type'] == 'missing_forward_link':
                consistency_fixes.append({
                    'type': 'add_forward_link',
                    'promise_collection': 'promises',
                    'promise_id': issue['promise_id'],
                    'evidence_id': issue['evidence_id'],
                    'description': f"Add evidence {issue['evidence_id']} to promise {issue['promise_id']} linked_evidence_ids"
                })
        
        self.fixes = orphaned_fixes + duplicate_fixes + consistency_fixes
        print(f"    🔧 Generated {len(self.fixes)} automated fixes")
    
    async def export_results(self):
        """Export integrity check results and fixes."""
        print("  💾 Exporting integrity check results...")
        
        # Create output directory
        os.makedirs('integrity_results', exist_ok=True)
        
        # 1. JSON export of all issues
        with open('integrity_results/data_integrity_issues.json', 'w') as f:
            json.dump(self.issues, f, indent=2, default=str)
        
        # 2. JSON export of automated fixes
        with open('integrity_results/automated_fixes.json', 'w') as f:
            json.dump(self.fixes, f, indent=2, default=str)
        
        # 3. CSV exports for each issue type
        for issue_type, issues_list in self.issues.items():
            if isinstance(issues_list, list) and issues_list:
                df = pd.DataFrame(issues_list)
                df.to_csv(f'integrity_results/{issue_type}.csv', index=False)
        
        # 4. Generate integrity report
        await self.generate_integrity_report()
        
        # 5. Generate fix script
        await self.generate_fix_script()
        
        print("    ✅ Results exported to integrity_results/")
    
    async def generate_integrity_report(self):
        """Generate comprehensive integrity report."""
        summary = self.issues['summary']
        
        report = f"""
# Data Integrity Check Report
Generated: {self.issues['timestamp']}

## Executive Summary

### Issue Overview
- **Total Issues Found**: {summary['total_issues']:,}
- **Critical Issues**: {summary['severity_breakdown']['critical']:,}
- **High Priority Issues**: {summary['severity_breakdown']['high']:,}
- **Medium Priority Issues**: {summary['severity_breakdown']['medium']:,}
- **Low Priority Issues**: {summary['severity_breakdown']['low']:,}

### Issue Breakdown
- **Bidirectional Inconsistencies**: {summary['bidirectional_inconsistencies']:,}
- **Orphaned References**: {summary['orphaned_references']:,}
- **Duplicate Links**: {summary['duplicate_links']:,}
- **Missing Required Fields**: {summary['missing_fields']:,}
- **Date Format Issues**: {summary['date_format_issues']:,}
- **Department Standardization**: {summary['department_standardization']:,}

## Critical Issues (Immediate Action Required)

### Bidirectional Inconsistencies ({summary['bidirectional_inconsistencies']:,} issues)
These issues indicate that promise-evidence links are not properly synchronized between collections.

**Impact**: Data inconsistency, unreliable link counts, potential frontend display errors
**Priority**: CRITICAL
**Automated Fix Available**: Yes

### Orphaned References ({summary['orphaned_references']:,} issues)
These issues indicate references to documents that no longer exist.

**Impact**: Broken links, potential application errors, data corruption
**Priority**: CRITICAL
**Automated Fix Available**: Yes

## High Priority Issues

### Missing Required Fields ({summary['missing_fields']:,} issues)
Documents are missing essential fields required for proper functionality.

**Impact**: Incomplete data display, potential search/filter issues
**Priority**: HIGH
**Automated Fix Available**: Partial (requires manual data entry)

## Medium Priority Issues

### Duplicate Links ({summary['duplicate_links']:,} issues)
Arrays contain duplicate references to the same documents.

**Impact**: Inflated counts, potential performance issues
**Priority**: MEDIUM
**Automated Fix Available**: Yes

### Date Format Issues ({summary['date_format_issues']:,} issues)
Inconsistent or invalid date formats across documents.

**Impact**: Sorting issues, timeline display problems
**Priority**: MEDIUM
**Automated Fix Available**: Partial

## Low Priority Issues

### Department Standardization ({summary['department_standardization']:,} issues)
Potential inconsistencies in department naming conventions.

**Impact**: Grouping and filtering accuracy
**Priority**: LOW
**Automated Fix Available**: No (requires manual review)

## Automated Fixes Available

**Total Automated Fixes**: {len(self.fixes):,}

### Fix Categories:
1. **Remove Orphaned References**: Clean up broken links
2. **Remove Duplicate Links**: Deduplicate arrays
3. **Add Missing Bidirectional Links**: Synchronize promise-evidence links

## Recommendations

### Immediate Actions (Critical)
1. **Run Automated Fixes**: Execute the generated fix script for critical issues
2. **Backup Database**: Ensure full backup before applying any fixes
3. **Validate Results**: Re-run integrity check after applying fixes

### Short-term Actions (High Priority)
1. **Data Entry**: Address missing required fields
2. **Date Standardization**: Implement consistent date format handling
3. **Validation Rules**: Add database constraints to prevent future issues

### Long-term Actions (Medium/Low Priority)
1. **Department Standardization**: Create canonical department name list
2. **Automated Monitoring**: Set up regular integrity checks
3. **Data Quality Metrics**: Implement ongoing quality monitoring

## Next Steps
1. Review this report with the development team
2. Execute automated fixes in a test environment first
3. Implement data validation rules to prevent future issues
4. Set up regular integrity monitoring
"""
        
        with open('integrity_results/integrity_report.md', 'w') as f:
            f.write(report)
        
        print("    📄 Integrity report saved to integrity_results/integrity_report.md")
    
    async def generate_fix_script(self):
        """Generate executable script to apply automated fixes."""
        script_content = '''#!/usr/bin/env python3
"""
Automated Data Integrity Fix Script
Generated from data integrity check results.

WARNING: This script will modify your database. 
Make sure you have a complete backup before running!
"""

import firebase_admin
from firebase_admin import credentials, firestore
import json

# Initialize Firebase Admin
try:
    firebase_admin.get_app()
except ValueError:
    firebase_admin.initialize_app()

db = firestore.client()

def apply_fixes():
    """Apply all automated fixes."""
    with open('automated_fixes.json', 'r') as f:
        fixes = json.load(f)
    
    print(f"Applying {len(fixes)} automated fixes...")
    
    for i, fix in enumerate(fixes, 1):
        print(f"Fix {i}/{len(fixes)}: {fix['description']}")
        
        try:
            if fix['type'] == 'remove_orphaned_evidence_reference':
                doc_ref = db.collection(fix['collection']).document(fix['document_id'])
                doc = doc_ref.get()
                if doc.exists:
                    data = doc.to_dict()
                    linked_ids = data.get(fix['field'], [])
                    if fix['value_to_remove'] in linked_ids:
                        linked_ids.remove(fix['value_to_remove'])
                        doc_ref.update({fix['field']: linked_ids})
                        print(f"  ✅ Removed orphaned reference")
                    else:
                        print(f"  ⚠️  Reference not found")
                else:
                    print(f"  ❌ Document not found")
            
            elif fix['type'] == 'remove_orphaned_promise_reference':
                doc_ref = db.collection(fix['collection']).document(fix['document_id'])
                doc = doc_ref.get()
                if doc.exists:
                    data = doc.to_dict()
                    promise_ids = data.get(fix['field'], [])
                    if fix['value_to_remove'] in promise_ids:
                        promise_ids.remove(fix['value_to_remove'])
                        doc_ref.update({fix['field']: promise_ids})
                        print(f"  ✅ Removed orphaned reference")
                    else:
                        print(f"  ⚠️  Reference not found")
                else:
                    print(f"  ❌ Document not found")
            
            elif fix['type'] == 'remove_duplicates':
                doc_ref = db.collection(fix['collection']).document(fix['document_id'])
                doc = doc_ref.get()
                if doc.exists:
                    data = doc.to_dict()
                    ids_list = data.get(fix['field'], [])
                    unique_ids = list(set(ids_list))
                    if len(unique_ids) != len(ids_list):
                        doc_ref.update({fix['field']: unique_ids})
                        print(f"  ✅ Removed {len(ids_list) - len(unique_ids)} duplicates")
                    else:
                        print(f"  ⚠️  No duplicates found")
                else:
                    print(f"  ❌ Document not found")
            
            elif fix['type'] == 'add_reverse_link':
                doc_ref = db.collection('evidence_items').document(fix['evidence_id'])
                doc = doc_ref.get()
                if doc.exists:
                    data = doc.to_dict()
                    promise_ids = data.get('promise_ids', [])
                    if fix['promise_id'] not in promise_ids:
                        promise_ids.append(fix['promise_id'])
                        doc_ref.update({'promise_ids': promise_ids})
                        print(f"  ✅ Added reverse link")
                    else:
                        print(f"  ⚠️  Link already exists")
                else:
                    print(f"  ❌ Evidence document not found")
            
            elif fix['type'] == 'add_forward_link':
                doc_ref = db.collection('promises').document(fix['promise_id'])
                doc = doc_ref.get()
                if doc.exists:
                    data = doc.to_dict()
                    linked_evidence_ids = data.get('linked_evidence_ids', [])
                    if fix['evidence_id'] not in linked_evidence_ids:
                        linked_evidence_ids.append(fix['evidence_id'])
                        doc_ref.update({'linked_evidence_ids': linked_evidence_ids})
                        print(f"  ✅ Added forward link")
                    else:
                        print(f"  ⚠️  Link already exists")
                else:
                    print(f"  ❌ Promise document not found")
            
        except Exception as e:
            print(f"  ❌ Error applying fix: {e}")
    
    print("\\n✅ All fixes applied!")
    print("\\n🔍 Recommendation: Run integrity check again to verify fixes")

if __name__ == "__main__":
    print("⚠️  WARNING: This will modify your database!")
    print("Make sure you have a backup before proceeding.")
    
    response = input("\\nDo you want to continue? (yes/no): ")
    if response.lower() == 'yes':
        apply_fixes()
    else:
        print("Fix application cancelled.")
'''
        
        with open('integrity_results/apply_fixes.py', 'w') as f:
            f.write(script_content)
        
        # Make script executable
        os.chmod('integrity_results/apply_fixes.py', 0o755)
        
        print("    🔧 Fix script saved to integrity_results/apply_fixes.py")

async def main():
    """Main execution function."""
    checker = DataIntegrityChecker()
    results = await checker.run_integrity_check()
    
    print("\n" + "=" * 60)
    print("🎉 INTEGRITY CHECK COMPLETE!")
    print("=" * 60)
    print(f"📊 Total issues found: {results['summary']['total_issues']:,}")
    print(f"🚨 Critical issues: {results['summary']['severity_breakdown']['critical']:,}")
    print(f"⚠️  High priority: {results['summary']['severity_breakdown']['high']:,}")
    print(f"🔧 Automated fixes available: {len(checker.fixes):,}")
    print("\n📁 Results saved to: integrity_results/")
    print("📄 Full report: integrity_results/integrity_report.md")
    print("🔧 Fix script: integrity_results/apply_fixes.py")

if __name__ == "__main__":
    asyncio.run(main()) 