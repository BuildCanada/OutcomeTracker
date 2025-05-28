#!/usr/bin/env python3
"""
Algorithm Parameter Analysis for Promise-Evidence Linking

This script analyzes the current linking algorithm's performance with different parameters
to understand why it's not working effectively with real evidence data.

Key Analysis Areas:
1. Keyword extraction effectiveness
2. Similarity threshold impact
3. LLM evaluation patterns
4. Parameter optimization opportunities
"""

import asyncio
import json
import os
import sys
import time
from datetime import datetime
from typing import Dict, List, Any, Set, Tuple
import re
from collections import defaultdict, Counter
from pathlib import Path

# Firebase imports
import firebase_admin
from firebase_admin import credentials, firestore

# Initialize Firebase
def initialize_firebase():
    """Initialize Firebase Admin SDK."""
    try:
        if not firebase_admin._apps:
            current_dir = Path(__file__).parent
            service_account_path = current_dir.parent.parent / 'service-account-key.json'
            
            if service_account_path.exists():
                cred = credentials.Certificate(str(service_account_path))
                firebase_admin.initialize_app(cred)
            else:
                # Try to use environment variable
                cred = credentials.ApplicationDefault()
                firebase_admin.initialize_app(cred)
                
        return firestore.client()
    except Exception as e:
        print(f"Failed to initialize Firebase: {e}")
        return None

# Initialize Firebase
db = initialize_firebase()

PROMISES_COLLECTION_ROOT = "promises"
EVIDENCE_COLLECTION_ROOT = "evidence_items"

