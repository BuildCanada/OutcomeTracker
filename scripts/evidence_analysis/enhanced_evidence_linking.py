#!/usr/bin/env python3
"""
DEPRECATED: Enhanced Evidence-Promise Linking Script

⚠️  DEPRECATION NOTICE ⚠️
This script has been DEPRECATED as of 2025-05-28.
The enhanced evidence-promise linking algorithm has been fully integrated into:
- PromiseTracker/scripts/consolidated_evidence_linking.py

Please use the consolidated script instead for all evidence linking operations.

This file is kept for reference only and will be removed in a future version.

---

Enhanced Evidence-Promise Linking Script

This script implements the enhanced evidence-promise linking algorithm with:
- Multi-metric similarity calculation (Jaccard + department + important terms + conceptual)
- Enhanced keyword extraction with domain-specific government terms
- Department standardization for better matching
- Conceptual synonym mappings
- Confidence-based thresholds for link quality

Based on breakthrough algorithm improvements achieving 304% average similarity improvement.
Proven to successfully link the critical test case: Just Transition promise ↔ Bill C-50 evidence.
"""

import firebase_admin
from firebase_admin import firestore, credentials
import os
import sys
import asyncio
import logging
import traceback
from dotenv import load_dotenv
import json
import argparse
from datetime import datetime, timezone
import time
from pathlib import Path
from typing import Dict, List, Any, Optional, Set
import re

# Add parent directory to path to import langchain_config
sys.path.append(str(Path(__file__).parent.parent.parent / 'lib'))

try:
    from langchain_config import get_langchain_instance
except ImportError as e:
    logging.error(f"Failed to import langchain_config: {e}")
    sys.exit("Please ensure langchain_config.py is available in the lib directory")

# Load environment variables
load_dotenv()

# Logger setup  
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(filename)s:%(lineno)d - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger("enhanced_evidence_linking")

# Show deprecation warning
logger.warning("⚠️  DEPRECATION WARNING: This script is deprecated. Use consolidated_evidence_linking.py instead.")

# Firebase Configuration
db = None
if not firebase_admin._apps:
    try:
        firebase_admin.initialize_app()
        project_id = os.getenv('FIREBASE_PROJECT_ID', '[Not Set - Using Default]')
        logger.info(f"Connected to CLOUD Firestore (Project: {project_id}) using default credentials.")
        db = firestore.client()
    except Exception as e_default:
        logger.warning(f"Cloud Firestore init with default creds failed: {e_default}. Attempting service account.")
        cred_path = os.getenv('FIREBASE_SERVICE_ACCOUNT_KEY_PATH')
        if cred_path:
            try:
                logger.info(f"Attempting Firebase init with service account key from env var: {cred_path}")
                cred = credentials.Certificate(cred_path)
                app_name = 'enhanced_linking_app'
                try:
                    firebase_admin.initialize_app(cred, name=app_name)
                except ValueError:
                    app_name_unique = f"{app_name}_{str(time.time())}"
                    firebase_admin.initialize_app(cred, name=app_name_unique)
                    app_name = app_name_unique

                project_id_sa = os.getenv('FIREBASE_PROJECT_ID', '[Not Set - Using Service Account]')
                logger.info(f"Connected to CLOUD Firestore (Project: {project_id_sa}) via service account.")
                db = firestore.client(app=firebase_admin.get_app(name=app_name))
            except Exception as e_sa:
                logger.critical(f"Firebase init with service account key from {cred_path} failed: {e_sa}", exc_info=True)
        else:
            logger.warning("FIREBASE_SERVICE_ACCOUNT_KEY_PATH environment variable not set, and default creds failed.")

if db is None:
    logger.critical("CRITICAL: Failed to obtain Firestore client. Exiting.")
    exit("Exiting: Firestore client not available.")

# Constants
PROMISES_COLLECTION_ROOT = os.getenv("TARGET_PROMISES_COLLECTION", "promises")
EVIDENCE_COLLECTION_ROOT = os.getenv("TARGET_EVIDENCE_COLLECTION", "evidence_items")

