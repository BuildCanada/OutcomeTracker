#!/usr/bin/env python3
"""
Backup Production Collections Script

This script creates backups of the current production collections (promises and evidence_items)
before migration. It exports all documents to timestamped backup collections and creates
metadata files documenting the backup process.

Usage:
    python backup_production_collections.py [--dry-run]
"""

import os
import sys
import json
import argparse
from datetime import datetime
from typing import Dict, List, Any

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


class ProductionBackupManager:
    """Manages backup of production Firestore collections."""
    
    def __init__(self):
        """Initialize the backup manager."""
        self.db = self._init_firebase()
        self.timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        
        # Define source and backup collection names
        self.collections_to_backup = {
            'promises': f'promises_backup_{self.timestamp}',
            'evidence_items': f'evidence_items_backup_{self.timestamp}'
        }
        
        self.backup_metadata = {
            'backup_timestamp': self.timestamp,
            'backup_date': datetime.now().isoformat(),
            'collections_backed_up': {},
            'backup_status': 'in_progress'
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
    
    def backup_collection(self, source_collection: str, backup_collection: str, dry_run: bool = False) -> Dict[str, Any]:
        """
        Backup a single collection.
        
        Args:
            source_collection: Name of the source collection
            backup_collection: Name of the backup collection
            dry_run: If True, only simulate the backup
            
        Returns:
            Dictionary with backup results
        """
        print(f"\n{'[DRY RUN] ' if dry_run else ''}Backing up {source_collection} -> {backup_collection}")
        
        backup_result = {
            'source_collection': source_collection,
            'backup_collection': backup_collection,
            'documents_processed': 0,
            'errors': [],
            'status': 'started'
        }
        
        try:
            # Get all documents from source collection
            source_docs = self.db.collection(source_collection).stream()
            
            documents_processed = 0
            batch_size = 100
            current_batch = []
            
            for doc in source_docs:
                if dry_run:
                    documents_processed += 1
                    continue
                
                # Prepare document data
                doc_data = doc.to_dict()
                current_batch.append({
                    'id': doc.id,
                    'data': doc_data
                })
                
                # Process batch when it reaches batch_size
                if len(current_batch) >= batch_size:
                    self._process_batch(backup_collection, current_batch)
                    documents_processed += len(current_batch)
                    current_batch = []
                    print(f"  Processed {documents_processed} documents...")
            
            # Process remaining documents in the last batch
            if current_batch and not dry_run:
                self._process_batch(backup_collection, current_batch)
                documents_processed += len(current_batch)
            
            backup_result['documents_processed'] = documents_processed
            backup_result['status'] = 'completed'
            
            print(f"  ✓ Successfully backed up {documents_processed} documents")
            
        except Exception as e:
            error_msg = f"Error backing up {source_collection}: {str(e)}"
            print(f"  ✗ {error_msg}")
            backup_result['errors'].append(error_msg)
            backup_result['status'] = 'failed'
        
        return backup_result
    
    def _process_batch(self, backup_collection: str, batch: List[Dict[str, Any]]):
        """Process a batch of documents for backup."""
        batch_ref = self.db.batch()
        
        for doc_info in batch:
            doc_ref = self.db.collection(backup_collection).document(doc_info['id'])
            batch_ref.set(doc_ref, doc_info['data'])
        
        batch_ref.commit()
    
    def verify_backup(self, source_collection: str, backup_collection: str) -> bool:
        """
        Verify that backup was successful by comparing document counts.
        
        Args:
            source_collection: Name of the source collection
            backup_collection: Name of the backup collection
            
        Returns:
            True if verification passes, False otherwise
        """
        print(f"\nVerifying backup: {source_collection} -> {backup_collection}")
        
        try:
            source_count = self.count_documents(source_collection)
            backup_count = self.count_documents(backup_collection)
            
            print(f"  Source collection ({source_collection}): {source_count} documents")
            print(f"  Backup collection ({backup_collection}): {backup_count} documents")
            
            if source_count == backup_count:
                print(f"  ✓ Verification passed: Document counts match")
                return True
            else:
                print(f"  ✗ Verification failed: Document counts don't match")
                return False
                
        except Exception as e:
            print(f"  ✗ Verification error: {e}")
            return False
    
    def save_backup_metadata(self, dry_run: bool = False):
        """Save backup metadata to a JSON file."""
        metadata_filename = f"backup_metadata_{self.timestamp}.json"
        metadata_path = os.path.join(
            os.path.dirname(__file__), 
            metadata_filename
        )
        
        if not dry_run:
            try:
                with open(metadata_path, 'w') as f:
                    json.dump(self.backup_metadata, f, indent=2)
                print(f"\n✓ Backup metadata saved to: {metadata_path}")
            except Exception as e:
                print(f"\n✗ Error saving backup metadata: {e}")
        else:
            print(f"\n[DRY RUN] Would save backup metadata to: {metadata_path}")
    
    def run_backup(self, dry_run: bool = False) -> bool:
        """
        Run the complete backup process.
        
        Args:
            dry_run: If True, only simulate the backup
            
        Returns:
            True if all backups successful, False otherwise
        """
        print(f"{'='*60}")
        print(f"{'DRY RUN - ' if dry_run else ''}PRODUCTION COLLECTIONS BACKUP")
        print(f"Timestamp: {self.timestamp}")
        print(f"{'='*60}")
        
        all_successful = True
        
        for source_collection, backup_collection in self.collections_to_backup.items():
            # Check if source collection exists and has documents
            source_count = self.count_documents(source_collection)
            print(f"\nSource collection '{source_collection}' contains {source_count} documents")
            
            if source_count == 0:
                print(f"  ⚠ Warning: Source collection '{source_collection}' is empty")
                self.backup_metadata['collections_backed_up'][source_collection] = {
                    'backup_collection': backup_collection,
                    'documents_processed': 0,
                    'status': 'empty_source',
                    'verified': True
                }
                continue
            
            # Perform backup
            backup_result = self.backup_collection(source_collection, backup_collection, dry_run)
            
            # Verify backup (only if not dry run)
            verified = True
            if not dry_run and backup_result['status'] == 'completed':
                verified = self.verify_backup(source_collection, backup_collection)
            
            # Update metadata
            self.backup_metadata['collections_backed_up'][source_collection] = {
                **backup_result,
                'verified': verified
            }
            
            if backup_result['status'] != 'completed' or not verified:
                all_successful = False
        
        # Update overall backup status
        self.backup_metadata['backup_status'] = 'completed' if all_successful else 'failed'
        
        # Save metadata
        self.save_backup_metadata(dry_run)
        
        # Print summary
        print(f"\n{'='*60}")
        print(f"BACKUP SUMMARY")
        print(f"{'='*60}")
        
        for source_collection, result in self.backup_metadata['collections_backed_up'].items():
            status_icon = "✓" if result['status'] == 'completed' and result['verified'] else "✗"
            print(f"{status_icon} {source_collection}: {result['documents_processed']} documents -> {result['backup_collection']}")
            
            if result.get('errors'):
                for error in result['errors']:
                    print(f"    Error: {error}")
        
        print(f"\nOverall Status: {'SUCCESS' if all_successful else 'FAILED'}")
        
        if not dry_run and all_successful:
            print(f"\n✓ Backup collections created:")
            for backup_collection in self.collections_to_backup.values():
                print(f"  - {backup_collection}")
        
        return all_successful


def main():
    """Main function."""
    parser = argparse.ArgumentParser(description='Backup production Firestore collections')
    parser.add_argument('--dry-run', action='store_true', 
                       help='Simulate the backup without actually creating backup collections')
    
    args = parser.parse_args()
    
    try:
        backup_manager = ProductionBackupManager()
        success = backup_manager.run_backup(dry_run=args.dry_run)
        
        if success:
            print(f"\n🎉 Backup {'simulation' if args.dry_run else 'process'} completed successfully!")
            if not args.dry_run:
                print("You can now proceed with the migration.")
        else:
            print(f"\n❌ Backup {'simulation' if args.dry_run else 'process'} failed!")
            print("Please review the errors above before proceeding.")
            sys.exit(1)
            
    except KeyboardInterrupt:
        print("\n\n⚠ Backup interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ Unexpected error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main() 