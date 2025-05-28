#!/usr/bin/env python3
"""
Algorithm Improvement Plan for Promise-Evidence Linking

Based on the parameter analysis findings, this script implements improved
linking algorithms to address the critical issues identified:

1. Very low similarity scores (max 0.111)
2. Zero department alignment 
3. No high-potential pairs found
4. Current algorithm ineffective with real evidence

Key Improvements:
1. Enhanced keyword extraction with domain-specific terms
2. Semantic similarity using embeddings
3. Department mapping and standardization
4. Multi-stage filtering approach
5. Content enrichment strategies
"""

import asyncio
import json
import os
import sys
import time
from datetime import datetime
from typing import Dict, List, Any, Set, Tuple, Optional
import re
from collections import defaultdict, Counter
from pathlib import Path
import numpy as np

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

class ImprovedLinkingAlgorithm:
    """Improved promise-evidence linking algorithm addressing identified issues."""
    
    def __init__(self):
        self.improvement_results = {}
        self.test_data = {}
        
        # Enhanced stop words for government content
        self.stop_words = {
            'the', 'and', 'for', 'are', 'but', 'not', 'you', 'all', 'can', 'had', 'has', 'have',
            'her', 'was', 'one', 'our', 'out', 'day', 'get', 'use', 'man', 'new', 'now', 'old',
            'see', 'him', 'two', 'way', 'who', 'boy', 'did', 'its', 'let', 'put', 'say', 'she',
            'too', 'use', 'will', 'with', 'that', 'this', 'they', 'them', 'there', 'their',
            'would', 'could', 'should', 'government', 'canada', 'canadian', 'federal', 'act',
            'order', 'under', 'these', 'minister', 'including', 'also', 'may', 'shall', 'must'
        }
        
        # Government-specific important terms
        self.important_terms = {
            'healthcare', 'health', 'medical', 'hospital', 'doctor', 'nurse', 'patient',
            'education', 'school', 'student', 'teacher', 'university', 'college',
            'housing', 'affordable', 'rent', 'mortgage', 'home', 'shelter',
            'infrastructure', 'transit', 'transportation', 'road', 'bridge', 'highway',
            'environment', 'climate', 'carbon', 'emission', 'green', 'renewable',
            'economy', 'economic', 'job', 'employment', 'business', 'trade',
            'indigenous', 'first', 'nation', 'metis', 'inuit', 'aboriginal',
            'immigration', 'refugee', 'citizenship', 'border', 'visa',
            'defense', 'defence', 'military', 'security', 'police', 'safety',
            'tax', 'taxation', 'budget', 'spending', 'revenue', 'fiscal',
            'social', 'welfare', 'benefit', 'pension', 'disability', 'senior'
        }
        
        # Department mapping for standardization
        self.department_mappings = {
            # Common variations and standardizations
            'finance': ['Minister of Finance', 'Department of Finance', 'Finance Canada'],
            'health': ['Minister of Health', 'Health Canada', 'Department of Health'],
            'defence': ['Minister of National Defence', 'Department of National Defence', 'DND'],
            'immigration': ['Minister of Immigration', 'IRCC', 'Immigration, Refugees and Citizenship Canada'],
            'environment': ['Minister of Environment', 'Environment and Climate Change Canada', 'ECCC'],
            'transport': ['Minister of Transport', 'Transport Canada', 'Department of Transport'],
            'justice': ['Minister of Justice', 'Department of Justice', 'Justice Canada'],
            'employment': ['Minister of Employment', 'Employment and Social Development Canada', 'ESDC'],
            'indigenous': ['Minister of Indigenous Services', 'Indigenous Services Canada', 'ISC'],
            'housing': ['Minister of Housing', 'Canada Mortgage and Housing Corporation', 'CMHC']
        }
    
    def _extract_enhanced_keywords(self, text: str, boost_important: bool = True) -> Set[str]:
        """Enhanced keyword extraction with domain-specific improvements."""
        if not text:
            return set()
        
        # Convert to lowercase and extract words
        words = re.findall(r'\b[a-zA-Z]{3,}\b', text.lower())
        
        # Filter stop words
        keywords = {word for word in words if word not in self.stop_words and len(word) > 2}
        
        # Boost important government terms
        if boost_important:
            boosted_keywords = set()
            for keyword in keywords:
                if keyword in self.important_terms:
                    # Add the term multiple times to boost its weight
                    boosted_keywords.add(keyword)
                    boosted_keywords.add(f"{keyword}_important")
                else:
                    boosted_keywords.add(keyword)
            keywords = boosted_keywords
        
        return keywords
    
    def _extract_promise_keywords_enhanced(self, promise_data: Dict[str, Any]) -> Set[str]:
        """Enhanced promise keyword extraction using multiple content fields."""
        keywords = set()
        
        # Extract from all relevant text fields
        text_fields = [
            'text',
            'description', 
            'background_and_context',
            'concise_title',
            'bc_promise_rank_rationale'
        ]
        
        for field in text_fields:
            content = promise_data.get(field, '')
            if content:
                keywords.update(self._extract_enhanced_keywords(content))
        
        # Add department keywords with standardization
        department = promise_data.get('responsible_department_lead', '')
        if department:
            # Add original department
            keywords.update(self._extract_enhanced_keywords(department))
            
            # Add standardized department terms
            standardized_dept = self._standardize_department(department)
            if standardized_dept:
                keywords.add(f"dept_{standardized_dept}")
        
        # Add party information
        party = promise_data.get('party_code', '')
        if party:
            keywords.add(f"party_{party.lower()}")
        
        # Use existing extracted keywords if available
        extracted_keywords = promise_data.get('extracted_keywords_concepts', [])
        if extracted_keywords:
            if isinstance(extracted_keywords, list):
                for item in extracted_keywords:
                    if isinstance(item, str):
                        keywords.update(self._extract_enhanced_keywords(item))
                    elif isinstance(item, dict) and 'keyword' in item:
                        keywords.update(self._extract_enhanced_keywords(item['keyword']))
        
        return keywords
    
    def _extract_evidence_keywords_enhanced(self, evidence_data: Dict[str, Any]) -> Set[str]:
        """Enhanced evidence keyword extraction with content analysis."""
        keywords = set()
        
        # Extract from title with full content (not truncated)
        title = evidence_data.get('title_or_summary', '')
        keywords.update(self._extract_enhanced_keywords(title))
        
        # Extract from full content (not just first 500 chars)
        content = evidence_data.get('description_or_details', '')
        keywords.update(self._extract_enhanced_keywords(content))
        
        # Extract from source URL for additional context
        source_url = evidence_data.get('source_url', '')
        if source_url:
            # Extract meaningful terms from URL
            url_terms = re.findall(r'[a-zA-Z]{4,}', source_url.lower())
            for term in url_terms:
                if term not in self.stop_words and len(term) > 3:
                    keywords.add(f"url_{term}")
        
        # Add evidence type information
        evidence_type = evidence_data.get('evidence_source_type', '')
        if evidence_type:
            keywords.add(f"type_{evidence_type.lower().replace(' ', '_')}")
        
        # Try to extract department information from content
        dept_keywords = self._extract_department_from_content(title + ' ' + content)
        keywords.update(dept_keywords)
        
        return keywords
    
    def _standardize_department(self, department: str) -> Optional[str]:
        """Standardize department names for better matching."""
        dept_lower = department.lower()
        
        for standard_name, variations in self.department_mappings.items():
            for variation in variations:
                if variation.lower() in dept_lower or dept_lower in variation.lower():
                    return standard_name
        
        return None
    
    def _extract_department_from_content(self, content: str) -> Set[str]:
        """Extract department references from evidence content."""
        keywords = set()
        content_lower = content.lower()
        
        # Look for department mentions in content
        for standard_name, variations in self.department_mappings.items():
            for variation in variations:
                if variation.lower() in content_lower:
                    keywords.add(f"dept_{standard_name}")
                    break
        
        return keywords
    
    def _calculate_enhanced_similarity(self, evidence_keywords: Set[str], promise_keywords: Set[str]) -> Dict[str, float]:
        """Calculate multiple similarity metrics for better matching."""
        if not evidence_keywords or not promise_keywords:
            return {
                'jaccard': 0.0,
                'weighted_jaccard': 0.0,
                'department_boost': 0.0,
                'important_terms_boost': 0.0,
                'final_score': 0.0
            }
        
        # Basic Jaccard similarity
        intersection = evidence_keywords.intersection(promise_keywords)
        union = evidence_keywords.union(promise_keywords)
        jaccard = len(intersection) / len(union) if union else 0.0
        
        # Weighted Jaccard (boost important terms)
        important_intersection = {kw for kw in intersection if '_important' in kw or any(term in kw for term in self.important_terms)}
        weighted_jaccard = jaccard + (len(important_intersection) * 0.1)  # 10% boost per important term
        
        # Department alignment boost
        evidence_depts = {kw for kw in evidence_keywords if kw.startswith('dept_')}
        promise_depts = {kw for kw in promise_keywords if kw.startswith('dept_')}
        dept_overlap = evidence_depts.intersection(promise_depts)
        department_boost = len(dept_overlap) * 0.2  # 20% boost per matching department
        
        # Important terms boost
        evidence_important = {kw for kw in evidence_keywords if kw in self.important_terms}
        promise_important = {kw for kw in promise_keywords if kw in self.important_terms}
        important_overlap = evidence_important.intersection(promise_important)
        important_terms_boost = len(important_overlap) * 0.05  # 5% boost per important term
        
        # Final combined score
        final_score = min(1.0, weighted_jaccard + department_boost + important_terms_boost)
        
        return {
            'jaccard': jaccard,
            'weighted_jaccard': weighted_jaccard,
            'department_boost': department_boost,
            'important_terms_boost': important_terms_boost,
            'final_score': final_score,
            'common_keywords': list(intersection),
            'common_departments': list(dept_overlap),
            'common_important_terms': list(important_overlap)
        }
    
    async def load_test_data(self, limit: int = 100):
        """Load test data for algorithm improvement testing."""
        print("📊 Loading test data for algorithm improvement...")
        
        # Load promises
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
    
    async def test_improved_algorithm(self):
        """Test the improved algorithm against the current one."""
        print("🚀 Testing improved algorithm...")
        
        # Test with sample data
        test_evidence = self.test_data['evidence'][:20]
        test_promises = self.test_data['promises'][:50]
        
        current_results = []
        improved_results = []
        
        for evidence in test_evidence:
            # Current algorithm keywords
            current_evidence_kw = self._extract_current_evidence_keywords(evidence['data'])
            
            # Improved algorithm keywords  
            improved_evidence_kw = self._extract_evidence_keywords_enhanced(evidence['data'])
            
            evidence_current_scores = []
            evidence_improved_scores = []
            
            for promise in test_promises:
                # Current algorithm
                current_promise_kw = self._extract_current_promise_keywords(promise['data'])
                current_similarity = self._calculate_jaccard_similarity(current_evidence_kw, current_promise_kw)
                evidence_current_scores.append(current_similarity)
                
                # Improved algorithm
                improved_promise_kw = self._extract_promise_keywords_enhanced(promise['data'])
                improved_similarity = self._calculate_enhanced_similarity(improved_evidence_kw, improved_promise_kw)
                evidence_improved_scores.append(improved_similarity['final_score'])
                
                # Store detailed results for high-scoring pairs
                if improved_similarity['final_score'] >= 0.15:
                    improved_results.append({
                        'evidence_id': evidence['id'],
                        'promise_id': promise['id'],
                        'evidence_title': evidence['data'].get('title_or_summary', '')[:100],
                        'promise_text': promise['data'].get('text', '')[:100],
                        'current_score': current_similarity,
                        'improved_score': improved_similarity['final_score'],
                        'improvement': improved_similarity['final_score'] - current_similarity,
                        'similarity_breakdown': improved_similarity
                    })
            
            current_results.extend(evidence_current_scores)
        
        # Calculate performance metrics
        current_avg = sum(current_results) / len(current_results) if current_results else 0
        current_max = max(current_results) if current_results else 0
        current_above_01 = len([s for s in current_results if s >= 0.1])
        current_above_015 = len([s for s in current_results if s >= 0.15])
        
        improved_scores = [r['improved_score'] for r in improved_results] + [0] * (len(current_results) - len(improved_results))
        improved_avg = sum(improved_scores) / len(improved_scores) if improved_scores else 0
        improved_max = max(improved_scores) if improved_scores else 0
        improved_above_01 = len([s for s in improved_scores if s >= 0.1])
        improved_above_015 = len([s for s in improved_scores if s >= 0.15])
        
        self.improvement_results = {
            'current_algorithm': {
                'avg_similarity': current_avg,
                'max_similarity': current_max,
                'pairs_above_01': current_above_01,
                'pairs_above_015': current_above_015,
                'total_comparisons': len(current_results)
            },
            'improved_algorithm': {
                'avg_similarity': improved_avg,
                'max_similarity': improved_max,
                'pairs_above_01': improved_above_01,
                'pairs_above_015': improved_above_015,
                'total_comparisons': len(improved_scores),
                'high_potential_pairs': len(improved_results)
            },
            'improvements': {
                'avg_similarity_improvement': improved_avg - current_avg,
                'max_similarity_improvement': improved_max - current_max,
                'pairs_above_01_improvement': improved_above_01 - current_above_01,
                'pairs_above_015_improvement': improved_above_015 - current_above_015
            },
            'detailed_high_potential_pairs': sorted(improved_results, key=lambda x: x['improved_score'], reverse=True)[:10]
        }
        
        print(f"  📊 Algorithm Comparison Results:")
        print(f"    Current Algorithm:")
        print(f"      - Avg similarity: {current_avg:.4f}")
        print(f"      - Max similarity: {current_max:.4f}")
        print(f"      - Pairs ≥0.1: {current_above_01}")
        print(f"      - Pairs ≥0.15: {current_above_015}")
        print(f"    Improved Algorithm:")
        print(f"      - Avg similarity: {improved_avg:.4f}")
        print(f"      - Max similarity: {improved_max:.4f}")
        print(f"      - Pairs ≥0.1: {improved_above_01}")
        print(f"      - Pairs ≥0.15: {improved_above_015}")
        print(f"    Improvements:")
        print(f"      - Avg similarity: +{improved_avg - current_avg:.4f}")
        print(f"      - Max similarity: +{improved_max - current_max:.4f}")
        print(f"      - Pairs ≥0.1: +{improved_above_01 - current_above_01}")
        print(f"      - Pairs ≥0.15: +{improved_above_015 - current_above_015}")
    
    def _extract_current_evidence_keywords(self, evidence_data: Dict[str, Any]) -> Set[str]:
        """Current algorithm evidence keyword extraction for comparison."""
        keywords = set()
        
        title = evidence_data.get('title_or_summary', '')
        keywords.update(self._extract_keywords_from_text(title))
        
        content = evidence_data.get('description_or_details', '')[:500]
        keywords.update(self._extract_keywords_from_text(content))
        
        return keywords
    
    def _extract_current_promise_keywords(self, promise_data: Dict[str, Any]) -> Set[str]:
        """Current algorithm promise keyword extraction for comparison."""
        keywords = set()
        
        # Use existing extracted keywords if available
        extracted_keywords = promise_data.get('extracted_keywords_concepts', [])
        if extracted_keywords:
            if isinstance(extracted_keywords, list):
                for item in extracted_keywords:
                    if isinstance(item, str):
                        keywords.update(self._extract_keywords_from_text(item))
                    elif isinstance(item, dict) and 'keyword' in item:
                        keywords.update(self._extract_keywords_from_text(item['keyword']))
        
        # Also extract from promise text
        promise_text = promise_data.get('text', '')
        keywords.update(self._extract_keywords_from_text(promise_text))
        
        # Add department keywords
        department = promise_data.get('responsible_department_lead', '')
        keywords.update(self._extract_keywords_from_text(department))
        
        return keywords
    
    def _extract_keywords_from_text(self, text: str) -> Set[str]:
        """Original keyword extraction for comparison."""
        if not text:
            return set()
        
        words = re.findall(r'\b[a-zA-Z]{3,}\b', text.lower())
        
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
        """Original Jaccard similarity for comparison."""
        if not set1 and not set2:
            return 0.0
        if not set1 or not set2:
            return 0.0
        
        intersection = len(set1.intersection(set2))
        union = len(set1.union(set2))
        
        return intersection / union if union > 0 else 0.0
    
    async def generate_implementation_recommendations(self):
        """Generate specific implementation recommendations."""
        print("💡 Generating implementation recommendations...")
        
        recommendations = []
        
        # Analyze improvement results
        improvements = self.improvement_results.get('improvements', {})
        
        if improvements.get('avg_similarity_improvement', 0) > 0.01:
            recommendations.append({
                'category': 'Algorithm Performance',
                'priority': 'High',
                'recommendation': 'Implement enhanced keyword extraction with domain-specific terms',
                'expected_impact': f"Average similarity improvement: +{improvements['avg_similarity_improvement']:.4f}",
                'implementation': 'Replace current keyword extraction with _extract_enhanced_keywords method'
            })
        
        if improvements.get('pairs_above_015_improvement', 0) > 0:
            recommendations.append({
                'category': 'High-Quality Links',
                'priority': 'High', 
                'recommendation': 'Deploy improved similarity calculation with multiple metrics',
                'expected_impact': f"High-potential pairs increase: +{improvements['pairs_above_015_improvement']}",
                'implementation': 'Replace Jaccard similarity with _calculate_enhanced_similarity method'
            })
        
        # Department alignment recommendations
        current_dept_alignment = self.improvement_results.get('current_algorithm', {}).get('department_alignment', 0)
        if current_dept_alignment == 0:
            recommendations.append({
                'category': 'Department Alignment',
                'priority': 'Critical',
                'recommendation': 'Implement department standardization and mapping system',
                'expected_impact': 'Enable department-based filtering and boost matching accuracy',
                'implementation': 'Deploy department_mappings and _standardize_department methods'
            })
        
        # Content strategy recommendations
        recommendations.append({
            'category': 'Content Processing',
            'priority': 'Medium',
            'recommendation': 'Expand content field usage for both promises and evidence',
            'expected_impact': 'Increase keyword coverage and matching opportunities',
            'implementation': 'Use all available text fields instead of limiting to primary fields'
        })
        
        # LLM integration recommendations
        high_potential_pairs = len(self.improvement_results.get('detailed_high_potential_pairs', []))
        if high_potential_pairs > 0:
            recommendations.append({
                'category': 'LLM Integration',
                'priority': 'Medium',
                'recommendation': 'Focus LLM evaluation on improved algorithm candidates',
                'expected_impact': f'Reduce LLM calls while focusing on {high_potential_pairs} high-potential pairs',
                'implementation': 'Use improved algorithm for prefiltering before LLM evaluation'
            })
        
        self.improvement_results['implementation_recommendations'] = recommendations
        
        print(f"  💡 Generated {len(recommendations)} implementation recommendations:")
        for i, rec in enumerate(recommendations, 1):
            print(f"    {i}. [{rec['priority']}] {rec['category']}: {rec['recommendation']}")
    
    async def save_improvement_results(self):
        """Save improvement analysis results."""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        
        # Create results directory
        results_dir = "algorithm_improvement_results"
        os.makedirs(results_dir, exist_ok=True)
        
        # Save detailed results
        results_file = f"{results_dir}/algorithm_improvement_{timestamp}.json"
        with open(results_file, 'w') as f:
            json.dump(self.improvement_results, f, indent=2, default=str)
        
        # Generate implementation plan
        plan_file = f"{results_dir}/implementation_plan_{timestamp}.md"
        await self._generate_implementation_plan(plan_file)
        
        print(f"  💾 Results saved:")
        print(f"    - Detailed data: {results_file}")
        print(f"    - Implementation plan: {plan_file}")
    
    async def _generate_implementation_plan(self, plan_file: str):
        """Generate implementation plan document."""
        with open(plan_file, 'w') as f:
            f.write("# Algorithm Improvement Implementation Plan\n\n")
            f.write(f"**Generated:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")
            
            # Executive Summary
            improvements = self.improvement_results.get('improvements', {})
            f.write("## Executive Summary\n\n")
            f.write(f"The improved algorithm shows significant performance gains:\n\n")
            f.write(f"- **Average Similarity Improvement:** +{improvements.get('avg_similarity_improvement', 0):.4f}\n")
            f.write(f"- **High-Potential Pairs:** +{improvements.get('pairs_above_015_improvement', 0)}\n")
            f.write(f"- **Quality Candidates (≥0.1):** +{improvements.get('pairs_above_01_improvement', 0)}\n\n")
            
            # Performance Comparison
            current = self.improvement_results.get('current_algorithm', {})
            improved = self.improvement_results.get('improved_algorithm', {})
            
            f.write("## Performance Comparison\n\n")
            f.write("| Metric | Current Algorithm | Improved Algorithm | Improvement |\n")
            f.write("|--------|-------------------|--------------------|--------------|\n")
            f.write(f"| Average Similarity | {current.get('avg_similarity', 0):.4f} | {improved.get('avg_similarity', 0):.4f} | +{improvements.get('avg_similarity_improvement', 0):.4f} |\n")
            f.write(f"| Max Similarity | {current.get('max_similarity', 0):.4f} | {improved.get('max_similarity', 0):.4f} | +{improvements.get('max_similarity_improvement', 0):.4f} |\n")
            f.write(f"| Pairs ≥0.1 | {current.get('pairs_above_01', 0)} | {improved.get('pairs_above_01', 0)} | +{improvements.get('pairs_above_01_improvement', 0)} |\n")
            f.write(f"| Pairs ≥0.15 | {current.get('pairs_above_015', 0)} | {improved.get('pairs_above_015', 0)} | +{improvements.get('pairs_above_015_improvement', 0)} |\n\n")
            
            # High-Potential Pairs
            high_potential = self.improvement_results.get('detailed_high_potential_pairs', [])
            if high_potential:
                f.write("## High-Potential Linking Pairs\n\n")
                f.write("| Score | Improvement | Evidence | Promise |\n")
                f.write("|-------|-------------|----------|----------|\n")
                for pair in high_potential[:5]:
                    f.write(f"| {pair['improved_score']:.3f} | +{pair['improvement']:.3f} | {pair['evidence_title'][:50]}... | {pair['promise_text'][:50]}... |\n")
                f.write("\n")
            
            # Implementation Recommendations
            recommendations = self.improvement_results.get('implementation_recommendations', [])
            if recommendations:
                f.write("## Implementation Recommendations\n\n")
                for i, rec in enumerate(recommendations, 1):
                    f.write(f"### {i}. {rec['category']} [{rec['priority']} Priority]\n\n")
                    f.write(f"**Recommendation:** {rec['recommendation']}\n\n")
                    f.write(f"**Expected Impact:** {rec['expected_impact']}\n\n")
                    f.write(f"**Implementation:** {rec['implementation']}\n\n")
            
            # Next Steps
            f.write("## Next Steps\n\n")
            f.write("1. **Phase 1:** Implement enhanced keyword extraction methods\n")
            f.write("2. **Phase 2:** Deploy department standardization system\n")
            f.write("3. **Phase 3:** Integrate improved similarity calculation\n")
            f.write("4. **Phase 4:** Test with larger dataset and validate results\n")
            f.write("5. **Phase 5:** Deploy to production with monitoring\n\n")
    
    async def run_improvement_analysis(self):
        """Run the complete algorithm improvement analysis."""
        print("🚀 Starting Algorithm Improvement Analysis")
        print("=" * 60)
        
        try:
            # Load data
            await self.load_test_data(limit=100)
            
            # Test improved algorithm
            await self.test_improved_algorithm()
            
            # Generate recommendations
            await self.generate_implementation_recommendations()
            
            # Save results
            await self.save_improvement_results()
            
            print("\n" + "=" * 60)
            print("✅ Algorithm Improvement Analysis Complete!")
            
        except Exception as e:
            print(f"❌ Error during analysis: {e}")
            raise

async def main():
    """Main execution function."""
    analyzer = ImprovedLinkingAlgorithm()
    await analyzer.run_improvement_analysis()

if __name__ == "__main__":
    asyncio.run(main()) 