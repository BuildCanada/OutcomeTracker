#!/usr/bin/env python3
"""
Migration script to flatten promises collection structure.
Migrates from promises/{region}/{party}/promise_docs to promises/promise_docs
with region and party stored as document fields.
"""

import firebase_admin
from firebase_admin import firestore
import os
import logging
import sys
import argparse
from datetime import datetime
from typing import Dict, List, Optional, Tuple
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

# Migration constants
MIGRATION_TRACKING_COLLECTION = "migration_tracking"
MIGRATION_VERSION = "1.0"
DEFAULT_BATCH_SIZE = 100

class PromiseMigrator:
    """Handles the migration of promises from subcollections to flat structure."""
    
    def __init__(self, db: firestore.Client, dry_run: bool = False, batch_size: int = DEFAULT_BATCH_SIZE):
        self.db = db
        self.dry_run = dry_run
        self.batch_size = batch_size
        self.migration_stats = {
            'total_processed': 0,
            'successful_migrations': 0,
            'failed_migrations': 0,
            'id_conflicts': 0,
            'parties_processed': {},
            'start_time': None,
            'end_time': None
        }
    
    def initialize_migration_tracking(self) -> None:
        """Initialize migration tracking collection."""
        try:
            # Create migration session record
            session_data = {
                'migration_version': MIGRATION_VERSION,
                'started_at': firestore.SERVER_TIMESTAMP,
                'status': 'in_progress',
                'dry_run': self.dry_run,
                'batch_size': self.batch_size,
                'total_documents': 0,
                'migrated_documents': 0,
                'failed_documents': 0
            }
            
            if not self.dry_run:
                self.migration_session_ref = self.db.collection(MIGRATION_TRACKING_COLLECTION).document()
                self.migration_session_ref.set(session_data)
                logger.info(f"Created migration session: {self.migration_session_ref.id}")
            else:
                logger.info("[DRY RUN] Would create migration tracking session")
                
        except Exception as e:
            logger.error(f"Failed to initialize migration tracking: {e}")
            raise
    
    def check_document_conflicts(self, region_code: str, party_code: str) -> Dict[str, str]:
        """Check for potential document ID conflicts in the target collection."""
        logger.info(f"Checking for document ID conflicts for {region_code}/{party_code}")
        
        conflicts = {}
        try:
            # Get all document IDs from the source subcollection
            source_collection_path = f"{TARGET_PROMISES_COLLECTION_ROOT}/{region_code}/{party_code}"
            source_docs = self.db.collection(source_collection_path).select([]).stream()
            source_ids = [doc.id for doc in source_docs]
            
            # Check if any exist in target flat collection
            target_collection = self.db.collection(TARGET_PROMISES_COLLECTION_ROOT)
            
            for doc_id in source_ids:
                target_doc = target_collection.document(doc_id).get()
                if target_doc.exists:
                    conflicts[doc_id] = f"Document already exists in target collection"
            
            if conflicts:
                logger.warning(f"Found {len(conflicts)} potential ID conflicts for {party_code}")
                for doc_id, reason in conflicts.items():
                    logger.warning(f"  Conflict: {doc_id} - {reason}")
            else:
                logger.info(f"No ID conflicts found for {party_code}")
                
        except Exception as e:
            logger.error(f"Error checking conflicts for {party_code}: {e}")
            
        return conflicts
    
    def generate_conflict_free_id(self, original_id: str, party_code: str, region_code: str) -> str:
        """Generate a conflict-free document ID."""
        # Strategy: append party and region to make it unique
        new_id = f"{original_id}_{region_code}_{party_code}"
        
        # Check if this new ID also conflicts
        target_doc = self.db.collection(TARGET_PROMISES_COLLECTION_ROOT).document(new_id).get()
        if target_doc.exists:
            # If still conflicts, add timestamp
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            new_id = f"{original_id}_{region_code}_{party_code}_{timestamp}"
        
        return new_id
    
    def migrate_document(self, doc_snapshot, region_code: str, party_code: str) -> Tuple[bool, str]:
        """Migrate a single document from subcollection to flat structure."""
        try:
            original_id = doc_snapshot.id
            original_data = doc_snapshot.to_dict()
            original_path = doc_snapshot.reference.path
            
            # Prepare new document data
            new_doc_data = {
                **original_data,
                'region_code': region_code,
                'party_code': party_code,
                'migration_metadata': {
                    'migrated_at': firestore.SERVER_TIMESTAMP,
                    'source_path': original_path,
                    'migration_version': MIGRATION_VERSION,
                    'original_id': original_id
                }
            }
            
            # Handle potential ID conflicts
            target_id = original_id
            target_doc_ref = self.db.collection(TARGET_PROMISES_COLLECTION_ROOT).document(target_id)
            
            if not self.dry_run:
                target_doc = target_doc_ref.get()
                if target_doc.exists:
                    # Generate conflict-free ID
                    target_id = self.generate_conflict_free_id(original_id, party_code, region_code)
                    target_doc_ref = self.db.collection(TARGET_PROMISES_COLLECTION_ROOT).document(target_id)
                    new_doc_data['migration_metadata']['conflict_resolved'] = True
                    new_doc_data['migration_metadata']['new_id'] = target_id
                    self.migration_stats['id_conflicts'] += 1
                    logger.warning(f"ID conflict resolved: {original_id} -> {target_id}")
            
            # Write new document
            if not self.dry_run:
                target_doc_ref.set(new_doc_data)
                
                # Track migration in migration_tracking collection
                tracking_doc_ref = self.db.collection(MIGRATION_TRACKING_COLLECTION).document()
                tracking_data = {
                    'source_path': original_path,
                    'target_id': target_id,
                    'migration_status': 'completed',
                    'migration_timestamp': firestore.SERVER_TIMESTAMP,
                    'region_code': region_code,
                    'party_code': party_code,
                    'original_id': original_id,
                    'had_conflict': target_id != original_id
                }
                tracking_doc_ref.set(tracking_data)
                
                logger.debug(f"Migrated: {original_path} -> promises/{target_id}")
            else:
                logger.debug(f"[DRY RUN] Would migrate: {original_path} -> promises/{target_id}")
            
            return True, target_id
            
        except Exception as e:
            error_msg = f"Failed to migrate document {doc_snapshot.id}: {e}"
            logger.error(error_msg)
            
            if not self.dry_run:
                # Track failed migration
                try:
                    tracking_doc_ref = self.db.collection(MIGRATION_TRACKING_COLLECTION).document()
                    tracking_data = {
                        'source_path': doc_snapshot.reference.path,
                        'target_id': None,
                        'migration_status': 'failed',
                        'migration_timestamp': firestore.SERVER_TIMESTAMP,
                        'error_message': str(e),
                        'region_code': region_code,
                        'party_code': party_code,
                        'original_id': doc_snapshot.id
                    }
                    tracking_doc_ref.set(tracking_data)
                except Exception as tracking_error:
                    logger.error(f"Failed to track migration failure: {tracking_error}")
            
            return False, error_msg
    
    def migrate_party_collection(self, region_code: str, party_code: str) -> Dict:
        """Migrate all documents for a specific party."""
        logger.info(f"Starting migration for {region_code}/{party_code}")
        
        party_stats = {
            'total_docs': 0,
            'successful_migrations': 0,
            'failed_migrations': 0,
            'conflicts_resolved': 0,
            'start_time': datetime.now(),
            'end_time': None
        }
        
        try:
            source_collection_path = f"{TARGET_PROMISES_COLLECTION_ROOT}/{region_code}/{party_code}"
            source_collection = self.db.collection(source_collection_path)
            
            # First, check for conflicts
            conflicts = self.check_document_conflicts(region_code, party_code)
            party_stats['potential_conflicts'] = len(conflicts)
            
            # Get all documents in batches
            docs_stream = source_collection.stream()
            docs_batch = []
            
            for doc_snapshot in docs_stream:
                docs_batch.append(doc_snapshot)
                party_stats['total_docs'] += 1
                
                # Process batch when it reaches batch_size
                if len(docs_batch) >= self.batch_size:
                    self._process_document_batch(docs_batch, region_code, party_code, party_stats)
                    docs_batch = []
            
            # Process remaining documents
            if docs_batch:
                self._process_document_batch(docs_batch, region_code, party_code, party_stats)
            
            party_stats['end_time'] = datetime.now()
            party_stats['duration_seconds'] = (party_stats['end_time'] - party_stats['start_time']).total_seconds()
            
            logger.info(f"Completed migration for {party_code}: {party_stats['successful_migrations']}/{party_stats['total_docs']} successful")
            
        except Exception as e:
            logger.error(f"Error migrating party {party_code}: {e}")
            party_stats['error'] = str(e)
        
        return party_stats
    
    def _process_document_batch(self, docs_batch: List, region_code: str, party_code: str, party_stats: Dict) -> None:
        """Process a batch of documents."""
        logger.info(f"Processing batch of {len(docs_batch)} documents for {party_code}")
        
        for doc_snapshot in docs_batch:
            success, result = self.migrate_document(doc_snapshot, region_code, party_code)
            
            if success:
                party_stats['successful_migrations'] += 1
                self.migration_stats['successful_migrations'] += 1
            else:
                party_stats['failed_migrations'] += 1
                self.migration_stats['failed_migrations'] += 1
            
            self.migration_stats['total_processed'] += 1
            
            # Log progress
            if self.migration_stats['total_processed'] % 50 == 0:
                logger.info(f"Progress: {self.migration_stats['total_processed']} documents processed")
    
    def run_migration(self, regions: Optional[List[str]] = None, parties: Optional[List[str]] = None) -> bool:
        """Run the complete migration process."""
        logger.info("Starting promises collection flattening migration")
        logger.info(f"Dry run mode: {self.dry_run}")
        
        self.migration_stats['start_time'] = datetime.now()
        
        try:
            # Initialize migration tracking
            self.initialize_migration_tracking()
            
            # Default to known values if not specified
            regions_to_process = regions or [DEFAULT_REGION_CODE]
            parties_to_process = parties or KNOWN_PARTY_CODES
            
            logger.info(f"Processing regions: {regions_to_process}")
            logger.info(f"Processing parties: {parties_to_process}")
            
            # Migrate each region/party combination
            for region_code in regions_to_process:
                for party_code in parties_to_process:
                    party_stats = self.migrate_party_collection(region_code, party_code)
                    self.migration_stats['parties_processed'][f"{region_code}/{party_code}"] = party_stats
            
            self.migration_stats['end_time'] = datetime.now()
            
            # Update migration session
            if not self.dry_run and hasattr(self, 'migration_session_ref'):
                self.migration_session_ref.update({
                    'status': 'completed',
                    'completed_at': firestore.SERVER_TIMESTAMP,
                    'total_documents': self.migration_stats['total_processed'],
                    'migrated_documents': self.migration_stats['successful_migrations'],
                    'failed_documents': self.migration_stats['failed_migrations'],
                    'id_conflicts': self.migration_stats['id_conflicts']
                })
            
            # Print final summary
            self._print_migration_summary()
            
            return self.migration_stats['failed_migrations'] == 0
            
        except Exception as e:
            logger.critical(f"Migration failed: {e}", exc_info=True)
            
            # Update migration session with failure
            if not self.dry_run and hasattr(self, 'migration_session_ref'):
                try:
                    self.migration_session_ref.update({
                        'status': 'failed',
                        'failed_at': firestore.SERVER_TIMESTAMP,
                        'error_message': str(e)
                    })
                except Exception as update_error:
                    logger.error(f"Failed to update migration session: {update_error}")
            
            return False
    
    def _print_migration_summary(self) -> None:
        """Print a comprehensive migration summary."""
        duration = self.migration_stats['end_time'] - self.migration_stats['start_time']
        
        logger.info("=" * 80)
        logger.info("MIGRATION SUMMARY")
        logger.info("=" * 80)
        logger.info(f"Mode: {'DRY RUN' if self.dry_run else 'LIVE MIGRATION'}")
        logger.info(f"Duration: {duration.total_seconds():.2f} seconds")
        logger.info(f"Total documents processed: {self.migration_stats['total_processed']}")
        logger.info(f"Successful migrations: {self.migration_stats['successful_migrations']}")
        logger.info(f"Failed migrations: {self.migration_stats['failed_migrations']}")
        logger.info(f"ID conflicts resolved: {self.migration_stats['id_conflicts']}")
        
        logger.info("\nParty breakdown:")
        for party_key, stats in self.migration_stats['parties_processed'].items():
            if 'error' in stats:
                logger.info(f"  {party_key}: ERROR - {stats['error']}")
            else:
                success_rate = (stats['successful_migrations'] / stats['total_docs'] * 100) if stats['total_docs'] > 0 else 0
                logger.info(f"  {party_key}: {stats['successful_migrations']}/{stats['total_docs']} ({success_rate:.1f}%)")
        
        if self.migration_stats['failed_migrations'] > 0:
            logger.warning(f"\n⚠️  {self.migration_stats['failed_migrations']} migrations failed. Check logs for details.")
        else:
            logger.info("\n✅ All migrations completed successfully!")

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
    """Main migration execution function."""
    parser = argparse.ArgumentParser(description='Migrate promises collection to flat structure')
    parser.add_argument('--dry-run', action='store_true', help='Run in dry-run mode (no actual changes)')
    parser.add_argument('--batch-size', type=int, default=DEFAULT_BATCH_SIZE, help='Batch size for processing')
    parser.add_argument('--regions', nargs='+', help='Specific regions to migrate (default: all)')
    parser.add_argument('--parties', nargs='+', help='Specific parties to migrate (default: all)')
    parser.add_argument('--confirm', action='store_true', help='Skip confirmation prompt')
    
    args = parser.parse_args()
    
    if not args.dry_run and not args.confirm:
        print("⚠️  WARNING: This will permanently modify your Firestore database!")
        print("This migration will move documents from subcollections to a flat structure.")
        print("Make sure you have created a backup before proceeding.")
        print()
        response = input("Are you sure you want to continue? (yes/no): ").strip().lower()
        if response not in ['yes', 'y']:
            print("Migration cancelled.")
            return False
    
    try:
        # Initialize Firestore
        db = initialize_firestore()
        
        # Create migrator
        migrator = PromiseMigrator(
            db=db,
            dry_run=args.dry_run,
            batch_size=args.batch_size
        )
        
        # Run migration
        success = migrator.run_migration(
            regions=args.regions,
            parties=args.parties
        )
        
        return success
        
    except Exception as e:
        logger.critical(f"Migration failed: {e}", exc_info=True)
        return False

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1) 