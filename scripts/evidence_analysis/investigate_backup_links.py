#!/usr/bin/env python3
"""
Backup Data Investigation Script
Investigates the backup data to understand existing links and compare with current data

This script examines the backup collections to:
1. Find examples of successful promise-evidence links
2. Compare backup data structure with current data
3. Identify specific bill-promise links for testing
4. Generate test cases for the linking algorithms
"""

import asyncio
import json
import os
from datetime import datetime, timezone
from collections import defaultdict, Counter
from typing import Dict, List, Any, Tuple
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

class BackupDataInvestigator:
    """Investigates backup data to understand existing links."""
    
    def __init__(self):
        self.db = db
        self.investigation_results = {
            'timestamp': datetime.now(timezone.utc).isoformat(),
            'backup_analysis': {},
            'current_analysis': {},
            'comparison': {},
            'test_cases': [],
            'recommendations': []
        }
        
    async def run_investigation(self) -> Dict[str, Any]:
        """Run the complete backup data investigation."""
        print("🔍 Starting Backup Data Investigation...")
        print("=" * 60)
        
        # Step 1: Analyze backup promises
        print("📊 Step 1: Analyzing backup promises...")
        backup_promises = await self.analyze_backup_promises()
        
        # Step 2: Analyze backup evidence
        print("📋 Step 2: Analyzing backup evidence...")
        backup_evidence = await self.analyze_backup_evidence()
        
        # Step 3: Find successful links in backup
        print("🔗 Step 3: Finding successful links in backup...")
        successful_links = await self.find_successful_backup_links(backup_promises, backup_evidence)
        
        # Step 4: Analyze current data structure
        print("🆕 Step 4: Analyzing current data structure...")
        current_promises = await self.analyze_current_promises()
        current_evidence = await self.analyze_current_evidence()
        
        # Step 5: Compare data structures
        print("⚖️ Step 5: Comparing data structures...")
        await self.compare_data_structures(backup_promises, backup_evidence, current_promises, current_evidence)
        
        # Step 6: Generate test cases
        print("🧪 Step 6: Generating test cases...")
        await self.generate_test_cases(successful_links, current_promises, current_evidence)
        
        # Step 7: Export results
        print("💾 Step 7: Exporting investigation results...")
        await self.export_results()
        
        print("✅ Investigation complete!")
        return self.investigation_results
    
    async def analyze_backup_promises(self) -> List[Dict[str, Any]]:
        """Analyze promises from backup collection."""
        print("  📥 Fetching backup promises...")
        
        try:
            backup_ref = self.db.collection('promises_backup_20250527_212346')
            backup_docs = backup_ref.stream()
            
            backup_promises = []
            promises_with_links = 0
            total_linked_evidence = 0
            
            for doc in backup_docs:
                data = doc.to_dict()
                data['id'] = doc.id
                backup_promises.append(data)
                
                # Count links
                linked_evidence_ids = data.get('linked_evidence_ids', [])
                evidence_array = data.get('evidence', [])
                
                if linked_evidence_ids or evidence_array:
                    promises_with_links += 1
                    total_linked_evidence += len(linked_evidence_ids) + len(evidence_array)
            
            self.investigation_results['backup_analysis']['promises'] = {
                'total_count': len(backup_promises),
                'with_links': promises_with_links,
                'total_linked_evidence': total_linked_evidence,
                'avg_evidence_per_promise': total_linked_evidence / max(promises_with_links, 1)
            }
            
            print(f"  ✅ Backup promises: {len(backup_promises)} total, {promises_with_links} with links")
            return backup_promises
            
        except Exception as e:
            print(f"  ❌ Error analyzing backup promises: {e}")
            return []
    
    async def analyze_backup_evidence(self) -> List[Dict[str, Any]]:
        """Analyze evidence from backup collection."""
        print("  📥 Fetching backup evidence...")
        
        try:
            backup_ref = self.db.collection('evidence_items_backup_20250527_212346')
            backup_docs = backup_ref.stream()
            
            backup_evidence = []
            evidence_with_links = 0
            total_linked_promises = 0
            
            for doc in backup_docs:
                data = doc.to_dict()
                data['id'] = doc.id
                backup_evidence.append(data)
                
                # Count links
                promise_ids = data.get('promise_ids', [])
                if promise_ids:
                    evidence_with_links += 1
                    total_linked_promises += len(promise_ids)
            
            self.investigation_results['backup_analysis']['evidence'] = {
                'total_count': len(backup_evidence),
                'with_links': evidence_with_links,
                'total_linked_promises': total_linked_promises,
                'avg_promises_per_evidence': total_linked_promises / max(evidence_with_links, 1)
            }
            
            print(f"  ✅ Backup evidence: {len(backup_evidence)} total, {evidence_with_links} with links")
            return backup_evidence
            
        except Exception as e:
            print(f"  ❌ Error analyzing backup evidence: {e}")
            return []
    
    async def find_successful_backup_links(self, backup_promises: List[Dict[str, Any]], 
                                         backup_evidence: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Find examples of successful links in backup data."""
        print("  🔗 Analyzing successful links...")
        
        # Create lookup dictionaries
        promise_lookup = {p['id']: p for p in backup_promises}
        evidence_lookup = {e['id']: e for e in backup_evidence}
        
        successful_links = []
        bill_links = []
        
        # Find bidirectional links
        for evidence in backup_evidence:
            evidence_id = evidence['id']
            promise_ids = evidence.get('promise_ids', [])
            
            for promise_id in promise_ids:
                if promise_id in promise_lookup:
                    promise = promise_lookup[promise_id]
                    
                    # Check if promise links back
                    linked_evidence_ids = promise.get('linked_evidence_ids', [])
                    evidence_array = promise.get('evidence', [])
                    
                    # Check for bidirectional link
                    is_bidirectional = (evidence_id in linked_evidence_ids or 
                                      any(e.get('evidence_id') == evidence_id for e in evidence_array))
                    
                    link_info = {
                        'promise_id': promise_id,
                        'evidence_id': evidence_id,
                        'bidirectional': is_bidirectional,
                        'promise_text': promise.get('text', '')[:200],
                        'evidence_title': evidence.get('title_or_summary', ''),
                        'evidence_type': evidence.get('evidence_source_type', ''),
                        'promise_department': promise.get('responsible_department_lead', ''),
                        'evidence_departments': evidence.get('linked_departments', []),
                        'parliament_session': promise.get('parliament_session_id', '')
                    }
                    
                    successful_links.append(link_info)
                    
                    # Specifically track bill links
                    if 'Bill Event' in evidence.get('evidence_source_type', ''):
                        bill_links.append(link_info)
        
        # Store results
        self.investigation_results['backup_analysis']['successful_links'] = {
            'total_links': len(successful_links),
            'bidirectional_links': len([l for l in successful_links if l['bidirectional']]),
            'bill_links': len(bill_links),
            'by_evidence_type': Counter(l['evidence_type'] for l in successful_links),
            'by_parliament_session': Counter(l['parliament_session'] for l in successful_links)
        }
        
        print(f"  ✅ Found {len(successful_links)} successful links ({len(bill_links)} bill links)")
        return successful_links
    
    async def analyze_current_promises(self) -> List[Dict[str, Any]]:
        """Analyze current promises collection."""
        print("  📥 Fetching current promises...")
        
        try:
            current_ref = self.db.collection('promises')
            current_docs = current_ref.stream()
            
            current_promises = []
            promises_with_links = 0
            
            for doc in current_docs:
                data = doc.to_dict()
                data['id'] = doc.id
                current_promises.append(data)
                
                # Count links
                linked_evidence_ids = data.get('linked_evidence_ids', [])
                evidence_array = data.get('evidence', [])
                
                if linked_evidence_ids or evidence_array:
                    promises_with_links += 1
            
            self.investigation_results['current_analysis']['promises'] = {
                'total_count': len(current_promises),
                'with_links': promises_with_links
            }
            
            print(f"  ✅ Current promises: {len(current_promises)} total, {promises_with_links} with links")
            return current_promises
            
        except Exception as e:
            print(f"  ❌ Error analyzing current promises: {e}")
            return []
    
    async def analyze_current_evidence(self) -> List[Dict[str, Any]]:
        """Analyze current evidence collection."""
        print("  📥 Fetching current evidence...")
        
        try:
            current_ref = self.db.collection('evidence_items')
            current_docs = current_ref.stream()
            
            current_evidence = []
            evidence_with_links = 0
            
            for doc in current_docs:
                data = doc.to_dict()
                data['id'] = doc.id
                current_evidence.append(data)
                
                # Count links
                promise_ids = data.get('promise_ids', [])
                if promise_ids:
                    evidence_with_links += 1
            
            self.investigation_results['current_analysis']['evidence'] = {
                'total_count': len(current_evidence),
                'with_links': evidence_with_links
            }
            
            print(f"  ✅ Current evidence: {len(current_evidence)} total, {evidence_with_links} with links")
            return current_evidence
            
        except Exception as e:
            print(f"  ❌ Error analyzing current evidence: {e}")
            return []
    
    async def compare_data_structures(self, backup_promises: List[Dict[str, Any]], 
                                    backup_evidence: List[Dict[str, Any]],
                                    current_promises: List[Dict[str, Any]], 
                                    current_evidence: List[Dict[str, Any]]):
        """Compare data structures between backup and current."""
        print("  ⚖️ Comparing data structures...")
        
        # Compare promise fields
        backup_promise_fields = set()
        current_promise_fields = set()
        
        for promise in backup_promises[:10]:  # Sample first 10
            backup_promise_fields.update(promise.keys())
        
        for promise in current_promises[:10]:  # Sample first 10
            current_promise_fields.update(promise.keys())
        
        # Compare evidence fields
        backup_evidence_fields = set()
        current_evidence_fields = set()
        
        for evidence in backup_evidence[:10]:  # Sample first 10
            backup_evidence_fields.update(evidence.keys())
        
        for evidence in current_evidence[:10]:  # Sample first 10
            current_evidence_fields.update(evidence.keys())
        
        # Store comparison
        self.investigation_results['comparison'] = {
            'promise_fields': {
                'backup_only': list(backup_promise_fields - current_promise_fields),
                'current_only': list(current_promise_fields - backup_promise_fields),
                'common': list(backup_promise_fields.intersection(current_promise_fields))
            },
            'evidence_fields': {
                'backup_only': list(backup_evidence_fields - current_evidence_fields),
                'current_only': list(current_evidence_fields - backup_evidence_fields),
                'common': list(backup_evidence_fields.intersection(current_evidence_fields))
            },
            'data_counts': {
                'backup_promises': len(backup_promises),
                'current_promises': len(current_promises),
                'backup_evidence': len(backup_evidence),
                'current_evidence': len(current_evidence)
            }
        }
        
        print(f"  📊 Promise fields - Backup only: {len(backup_promise_fields - current_promise_fields)}")
        print(f"  📊 Evidence fields - Backup only: {len(backup_evidence_fields - current_evidence_fields)}")
    
    async def generate_test_cases(self, successful_links: List[Dict[str, Any]], 
                                current_promises: List[Dict[str, Any]], 
                                current_evidence: List[Dict[str, Any]]):
        """Generate test cases based on successful backup links."""
        print("  🧪 Generating test cases...")
        
        # Create lookup dictionaries for current data
        current_promise_lookup = {}
        current_evidence_lookup = {}
        
        # Try to match by text/title for promises
        for promise in current_promises:
            text = promise.get('text', '').strip()
            if text:
                current_promise_lookup[text] = promise
        
        # Try to match by title for evidence
        for evidence in current_evidence:
            title = evidence.get('title_or_summary', '').strip()
            if title:
                current_evidence_lookup[title] = evidence
        
        test_cases = []
        
        # Focus on bill links for testing
        bill_links = [l for l in successful_links if 'Bill Event' in l['evidence_type']]
        
        for link in bill_links[:10]:  # Top 10 bill links
            # Try to find matching promise in current data
            promise_text = link['promise_text'].strip()
            evidence_title = link['evidence_title'].strip()
            
            current_promise = current_promise_lookup.get(promise_text)
            current_evidence = current_evidence_lookup.get(evidence_title)
            
            if current_promise and current_evidence:
                test_case = {
                    'backup_promise_id': link['promise_id'],
                    'backup_evidence_id': link['evidence_id'],
                    'current_promise_id': current_promise['id'],
                    'current_evidence_id': current_evidence['id'],
                    'promise_text': promise_text[:200],
                    'evidence_title': evidence_title,
                    'evidence_type': link['evidence_type'],
                    'department_match': link['promise_department'] in link['evidence_departments'],
                    'parliament_session': link['parliament_session'],
                    'test_priority': 'high'  # Bill links are high priority
                }
                test_cases.append(test_case)
        
        # Add some non-bill test cases
        non_bill_links = [l for l in successful_links if 'Bill Event' not in l['evidence_type']]
        for link in non_bill_links[:5]:  # Top 5 non-bill links
            promise_text = link['promise_text'].strip()
            evidence_title = link['evidence_title'].strip()
            
            current_promise = current_promise_lookup.get(promise_text)
            current_evidence = current_evidence_lookup.get(evidence_title)
            
            if current_promise and current_evidence:
                test_case = {
                    'backup_promise_id': link['promise_id'],
                    'backup_evidence_id': link['evidence_id'],
                    'current_promise_id': current_promise['id'],
                    'current_evidence_id': current_evidence['id'],
                    'promise_text': promise_text[:200],
                    'evidence_title': evidence_title,
                    'evidence_type': link['evidence_type'],
                    'department_match': link['promise_department'] in link['evidence_departments'],
                    'parliament_session': link['parliament_session'],
                    'test_priority': 'medium'
                }
                test_cases.append(test_case)
        
        self.investigation_results['test_cases'] = test_cases
        
        print(f"  ✅ Generated {len(test_cases)} test cases")
        
        # Generate recommendations
        recommendations = []
        
        if len(test_cases) == 0:
            recommendations.append("No matching test cases found - data structure may have changed significantly")
        
        if self.investigation_results['current_analysis']['promises']['with_links'] == 0:
            recommendations.append("Current promises have no links - linking system may not be working")
        
        if self.investigation_results['current_analysis']['evidence']['with_links'] == 0:
            recommendations.append("Current evidence has no links - check promise_ids field population")
        
        backup_links = self.investigation_results['backup_analysis']['successful_links']['total_links']
        if backup_links > 100:
            recommendations.append(f"Backup had {backup_links} successful links - investigate why current system isn't creating links")
        
        self.investigation_results['recommendations'] = recommendations
    
    async def export_results(self):
        """Export investigation results."""
        print("  💾 Exporting investigation results...")
        
        # Create output directory
        os.makedirs('investigation_results', exist_ok=True)
        
        # 1. JSON export
        with open('investigation_results/backup_investigation.json', 'w') as f:
            json.dump(self.investigation_results, f, indent=2, default=str)
        
        # 2. Test cases CSV
        if self.investigation_results['test_cases']:
            df = pd.DataFrame(self.investigation_results['test_cases'])
            df.to_csv('investigation_results/test_cases.csv', index=False)
        
        # 3. Generate investigation report
        await self.generate_investigation_report()
        
        print("    ✅ Results exported to investigation_results/")
    
    async def generate_investigation_report(self):
        """Generate comprehensive investigation report."""
        backup_analysis = self.investigation_results['backup_analysis']
        current_analysis = self.investigation_results['current_analysis']
        comparison = self.investigation_results['comparison']
        test_cases = self.investigation_results['test_cases']
        recommendations = self.investigation_results['recommendations']
        
        report = f"""
# Backup Data Investigation Report
Generated: {self.investigation_results['timestamp']}

## Executive Summary

### Backup Data Analysis
- **Backup Promises**: {backup_analysis.get('promises', {}).get('total_count', 0):,} total, {backup_analysis.get('promises', {}).get('with_links', 0):,} with links
- **Backup Evidence**: {backup_analysis.get('evidence', {}).get('total_count', 0):,} total, {backup_analysis.get('evidence', {}).get('with_links', 0):,} with links
- **Successful Links**: {backup_analysis.get('successful_links', {}).get('total_links', 0):,} total links found

### Current Data Analysis
- **Current Promises**: {current_analysis.get('promises', {}).get('total_count', 0):,} total, {current_analysis.get('promises', {}).get('with_links', 0):,} with links
- **Current Evidence**: {current_analysis.get('evidence', {}).get('total_count', 0):,} total, {current_analysis.get('evidence', {}).get('with_links', 0):,} with links

### Key Findings
"""
        
        # Add key findings
        backup_promise_links = backup_analysis.get('promises', {}).get('with_links', 0)
        current_promise_links = current_analysis.get('promises', {}).get('with_links', 0)
        
        if backup_promise_links > 0 and current_promise_links == 0:
            report += """
🚨 **CRITICAL ISSUE**: Backup data shows {backup_promise_links:,} promises with links, but current data shows 0 links.
This indicates a significant regression in the linking system.
"""
        
        backup_evidence_links = backup_analysis.get('evidence', {}).get('with_links', 0)
        current_evidence_links = current_analysis.get('evidence', {}).get('with_links', 0)
        
        if backup_evidence_links > 0 and current_evidence_links == 0:
            report += f"""
🚨 **CRITICAL ISSUE**: Backup data shows {backup_evidence_links:,} evidence items with links, but current data shows 0 links.
"""
        
        report += f"""

## Detailed Analysis

### Successful Links in Backup
- **Total Links**: {backup_analysis.get('successful_links', {}).get('total_links', 0):,}
- **Bidirectional Links**: {backup_analysis.get('successful_links', {}).get('bidirectional_links', 0):,}
- **Bill Links**: {backup_analysis.get('successful_links', {}).get('bill_links', 0):,}

### Links by Evidence Type
"""
        
        evidence_types = backup_analysis.get('successful_links', {}).get('by_evidence_type', {})
        for evidence_type, count in evidence_types.items():
            report += f"- **{evidence_type}**: {count:,} links\n"
        
        report += f"""

### Links by Parliament Session
"""
        
        sessions = backup_analysis.get('successful_links', {}).get('by_parliament_session', {})
        for session, count in sessions.items():
            report += f"- **Session {session}**: {count:,} links\n"
        
        report += f"""

## Data Structure Comparison

### Promise Fields
- **Backup Only**: {len(comparison.get('promise_fields', {}).get('backup_only', []))} fields
- **Current Only**: {len(comparison.get('promise_fields', {}).get('current_only', []))} fields
- **Common**: {len(comparison.get('promise_fields', {}).get('common', []))} fields

### Evidence Fields
- **Backup Only**: {len(comparison.get('evidence_fields', {}).get('backup_only', []))} fields
- **Current Only**: {len(comparison.get('evidence_fields', {}).get('current_only', []))} fields
- **Common**: {len(comparison.get('evidence_fields', {}).get('common', []))} fields

## Test Cases Generated

**Total Test Cases**: {len(test_cases)}

### High Priority Test Cases (Bill Links)
"""
        
        high_priority_cases = [tc for tc in test_cases if tc.get('test_priority') == 'high']
        for i, case in enumerate(high_priority_cases[:5], 1):
            report += f"""
**Test Case {i}**:
- Promise: {case['promise_text'][:100]}...
- Evidence: {case['evidence_title'][:100]}
- Type: {case['evidence_type']}
- Department Match: {case['department_match']}
- Session: {case['parliament_session']}
"""
        
        report += f"""

## Recommendations

"""
        
        for i, rec in enumerate(recommendations, 1):
            report += f"{i}. {rec}\n"
        
        report += f"""

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
"""
        
        with open('investigation_results/investigation_report.md', 'w') as f:
            f.write(report)
        
        print("    📄 Investigation report saved to investigation_results/investigation_report.md")

async def main():
    """Main execution function."""
    investigator = BackupDataInvestigator()
    results = await investigator.run_investigation()
    
    print("\n" + "=" * 60)
    print("🎉 BACKUP INVESTIGATION COMPLETE!")
    print("=" * 60)
    
    backup_analysis = results['backup_analysis']
    current_analysis = results['current_analysis']
    test_cases = results['test_cases']
    
    print(f"📊 Backup links found: {backup_analysis.get('successful_links', {}).get('total_links', 0):,}")
    print(f"📊 Current promise links: {current_analysis.get('promises', {}).get('with_links', 0):,}")
    print(f"📊 Current evidence links: {current_analysis.get('evidence', {}).get('with_links', 0):,}")
    print(f"🧪 Test cases generated: {len(test_cases)}")
    print("\n📁 Results saved to: investigation_results/")
    print("📄 Full report: investigation_results/investigation_report.md")
    print("🧪 Test cases: investigation_results/test_cases.csv")

if __name__ == "__main__":
    asyncio.run(main()) 