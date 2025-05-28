#!/usr/bin/env python3
"""
Test Specific Promise-Evidence Pair Linking

Tests whether the improved algorithm will successfully link:
- Promise: LPC_20211216_MANDL_6718c486 (Just Transition legislation)
- Evidence: 20230615_44_C-50_event_houseofcommons_d7d2da8e (Bill C-50 sustainable jobs)

This ensures our algorithm improvements will correctly identify this critical link.
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

class SpecificPairTester:
    """Tests specific promise-evidence pair linking with improved algorithm."""
    
    def __init__(self):
        self.test_results = {}
        
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
            'social', 'welfare', 'benefit', 'pension', 'disability', 'senior',
            'sustainable', 'jobs', 'transition', 'workers', 'communities', 'legislation'
        }
        
        # Department mapping for standardization
        self.department_mappings = {
            'natural_resources': ['Natural Resources Canada', 'Minister of Natural Resources', 'NRCan'],
            'employment': ['Employment and Social Development Canada', 'ESDC', 'Minister of Employment'],
            'indigenous': ['Indigenous Services Canada', 'ISC', 'Minister of Indigenous Services'],
            'economic_development': ['Federal Economic Development Agency for Southern Ontario', 'FedDev Ontario'],
            'heritage': ['Canadian Heritage', 'Minister of Canadian Heritage'],
            'global_affairs': ['Global Affairs Canada', 'GAC', 'Minister of Foreign Affairs'],
            'crown_indigenous': ['Crown-Indigenous Relations and Northern Affairs Canada', 'CIRNAC']
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
    
    def _extract_promise_keywords_enhanced(self, promise_data: Dict[str, Any]) -> Set[str]:
        """Enhanced promise keyword extraction using multiple content fields."""
        keywords = set()
        
        # Extract from all relevant text fields
        text_fields = [
            'text',
            'description', 
            'background_and_context',
            'concise_title'
        ]
        
        for field in text_fields:
            content = promise_data.get(field, '')
            if content:
                if isinstance(content, list):
                    # Handle list fields like description
                    for item in content:
                        if isinstance(item, str):
                            keywords.update(self._extract_enhanced_keywords(item))
                else:
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
        
        # Extract from title with full content
        title = evidence_data.get('title_or_summary', '')
        keywords.update(self._extract_enhanced_keywords(title))
        
        # Extract from description/details
        content = evidence_data.get('description_or_details', '')
        keywords.update(self._extract_enhanced_keywords(content))
        
        # Extract from bill-specific fields
        bill_summary = evidence_data.get('bill_timeline_summary_llm', '')
        keywords.update(self._extract_enhanced_keywords(bill_summary))
        
        bill_description = evidence_data.get('bill_one_sentence_description_llm', '')
        keywords.update(self._extract_enhanced_keywords(bill_description))
        
        # Extract from bill keywords
        bill_keywords = evidence_data.get('bill_extracted_keywords_concepts', [])
        if bill_keywords:
            for keyword in bill_keywords:
                keywords.update(self._extract_enhanced_keywords(keyword))
        
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
        
        # Add department information
        linked_departments = evidence_data.get('linked_departments', [])
        for dept in linked_departments:
            keywords.update(self._extract_enhanced_keywords(dept))
            standardized_dept = self._standardize_department(dept)
            if standardized_dept:
                keywords.add(f"dept_{standardized_dept}")
        
        return keywords
    
    def _calculate_enhanced_similarity(self, evidence_keywords: Set[str], promise_keywords: Set[str]) -> Dict[str, float]:
        """Calculate multiple similarity metrics for better matching."""
        if not evidence_keywords or not promise_keywords:
            return {
                'jaccard': 0.0,
                'weighted_jaccard': 0.0,
                'department_boost': 0.0,
                'important_terms_boost': 0.0,
                'final_score': 0.0,
                'common_keywords': [],
                'common_departments': [],
                'common_important_terms': []
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
    
    async def load_specific_pair(self):
        """Load the specific promise and evidence pair for testing."""
        print("📊 Loading specific promise-evidence pair...")
        
        # Load specific promise
        promise_id = "LPC_20211216_MANDL_6718c486"
        evidence_id = "20230615_44_C-50_event_houseofcommons_d7d2da8e"
        
        try:
            # Get promise
            promise_doc = await asyncio.to_thread(
                db.collection(PROMISES_COLLECTION_ROOT).document(promise_id).get
            )
            
            if not promise_doc.exists:
                raise Exception(f"Promise {promise_id} not found")
            
            promise_data = promise_doc.to_dict()
            
            # Get evidence
            evidence_doc = await asyncio.to_thread(
                db.collection(EVIDENCE_COLLECTION_ROOT).document(evidence_id).get
            )
            
            if not evidence_doc.exists:
                raise Exception(f"Evidence {evidence_id} not found")
            
            evidence_data = evidence_doc.to_dict()
            
            self.test_data = {
                'promise': {
                    'id': promise_id,
                    'data': promise_data
                },
                'evidence': {
                    'id': evidence_id,
                    'data': evidence_data
                }
            }
            
            print(f"  ✅ Loaded promise: {promise_data.get('concise_title', 'No title')}")
            print(f"  ✅ Loaded evidence: {evidence_data.get('title_or_summary', 'No title')}")
            
        except Exception as e:
            print(f"  ❌ Error loading data: {e}")
            raise
    
    async def test_current_algorithm(self):
        """Test the current algorithm on this specific pair."""
        print("🔍 Testing current algorithm...")
        
        promise_data = self.test_data['promise']['data']
        evidence_data = self.test_data['evidence']['data']
        
        # Current algorithm keyword extraction
        promise_keywords = self._extract_current_promise_keywords(promise_data)
        evidence_keywords = self._extract_current_evidence_keywords(evidence_data)
        
        # Current algorithm similarity
        similarity = self._calculate_jaccard_similarity(promise_keywords, evidence_keywords)
        
        self.test_results['current_algorithm'] = {
            'promise_keywords': list(promise_keywords),
            'evidence_keywords': list(evidence_keywords),
            'similarity_score': similarity,
            'common_keywords': list(promise_keywords.intersection(evidence_keywords)),
            'would_link': similarity >= 0.1  # Assuming 0.1 threshold
        }
        
        print(f"  📊 Current Algorithm Results:")
        print(f"    - Promise keywords: {len(promise_keywords)}")
        print(f"    - Evidence keywords: {len(evidence_keywords)}")
        print(f"    - Similarity score: {similarity:.4f}")
        print(f"    - Common keywords: {len(promise_keywords.intersection(evidence_keywords))}")
        print(f"    - Would link (≥0.1): {similarity >= 0.1}")
    
    async def test_improved_algorithm(self):
        """Test the improved algorithm on this specific pair."""
        print("🚀 Testing improved algorithm...")
        
        promise_data = self.test_data['promise']['data']
        evidence_data = self.test_data['evidence']['data']
        
        # Improved algorithm keyword extraction
        promise_keywords = self._extract_promise_keywords_enhanced(promise_data)
        evidence_keywords = self._extract_evidence_keywords_enhanced(evidence_data)
        
        # Improved algorithm similarity
        similarity_result = self._calculate_enhanced_similarity(evidence_keywords, promise_keywords)
        
        self.test_results['improved_algorithm'] = {
            'promise_keywords': list(promise_keywords),
            'evidence_keywords': list(evidence_keywords),
            'similarity_breakdown': similarity_result,
            'would_link': similarity_result['final_score'] >= 0.15  # Higher threshold for improved
        }
        
        print(f"  📊 Improved Algorithm Results:")
        print(f"    - Promise keywords: {len(promise_keywords)}")
        print(f"    - Evidence keywords: {len(evidence_keywords)}")
        print(f"    - Final similarity score: {similarity_result['final_score']:.4f}")
        print(f"    - Jaccard similarity: {similarity_result['jaccard']:.4f}")
        print(f"    - Department boost: {similarity_result['department_boost']:.4f}")
        print(f"    - Important terms boost: {similarity_result['important_terms_boost']:.4f}")
        print(f"    - Common keywords: {len(similarity_result['common_keywords'])}")
        print(f"    - Common departments: {len(similarity_result['common_departments'])}")
        print(f"    - Would link (≥0.15): {similarity_result['final_score'] >= 0.15}")
    
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
    
    def _extract_current_evidence_keywords(self, evidence_data: Dict[str, Any]) -> Set[str]:
        """Current algorithm evidence keyword extraction for comparison."""
        keywords = set()
        
        title = evidence_data.get('title_or_summary', '')
        keywords.update(self._extract_keywords_from_text(title))
        
        content = evidence_data.get('description_or_details', '')[:500]
        keywords.update(self._extract_keywords_from_text(content))
        
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
    
    async def analyze_content_overlap(self):
        """Analyze the content overlap between promise and evidence."""
        print("🔍 Analyzing content overlap...")
        
        promise_data = self.test_data['promise']['data']
        evidence_data = self.test_data['evidence']['data']
        
        # Extract key content for analysis
        promise_content = {
            'text': promise_data.get('text', ''),
            'title': promise_data.get('concise_title', ''),
            'description': promise_data.get('description', ''),
            'background': promise_data.get('background_and_context', ''),
            'department': promise_data.get('responsible_department_lead', ''),
            'keywords': promise_data.get('extracted_keywords_concepts', [])
        }
        
        evidence_content = {
            'title': evidence_data.get('title_or_summary', ''),
            'description': evidence_data.get('description_or_details', ''),
            'bill_summary': evidence_data.get('bill_timeline_summary_llm', ''),
            'bill_description': evidence_data.get('bill_one_sentence_description_llm', ''),
            'departments': evidence_data.get('linked_departments', []),
            'keywords': evidence_data.get('bill_extracted_keywords_concepts', [])
        }
        
        print(f"  📋 Promise Content Analysis:")
        print(f"    - Text: {promise_content['text'][:100]}...")
        print(f"    - Title: {promise_content['title']}")
        print(f"    - Department: {promise_content['department']}")
        print(f"    - Keywords: {promise_content['keywords']}")
        
        print(f"  📋 Evidence Content Analysis:")
        print(f"    - Title: {evidence_content['title']}")
        print(f"    - Bill Summary: {evidence_content['bill_summary'][:100]}...")
        print(f"    - Departments: {evidence_content['departments']}")
        print(f"    - Keywords: {evidence_content['keywords']}")
        
        # Identify key overlapping concepts
        overlaps = []
        
        # Check for "just transition" / "sustainable jobs" connection
        promise_text_lower = promise_content['text'].lower()
        evidence_summary_lower = evidence_content['bill_summary'].lower()
        
        if 'just transition' in promise_text_lower and 'sustainable jobs' in evidence_summary_lower:
            overlaps.append("Conceptual match: 'Just Transition' (promise) ↔ 'Sustainable Jobs' (evidence)")
        
        # Check department alignment
        if promise_content['department'] in evidence_content['departments']:
            overlaps.append(f"Department match: {promise_content['department']}")
        
        # Check keyword overlaps
        promise_kw_lower = [kw.lower() for kw in promise_content['keywords'] if isinstance(kw, str)]
        evidence_kw_lower = [kw.lower() for kw in evidence_content['keywords'] if isinstance(kw, str)]
        
        common_keywords = set(promise_kw_lower).intersection(set(evidence_kw_lower))
        if common_keywords:
            overlaps.append(f"Keyword matches: {list(common_keywords)}")
        
        self.test_results['content_analysis'] = {
            'promise_content': promise_content,
            'evidence_content': evidence_content,
            'identified_overlaps': overlaps
        }
        
        print(f"  🎯 Identified Overlaps:")
        for overlap in overlaps:
            print(f"    - {overlap}")
    
    async def generate_recommendations(self):
        """Generate recommendations for ensuring this pair links correctly."""
        print("💡 Generating recommendations...")
        
        current_result = self.test_results['current_algorithm']
        improved_result = self.test_results['improved_algorithm']
        
        recommendations = []
        
        # Check if improved algorithm successfully links
        if improved_result['would_link']:
            recommendations.append({
                'priority': 'SUCCESS',
                'recommendation': 'Improved algorithm successfully identifies this link',
                'details': f"Final score: {improved_result['similarity_breakdown']['final_score']:.4f} (≥0.15 threshold)"
            })
        else:
            recommendations.append({
                'priority': 'CRITICAL',
                'recommendation': 'Improved algorithm still fails to link this pair',
                'details': f"Final score: {improved_result['similarity_breakdown']['final_score']:.4f} (below 0.15 threshold)"
            })
        
        # Check department alignment
        dept_boost = improved_result['similarity_breakdown']['department_boost']
        if dept_boost > 0:
            recommendations.append({
                'priority': 'SUCCESS',
                'recommendation': 'Department standardization working correctly',
                'details': f"Department boost: +{dept_boost:.4f}"
            })
        else:
            recommendations.append({
                'priority': 'HIGH',
                'recommendation': 'Improve department standardization mapping',
                'details': 'No department alignment detected despite both mentioning Natural Resources Canada'
            })
        
        # Check important terms
        important_boost = improved_result['similarity_breakdown']['important_terms_boost']
        if important_boost > 0:
            recommendations.append({
                'priority': 'SUCCESS',
                'recommendation': 'Important terms boost working',
                'details': f"Important terms boost: +{important_boost:.4f}"
            })
        
        # Check for conceptual matching needs
        content_analysis = self.test_results['content_analysis']
        overlaps = content_analysis['identified_overlaps']
        
        if any('just transition' in overlap.lower() and 'sustainable jobs' in overlap.lower() for overlap in overlaps):
            recommendations.append({
                'priority': 'HIGH',
                'recommendation': 'Add conceptual synonym mapping',
                'details': 'Map "Just Transition" ↔ "Sustainable Jobs" as related concepts'
            })
        
        self.test_results['recommendations'] = recommendations
        
        print(f"  💡 Recommendations:")
        for rec in recommendations:
            print(f"    [{rec['priority']}] {rec['recommendation']}")
            print(f"        {rec['details']}")
    
    async def save_test_results(self):
        """Save test results to file."""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        
        # Create results directory
        results_dir = "specific_pair_test_results"
        os.makedirs(results_dir, exist_ok=True)
        
        # Save detailed results
        results_file = f"{results_dir}/specific_pair_test_{timestamp}.json"
        with open(results_file, 'w') as f:
            json.dump(self.test_results, f, indent=2, default=str)
        
        print(f"  💾 Test results saved: {results_file}")
    
    async def run_complete_test(self):
        """Run the complete test for the specific promise-evidence pair."""
        print("🚀 Testing Specific Promise-Evidence Pair Linking")
        print("=" * 60)
        print("Promise: LPC_20211216_MANDL_6718c486 (Just Transition)")
        print("Evidence: 20230615_44_C-50_event_houseofcommons_d7d2da8e (Bill C-50)")
        print("=" * 60)
        
        try:
            # Load data
            await self.load_specific_pair()
            
            # Test current algorithm
            await self.test_current_algorithm()
            
            # Test improved algorithm
            await self.test_improved_algorithm()
            
            # Analyze content
            await self.analyze_content_overlap()
            
            # Generate recommendations
            await self.generate_recommendations()
            
            # Save results
            await self.save_test_results()
            
            print("\n" + "=" * 60)
            print("✅ Specific Pair Test Complete!")
            
            # Summary
            current_links = self.test_results['current_algorithm']['would_link']
            improved_links = self.test_results['improved_algorithm']['would_link']
            
            print(f"\n📊 SUMMARY:")
            print(f"  Current Algorithm Links: {'✅ YES' if current_links else '❌ NO'}")
            print(f"  Improved Algorithm Links: {'✅ YES' if improved_links else '❌ NO'}")
            
            if improved_links:
                print(f"  🎉 SUCCESS: Improved algorithm will correctly link this pair!")
            else:
                print(f"  ⚠️  WARNING: Additional improvements needed for this pair")
            
        except Exception as e:
            print(f"❌ Error during test: {e}")
            raise

async def main():
    """Main execution function."""
    tester = SpecificPairTester()
    await tester.run_complete_test()

if __name__ == "__main__":
    asyncio.run(main()) 