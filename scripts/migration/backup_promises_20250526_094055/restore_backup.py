#!/usr/bin/env python3
"""
Restore script for promises backup created on 2025-05-26T09:40:55.534681.
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
    parties = {
    "CPC": {
        "document_count": 0,
        "backup_file": "promises_Canada_CPC.json",
        "collection_path": "promises/Canada/CPC"
    },
    "LPC": {
        "document_count": 1374,
        "backup_file": "promises_Canada_LPC.json",
        "collection_path": "promises/Canada/LPC"
    },
    "NDP": {
        "document_count": 0,
        "backup_file": "promises_Canada_NDP.json",
        "collection_path": "promises/Canada/NDP"
    },
    "BQ": {
        "document_count": 0,
        "backup_file": "promises_Canada_BQ.json",
        "collection_path": "promises/Canada/BQ"
    }
}
    
    for party_code, party_info in parties.items():
        if 'error' in party_info:
            print(f"Skipping {party_code} due to backup error: {party_info['error']}")
            continue
            
        backup_file = backup_dir / party_info['backup_file']
        if not backup_file.exists():
            print(f"Backup file not found: {backup_file}")
            continue
            
        with open(backup_file, 'r', encoding='utf-8') as f:
            backup_data = json.load(f)
        
        collection_path = party_info['collection_path']
        print(f"Restoring {len(backup_data['documents'])} documents to {collection_path}")
        
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
        
        print(f"Restored {party_info['document_count']} documents for {party_code}")

def restore_firestore_data(data):
    """Convert JSON data back to Firestore format."""
    if isinstance(data, dict):
        if '_firestore_type' in data and data['_firestore_type'] == 'timestamp':
            return firestore.SERVER_TIMESTAMP  # Or use specific timestamp if needed
        else:
            return {key: restore_firestore_data(value) for key, value in data.items()}
    elif isinstance(data, list):
        return [restore_firestore_data(item) for item in data]
    else:
        return data

if __name__ == "__main__":
    restore_promises_backup()
