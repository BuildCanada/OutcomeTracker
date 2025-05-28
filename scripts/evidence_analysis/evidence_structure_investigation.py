#!/usr/bin/env python3
"""
Evidence Structure Investigation Script
Investigates the fundamental differences between LLM-generated evidence (backup) and real evidence (current)

This script:
1. Analyzes content patterns in backup vs. current evidence
2. Compares field usage and data quality
3. Identifies what makes evidence linkable to promises
4. Provides insights for algorithm redesign
"""

import asyncio
import json
import os
from datetime import datetime, timezone
from collections import defaultdict, Counter
from typing import Dict, List, Any, Optional
import re
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

class EvidenceStructureInvestigator:
    """Investigates structural differences between backup and current evidence."""
    
    def __init__(self):
        self.db = db
        self.investigation_results = {
            'timestamp': datetime.now(timezone.utc).isoformat(),
            'backup_evidence_analysis': {},
            'current_evidence_analysis': {},
            'structural_comparison': {},
            'content_analysis': {},
            'linking_insights': [],
            'algorithm_recommendations': []
        }
        
    async def run_investigation(self) -> Dict[str, Any]:
        """Run the complete evidence structure investigation."""
        print("🔍 Starting Evidence Structure Investigation...")
        print("=" * 60)
        
        # Step 1: Analyze backup evidence structure
        print("📊 Step 1: Analyzing backup evidence structure...")
        backup_evidence = await self.analyze_backup_evidence_structure()
        
        # Step 2: Analyze current evidence structure
        print("📋 Step 2: Analyzing current evidence structure...")
        current_evidence = await self.analyze_current_evidence_structure()
        
        # Step 3: Compare structures
        print("⚖️ Step 3: Comparing evidence structures...")
        await self.compare_evidence_structures(backup_evidence, current_evidence)
        
        # Step 4: Analyze content patterns
        print("📝 Step 4: Analyzing content patterns...")
        await self.analyze_content_patterns(backup_evidence, current_evidence)
        
        # Step 5: Generate linking insights
        print("💡 Step 5: Generating linking insights...")
        await self.generate_linking_insights()
        
        # Step 6: Export results
        print("💾 Step 6: Exporting investigation results...")
        await self.export_results()
        
        print("✅ Evidence structure investigation complete!")
        return self.investigation_results
    
    async def analyze_backup_evidence_structure(self) -> List[Dict[str, Any]]:
        """Analyze the structure and content of backup evidence."""
        print("  📥 Fetching backup evidence...")
        
        try:
            backup_ref = self.db.collection('evidence_items_backup_20250527_212346')
            backup_docs = backup_ref.limit(500).stream()  # Sample for analysis
            
            backup_evidence = []
            field_usage = defaultdict(int)
            field_types = defaultdict(set)
            content_lengths = defaultdict(list)
            evidence_types = Counter()
            departments = Counter()
            
            for doc in backup_docs:
                data = doc.to_dict()
                data['id'] = doc.id
                backup_evidence.append(data)
                
                # Analyze field usage
                for field, value in data.items():
                    if value is not None and value != '' and value != []:
                        field_usage[field] += 1
                        field_types[field].add(type(value).__name__)
                        
                        # Track content lengths for text fields
                        if isinstance(value, str):
                            content_lengths[field].append(len(value))
                
                # Track evidence types and departments
                evidence_types[data.get('evidence_source_type', 'Unknown')] += 1
                linked_depts = data.get('linked_departments', [])
                if isinstance(linked_depts, list):
                    for dept in linked_depts:
                        departments[dept] += 1
            
            # Calculate statistics
            total_docs = len(backup_evidence)
            
            self.investigation_results['backup_evidence_analysis'] = {
                'total_documents': total_docs,
                'field_usage': dict(field_usage),
                'field_usage_percentages': {field: (count/total_docs)*100 for field, count in field_usage.items()},
                'field_types': {field: list(types) for field, types in field_types.items()},
                'content_length_stats': {
                    field: {
                        'avg': sum(lengths)/len(lengths) if lengths else 0,
                        'min': min(lengths) if lengths else 0,
                        'max': max(lengths) if lengths else 0,
                        'count': len(lengths)
                    } for field, lengths in content_lengths.items()
                },
                'evidence_types': dict(evidence_types),
                'top_departments': dict(departments.most_common(10)),
                'with_promise_links': len([e for e in backup_evidence if e.get('promise_ids', [])]),
                'avg_promise_links': sum(len(e.get('promise_ids', [])) for e in backup_evidence) / total_docs
            }
            
            print(f"  ✅ Analyzed {total_docs} backup evidence items")
            return backup_evidence
            
        except Exception as e:
            print(f"  ❌ Error analyzing backup evidence: {e}")
            return []
    
    async def analyze_current_evidence_structure(self) -> List[Dict[str, Any]]:
        """Analyze the structure and content of current evidence."""
        print("  📥 Fetching current evidence...")
        
        try:
            current_ref = self.db.collection('evidence_items')
            current_docs = current_ref.limit(500).stream()  # Sample for analysis
            
            current_evidence = []
            field_usage = defaultdict(int)
            field_types = defaultdict(set)
            content_lengths = defaultdict(list)
            evidence_types = Counter()
            departments = Counter()
            sources = Counter()
            
            for doc in current_docs:
                data = doc.to_dict()
                data['id'] = doc.id
                current_evidence.append(data)
                
                # Analyze field usage
                for field, value in data.items():
                    if value is not None and value != '' and value != []:
                        field_usage[field] += 1
                        field_types[field].add(type(value).__name__)
                        
                        # Track content lengths for text fields
                        if isinstance(value, str):
                            content_lengths[field].append(len(value))
                
                # Track evidence types, departments, and sources
                evidence_types[data.get('evidence_source_type', 'Unknown')] += 1
                
                linked_depts = data.get('linked_departments', [])
                if isinstance(linked_depts, list):
                    for dept in linked_depts:
                        departments[dept] += 1
                
                # Track data sources
                source = data.get('source_feed_name', data.get('source_type', 'Unknown'))
                sources[source] += 1
            
            # Calculate statistics
            total_docs = len(current_evidence)
            
            self.investigation_results['current_evidence_analysis'] = {
                'total_documents': total_docs,
                'field_usage': dict(field_usage),
                'field_usage_percentages': {field: (count/total_docs)*100 for field, count in field_usage.items()},
                'field_types': {field: list(types) for field, types in field_types.items()},
                'content_length_stats': {
                    field: {
                        'avg': sum(lengths)/len(lengths) if lengths else 0,
                        'min': min(lengths) if lengths else 0,
                        'max': max(lengths) if lengths else 0,
                        'count': len(lengths)
                    } for field, lengths in content_lengths.items()
                },
                'evidence_types': dict(evidence_types),
                'top_departments': dict(departments.most_common(10)),
                'data_sources': dict(sources),
                'with_promise_links': len([e for e in current_evidence if e.get('promise_ids', [])]),
                'avg_promise_links': sum(len(e.get('promise_ids', [])) for e in current_evidence) / total_docs if total_docs > 0 else 0
            }
            
            print(f"  ✅ Analyzed {total_docs} current evidence items")
            return current_evidence
            
        except Exception as e:
            print(f"  ❌ Error analyzing current evidence: {e}")
            return []
    
    async def compare_evidence_structures(self, backup_evidence: List[Dict[str, Any]], 
                                        current_evidence: List[Dict[str, Any]]):
        """Compare structural differences between backup and current evidence."""
        print("  ⚖️ Comparing evidence structures...")
        
        backup_analysis = self.investigation_results['backup_evidence_analysis']
        current_analysis = self.investigation_results['current_evidence_analysis']
        
        # Compare field usage
        backup_fields = set(backup_analysis['field_usage'].keys())
        current_fields = set(current_analysis['field_usage'].keys())
        
        # Compare evidence types
        backup_types = set(backup_analysis['evidence_types'].keys())
        current_types = set(current_analysis['evidence_types'].keys())
        
        # Compare departments
        backup_depts = set(backup_analysis['top_departments'].keys())
        current_depts = set(current_analysis['top_departments'].keys())
        
        self.investigation_results['structural_comparison'] = {
            'field_differences': {
                'backup_only_fields': list(backup_fields - current_fields),
                'current_only_fields': list(current_fields - backup_fields),
                'common_fields': list(backup_fields.intersection(current_fields)),
                'field_usage_changes': self._compare_field_usage(backup_analysis, current_analysis)
            },
            'evidence_type_differences': {
                'backup_only_types': list(backup_types - current_types),
                'current_only_types': list(current_types - backup_types),
                'common_types': list(backup_types.intersection(current_types)),
                'type_distribution_changes': self._compare_distributions(
                    backup_analysis['evidence_types'], 
                    current_analysis['evidence_types']
                )
            },
            'department_differences': {
                'backup_only_depts': list(backup_depts - current_depts),
                'current_only_depts': list(current_depts - backup_depts),
                'common_depts': list(backup_depts.intersection(current_depts))
            },
            'linking_comparison': {
                'backup_with_links': backup_analysis['with_promise_links'],
                'current_with_links': current_analysis['with_promise_links'],
                'backup_avg_links': backup_analysis['avg_promise_links'],
                'current_avg_links': current_analysis['avg_promise_links']
            }
        }
        
        print(f"  📊 Field differences: {len(backup_fields - current_fields)} backup-only, {len(current_fields - backup_fields)} current-only")
        print(f"  📊 Evidence type differences: {len(backup_types - current_types)} backup-only, {len(current_types - backup_types)} current-only")
    
    def _compare_field_usage(self, backup_analysis: Dict, current_analysis: Dict) -> Dict:
        """Compare field usage percentages between backup and current."""
        backup_usage = backup_analysis['field_usage_percentages']
        current_usage = current_analysis['field_usage_percentages']
        
        changes = {}
        for field in set(backup_usage.keys()).union(set(current_usage.keys())):
            backup_pct = backup_usage.get(field, 0)
            current_pct = current_usage.get(field, 0)
            change = current_pct - backup_pct
            
            if abs(change) > 5:  # Only track significant changes
                changes[field] = {
                    'backup_usage': backup_pct,
                    'current_usage': current_pct,
                    'change': change
                }
        
        return changes
    
    def _compare_distributions(self, backup_dist: Dict, current_dist: Dict) -> Dict:
        """Compare distribution changes between backup and current."""
        backup_total = sum(backup_dist.values())
        current_total = sum(current_dist.values())
        
        changes = {}
        for item in set(backup_dist.keys()).union(set(current_dist.keys())):
            backup_pct = (backup_dist.get(item, 0) / backup_total * 100) if backup_total > 0 else 0
            current_pct = (current_dist.get(item, 0) / current_total * 100) if current_total > 0 else 0
            change = current_pct - backup_pct
            
            if abs(change) > 2:  # Only track significant changes
                changes[item] = {
                    'backup_percentage': backup_pct,
                    'current_percentage': current_pct,
                    'change': change
                }
        
        return changes
    
    async def analyze_content_patterns(self, backup_evidence: List[Dict[str, Any]], 
                                     current_evidence: List[Dict[str, Any]]):
        """Analyze content patterns that affect linkability."""
        print("  📝 Analyzing content patterns...")
        
        # Sample evidence for detailed content analysis
        backup_sample = backup_evidence[:50]
        current_sample = current_evidence[:50]
        
        content_analysis = {
            'backup_content_patterns': self._analyze_content_sample(backup_sample, 'backup'),
            'current_content_patterns': self._analyze_content_sample(current_sample, 'current'),
            'linkability_factors': self._analyze_linkability_factors(backup_sample, current_sample)
        }
        
        self.investigation_results['content_analysis'] = content_analysis
        
        print(f"  📊 Analyzed content patterns in {len(backup_sample)} backup and {len(current_sample)} current samples")
    
    def _analyze_content_sample(self, evidence_sample: List[Dict[str, Any]], sample_type: str) -> Dict:
        """Analyze content patterns in a sample of evidence."""
        patterns = {
            'title_patterns': [],
            'content_characteristics': {},
            'keyword_density': {},
            'department_mentions': Counter(),
            'policy_terms': Counter(),
            'temporal_references': []
        }
        
        # Common policy terms to look for
        policy_terms = [
            'budget', 'funding', 'investment', 'program', 'initiative', 'policy', 
            'legislation', 'regulation', 'bill', 'act', 'commitment', 'promise',
            'announcement', 'launch', 'implement', 'establish', 'create', 'support'
        ]
        
        for evidence in evidence_sample:
            title = evidence.get('title_or_summary', '')
            content = evidence.get('full_text_scraped', '') or evidence.get('summary_or_snippet_raw', '')
            
            # Analyze title patterns
            if title:
                patterns['title_patterns'].append({
                    'length': len(title),
                    'word_count': len(title.split()),
                    'has_date': bool(re.search(r'\d{4}', title)),
                    'has_department': any(dept in title.lower() for dept in ['minister', 'department', 'canada', 'government']),
                    'title_sample': title[:100]
                })
            
            # Analyze content characteristics
            if content:
                word_count = len(content.split())
                patterns['content_characteristics'][evidence['id']] = {
                    'word_count': word_count,
                    'char_count': len(content),
                    'paragraph_count': len(content.split('\n\n')),
                    'has_structured_content': bool(re.search(r'(WHEREAS|THEREFORE|Section \d+)', content))
                }
                
                # Count policy terms
                content_lower = content.lower()
                for term in policy_terms:
                    if term in content_lower:
                        patterns['policy_terms'][term] += 1
            
            # Track department mentions
            departments = evidence.get('linked_departments', [])
            if departments:  # Check if departments is not None and not empty
                for dept in departments:
                    patterns['department_mentions'][dept] += 1
        
        # Calculate averages
        if patterns['title_patterns']:
            avg_title_length = sum(p['length'] for p in patterns['title_patterns']) / len(patterns['title_patterns'])
            avg_title_words = sum(p['word_count'] for p in patterns['title_patterns']) / len(patterns['title_patterns'])
            patterns['title_averages'] = {
                'avg_length': avg_title_length,
                'avg_word_count': avg_title_words,
                'pct_with_dates': sum(1 for p in patterns['title_patterns'] if p['has_date']) / len(patterns['title_patterns']) * 100,
                'pct_with_departments': sum(1 for p in patterns['title_patterns'] if p['has_department']) / len(patterns['title_patterns']) * 100
            }
        
        if patterns['content_characteristics']:
            word_counts = [c['word_count'] for c in patterns['content_characteristics'].values()]
            patterns['content_averages'] = {
                'avg_word_count': sum(word_counts) / len(word_counts),
                'min_word_count': min(word_counts),
                'max_word_count': max(word_counts),
                'pct_structured': sum(1 for c in patterns['content_characteristics'].values() if c['has_structured_content']) / len(patterns['content_characteristics']) * 100
            }
        
        return patterns
    
    def _analyze_linkability_factors(self, backup_sample: List[Dict[str, Any]], 
                                   current_sample: List[Dict[str, Any]]) -> Dict:
        """Analyze factors that affect evidence linkability to promises."""
        factors = {
            'keyword_extractability': {},
            'department_alignment': {},
            'temporal_alignment': {},
            'content_specificity': {},
            'linking_challenges': []
        }
        
        # Analyze keyword extractability
        backup_keywords = []
        current_keywords = []
        
        for evidence in backup_sample:
            keywords = evidence.get('key_concepts', []) or evidence.get('extracted_keywords_concepts', [])
            if keywords:
                backup_keywords.extend(keywords)
        
        for evidence in current_sample:
            keywords = evidence.get('key_concepts', []) or evidence.get('extracted_keywords_concepts', [])
            if keywords:
                current_keywords.extend(keywords)
        
        factors['keyword_extractability'] = {
            'backup_avg_keywords': len(backup_keywords) / len(backup_sample) if backup_sample else 0,
            'current_avg_keywords': len(current_keywords) / len(current_sample) if current_sample else 0,
            'backup_unique_keywords': len(set(backup_keywords)),
            'current_unique_keywords': len(set(current_keywords)),
            'keyword_overlap': len(set(backup_keywords).intersection(set(current_keywords)))
        }
        
        # Analyze department alignment potential
        backup_depts = set()
        current_depts = set()
        
        for evidence in backup_sample:
            depts = evidence.get('linked_departments', [])
            if depts:  # Check if depts is not None and not empty
                backup_depts.update(depts)
        
        for evidence in current_sample:
            depts = evidence.get('linked_departments', [])
            if depts:  # Check if depts is not None and not empty
                current_depts.update(depts)
        
        factors['department_alignment'] = {
            'backup_unique_departments': len(backup_depts),
            'current_unique_departments': len(current_depts),
            'department_overlap': len(backup_depts.intersection(current_depts)),
            'department_overlap_pct': len(backup_depts.intersection(current_depts)) / len(backup_depts.union(current_depts)) * 100 if backup_depts.union(current_depts) else 0
        }
        
        # Identify linking challenges
        challenges = []
        
        if factors['keyword_extractability']['current_avg_keywords'] < factors['keyword_extractability']['backup_avg_keywords']:
            challenges.append("Current evidence has fewer extractable keywords than backup")
        
        if factors['department_alignment']['department_overlap_pct'] < 50:
            challenges.append("Low department overlap between backup and current evidence")
        
        if len(current_sample) > 0:
            current_with_content = len([e for e in current_sample if e.get('full_text_scraped') or e.get('summary_or_snippet_raw')])
            if current_with_content / len(current_sample) < 0.8:
                challenges.append("Many current evidence items lack sufficient content for analysis")
        
        factors['linking_challenges'] = challenges
        
        return factors
    
    async def generate_linking_insights(self):
        """Generate insights for improving the linking algorithm."""
        print("  💡 Generating linking insights...")
        
        structural_comp = self.investigation_results['structural_comparison']
        content_analysis = self.investigation_results['content_analysis']
        
        insights = []
        recommendations = []
        
        # Analyze linking field availability
        if structural_comp['linking_comparison']['current_with_links'] == 0:
            insights.append("Current evidence has no promise links, indicating linking system needs activation")
            recommendations.append("Implement initial linking run with relaxed parameters to establish baseline")
        
        # Analyze content differences
        backup_patterns = content_analysis['backup_content_patterns']
        current_patterns = content_analysis['current_content_patterns']
        
        if 'title_averages' in backup_patterns and 'title_averages' in current_patterns:
            backup_title_len = backup_patterns['title_averages']['avg_length']
            current_title_len = current_patterns['title_averages']['avg_length']
            
            if abs(backup_title_len - current_title_len) > 50:
                insights.append(f"Title length difference: backup avg {backup_title_len:.0f} vs current avg {current_title_len:.0f}")
                recommendations.append("Adjust text similarity algorithms to account for title length differences")
        
        # Analyze keyword availability
        linkability = content_analysis['linkability_factors']
        if linkability['keyword_extractability']['current_avg_keywords'] < 2:
            insights.append("Current evidence has low keyword density, may need enhanced extraction")
            recommendations.append("Implement advanced keyword extraction using NLP techniques")
        
        # Analyze department alignment
        if linkability['department_alignment']['department_overlap_pct'] < 70:
            insights.append(f"Department overlap only {linkability['department_alignment']['department_overlap_pct']:.1f}%")
            recommendations.append("Review department name standardization and mapping")
        
        # Evidence type analysis
        backup_types = self.investigation_results['backup_evidence_analysis']['evidence_types']
        current_types = self.investigation_results['current_evidence_analysis']['evidence_types']
        
        if 'Bill Event' in backup_types and 'Bill Event' not in current_types:
            insights.append("Current evidence lacks 'Bill Event' type that was prominent in backup")
            recommendations.append("Verify bill processing pipeline is creating evidence items correctly")
        
        # Content quality analysis
        challenges = linkability.get('linking_challenges', [])
        for challenge in challenges:
            insights.append(challenge)
            
            if "fewer extractable keywords" in challenge:
                recommendations.append("Implement content enrichment pipeline to extract more keywords")
            elif "lack sufficient content" in challenge:
                recommendations.append("Improve content scraping and processing for evidence items")
            elif "Low department overlap" in challenge:
                recommendations.append("Create department mapping and standardization system")
        
        self.investigation_results['linking_insights'] = insights
        self.investigation_results['algorithm_recommendations'] = recommendations
        
        print(f"  💡 Generated {len(insights)} insights and {len(recommendations)} recommendations")
    
    async def export_results(self):
        """Export investigation results."""
        print("  💾 Exporting investigation results...")
        
        # Create output directory
        os.makedirs('evidence_structure_results', exist_ok=True)
        
        # 1. JSON export
        with open('evidence_structure_results/evidence_structure_investigation.json', 'w') as f:
            json.dump(self.investigation_results, f, indent=2, default=str)
        
        # 2. Generate comprehensive report
        await self.generate_investigation_report()
        
        print("    ✅ Results exported to evidence_structure_results/")
    
    async def generate_investigation_report(self):
        """Generate comprehensive investigation report."""
        backup_analysis = self.investigation_results['backup_evidence_analysis']
        current_analysis = self.investigation_results['current_evidence_analysis']
        structural_comp = self.investigation_results['structural_comparison']
        content_analysis = self.investigation_results['content_analysis']
        insights = self.investigation_results['linking_insights']
        recommendations = self.investigation_results['algorithm_recommendations']
        
        report = f"""
# Evidence Structure Investigation Report
Generated: {self.investigation_results['timestamp']}

## Executive Summary

This investigation analyzes the fundamental differences between LLM-generated evidence (backup data) and real government evidence (current data) to understand why the linking algorithms aren't working effectively.

### Key Findings

**Data Volume**:
- **Backup Evidence**: {backup_analysis['total_documents']:,} items (LLM-generated)
- **Current Evidence**: {current_analysis['total_documents']:,} items (real government data)

**Linking Status**:
- **Backup Links**: {backup_analysis['with_promise_links']:,} items with promise links ({backup_analysis['avg_promise_links']:.2f} avg links per item)
- **Current Links**: {current_analysis['with_promise_links']:,} items with promise links ({current_analysis['avg_promise_links']:.2f} avg links per item)

**Critical Issue**: Current evidence has {current_analysis['with_promise_links']} links vs. backup's {backup_analysis['with_promise_links']} links, indicating the linking system needs fundamental redesign for real evidence.

## Structural Analysis

### Field Usage Comparison

**Fields Only in Backup**:
"""
        
        backup_only_fields = structural_comp['field_differences']['backup_only_fields']
        for field in backup_only_fields[:10]:  # Top 10
            backup_usage = backup_analysis['field_usage_percentages'].get(field, 0)
            report += f"- `{field}`: {backup_usage:.1f}% usage in backup\n"
        
        report += f"""

**Fields Only in Current**:
"""
        
        current_only_fields = structural_comp['field_differences']['current_only_fields']
        for field in current_only_fields[:10]:  # Top 10
            current_usage = current_analysis['field_usage_percentages'].get(field, 0)
            report += f"- `{field}`: {current_usage:.1f}% usage in current\n"
        
        report += f"""

### Evidence Type Distribution

**Backup Evidence Types**:
"""
        
        for etype, count in backup_analysis['evidence_types'].items():
            pct = (count / backup_analysis['total_documents']) * 100
            report += f"- **{etype}**: {count:,} ({pct:.1f}%)\n"
        
        report += f"""

**Current Evidence Types**:
"""
        
        for etype, count in current_analysis['evidence_types'].items():
            pct = (count / current_analysis['total_documents']) * 100
            report += f"- **{etype}**: {count:,} ({pct:.1f}%)\n"
        
        report += f"""

### Data Sources

**Current Evidence Sources**:
"""
        
        for source, count in current_analysis.get('data_sources', {}).items():
            pct = (count / current_analysis['total_documents']) * 100
            report += f"- **{source}**: {count:,} ({pct:.1f}%)\n"
        
        report += f"""

## Content Pattern Analysis

### Title Characteristics

**Backup Evidence Titles**:
"""
        
        backup_patterns = content_analysis['backup_content_patterns']
        if 'title_averages' in backup_patterns:
            ta = backup_patterns['title_averages']
            report += f"""- Average length: {ta['avg_length']:.0f} characters
- Average words: {ta['avg_word_count']:.1f} words
- With dates: {ta['pct_with_dates']:.1f}%
- With departments: {ta['pct_with_departments']:.1f}%
"""
        
        report += f"""

**Current Evidence Titles**:
"""
        
        current_patterns = content_analysis['current_content_patterns']
        if 'title_averages' in current_patterns:
            ta = current_patterns['title_averages']
            report += f"""- Average length: {ta['avg_length']:.0f} characters
- Average words: {ta['avg_word_count']:.1f} words
- With dates: {ta['pct_with_dates']:.1f}%
- With departments: {ta['pct_with_departments']:.1f}%
"""
        
        report += f"""

### Content Quality

**Backup Content**:
"""
        
        if 'content_averages' in backup_patterns:
            ca = backup_patterns['content_averages']
            report += f"""- Average word count: {ca['avg_word_count']:.0f} words
- Word count range: {ca['min_word_count']:,} - {ca['max_word_count']:,}
- Structured content: {ca['pct_structured']:.1f}%
"""
        
        report += f"""

**Current Content**:
"""
        
        if 'content_averages' in current_patterns:
            ca = current_patterns['content_averages']
            report += f"""- Average word count: {ca['avg_word_count']:.0f} words
- Word count range: {ca['min_word_count']:,} - {ca['max_word_count']:,}
- Structured content: {ca['pct_structured']:.1f}%
"""
        
        report += f"""

## Linkability Analysis

### Keyword Extraction Potential
"""
        
        linkability = content_analysis['linkability_factors']
        ke = linkability['keyword_extractability']
        report += f"""
- **Backup**: {ke['backup_avg_keywords']:.1f} avg keywords per item, {ke['backup_unique_keywords']:,} unique keywords
- **Current**: {ke['current_avg_keywords']:.1f} avg keywords per item, {ke['current_unique_keywords']:,} unique keywords
- **Keyword Overlap**: {ke['keyword_overlap']:,} keywords in common
"""
        
        report += f"""

### Department Alignment
"""
        
        da = linkability['department_alignment']
        report += f"""
- **Backup Departments**: {da['backup_unique_departments']} unique departments
- **Current Departments**: {da['current_unique_departments']} unique departments
- **Department Overlap**: {da['department_overlap']} departments ({da['department_overlap_pct']:.1f}%)
"""
        
        report += f"""

## Key Insights

"""
        
        for i, insight in enumerate(insights, 1):
            report += f"{i}. {insight}\n"
        
        report += f"""

## Algorithm Recommendations

"""
        
        for i, rec in enumerate(recommendations, 1):
            report += f"{i}. {rec}\n"
        
        report += f"""

## Critical Differences: LLM vs. Real Evidence

### LLM-Generated Evidence (Backup)
- **Purpose-built**: Created specifically to match existing promises
- **Consistent structure**: Uniform field usage and content patterns
- **High linkability**: Designed with promise alignment in mind
- **Artificial keywords**: Keywords extracted or generated to match promise concepts

### Real Government Evidence (Current)
- **Authentic documents**: Actual government announcements, bills, regulations
- **Variable structure**: Different formats based on source (news, bills, OICs)
- **Natural language**: Real-world government communication patterns
- **Organic content**: Keywords and concepts emerge naturally from content

### Implications for Linking Algorithms

1. **Lower Match Rates Expected**: Real evidence won't have the artificial alignment of LLM-generated content
2. **Enhanced Preprocessing Needed**: Real evidence requires more sophisticated content extraction and normalization
3. **Semantic Understanding Required**: Simple keyword matching insufficient for real government language
4. **Temporal Considerations**: Real evidence may precede or follow promises by significant time periods
5. **Domain Expertise**: Understanding government processes and terminology becomes critical

## Next Steps

### Immediate Actions
1. **Manual Link Testing**: Create 5-10 manual links to verify system functionality
2. **Algorithm Parameter Adjustment**: Lower similarity thresholds for real evidence
3. **Content Enhancement**: Improve keyword extraction for government documents

### Medium-term Improvements
1. **Semantic Similarity**: Implement embedding-based matching
2. **Domain-specific Processing**: Government document type-specific algorithms
3. **Temporal Correlation**: Time-based relevance scoring

### Long-term Strategy
1. **Hybrid Approach**: Combine automated suggestions with human review
2. **Continuous Learning**: Algorithm improvement based on validated links
3. **Quality over Quantity**: Focus on high-confidence, high-value links

## Files Generated
- `evidence_structure_investigation.json`: Complete analysis data
- `evidence_structure_report.md`: This comprehensive report
"""
        
        with open('evidence_structure_results/evidence_structure_report.md', 'w') as f:
            f.write(report)
        
        print("    📄 Investigation report saved to evidence_structure_results/evidence_structure_report.md")

async def main():
    """Main execution function."""
    investigator = EvidenceStructureInvestigator()
    results = await investigator.run_investigation()
    
    print("\n" + "=" * 60)
    print("🎉 EVIDENCE STRUCTURE INVESTIGATION COMPLETE!")
    print("=" * 60)
    
    backup_analysis = results['backup_evidence_analysis']
    current_analysis = results['current_evidence_analysis']
    insights = results['linking_insights']
    recommendations = results['algorithm_recommendations']
    
    print(f"📊 Backup evidence analyzed: {backup_analysis['total_documents']:,} items")
    print(f"📊 Current evidence analyzed: {current_analysis['total_documents']:,} items")
    print(f"💡 Insights generated: {len(insights)}")
    print(f"🔧 Recommendations: {len(recommendations)}")
    print("\n📁 Results saved to: evidence_structure_results/")
    print("📄 Full report: evidence_structure_results/evidence_structure_report.md")

if __name__ == "__main__":
    asyncio.run(main()) 