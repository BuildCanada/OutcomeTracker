#!/usr/bin/env python3
"""
Enhanced Evidence Linking Algorithm (Temporary Version)

This is a temporary enhanced version of the evidence linking system that incorporates:
- Enhanced keyword extraction with domain-specific terms
- Department standardization and mapping
- Multi-metric similarity calculation
- Important terms boosting
- Conceptual synonym mapping

This version will be tested before updating the production scripts.
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

class EnhancedEvidenceLinking:
    """Enhanced evidence linking with improved algorithm."""
    
    def __init__(self):
        self.linking_results = {}
        
        # Enhanced stop words for government content
        self.stop_words = {
            'the', 'and', 'for', 'are', 'but', 'not', 'you', 'all', 'can', 'had', 'has', 'have',
            'her', 'was', 'one', 'our', 'out', 'day', 'get', 'use', 'man', 'new', 'now', 'old',
            'see', 'him', 'two', 'way', 'who', 'boy', 'did', 'its', 'let', 'put', 'say', 'she',
            'too', 'use', 'will', 'with', 'that', 'this', 'they', 'them', 'there', 'their',
            'would', 'could', 'should', 'government', 'canada', 'canadian', 'federal', 'act',
            'order', 'under', 'these', 'minister', 'including', 'also', 'may', 'shall', 'must',
            'bill', 'house', 'commons', 'parliament', 'reading', 'committee', 'royal', 'assent'
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
            'sustainable', 'jobs', 'transition', 'workers', 'communities', 'legislation',
            'energy', 'oil', 'gas', 'mining', 'forestry', 'agriculture', 'fisheries'
        }
        
        # Department mapping for standardization
        self.department_mappings = {
            'natural_resources': [
                'Natural Resources Canada', 'Minister of Natural Resources', 'NRCan',
                'natural resources canada', 'minister of natural resources'
            ],
            'employment': [
                'Employment and Social Development Canada', 'ESDC', 'Minister of Employment',
                'employment and social development canada', 'minister of employment'
            ],
            'indigenous': [
                'Indigenous Services Canada', 'ISC', 'Minister of Indigenous Services',
                'indigenous services canada', 'minister of indigenous services'
            ],
            'economic_development': [
                'Federal Economic Development Agency for Southern Ontario', 'FedDev Ontario',
                'Innovation, Science and Economic Development Canada', 'ISED'
            ],
            'heritage': [
                'Canadian Heritage', 'Minister of Canadian Heritage',
                'canadian heritage', 'minister of canadian heritage'
            ],
            'global_affairs': [
                'Global Affairs Canada', 'GAC', 'Minister of Foreign Affairs',
                'global affairs canada', 'minister of foreign affairs'
            ],
            'crown_indigenous': [
                'Crown-Indigenous Relations and Northern Affairs Canada', 'CIRNAC',
                'crown-indigenous relations and northern affairs canada'
            ],
            'finance': [
                'Department of Finance Canada', 'Minister of Finance',
                'department of finance canada', 'minister of finance'
            ],
            'health': [
                'Health Canada', 'Minister of Health',
                'health canada', 'minister of health'
            ],
            'transport': [
                'Transport Canada', 'Minister of Transport',
                'transport canada', 'minister of transport'
            ]
        }
        
        # Conceptual synonym mappings
        self.conceptual_synonyms = {
            'just_transition': ['sustainable jobs', 'green transition', 'clean economy transition'],
            'climate_action': ['environmental protection', 'carbon reduction', 'emissions reduction'],
            'affordable_housing': ['housing affordability', 'housing crisis', 'housing support'],
            'healthcare_access': ['health services', 'medical care', 'healthcare delivery'],
            'economic_growth': ['economic development', 'job creation', 'business support'],
            'indigenous_reconciliation': ['indigenous rights', 'first nations', 'reconciliation'],
            'immigration_support': ['newcomer services', 'refugee support', 'citizenship services']
        }
        
        # Similarity thresholds
        self.similarity_thresholds = {
            'high_confidence': 0.25,
            'medium_confidence': 0.15,
            'low_confidence': 0.10
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
        
        # Add conceptual synonyms
        for concept, synonyms in self.conceptual_synonyms.items():
            for synonym in synonyms:
                if synonym.lower() in text.lower():
                    keywords.add(f"concept_{concept}")
                    break
        
        return keywords
    
    def _standardize_department(self, department: str) -> Optional[str]:
        """Standardize department names for better matching."""
        if not department:
            return None
            
        dept_lower = department.lower()
        
        for standard_name, variations in self.department_mappings.items():
            for variation in variations:
                if variation.lower() in dept_lower or dept_lower in variation.lower():
                    return standard_name
        
        return None
    
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
        
        # Use existing extracted keywords if available (with null check)
        extracted_keywords = promise_data.get('extracted_keywords_concepts', [])
        if extracted_keywords:
            if isinstance(extracted_keywords, list):
                for item in extracted_keywords:
                    if isinstance(item, str):
                        keywords.update(self._extract_enhanced_keywords(item))
                    elif isinstance(item, dict) and 'keyword' in item:
                        keyword_value = item['keyword']
                        if keyword_value:  # Check if not None or empty
                            keywords.update(self._extract_enhanced_keywords(keyword_value))
        
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
                if isinstance(keyword, str):
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
        
        # Add department information (with null check)
        linked_departments = evidence_data.get('linked_departments', [])
        if linked_departments:  # Check if not None and not empty
            for dept in linked_departments:
                if dept:  # Check if department is not None or empty
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
                'conceptual_boost': 0.0,
                'final_score': 0.0,
                'common_keywords': [],
                'common_departments': [],
                'common_important_terms': [],
                'common_concepts': []
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
        
        # Conceptual similarity boost
        evidence_concepts = {kw for kw in evidence_keywords if kw.startswith('concept_')}
        promise_concepts = {kw for kw in promise_keywords if kw.startswith('concept_')}
        concept_overlap = evidence_concepts.intersection(promise_concepts)
        conceptual_boost = len(concept_overlap) * 0.15  # 15% boost per conceptual match
        
        # Final combined score
        final_score = min(1.0, weighted_jaccard + department_boost + important_terms_boost + conceptual_boost)
        
        return {
            'jaccard': jaccard,
            'weighted_jaccard': weighted_jaccard,
            'department_boost': department_boost,
            'important_terms_boost': important_terms_boost,
            'conceptual_boost': conceptual_boost,
            'final_score': final_score,
            'common_keywords': list(intersection),
            'common_departments': list(dept_overlap),
            'common_important_terms': list(important_overlap),
            'common_concepts': list(concept_overlap)
        }
    
    async def load_promises_and_evidence(self, limit_promises: int = 50, limit_evidence: int = 100):
        """Load promises and evidence for linking analysis."""
        print(f"📊 Loading {limit_promises} promises and {limit_evidence} evidence items...")
        
        try:
            # Load promises
            promises_query = db.collection(PROMISES_COLLECTION_ROOT).limit(limit_promises)
            promises_docs = await asyncio.to_thread(promises_query.get)
            
            promises = {}
            for doc in promises_docs:
                promises[doc.id] = doc.to_dict()
            
            # Load evidence
            evidence_query = db.collection(EVIDENCE_COLLECTION_ROOT).limit(limit_evidence)
            evidence_docs = await asyncio.to_thread(evidence_query.get)
            
            evidence_items = {}
            for doc in evidence_docs:
                evidence_items[doc.id] = doc.to_dict()
            
            self.promises = promises
            self.evidence_items = evidence_items
            
            print(f"  ✅ Loaded {len(promises)} promises")
            print(f"  ✅ Loaded {len(evidence_items)} evidence items")
            
        except Exception as e:
            print(f"  ❌ Error loading data: {e}")
            raise
    
    async def run_enhanced_linking(self, confidence_threshold: str = 'medium_confidence'):
        """Run enhanced linking algorithm on loaded data."""
        print(f"🚀 Running enhanced linking with {confidence_threshold} threshold...")
        
        threshold = self.similarity_thresholds[confidence_threshold]
        links_found = []
        
        total_comparisons = len(self.promises) * len(self.evidence_items)
        comparisons_done = 0
        
        print(f"  📊 Will perform {total_comparisons:,} comparisons")
        
        for promise_id, promise_data in self.promises.items():
            promise_keywords = self._extract_promise_keywords_enhanced(promise_data)
            
            for evidence_id, evidence_data in self.evidence_items.items():
                evidence_keywords = self._extract_evidence_keywords_enhanced(evidence_data)
                
                # Calculate similarity
                similarity_result = self._calculate_enhanced_similarity(evidence_keywords, promise_keywords)
                
                # Check if meets threshold
                if similarity_result['final_score'] >= threshold:
                    link = {
                        'promise_id': promise_id,
                        'evidence_id': evidence_id,
                        'similarity_score': similarity_result['final_score'],
                        'similarity_breakdown': similarity_result,
                        'promise_title': promise_data.get('concise_title', 'No title'),
                        'evidence_title': evidence_data.get('title_or_summary', 'No title'),
                        'confidence_level': self._get_confidence_level(similarity_result['final_score'])
                    }
                    links_found.append(link)
                
                comparisons_done += 1
                if comparisons_done % 1000 == 0:
                    print(f"    Progress: {comparisons_done:,}/{total_comparisons:,} ({comparisons_done/total_comparisons*100:.1f}%)")
        
        # Sort by similarity score
        links_found.sort(key=lambda x: x['similarity_score'], reverse=True)
        
        self.linking_results = {
            'threshold_used': threshold,
            'confidence_level': confidence_threshold,
            'total_comparisons': total_comparisons,
            'links_found': len(links_found),
            'links': links_found
        }
        
        print(f"  ✅ Found {len(links_found)} potential links")
        
        # Show confidence breakdown
        confidence_breakdown = {}
        for link in links_found:
            conf_level = link['confidence_level']
            confidence_breakdown[conf_level] = confidence_breakdown.get(conf_level, 0) + 1
        
        print(f"  📊 Confidence breakdown:")
        for level, count in confidence_breakdown.items():
            print(f"    - {level}: {count} links")
    
    def _get_confidence_level(self, score: float) -> str:
        """Determine confidence level based on similarity score."""
        if score >= self.similarity_thresholds['high_confidence']:
            return 'high_confidence'
        elif score >= self.similarity_thresholds['medium_confidence']:
            return 'medium_confidence'
        else:
            return 'low_confidence'
    
    async def save_linking_results(self):
        """Save linking results to file."""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        
        # Create results directory
        results_dir = "enhanced_linking_results"
        os.makedirs(results_dir, exist_ok=True)
        
        # Save detailed results
        results_file = f"{results_dir}/enhanced_linking_{timestamp}.json"
        with open(results_file, 'w') as f:
            json.dump(self.linking_results, f, indent=2, default=str)
        
        print(f"  💾 Results saved: {results_file}")
        
        # Save summary report
        summary_file = f"{results_dir}/enhanced_linking_summary_{timestamp}.txt"
        with open(summary_file, 'w') as f:
            f.write("Enhanced Evidence Linking Results Summary\n")
            f.write("=" * 50 + "\n\n")
            f.write(f"Timestamp: {timestamp}\n")
            f.write(f"Threshold: {self.linking_results['threshold_used']:.4f} ({self.linking_results['confidence_level']})\n")
            f.write(f"Total Comparisons: {self.linking_results['total_comparisons']:,}\n")
            f.write(f"Links Found: {self.linking_results['links_found']}\n\n")
            
            f.write("Top 10 Links:\n")
            f.write("-" * 30 + "\n")
            for i, link in enumerate(self.linking_results['links'][:10], 1):
                f.write(f"{i}. Score: {link['similarity_score']:.4f} ({link['confidence_level']})\n")
                f.write(f"   Promise: {link['promise_title']}\n")
                f.write(f"   Evidence: {link['evidence_title']}\n\n")
        
        print(f"  📄 Summary saved: {summary_file}")
    
    async def apply_links_to_database(self, dry_run: bool = True, max_links: int = 10):
        """Apply the found links to the database (with dry run option)."""
        if dry_run:
            print(f"🧪 DRY RUN: Would apply top {max_links} links to database")
        else:
            print(f"💾 Applying top {max_links} links to database...")
        
        links_to_apply = self.linking_results['links'][:max_links]
        
        for i, link in enumerate(links_to_apply, 1):
            promise_id = link['promise_id']
            evidence_id = link['evidence_id']
            
            if dry_run:
                print(f"  {i}. Would link: {promise_id} ↔ {evidence_id} (score: {link['similarity_score']:.4f})")
            else:
                try:
                    # Update promise with evidence link
                    promise_ref = db.collection(PROMISES_COLLECTION_ROOT).document(promise_id)
                    await asyncio.to_thread(
                        promise_ref.update,
                        {
                            'linked_evidence_ids': firestore.ArrayUnion([evidence_id]),
                            'last_evidence_link_update': datetime.now()
                        }
                    )
                    
                    # Update evidence with promise link
                    evidence_ref = db.collection(EVIDENCE_COLLECTION_ROOT).document(evidence_id)
                    await asyncio.to_thread(
                        evidence_ref.update,
                        {
                            'promise_ids': firestore.ArrayUnion([promise_id]),
                            'last_promise_link_update': datetime.now()
                        }
                    )
                    
                    print(f"  ✅ {i}. Linked: {promise_id} ↔ {evidence_id} (score: {link['similarity_score']:.4f})")
                    
                except Exception as e:
                    print(f"  ❌ {i}. Failed to link {promise_id} ↔ {evidence_id}: {e}")
    
    async def run_complete_enhanced_linking(self, 
                                          limit_promises: int = 50, 
                                          limit_evidence: int = 100,
                                          confidence_threshold: str = 'medium_confidence',
                                          apply_links: bool = False,
                                          max_links_to_apply: int = 10):
        """Run the complete enhanced linking process."""
        print("🚀 Enhanced Evidence Linking System")
        print("=" * 50)
        
        try:
            # Load data
            await self.load_promises_and_evidence(limit_promises, limit_evidence)
            
            # Run linking
            await self.run_enhanced_linking(confidence_threshold)
            
            # Save results
            await self.save_linking_results()
            
            # Apply links if requested
            if apply_links:
                await self.apply_links_to_database(dry_run=False, max_links=max_links_to_apply)
            else:
                await self.apply_links_to_database(dry_run=True, max_links=max_links_to_apply)
            
            print("\n" + "=" * 50)
            print("✅ Enhanced Linking Complete!")
            
            # Summary
            print(f"\n📊 SUMMARY:")
            print(f"  Links Found: {self.linking_results['links_found']}")
            print(f"  Threshold Used: {self.linking_results['threshold_used']:.4f}")
            print(f"  Applied to Database: {'Yes' if apply_links else 'No (dry run)'}")
            
        except Exception as e:
            print(f"❌ Error during enhanced linking: {e}")
            raise

async def main():
    """Main execution function."""
    linker = EnhancedEvidenceLinking()
    
    # Run with conservative settings for testing
    await linker.run_complete_enhanced_linking(
        limit_promises=20,  # Start small for testing
        limit_evidence=50,
        confidence_threshold='medium_confidence',
        apply_links=False,  # Dry run first
        max_links_to_apply=5
    )

if __name__ == "__main__":
    asyncio.run(main()) 