class AlgorithmParameterAnalyzer:
    """Analyzes current linking algorithm parameters and performance."""
    
    def __init__(self):
        self.analysis_results = {}
        self.test_data = {}
        self.parameter_tests = {}
        
    def _extract_keywords_from_text(self, text: str) -> Set[str]:
        """Extract keywords from text (same as current algorithm)."""
        if not text:
            return set()
        
        # Convert to lowercase and split into words
        words = re.findall(r'\b[a-zA-Z]{3,}\b', text.lower())
        
        # Filter out common stop words
        stop_words = {
            'the', 'and', 'for', 'are', 'but', 'not', 'you', 'all', 'can', 'had', 'has', 'have',
            'her', 'was', 'one', 'our', 'out', 'day', 'get', 'use', 'man', 'new', 'now', 'old',
            'see', 'him', 'two', 'way', 'who', 'boy', 'did', 'its', 'let', 'put', 'say', 'she',
            'too', 'use', 'will', 'with', 'that', 'this', 'they', 'them', 'there', 'their',
            'would', 'could', 'should', 'government', 'canada', 'canadian', 'federal'
        }
        
        keywords = {word for word in words if word not in stop_words and len(word) > 2}
        return keywords
    
    def _calculate_jaccard_similarity(self, set1: Set[str], set2: Set[str]) -> float:
        """Calculate Jaccard similarity between two sets."""
        if not set1 and not set2:
            return 0.0
        if not set1 or not set2:
            return 0.0
        
        intersection = len(set1.intersection(set2))
        union = len(set1.union(set2))
        
        return intersection / union if union > 0 else 0.0
    
    def _get_evidence_keywords(self, evidence_data: Dict[str, Any]) -> Set[str]:
        """Extract keywords from evidence item (same as current algorithm)."""
        keywords = set()
        
        # Extract from title
        title = evidence_data.get('title_or_summary', '')
        keywords.update(self._extract_keywords_from_text(title))
        
        # Extract from content (first 500 chars to avoid noise)
        content = evidence_data.get('description_or_details', '')[:500]
        keywords.update(self._extract_keywords_from_text(content))
        
        return keywords
    
    def _get_promise_keywords(self, promise_data: Dict[str, Any]) -> Set[str]:
        """Extract keywords from promise item (same as current algorithm)."""
        keywords = set()
        
        # Use existing extracted keywords if available
        extracted_keywords = promise_data.get('extracted_keywords_concepts', [])
        if extracted_keywords:
            # Handle both list and dict formats
            if isinstance(extracted_keywords, list):
                for item in extracted_keywords:
                    if isinstance(item, str):
                        keywords.update(self._extract_keywords_from_text(item))
                    elif isinstance(item, dict) and 'keyword' in item:
                        keywords.update(self._extract_keywords_from_text(item['keyword']))
            elif isinstance(extracted_keywords, dict):
                for key, value in extracted_keywords.items():
                    keywords.update(self._extract_keywords_from_text(str(value)))
        
        # Also extract from promise text
        promise_text = promise_data.get('text', '')
        keywords.update(self._extract_keywords_from_text(promise_text))
        
        # Add department keywords
        department = promise_data.get('responsible_department_lead', '')
        keywords.update(self._extract_keywords_from_text(department))
        
        return keywords
    
    async def load_sample_data(self, limit: int = 100):
        """Load sample promises and evidence for analysis."""
        print("📊 Loading sample data for analysis...")
        
        # Load promises
        print("  Loading promises...")
        promises_query = db.collection(PROMISES_COLLECTION_ROOT).where(
            filter=firestore.FieldFilter("parliament_session_id", "==", "45")
        ).limit(limit)
        
        promise_docs = list(await asyncio.to_thread(promises_query.stream))
        promises = []
        for doc in promise_docs:
            data = doc.to_dict()
            if data and data.get("text"):
                promises.append({
                    "id": doc.id,
                    "data": data
                })
        
        # Load evidence
        print("  Loading evidence...")
        evidence_query = db.collection(EVIDENCE_COLLECTION_ROOT).where(
            filter=firestore.FieldFilter("parliament_session_id", "==", "45")
        ).limit(limit)
        
        evidence_docs = list(await asyncio.to_thread(evidence_query.stream))
        evidence_items = []
        for doc in evidence_docs:
            data = doc.to_dict()
            if data:
                evidence_items.append({
                    "id": doc.id,
                    "data": data
                })
        
        self.test_data = {
            'promises': promises,
            'evidence': evidence_items
        }
        
        print(f"  ✅ Loaded {len(promises)} promises and {len(evidence_items)} evidence items")
        return len(promises), len(evidence_items)
    
    async def analyze_keyword_extraction_quality(self):
        """Analyze the quality of keyword extraction from real data."""
        print("🔍 Analyzing keyword extraction quality...")
        
        promise_keyword_stats = {
            'total_promises': 0,
            'promises_with_keywords': 0,
            'avg_keywords_per_promise': 0,
            'keyword_length_distribution': defaultdict(int),
            'most_common_keywords': Counter(),
            'empty_keyword_promises': []
        }
        
        evidence_keyword_stats = {
            'total_evidence': 0,
            'evidence_with_keywords': 0,
            'avg_keywords_per_evidence': 0,
            'keyword_length_distribution': defaultdict(int),
            'most_common_keywords': Counter(),
            'empty_keyword_evidence': []
        }
        
        # Analyze promise keywords
        total_promise_keywords = 0
        for promise in self.test_data['promises']:
            promise_keyword_stats['total_promises'] += 1
            keywords = self._get_promise_keywords(promise['data'])
            
            if keywords:
                promise_keyword_stats['promises_with_keywords'] += 1
                total_promise_keywords += len(keywords)
                
                # Track keyword lengths
                for keyword in keywords:
                    promise_keyword_stats['keyword_length_distribution'][len(keyword)] += 1
                    promise_keyword_stats['most_common_keywords'][keyword] += 1
            else:
                promise_keyword_stats['empty_keyword_promises'].append({
                    'id': promise['id'],
                    'text': promise['data'].get('text', '')[:100] + '...'
                })
        
        if promise_keyword_stats['promises_with_keywords'] > 0:
            promise_keyword_stats['avg_keywords_per_promise'] = total_promise_keywords / promise_keyword_stats['promises_with_keywords']
        
        # Analyze evidence keywords
        total_evidence_keywords = 0
        for evidence in self.test_data['evidence']:
            evidence_keyword_stats['total_evidence'] += 1
            keywords = self._get_evidence_keywords(evidence['data'])
            
            if keywords:
                evidence_keyword_stats['evidence_with_keywords'] += 1
                total_evidence_keywords += len(keywords)
                
                # Track keyword lengths
                for keyword in keywords:
                    evidence_keyword_stats['keyword_length_distribution'][len(keyword)] += 1
                    evidence_keyword_stats['most_common_keywords'][keyword] += 1
            else:
                evidence_keyword_stats['empty_keyword_evidence'].append({
                    'id': evidence['id'],
                    'title': evidence['data'].get('title_or_summary', '')[:100] + '...',
                    'content': evidence['data'].get('description_or_details', '')[:100] + '...'
                })
        
        if evidence_keyword_stats['evidence_with_keywords'] > 0:
            evidence_keyword_stats['avg_keywords_per_evidence'] = total_evidence_keywords / evidence_keyword_stats['evidence_with_keywords']
        
        self.analysis_results['keyword_extraction'] = {
            'promises': promise_keyword_stats,
            'evidence': evidence_keyword_stats
        }
        
        # Print summary
        print(f"  📊 Promise Keywords:")
        print(f"    - {promise_keyword_stats['promises_with_keywords']}/{promise_keyword_stats['total_promises']} promises have keywords ({promise_keyword_stats['promises_with_keywords']/promise_keyword_stats['total_promises']*100:.1f}%)")
        print(f"    - Average keywords per promise: {promise_keyword_stats['avg_keywords_per_promise']:.1f}")
        print(f"    - Most common: {dict(promise_keyword_stats['most_common_keywords'].most_common(5))}")
        
        print(f"  📊 Evidence Keywords:")
        print(f"    - {evidence_keyword_stats['evidence_with_keywords']}/{evidence_keyword_stats['total_evidence']} evidence items have keywords ({evidence_keyword_stats['evidence_with_keywords']/evidence_keyword_stats['total_evidence']*100:.1f}%)")
        print(f"    - Average keywords per evidence: {evidence_keyword_stats['avg_keywords_per_evidence']:.1f}")
        print(f"    - Most common: {dict(evidence_keyword_stats['most_common_keywords'].most_common(5))}")
    
    async def test_similarity_thresholds(self):
        """Test different similarity thresholds to understand their impact."""
        print("🎯 Testing similarity thresholds...")
        
        thresholds = [0.0, 0.05, 0.1, 0.15, 0.2, 0.25, 0.3, 0.4, 0.5]
        threshold_results = {}
        
        # Test with first 20 evidence items against all promises
        test_evidence = self.test_data['evidence'][:20]
        all_promises = self.test_data['promises']
        
        for threshold in thresholds:
            print(f"  Testing threshold {threshold}...")
            
            total_candidates = 0
            similarity_scores = []
            
            for evidence in test_evidence:
                evidence_keywords = self._get_evidence_keywords(evidence['data'])
                
                candidates_for_this_evidence = 0
                for promise in all_promises:
                    promise_keywords = self._get_promise_keywords(promise['data'])
                    similarity = self._calculate_jaccard_similarity(evidence_keywords, promise_keywords)
                    
                    similarity_scores.append(similarity)
                    
                    if similarity >= threshold:
                        candidates_for_this_evidence += 1
                
                total_candidates += candidates_for_this_evidence
            
            avg_candidates_per_evidence = total_candidates / len(test_evidence)
            avg_similarity = sum(similarity_scores) / len(similarity_scores) if similarity_scores else 0
            max_similarity = max(similarity_scores) if similarity_scores else 0
            
            threshold_results[threshold] = {
                'avg_candidates_per_evidence': avg_candidates_per_evidence,
                'total_candidates': total_candidates,
                'avg_similarity_score': avg_similarity,
                'max_similarity_score': max_similarity,
                'percentage_above_threshold': len([s for s in similarity_scores if s >= threshold]) / len(similarity_scores) * 100
            }
            
            print(f"    - Avg candidates per evidence: {avg_candidates_per_evidence:.1f}")
            print(f"    - {threshold_results[threshold]['percentage_above_threshold']:.1f}% of pairs above threshold")
        
        self.analysis_results['similarity_thresholds'] = threshold_results
    
    async def analyze_department_alignment(self):
        """Analyze how well departments align between promises and evidence."""
        print("🏛️ Analyzing department alignment...")
        
        # Extract departments from promises
        promise_departments = defaultdict(int)
        for promise in self.test_data['promises']:
            dept = promise['data'].get('responsible_department_lead', '').strip()
            if dept:
                promise_departments[dept] += 1
        
        # Extract departments from evidence (if available)
        evidence_departments = defaultdict(int)
        for evidence in self.test_data['evidence']:
            # Evidence might have department info in different fields
            dept_fields = ['department', 'responsible_department', 'source_department']
            for field in dept_fields:
                dept = evidence['data'].get(field, '').strip()
                if dept:
                    evidence_departments[dept] += 1
                    break
        
        # Find overlapping departments
        promise_dept_set = set(promise_departments.keys())
        evidence_dept_set = set(evidence_departments.keys())
        overlapping_depts = promise_dept_set.intersection(evidence_dept_set)
        
        department_analysis = {
            'promise_departments': dict(promise_departments),
            'evidence_departments': dict(evidence_departments),
            'overlapping_departments': list(overlapping_depts),
            'promise_dept_count': len(promise_dept_set),
            'evidence_dept_count': len(evidence_dept_set),
            'overlap_count': len(overlapping_depts),
            'overlap_percentage': len(overlapping_depts) / max(len(promise_dept_set), 1) * 100
        }
        
        self.analysis_results['department_alignment'] = department_analysis
        
        print(f"  📊 Department Analysis:")
        print(f"    - Promise departments: {len(promise_dept_set)}")
        print(f"    - Evidence departments: {len(evidence_dept_set)}")
        print(f"    - Overlapping departments: {len(overlapping_depts)} ({department_analysis['overlap_percentage']:.1f}%)")
        print(f"    - Top promise departments: {dict(Counter(promise_departments).most_common(5))}")
        print(f"    - Top evidence departments: {dict(Counter(evidence_departments).most_common(5))}")
    
    async def test_content_field_combinations(self):
        """Test different combinations of content fields for keyword extraction."""
        print("📝 Testing content field combinations...")
        
        # Define different extraction strategies
        strategies = {
            'current_algorithm': {
                'promise_fields': ['text', 'extracted_keywords_concepts', 'responsible_department_lead'],
                'evidence_fields': ['title_or_summary', 'description_or_details']
            },
            'promise_all_content': {
                'promise_fields': ['text', 'description', 'background_and_context', 'concise_title', 'responsible_department_lead'],
                'evidence_fields': ['title_or_summary', 'description_or_details']
            },
            'evidence_extended': {
                'promise_fields': ['text', 'extracted_keywords_concepts', 'responsible_department_lead'],
                'evidence_fields': ['title_or_summary', 'description_or_details', 'source_url']
            },
            'minimal_content': {
                'promise_fields': ['text'],
                'evidence_fields': ['title_or_summary']
            }
        }
        
        strategy_results = {}
        
        # Test with first 10 evidence items against first 50 promises
        test_evidence = self.test_data['evidence'][:10]
        test_promises = self.test_data['promises'][:50]
        
        for strategy_name, strategy in strategies.items():
            print(f"  Testing strategy: {strategy_name}")
            
            total_similarities = []
            candidates_above_01 = 0
            candidates_above_02 = 0
            
            for evidence in test_evidence:
                evidence_keywords = self._extract_keywords_for_strategy(evidence['data'], strategy['evidence_fields'])
                
                for promise in test_promises:
                    promise_keywords = self._extract_keywords_for_strategy(promise['data'], strategy['promise_fields'])
                    similarity = self._calculate_jaccard_similarity(evidence_keywords, promise_keywords)
                    
                    total_similarities.append(similarity)
                    if similarity >= 0.1:
                        candidates_above_01 += 1
                    if similarity >= 0.2:
                        candidates_above_02 += 1
            
            avg_similarity = sum(total_similarities) / len(total_similarities) if total_similarities else 0
            max_similarity = max(total_similarities) if total_similarities else 0
            
            strategy_results[strategy_name] = {
                'avg_similarity': avg_similarity,
                'max_similarity': max_similarity,
                'candidates_above_01': candidates_above_01,
                'candidates_above_02': candidates_above_02,
                'total_comparisons': len(total_similarities)
            }
            
            print(f"    - Avg similarity: {avg_similarity:.4f}")
            print(f"    - Max similarity: {max_similarity:.4f}")
            print(f"    - Candidates ≥0.1: {candidates_above_01}")
            print(f"    - Candidates ≥0.2: {candidates_above_02}")
        
        self.analysis_results['content_field_strategies'] = strategy_results
    
    def _extract_keywords_for_strategy(self, data: Dict[str, Any], fields: List[str]) -> Set[str]:
        """Extract keywords using specific field strategy."""
        keywords = set()
        
        for field in fields:
            if field == 'extracted_keywords_concepts':
                # Special handling for extracted keywords
                extracted_keywords = data.get(field, [])
                if extracted_keywords:
                    if isinstance(extracted_keywords, list):
                        for item in extracted_keywords:
                            if isinstance(item, str):
                                keywords.update(self._extract_keywords_from_text(item))
                            elif isinstance(item, dict) and 'keyword' in item:
                                keywords.update(self._extract_keywords_from_text(item['keyword']))
                    elif isinstance(extracted_keywords, dict):
                        for key, value in extracted_keywords.items():
                            keywords.update(self._extract_keywords_from_text(str(value)))
            else:
                # Regular text field
                text = data.get(field, '')
                if text:
                    if field == 'description_or_details':
                        # Limit content to first 500 chars like current algorithm
                        text = text[:500]
                    keywords.update(self._extract_keywords_from_text(text))
        
        return keywords
    
    async def identify_high_potential_pairs(self):
        """Identify promise-evidence pairs with highest linking potential."""
        print("🎯 Identifying high-potential linking pairs...")
        
        high_potential_pairs = []
        
        # Test all evidence against all promises (limited sample)
        test_evidence = self.test_data['evidence'][:20]
        test_promises = self.test_data['promises'][:100]
        
        for evidence in test_evidence:
            evidence_keywords = self._get_evidence_keywords(evidence['data'])
            
            for promise in test_promises:
                promise_keywords = self._get_promise_keywords(promise['data'])
                similarity = self._calculate_jaccard_similarity(evidence_keywords, promise_keywords)
                
                if similarity >= 0.15:  # Higher threshold for high potential
                    # Calculate additional metrics
                    common_keywords = evidence_keywords.intersection(promise_keywords)
                    
                    # Check department alignment
                    evidence_dept = evidence['data'].get('department', '')
                    promise_dept = promise['data'].get('responsible_department_lead', '')
                    dept_match = evidence_dept.lower() == promise_dept.lower() if evidence_dept and promise_dept else False
                    
                    high_potential_pairs.append({
                        'evidence_id': evidence['id'],
                        'promise_id': promise['id'],
                        'similarity_score': similarity,
                        'common_keywords': list(common_keywords),
                        'common_keyword_count': len(common_keywords),
                        'department_match': dept_match,
                        'evidence_title': evidence['data'].get('title_or_summary', '')[:100],
                        'promise_text': promise['data'].get('text', '')[:100],
                        'evidence_type': evidence['data'].get('evidence_source_type', ''),
                        'promise_party': promise['data'].get('party_code', '')
                    })
        
        # Sort by similarity score
        high_potential_pairs.sort(key=lambda x: x['similarity_score'], reverse=True)
        
        self.analysis_results['high_potential_pairs'] = high_potential_pairs[:20]  # Top 20
        
        print(f"  🎯 Found {len(high_potential_pairs)} pairs with similarity ≥0.15")
        print(f"  📊 Top 5 pairs:")
        for i, pair in enumerate(high_potential_pairs[:5]):
            print(f"    {i+1}. Similarity: {pair['similarity_score']:.3f}, Keywords: {pair['common_keyword_count']}")
            print(f"       Evidence: {pair['evidence_title']}")
            print(f"       Promise: {pair['promise_text']}")
    
    async def generate_algorithm_recommendations(self):
        """Generate recommendations for algorithm improvements."""
        print("💡 Generating algorithm recommendations...")
        
        recommendations = []
        
        # Analyze keyword extraction results
        keyword_stats = self.analysis_results.get('keyword_extraction', {})
        if keyword_stats:
            promise_stats = keyword_stats.get('promises', {})
            evidence_stats = keyword_stats.get('evidence', {})
            
            if promise_stats.get('avg_keywords_per_promise', 0) < 5:
                recommendations.append({
                    'category': 'Keyword Extraction',
                    'issue': 'Low average keywords per promise',
                    'recommendation': 'Expand promise keyword extraction to include description, background_and_context fields',
                    'priority': 'High'
                })
            
            if evidence_stats.get('avg_keywords_per_evidence', 0) < 3:
                recommendations.append({
                    'category': 'Keyword Extraction',
                    'issue': 'Low average keywords per evidence',
                    'recommendation': 'Improve evidence content processing and keyword extraction',
                    'priority': 'High'
                })
        
        # Analyze similarity thresholds
        threshold_stats = self.analysis_results.get('similarity_thresholds', {})
        if threshold_stats:
            # Find optimal threshold
            best_threshold = None
            best_balance = 0
            
            for threshold, stats in threshold_stats.items():
                # Balance between having candidates and not too many
                candidates = stats['avg_candidates_per_evidence']
                if 5 <= candidates <= 20:  # Sweet spot
                    balance_score = 20 - abs(candidates - 10)  # Prefer around 10 candidates
                    if balance_score > best_balance:
                        best_balance = balance_score
                        best_threshold = threshold
            
            if best_threshold:
                recommendations.append({
                    'category': 'Similarity Threshold',
                    'issue': 'Current threshold may not be optimal',
                    'recommendation': f'Consider using similarity threshold of {best_threshold} for better candidate selection',
                    'priority': 'Medium'
                })
        
        # Analyze department alignment
        dept_stats = self.analysis_results.get('department_alignment', {})
        if dept_stats and dept_stats.get('overlap_percentage', 0) < 50:
            recommendations.append({
                'category': 'Department Alignment',
                'issue': 'Low department overlap between promises and evidence',
                'recommendation': 'Implement department name standardization and mapping system',
                'priority': 'High'
            })
        
        # Analyze content strategies
        strategy_stats = self.analysis_results.get('content_field_strategies', {})
        if strategy_stats:
            current_avg = strategy_stats.get('current_algorithm', {}).get('avg_similarity', 0)
            best_strategy = None
            best_avg = current_avg
            
            for strategy_name, stats in strategy_stats.items():
                if stats.get('avg_similarity', 0) > best_avg:
                    best_avg = stats['avg_similarity']
                    best_strategy = strategy_name
            
            if best_strategy and best_strategy != 'current_algorithm':
                recommendations.append({
                    'category': 'Content Strategy',
                    'issue': 'Current content field selection may not be optimal',
                    'recommendation': f'Consider using {best_strategy} strategy for better similarity scores',
                    'priority': 'Medium'
                })
        
        # Analyze high potential pairs
        potential_pairs = self.analysis_results.get('high_potential_pairs', [])
        if len(potential_pairs) < 5:
            recommendations.append({
                'category': 'Overall Performance',
                'issue': 'Very few high-potential linking pairs found',
                'recommendation': 'Consider implementing semantic similarity (embeddings) instead of keyword-based similarity',
                'priority': 'High'
            })
        
        self.analysis_results['recommendations'] = recommendations
        
        print(f"  💡 Generated {len(recommendations)} recommendations:")
        for i, rec in enumerate(recommendations, 1):
            print(f"    {i}. [{rec['priority']}] {rec['category']}: {rec['recommendation']}")
    
    async def save_analysis_results(self):
        """Save analysis results to files."""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        
        # Create results directory
        results_dir = "algorithm_analysis_results"
        os.makedirs(results_dir, exist_ok=True)
        
        # Save detailed results
        results_file = f"{results_dir}/algorithm_analysis_{timestamp}.json"
        with open(results_file, 'w') as f:
            json.dump(self.analysis_results, f, indent=2, default=str)
        
        # Generate summary report
        report_file = f"{results_dir}/algorithm_analysis_report_{timestamp}.md"
        await self._generate_summary_report(report_file)
        
        print(f"  💾 Results saved:")
        print(f"    - Detailed data: {results_file}")
        print(f"    - Summary report: {report_file}")
    
    async def _generate_summary_report(self, report_file: str):
        """Generate a summary report in markdown format."""
        with open(report_file, 'w') as f:
            f.write("# Algorithm Parameter Analysis Report\n\n")
            f.write(f"**Generated:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")
            
            # Executive Summary
            f.write("## Executive Summary\n\n")
            recommendations = self.analysis_results.get('recommendations', [])
            high_priority = [r for r in recommendations if r['priority'] == 'High']
            f.write(f"- **High Priority Issues:** {len(high_priority)}\n")
            f.write(f"- **Total Recommendations:** {len(recommendations)}\n")
            
            potential_pairs = self.analysis_results.get('high_potential_pairs', [])
            f.write(f"- **High-Potential Pairs Found:** {len(potential_pairs)}\n\n")
            
            # Keyword Extraction Analysis
            keyword_stats = self.analysis_results.get('keyword_extraction', {})
            if keyword_stats:
                f.write("## Keyword Extraction Analysis\n\n")
                
                promise_stats = keyword_stats.get('promises', {})
                f.write("### Promise Keywords\n")
                f.write(f"- **Coverage:** {promise_stats.get('promises_with_keywords', 0)}/{promise_stats.get('total_promises', 0)} promises have keywords\n")
                f.write(f"- **Average Keywords:** {promise_stats.get('avg_keywords_per_promise', 0):.1f} per promise\n")
                f.write(f"- **Most Common:** {dict(Counter(promise_stats.get('most_common_keywords', {})).most_common(5))}\n\n")
                
                evidence_stats = keyword_stats.get('evidence', {})
                f.write("### Evidence Keywords\n")
                f.write(f"- **Coverage:** {evidence_stats.get('evidence_with_keywords', 0)}/{evidence_stats.get('total_evidence', 0)} evidence items have keywords\n")
                f.write(f"- **Average Keywords:** {evidence_stats.get('avg_keywords_per_evidence', 0):.1f} per evidence\n")
                f.write(f"- **Most Common:** {dict(Counter(evidence_stats.get('most_common_keywords', {})).most_common(5))}\n\n")
            
            # Similarity Threshold Analysis
            threshold_stats = self.analysis_results.get('similarity_thresholds', {})
            if threshold_stats:
                f.write("## Similarity Threshold Analysis\n\n")
                f.write("| Threshold | Avg Candidates | % Above Threshold | Max Similarity |\n")
                f.write("|-----------|----------------|-------------------|----------------|\n")
                for threshold, stats in threshold_stats.items():
                    f.write(f"| {threshold} | {stats['avg_candidates_per_evidence']:.1f} | {stats['percentage_above_threshold']:.1f}% | {stats['max_similarity_score']:.3f} |\n")
                f.write("\n")
            
            # Department Alignment
            dept_stats = self.analysis_results.get('department_alignment', {})
            if dept_stats:
                f.write("## Department Alignment Analysis\n\n")
                f.write(f"- **Promise Departments:** {dept_stats.get('promise_dept_count', 0)}\n")
                f.write(f"- **Evidence Departments:** {dept_stats.get('evidence_dept_count', 0)}\n")
                f.write(f"- **Overlap:** {dept_stats.get('overlap_count', 0)} departments ({dept_stats.get('overlap_percentage', 0):.1f}%)\n\n")
            
            # High Potential Pairs
            if potential_pairs:
                f.write("## High-Potential Linking Pairs\n\n")
                f.write("| Similarity | Common Keywords | Evidence Type | Promise Party |\n")
                f.write("|------------|-----------------|---------------|---------------|\n")
                for pair in potential_pairs[:10]:
                    f.write(f"| {pair['similarity_score']:.3f} | {pair['common_keyword_count']} | {pair['evidence_type']} | {pair['promise_party']} |\n")
                f.write("\n")
            
            # Recommendations
            if recommendations:
                f.write("## Recommendations\n\n")
                for i, rec in enumerate(recommendations, 1):
                    f.write(f"### {i}. {rec['category']} [{rec['priority']} Priority]\n")
                    f.write(f"**Issue:** {rec['issue']}\n\n")
                    f.write(f"**Recommendation:** {rec['recommendation']}\n\n")
    
    async def run_complete_analysis(self):
        """Run the complete algorithm parameter analysis."""
        print("🚀 Starting Algorithm Parameter Analysis")
        print("=" * 60)
        
        try:
            # Load data
            await self.load_sample_data(limit=100)
            
            # Run analyses
            await self.analyze_keyword_extraction_quality()
            await self.test_similarity_thresholds()
            await self.analyze_department_alignment()
            await self.test_content_field_combinations()
            await self.identify_high_potential_pairs()
            await self.generate_algorithm_recommendations()
            
            # Save results
            await self.save_analysis_results()
            
            print("\n" + "=" * 60)
            print("✅ Algorithm Parameter Analysis Complete!")
            
        except Exception as e:
            print(f"❌ Error during analysis: {e}")
            raise

async def main():
    """Main execution function."""
    analyzer = AlgorithmParameterAnalyzer()
    await analyzer.run_complete_analysis()

if __name__ == "__main__":
    asyncio.run(main()) 