"""
Test Bill Linker for Promise Tracker Pipeline

This script performs a dry run of the hybrid evidence linking process specifically
for evidence items of type 'Bill Event (LEGISinfo)'. It does not write to the
database. Instead, it generates a detailed CSV file with matching results for
analysis and quality tuning.
"""

import logging
import sys
import csv
from datetime import datetime
from typing import Dict, Any, List
from pathlib import Path
import os

# Handle imports for both module execution and testing
try:
    from pipeline.core.base_job import BaseJob
    from pipeline.stages.linking.semantic_evidence_linker import SemanticEvidenceLinker
    from pipeline.stages.linking.llm_evidence_validator import LLMEvidenceValidator, MatchEvaluation
except ImportError:
    pipeline_dir = Path(__file__).resolve().parent.parent.parent
    sys.path.insert(0, str(pipeline_dir))
    sys.path.insert(0, str(pipeline_dir.parent))
    from pipeline.core.base_job import BaseJob
    from pipeline.stages.linking.semantic_evidence_linker import SemanticEvidenceLinker
    from pipeline.stages.linking.llm_evidence_validator import LLMEvidenceValidator, MatchEvaluation

from google.cloud import firestore

class TestBillLinker(BaseJob):
    """A testing version of the EvidenceLinker for dry runs on bill events."""
    
    def __init__(self, config: Dict[str, Any] = None):
        super().__init__("test_bill_linker", config)
        
        # Use production settings for realistic testing
        self.semantic_threshold = self.config.get('semantic_threshold', 0.47)
        self.high_similarity_bypass_threshold = self.config.get('high_similarity_bypass_threshold', 0.50)
        self.llm_validation_threshold = self.config.get('llm_validation_threshold', 0.5)
        self.max_llm_candidates = self.config.get('max_llm_candidates', 5)
        
        # Collections
        self.evidence_collection = self.config.get('evidence_collection', 'evidence_items')
        self.promises_collection = self.config.get('promises_collection', 'promises')
        
        self.semantic_linker = None
        self.llm_validator = None
        
        self._promises_cache = None
        self._promise_embeddings_cache = None

        # Setup output directory
        self.output_dir = Path(__file__).parent.parent.parent / 'debug_output'
        self.output_dir.mkdir(exist_ok=True)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        self.csv_path = self.output_dir / f'bill_linking_analysis_{timestamp}.csv'


    def _execute_job(self, **kwargs) -> Dict[str, Any]:
        parliament_session_id = kwargs.get('parliament_session_id', '45')
        
        self.logger.info("Starting test run for Bill Event linking.")
        self.logger.info(f"Output will be saved to: {self.csv_path}")
        
        self._init_components()
        self._load_promises_cache(parliament_session_id)
        
        if not self._promises_cache:
            self.logger.warning("No promises found. Exiting.")
            return {}

        evidence_items = self._get_bill_evidence_items(parliament_session_id)
        if not evidence_items:
            self.logger.info("No 'Bill Event (LEGISinfo)' evidence items found.")
            return {}
            
        self.logger.info(f"Found {len(evidence_items)} bill events to test against {len(self._promises_cache)} promises.")

        with open(self.csv_path, 'w', newline='', encoding='utf-8') as csvfile:
            fieldnames = [
                'evidence_id', 'evidence_title', 'promise_id', 'promise_text', 
                'match_type', 'semantic_score', 'llm_confidence', 'llm_reasoning', 
                'is_final_match'
            ]
            writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
            writer.writeheader()

            for evidence_item in evidence_items:
                self._process_single_evidence(evidence_item, writer)

        self.logger.info(f"Test run complete. Results saved to {self.csv_path}")
        return {'status': 'complete', 'output_file': str(self.csv_path)}


    def _process_single_evidence(self, evidence_item: Dict[str, Any], writer: csv.DictWriter):
        """Processes one evidence item and writes all potential matches to the CSV."""
        evidence_id = evidence_item.get('_doc_id', 'N/A')
        self.logger.info(f"--- Processing Evidence: {evidence_id} ---")

        evidence_text_for_csv = self.semantic_linker.create_evidence_text(evidence_item)
        evidence_embedding = self.semantic_linker.generate_embeddings([evidence_text_for_csv])
        
        semantic_matches = self.semantic_linker.find_semantic_matches(
            evidence_embedding[0], self._promise_embeddings_cache, self._promises_cache
        )
        
        if not semantic_matches:
            self.logger.debug(f"No semantic matches for {evidence_id}")
            # Optionally write a row indicating no matches
            return

        final_validated_matches = self._hybrid_evidence_linking(evidence_item, semantic_matches)
        final_promise_ids = {match.promise_id for match in final_validated_matches}

        # Write all semantic matches to CSV, annotating which ones were final
        for match in semantic_matches:
            promise_id = match['promise_full']['promise_id']
            is_final = promise_id in final_promise_ids
            
            # Find the corresponding llm_validated_match if it exists
            llm_eval = next((m for m in final_validated_matches if m.promise_id == promise_id), None)

            writer.writerow({
                'evidence_id': evidence_id,
                'evidence_title': evidence_item.get('title_or_summary', 'N/A'),
                'promise_id': promise_id,
                'promise_text': match['promise_full'].get('text', 'N/A'),
                'match_type': 'semantic',
                'semantic_score': f"{match['similarity_score']:.4f}",
                'llm_confidence': f"{llm_eval.confidence_score:.4f}" if llm_eval else 'N/A',
                'llm_reasoning': llm_eval.reasoning if llm_eval else 'N/A',
                'is_final_match': is_final
            })

    def _get_bill_evidence_items(self, parliament_session_id: str) -> List[Dict[str, Any]]:
        """Gets all evidence items of type 'Bill Event (LEGISinfo)' for a session."""
        try:
            query = self.db.collection(self.evidence_collection).where(
                filter=firestore.FieldFilter('parliament_session_id', '==', parliament_session_id)
            ).where(
                filter=firestore.FieldFilter('evidence_source_type', '==', 'Bill Event (LEGISinfo)')
            )
            
            items = []
            for doc in query.stream():
                item_data = doc.to_dict()
                item_data['_doc_id'] = doc.id
                items.append(item_data)
            self.logger.info(f"Found {len(items)} 'Bill Event (LEGISinfo)' items for session {parliament_session_id}")
            return items
        except Exception as e:
            self.logger.error(f"Error querying bill evidence items: {e}")
            return []

    # Simplified hybrid linking for test purposes (doesn't need batch_stats)
    def _hybrid_evidence_linking(self, evidence_item, semantic_matches) -> List[MatchEvaluation]:
        high_similarity_matches = []
        llm_validation_matches = []

        for match in semantic_matches:
            if match['similarity_score'] >= self.high_similarity_bypass_threshold:
                high_similarity_matches.append(match)
            else:
                llm_validation_matches.append(match)
        
        if len(llm_validation_matches) > self.max_llm_candidates:
            llm_validation_matches = sorted(
                llm_validation_matches, key=lambda x: x['similarity_score'], reverse=True
            )[:self.max_llm_candidates]
        
        validated_matches = []
        for match in high_similarity_matches:
            validated_matches.append(self._create_high_confidence_evaluation(match))
        
        if llm_validation_matches:
            llm_validated = self.llm_validator.batch_validate_matches(
                evidence_item, llm_validation_matches, validation_threshold=self.llm_validation_threshold
            )
            validated_matches.extend(llm_validated)
            
        return validated_matches

    # Copied from EvidenceLinker, no changes needed
    def _init_components(self):
        self.logger.info("Initializing linking components for test run.")
        gemini_api_key = os.getenv('GEMINI_API_KEY') or os.getenv('GOOGLE_API_KEY')
        if not gemini_api_key:
            raise EnvironmentError("Missing required environment variable: GEMINI_API_KEY or GOOGLE_API_KEY.")
        self.semantic_linker = SemanticEvidenceLinker(similarity_threshold=self.semantic_threshold, max_links_per_evidence=50)
        self.semantic_linker.initialize()
        self.llm_validator = LLMEvidenceValidator(validation_threshold=self.llm_validation_threshold)
        self.logger.info("Components initialized.")

    def _load_promises_cache(self, parliament_session_id: str):
        self.logger.info(f"Loading promises for parliament session {parliament_session_id}")
        query = self.db.collection(self.promises_collection).where(filter=firestore.FieldFilter('parliament_session_id', '==', parliament_session_id))
        promise_docs = [{'promise_id': doc.id, **doc.to_dict()} for doc in query.stream()]
        if promise_docs:
            promise_texts = [self.semantic_linker.create_promise_text(p) for p in promise_docs]
            self._promise_embeddings_cache = self.semantic_linker.generate_embeddings(promise_texts)
            self._promises_cache = promise_docs
            self.logger.info(f"Cached {len(promise_docs)} promises.")
        else:
            self._promises_cache, self._promise_embeddings_cache = [], None
            self.logger.warning(f"No promises found for session {parliament_session_id}")

    def _create_high_confidence_evaluation(self, semantic_match: Dict[str, Any]) -> MatchEvaluation:
        similarity_score = semantic_match.get('similarity_score', 0.0)
        promise_data = semantic_match.get('promise_full', {})
        if similarity_score >= 0.65: category, confidence = "Direct Implementation", 0.9
        elif similarity_score >= 0.55: category, confidence = "Supporting Action", 0.8
        else: category, confidence = "Related Policy", 0.7
        return MatchEvaluation(
            confidence_score=confidence, reasoning=f"High semantic similarity ({similarity_score:.3f})",
            category=category, promise_id=promise_data.get('promise_id', ''), semantic_similarity_score=similarity_score,
            thematic_alignment=0,department_overlap=False,timeline_relevance="",implementation_type="",semantic_quality_assessment="",progress_indicator=""
        )


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
    
    try:
        from dotenv import load_dotenv
        env_path = Path(__file__).resolve().parent.parent.parent / '.env'
        if env_path.exists():
            load_dotenv(env_path)
            logging.info(f"Loaded environment from: {env_path}")
    except ImportError:
        logging.info("python-dotenv not found, skipping .env load.")

    tester = TestBillLinker()
    tester.execute(parliament_session_id='45') 