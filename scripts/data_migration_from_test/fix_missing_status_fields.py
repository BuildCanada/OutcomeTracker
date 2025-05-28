#!/usr/bin/env python3
"""
Fix Missing Status Fields Script

This script fixes documents in raw_news_releases that are missing the 
evidence_processing_status field by setting them to 'pending_evidence_creation'.

Usage:
    python fix_missing_status_fields.py [--dry-run]
"""

import os
import sys
from datetime import datetime
from typing import List

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
    sys.exit(1)


class StatusFieldFixer:
    """Fixes missing status fields in raw collections."""
    
    def __init__(self):
        """Initialize the fixer."""
        self.db = self._init_firebase()
        self.timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    
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
    
    def find_documents_missing_status_field(self, collection_name: str, status_field: str) -> List[str]:
        """Find document IDs that are missing the status field."""
        missing_docs = []
        
        try:
            print(f"Scanning {collection_name} for documents missing {status_field}...")
            docs = self.db.collection(collection_name).stream()
            
            for doc in docs:
                doc_data = doc.to_dict()
                if status_field not in doc_data:
                    missing_docs.append(doc.id)
            
            print(f"Found {len(missing_docs)} documents missing {status_field}")
            
        except Exception as e:
            print(f"Error scanning {collection_name}: {e}")
            raise
        
        return missing_docs
    
    def fix_missing_status_fields(self, collection_name: str, status_field: str, 
                                 default_status: str, dry_run: bool = False) -> int:
        """Fix documents missing the status field."""
        missing_doc_ids = self.find_documents_missing_status_field(collection_name, status_field)
        
        if not missing_doc_ids:
            print(f"No documents found missing {status_field} in {collection_name}")
            return 0
        
        if dry_run:
            print(f"[DRY RUN] Would update {len(missing_doc_ids)} documents in {collection_name}")
            print(f"[DRY RUN] Would set {status_field} = '{default_status}'")
            return len(missing_doc_ids)
        
        print(f"Updating {len(missing_doc_ids)} documents in {collection_name}...")
        
        # Process in batches
        batch_size = 100
        updated_count = 0
        
        for i in range(0, len(missing_doc_ids), batch_size):
            batch_ids = missing_doc_ids[i:i + batch_size]
            batch = self.db.batch()
            
            for doc_id in batch_ids:
                doc_ref = self.db.collection(collection_name).document(doc_id)
                batch.update(doc_ref, {
                    status_field: default_status,
                    'status_field_fixed_at': firestore.SERVER_TIMESTAMP,
                    'status_field_fixed_by': 'fix_missing_status_fields.py'
                })
            
            try:
                batch.commit()
                updated_count += len(batch_ids)
                print(f"  Updated batch {i//batch_size + 1}: {len(batch_ids)} documents")
            except Exception as e:
                print(f"  Error updating batch {i//batch_size + 1}: {e}")
                continue
        
        print(f"Successfully updated {updated_count} documents")
        return updated_count
    
    def run_fix(self, dry_run: bool = False):
        """Run the fix for all collections that need it."""
        print(f"{'='*60}")
        print(f"FIXING MISSING STATUS FIELDS")
        print(f"Timestamp: {self.timestamp}")
        print(f"Mode: {'DRY RUN' if dry_run else 'LIVE UPDATE'}")
        print(f"{'='*60}")
        
        # Fix raw_news_releases collection
        collection_name = 'raw_news_releases'
        status_field = 'evidence_processing_status'
        default_status = 'pending_evidence_creation'
        
        print(f"\nProcessing {collection_name}:")
        updated_count = self.fix_missing_status_fields(
            collection_name, status_field, default_status, dry_run
        )
        
        print(f"\n{'='*60}")
        print(f"SUMMARY")
        print(f"{'='*60}")
        print(f"Collection: {collection_name}")
        print(f"Documents {'would be ' if dry_run else ''}updated: {updated_count}")
        print(f"Status field: {status_field}")
        print(f"Default value: {default_status}")
        
        if not dry_run and updated_count > 0:
            print(f"\n✅ Status fields have been fixed!")
            print(f"   Run the status check again to verify the fix.")
        elif dry_run:
            print(f"\n🔍 This was a dry run. Use without --dry-run to apply changes.")
        
        return updated_count > 0


def main():
    """Main function."""
    import argparse
    
    parser = argparse.ArgumentParser(description='Fix missing status fields in raw collections')
    parser.add_argument('--dry-run', action='store_true',
                       help='Show what would be updated without making changes')
    
    args = parser.parse_args()
    
    try:
        fixer = StatusFieldFixer()
        success = fixer.run_fix(dry_run=args.dry_run)
        
        if success or args.dry_run:
            sys.exit(0)
        else:
            print("No updates needed.")
            sys.exit(0)
            
    except KeyboardInterrupt:
        print("\n\n⚠ Fix interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ Unexpected error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main() 