#!/usr/bin/env python3
"""
Promise-Evidence Linking Analysis Script
Task 1.1: Current Link Statistics Report

This script analyzes the current state of promise-evidence links in the database
to understand distribution, quality, and identify patterns.
"""

import asyncio
import json
import csv
import os
from datetime import datetime, timezone
from collections import defaultdict, Counter
from typing import Dict, List, Any, Tuple
import matplotlib.pyplot as plt
import plotly.graph_objects as go
import plotly.express as px
from plotly.subplots import make_subplots
import pandas as pd

# Firebase imports
import firebase_admin
from firebase_admin import credentials, firestore
from google.cloud.firestore_v1.base_query import FieldFilter

# Initialize Firebase Admin if not already done
try:
    firebase_admin.get_app()
except ValueError:
    # Initialize with default credentials
    firebase_admin.initialize_app()

db = firestore.client()

class PromiseEvidenceLinkAnalyzer:
    """Analyzes current promise-evidence links in the database."""
    
    def __init__(self):
        self.db = db
        self.results = {
            'timestamp': datetime.now(timezone.utc).isoformat(),
            'summary': {},
            'promises': {},
            'evidence': {},
            'links': {},
            'distributions': {},
            'quality_indicators': {}
        }
        
    async def run_complete_analysis(self) -> Dict[str, Any]:
        """Run the complete analysis pipeline."""
        print("🔍 Starting Promise-Evidence Link Analysis...")
        print("=" * 60)
        
        # Step 1: Fetch all data
        print("📊 Step 1: Fetching data from Firestore...")
        promises_data = await self.fetch_promises_data()
        evidence_data = await self.fetch_evidence_data()
        
        # Step 2: Analyze promises
        print("🎯 Step 2: Analyzing promises...")
        await self.analyze_promises(promises_data)
        
        # Step 3: Analyze evidence
        print("📋 Step 3: Analyzing evidence...")
        await self.analyze_evidence(evidence_data)
        
        # Step 4: Analyze linking patterns
        print("🔗 Step 4: Analyzing linking patterns...")
        await self.analyze_linking_patterns(promises_data, evidence_data)
        
        # Step 5: Generate summary statistics
        print("📈 Step 5: Generating summary statistics...")
        await self.generate_summary_statistics()
        
        # Step 6: Create visualizations
        print("📊 Step 6: Creating visualizations...")
        await self.create_visualizations()
        
        # Step 7: Export results
        print("💾 Step 7: Exporting results...")
        await self.export_results()
        
        print("✅ Analysis complete!")
        return self.results
    
    async def fetch_promises_data(self) -> List[Dict[str, Any]]:
        """Fetch all promises from Firestore."""
        print("  📥 Fetching promises...")
        
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
        print("  📥 Fetching evidence items...")
        
        evidence_ref = self.db.collection('evidence_items')
        evidence_docs = evidence_ref.stream()
        
        evidence_data = []
        for doc in evidence_docs:
            data = doc.to_dict()
            data['id'] = doc.id
            evidence_data.append(data)
        
        print(f"  ✅ Fetched {len(evidence_data)} evidence items")
        return evidence_data
    
    async def analyze_promises(self, promises_data: List[Dict[str, Any]]):
        """Analyze promise data and linking status."""
        print("  🎯 Analyzing promise characteristics...")
        
        total_promises = len(promises_data)
        promises_with_legacy_links = 0
        promises_with_evidence_array = 0
        
        # Distribution counters
        session_dist = Counter()
        party_dist = Counter()
        department_dist = Counter()
        source_type_dist = Counter()
        rank_dist = Counter()
        
        # Evidence count distribution
        evidence_count_dist = Counter()
        
        for promise in promises_data:
            # Basic distributions
            session_dist[promise.get('parliament_session_id', 'Unknown')] += 1
            party_dist[promise.get('party_code', 'Unknown')] += 1
            department_dist[promise.get('responsible_department_lead', 'Unknown')] += 1
            source_type_dist[promise.get('source_type', 'Unknown')] += 1
            rank_dist[promise.get('bc_promise_rank', 'None')] += 1
            
            # Check linking methods
            linked_evidence_ids = promise.get('linked_evidence_ids', [])
            evidence_array = promise.get('evidence', [])
            
            if linked_evidence_ids:
                promises_with_legacy_links += 1
                evidence_count_dist[len(linked_evidence_ids)] += 1
            elif evidence_array:
                promises_with_evidence_array += 1
                evidence_count_dist[len(evidence_array)] += 1
            else:
                evidence_count_dist[0] += 1
        
        # Store results
        self.results['promises'] = {
            'total_count': total_promises,
            'with_legacy_links': promises_with_legacy_links,
            'with_evidence_array': promises_with_evidence_array,
            'without_links': total_promises - promises_with_legacy_links - promises_with_evidence_array,
            'distributions': {
                'parliament_session': dict(session_dist),
                'party': dict(party_dist),
                'department': dict(department_dist),
                'source_type': dict(source_type_dist),
                'bc_promise_rank': dict(rank_dist),
                'evidence_count': dict(evidence_count_dist)
            }
        }
        
        print(f"    📊 Total promises: {total_promises}")
        print(f"    🔗 With legacy links: {promises_with_legacy_links}")
        print(f"    📋 With evidence array: {promises_with_evidence_array}")
        print(f"    ❌ Without links: {total_promises - promises_with_legacy_links - promises_with_evidence_array}")
    
    async def analyze_evidence(self, evidence_data: List[Dict[str, Any]]):
        """Analyze evidence data and linking status."""
        print("  📋 Analyzing evidence characteristics...")
        
        total_evidence = len(evidence_data)
        evidence_with_promise_links = 0
        
        # Distribution counters
        source_type_dist = Counter()
        session_dist = Counter()
        department_dist = Counter()
        linking_status_dist = Counter()
        
        # Promise count distribution
        promise_count_dist = Counter()
        
        # Date analysis
        evidence_dates = []
        
        for evidence in evidence_data:
            # Basic distributions
            source_type_dist[evidence.get('evidence_source_type', 'Unknown')] += 1
            session_dist[evidence.get('parliament_session_id', 'Unknown')] += 1
            linking_status_dist[evidence.get('promise_linking_status', 'Unknown')] += 1
            
            # Department analysis
            departments = evidence.get('linked_departments', [])
            if departments:
                for dept in departments:
                    department_dist[dept] += 1
            else:
                department_dist['None'] += 1
            
            # Promise linking analysis
            promise_ids = evidence.get('promise_ids', [])
            if promise_ids:
                evidence_with_promise_links += 1
                promise_count_dist[len(promise_ids)] += 1
            else:
                promise_count_dist[0] += 1
            
            # Date analysis
            evidence_date = evidence.get('evidence_date')
            if evidence_date:
                try:
                    if hasattr(evidence_date, 'timestamp'):
                        # Firestore Timestamp
                        evidence_dates.append(evidence_date.timestamp())
                    elif isinstance(evidence_date, str):
                        # String date
                        dt = datetime.fromisoformat(evidence_date.replace('Z', '+00:00'))
                        evidence_dates.append(dt.timestamp())
                except Exception as e:
                    print(f"    ⚠️  Date parsing error: {e}")
        
        # Store results
        self.results['evidence'] = {
            'total_count': total_evidence,
            'with_promise_links': evidence_with_promise_links,
            'without_links': total_evidence - evidence_with_promise_links,
            'distributions': {
                'source_type': dict(source_type_dist),
                'parliament_session': dict(session_dist),
                'department': dict(department_dist),
                'linking_status': dict(linking_status_dist),
                'promise_count': dict(promise_count_dist)
            },
            'date_analysis': {
                'total_with_dates': len(evidence_dates),
                'date_range': {
                    'earliest': min(evidence_dates) if evidence_dates else None,
                    'latest': max(evidence_dates) if evidence_dates else None
                }
            }
        }
        
        print(f"    📊 Total evidence: {total_evidence}")
        print(f"    🔗 With promise links: {evidence_with_promise_links}")
        print(f"    ❌ Without links: {total_evidence - evidence_with_promise_links}")
    
    async def analyze_linking_patterns(self, promises_data: List[Dict[str, Any]], 
                                     evidence_data: List[Dict[str, Any]]):
        """Analyze patterns in promise-evidence linking."""
        print("  🔗 Analyzing linking patterns...")
        
        # Create lookup dictionaries
        evidence_lookup = {item['id']: item for item in evidence_data}
        promise_lookup = {item['id']: item for item in promises_data}
        
        # Track bidirectional consistency
        legacy_links = []  # (promise_id, evidence_id) from linked_evidence_ids
        current_links = []  # (promise_id, evidence_id) from promise_ids
        
        # Collect legacy links
        for promise in promises_data:
            promise_id = promise['id']
            linked_evidence_ids = promise.get('linked_evidence_ids', [])
            for evidence_id in linked_evidence_ids:
                legacy_links.append((promise_id, evidence_id))
        
        # Collect current links
        for evidence in evidence_data:
            evidence_id = evidence['id']
            promise_ids = evidence.get('promise_ids', [])
            for promise_id in promise_ids:
                current_links.append((promise_id, evidence_id))
        
        # Analyze consistency
        legacy_set = set(legacy_links)
        current_set = set(current_links)
        
        consistent_links = legacy_set.intersection(current_set)
        legacy_only = legacy_set - current_set
        current_only = current_set - legacy_set
        
        # Analyze link quality indicators
        department_alignment = 0
        temporal_relevance = 0
        
        for promise_id, evidence_id in consistent_links:
            promise = promise_lookup.get(promise_id)
            evidence = evidence_lookup.get(evidence_id)
            
            if promise and evidence:
                # Check department alignment
                promise_dept = promise.get('responsible_department_lead', '')
                evidence_depts = evidence.get('linked_departments', [])
                if promise_dept in evidence_depts:
                    department_alignment += 1
                
                # Check temporal relevance (evidence after promise)
                promise_date = promise.get('date_issued')
                evidence_date = evidence.get('evidence_date')
                if promise_date and evidence_date:
                    try:
                        # Simple temporal check
                        temporal_relevance += 1
                    except Exception:
                        pass
        
        # Store results
        self.results['links'] = {
            'legacy_links': len(legacy_links),
            'current_links': len(current_links),
            'consistent_links': len(consistent_links),
            'legacy_only': len(legacy_only),
            'current_only': len(current_only),
            'consistency_rate': len(consistent_links) / max(len(legacy_set.union(current_set)), 1),
            'quality_indicators': {
                'department_alignment': department_alignment,
                'department_alignment_rate': department_alignment / max(len(consistent_links), 1),
                'temporal_relevance': temporal_relevance,
                'temporal_relevance_rate': temporal_relevance / max(len(consistent_links), 1)
            }
        }
        
        print(f"    🔗 Legacy links: {len(legacy_links)}")
        print(f"    🔗 Current links: {len(current_links)}")
        print(f"    ✅ Consistent links: {len(consistent_links)}")
        print(f"    📊 Consistency rate: {self.results['links']['consistency_rate']:.2%}")
    
    async def generate_summary_statistics(self):
        """Generate high-level summary statistics."""
        print("  📈 Generating summary statistics...")
        
        promises = self.results['promises']
        evidence = self.results['evidence']
        links = self.results['links']
        
        # Calculate key metrics
        total_promises = promises['total_count']
        total_evidence = evidence['total_count']
        linked_promises = promises['with_legacy_links'] + promises['with_evidence_array']
        linked_evidence = evidence['with_promise_links']
        
        self.results['summary'] = {
            'total_promises': total_promises,
            'total_evidence': total_evidence,
            'linked_promises': linked_promises,
            'linked_evidence': linked_evidence,
            'promise_linking_rate': linked_promises / max(total_promises, 1),
            'evidence_linking_rate': linked_evidence / max(total_evidence, 1),
            'avg_evidence_per_promise': links['consistent_links'] / max(linked_promises, 1),
            'avg_promises_per_evidence': links['consistent_links'] / max(linked_evidence, 1),
            'data_consistency_score': links['consistency_rate'],
            'department_alignment_score': links['quality_indicators']['department_alignment_rate']
        }
        
        print(f"    📊 Promise linking rate: {self.results['summary']['promise_linking_rate']:.2%}")
        print(f"    📊 Evidence linking rate: {self.results['summary']['evidence_linking_rate']:.2%}")
        print(f"    📊 Data consistency score: {self.results['summary']['data_consistency_score']:.2%}")
    
    async def create_visualizations(self):
        """Create visualization charts."""
        print("  📊 Creating visualizations...")
        
        # Create output directory
        os.makedirs('analysis_results/charts', exist_ok=True)
        
        # 1. Promise linking status pie chart
        fig = go.Figure(data=[go.Pie(
            labels=['Linked (Legacy)', 'Linked (Evidence Array)', 'Not Linked'],
            values=[
                self.results['promises']['with_legacy_links'],
                self.results['promises']['with_evidence_array'],
                self.results['promises']['without_links']
            ],
            title="Promise Linking Status"
        )])
        fig.write_html('analysis_results/charts/promise_linking_status.html')
        
        # 2. Evidence source type distribution
        source_types = self.results['evidence']['distributions']['source_type']
        fig = px.bar(
            x=list(source_types.keys()),
            y=list(source_types.values()),
            title="Evidence Items by Source Type"
        )
        fig.write_html('analysis_results/charts/evidence_source_types.html')
        
        # 3. Parliament session distribution
        session_dist = self.results['promises']['distributions']['parliament_session']
        fig = px.bar(
            x=list(session_dist.keys()),
            y=list(session_dist.values()),
            title="Promises by Parliament Session"
        )
        fig.write_html('analysis_results/charts/promises_by_session.html')
        
        # 4. Department distribution (top 10)
        dept_dist = self.results['promises']['distributions']['department']
        top_depts = dict(sorted(dept_dist.items(), key=lambda x: x[1], reverse=True)[:10])
        fig = px.bar(
            x=list(top_depts.values()),
            y=list(top_depts.keys()),
            orientation='h',
            title="Top 10 Departments by Promise Count"
        )
        fig.write_html('analysis_results/charts/top_departments.html')
        
        print("    ✅ Visualizations saved to analysis_results/charts/")
    
    async def export_results(self):
        """Export results to various formats."""
        print("  💾 Exporting results...")
        
        # Create output directory
        os.makedirs('analysis_results', exist_ok=True)
        
        # 1. JSON export
        with open('analysis_results/current_linking_state.json', 'w') as f:
            json.dump(self.results, f, indent=2, default=str)
        
        # 2. CSV exports
        # Summary statistics
        summary_df = pd.DataFrame([self.results['summary']])
        summary_df.to_csv('analysis_results/summary_statistics.csv', index=False)
        
        # Promise distributions
        for dist_name, dist_data in self.results['promises']['distributions'].items():
            df = pd.DataFrame(list(dist_data.items()), columns=[dist_name, 'count'])
            df.to_csv(f'analysis_results/promises_{dist_name}_distribution.csv', index=False)
        
        # Evidence distributions
        for dist_name, dist_data in self.results['evidence']['distributions'].items():
            df = pd.DataFrame(list(dist_data.items()), columns=[dist_name, 'count'])
            df.to_csv(f'analysis_results/evidence_{dist_name}_distribution.csv', index=False)
        
        # 3. Generate report
        await self.generate_report()
        
        print("    ✅ Results exported to analysis_results/")
    
    async def generate_report(self):
        """Generate a comprehensive analysis report."""
        report = f"""
# Promise-Evidence Linking Analysis Report
Generated: {self.results['timestamp']}

## Executive Summary

### Key Metrics
- **Total Promises**: {self.results['summary']['total_promises']:,}
- **Total Evidence Items**: {self.results['summary']['total_evidence']:,}
- **Promise Linking Rate**: {self.results['summary']['promise_linking_rate']:.1%}
- **Evidence Linking Rate**: {self.results['summary']['evidence_linking_rate']:.1%}
- **Data Consistency Score**: {self.results['summary']['data_consistency_score']:.1%}

### Data Quality Assessment
- **Bidirectional Consistency**: {self.results['links']['consistency_rate']:.1%}
- **Department Alignment**: {self.results['links']['quality_indicators']['department_alignment_rate']:.1%}
- **Legacy Links**: {self.results['links']['legacy_links']:,}
- **Current Links**: {self.results['links']['current_links']:,}

## Detailed Findings

### Promise Analysis
- **Total Promises**: {self.results['promises']['total_count']:,}
- **With Legacy Links**: {self.results['promises']['with_legacy_links']:,}
- **With Evidence Array**: {self.results['promises']['with_evidence_array']:,}
- **Without Links**: {self.results['promises']['without_links']:,}

### Evidence Analysis
- **Total Evidence Items**: {self.results['evidence']['total_count']:,}
- **With Promise Links**: {self.results['evidence']['with_promise_links']:,}
- **Without Links**: {self.results['evidence']['without_links']:,}

### Linking Patterns
- **Consistent Links**: {self.results['links']['consistent_links']:,}
- **Legacy Only**: {self.results['links']['legacy_only']:,}
- **Current Only**: {self.results['links']['current_only']:,}

## Recommendations

### Data Integrity
1. **Address Bidirectional Inconsistencies**: {self.results['links']['legacy_only'] + self.results['links']['current_only']:,} links need reconciliation
2. **Standardize Linking Approach**: Migrate from legacy `linked_evidence_ids` to `promise_ids` approach
3. **Improve Department Alignment**: {(1 - self.results['links']['quality_indicators']['department_alignment_rate']):.1%} of links lack department alignment

### Coverage Improvement
1. **Increase Promise Linking**: {(1 - self.results['summary']['promise_linking_rate']):.1%} of promises lack evidence
2. **Increase Evidence Linking**: {(1 - self.results['summary']['evidence_linking_rate']):.1%} of evidence items are unlinked

### Quality Enhancement
1. **Review Low-Quality Links**: Focus on links without department alignment
2. **Implement Quality Scoring**: Add confidence scores to existing links
3. **Automate Quality Checks**: Set up monitoring for data consistency

## Next Steps
1. Run data integrity check script
2. Implement bidirectional consistency fixes
3. Begin frontend component testing
4. Optimize linking algorithm parameters
"""
        
        with open('analysis_results/analysis_report.md', 'w') as f:
            f.write(report)
        
        print("    📄 Analysis report saved to analysis_results/analysis_report.md")

async def main():
    """Main execution function."""
    analyzer = PromiseEvidenceLinkAnalyzer()
    results = await analyzer.run_complete_analysis()
    
    print("\n" + "=" * 60)
    print("🎉 ANALYSIS COMPLETE!")
    print("=" * 60)
    print(f"📊 Analyzed {results['summary']['total_promises']:,} promises")
    print(f"📋 Analyzed {results['summary']['total_evidence']:,} evidence items")
    print(f"🔗 Found {results['links']['consistent_links']:,} consistent links")
    print(f"📈 Data consistency: {results['summary']['data_consistency_score']:.1%}")
    print("\n📁 Results saved to: analysis_results/")
    print("📄 Full report: analysis_results/analysis_report.md")
    print("📊 Charts: analysis_results/charts/")

if __name__ == "__main__":
    asyncio.run(main()) 