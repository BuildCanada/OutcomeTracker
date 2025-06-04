#!/usr/bin/env python3
"""
Production Collections Backup Script

Creates timestamped backups of critical collections before running 
the new hybrid evidence linking system on production data.

Usage:
    python scripts/utilities/backup_production_collections.py --collections evidence_items promises
    python scripts/utilities/backup_production_collections.py --all --verify
    python scripts/utilities/backup_production_collections.py --restore backup_20241201_143022
"""

import os
import sys
import json
import argparse
import logging
from datetime import datetime
from typing import Dict, List, Any, Optional
from pathlib import Path

# Add project root to Python path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from google.cloud import firestore
from google.cloud.firestore_v1.base_query import FieldFilter

def setup_logging(verbose: bool = False):
    """Setup logging configuration."""
    log_level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=log_level,
        format='%(asctime)s - %(levelname)s - %(message)s',
        handlers=[
            logging.StreamHandler(),
            logging.FileHandler(f'backup_log_{datetime.now().strftime("%Y%m%d_%H%M%S")}.log')
        ]
    )

def setup_firebase() -> firestore.Client:
    """Initialize Firebase client."""
    try:
        # Initialize Firebase client
        db = firestore.Client()
        
        # Test connection with a valid collection name
        test_ref = db.collection('backup_connection_test').document('connection_test')
        test_ref.set({'test': True, 'timestamp': firestore.SERVER_TIMESTAMP})
        test_ref.delete()
        
        logging.info("✅ Firebase connection established successfully")
        return db
        
    except Exception as e:
        logging.error(f"❌ Failed to connect to Firebase: {e}")
        raise