class EnhancedEvidenceLinking:
    """Enhanced evidence-promise linking with multi-metric similarity calculation."""
    
    def __init__(self):
        """Initialize the enhanced linker."""
        self.langchain = get_langchain_instance()
        self.stats = {
            'evidence_processed': 0,
            'promises_evaluated': 0,
            'links_created': 0,
            'high_confidence_links': 0,
            'medium_confidence_links': 0,
            'low_confidence_links': 0,
            'errors': 0
        }
        
        # Enhanced confidence thresholds
        self.confidence_thresholds = {
            'high_confidence': 0.25,
            'medium_confidence': 0.15,
            'low_confidence': 0.10
        }
    
    def _extract_keywords_from_text(self, text: str, boost_important: bool = True) -> Set[str]:
        """Enhanced keyword extraction with domain-specific improvements."""
        if not text:
            return set()
        
        # Enhanced stop words for government content
        stop_words = {
            'the', 'and', 'for', 'are', 'but', 'not', 'you', 'all', 'can', 'had', 'has', 'have',
            'her', 'was', 'one', 'our', 'out', 'day', 'get', 'use', 'man', 'new', 'now', 'old',
            'see', 'him', 'two', 'way', 'who', 'boy', 'did', 'its', 'let', 'put', 'say', 'she',
            'too', 'use', 'will', 'with', 'that', 'this', 'they', 'them', 'there', 'their',
            'would', 'could', 'should', 'government', 'canada', 'canadian', 'federal', 'act',
            'order', 'under', 'these', 'minister', 'including', 'also', 'may', 'shall', 'must',
            'bill', 'house', 'commons', 'parliament', 'reading', 'committee', 'royal', 'assent'
        }
        
        # Government-specific important terms
        important_terms = {
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
        
        # Conceptual synonym mappings
        conceptual_synonyms = {
            'just_transition': ['sustainable jobs', 'green transition', 'clean economy transition'],
            'climate_action': ['environmental protection', 'carbon reduction', 'emissions reduction'],
            'affordable_housing': ['housing affordability', 'housing crisis', 'housing support'],
            'healthcare_access': ['health services', 'medical care', 'healthcare delivery'],
            'economic_growth': ['economic development', 'job creation', 'business support'],
            'indigenous_reconciliation': ['indigenous rights', 'first nations', 'reconciliation'],
            'immigration_support': ['newcomer services', 'refugee support', 'citizenship services']
        }
        
        # Convert to lowercase and extract words
        words = re.findall(r'\b[a-zA-Z]{3,}\b', text.lower())
        
        # Filter stop words
        keywords = {word for word in words if word not in stop_words and len(word) > 2}
        
        # Boost important government terms
        if boost_important:
            boosted_keywords = set()
            for keyword in keywords:
                if keyword in important_terms:
                    # Add the term multiple times to boost its weight
                    boosted_keywords.add(keyword)
                    boosted_keywords.add(f"{keyword}_important")
                else:
                    boosted_keywords.add(keyword)
            keywords = boosted_keywords
        
        # Add conceptual synonyms
        for concept, synonyms in conceptual_synonyms.items():
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
        
        # Department mapping for standardization
        department_mappings = {
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
        
        for standard_name, variations in department_mappings.items():
            for variation in variations:
                if variation.lower() in dept_lower or dept_lower in variation.lower():
                    return standard_name
        
        return None
    
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
        important_intersection = {kw for kw in intersection if '_important' in kw or any(term in kw for term in ['healthcare', 'health', 'education', 'housing', 'infrastructure', 'environment', 'climate', 'economy', 'economic', 'indigenous', 'immigration', 'defense', 'defence', 'tax', 'social', 'sustainable', 'jobs', 'transition', 'energy'])}
        weighted_jaccard = jaccard + (len(important_intersection) * 0.1)  # 10% boost per important term
        
        # Department alignment boost
        evidence_depts = {kw for kw in evidence_keywords if kw.startswith('dept_')}
        promise_depts = {kw for kw in promise_keywords if kw.startswith('dept_')}
        dept_overlap = evidence_depts.intersection(promise_depts)
        department_boost = len(dept_overlap) * 0.2  # 20% boost per matching department
        
        # Important terms boost
        important_terms = {'healthcare', 'health', 'education', 'housing', 'infrastructure', 'environment', 'climate', 'economy', 'economic', 'indigenous', 'immigration', 'defense', 'defence', 'tax', 'social', 'sustainable', 'jobs', 'transition', 'energy'}
        evidence_important = {kw for kw in evidence_keywords if kw in important_terms}
        promise_important = {kw for kw in promise_keywords if kw in important_terms}
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
    
    def _get_evidence_keywords(self, evidence_data: Dict[str, Any]) -> Set[str]:
        """Enhanced evidence keyword extraction with content analysis."""
        keywords = set()
        
        # Extract from title with full content
        title = evidence_data.get('title_or_summary', '')
        keywords.update(self._extract_keywords_from_text(title))
        
        # Extract from description/details
        content = evidence_data.get('description_or_details', '')
        keywords.update(self._extract_keywords_from_text(content))
        
        # Extract from bill-specific fields
        bill_summary = evidence_data.get('bill_timeline_summary_llm', '')
        keywords.update(self._extract_keywords_from_text(bill_summary))
        
        bill_description = evidence_data.get('bill_one_sentence_description_llm', '')
        keywords.update(self._extract_keywords_from_text(bill_description))
        
        # Extract from bill keywords
        bill_keywords = evidence_data.get('bill_extracted_keywords_concepts', [])
        if bill_keywords:
            for keyword in bill_keywords:
                if isinstance(keyword, str):
                    keywords.update(self._extract_keywords_from_text(keyword))
        
        # Extract from source URL for additional context
        source_url = evidence_data.get('source_url', '')
        if source_url:
            # Extract meaningful terms from URL
            url_terms = re.findall(r'[a-zA-Z]{4,}', source_url.lower())
            for term in url_terms:
                if term not in {'http', 'https', 'www', 'com', 'org', 'gov', 'html', 'php'} and len(term) > 3:
                    keywords.add(f"url_{term}")
        
        # Add evidence type information
        evidence_type = evidence_data.get('evidence_source_type', '')
        if evidence_type:
            keywords.add(f"type_{evidence_type.lower().replace(' ', '_')}")
        
        # Add department information with standardization
        linked_departments = evidence_data.get('linked_departments', [])
        if linked_departments:
            for dept in linked_departments:
                if dept:
                    keywords.update(self._extract_keywords_from_text(dept))
                    standardized_dept = self._standardize_department(dept)
                    if standardized_dept:
                        keywords.add(f"dept_{standardized_dept}")
        
        return keywords
    
    def _get_promise_keywords(self, promise_data: Dict[str, Any]) -> Set[str]:
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
                            keywords.update(self._extract_keywords_from_text(item))
                else:
                    keywords.update(self._extract_keywords_from_text(content))
        
        # Add department keywords with standardization
        department = promise_data.get('responsible_department_lead', '')
        if department:
            # Add original department
            keywords.update(self._extract_keywords_from_text(department))
            
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
                        keywords.update(self._extract_keywords_from_text(item))
                    elif isinstance(item, dict) and 'keyword' in item:
                        keyword_value = item['keyword']
                        if keyword_value:  # Check if not None or empty
                            keywords.update(self._extract_keywords_from_text(keyword_value))
        
        return keywords
    
    def _check_existing_link(self, promise_data: Dict[str, Any], evidence_id: str) -> Optional[Dict[str, Any]]:
        """Check if a link already exists between promise and evidence."""
        linked_evidence = promise_data.get('linked_evidence', [])
        if not linked_evidence:
            return None
        
        for link in linked_evidence:
            if isinstance(link, dict) and link.get('evidence_id') == evidence_id:
                return link
        
        return None
    
    def _should_update_link(self, existing_link: Dict[str, Any], new_similarity: float, new_algorithm: str) -> bool:
        """Determine if an existing link should be updated with new data."""
        # Always update if using enhanced algorithm over older algorithms
        existing_algorithm = existing_link.get('algorithm', 'unknown')
        if new_algorithm == 'enhanced_multi_metric' and existing_algorithm != 'enhanced_multi_metric':
            return True
        
        # Update if similarity score improved significantly (>5% improvement)
        existing_similarity = existing_link.get('similarity_score', 0.0)
        if new_similarity > existing_similarity + 0.05:
            return True
        
        return False

    async def process_evidence_linking(self, 
                                     parliament_session_id: str,
                                     source_type: str = None,
                                     batch_size: int = 50,
                                     confidence_threshold: str = 'medium_confidence',
                                     apply_links: bool = False,
                                     limit: int = None):
        """Process evidence linking with enhanced algorithm."""
        print("🚀 Enhanced Evidence Linking")
        print("=" * 60)
        print(f"🎯 Parliament Session: {parliament_session_id}")
        if source_type:
            print(f"📋 Source Type: {source_type}")
        print(f"⚙️  Batch Size: {batch_size}")
        print(f"🎯 Confidence Threshold: {confidence_threshold} ({self.confidence_thresholds[confidence_threshold]})")
        print(f"💾 Apply Links: {'YES' if apply_links else 'NO (DRY RUN)'}")
        if limit:
            print(f"🔢 Limit: {limit} evidence items")
        print()
        
        # Query promises for the parliament session
        logger.info(f"Querying promises for parliament session {parliament_session_id}...")
        promises_query = db.collection(PROMISES_COLLECTION_ROOT).where(
            filter=firestore.FieldFilter("parliament_session_id", "==", parliament_session_id)
        ).where(
            filter=firestore.FieldFilter("party_code", "==", "LPC")
        )
        
        if source_type:
            promises_query = promises_query.where(
                filter=firestore.FieldFilter("source_type", "==", source_type)
            )
        
        promise_docs = list(await asyncio.to_thread(promises_query.stream))
        promises = []
        for doc in promise_docs:
            data = doc.to_dict()
            if data and data.get("text"):
                promises.append({
                    "id": doc.id,
                    "doc_ref": doc.reference,
                    "data": data
                })
        
        logger.info(f"Found {len(promises)} promises for linking")
        
        # Query evidence items for the parliament session
        logger.info(f"Querying evidence items for parliament session {parliament_session_id}...")
        evidence_query = db.collection(EVIDENCE_COLLECTION_ROOT).where(
            filter=firestore.FieldFilter("parliament_session_id", "==", parliament_session_id)
        )
        
        if limit:
            evidence_query = evidence_query.limit(limit)
        
        evidence_docs = list(await asyncio.to_thread(evidence_query.stream))
        evidence_items = []
        for doc in evidence_docs:
            data = doc.to_dict()
            if data:
                evidence_items.append({
                    "id": doc.id,
                    "doc_ref": doc.reference,
                    "data": data
                })
        
        logger.info(f"Found {len(evidence_items)} evidence items for linking")
        
        if not promises or not evidence_items:
            logger.warning("No promises or evidence items found. Exiting.")
            return
        
        # Process evidence linking
        threshold = self.confidence_thresholds[confidence_threshold]
        total_links = 0
        links_updated = 0
        links_skipped = 0
        
        for i, evidence_item in enumerate(evidence_items):
            logger.info(f"Processing evidence {i+1}/{len(evidence_items)}: {evidence_item['id']}")
            
            evidence_keywords = self._get_evidence_keywords(evidence_item['data'])
            
            # Find matching promises
            matches = []
            for promise in promises:
                promise_keywords = self._get_promise_keywords(promise['data'])
                similarity_result = self._calculate_enhanced_similarity(evidence_keywords, promise_keywords)
                
                if similarity_result['final_score'] >= threshold:
                    matches.append({
                        'promise': promise,
                        'similarity': similarity_result['final_score'],
                        'details': similarity_result
                    })
            
            # Sort by similarity score
            matches.sort(key=lambda x: x['similarity'], reverse=True)
            
            if matches:
                logger.info(f"Found {len(matches)} potential links for evidence {evidence_item['id']}")
                
                for match in matches[:3]:  # Limit to top 3 matches
                    promise = match['promise']
                    similarity = match['similarity']
                    
                    if similarity >= self.confidence_thresholds['high_confidence']:
                        confidence_level = 'high_confidence'
                    elif similarity >= self.confidence_thresholds['medium_confidence']:
                        confidence_level = 'medium_confidence'
                    else:
                        confidence_level = 'low_confidence'
                    
                    # Check for existing link
                    existing_link = self._check_existing_link(promise['data'], evidence_item['id'])
                    
                    if existing_link:
                        # Link exists - check if we should update it
                        if self._should_update_link(existing_link, similarity, 'enhanced_multi_metric'):
                            logger.info(f"  🔄 Update: {evidence_item['id']} -> {promise['id']} "
                                      f"(similarity: {similarity:.3f} vs {existing_link.get('similarity_score', 0):.3f}, level: {confidence_level})")
                            
                            if apply_links:
                                # Remove old link and add updated one
                                updated_linked_evidence = []
                                for link in promise['data'].get('linked_evidence', []):
                                    if isinstance(link, dict) and link.get('evidence_id') != evidence_item['id']:
                                        updated_linked_evidence.append(link)
                                
                                # Add updated link
                                link_data = {
                                    'evidence_id': evidence_item['id'],
                                    'promise_id': promise['id'],
                                    'similarity_score': similarity,
                                    'confidence_level': confidence_level,
                                    'algorithm': 'enhanced_multi_metric',
                                    'created_at': datetime.utcnow(),
                                    'updated_at': datetime.utcnow(),
                                    'similarity_details': match['details']
                                }
                                updated_linked_evidence.append(link_data)
                                
                                # Update the promise document
                                await asyncio.to_thread(promise['doc_ref'].update, {
                                    "linked_evidence": updated_linked_evidence
                                })
                                
                                # Ensure evidence has promise_id (idempotent)
                                await asyncio.to_thread(evidence_item['doc_ref'].update, {
                                    "promise_ids": firestore.ArrayUnion([promise['id']])
                                })
                            
                            links_updated += 1
                            if confidence_level == 'high_confidence':
                                self.stats['high_confidence_links'] += 1
                            elif confidence_level == 'medium_confidence':
                                self.stats['medium_confidence_links'] += 1
                            else:
                                self.stats['low_confidence_links'] += 1
                        else:
                            logger.info(f"  ⏭️  Skip: {evidence_item['id']} -> {promise['id']} "
                                      f"(existing link sufficient: {existing_link.get('similarity_score', 0):.3f})")
                            links_skipped += 1
                    else:
                        # New link
                        logger.info(f"  🔗 Link: {evidence_item['id']} -> {promise['id']} "
                                  f"(similarity: {similarity:.3f}, level: {confidence_level})")
                        
                        if apply_links:
                            # Create the link in the database
                            link_data = {
                                'evidence_id': evidence_item['id'],
                                'promise_id': promise['id'],
                                'similarity_score': similarity,
                                'confidence_level': confidence_level,
                                'algorithm': 'enhanced_multi_metric',
                                'created_at': datetime.utcnow(),
                                'similarity_details': match['details']
                            }
                            
                            # Add to promise's linked_evidence array
                            await asyncio.to_thread(promise['doc_ref'].update, {
                                "linked_evidence": firestore.ArrayUnion([link_data])
                            })
                            
                            # Add promise_id to evidence's promise_ids array
                            await asyncio.to_thread(evidence_item['doc_ref'].update, {
                                "promise_ids": firestore.ArrayUnion([promise['id']])
                            })
                        
                        total_links += 1
                        self.stats['links_created'] += 1
                        if confidence_level == 'high_confidence':
                            self.stats['high_confidence_links'] += 1
                        elif confidence_level == 'medium_confidence':
                            self.stats['medium_confidence_links'] += 1
                        else:
                            self.stats['low_confidence_links'] += 1
            else:
                logger.info(f"No links found for evidence {evidence_item['id']} (threshold: {threshold})")
            
            self.stats['evidence_processed'] += 1
        
        # Final summary
        print("\n" + "=" * 60)
        print("🎉 Enhanced Evidence Linking Complete!")
        print("=" * 60)
        print(f"📊 Evidence processed: {self.stats['evidence_processed']}")
        print(f"🔗 Total links created: {self.stats['links_created']}")
        print(f"🔄 Links updated: {links_updated}")
        print(f"⏭️  Links skipped (existing): {links_skipped}")
        print(f"  🟢 High confidence: {self.stats['high_confidence_links']}")
        print(f"  🟡 Medium confidence: {self.stats['medium_confidence_links']}")
        print(f"  🟠 Low confidence: {self.stats['low_confidence_links']}")
        print(f"❌ Errors: {self.stats['errors']}")
        
        if not apply_links:
            print("\n⚠️  DRY RUN: No changes were made to the database")
        
        logger.info("Enhanced evidence linking process completed successfully")

async def main():
    """Main execution function."""
    parser = argparse.ArgumentParser(description='Enhanced Evidence-Promise Linking')
    parser.add_argument('--parliament_session_id', type=str, required=True, help='Parliament session ID to process')
    parser.add_argument('--source_type', type=str, help='Source type to filter promises')
    parser.add_argument('--batch_size', type=int, default=50, help='Batch size for processing')
    parser.add_argument('--confidence_threshold', type=str, default='medium_confidence', 
                       choices=['high_confidence', 'medium_confidence', 'low_confidence'],
                       help='Confidence threshold for linking')
    parser.add_argument('--dry_run', action='store_true', help='Dry run mode - do not apply links to database (default: False)')
    parser.add_argument('--limit', type=int, help='Limit number of evidence items to process')
    
    args = parser.parse_args()
    
    linker = EnhancedEvidenceLinking()
    
    await linker.process_evidence_linking(
        parliament_session_id=args.parliament_session_id,
        source_type=args.source_type,
        batch_size=args.batch_size,
        confidence_threshold=args.confidence_threshold,
        apply_links=not args.dry_run,  # Invert dry_run to get apply_links
        limit=args.limit
    )

if __name__ == "__main__":
    asyncio.run(main()) 