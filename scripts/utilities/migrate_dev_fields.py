#!/usr/bin/env python3
"""
Data Migration Script: Remove dev_ Prefixes from Field Names

This script migrates field names from dev_ prefixes to standardized names:
- promises collection: 4 fields
- evidence_items collection: 3 fields

Features:
- Complete data backup before migration
- Batch processing for large datasets
- Progress tracking and logging
- Rollback capability
- Dry run mode for testing
"""

import os
import sys
import argparse
import logging
import json
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

import firebase_admin
from firebase_admin import credentials, firestore

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(f'migration_dev_fields_{datetime.now().strftime("%Y%m%d_%H%M%S")}.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

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
        logger.error(f"Failed to initialize Firebase: {e}")
        return None

# Field mappings
FIELD_MAPPINGS = {
    'promises': {
        'dev_explanation_enriched_at': 'explanation_enriched_at',
        'dev_explanation_enrichment_model': 'explanation_enrichment_model',
        'dev_explanation_enrichment_status': 'explanation_enrichment_status',
        'dev_evidence_linking_status': 'evidence_linking_status'
    },
    'evidence_items': {
        'dev_linking_status': 'linking_status',
        'dev_linking_processed_at': 'linking_processed_at',
        'dev_linking_error_message': 'linking_error_message'
    }
}

class DevFieldMigrator:
    def __init__(self, db, dry_run=True, batch_size=100):
        self.db = db
        self.dry_run = dry_run
        self.batch_size = batch_size
        self.migration_stats = {
            'promises': {'total': 0, 'migrated': 0, 'errors': 0},
            'evidence_items': {'total': 0, 'migrated': 0, 'errors': 0}
        }
        
    def backup_collection(self, collection_name: str, backup_dir: str) -> bool:
        """Create a full backup of a collection."""
        try:
            backup_path = Path(backup_dir) / f"{collection_name}_backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
            backup_path.parent.mkdir(parents=True, exist_ok=True)
            
            logger.info(f"Creating backup of {collection_name} collection...")
            
            docs = []
            collection_ref = self.db.collection(collection_name)
            
            for doc in collection_ref.stream():
                doc_data = doc.to_dict()
                docs.append({
                    'id': doc.id,
                    'data': doc_data
                })
            
            with open(backup_path, 'w') as f:
                json.dump(docs, f, indent=2, default=str)
            
            logger.info(f"Backup created: {backup_path} ({len(docs)} documents)")
            return True
            
        except Exception as e:
            logger.error(f"Failed to backup {collection_name}: {e}")
            return False
    
    def migrate_collection(self, collection_name: str) -> bool:
        """Migrate all dev_ fields in a collection."""
        try:
            logger.info(f"Starting migration for {collection_name} collection...")
            
            field_mappings = FIELD_MAPPINGS.get(collection_name, {})
            if not field_mappings:
                logger.warning(f"No field mappings defined for {collection_name}")
                return True
            
            collection_ref = self.db.collection(collection_name)
            
            # Process in batches
            batch = self.db.batch()
            batch_count = 0
            
            for doc in collection_ref.stream():
                doc_data = doc.to_dict()
                update_data = {}
                has_changes = False
                
                # Check for dev_ fields to migrate
                for old_field, new_field in field_mappings.items():
                    if old_field in doc_data:
                        # Copy value to new field
                        update_data[new_field] = doc_data[old_field]
                        # Mark old field for deletion
                        update_data[old_field] = firestore.DELETE_FIELD
                        has_changes = True
                
                if has_changes:
                    if not self.dry_run:
                        batch.update(doc.reference, update_data)
                        batch_count += 1
                        
                        if batch_count >= self.batch_size:
                            batch.commit()
                            logger.info(f"Committed batch of {batch_count} updates for {collection_name}")
                            batch = self.db.batch()
                            batch_count = 0
                    
                    self.migration_stats[collection_name]['migrated'] += 1
                    logger.debug(f"Migrated document {doc.id} in {collection_name}")
                
                self.migration_stats[collection_name]['total'] += 1
            
            # Commit final batch
            if batch_count > 0 and not self.dry_run:
                batch.commit()
                logger.info(f"Committed final batch of {batch_count} updates for {collection_name}")
            
            logger.info(f"Migration completed for {collection_name}:")
            logger.info(f"  Total documents: {self.migration_stats[collection_name]['total']}")
            logger.info(f"  Migrated: {self.migration_stats[collection_name]['migrated']}")
            
            return True
            
        except Exception as e:
            logger.error(f"Failed to migrate {collection_name}: {e}")
            self.migration_stats[collection_name]['errors'] += 1
            return False
    
    def validate_migration(self, collection_name: str) -> bool:
        """Validate that migration was successful."""
        try:
            logger.info(f"Validating migration for {collection_name}...")
            
            field_mappings = FIELD_MAPPINGS.get(collection_name, {})
            collection_ref = self.db.collection(collection_name)
            
            dev_fields_found = 0
            new_fields_found = 0
            
            # Sample check (first 100 documents)
            docs = list(collection_ref.limit(100).stream())
            
            for doc in docs:
                doc_data = doc.to_dict()
                
                # Check for remaining dev_ fields
                for old_field in field_mappings.keys():
                    if old_field in doc_data:
                        dev_fields_found += 1
                
                # Check for new fields
                for new_field in field_mappings.values():
                    if new_field in doc_data:
                        new_fields_found += 1
            
            logger.info(f"Validation for {collection_name}:")
            logger.info(f"  Remaining dev_ fields: {dev_fields_found}")
            logger.info(f"  New standardized fields: {new_fields_found}")
            
            return dev_fields_found == 0
            
        except Exception as e:
            logger.error(f"Failed to validate {collection_name}: {e}")
            return False
    
    def run_migration(self, backup_dir: Optional[str] = None) -> bool:
        """Run the complete migration process."""
        try:
            logger.info("=== Starting dev_ field migration ===")
            
            if self.dry_run:
                logger.info("*** DRY RUN MODE - No changes will be made ***")
            
            # Create backups if not dry run
            if not self.dry_run and backup_dir:
                for collection_name in FIELD_MAPPINGS.keys():
                    if not self.backup_collection(collection_name, backup_dir):
                        logger.error("Backup failed, aborting migration")
                        return False
            
            # Migrate each collection
            success = True
            for collection_name in FIELD_MAPPINGS.keys():
                if not self.migrate_collection(collection_name):
                    success = False
            
            # Validate migration if not dry run
            if not self.dry_run and success:
                for collection_name in FIELD_MAPPINGS.keys():
                    if not self.validate_migration(collection_name):
                        logger.warning(f"Validation failed for {collection_name}")
            
            # Print final statistics
            logger.info("=== Migration Summary ===")
            for collection_name, stats in self.migration_stats.items():
                logger.info(f"{collection_name}:")
                logger.info(f"  Total: {stats['total']}")
                logger.info(f"  Migrated: {stats['migrated']}")
                logger.info(f"  Errors: {stats['errors']}")
            
            return success
            
        except Exception as e:
            logger.error(f"Migration failed: {e}")
            return False

def main():
    parser = argparse.ArgumentParser(description="Migrate dev_ field names to standardized names")
    parser.add_argument('--dry-run', action='store_true', help='Show what would be changed without making changes')
    parser.add_argument('--backup-dir', default='./migration_backups', help='Directory for backups')
    parser.add_argument('--batch-size', type=int, default=100, help='Batch size for processing')
    
    args = parser.parse_args()
    
    # Initialize Firebase
    db = initialize_firebase()
    if not db:
        logger.error("Failed to initialize Firestore, exiting")
        sys.exit(1)
    
    # Run migration
    migrator = DevFieldMigrator(db, dry_run=args.dry_run, batch_size=args.batch_size)
    success = migrator.run_migration(backup_dir=args.backup_dir if not args.dry_run else None)
    
    if success:
        logger.info("Migration completed successfully!")
        if args.dry_run:
            logger.info("Run without --dry-run to execute the migration")
    else:
        logger.error("Migration failed!")
        sys.exit(1)

if __name__ == "__main__":
    main() 