class ProductionBackup:
    """Handle production collection backups with verification and restoration."""
    
    def __init__(self, db: firestore.Client):
        self.db = db
        self.backup_timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        
        # Critical collections to backup
        self.critical_collections = {
            'evidence_items': 'Core evidence data with promise links',
            'promises': 'Government promises and progress tracking',
            'evidence_promise_links': 'Legacy evidence-promise relationships',
            'promise_progress_scores': 'Historical progress scoring data',
            'pipeline_job_executions': 'Pipeline execution history'
        }
        
    def create_backup(self, collections: List[str], verify: bool = True) -> Dict[str, Any]:
        """
        Create timestamped backups of specified collections.
        
        Args:
            collections: List of collection names to backup
            verify: Whether to verify backup integrity
            
        Returns:
            Backup summary with statistics
        """
        backup_summary = {
            'backup_timestamp': self.backup_timestamp,
            'collections_backed_up': {},
            'total_documents': 0,
            'total_size_mb': 0,
            'backup_duration_seconds': 0,
            'verification_passed': False
        }
        
        start_time = datetime.now()
        logging.info(f"🚀 Starting production backup at {self.backup_timestamp}")
        
        try:
            for collection_name in collections:
                if collection_name not in self.critical_collections:
                    logging.warning(f"⚠️  Collection '{collection_name}' not in critical collections list")
                
                collection_stats = self._backup_collection(collection_name)
                backup_summary['collections_backed_up'][collection_name] = collection_stats
                backup_summary['total_documents'] += collection_stats['document_count']
                backup_summary['total_size_mb'] += collection_stats['estimated_size_mb']
                
                logging.info(f"✅ Backed up {collection_name}: {collection_stats['document_count']} documents")
            
            # Calculate total time
            backup_summary['backup_duration_seconds'] = (datetime.now() - start_time).total_seconds()
            
            # Verify backups if requested
            if verify:
                backup_summary['verification_passed'] = self._verify_backups(collections)
            
            # Save backup metadata
            self._save_backup_metadata(backup_summary)
            
            logging.info(f"🎉 Backup completed successfully in {backup_summary['backup_duration_seconds']:.1f} seconds")
            logging.info(f"📊 Total: {backup_summary['total_documents']} documents, ~{backup_summary['total_size_mb']:.1f} MB")
            
            return backup_summary
            
        except Exception as e:
            logging.error(f"❌ Backup failed: {e}")
            raise
    
    def _backup_collection(self, collection_name: str) -> Dict[str, Any]:
        """Backup a single collection to a timestamped backup collection."""
        backup_collection_name = f"{collection_name}_backup_{self.backup_timestamp}"
        
        logging.info(f"📦 Backing up {collection_name} → {backup_collection_name}")
        
        # Get source collection
        source_ref = self.db.collection(collection_name)
        backup_ref = self.db.collection(backup_collection_name)
        
        document_count = 0
        estimated_size = 0
        batch_size = 100  # Reduced from 500 to avoid transaction limits
        batch = self.db.batch()
        batch_count = 0
        
        try:
            # Stream all documents from source collection
            for doc in source_ref.stream():
                doc_data = doc.to_dict()
                
                # Add backup metadata
                doc_data['_backup_metadata'] = {
                    'original_collection': collection_name,
                    'backup_timestamp': self.backup_timestamp,
                    'original_doc_id': doc.id,
                    'backup_created_at': firestore.SERVER_TIMESTAMP
                }
                
                # Add to batch
                backup_doc_ref = backup_ref.document(doc.id)
                batch.set(backup_doc_ref, doc_data)
                
                document_count += 1
                estimated_size += len(json.dumps(doc_data, default=str))
                batch_count += 1
                
                # Commit batch when full
                if batch_count >= batch_size:
                    try:
                        batch.commit()
                        batch = self.db.batch()
                        batch_count = 0
                        if document_count % 500 == 0:  # Log every 500 docs
                            logging.debug(f"📝 Backed up {document_count} documents...")
                    except Exception as e:
                        logging.error(f"❌ Batch commit failed at document {document_count}: {e}")
                        raise
            
            # Commit remaining documents
            if batch_count > 0:
                batch.commit()
            
            return {
                'backup_collection_name': backup_collection_name,
                'document_count': document_count,
                'estimated_size_mb': estimated_size / (1024 * 1024),
                'backup_completed_at': datetime.now().isoformat()
            }
            
        except Exception as e:
            logging.error(f"❌ Failed to backup {collection_name}: {e}")
            raise
    
    def _verify_backups(self, collections: List[str]) -> bool:
        """Verify backup integrity by comparing document counts and sample data."""
        logging.info("🔍 Verifying backup integrity...")
        
        try:
            for collection_name in collections:
                backup_collection_name = f"{collection_name}_backup_{self.backup_timestamp}"
                
                # Count documents in original and backup
                original_count = len(list(self.db.collection(collection_name).stream()))
                backup_count = len(list(self.db.collection(backup_collection_name).stream()))
                
                if original_count != backup_count:
                    logging.error(f"❌ Document count mismatch for {collection_name}: {original_count} → {backup_count}")
                    return False
                
                # Sample verification - check a few random documents
                sample_docs = list(self.db.collection(collection_name).limit(5).stream())
                for original_doc in sample_docs:
                    backup_doc = self.db.collection(backup_collection_name).document(original_doc.id).get()
                    
                    if not backup_doc.exists:
                        logging.error(f"❌ Missing backup document: {collection_name}/{original_doc.id}")
                        return False
                    
                    # Compare key fields (excluding backup metadata)
                    original_data = original_doc.to_dict()
                    backup_data = backup_doc.to_dict()
                    backup_data.pop('_backup_metadata', None)  # Remove backup metadata for comparison
                    
                    # Quick comparison of a few key fields
                    for key in list(original_data.keys())[:5]:  # Check first 5 fields
                        if original_data.get(key) != backup_data.get(key):
                            logging.error(f"❌ Data mismatch in {collection_name}/{original_doc.id}.{key}")
                            return False
                
                logging.info(f"✅ {collection_name}: {original_count} documents verified")
            
            logging.info("✅ All backups verified successfully")
            return True
            
        except Exception as e:
            logging.error(f"❌ Backup verification failed: {e}")
            return False
    
    def _save_backup_metadata(self, backup_summary: Dict[str, Any]):
        """Save backup metadata for future reference and restoration."""
        metadata_collection = f"backup_metadata_{self.backup_timestamp}"
        
        try:
            self.db.collection(metadata_collection).document('backup_summary').set(backup_summary)
            
            # Also save to local file
            metadata_file = f"backup_metadata_{self.backup_timestamp}.json"
            with open(metadata_file, 'w') as f:
                json.dump(backup_summary, f, indent=2, default=str)
            
            logging.info(f"💾 Backup metadata saved to {metadata_file}")
            
        except Exception as e:
            logging.warning(f"⚠️  Failed to save backup metadata: {e}")
    
    def list_backups(self) -> List[Dict[str, Any]]:
        """List all available backups."""
        logging.info("📋 Listing available backups...")
        
        backups = []
        
        try:
            # Find all backup metadata collections
            collections = self.db.collections()
            
            for collection in collections:
                if collection.id.startswith('backup_metadata_'):
                    timestamp = collection.id.replace('backup_metadata_', '')
                    
                    # Get backup summary
                    summary_doc = collection.document('backup_summary').get()
                    if summary_doc.exists:
                        backup_info = summary_doc.to_dict()
                        backup_info['backup_id'] = timestamp
                        backups.append(backup_info)
            
            # Sort by timestamp (newest first)
            backups.sort(key=lambda x: x['backup_timestamp'], reverse=True)
            
            return backups
            
        except Exception as e:
            logging.error(f"❌ Failed to list backups: {e}")
            return []
    
    def restore_backup(self, backup_timestamp: str, collections: List[str], 
                      confirm_restore: bool = False) -> bool:
        """
        Restore collections from a backup.
        
        Args:
            backup_timestamp: Timestamp of backup to restore
            collections: Collections to restore
            confirm_restore: Safety confirmation flag
            
        Returns:
            True if restoration successful
        """
        if not confirm_restore:
            logging.error("❌ Restoration requires explicit confirmation flag --confirm-restore")
            return False
        
        logging.warning(f"⚠️  RESTORING FROM BACKUP {backup_timestamp}")
        logging.warning("⚠️  THIS WILL OVERWRITE CURRENT PRODUCTION DATA!")
        
        try:
            for collection_name in collections:
                backup_collection_name = f"{collection_name}_backup_{backup_timestamp}"
                
                # Check if backup exists
                backup_docs = list(self.db.collection(backup_collection_name).limit(1).stream())
                if not backup_docs:
                    logging.error(f"❌ Backup collection {backup_collection_name} not found")
                    return False
                
                logging.info(f"🔄 Restoring {backup_collection_name} → {collection_name}")
                
                # Clear current collection
                self._clear_collection(collection_name)
                
                # Restore from backup
                batch = self.db.batch()
                batch_count = 0
                restored_count = 0
                
                for backup_doc in self.db.collection(backup_collection_name).stream():
                    doc_data = backup_doc.to_dict()
                    
                    # Remove backup metadata
                    doc_data.pop('_backup_metadata', None)
                    
                    # Restore to original collection
                    original_ref = self.db.collection(collection_name).document(backup_doc.id)
                    batch.set(original_ref, doc_data)
                    
                    batch_count += 1
                    restored_count += 1
                    
                    if batch_count >= 500:
                        batch.commit()
                        batch = self.db.batch()
                        batch_count = 0
                
                # Commit remaining
                if batch_count > 0:
                    batch.commit()
                
                logging.info(f"✅ Restored {restored_count} documents to {collection_name}")
            
            logging.info("🎉 Restoration completed successfully")
            return True
            
        except Exception as e:
            logging.error(f"❌ Restoration failed: {e}")
            return False
    
    def _clear_collection(self, collection_name: str):
        """Clear all documents from a collection."""
        logging.warning(f"🗑️  Clearing collection {collection_name}")
        
        docs = self.db.collection(collection_name).stream()
        batch = self.db.batch()
        batch_count = 0
        
        for doc in docs:
            batch.delete(doc.reference)
            batch_count += 1
            
            if batch_count >= 500:
                batch.commit()
                batch = self.db.batch()
                batch_count = 0
        
        if batch_count > 0:
            batch.commit()

