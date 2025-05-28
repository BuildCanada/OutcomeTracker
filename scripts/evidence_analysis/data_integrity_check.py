#!/usr/bin/env python3
"""
Data Integrity Check Script
Verifies the current state of the promise-evidence linking system

This script:
1. Checks bidirectional link consistency
2. Identifies orphaned references
3. Validates data structure integrity
4. Reports on linking system health
"""

import asyncio
import json
import os
from datetime import datetime, timezone
from collections import defaultdict, Counter
from typing import Dict, List, Any, Optional, Set, Tuple

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
    """Checks data integrity of the promise-evidence linking system."""
    
    def __init__(self):
        self.db = db
        self.integrity_results = {
            'timestamp': datetime.now(timezone.utc).isoformat(),
            'promises_analysis': {},
            'evidence_analysis': {},
            'linking_integrity': {},
            'orphaned_references': {},
            'data_quality_issues': [],
            'recommendations': []
        }
        
    async def run_integrity_check(self) -> Dict[str, Any]:
        """Run the complete data integrity check."""
        print("🔍 Starting Data Integrity Check...")
        print("=" * 60)
        
        # Step 1: Analyze promises collection
        print("📋 Step 1: Analyzing promises collection...")
        promises_data = await self.analyze_promises_collection()
        
        # Step 2: Analyze evidence collection
        print("📊 Step 2: Analyzing evidence collection...")
        evidence_data = await self.analyze_evidence_collection()
        
        # Step 3: Check bidirectional linking integrity
        print("🔗 Step 3: Checking bidirectional linking integrity...")
        await self.check_bidirectional_integrity(promises_data, evidence_data)
        
        # Step 4: Identify orphaned references
        print("🔍 Step 4: Identifying orphaned references...")
        await self.identify_orphaned_references(promises_data, evidence_data)
        
        # Step 5: Validate data quality
        print("✅ Step 5: Validating data quality...")
        await self.validate_data_quality(promises_data, evidence_data)
        
        # Step 6: Generate recommendations
        print("💡 Step 6: Generating recommendations...")
        await self.generate_recommendations()
        
        # Step 7: Export results
        print("💾 Step 7: Exporting integrity check results...")
        await self.export_results()
        
        print("✅ Data integrity check complete!")
        return self.integrity_results
    
    async def analyze_promises_collection(self) -> List[Dict[str, Any]]:
        """Analyze the promises collection structure and linking data."""
        print("  📥 Fetching promises data...")
        
        try:
            promises_ref = self.db.collection('promises')
            promises_docs = promises_ref.stream()
            
            promises_data = []
            linking_stats = {
                'total_promises': 0,
                'with_linked_evidence': 0,
                'total_evidence_links': 0,
                'evidence_link_distribution': Counter(),
                'linking_status_distribution': Counter(),
                'parliament_distribution': Counter(),
                'department_distribution': Counter(),
                'party_distribution': Counter()
            }
            
            for doc in promises_docs:
                data = doc.to_dict()
                data['id'] = doc.id
                promises_data.append(data)
                
                linking_stats['total_promises'] += 1
                
                # Analyze linked evidence
                linked_evidence = data.get('linked_evidence_ids', [])
                if linked_evidence:
                    linking_stats['with_linked_evidence'] += 1
                    linking_stats['total_evidence_links'] += len(linked_evidence)
                    linking_stats['evidence_link_distribution'][len(linked_evidence)] += 1
                else:
                    linking_stats['evidence_link_distribution'][0] += 1
                
                # Track other distributions
                linking_stats['parliament_distribution'][data.get('parliament_number', 'Unknown')] += 1
                linking_stats['department_distribution'][data.get('department', 'Unknown')] += 1
                linking_stats['party_distribution'][data.get('party', 'Unknown')] += 1
                
                # Track linking status if available
                linking_status = data.get('linking_status', 'Unknown')
                linking_stats['linking_status_distribution'][linking_status] += 1
            
            # Calculate percentages
            total = linking_stats['total_promises']
            linking_stats['pct_with_evidence'] = (linking_stats['with_linked_evidence'] / total * 100) if total > 0 else 0
            linking_stats['avg_evidence_per_promise'] = (linking_stats['total_evidence_links'] / total) if total > 0 else 0
            
            self.integrity_results['promises_analysis'] = {
                'collection_stats': linking_stats,
                'sample_promises': promises_data[:10]  # Store sample for analysis
            }
            
            print(f"  ✅ Analyzed {total:,} promises")
            print(f"  📊 {linking_stats['with_linked_evidence']:,} promises have evidence links ({linking_stats['pct_with_evidence']:.1f}%)")
            print(f"  📊 {linking_stats['avg_evidence_per_promise']:.2f} average evidence items per promise")
            
            return promises_data
            
        except Exception as e:
            print(f"  ❌ Error analyzing promises: {e}")
            return []
    
    async def analyze_evidence_collection(self) -> List[Dict[str, Any]]:
        """Analyze the evidence collection structure and linking data."""
        print("  📥 Fetching evidence data...")
        
        try:
            evidence_ref = self.db.collection('evidence_items')
            evidence_docs = evidence_ref.stream()
            
            evidence_data = []
            linking_stats = {
                'total_evidence': 0,
                'with_promise_links': 0,
                'total_promise_links': 0,
                'promise_link_distribution': Counter(),
                'evidence_type_distribution': Counter(),
                'source_distribution': Counter(),
                'department_distribution': Counter(),
                'linking_status_distribution': Counter()
            }
            
            for doc in evidence_docs:
                data = doc.to_dict()
                data['id'] = doc.id
                evidence_data.append(data)
                
                linking_stats['total_evidence'] += 1
                
                # Analyze promise links
                promise_links = data.get('promise_ids', [])
                if promise_links:
                    linking_stats['with_promise_links'] += 1
                    linking_stats['total_promise_links'] += len(promise_links)
                    linking_stats['promise_link_distribution'][len(promise_links)] += 1
                else:
                    linking_stats['promise_link_distribution'][0] += 1
                
                # Track distributions
                linking_stats['evidence_type_distribution'][data.get('evidence_source_type', 'Unknown')] += 1
                linking_stats['source_distribution'][data.get('source_feed_name', data.get('source_type', 'Unknown'))] += 1
                
                # Track departments
                departments = data.get('linked_departments', [])
                if departments:
                    for dept in departments:
                        linking_stats['department_distribution'][dept] += 1
                
                # Track linking status
                linking_status = data.get('promise_linking_status', 'Unknown')
                linking_stats['linking_status_distribution'][linking_status] += 1
            
            # Calculate percentages
            total = linking_stats['total_evidence']
            linking_stats['pct_with_promises'] = (linking_stats['with_promise_links'] / total * 100) if total > 0 else 0
            linking_stats['avg_promises_per_evidence'] = (linking_stats['total_promise_links'] / total) if total > 0 else 0
            
            self.integrity_results['evidence_analysis'] = {
                'collection_stats': linking_stats,
                'sample_evidence': evidence_data[:10]  # Store sample for analysis
            }
            
            print(f"  ✅ Analyzed {total:,} evidence items")
            print(f"  📊 {linking_stats['with_promise_links']:,} evidence items have promise links ({linking_stats['pct_with_promises']:.1f}%)")
            print(f"  📊 {linking_stats['avg_promises_per_evidence']:.2f} average promises per evidence item")
            
            return evidence_data
            
        except Exception as e:
            print(f"  ❌ Error analyzing evidence: {e}")
            return []
    
    async def check_bidirectional_integrity(self, promises_data: List[Dict[str, Any]], 
                                          evidence_data: List[Dict[str, Any]]):
        """Check bidirectional linking integrity between promises and evidence."""
        print("  🔗 Checking bidirectional link consistency...")
        
        # Build lookup maps
        promise_to_evidence = {}  # promise_id -> set of evidence_ids
        evidence_to_promise = {}  # evidence_id -> set of promise_ids
        
        # Extract promise -> evidence mappings
        for promise in promises_data:
            promise_id = promise['id']
            evidence_ids = set(promise.get('linked_evidence_ids', []))
            promise_to_evidence[promise_id] = evidence_ids
        
        # Extract evidence -> promise mappings
        for evidence in evidence_data:
            evidence_id = evidence['id']
            promise_ids = set(evidence.get('promise_ids', []))
            evidence_to_promise[evidence_id] = promise_ids
        
        # Check consistency
        integrity_issues = {
            'promise_orphaned_evidence': [],  # Promise links to evidence that doesn't link back
            'evidence_orphaned_promises': [],  # Evidence links to promise that doesn't link back
            'missing_evidence_items': [],     # Promise links to non-existent evidence
            'missing_promise_items': [],      # Evidence links to non-existent promise
            'total_bidirectional_links': 0,
            'total_unidirectional_links': 0,
            'consistency_percentage': 0
        }
        
        evidence_ids_set = set(evidence['id'] for evidence in evidence_data)
        promise_ids_set = set(promise['id'] for promise in promises_data)
        
        # Check promise -> evidence consistency
        for promise_id, evidence_ids in promise_to_evidence.items():
            for evidence_id in evidence_ids:
                # Check if evidence exists
                if evidence_id not in evidence_ids_set:
                    integrity_issues['missing_evidence_items'].append({
                        'promise_id': promise_id,
                        'missing_evidence_id': evidence_id
                    })
                    continue
                
                # Check if evidence links back to promise
                if promise_id not in evidence_to_promise.get(evidence_id, set()):
                    integrity_issues['promise_orphaned_evidence'].append({
                        'promise_id': promise_id,
                        'orphaned_evidence_id': evidence_id
                    })
                else:
                    integrity_issues['total_bidirectional_links'] += 1
        
        # Check evidence -> promise consistency
        for evidence_id, promise_ids in evidence_to_promise.items():
            for promise_id in promise_ids:
                # Check if promise exists
                if promise_id not in promise_ids_set:
                    integrity_issues['missing_promise_items'].append({
                        'evidence_id': evidence_id,
                        'missing_promise_id': promise_id
                    })
                    continue
                
                # Check if promise links back to evidence
                if evidence_id not in promise_to_evidence.get(promise_id, set()):
                    integrity_issues['evidence_orphaned_promises'].append({
                        'evidence_id': evidence_id,
                        'orphaned_promise_id': promise_id
                    })
                    integrity_issues['total_unidirectional_links'] += 1
        
        # Calculate consistency percentage
        total_links = integrity_issues['total_bidirectional_links'] + integrity_issues['total_unidirectional_links']
        if total_links > 0:
            integrity_issues['consistency_percentage'] = (integrity_issues['total_bidirectional_links'] / total_links) * 100
        
        self.integrity_results['linking_integrity'] = integrity_issues
        
        print(f"  📊 Bidirectional links: {integrity_issues['total_bidirectional_links']:,}")
        print(f"  📊 Unidirectional links: {integrity_issues['total_unidirectional_links']:,}")
        print(f"  📊 Consistency: {integrity_issues['consistency_percentage']:.1f}%")
        print(f"  ⚠️ Orphaned evidence refs: {len(integrity_issues['promise_orphaned_evidence']):,}")
        print(f"  ⚠️ Orphaned promise refs: {len(integrity_issues['evidence_orphaned_promises']):,}")
        print(f"  ❌ Missing evidence items: {len(integrity_issues['missing_evidence_items']):,}")
        print(f"  ❌ Missing promise items: {len(integrity_issues['missing_promise_items']):,}")
    
    async def identify_orphaned_references(self, promises_data: List[Dict[str, Any]], 
                                         evidence_data: List[Dict[str, Any]]):
        """Identify orphaned references and data quality issues."""
        print("  🔍 Identifying orphaned references...")
        
        orphaned_refs = {
            'promises_without_evidence': [],
            'evidence_without_promises': [],
            'empty_link_arrays': {
                'promises_empty_evidence_array': 0,
                'evidence_empty_promise_array': 0
            },
            'null_link_fields': {
                'promises_null_evidence_field': 0,
                'evidence_null_promise_field': 0
            }
        }
        
        # Check promises
        for promise in promises_data:
            evidence_ids = promise.get('linked_evidence_ids')
            
            if evidence_ids is None:
                orphaned_refs['null_link_fields']['promises_null_evidence_field'] += 1
            elif len(evidence_ids) == 0:
                orphaned_refs['empty_link_arrays']['promises_empty_evidence_array'] += 1
                orphaned_refs['promises_without_evidence'].append({
                    'id': promise['id'],
                    'title': promise.get('promise_title', 'No title')[:100],
                    'department': promise.get('department', 'Unknown'),
                    'parliament': promise.get('parliament_number', 'Unknown')
                })
        
        # Check evidence
        for evidence in evidence_data:
            promise_ids = evidence.get('promise_ids')
            
            if promise_ids is None:
                orphaned_refs['null_link_fields']['evidence_null_promise_field'] += 1
            elif len(promise_ids) == 0:
                orphaned_refs['empty_link_arrays']['evidence_empty_promise_array'] += 1
                orphaned_refs['evidence_without_promises'].append({
                    'id': evidence['id'],
                    'title': evidence.get('title_or_summary', 'No title')[:100],
                    'type': evidence.get('evidence_source_type', 'Unknown'),
                    'source': evidence.get('source_feed_name', 'Unknown')
                })
        
        self.integrity_results['orphaned_references'] = orphaned_refs
        
        print(f"  📊 Promises without evidence: {len(orphaned_refs['promises_without_evidence']):,}")
        print(f"  📊 Evidence without promises: {len(orphaned_refs['evidence_without_promises']):,}")
        print(f"  📊 Empty evidence arrays: {orphaned_refs['empty_link_arrays']['promises_empty_evidence_array']:,}")
        print(f"  📊 Empty promise arrays: {orphaned_refs['empty_link_arrays']['evidence_empty_promise_array']:,}")
    
    async def validate_data_quality(self, promises_data: List[Dict[str, Any]], 
                                   evidence_data: List[Dict[str, Any]]):
        """Validate data quality and identify potential issues."""
        print("  ✅ Validating data quality...")
        
        quality_issues = []
        
        # Check promises data quality
        promises_missing_fields = defaultdict(int)
        for promise in promises_data:
            required_fields = ['promise_title', 'department', 'parliament_number', 'party']
            for field in required_fields:
                if not promise.get(field):
                    promises_missing_fields[field] += 1
        
        for field, count in promises_missing_fields.items():
            if count > 0:
                pct = (count / len(promises_data)) * 100
                quality_issues.append(f"Promises missing {field}: {count:,} ({pct:.1f}%)")
        
        # Check evidence data quality
        evidence_missing_fields = defaultdict(int)
        for evidence in evidence_data:
            required_fields = ['title_or_summary', 'evidence_source_type', 'date_published']
            for field in required_fields:
                if not evidence.get(field):
                    evidence_missing_fields[field] += 1
        
        for field, count in evidence_missing_fields.items():
            if count > 0:
                pct = (count / len(evidence_data)) * 100
                quality_issues.append(f"Evidence missing {field}: {count:,} ({pct:.1f}%)")
        
        # Check for duplicate IDs (shouldn't happen but good to verify)
        promise_ids = [p['id'] for p in promises_data]
        evidence_ids = [e['id'] for e in evidence_data]
        
        if len(promise_ids) != len(set(promise_ids)):
            quality_issues.append("Duplicate promise IDs detected")
        
        if len(evidence_ids) != len(set(evidence_ids)):
            quality_issues.append("Duplicate evidence IDs detected")
        
        # Check for content quality
        promises_no_content = len([p for p in promises_data if not p.get('promise_title', '').strip()])
        evidence_no_content = len([e for e in evidence_data if not e.get('title_or_summary', '').strip()])
        
        if promises_no_content > 0:
            quality_issues.append(f"Promises with no title content: {promises_no_content:,}")
        
        if evidence_no_content > 0:
            quality_issues.append(f"Evidence with no title content: {evidence_no_content:,}")
        
        self.integrity_results['data_quality_issues'] = quality_issues
        
        if quality_issues:
            print(f"  ⚠️ Found {len(quality_issues)} data quality issues")
            for issue in quality_issues[:5]:  # Show first 5
                print(f"    - {issue}")
        else:
            print("  ✅ No major data quality issues found")
    
    async def generate_recommendations(self):
        """Generate recommendations based on integrity check results."""
        print("  💡 Generating recommendations...")
        
        recommendations = []
        
        promises_stats = self.integrity_results['promises_analysis']['collection_stats']
        evidence_stats = self.integrity_results['evidence_analysis']['collection_stats']
        linking_integrity = self.integrity_results['linking_integrity']
        orphaned_refs = self.integrity_results['orphaned_references']
        
        # Linking system recommendations
        if promises_stats['with_linked_evidence'] == 0 and evidence_stats['with_promise_links'] == 0:
            recommendations.append("CRITICAL: No active links detected. Initialize linking system immediately.")
            recommendations.append("Run initial linking algorithm with relaxed parameters to establish baseline.")
        
        # Bidirectional consistency recommendations
        if linking_integrity['consistency_percentage'] < 100:
            recommendations.append(f"Fix bidirectional consistency issues ({linking_integrity['consistency_percentage']:.1f}% consistent).")
            recommendations.append("Implement automated bidirectional link maintenance.")
        
        # Orphaned reference recommendations
        orphaned_promises = len(orphaned_refs['promises_without_evidence'])
        orphaned_evidence = len(orphaned_refs['evidence_without_promises'])
        
        if orphaned_promises > 0:
            pct = (orphaned_promises / promises_stats['total_promises']) * 100
            recommendations.append(f"Address {orphaned_promises:,} promises without evidence ({pct:.1f}%).")
        
        if orphaned_evidence > 0:
            pct = (orphaned_evidence / evidence_stats['total_evidence']) * 100
            recommendations.append(f"Process {orphaned_evidence:,} unlinked evidence items ({pct:.1f}%).")
        
        # Data quality recommendations
        quality_issues = self.integrity_results['data_quality_issues']
        if quality_issues:
            recommendations.append("Address data quality issues before running linking algorithms.")
            recommendations.append("Implement data validation pipeline for new ingestion.")
        
        # Performance recommendations
        if promises_stats['total_promises'] > 1000 and evidence_stats['total_evidence'] > 5000:
            recommendations.append("Consider implementing batch processing for large-scale linking operations.")
            recommendations.append("Implement caching and indexing for improved linking performance.")
        
        self.integrity_results['recommendations'] = recommendations
        
        print(f"  💡 Generated {len(recommendations)} recommendations")
    
    async def export_results(self):
        """Export integrity check results."""
        print("  💾 Exporting integrity check results...")
        
        # Create output directory
        os.makedirs('integrity_check_results', exist_ok=True)
        
        # 1. JSON export
        with open('integrity_check_results/data_integrity_check.json', 'w') as f:
            json.dump(self.integrity_results, f, indent=2, default=str)
        
        # 2. Generate comprehensive report
        await self.generate_integrity_report()
        
        print("    ✅ Results exported to integrity_check_results/")
    
    async def generate_integrity_report(self):
        """Generate comprehensive integrity check report."""
        promises_stats = self.integrity_results['promises_analysis']['collection_stats']
        evidence_stats = self.integrity_results['evidence_analysis']['collection_stats']
        linking_integrity = self.integrity_results['linking_integrity']
        orphaned_refs = self.integrity_results['orphaned_references']
        quality_issues = self.integrity_results['data_quality_issues']
        recommendations = self.integrity_results['recommendations']
        
        report = f"""
# Data Integrity Check Report
Generated: {self.integrity_results['timestamp']}

## Executive Summary

This report provides a comprehensive analysis of the promise-evidence linking system's data integrity and current operational status.

### System Status: {"🔴 CRITICAL" if promises_stats['with_linked_evidence'] == 0 else "🟡 NEEDS ATTENTION" if linking_integrity['consistency_percentage'] < 90 else "🟢 HEALTHY"}

**Data Volume**:
- **Promises**: {promises_stats['total_promises']:,} total items
- **Evidence**: {evidence_stats['total_evidence']:,} total items

**Linking Status**:
- **Promises with Evidence**: {promises_stats['with_linked_evidence']:,} ({promises_stats['pct_with_evidence']:.1f}%)
- **Evidence with Promises**: {evidence_stats['with_promise_links']:,} ({evidence_stats['pct_with_promises']:.1f}%)
- **Bidirectional Consistency**: {linking_integrity['consistency_percentage']:.1f}%

## Collection Analysis

### Promises Collection

**Basic Statistics**:
- Total promises: {promises_stats['total_promises']:,}
- With evidence links: {promises_stats['with_linked_evidence']:,} ({promises_stats['pct_with_evidence']:.1f}%)
- Total evidence links: {promises_stats['total_evidence_links']:,}
- Average evidence per promise: {promises_stats['avg_evidence_per_promise']:.2f}

**Parliament Distribution**:
"""
        
        for parliament, count in promises_stats['parliament_distribution'].most_common():
            pct = (count / promises_stats['total_promises']) * 100
            report += f"- **Parliament {parliament}**: {count:,} ({pct:.1f}%)\n"
        
        report += f"""

**Party Distribution**:
"""
        
        for party, count in promises_stats['party_distribution'].most_common(5):
            pct = (count / promises_stats['total_promises']) * 100
            report += f"- **{party}**: {count:,} ({pct:.1f}%)\n"
        
        report += f"""

**Top Departments**:
"""
        
        for dept, count in promises_stats['department_distribution'].most_common(10):
            pct = (count / promises_stats['total_promises']) * 100
            report += f"- **{dept}**: {count:,} ({pct:.1f}%)\n"
        
        report += f"""

### Evidence Collection

**Basic Statistics**:
- Total evidence items: {evidence_stats['total_evidence']:,}
- With promise links: {evidence_stats['with_promise_links']:,} ({evidence_stats['pct_with_promises']:.1f}%)
- Total promise links: {evidence_stats['total_promise_links']:,}
- Average promises per evidence: {evidence_stats['avg_promises_per_evidence']:.2f}

**Evidence Type Distribution**:
"""
        
        for etype, count in evidence_stats['evidence_type_distribution'].most_common():
            pct = (count / evidence_stats['total_evidence']) * 100
            report += f"- **{etype}**: {count:,} ({pct:.1f}%)\n"
        
        report += f"""

**Source Distribution**:
"""
        
        for source, count in evidence_stats['source_distribution'].most_common(10):
            pct = (count / evidence_stats['total_evidence']) * 100
            report += f"- **{source}**: {count:,} ({pct:.1f}%)\n"
        
        report += f"""

## Linking Integrity Analysis

### Bidirectional Consistency

**Link Consistency**:
- **Bidirectional links**: {linking_integrity['total_bidirectional_links']:,} (properly linked both ways)
- **Unidirectional links**: {linking_integrity['total_unidirectional_links']:,} (linked only one way)
- **Consistency percentage**: {linking_integrity['consistency_percentage']:.1f}%

### Integrity Issues

**Orphaned References**:
- **Promise → Evidence orphans**: {len(linking_integrity['promise_orphaned_evidence']):,} (promise links to evidence that doesn't link back)
- **Evidence → Promise orphans**: {len(linking_integrity['evidence_orphaned_promises']):,} (evidence links to promise that doesn't link back)

**Missing References**:
- **Missing evidence items**: {len(linking_integrity['missing_evidence_items']):,} (promise links to non-existent evidence)
- **Missing promise items**: {len(linking_integrity['missing_promise_items']):,} (evidence links to non-existent promise)

## Orphaned Data Analysis

### Unlinked Items

**Promises Without Evidence**:
- Count: {len(orphaned_refs['promises_without_evidence']):,}
- Percentage: {(len(orphaned_refs['promises_without_evidence']) / promises_stats['total_promises'] * 100):.1f}%

**Evidence Without Promises**:
- Count: {len(orphaned_refs['evidence_without_promises']):,}
- Percentage: {(len(orphaned_refs['evidence_without_promises']) / evidence_stats['total_evidence'] * 100):.1f}%

### Data Structure Issues

**Empty Link Arrays**:
- Promises with empty evidence arrays: {orphaned_refs['empty_link_arrays']['promises_empty_evidence_array']:,}
- Evidence with empty promise arrays: {orphaned_refs['empty_link_arrays']['evidence_empty_promise_array']:,}

**Null Link Fields**:
- Promises with null evidence field: {orphaned_refs['null_link_fields']['promises_null_evidence_field']:,}
- Evidence with null promise field: {orphaned_refs['null_link_fields']['evidence_null_promise_field']:,}

## Data Quality Issues

"""
        
        if quality_issues:
            for i, issue in enumerate(quality_issues, 1):
                report += f"{i}. {issue}\n"
        else:
            report += "✅ No major data quality issues detected.\n"
        
        report += f"""

## Recommendations

### Immediate Actions Required

"""
        
        critical_recs = [r for r in recommendations if 'CRITICAL' in r or 'immediately' in r.lower()]
        for i, rec in enumerate(critical_recs, 1):
            report += f"{i}. {rec}\n"
        
        report += f"""

### System Improvements

"""
        
        improvement_recs = [r for r in recommendations if r not in critical_recs]
        for i, rec in enumerate(improvement_recs, 1):
            report += f"{i}. {rec}\n"
        
        report += f"""

## System Health Assessment

### Overall Status
"""
        
        if promises_stats['with_linked_evidence'] == 0:
            report += """
🔴 **CRITICAL**: No active links detected in the system. The linking functionality appears to be completely non-operational.

**Immediate Actions Required**:
1. Verify linking algorithm deployment status
2. Check for recent system changes that may have broken linking
3. Run diagnostic linking test on small dataset
4. Initialize linking system with baseline parameters
"""
        elif linking_integrity['consistency_percentage'] < 50:
            report += f"""
🟡 **NEEDS ATTENTION**: System has {linking_integrity['consistency_percentage']:.1f}% bidirectional consistency. Significant integrity issues detected.

**Priority Actions**:
1. Fix bidirectional linking inconsistencies
2. Clean up orphaned references
3. Implement automated integrity maintenance
"""
        elif linking_integrity['consistency_percentage'] < 90:
            report += f"""
🟡 **MODERATE ISSUES**: System has {linking_integrity['consistency_percentage']:.1f}% bidirectional consistency. Some integrity issues present.

**Recommended Actions**:
1. Address orphaned references
2. Improve linking algorithm accuracy
3. Implement regular integrity checks
"""
        else:
            report += f"""
🟢 **HEALTHY**: System has {linking_integrity['consistency_percentage']:.1f}% bidirectional consistency. Minor issues may be present but system is operational.

**Maintenance Actions**:
1. Continue regular integrity monitoring
2. Optimize linking performance
3. Address any remaining orphaned references
"""
        
        report += f"""

### Performance Metrics

**Linking Efficiency**:
- Promise linking rate: {promises_stats['pct_with_evidence']:.1f}%
- Evidence linking rate: {evidence_stats['pct_with_promises']:.1f}%
- Average links per promise: {promises_stats['avg_evidence_per_promise']:.2f}
- Average links per evidence: {evidence_stats['avg_promises_per_evidence']:.2f}

**Data Quality Score**: {100 - len(quality_issues) * 5:.0f}/100 (based on {len(quality_issues)} quality issues)

## Files Generated
- `data_integrity_check.json`: Complete integrity analysis data
- `data_integrity_report.md`: This comprehensive report

---
*Report generated by Promise Tracker Data Integrity Checker*
"""
        
        with open('integrity_check_results/data_integrity_report.md', 'w') as f:
            f.write(report)
        
        print("    📄 Integrity report saved to integrity_check_results/data_integrity_report.md")

