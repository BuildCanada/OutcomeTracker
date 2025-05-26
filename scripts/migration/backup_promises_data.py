#!/usr/bin/env python3
"""
Backup script for promises data before flattening migration.
Creates a complete backup of all promises data from the current subcollection structure.
"""

import firebase_admin
from firebase_admin import firestore
import os
import json
import logging
import sys
from datetime import datetime
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

# Initialize Firebase Admin SDK
def initialize_firestore():
    """Initialize Firebase Admin SDK and return Firestore client."""
    global db
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

def create_backup_directory():
    """Create backup directory with timestamp."""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_dir = Path(f"backup_promises_{timestamp}")
    backup_dir.mkdir(exist_ok=True)
    logger.info(f"Created backup directory: {backup_dir}")
    return backup_dir

def serialize_firestore_data(data):
    """Convert Firestore data types to JSON-serializable format."""
    if hasattr(data, 'to_dict'):
        data = data.to_dict()
    
    if isinstance(data, dict):
        result = {}
        for key, value in data.items():
            if hasattr(value, 'timestamp'):  # Firestore Timestamp
                result[key] = {
                    '_firestore_type': 'timestamp',
                    'value': value.timestamp()
                }
            elif isinstance(value, (dict, list)):
                result[key] = serialize_firestore_data(value)
            else:
                result[key] = value
        return result
    elif isinstance(data, list):
        return [serialize_firestore_data(item) for item in data]
    else:
        return data

def backup_promises_by_party(db, backup_dir, region_code=DEFAULT_REGION_CODE):
    """Backup promises for each party separately."""
    total_docs = 0
    backup_summary = {
        'timestamp': datetime.now().isoformat(),
        'region_code': region_code,
        'parties': {},
        'total_documents': 0,
        'collection_root': TARGET_PROMISES_COLLECTION_ROOT
    }
    
    for party_code in KNOWN_PARTY_CODES:
        party_collection_path = f"{TARGET_PROMISES_COLLECTION_ROOT}/{region_code}/{party_code}"
        logger.info(f"Backing up party collection: {party_collection_path}")
        
        try:
            # Get all documents in this party collection
            party_docs = []
            docs_stream = db.collection(party_collection_path).stream()
            party_doc_count = 0
            
            for doc_snapshot in docs_stream:
                doc_data = serialize_firestore_data(doc_snapshot.to_dict())
                party_docs.append({
                    'id': doc_snapshot.id,
                    'path': doc_snapshot.reference.path,
                    'data': doc_data,
                    'update_time': doc_snapshot.update_time.isoformat() if doc_snapshot.update_time else None,
                    'create_time': doc_snapshot.create_time.isoformat() if doc_snapshot.create_time else None
                })
                party_doc_count += 1
            
            # Save party backup to separate file
            party_backup_file = backup_dir / f"promises_{region_code}_{party_code}.json"
            with open(party_backup_file, 'w', encoding='utf-8') as f:
                json.dump({
                    'collection_path': party_collection_path,
                    'document_count': party_doc_count,
                    'backup_timestamp': datetime.now().isoformat(),
                    'documents': party_docs
                }, f, indent=2, ensure_ascii=False)
            
            logger.info(f"Backed up {party_doc_count} documents for {party_code} to {party_backup_file}")
            
            # Update summary
            backup_summary['parties'][party_code] = {
                'document_count': party_doc_count,
                'backup_file': str(party_backup_file.name),
                'collection_path': party_collection_path
            }
            total_docs += party_doc_count
            
        except Exception as e:
            logger.error(f"Error backing up party {party_code}: {e}", exc_info=True)
            backup_summary['parties'][party_code] = {
                'error': str(e),
                'collection_path': party_collection_path
            }
    
    backup_summary['total_documents'] = total_docs
    return backup_summary

def backup_metadata_collections(db, backup_dir):
    """Backup related collections that might be affected by migration."""
    related_collections = [
        'evidence_items',
        'promise_evidence_links', 
        'department_config',
        'parliament_session'
    ]
    
    metadata_summary = {}
    
    for collection_name in related_collections:
        try:
            logger.info(f"Backing up metadata collection: {collection_name}")
            docs = []
            docs_stream = db.collection(collection_name).stream()
            doc_count = 0
            
            for doc_snapshot in docs_stream:
                doc_data = serialize_firestore_data(doc_snapshot.to_dict())
                docs.append({
                    'id': doc_snapshot.id,
                    'data': doc_data
                })
                doc_count += 1
            
            # Save to file
            metadata_file = backup_dir / f"metadata_{collection_name}.json"
            with open(metadata_file, 'w', encoding='utf-8') as f:
                json.dump({
                    'collection_name': collection_name,
                    'document_count': doc_count,
                    'backup_timestamp': datetime.now().isoformat(),
                    'documents': docs
                }, f, indent=2, ensure_ascii=False)
            
            logger.info(f"Backed up {doc_count} documents from {collection_name}")
            metadata_summary[collection_name] = {
                'document_count': doc_count,
                'backup_file': str(metadata_file.name)
            }
            
        except Exception as e:
            logger.error(f"Error backing up {collection_name}: {e}", exc_info=True)
            metadata_summary[collection_name] = {'error': str(e)}
    
    return metadata_summary

