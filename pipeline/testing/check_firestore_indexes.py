#!/usr/bin/env python3
"""
Check Firestore Indexes Status

This script checks if the required composite indexes for the processing pipeline are ready.
Use this to verify indexes are built before running processing tests.

Usage:
    python check_firestore_indexes.py
"""

import sys
import logging
from pathlib import Path

# Add pipeline directory to path
pipeline_dir = Path(__file__).parent.parent
sys.path.insert(0, str(pipeline_dir))

import firebase_admin
from firebase_admin import firestore
from google.cloud.firestore_v1.base_collection import BaseCollectionReference


def setup_firebase():
    """Initialize Firebase connection"""
    try:
        if not firebase_admin._apps:
            firebase_admin.initialize_app()
        return firestore.client()
    except Exception as e:
        print(f"❌ Failed to initialize Firebase: {e}")
        sys.exit(1)


def test_collection_query(db: firestore.Client, collection_name: str) -> bool:
    """
    Test if we can query a collection with the required composite index.
    
    Args:
        db: Firestore client
        collection_name: Name of collection to test
        
    Returns:
        True if index is ready, False if not
    """
    try:
        # Try the exact query that processing jobs use (modern syntax)
        query = (db.collection(collection_name)
                .where(filter=firestore.FieldFilter("evidence_processing_status", "==", "pending_evidence_creation"))
                .order_by("last_updated_at")
                .limit(1))
        
        # Execute query - this will fail if index doesn't exist
        docs = list(query.stream())
        
        print(f"✅ {collection_name}: Index ready ({len(docs)} items found)")
        return True
        
    except Exception as e:
        if "requires an index" in str(e):
            print(f"❌ {collection_name}: Index not ready - {str(e)[:100]}...")
            return False
        else:
            print(f"⚠️ {collection_name}: Query error - {e}")
            return False


def check_all_indexes():
    """Check all required indexes for the processing pipeline"""
    
    print("🔍 Checking Firestore indexes for Promise Tracker pipeline...")
    print("=" * 60)
    
    # Initialize Firebase
    db = setup_firebase()
    
    # Collections that need indexes
    required_collections = [
        "raw_news_releases",
        "raw_legisinfo_bill_details", 
        "raw_orders_in_council",
        "raw_gazette_p2_notices"
    ]
    
    results = {}
    all_ready = True
    
    for collection in required_collections:
        is_ready = test_collection_query(db, collection)
        results[collection] = is_ready
        if not is_ready:
            all_ready = False
    
    print("\n" + "=" * 60)
    print("📊 INDEX STATUS SUMMARY")
    print("=" * 60)
    
    for collection, is_ready in results.items():
        status = "✅ READY" if is_ready else "❌ NOT READY"
        print(f"{collection:<30} {status}")
    
    if all_ready:
        print("\n🎉 All indexes are ready! Processing pipeline can run.")
        print("You can now proceed with:")
        print("  python pipeline_validation.py --component processing")
        return True
    else:
        print("\n⏳ Some indexes are still building. Please wait and try again.")
        print("Index creation typically takes 1-5 minutes per collection.")
        print("\nTo create missing indexes, see:")
        print("  pipeline/testing/create_firestore_indexes.md")
        return False


def main():
    """Main entry point"""
    try:
        all_ready = check_all_indexes()
        sys.exit(0 if all_ready else 1)
    except KeyboardInterrupt:
        print("\n🛑 Check interrupted by user")
        sys.exit(130)
    except Exception as e:
        print(f"💥 Check failed with error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main() 