def main():
    """Main execution function."""
    parser = argparse.ArgumentParser(description='Production Collections Backup Tool')
    parser.add_argument('--collections', nargs='+', 
                       help='Specific collections to backup')
    parser.add_argument('--all', action='store_true',
                       help='Backup all critical collections')
    parser.add_argument('--verify', action='store_true', default=True,
                       help='Verify backup integrity (default: True)')
    parser.add_argument('--no-verify', action='store_true',
                       help='Skip backup verification')
    parser.add_argument('--list-backups', action='store_true',
                       help='List available backups')
    parser.add_argument('--restore', type=str,
                       help='Restore from backup timestamp')
    parser.add_argument('--confirm-restore', action='store_true',
                       help='Confirm restoration (required for safety)')
    parser.add_argument('--verbose', action='store_true',
                       help='Enable verbose logging')
    
    args = parser.parse_args()
    
    # Setup logging
    setup_logging(args.verbose)
    
    try:
        # Initialize Firebase
        db = setup_firebase()
        backup_tool = ProductionBackup(db)
        
        # List backups
        if args.list_backups:
            backups = backup_tool.list_backups()
            if backups:
                print("\n📋 Available Backups:")
                for backup in backups:
                    print(f"  🕐 {backup['backup_timestamp']}: {backup['total_documents']} docs, "
                          f"{backup.get('total_size_mb', 0):.1f} MB")
                    for collection, stats in backup['collections_backed_up'].items():
                        print(f"     └─ {collection}: {stats['document_count']} documents")
            else:
                print("No backups found")
            return
        
        # Restore from backup
        if args.restore:
            collections_to_restore = args.collections or ['evidence_items', 'promises']
            success = backup_tool.restore_backup(
                args.restore, 
                collections_to_restore, 
                args.confirm_restore
            )
            sys.exit(0 if success else 1)
        
        # Create backup
        if args.all:
            collections_to_backup = list(backup_tool.critical_collections.keys())
        elif args.collections:
            collections_to_backup = args.collections
        else:
            # Default: backup core collections
            collections_to_backup = ['evidence_items', 'promises']
        
        verify_backup = args.verify and not args.no_verify
        
        logging.info(f"📦 Backing up collections: {', '.join(collections_to_backup)}")
        
        backup_summary = backup_tool.create_backup(collections_to_backup, verify_backup)
        
        print(f"\n🎉 Backup completed successfully!")
        print(f"📊 Backup ID: {backup_summary['backup_timestamp']}")
        print(f"📄 Documents: {backup_summary['total_documents']}")
        print(f"💾 Size: ~{backup_summary['total_size_mb']:.1f} MB")
        print(f"⏱️  Duration: {backup_summary['backup_duration_seconds']:.1f} seconds")
        
        if verify_backup:
            if backup_summary['verification_passed']:
                print("✅ Backup verification: PASSED")
            else:
                print("❌ Backup verification: FAILED")
                sys.exit(1)
        
        print(f"\n💡 To restore this backup later:")
        print(f"   python scripts/utilities/backup_production_collections.py \\")
        print(f"     --restore {backup_summary['backup_timestamp']} \\")
        print(f"     --collections {' '.join(collections_to_backup)} \\")
        print(f"     --confirm-restore")
        
    except Exception as e:
        logging.error(f"❌ Backup operation failed: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main() 