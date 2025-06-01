#!/usr/bin/env python3
"""
Simple script to cleanup test collections
"""

import sys
from pathlib import Path

# Add the PromiseTracker directory to Python path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

import firebase_admin
from firebase_admin import firestore

def cleanup_test_collections():
    """Clean up test collections"""
    try:
        if not firebase_admin._apps:
            firebase_admin.initialize_app()
        
        db = firestore.client()
        
        # Delete test documents
        for collection_name in ['test_raw_orders_in_council', 'test_evidence_items']:
            docs = list(db.collection(collection_name).limit(100).stream())
            deleted_count = 0
            for doc in docs:
                doc.reference.delete()
                deleted_count += 1
            
            print(f'✓ Deleted {deleted_count} documents from {collection_name}')
        
        print('✅ Test collections cleared successfully!')
        
    except Exception as e:
        print(f'❌ Error cleaning collections: {e}')

if __name__ == "__main__":
    cleanup_test_collections() 