async def main():
    """Main execution function."""
    checker = DataIntegrityChecker()
    results = await checker.run_integrity_check()
    
    print("\n" + "=" * 60)
    print("🎉 DATA INTEGRITY CHECK COMPLETE!")
    print("=" * 60)
    
    promises_stats = results['promises_analysis']['collection_stats']
    evidence_stats = results['evidence_analysis']['collection_stats']
    linking_integrity = results['linking_integrity']
    recommendations = results['recommendations']
    
    print(f"📊 Promises analyzed: {promises_stats['total_promises']:,}")
    print(f"📊 Evidence analyzed: {evidence_stats['total_evidence']:,}")
    print(f"🔗 Bidirectional consistency: {linking_integrity['consistency_percentage']:.1f}%")
    print(f"💡 Recommendations: {len(recommendations)}")
    
    # Show system status
    if promises_stats['with_linked_evidence'] == 0:
        print("🔴 SYSTEM STATUS: CRITICAL - No active links detected")
    elif linking_integrity['consistency_percentage'] < 90:
        print("🟡 SYSTEM STATUS: NEEDS ATTENTION - Integrity issues detected")
    else:
        print("🟢 SYSTEM STATUS: HEALTHY - System operational")
    
    print("\n📁 Results saved to: integrity_check_results/")
    print("📄 Full report: integrity_check_results/data_integrity_report.md")

if __name__ == "__main__":
    asyncio.run(main()) 