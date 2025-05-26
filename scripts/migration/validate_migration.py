#!/usr/bin/env python3
"""
Validation script for promises collection flattening migration.
Verifies data integrity and migration success.
"""

import firebase_admin
from firebase_admin import firestore
import os
import logging
import sys
import argparse
from datetime import datetime
from typing import Dict, List, Set
from dotenv import load_dotenv
from pathlib import Path

# Add parent directory to path for imports
sys.path.append(str(Path(__file__).parent.parent))
from common_utils import TARGET_PROMISES_COLLECTION_ROOT, DEFAULT_REGION_CODE, PARTY_NAME_TO_CODE_MAPPING

# Derive known party codes from the mapping
KNOWN_PARTY_CODES = list(set(PARTY_NAME_TO_CODE_MAPPING.values()))

# Load environment variables
load_dotenv()

# Logger setup
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(filename)s:%(lineno)d - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)

class MigrationValidator:
    """Validates the promises collection migration results."""
    
    def __init__(self, db: firestore.Client):
        self.db = db
        self.validation_results = {
            'total_legacy_docs': 0,
            'total_flat_docs': 0,
            'migrated_docs': 0,
            'missing_docs': [],
            'data_mismatches': [],
            'field_validation_errors': [],
            'reference_validation_errors': [],
            'start_time': None,
            'end_time': None,
            'validation_passed': False
        }
    
    def get_legacy_document_count(self, region_code: str = DEFAULT_REGION_CODE) -> Dict[str, int]:
        """Count documents in the legacy subcollection structure."""
        logger.info("Counting documents in legacy subcollection structure...")
        
        party_counts = {}
        total_count = 0
        
        for party_code in KNOWN_PARTY_CODES:
            try:
                legacy_collection_path = f"{TARGET_PROMISES_COLLECTION_ROOT}/{region_code}/{party_code}"
                legacy_docs = list(self.db.collection(legacy_collection_path).select([]).stream())
                count = len(legacy_docs)
                party_counts[party_code] = count
                total_count += count
                logger.info(f"Legacy collection {legacy_collection_path}: {count} documents")
            except Exception as e:
                logger.error(f"Error counting legacy documents for {party_code}: {e}")
                party_counts[party_code] = -1  # Indicate error
        
        party_counts['total'] = total_count
        self.validation_results['total_legacy_docs'] = total_count
        return party_counts
    
    def get_flat_document_count(self) -> int:
        """Count documents in the flat promises collection."""
        logger.info("Counting documents in flat promises collection...")
        
        try:
            flat_docs = list(self.db.collection(TARGET_PROMISES_COLLECTION_ROOT).select([]).stream())
            count = len(flat_docs)
            logger.info(f"Flat collection {TARGET_PROMISES_COLLECTION_ROOT}: {count} documents")
            self.validation_results['total_flat_docs'] = count
            return count
        except Exception as e:
            logger.error(f"Error counting flat documents: {e}")
            return -1
    
    def get_migrated_document_count(self) -> int:
        """Count documents with migration metadata in the flat collection."""
        logger.info("Counting migrated documents (with migration metadata)...")
        
        try:
            migrated_query = self.db.collection(TARGET_PROMISES_COLLECTION_ROOT).where(
                'migration_metadata.migration_version', '==', '1.0'
            )
            migrated_docs = list(migrated_query.select([]).stream())
            count = len(migrated_docs)
            logger.info(f"Documents with migration metadata: {count}")
            self.validation_results['migrated_docs'] = count
            return count
        except Exception as e:
            logger.error(f"Error counting migrated documents: {e}")
            return -1
    
    def validate_document_data_integrity(self, sample_size: int = 50) -> List[Dict]:
        """Validate data integrity by comparing legacy and flat documents."""
        logger.info(f"Validating data integrity (sample size: {sample_size})...")
        
        data_mismatches = []
        validated_count = 0
        
        try:
            for party_code in KNOWN_PARTY_CODES:
                if validated_count >= sample_size:
                    break
                
                legacy_collection_path = f"{TARGET_PROMISES_COLLECTION_ROOT}/{DEFAULT_REGION_CODE}/{party_code}"
                legacy_docs = self.db.collection(legacy_collection_path).limit(sample_size // len(KNOWN_PARTY_CODES)).stream()
                
                for legacy_doc in legacy_docs:
                    if validated_count >= sample_size:
                        break
                    
                    legacy_data = legacy_doc.to_dict()
                    legacy_id = legacy_doc.id
                    
                    # Try to find corresponding document in flat collection
                    flat_doc_candidates = list(self.db.collection(TARGET_PROMISES_COLLECTION_ROOT)
                                            .where('migration_metadata.original_id', '==', legacy_id)
                                            .where('party_code', '==', party_code).stream())
                    
                    if not flat_doc_candidates:
                        data_mismatches.append({
                            'type': 'missing_flat_doc',
                            'legacy_id': legacy_id,
                            'party_code': party_code,
                            'message': f"No corresponding flat document found for legacy ID {legacy_id}"
                        })
                        continue
                    
                    if len(flat_doc_candidates) > 1:
                        data_mismatches.append({
                            'type': 'duplicate_flat_docs',
                            'legacy_id': legacy_id,
                            'party_code': party_code,
                            'flat_ids': [doc.id for doc in flat_doc_candidates],
                            'message': f"Multiple flat documents found for legacy ID {legacy_id}"
                        })
                        continue
                    
                    flat_doc = flat_doc_candidates[0]
                    flat_data = flat_doc.to_dict()
                    
                    # Validate core fields match
                    core_fields = ['text', 'responsible_department_lead', 'parliament_session_id', 
                                 'date_issued', 'source_type', 'bc_promise_rank']
                    
                    for field in core_fields:
                        legacy_value = legacy_data.get(field)
                        flat_value = flat_data.get(field)
                        
                        if legacy_value != flat_value:
                            data_mismatches.append({
                                'type': 'field_mismatch',
                                'legacy_id': legacy_id,
                                'flat_id': flat_doc.id,
                                'field': field,
                                'legacy_value': legacy_value,
                                'flat_value': flat_value,
                                'message': f"Field '{field}' mismatch between legacy and flat document"
                            })
                    
                    # Validate new flat structure fields are present
                    required_flat_fields = ['region_code', 'party_code', 'migration_metadata']
                    for field in required_flat_fields:
                        if field not in flat_data:
                            data_mismatches.append({
                                'type': 'missing_flat_field',
                                'flat_id': flat_doc.id,
                                'field': field,
                                'message': f"Required flat structure field '{field}' missing"
                            })
                    
                    validated_count += 1
                    
                    if validated_count % 10 == 0:
                        logger.info(f"Validated {validated_count} documents...")
        
        except Exception as e:
            logger.error(f"Error during data integrity validation: {e}")
            data_mismatches.append({
                'type': 'validation_error',
                'message': f"Validation process error: {e}"
            })
        
        self.validation_results['data_mismatches'] = data_mismatches
        logger.info(f"Data integrity validation completed. Found {len(data_mismatches)} issues.")
        return data_mismatches
    
    def validate_required_fields(self) -> List[Dict]:
        """Validate that all flat documents have required fields."""
        logger.info("Validating required fields in flat documents...")
        
        field_errors = []
        required_fields = {
            'text': str,
            'region_code': str,
            'party_code': str,
            'migration_metadata': dict,
            'responsible_department_lead': str,
            'parliament_session_id': str
        }
        
        try:
            flat_docs = self.db.collection(TARGET_PROMISES_COLLECTION_ROOT).stream()
            doc_count = 0
            
            for doc in flat_docs:
                doc_data = doc.to_dict()
                doc_count += 1
                
                for field, expected_type in required_fields.items():
                    if field not in doc_data:
                        field_errors.append({
                            'type': 'missing_field',
                            'document_id': doc.id,
                            'field': field,
                            'message': f"Required field '{field}' missing"
                        })
                    elif doc_data[field] is not None and not isinstance(doc_data[field], expected_type):
                        field_errors.append({
                            'type': 'wrong_field_type',
                            'document_id': doc.id,
                            'field': field,
                            'expected_type': expected_type.__name__,
                            'actual_type': type(doc_data[field]).__name__,
                            'message': f"Field '{field}' has wrong type"
                        })
                
                if doc_count % 100 == 0:
                    logger.info(f"Validated fields for {doc_count} documents...")
            
            logger.info(f"Field validation completed for {doc_count} documents.")
        
        except Exception as e:
            logger.error(f"Error during field validation: {e}")
            field_errors.append({
                'type': 'validation_error',
                'message': f"Field validation error: {e}"
            })
        
        self.validation_results['field_validation_errors'] = field_errors
        return field_errors
    
    def validate_evidence_references(self) -> List[Dict]:
        """Validate that evidence items reference the correct promise IDs after migration."""
        logger.info("Validating evidence item references...")
        
        reference_errors = []
        
        try:
            # Get all evidence items
            evidence_docs = self.db.collection('evidence_items').stream()
            
            for evidence_doc in evidence_docs:
                evidence_data = evidence_doc.to_dict()
                linked_promise_ids = evidence_data.get('linked_promise_ids', [])
                
                if not linked_promise_ids:
                    continue
                
                # Check if referenced promise IDs exist in flat collection
                for promise_id in linked_promise_ids:
                    try:
                        promise_doc = self.db.collection(TARGET_PROMISES_COLLECTION_ROOT).document(promise_id).get()
                        if not promise_doc.exists:
                            reference_errors.append({
                                'type': 'broken_promise_reference',
                                'evidence_id': evidence_doc.id,
                                'promise_id': promise_id,
                                'message': f"Evidence item references non-existent promise ID {promise_id}"
                            })
                    except Exception as e:
                        reference_errors.append({
                            'type': 'promise_lookup_error',
                            'evidence_id': evidence_doc.id,
                            'promise_id': promise_id,
                            'error': str(e),
                            'message': f"Error looking up promise ID {promise_id}"
                        })
        
        except Exception as e:
            logger.error(f"Error during evidence reference validation: {e}")
            reference_errors.append({
                'type': 'validation_error',
                'message': f"Evidence reference validation error: {e}"
            })
        
        self.validation_results['reference_validation_errors'] = reference_errors
        logger.info(f"Evidence reference validation completed. Found {len(reference_errors)} issues.")
        return reference_errors
    
    def validate_query_performance(self) -> Dict:
        """Test query performance on the flat structure."""
        logger.info("Testing query performance on flat structure...")
        
        performance_results = {}
        
        try:
            # Test basic party query
            start_time = datetime.now()
            party_query = self.db.collection(TARGET_PROMISES_COLLECTION_ROOT).where('party_code', '==', 'LPC').limit(10)
            list(party_query.stream())
            party_query_time = (datetime.now() - start_time).total_seconds()
            performance_results['party_query_time'] = party_query_time
            
            # Test department query
            start_time = datetime.now()
            dept_query = self.db.collection(TARGET_PROMISES_COLLECTION_ROOT).where(
                'responsible_department_lead', '==', 'Finance Canada'
            ).limit(10)
            list(dept_query.stream())
            dept_query_time = (datetime.now() - start_time).total_seconds()
            performance_results['department_query_time'] = dept_query_time
            
            # Test combined query
            start_time = datetime.now()
            combined_query = self.db.collection(TARGET_PROMISES_COLLECTION_ROOT).where(
                'party_code', '==', 'LPC'
            ).where(
                'region_code', '==', 'Canada'
            ).where(
                'parliament_session_id', '==', '44-1'
            ).limit(10)
            list(combined_query.stream())
            combined_query_time = (datetime.now() - start_time).total_seconds()
            performance_results['combined_query_time'] = combined_query_time
            
            logger.info(f"Query performance: party={party_query_time:.3f}s, department={dept_query_time:.3f}s, combined={combined_query_time:.3f}s")
            
        except Exception as e:
            logger.error(f"Error during performance testing: {e}")
            performance_results['error'] = str(e)
        
        return performance_results
    
    def run_full_validation(self, sample_size: int = 50) -> bool:
        """Run complete validation suite."""
        logger.info("Starting comprehensive migration validation...")
        self.validation_results['start_time'] = datetime.now()
        
        try:
            # 1. Count validation
            logger.info("=== STEP 1: Document Count Validation ===")
            legacy_counts = self.get_legacy_document_count()
            flat_count = self.get_flat_document_count()
            migrated_count = self.get_migrated_document_count()
            
            count_validation_passed = (
                legacy_counts['total'] > 0 and
                flat_count >= legacy_counts['total'] and
                migrated_count > 0
            )
            
            # 2. Data integrity validation
            logger.info("=== STEP 2: Data Integrity Validation ===")
            data_mismatches = self.validate_document_data_integrity(sample_size)
            data_integrity_passed = len(data_mismatches) == 0
            
            # 3. Field validation
            logger.info("=== STEP 3: Required Fields Validation ===")
            field_errors = self.validate_required_fields()
            field_validation_passed = len(field_errors) == 0
            
            # 4. Reference validation
            logger.info("=== STEP 4: Evidence Reference Validation ===")
            reference_errors = self.validate_evidence_references()
            reference_validation_passed = len(reference_errors) == 0
            
            # 5. Performance validation
            logger.info("=== STEP 5: Query Performance Testing ===")
            performance_results = self.validate_query_performance()
            performance_validation_passed = 'error' not in performance_results
            
            # Overall validation result
            overall_passed = (
                count_validation_passed and
                data_integrity_passed and
                field_validation_passed and
                reference_validation_passed and
                performance_validation_passed
            )
            
            self.validation_results['validation_passed'] = overall_passed
            self.validation_results['end_time'] = datetime.now()
            
            # Print summary
            self._print_validation_summary(legacy_counts, flat_count, migrated_count, performance_results)
            
            return overall_passed
            
        except Exception as e:
            logger.critical(f"Validation failed with critical error: {e}", exc_info=True)
            self.validation_results['validation_passed'] = False
            self.validation_results['critical_error'] = str(e)
            return False
    
    def _print_validation_summary(self, legacy_counts: Dict, flat_count: int, migrated_count: int, performance_results: Dict):
        """Print comprehensive validation summary."""
        duration = self.validation_results['end_time'] - self.validation_results['start_time']
        
        logger.info("=" * 80)
        logger.info("MIGRATION VALIDATION SUMMARY")
        logger.info("=" * 80)
        logger.info(f"Validation duration: {duration.total_seconds():.2f} seconds")
        logger.info(f"Overall validation status: {'✅ PASSED' if self.validation_results['validation_passed'] else '❌ FAILED'}")
        
        logger.info("\n--- Document Counts ---")
        logger.info(f"Legacy documents (total): {legacy_counts.get('total', 0)}")
        for party, count in legacy_counts.items():
            if party != 'total':
                logger.info(f"  {party}: {count}")
        logger.info(f"Flat collection documents: {flat_count}")
        logger.info(f"Migrated documents (with metadata): {migrated_count}")
        
        logger.info("\n--- Data Integrity ---")
        data_mismatches = len(self.validation_results['data_mismatches'])
        logger.info(f"Data mismatches found: {data_mismatches}")
        if data_mismatches > 0:
            for mismatch in self.validation_results['data_mismatches'][:5]:  # Show first 5
                logger.warning(f"  {mismatch['type']}: {mismatch['message']}")
            if data_mismatches > 5:
                logger.warning(f"  ... and {data_mismatches - 5} more")
        
        logger.info("\n--- Field Validation ---")
        field_errors = len(self.validation_results['field_validation_errors'])
        logger.info(f"Field validation errors: {field_errors}")
        if field_errors > 0:
            for error in self.validation_results['field_validation_errors'][:3]:  # Show first 3
                logger.warning(f"  {error['type']}: {error['message']}")
            if field_errors > 3:
                logger.warning(f"  ... and {field_errors - 3} more")
        
        logger.info("\n--- Reference Validation ---")
        reference_errors = len(self.validation_results['reference_validation_errors'])
        logger.info(f"Reference validation errors: {reference_errors}")
        if reference_errors > 0:
            for error in self.validation_results['reference_validation_errors'][:3]:  # Show first 3
                logger.warning(f"  {error['type']}: {error['message']}")
            if reference_errors > 3:
                logger.warning(f"  ... and {reference_errors - 3} more")
        
        logger.info("\n--- Query Performance ---")
        if 'error' not in performance_results:
            logger.info(f"Party query time: {performance_results.get('party_query_time', 0):.3f}s")
            logger.info(f"Department query time: {performance_results.get('department_query_time', 0):.3f}s")
            logger.info(f"Combined query time: {performance_results.get('combined_query_time', 0):.3f}s")
        else:
            logger.warning(f"Performance test error: {performance_results['error']}")
        
        if not self.validation_results['validation_passed']:
            logger.warning("\n⚠️  VALIDATION FAILED - Review errors above before using the migrated data")
        else:
            logger.info("\n✅ VALIDATION PASSED - Migration appears successful!")

def initialize_firestore():
    """Initialize Firebase Admin SDK and return Firestore client."""
    if not firebase_admin._apps:
        try:
            firebase_admin.initialize_app()
            project_id = os.getenv('FIREBASE_PROJECT_ID', '[Not Set - Using Default]')
            logger.info(f"Connected to CLOUD Firestore (Project: {project_id}) using default credentials.")
            return firestore.client()
        except Exception as e_default:
            logger.warning(f"Cloud Firestore init with default creds failed: {e_default}")
            cred_path = os.getenv('FIREBASE_SERVICE_ACCOUNT_KEY_PATH')
            if cred_path:
                try:
                    logger.info(f"Attempting Firebase init with service account key: {cred_path}")
                    cred = firebase_admin.credentials.Certificate(cred_path)
                    firebase_admin.initialize_app(cred)
                    project_id_sa = os.getenv('FIREBASE_PROJECT_ID', '[Not Set - Using Service Account]')
                    logger.info(f"Connected to CLOUD Firestore (Project: {project_id_sa}) via service account.")
                    return firestore.client()
                except Exception as e_sa:
                    logger.critical(f"Firebase init with service account key failed: {e_sa}", exc_info=True)
                    raise
            else:
                logger.error("FIREBASE_SERVICE_ACCOUNT_KEY_PATH not set and default creds failed.")
                raise
    else:
        logger.info("Firebase Admin SDK already initialized. Getting Firestore client.")
        return firestore.client()

def main():
    """Main validation execution function."""
    parser = argparse.ArgumentParser(description='Validate promises collection migration')
    parser.add_argument('--sample-size', type=int, default=50, help='Sample size for data integrity validation')
    
    args = parser.parse_args()
    
    try:
        # Initialize Firestore
        db = initialize_firestore()
        
        # Create validator
        validator = MigrationValidator(db)
        
        # Run validation
        success = validator.run_full_validation(sample_size=args.sample_size)
        
        return success
        
    except Exception as e:
        logger.critical(f"Validation failed: {e}", exc_info=True)
        return False

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1) 