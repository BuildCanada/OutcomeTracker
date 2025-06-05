#!/usr/bin/env python3
from firebase_admin import firestore

"""
Test Firebase Connection

Simple script to test Firebase credentials and connectivity using the
standardized firebase_init_util.py module.

Usage: python scripts/test_firebase_connection.py
"""

import sys
import logging
from pathlib import Path
from dotenv import load_dotenv

# Add the scripts directory to the path
sys.path.append(str(Path(__file__).parent))
from firebase_init_util import get_firestore_client, log_firebase_info

# Load environment variables
load_dotenv()

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(name)s - %(message)s'
)
logger = logging.getLogger(__name__)

def test_firebase_connection():
    """Test Firebase connection and basic functionality."""
    print("🧪 Testing Firebase Connection")
    print("=" * 50)
    
    try:
        # Log current environment info
        print("\n📋 Environment Information:")
        log_firebase_info()
        
        # Initialize Firebase
        print("\n🔥 Initializing Firebase...")
        db = get_firestore_client("test_connection_app")
        print("✅ Firebase initialization successful!")
        
        # Test basic connectivity
        print("\n🔍 Testing basic connectivity...")
        collections = list(db.collections())
        print(f"✅ Found {len(collections)} collections in database:")
        for col in collections[:5]:  # Show first 5 collections
            print(f"   - {col.id}")
        if len(collections) > 5:
            print(f"   ... and {len(collections) - 5} more")
        
        # Test a specific collection query
        print("\n📊 Testing promises collection...")
        promises_ref = db.collection("promises")
        
        # Count total promises
        count_query = promises_ref.limit(1)
        count_snapshot = count_query.get()
        
        if count_snapshot:
            print("✅ Promises collection accessible")
            
            # Try to get a count with filters
            try:
                active_query = promises_ref.where(filter=firestore.FieldFilter('status', '==', 'active')).limit(5)
                active_docs = active_query.get()
                print(f"✅ Found {len(active_docs)} active promises (sample)")
            except Exception as e:
                print(f"⚠️  Advanced query test failed: {e}")
        else:
            print("⚠️  Promises collection exists but appears empty")
        
        print("\n🎉 All tests passed! Firebase is properly configured.")
        return True
        
    except Exception as e:
        print(f"\n❌ Firebase connection test failed: {e}")
        logger.error("Firebase test failed", exc_info=True)
        return False

def main():
    """Main test execution."""
    print("Firebase Connection Test")
    print("For PromiseTracker project\n")
    
    success = test_firebase_connection()
    
    if success:
        print("\n✅ Ready to run other scripts!")
        sys.exit(0)
    else:
        print("\n❌ Please check your Firebase configuration.")
        print("\nTroubleshooting tips:")
        print("1. Ensure you're in a Google Cloud environment with default credentials, OR")
        print("2. Set FIREBASE_SERVICE_ACCOUNT_KEY_PATH to your service account JSON file, OR")
        print("3. Set FIREBASE_SERVICE_ACCOUNT_KEY to your service account JSON as a string, OR") 
        print("4. Set GOOGLE_APPLICATION_CREDENTIALS to your service account JSON file")
        print("5. Set FIREBASE_PROJECT_ID if not included in your service account file")
        sys.exit(1)

if __name__ == "__main__":
    main() 