def create_restore_script(backup_dir, backup_summary):
    """Create a restoration script for the backup."""
    restore_script = backup_dir / "restore_backup.py"
    
    script_content = f'''#!/usr/bin/env python3
"""
Restore script for promises backup created on {backup_summary['timestamp']}.
"""

import firebase_admin
from firebase_admin import firestore, credentials
import json
import os
import logging
from datetime import datetime
from pathlib import Path

def restore_promises_backup():
    """Restore promises from backup files."""
    if not firebase_admin._apps:
        firebase_admin.initialize_app()
    
    db = firestore.client()
    backup_dir = Path(__file__).parent
    
    # Restore each party collection
    parties = {json.dumps(backup_summary['parties'], indent=4)}
    
    for party_code, party_info in parties.items():
        if 'error' in party_info:
            print(f"Skipping {{party_code}} due to backup error: {{party_info['error']}}")
            continue
            
        backup_file = backup_dir / party_info['backup_file']
        if not backup_file.exists():
            print(f"Backup file not found: {{backup_file}}")
            continue
            
        with open(backup_file, 'r', encoding='utf-8') as f:
            backup_data = json.load(f)
        
        collection_path = party_info['collection_path']
        print(f"Restoring {{len(backup_data['documents'])}} documents to {{collection_path}}")
        
        batch = db.batch()
        batch_count = 0
        
        for doc_info in backup_data['documents']:
            doc_ref = db.document(doc_info['path'])
            doc_data = restore_firestore_data(doc_info['data'])
            batch.set(doc_ref, doc_data)
            batch_count += 1
            
            if batch_count >= 500:  # Firestore batch limit
                batch.commit()
                batch = db.batch()
                batch_count = 0
        
        if batch_count > 0:
            batch.commit()
        
        print(f"Restored {{party_info['document_count']}} documents for {{party_code}}")

def restore_firestore_data(data):
    """Convert JSON data back to Firestore format."""
    if isinstance(data, dict):
        if '_firestore_type' in data and data['_firestore_type'] == 'timestamp':
            return firestore.SERVER_TIMESTAMP  # Or use specific timestamp if needed
        else:
            return {{key: restore_firestore_data(value) for key, value in data.items()}}
    elif isinstance(data, list):
        return [restore_firestore_data(item) for item in data]
    else:
        return data

if __name__ == "__main__":
    restore_promises_backup()
'''
    
    with open(restore_script, 'w', encoding='utf-8') as f:
        f.write(script_content)
    
    # Make script executable
    restore_script.chmod(0o755)
    logger.info(f"Created restore script: {restore_script}")

def main():
    """Main backup execution function."""
    logger.info("Starting promises data backup...")
    
    try:
        # Initialize Firestore
        db = initialize_firestore()
        
        # Create backup directory
        backup_dir = create_backup_directory()
        
        # Backup promises data
        logger.info("Backing up promises data by party...")
        backup_summary = backup_promises_by_party(db, backup_dir)
        
        # Backup related metadata collections
        logger.info("Backing up related metadata collections...")
        metadata_summary = backup_metadata_collections(db, backup_dir)
        
        # Create comprehensive summary
        full_summary = {
            'backup_info': backup_summary,
            'metadata_backup': metadata_summary,
            'backup_directory': str(backup_dir),
            'backup_completed_at': datetime.now().isoformat()
        }
        
        # Save summary
        summary_file = backup_dir / "backup_summary.json"
        with open(summary_file, 'w', encoding='utf-8') as f:
            json.dump(full_summary, f, indent=2, ensure_ascii=False)
        
        # Create restore script
        create_restore_script(backup_dir, backup_summary)
        
        # Print summary
        logger.info("=" * 60)
        logger.info("BACKUP COMPLETED SUCCESSFULLY")
        logger.info("=" * 60)
        logger.info(f"Backup directory: {backup_dir}")
        logger.info(f"Total promises backed up: {backup_summary['total_documents']}")
        logger.info("Party breakdown:")
        for party, info in backup_summary['parties'].items():
            if 'document_count' in info:
                logger.info(f"  {party}: {info['document_count']} documents")
            else:
                logger.info(f"  {party}: ERROR - {info.get('error', 'Unknown error')}")
        
        logger.info(f"Summary saved to: {summary_file}")
        logger.info(f"Restore script created: {backup_dir / 'restore_backup.py'}")
        
        return True
        
    except Exception as e:
        logger.critical(f"Backup failed: {e}", exc_info=True)
        return False

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1) 