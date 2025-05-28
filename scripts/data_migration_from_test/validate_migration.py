#!/usr/bin/env python3
"""
Validate Migration Script

This script validates that the migration from test collections to production collections
was successful by checking data integrity, document counts, and testing key functionality.

Usage:
    python validate_migration.py [--detailed]
"""

import os
import sys
import json
import argparse
from datetime import datetime
from typing import Dict, List, Any, Optional

# Add the parent directory to the path to import common utilities
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

try:
    import firebase_admin
    from firebase_admin import credentials, firestore
    from dotenv import load_dotenv
    
    # Load environment variables
    load_dotenv()
except ImportError as e:
    print(f"Error: Could not import required modules: {e}")
    print("Make sure you have firebase-admin and python-dotenv installed")
    sys.exit(1)


class MigrationValidator:
    """Validates the migration from test collections to production collections."""
    
    def __init__(self):
        """Initialize the validator."""
        self.db = self._init_firebase()
        self.timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        
        # Define collection mappings
        self.collection_mappings = {
            'promises_test': 'promises',
            'evidence_items_test': 'evidence_items'
        }
        
        self.validation_report = {
            'validation_timestamp': self.timestamp,
            'validation_date': datetime.now().isoformat(),
            'collection_validations': {},
            'functional_tests': {},
            'overall_status': 'in_progress',
            'errors': [],
            'warnings': []
        }
    
    def _init_firebase(self):
        """Initialize Firebase connection."""
        if not firebase_admin._apps:
            try:
                firebase_admin.initialize_app()
                project_id = os.getenv('FIREBASE_PROJECT_ID', '[Not Set - Using Default]')
                print(f"Connected to Cloud Firestore (Project: {project_id}) using default credentials.")
            except Exception as e_default:
                print(f"Cloud Firestore init with default creds failed: {e_default}. Attempting service account.")
                cred_path = os.getenv('FIREBASE_SERVICE_ACCOUNT_KEY_PATH')
                if cred_path:
                    try:
                        print(f"Attempting Firebase init with service account key from env var: {cred_path}")
                        cred = credentials.Certificate(cred_path)
                        firebase_admin.initialize_app(cred)
                        project_id_sa = os.getenv('FIREBASE_PROJECT_ID', '[Not Set - Using Service Account]')
                        print(f"Connected to Cloud Firestore (Project: {project_id_sa}) via service account.")
                    except Exception as e_sa:
                        print(f"Firebase init with service account key from {cred_path} failed: {e_sa}")
                        raise
                else:
                    print("FIREBASE_SERVICE_ACCOUNT_KEY_PATH environment variable not set, and default creds failed.")
                    raise e_default
        
        return firestore.client()
    
    def count_documents(self, collection_name: str) -> int:
        """Count documents in a collection."""
        try:
            docs = self.db.collection(collection_name).stream()
            count = sum(1 for _ in docs)
            return count
        except Exception as e:
            print(f"Error counting documents in {collection_name}: {e}")
            return 0
    
    def get_sample_documents(self, collection_name: str, limit: int = 5) -> List[Dict]:
        """Get sample documents from a collection."""
        try:
            docs = self.db.collection(collection_name).limit(limit).stream()
            return [{'id': doc.id, 'data': doc.to_dict()} for doc in docs]
        except Exception as e:
            print(f"Error getting sample documents from {collection_name}: {e}")
            return []
    
    def validate_document_counts(self) -> bool:
        """Validate that document counts match between test and production collections."""
        print(f"\n{'='*60}")
        print("VALIDATING DOCUMENT COUNTS")
        print(f"{'='*60}")
        
        all_valid = True
        
        for test_collection, prod_collection in self.collection_mappings.items():
            print(f"\nValidating: {test_collection} -> {prod_collection}")
            
            test_count = self.count_documents(test_collection)
            prod_count = self.count_documents(prod_collection)
            
            print(f"  Test collection ({test_collection}): {test_count} documents")
            print(f"  Production collection ({prod_collection}): {prod_count} documents")
            
            validation_result = {
                'test_count': test_count,
                'production_count': prod_count,
                'counts_match': test_count == prod_count,
                'status': 'passed' if test_count == prod_count else 'failed'
            }
            
            if test_count == prod_count:
                print(f"  ✓ Document counts match")
            else:
                print(f"  ✗ Document counts don't match!")
                all_valid = False
            
            self.validation_report['collection_validations'][f"{test_collection}_to_{prod_collection}"] = validation_result
        
        return all_valid
    
    def validate_data_integrity(self, detailed: bool = False) -> bool:
        """Validate data integrity by comparing sample documents."""
        print(f"\n{'='*60}")
        print("VALIDATING DATA INTEGRITY")
        print(f"{'='*60}")
        
        all_valid = True
        
        for test_collection, prod_collection in self.collection_mappings.items():
            print(f"\nValidating data integrity: {test_collection} -> {prod_collection}")
            
            # Get sample documents from both collections
            test_samples = self.get_sample_documents(test_collection, 3)
            
            if not test_samples:
                print(f"  ⚠ No sample documents found in {test_collection}")
                continue
            
            integrity_issues = []
            
            for test_doc in test_samples:
                doc_id = test_doc['id']
                
                try:
                    # Get corresponding document from production collection
                    prod_doc_ref = self.db.collection(prod_collection).document(doc_id)
                    prod_doc = prod_doc_ref.get()
                    
                    if not prod_doc.exists:
                        integrity_issues.append(f"Document {doc_id} missing in production collection")
                        continue
                    
                    prod_data = prod_doc.to_dict()
                    test_data = test_doc['data']
                    
                    # Compare key fields
                    key_fields = ['text', 'source_type', 'date_issued'] if 'promises' in test_collection else ['title', 'publication_date', 'source_type']
                    
                    for field in key_fields:
                        if field in test_data and field in prod_data:
                            if test_data[field] != prod_data[field]:
                                integrity_issues.append(f"Document {doc_id}: Field '{field}' mismatch")
                        elif field in test_data or field in prod_data:
                            integrity_issues.append(f"Document {doc_id}: Field '{field}' missing in one collection")
                    
                    if detailed:
                        print(f"  ✓ Document {doc_id}: Key fields match")
                
                except Exception as e:
                    integrity_issues.append(f"Error validating document {doc_id}: {str(e)}")
            
            if integrity_issues:
                print(f"  ✗ Found {len(integrity_issues)} integrity issues:")
                for issue in integrity_issues:
                    print(f"    - {issue}")
                all_valid = False
            else:
                print(f"  ✓ Data integrity validation passed for sample documents")
            
            # Update validation report
            validation_key = f"{test_collection}_to_{prod_collection}_integrity"
            self.validation_report['collection_validations'][validation_key] = {
                'samples_checked': len(test_samples),
                'integrity_issues': integrity_issues,
                'status': 'passed' if not integrity_issues else 'failed'
            }
        
        return all_valid
    
    def test_collection_access(self) -> bool:
        """Test that production collections are accessible and queryable."""
        print(f"\n{'='*60}")
        print("TESTING COLLECTION ACCESS")
        print(f"{'='*60}")
        
        all_accessible = True
        
        for prod_collection in self.collection_mappings.values():
            print(f"\nTesting access to: {prod_collection}")
            
            try:
                # Test basic query
                docs = self.db.collection(prod_collection).limit(1).stream()
                doc_list = list(docs)
                
                if doc_list:
                    print(f"  ✓ Collection {prod_collection} is accessible and contains data")
                    
                    # Test filtering (if applicable)
                    if prod_collection == 'promises':
                        # Test filtering by party_code
                        filtered_docs = self.db.collection(prod_collection).where('party_code', '==', 'LPC').limit(1).stream()
                        filtered_list = list(filtered_docs)
                        if filtered_list:
                            print(f"  ✓ Filtering by party_code works")
                        else:
                            print(f"  ⚠ No LPC documents found (might be expected)")
                    
                    elif prod_collection == 'evidence_items':
                        # Test filtering by source_type
                        filtered_docs = self.db.collection(prod_collection).where('source_type', '==', 'News Release').limit(1).stream()
                        filtered_list = list(filtered_docs)
                        if filtered_list:
                            print(f"  ✓ Filtering by source_type works")
                        else:
                            print(f"  ⚠ No News Release documents found (might be expected)")
                
                else:
                    print(f"  ⚠ Collection {prod_collection} is accessible but empty")
                
                self.validation_report['functional_tests'][f"{prod_collection}_access"] = {
                    'accessible': True,
                    'has_data': len(doc_list) > 0,
                    'status': 'passed'
                }
                
            except Exception as e:
                print(f"  ✗ Error accessing collection {prod_collection}: {e}")
                all_accessible = False
                
                self.validation_report['functional_tests'][f"{prod_collection}_access"] = {
                    'accessible': False,
                    'error': str(e),
                    'status': 'failed'
                }
        
        return all_accessible
    
    def check_backup_collections(self) -> bool:
        """Check that backup collections exist."""
        print(f"\n{'='*60}")
        print("CHECKING BACKUP COLLECTIONS")
        print(f"{'='*60}")
        
        # Look for backup collections created today
        today = datetime.now().strftime("%Y%m%d")
        backup_patterns = [f'promises_backup_{today}', f'evidence_items_backup_{today}']
        
        existing_backups = []
        try:
            collections = self.db.collections()
            collection_names = [col.id for col in collections]
            
            for pattern in backup_patterns:
                matching_backups = [name for name in collection_names if name.startswith(pattern)]
                existing_backups.extend(matching_backups)
            
            if existing_backups:
                print(f"  ✓ Found backup collections: {existing_backups}")
                
                # Verify backup collections have data
                for backup_collection in existing_backups:
                    count = self.count_documents(backup_collection)
                    print(f"    - {backup_collection}: {count} documents")
                
                self.validation_report['functional_tests']['backup_collections'] = {
                    'found': True,
                    'collections': existing_backups,
                    'status': 'passed'
                }
                return True
            else:
                print(f"  ⚠ No backup collections found with today's date ({today})")
                self.validation_report['warnings'].append(f"No backup collections found for {today}")
                
                self.validation_report['functional_tests']['backup_collections'] = {
                    'found': False,
                    'status': 'warning'
                }
                return True  # Not a failure, just a warning
                
        except Exception as e:
            print(f"  ✗ Error checking for backup collections: {e}")
            self.validation_report['errors'].append(f"Error checking backup collections: {e}")
            
            self.validation_report['functional_tests']['backup_collections'] = {
                'found': False,
                'error': str(e),
                'status': 'failed'
            }
            return False
    
    def save_validation_report(self):
        """Save the validation report to a JSON file."""
        report_filename = f"validation_report_{self.timestamp}.json"
        report_path = os.path.join(
            os.path.dirname(__file__), 
            report_filename
        )
        
        try:
            with open(report_path, 'w') as f:
                json.dump(self.validation_report, f, indent=2)
            print(f"\n✓ Validation report saved to: {report_path}")
        except Exception as e:
            print(f"\n✗ Error saving validation report: {e}")
    
    def run_validation(self, detailed: bool = False) -> bool:
        """
        Run the complete validation process.
        
        Args:
            detailed: If True, provide detailed output
            
        Returns:
            True if all validations pass, False otherwise
        """
        print(f"{'='*60}")
        print("MIGRATION VALIDATION")
        print(f"Timestamp: {self.timestamp}")
        print(f"{'='*60}")
        
        # Run all validation tests
        tests = [
            ("Document Counts", self.validate_document_counts),
            ("Data Integrity", lambda: self.validate_data_integrity(detailed)),
            ("Collection Access", self.test_collection_access),
            ("Backup Collections", self.check_backup_collections)
        ]
        
        all_passed = True
        
        for test_name, test_func in tests:
            try:
                result = test_func()
                if not result:
                    all_passed = False
            except Exception as e:
                print(f"\n✗ Error in {test_name} validation: {e}")
                self.validation_report['errors'].append(f"{test_name} validation error: {e}")
                all_passed = False
        
        # Update overall status
        if all_passed and not self.validation_report['errors']:
            self.validation_report['overall_status'] = 'passed'
        elif self.validation_report['warnings'] and not self.validation_report['errors']:
            self.validation_report['overall_status'] = 'passed_with_warnings'
        else:
            self.validation_report['overall_status'] = 'failed'
        
        # Save report
        self.save_validation_report()
        
        # Print summary
        print(f"\n{'='*60}")
        print("VALIDATION SUMMARY")
        print(f"{'='*60}")
        
        if self.validation_report['overall_status'] == 'passed':
            print("✓ All validations passed successfully!")
            print("Migration appears to be successful.")
        elif self.validation_report['overall_status'] == 'passed_with_warnings':
            print("⚠ Validations passed with warnings:")
            for warning in self.validation_report['warnings']:
                print(f"  - {warning}")
        else:
            print("✗ Validation failed!")
            if self.validation_report['errors']:
                print("Errors encountered:")
                for error in self.validation_report['errors']:
                    print(f"  - {error}")
        
        return all_passed


def main():
    """Main function."""
    parser = argparse.ArgumentParser(description='Validate migration from test to production collections')
    parser.add_argument('--detailed', action='store_true', 
                       help='Provide detailed validation output')
    
    args = parser.parse_args()
    
    try:
        validator = MigrationValidator()
        success = validator.run_validation(detailed=args.detailed)
        
        if success:
            print(f"\n🎉 Migration validation completed successfully!")
            print("Production collections are ready for use.")
        else:
            print(f"\n❌ Migration validation failed!")
            print("Please review the errors above and check the migration.")
            sys.exit(1)
            
    except KeyboardInterrupt:
        print("\n\n⚠ Validation interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ Unexpected error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main() 