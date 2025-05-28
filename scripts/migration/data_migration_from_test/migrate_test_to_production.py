#!/usr/bin/env python3
"""
Migrate Test to Production Collections Script

This script migrates data from test collections (promises_test, evidence_items_test) 
to production collections (promises, evidence_items). It clears the production 
collections first, then copies all data from test collections.

Usage:
    python migrate_test_to_production.py [--dry-run] [--skip-backup-check]
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


class TestToProductionMigrator:
    """Manages migration from test collections to production collections."""
    
    def __init__(self):
        """Initialize the migrator."""
        self.db = self._init_firebase()
        self.timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        
        # Define source and target collection mappings
        self.migration_mappings = {
            'promises_test': 'promises',
            'evidence_items_test': 'evidence_items'
        }
        
        self.migration_metadata = {
            'migration_timestamp': self.timestamp,
            'migration_date': datetime.now().isoformat(),
            'collections_migrated': {},
            'migration_status': 'in_progress'
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
    
    def check_backup_exists(self) -> bool:
        """Check if recent backup collections exist."""
        print("\nChecking for recent backup collections...")
        
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
                print(f"  ✓ Found recent backup collections: {existing_backups}")
                return True
            else:
                print(f"  ⚠ No backup collections found with today's date ({today})")
                return False
                
        except Exception as e:
            print(f"  ✗ Error checking for backup collections: {e}")
            return False
    
    def clear_collection(self, collection_name: str, dry_run: bool = False) -> Dict[str, Any]:
        """
        Clear all documents from a collection.
        
        Args:
            collection_name: Name of the collection to clear
            dry_run: If True, only simulate the clearing
            
        Returns:
            Dictionary with clearing results
        """
        print(f"\n{'[DRY RUN] ' if dry_run else ''}Clearing collection: {collection_name}")
        
        clear_result = {
            'collection': collection_name,
            'documents_deleted': 0,
            'errors': [],
            'status': 'started'
        }
        
        try:
            # Get all documents in the collection
            docs = self.db.collection(collection_name).stream()
            
            documents_deleted = 0
            batch_size = 100
            current_batch = []
            
            for doc in docs:
                if dry_run:
                    documents_deleted += 1
                    continue
                
                current_batch.append(doc.reference)
                
                # Process batch when it reaches batch_size
                if len(current_batch) >= batch_size:
                    self._delete_batch(current_batch)
                    documents_deleted += len(current_batch)
                    current_batch = []
                    print(f"  Deleted {documents_deleted} documents...")
            
            # Process remaining documents in the last batch
            if current_batch and not dry_run:
                self._delete_batch(current_batch)
                documents_deleted += len(current_batch)
            
            clear_result['documents_deleted'] = documents_deleted
            clear_result['status'] = 'completed'
            
            print(f"  ✓ Successfully {'would delete' if dry_run else 'deleted'} {documents_deleted} documents")
            
        except Exception as e:
            error_msg = f"Error clearing {collection_name}: {str(e)}"
            print(f"  ✗ {error_msg}")
            clear_result['errors'].append(error_msg)
            clear_result['status'] = 'failed'
        
        return clear_result
    
    def _delete_batch(self, doc_refs: List):
        """Delete a batch of document references."""
        batch = self.db.batch()
        for doc_ref in doc_refs:
            batch.delete(doc_ref)
        batch.commit()
    
    def copy_collection(self, source_collection: str, target_collection: str, dry_run: bool = False) -> Dict[str, Any]:
        """
        Copy all documents from source collection to target collection.
        
        Args:
            source_collection: Name of the source collection
            target_collection: Name of the target collection
            dry_run: If True, only simulate the copy
            
        Returns:
            Dictionary with copy results
        """
        print(f"\n{'[DRY RUN] ' if dry_run else ''}Copying {source_collection} -> {target_collection}")
        
        copy_result = {
            'source_collection': source_collection,
            'target_collection': target_collection,
            'documents_copied': 0,
            'errors': [],
            'status': 'started'
        }
        
        try:
            # Get all documents from source collection
            source_docs = self.db.collection(source_collection).stream()
            
            documents_copied = 0
            batch_size = 100
            current_batch = []
            
            for doc in source_docs:
                if dry_run:
                    documents_copied += 1
                    continue
                
                # Prepare document data
                doc_data = doc.to_dict()
                current_batch.append({
                    'id': doc.id,
                    'data': doc_data
                })
                
                # Process batch when it reaches batch_size
                if len(current_batch) >= batch_size:
                    self._copy_batch(target_collection, current_batch)
                    documents_copied += len(current_batch)
                    current_batch = []
                    print(f"  Copied {documents_copied} documents...")
            
            # Process remaining documents in the last batch
            if current_batch and not dry_run:
                self._copy_batch(target_collection, current_batch)
                documents_copied += len(current_batch)
            
            copy_result['documents_copied'] = documents_copied
            copy_result['status'] = 'completed'
            
            print(f"  ✓ Successfully {'would copy' if dry_run else 'copied'} {documents_copied} documents")
            
        except Exception as e:
            error_msg = f"Error copying {source_collection} to {target_collection}: {str(e)}"
            print(f"  ✗ {error_msg}")
            copy_result['errors'].append(error_msg)
            copy_result['status'] = 'failed'
        
        return copy_result
    
    def _copy_batch(self, target_collection: str, batch: List[Dict[str, Any]]):
        """Copy a batch of documents to target collection."""
        batch_ref = self.db.batch()
        
        for doc_info in batch:
            doc_ref = self.db.collection(target_collection).document(doc_info['id'])
            batch_ref.set(doc_ref, doc_info['data'])
        
        batch_ref.commit()
    
    def verify_migration(self, source_collection: str, target_collection: str) -> bool:
        """
        Verify that migration was successful by comparing document counts.
        
        Args:
            source_collection: Name of the source collection
            target_collection: Name of the target collection
            
        Returns:
            True if verification passes, False otherwise
        """
        print(f"\nVerifying migration: {source_collection} -> {target_collection}")
        
        try:
            source_count = self.count_documents(source_collection)
            target_count = self.count_documents(target_collection)
            
            print(f"  Source collection ({source_collection}): {source_count} documents")
            print(f"  Target collection ({target_collection}): {target_count} documents")
            
            if source_count == target_count:
                print(f"  ✓ Verification passed: Document counts match")
                return True
            else:
                print(f"  ✗ Verification failed: Document counts don't match")
                return False
                
        except Exception as e:
            print(f"  ✗ Verification error: {e}")
            return False
    
    def save_migration_metadata(self, dry_run: bool = False):
        """Save migration metadata to a JSON file."""
        metadata_filename = f"migration_metadata_{self.timestamp}.json"
        metadata_path = os.path.join(
            os.path.dirname(__file__), 
            metadata_filename
        )
        
        if not dry_run:
            try:
                with open(metadata_path, 'w') as f:
                    json.dump(self.migration_metadata, f, indent=2)
                print(f"\n✓ Migration metadata saved to: {metadata_path}")
            except Exception as e:
                print(f"\n✗ Error saving migration metadata: {e}")
        else:
            print(f"\n[DRY RUN] Would save migration metadata to: {metadata_path}")
    
    def run_migration(self, dry_run: bool = False, skip_backup_check: bool = False) -> bool:
        """
        Run the complete migration process.
        
        Args:
            dry_run: If True, only simulate the migration
            skip_backup_check: If True, skip checking for backup collections
            
        Returns:
            True if all migrations successful, False otherwise
        """
        print(f"{'='*60}")
        print(f"{'DRY RUN - ' if dry_run else ''}TEST TO PRODUCTION MIGRATION")
        print(f"Timestamp: {self.timestamp}")
        print(f"{'='*60}")
        
        # Check for backups unless skipped
        if not skip_backup_check and not dry_run:
            if not self.check_backup_exists():
                print("\n❌ No recent backup collections found!")
                print("Please run backup_production_collections.py first to create backups.")
                print("Or use --skip-backup-check to proceed without backup verification.")
                return False
        
        all_successful = True
        
        for source_collection, target_collection in self.migration_mappings.items():
            # Check source collection
            source_count = self.count_documents(source_collection)
            target_count = self.count_documents(target_collection)
            
            print(f"\nMigration: {source_collection} ({source_count} docs) -> {target_collection} ({target_count} docs)")
            
            if source_count == 0:
                print(f"  ⚠ Warning: Source collection '{source_collection}' is empty")
                self.migration_metadata['collections_migrated'][source_collection] = {
                    'target_collection': target_collection,
                    'documents_copied': 0,
                    'status': 'empty_source',
                    'verified': True
                }
                continue
            
            # Step 1: Clear target collection
            clear_result = self.clear_collection(target_collection, dry_run)
            
            # Step 2: Copy from source to target
            copy_result = self.copy_collection(source_collection, target_collection, dry_run)
            
            # Step 3: Verify migration (only if not dry run)
            verified = True
            if not dry_run and copy_result['status'] == 'completed':
                verified = self.verify_migration(source_collection, target_collection)
            
            # Update metadata
            self.migration_metadata['collections_migrated'][source_collection] = {
                'target_collection': target_collection,
                'clear_result': clear_result,
                'copy_result': copy_result,
                'verified': verified
            }
            
            if clear_result['status'] != 'completed' or copy_result['status'] != 'completed' or not verified:
                all_successful = False
        
        # Update overall migration status
        self.migration_metadata['migration_status'] = 'completed' if all_successful else 'failed'
        
        # Save metadata
        self.save_migration_metadata(dry_run)
        
        # Print summary
        print(f"\n{'='*60}")
        print(f"MIGRATION SUMMARY")
        print(f"{'='*60}")
        
        for source_collection, result in self.migration_metadata['collections_migrated'].items():
            if result.get('copy_result'):
                docs_copied = result['copy_result']['documents_copied']
            else:
                docs_copied = result.get('documents_copied', 0)
            
            status_icon = "✓" if result.get('verified', False) else "✗"
            print(f"{status_icon} {source_collection}: {docs_copied} documents -> {result['target_collection']}")
            
            # Show any errors
            if result.get('clear_result', {}).get('errors'):
                for error in result['clear_result']['errors']:
                    print(f"    Clear Error: {error}")
            if result.get('copy_result', {}).get('errors'):
                for error in result['copy_result']['errors']:
                    print(f"    Copy Error: {error}")
        
        print(f"\nOverall Status: {'SUCCESS' if all_successful else 'FAILED'}")
        
        if not dry_run and all_successful:
            print(f"\n✓ Migration completed successfully!")
            print("Production collections now contain the data from test collections.")
            print("Next step: Update script collection references using update_collection_references.py")
        
        return all_successful


def main():
    """Main function."""
    parser = argparse.ArgumentParser(description='Migrate test collections to production collections')
    parser.add_argument('--dry-run', action='store_true', 
                       help='Simulate the migration without actually modifying collections')
    parser.add_argument('--skip-backup-check', action='store_true',
                       help='Skip checking for backup collections (not recommended)')
    
    args = parser.parse_args()
    
    try:
        migrator = TestToProductionMigrator()
        success = migrator.run_migration(dry_run=args.dry_run, skip_backup_check=args.skip_backup_check)
        
        if success:
            print(f"\n🎉 Migration {'simulation' if args.dry_run else 'process'} completed successfully!")
            if not args.dry_run:
                print("You can now proceed with updating script references.")
        else:
            print(f"\n❌ Migration {'simulation' if args.dry_run else 'process'} failed!")
            print("Please review the errors above before proceeding.")
            sys.exit(1)
            
    except KeyboardInterrupt:
        print("\n\n⚠ Migration interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ Unexpected error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main() 