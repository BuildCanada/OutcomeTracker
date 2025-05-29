#!/usr/bin/env python3
"""
Consolidated Evidence-Promise Linking Pipeline

This script combines and modernizes the evidence-promise linking functionality:
- link_evidence_to_promises.py (main linking logic)
- linking_jobs/link_evidence_to_promises.py (batch processing)

Uses the centralized Langchain framework for LLM coordination and prompt management.
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
sys.path.append(str(Path(__file__).parent.parent / 'lib'))

try:
    from langchain_config import get_langchain_instance
except ImportError as e:
    logging.error(f"Failed to import langchain_config: {e}")
    sys.exit("Please ensure langchain_config.py is available in the lib directory")

# Load environment variables
load_dotenv()

# Logger setup  
logging.basicConfig(
    level=logging.DEBUG,  # Set to DEBUG to see all debug messages
    format='%(asctime)s - %(levelname)s - %(filename)s:%(lineno)d - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger("consolidated_linking")

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
                app_name = 'consolidated_linking_app'
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
RATE_LIMIT_DELAY_SECONDS = 1

class ConsolidatedEvidenceLinking:
    """Handles evidence-promise linking using Langchain framework."""
    
    def __init__(self):
        """Initialize the linker with Langchain instance."""
        self.langchain = get_langchain_instance()
        self.stats = {
            'evidence_processed': 0,
            'promises_evaluated': 0,
            'promises_prefiltered': 0,
            'promises_llm_evaluated': 0,
            'links_created': 0,
            'links_rejected': 0,
            'errors': 0
        }
        self.timing_stats = {
            'prefiltering_time': 0,
            'llm_evaluation_time': 0,
            'total_processing_time': 0
        }
    
    def _get_parliament_session_variants(self, parliament_session_id: str) -> List[str]:
        """Get all possible parliament session ID variants for matching."""
        variants = [parliament_session_id]
        
        # If session is like "44", also match "44-1", "44-2", etc.
        if "-" not in parliament_session_id:
            variants.extend([f"{parliament_session_id}-1", f"{parliament_session_id}-2"])
        else:
            # If session is like "44-1", also match base "44"
            base_session = parliament_session_id.split("-")[0]
            variants.append(base_session)
        
        return list(set(variants))  # Remove duplicates
    
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
    
    def _calculate_jaccard_similarity(self, set1: Set[str], set2: Set[str]) -> float:
        """Calculate basic Jaccard similarity between two sets (legacy method)."""
        if not set1 and not set2:
            return 0.0
        if not set1 or not set2:
            return 0.0
        
        intersection = len(set1.intersection(set2))
        union = len(set1.union(set2))
        
        return intersection / union if union > 0 else 0.0
    
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
    
    async def query_evidence_for_linking(self, parliament_session_id: str, evidence_types: List[str] = None,
                                       limit: int = None, force_reprocessing: bool = False) -> List[Dict[str, Any]]:
        """Query evidence items that need linking."""
        logger.info(f"Querying evidence for linking: session='{parliament_session_id}', types={evidence_types}, limit={limit}, force={force_reprocessing}")
        
        try:
            # Build query for unlinked evidence
            query = db.collection(EVIDENCE_COLLECTION_ROOT)
            
            # Filter by parliament session (handle variants like 44 vs 44-1)
            if parliament_session_id:
                session_variants = self._get_parliament_session_variants(parliament_session_id)
                query = query.where(filter=firestore.FieldFilter("parliament_session_id", "in", session_variants))
            
            # Filter by evidence types
            if evidence_types:
                query = query.where(filter=firestore.FieldFilter("evidence_source_type", "in", evidence_types))
            
            # Filter for evidence needing linking (unless force reprocessing)
            if not force_reprocessing:
                query = query.where(filter=firestore.FieldFilter("promise_linking_status", "in", ["pending", "unprocessed"]))
            
            if limit:
                query = query.limit(limit)
            
            # Execute query
            evidence_docs = list(await asyncio.to_thread(query.stream))
            
            evidence_items = []
            for doc in evidence_docs:
                data = doc.to_dict()
                if data:
                    evidence_items.append({
                        "id": doc.id,
                        "doc_ref": doc.reference,
                        "data": data
                    })
                else:
                    logger.warning(f"Empty data for evidence item {doc.id}, skipping.")
            
            logger.info(f"Retrieved {len(evidence_items)} evidence items for linking")
            return evidence_items
            
        except Exception as e:
            logger.error(f"Error querying evidence: {e}", exc_info=True)
            return []
    
    async def query_promises_for_linking(self, parliament_session_id: str, party_codes: List[str] = None, 
                                       promise_ranks: List[str] = None) -> List[Dict[str, Any]]:
        """Query promises that could be linked to evidence."""
        logger.info(f"Querying promises for linking: session='{parliament_session_id}', parties={party_codes}, ranks={promise_ranks}")
        
        try:
            # Build query for promises
            query = db.collection(PROMISES_COLLECTION_ROOT)
            
            # Filter by parliament session (handle variants like 44 vs 44-1)
            if parliament_session_id:
                session_variants = self._get_parliament_session_variants(parliament_session_id)
                query = query.where(filter=firestore.FieldFilter("parliament_session_id", "in", session_variants))
            
            # Filter by party codes
            if party_codes:
                query = query.where(filter=firestore.FieldFilter("party_code", "in", party_codes))
            
            # Filter by promise ranks (default to strong/medium if not specified)
            if promise_ranks:
                query = query.where(filter=firestore.FieldFilter("bc_promise_rank", "in", promise_ranks))
            
            # Execute query
            promise_docs = list(await asyncio.to_thread(query.stream))
            
            promises = []
            for doc in promise_docs:
                data = doc.to_dict()
                if data and data.get("text"):
                    promises.append({
                        "id": doc.id,
                        "doc_ref": doc.reference,
                        "data": data
                    })
                else:
                    logger.warning(f"Promise {doc.id} missing 'text' field, skipping.")
            
            logger.info(f"Retrieved {len(promises)} promises for linking")
            return promises
            
        except Exception as e:
            logger.error(f"Error querying promises: {e}", exc_info=True)
            return []
    
    def prefilter_promises_by_similarity(self, evidence_item: Dict[str, Any], promises: List[Dict[str, Any]], 
                                       min_similarity: float = 0.1, max_candidates: int = 50) -> List[Dict[str, Any]]:
        """Prefilter promises using keyword similarity to reduce LLM evaluations."""
        start_time = time.time()
        
        evidence_keywords = self._get_evidence_keywords(evidence_item['data'])
        logger.debug(f"Evidence keywords ({len(evidence_keywords)}): {sorted(list(evidence_keywords))[:10]}...")
        
        # Calculate similarity scores for all promises
        candidates = []
        for promise in promises:
            promise_keywords = self._get_promise_keywords(promise['data'])
            similarity = self._calculate_enhanced_similarity(evidence_keywords, promise_keywords)['final_score']
            
            if similarity >= min_similarity:
                candidates.append({
                    'promise': promise,
                    'similarity': similarity,
                    'evidence_keywords': evidence_keywords,
                    'promise_keywords': promise_keywords
                })
        
        # Sort by similarity (highest first) and limit
        candidates.sort(key=lambda x: x['similarity'], reverse=True)
        top_candidates = candidates[:max_candidates]
        
        prefilter_time = time.time() - start_time
        self.timing_stats['prefiltering_time'] += prefilter_time
        self.stats['promises_prefiltered'] += len(promises) - len(top_candidates)
        
        logger.info(f"Prefiltering: {len(promises)} -> {len(top_candidates)} candidates "
                   f"(similarity >= {min_similarity}) in {prefilter_time:.2f}s")
        
        if top_candidates:
            top_similarities = [f"{c['similarity']:.3f}" for c in top_candidates[:5]]
            logger.debug(f"Top similarities: {top_similarities}")
        
        return [c['promise'] for c in top_candidates]
    
    async def evaluate_evidence_promise_link(self, evidence_item: Dict[str, Any], 
                                           promise_item: Dict[str, Any]) -> Dict[str, Any]:
        """Evaluate if evidence should be linked to a promise using LLM."""
        try:
            evidence_data = evidence_item['data']
            promise_data = promise_item['data']
            
            logger.debug(f"Preparing data for LLM evaluation...")
            
            # Prepare data for LLM evaluation
            linking_data = {
                'evidence': {
                    'title': evidence_data.get('title_or_summary', ''),
                    'content': evidence_data.get('description_or_details', ''),
                    'type': evidence_data.get('evidence_source_type', ''),
                    'date': evidence_data.get('evidence_date'),
                    'source': evidence_data.get('source_url', '')
                },
                'promise': {
                    'text': promise_data.get('text', ''),
                    'party': promise_data.get('party_code', ''),
                    'department': promise_data.get('responsible_department_lead', ''),
                    'source_type': promise_data.get('source_type', ''),
                    'keywords': promise_data.get('extracted_keywords_concepts', [])
                }
            }
            
            logger.debug(f"Calling LLM for evaluation...")
            
            # Get LLM evaluation
            result = self.langchain.link_evidence_to_promise(
                evidence_data=linking_data['evidence'],
                promise_data=linking_data['promise']
            )
            
            logger.debug(f"LLM evaluation complete. Result: {result}")
            
            if 'error' in result:
                logger.error(f"Error evaluating link: {result['error']}")
                return {'should_link': False, 'error': result['error']}
            
            return result
            
        except Exception as e:
            logger.error(f"Error evaluating evidence-promise link: {e}")
            logger.error(f"Exception details: {traceback.format_exc()}")
            return {'should_link': False, 'error': str(e)}
    
    async def create_potential_link_for_review(self, evidence_item: Dict[str, Any], promise_item: Dict[str, Any],
                                             link_rationale: str, confidence_score: float, dry_run: bool = False) -> bool:
        """Create a potential link in the admin review queue instead of linking directly."""
        try:
            evidence_id = evidence_item['id']
            promise_id = promise_item['id']
            evidence_data = evidence_item['data']
            promise_data = promise_item['data']
            
            # Map confidence score to likelihood assessment for admin interface
            if confidence_score >= 0.8:
                llm_likelihood_score = "High"
            elif confidence_score >= 0.6:
                llm_likelihood_score = "Medium"
            elif confidence_score >= 0.4:
                llm_likelihood_score = "Low"
            else:
                llm_likelihood_score = "Not Related"
            
            # Create potential link data for admin review
            potential_link_data = {
                'promise_id': promise_id,
                'evidence_id': evidence_id,
                'promise_text_snippet': promise_data.get('text', '')[:500],  # Truncate for admin view
                'evidence_title_or_summary': evidence_data.get('title_or_summary', ''),
                'evidence_source_url': evidence_data.get('source_url', ''),
                'llm_explanation': link_rationale,
                'llm_likelihood_score': llm_likelihood_score,
                'confidence_score': confidence_score,
                'linking_model': self.langchain.model_name,
                'link_status': 'pending_review',
                'link_type': 'llm_generated',
                'created_at': firestore.SERVER_TIMESTAMP,
                # Add keyword overlap scores for admin filtering
                'keyword_overlap_score': {
                    'jaccard': 0.0,  # Would need to calculate if needed for admin interface
                    'common_count': 0
                }
            }
            
            if not dry_run:
                # Add to admin review queue
                await asyncio.to_thread(
                    db.collection('promise_evidence_links').add,
                    potential_link_data
                )
                
                # Update evidence processing status (but don't add final links yet)
                evidence_ref = evidence_item['doc_ref']
                await asyncio.to_thread(evidence_ref.update, {
                    "promise_linking_status": "processed",
                    "promise_linking_processed_at": firestore.SERVER_TIMESTAMP
                })
                
                logger.info(f"📋 QUEUED FOR REVIEW: evidence {evidence_id} -> promise {promise_id} (confidence: {confidence_score:.2f}, assessment: {llm_likelihood_score})")
            else:
                logger.info(f"[DRY RUN] Would queue for review: evidence {evidence_id} -> promise {promise_id} (confidence: {confidence_score:.2f}, assessment: {llm_likelihood_score})")
            
            self.stats['links_created'] += 1
            return True
            
        except Exception as e:
            logger.error(f"Error creating potential link for review: {e}")
            self.stats['errors'] += 1
            return False
    
    async def create_direct_evidence_link(self, evidence_item: Dict[str, Any], promise_item: Dict[str, Any],
                                        link_rationale: str, confidence_score: float, dry_run: bool = False) -> bool:
        """Create a direct link between evidence and promise (bypass admin review)."""
        try:
            evidence_id = evidence_item['id']
            promise_id = promise_item['id']
            
            link_data = {
                'evidence_id': evidence_id,
                'promise_id': promise_id,
                'link_rationale': link_rationale,
                'confidence_score': confidence_score,
                'linking_model': self.langchain.model_name,
                'linked_at': firestore.SERVER_TIMESTAMP,
                'link_type': 'llm_generated_direct'
            }
            
            if not dry_run:
                # Add link to promise's linked_evidence array
                promise_ref = promise_item['doc_ref']
                await asyncio.to_thread(promise_ref.update, {
                    "linked_evidence": firestore.ArrayUnion([link_data])
                })
                
                # Update evidence linking status
                evidence_ref = evidence_item['doc_ref']
                
                # Add promise_id to the promise_ids array field
                await asyncio.to_thread(evidence_ref.update, {
                    "promise_ids": firestore.ArrayUnion([promise_id]),
                    "promise_linking_status": "processed",
                    "promise_linking_processed_at": firestore.SERVER_TIMESTAMP
                })
                
                logger.info(f"🔗 DIRECT LINK: evidence {evidence_id} -> promise {promise_id} (confidence: {confidence_score:.2f})")
            else:
                logger.info(f"[DRY RUN] Would create direct link: evidence {evidence_id} -> promise {promise_id} (confidence: {confidence_score:.2f})")
            
            self.stats['links_created'] += 1
            return True
            
        except Exception as e:
            logger.error(f"Error creating direct evidence link: {e}")
            self.stats['errors'] += 1
            return False
    
    async def process_evidence_linking(self, evidence_item: Dict[str, Any], promises: List[Dict[str, Any]],
                                     min_confidence: float = 0.7, dry_run: bool = False, max_promises_per_evidence: int = None,
                                     min_similarity: float = 0.1, max_candidates: int = 50) -> int:
        """Process linking for a single evidence item against all promises using prefiltering."""
        evidence_id = evidence_item['id']
        links_created = 0
        total_start_time = time.time()
        
        logger.info(f"Processing evidence {evidence_id} against {len(promises)} promises")
        
        try:
            # Step 1: Prefilter promises using keyword similarity
            logger.info(f"🔍 Step 1: Prefiltering promises by keyword similarity...")
            prefilter_start = time.time()
            
            candidate_promises = self.prefilter_promises_by_similarity(
                evidence_item=evidence_item,
                promises=promises,
                min_similarity=min_similarity,
                max_candidates=max_candidates
            )
            
            prefilter_time = time.time() - prefilter_start
            logger.info(f"Prefiltering completed in {prefilter_time:.2f}s: {len(promises)} -> {len(candidate_promises)} candidates")
            
            if not candidate_promises:
                logger.info(f"No candidate promises found for evidence {evidence_id} with similarity >= {min_similarity}")
                return 0
            
            # Limit candidates for testing if specified
            final_candidates = candidate_promises[:max_promises_per_evidence] if max_promises_per_evidence else candidate_promises
            
            # Step 2: LLM evaluation of prefiltered candidates
            logger.info(f"🤖 Step 2: LLM evaluation of {len(final_candidates)} candidates...")
            llm_eval_start = time.time()
            
            for i, promise in enumerate(final_candidates):
                # Progress logging every 10 promises (since there are fewer now)
                if i > 0 and i % 10 == 0:
                    elapsed = time.time() - llm_eval_start
                    avg_time_per_promise = elapsed / i
                    remaining_promises = len(final_candidates) - i
                    estimated_remaining_time = avg_time_per_promise * remaining_promises
                    logger.info(f"LLM Progress: {i}/{len(final_candidates)} candidates evaluated for evidence {evidence_id} "
                              f"(avg: {avg_time_per_promise:.2f}s/candidate, est. remaining: {estimated_remaining_time:.1f}s)")
                
                self.stats['promises_llm_evaluated'] += 1
                
                # Time the evaluation
                eval_start = time.time()
                logger.debug(f"LLM evaluating evidence {evidence_id} -> promise {promise['id']} ({i+1}/{len(final_candidates)})")
                
                # Evaluate potential link
                evaluation = await self.evaluate_evidence_promise_link(evidence_item, promise)
                
                eval_time = time.time() - eval_start
                self.timing_stats['llm_evaluation_time'] += eval_time
                logger.debug(f"LLM evaluation took {eval_time:.2f}s")
                
                if evaluation.get('error'):
                    logger.warning(f"Error evaluating evidence {evidence_id} -> promise {promise['id']}: {evaluation['error']}")
                    continue
                
                should_link = evaluation.get('should_link', False)
                confidence = evaluation.get('confidence_score', 0.0)
                rationale = evaluation.get('rationale', '')
                
                if should_link and confidence >= min_confidence:
                    logger.info(f"✅ LINKING: evidence {evidence_id} -> promise {promise['id']} (confidence: {confidence:.2f})")
                    
                    # Create direct links (admin review workflow commented out for now)
                    success = await self.create_direct_evidence_link(
                        evidence_item=evidence_item,
                        promise_item=promise,
                        link_rationale=rationale,
                        confidence_score=confidence,
                        dry_run=dry_run
                    )
                    
                    # COMMENTED OUT: Admin review workflow (can be restored later)
                    # if bypass_review:
                    #     success = await self.create_direct_evidence_link(
                    #         evidence_item=evidence_item,
                    #         promise_item=promise,
                    #         link_rationale=rationale,
                    #         confidence_score=confidence,
                    #         dry_run=dry_run
                    #     )
                    # else:
                    #     success = await self.create_potential_link_for_review(
                    #         evidence_item=evidence_item,
                    #         promise_item=promise,
                    #         link_rationale=rationale,
                    #         confidence_score=confidence,
                    #         dry_run=dry_run
                    #     )
                    
                    if success:
                        links_created += 1
                else:
                    self.stats['links_rejected'] += 1
                    if should_link:  # Show rejected high-confidence links
                        logger.debug(f"❌ REJECTED (low confidence): evidence {evidence_id} -> promise {promise['id']} (confidence: {confidence:.2f})")
                
                # Small delay to prevent overwhelming the LLM
                await asyncio.sleep(0.1)
            
            llm_eval_time = time.time() - llm_eval_start
            total_time = time.time() - total_start_time
            self.timing_stats['total_processing_time'] += total_time
            
            logger.info(f"✅ Completed evidence {evidence_id}: {links_created} links created")
            logger.info(f"⏱️  Timing: prefilter={prefilter_time:.2f}s, llm_eval={llm_eval_time:.2f}s, total={total_time:.2f}s")
            logger.info(f"📊 Efficiency: {len(promises) - len(candidate_promises)} promises filtered out, "
                       f"{(len(candidate_promises)/len(promises)*100):.1f}% sent to LLM")
            
            # Update evidence processing status
            if not dry_run:
                await asyncio.to_thread(evidence_item['doc_ref'].update, {
                    "promise_linking_status": "processed",
                    "promise_linking_processed_at": firestore.SERVER_TIMESTAMP
                })
            
            return links_created
            
        except Exception as e:
            logger.error(f"Error processing evidence linking for {evidence_id}: {e}")
            self.stats['errors'] += 1
            return 0
    
    async def run_evidence_linking_pipeline(self, parliament_session_id: str, evidence_types: List[str] = None,
                                          party_codes: List[str] = None, promise_ranks: List[str] = None, 
                                          limit: int = None, min_confidence: float = 0.7, force_reprocessing: bool = False,
                                          dry_run: bool = False, max_promises_per_evidence: int = None,
                                          min_similarity: float = 0.1, max_candidates: int = 50) -> Dict[str, Any]:
        """Run the complete evidence-promise linking pipeline."""
        logger.info("=== Starting Consolidated Evidence-Promise Linking Pipeline ===")
        logger.info(f"Parliament Session: {parliament_session_id}")
        logger.info(f"Evidence Types: {evidence_types or 'All'}")
        logger.info(f"Party Codes: {party_codes or 'All'}")
        logger.info(f"Promise Ranks: {promise_ranks or 'All'}")
        logger.info(f"Limit: {limit or 'None'}")
        logger.info(f"Min Confidence: {min_confidence}")
        logger.info(f"Min Similarity: {min_similarity}")
        logger.info(f"Max Candidates: {max_candidates}")
        logger.info(f"Force Reprocessing: {force_reprocessing}")
        logger.info(f"Dry Run: {dry_run}")
        
        if dry_run:
            logger.warning("*** DRY RUN MODE: No changes will be written to Firestore ***")
        
        # Query evidence and promises
        evidence_items = await self.query_evidence_for_linking(
            parliament_session_id=parliament_session_id,
            evidence_types=evidence_types,
            limit=limit,
            force_reprocessing=force_reprocessing
        )
        
        if not evidence_items:
            logger.info("No evidence items found for linking. Exiting.")
            return self.stats
        
        promises = await self.query_promises_for_linking(
            parliament_session_id=parliament_session_id,
            party_codes=party_codes,
            promise_ranks=promise_ranks
        )
        
        if not promises:
            logger.info("No promises found for linking. Exiting.")
            return self.stats
        
        logger.info(f"Processing {len(evidence_items)} evidence items against {len(promises)} promises...")
        
        # Store for efficiency calculation
        total_promises_in_pool = len(promises)
        
        # Process each evidence item
        for i, evidence_item in enumerate(evidence_items):
            logger.info(f"--- Processing evidence {i+1}/{len(evidence_items)}: {evidence_item['id']} ---")
            
            links_created = await self.process_evidence_linking(
                evidence_item=evidence_item,
                promises=promises,
                min_confidence=min_confidence,
                dry_run=dry_run,
                max_promises_per_evidence=max_promises_per_evidence,
                min_similarity=min_similarity,
                max_candidates=max_candidates
            )
            
            self.stats['evidence_processed'] += 1
            logger.info(f"Evidence {evidence_item['id']} resulted in {links_created} links")
            
            # Rate limiting between evidence items
            if i < len(evidence_items) - 1:
                await asyncio.sleep(RATE_LIMIT_DELAY_SECONDS)
        
        # Log final statistics
        logger.info("=== Evidence-Promise Linking Pipeline Complete ===")
        logger.info(f"📊 Processing Summary:")
        logger.info(f"  Evidence items processed: {self.stats['evidence_processed']}")
        logger.info(f"  Promises prefiltered out: {self.stats['promises_prefiltered']}")
        logger.info(f"  Promises sent to LLM: {self.stats['promises_llm_evaluated']}")
        logger.info(f"  Direct links created: {self.stats['links_created']}")
        logger.info(f"  Links rejected by LLM: {self.stats['links_rejected']}")
        logger.info(f"  Errors encountered: {self.stats['errors']}")
        
        # Log timing statistics
        logger.info(f"⏱️  Timing Summary:")
        logger.info(f"  Total prefiltering time: {self.timing_stats['prefiltering_time']:.2f}s")
        logger.info(f"  Total LLM evaluation time: {self.timing_stats['llm_evaluation_time']:.2f}s")
        logger.info(f"  Total processing time: {self.timing_stats['total_processing_time']:.2f}s")
        
        if self.stats['promises_llm_evaluated'] > 0:
            avg_llm_time = self.timing_stats['llm_evaluation_time'] / self.stats['promises_llm_evaluated']
            logger.info(f"  Average LLM evaluation time: {avg_llm_time:.2f}s per promise")
        
        # Calculate efficiency gains
        if self.stats['evidence_processed'] > 0:
            # Calculate total promises that would have been evaluated without prefiltering
            total_possible_evaluations = self.stats['evidence_processed'] * total_promises_in_pool
            if total_possible_evaluations > 0:
                efficiency_gain = (self.stats['promises_prefiltered'] / total_possible_evaluations) * 100
                logger.info(f"🚀 Efficiency Gain: {efficiency_gain:.1f}% of promise evaluations avoided through prefiltering")
                logger.info(f"📈 Performance: {self.stats['promises_llm_evaluated']}/{total_possible_evaluations} LLM calls made ({(self.stats['promises_llm_evaluated']/total_possible_evaluations*100):.1f}%)")
        
        # Get cost summary
        cost_summary = self.langchain.get_cost_summary()
        logger.info(f"💰 LLM Usage Summary:")
        logger.info(f"  Total estimated cost: ${cost_summary['total_cost_usd']:.4f}")
        logger.info(f"  Total tokens: {cost_summary['total_tokens']}")
        logger.info(f"  Total LLM calls: {cost_summary['total_calls']}")
        
        return self.stats

async def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(description='Consolidated Evidence-Promise Linking Pipeline')
    parser.add_argument(
        '--parliament_session_id',
        type=str,
        required=True,
        help='Parliament session ID (e.g., "44")'
    )
    parser.add_argument(
        '--evidence_types',
        nargs='+',
        choices=['OIC', 'Canada Gazette Part II', 'Bill Event (LEGISinfo)', 'News'],
        help='Types of evidence to process'
    )
    parser.add_argument(
        '--party_codes',
        nargs='+',
        choices=['LPC', 'CPC', 'NDP', 'BQ', 'GPC'],
        help='Party codes to process promises for'
    )
    parser.add_argument(
        '--limit',
        type=int,
        help='Limit number of evidence items to process'
    )
    parser.add_argument(
        '--min_confidence',
        type=float,
        default=0.7,
        help='Minimum confidence score for creating links (default: 0.7)'
    )
    parser.add_argument(
        '--force_reprocessing',
        action='store_true',
        help='Force reprocessing even if evidence already processed'
    )
    parser.add_argument(
        '--dry_run',
        action='store_true',
        help='Run without making changes to Firestore'
    )
    parser.add_argument(
        '--max_promises_per_evidence',
        type=int,
        help='Limit number of promises to evaluate per evidence item (for testing)'
    )
    parser.add_argument(
        '--promise_ranks',
        nargs='+',
        choices=['strong', 'medium', 'weak'],
        default=['strong', 'medium'],
        help='Promise rank types to process (default: strong, medium)'
    )
    parser.add_argument(
        '--min_similarity',
        type=float,
        default=0.1,
        help='Minimum Jaccard similarity for prefiltering (default: 0.1)'
    )
    parser.add_argument(
        '--max_candidates',
        type=int,
        default=50,
        help='Maximum candidate promises to send to LLM after prefiltering (default: 50)'
    )
    # COMMENTED OUT: Admin review bypass parameter (direct linking is now default)
    # parser.add_argument(
    #     '--bypass_review',
    #     action='store_true',
    #     help='Bypass admin review queue and create links directly (for testing only)'
    # )
    
    args = parser.parse_args()
    
    # Run evidence linking pipeline
    linker = ConsolidatedEvidenceLinking()
    stats = await linker.run_evidence_linking_pipeline(
        parliament_session_id=args.parliament_session_id,
        evidence_types=args.evidence_types,
        party_codes=args.party_codes,
        promise_ranks=args.promise_ranks,
        limit=args.limit,
        min_confidence=args.min_confidence,
        force_reprocessing=args.force_reprocessing,
        dry_run=args.dry_run,
        max_promises_per_evidence=args.max_promises_per_evidence,
        min_similarity=args.min_similarity,
        max_candidates=args.max_candidates
    )
    
    logger.info("Evidence-promise linking pipeline completed successfully!")

if __name__ == "__main__":
    asyncio.run(main()) 