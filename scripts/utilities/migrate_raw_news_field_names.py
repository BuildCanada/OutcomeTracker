#!/usr/bin/env python3
"""
Migration script to rename field names in raw_news_releases collection
from old format to production format.

Old -> New mappings:
- title -> title_raw
- description -> summary_or_snippet_raw  
- full_content -> full_text_scraped
- feed_name -> source_feed_name
- feed_url -> rss_feed_url_used
- tags -> categories_rss
"""

import sys
from pathlib import Path
import logging
from datetime import datetime, timezone
from google.cloud import firestore

# Add the pipeline directory to Python path
pipeline_dir = Path(__file__).parent.parent.parent
sys.path.insert(0, str(pipeline_dir))

from pipeline.core.base_job import BaseJob

class RawNewsFieldMigration(BaseJob):
    """Migration job to rename field names in raw_news_releases collection"""
    
    def __init__(self):
        super().__init__("raw_news_field_migration")
        
        # Field mappings: old_name -> new_name
        self.field_mappings = {
            'title': 'title_raw',
            'description': 'summary_or_snippet_raw',
            'full_content': 'full_text_scraped',
            'feed_name': 'source_feed_name',
            'feed_url': 'rss_feed_url_used',
            'tags': 'categories_rss'
        }
        
        self.collection_name = 'raw_news_releases'
        self.batch_size = 50
        self.dry_run = False  # Set to True to see what would be changed without making changes
    
    def _execute_job(self, **kwargs) -> dict:
        """Execute the migration job"""
        self.dry_run = kwargs.get('dry_run', False)
        
        # First, find documents that need migration
        documents_to_migrate = self._find_documents_needing_migration()
        
        if not documents_to_migrate:
            self.logger.info("No documents found that need migration")
            return {
                'items_processed': 0,
                'items_created': 0,
                'items_updated': 0,
                'items_skipped': 0,
                'errors': 0,
                'metadata': {'migration_type': 'field_rename', 'dry_run': self.dry_run}
            }
            
        self.logger.info(f"Found {len(documents_to_migrate)} documents that need field migration")
        
        if self.dry_run:
            self.logger.info("DRY RUN MODE - No changes will be made")
            self._show_migration_preview(documents_to_migrate)
            return {
                'items_processed': len(documents_to_migrate),
                'items_created': 0,
                'items_updated': 0,
                'items_skipped': len(documents_to_migrate),
                'errors': 0,
                'metadata': {'migration_type': 'field_rename', 'dry_run': True}
            }
        
        # Migrate documents in batches
        total_migrated = self._migrate_documents(documents_to_migrate)
        
        return {
            'items_processed': len(documents_to_migrate),
            'items_created': 0,
            'items_updated': total_migrated,
            'items_skipped': len(documents_to_migrate) - total_migrated,
            'errors': 0,
            'metadata': {'migration_type': 'field_rename', 'dry_run': False}
        }
        
    def run(self, dry_run=False):
        """Run the migration (for direct script execution)"""
        self.dry_run = dry_run
        return self.execute(dry_run=dry_run)
    
    def _find_documents_needing_migration(self) -> list:
        """Find documents that have old field names"""
        collection = self.db.collection(self.collection_name)
        documents_to_migrate = []
        
        # Check for each old field name
        for old_field in self.field_mappings.keys():
            try:
                # Query for documents that have this old field
                query = collection.where(filter=firestore.FieldFilter(old_field, '!=', None)).limit(1000)
                docs = query.stream()
                
                for doc in docs:
                    doc_data = doc.to_dict()
                    doc_data['_doc_id'] = doc.id
                    
                    # Check if this document hasn't already been added
                    if not any(d['_doc_id'] == doc.id for d in documents_to_migrate):
                        documents_to_migrate.append(doc_data)
                        
            except Exception as e:
                self.logger.warning(f"Error querying for field {old_field}: {e}")
                continue
        
        return documents_to_migrate
    
    def _show_migration_preview(self, documents: list):
        """Show what would be migrated in dry run mode"""
        self.logger.info("MIGRATION PREVIEW:")
        
        for doc in documents[:5]:  # Show first 5 examples
            doc_id = doc['_doc_id']
            self.logger.info(f"\nDocument: {doc_id}")
            
            for old_field, new_field in self.field_mappings.items():
                if old_field in doc:
                    value = doc[old_field]
                    if isinstance(value, str):
                        value_preview = value[:100] + "..." if len(value) > 100 else value
                    else:
                        value_preview = str(value)
                    self.logger.info(f"  {old_field} -> {new_field}: {value_preview}")
        
        if len(documents) > 5:
            self.logger.info(f"\n... and {len(documents) - 5} more documents")
    
    def _migrate_documents(self, documents: list) -> int:
        """Migrate documents by renaming fields"""
        total_migrated = 0
        
        # Process in batches
        for i in range(0, len(documents), self.batch_size):
            batch = documents[i:i + self.batch_size]
            batch_migrated = self._migrate_batch(batch)
            total_migrated += batch_migrated
            
            self.logger.info(f"Migrated batch {i//self.batch_size + 1}: {batch_migrated} documents "
                           f"(Total: {total_migrated}/{len(documents)})")
        
        self.logger.info(f"Migration complete: {total_migrated} documents migrated")
        return total_migrated
    
    def _migrate_batch(self, batch: list) -> int:
        """Migrate a batch of documents"""
        migrated_count = 0
        
        for doc_data in batch:
            try:
                doc_id = doc_data['_doc_id']
                
                # Build update data
                update_data = {}
                fields_to_delete = []
                
                for old_field, new_field in self.field_mappings.items():
                    if old_field in doc_data:
                        # Copy old field value to new field
                        update_data[new_field] = doc_data[old_field]
                        # Mark old field for deletion
                        fields_to_delete.append(old_field)
                
                if not update_data:
                    continue  # No fields to migrate for this document
                
                # Add migration metadata
                update_data['field_migration_timestamp'] = datetime.now(timezone.utc)
                update_data['field_migration_script'] = 'migrate_raw_news_field_names.py'
                
                # Update the document
                doc_ref = self.db.collection(self.collection_name).document(doc_id)
                doc_ref.update(update_data)
                
                # Delete old fields (Firestore doesn't have a direct way to delete fields in update,
                # so we set them to firestore.DELETE_FIELD)
                delete_data = {}
                for field in fields_to_delete:
                    delete_data[field] = firestore.DELETE_FIELD
                
                if delete_data:
                    doc_ref.update(delete_data)
                
                migrated_count += 1
                self.logger.debug(f"Migrated document {doc_id}: renamed {len(fields_to_delete)} fields")
                
            except Exception as e:
                self.logger.error(f"Error migrating document {doc_data.get('_doc_id', 'unknown')}: {e}")
                continue
        
        return migrated_count


def main():
    # Set up logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    # Parse command line arguments
    import argparse
    parser = argparse.ArgumentParser(description='Migrate field names in raw_news_releases collection')
    parser.add_argument('--dry-run', action='store_true', 
                       help='Show what would be migrated without making changes')
    
    args = parser.parse_args()
    
    # Run migration
    migration = RawNewsFieldMigration()
    
    try:
        migration.run(dry_run=args.dry_run)
    except Exception as e:
        logging.error(f"Migration failed: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main() 