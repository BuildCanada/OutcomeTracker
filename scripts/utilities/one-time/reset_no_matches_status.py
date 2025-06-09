import sys
import os
from pathlib import Path
from google.cloud import firestore
from google.cloud.firestore_v1.base_query import FieldFilter

# Add project root to sys.path to allow for imports if needed in the future
project_root = Path(__file__).resolve().parent.parent.parent.parent
sys.path.append(str(project_root))

def reset_evidence_status():
    """
    Connects to Firestore and updates evidence items with 'no_matches' status.

    Finds all documents in the 'evidence_items' collection where the
    'promise_linking_status' is 'no_matches' and updates it to 'pending'
    to allow for reprocessing by the evidence_linker pipeline.
    """
    try:
        # Load environment variables for local development, which is necessary
        # for the gcloud SDK to find the credentials for Firestore.
        from dotenv import load_dotenv
        env_path = project_root / '.env'
        if env_path.exists():
            print(f"📋 Loading environment from: {env_path}")
            load_dotenv(env_path)
        else:
            print(f"📋 .env file not found at {env_path}, relying on system environment variables.")
    except ImportError:
        print("📋 python-dotenv not available, skipping .env file loading.")

    try:
        print("Connecting to Firestore...")
        # The Firestore client will automatically use the credentials from the
        # environment, which gcloud sets up or are loaded from the .env file.
        db = firestore.Client()
        print("✅ Firestore connection successful.")
    except Exception as e:
        print(f"❌ Failed to connect to Firestore: {e}")
        return

    evidence_collection = db.collection('evidence_items')
    # Use FieldFilter for modern, warning-free queries
    query = evidence_collection.where(filter=FieldFilter('promise_linking_status', '==', 'no_matches'))

    print("Querying for evidence items with status 'no_matches'...")
    docs_to_update = list(query.stream())

    if not docs_to_update:
        print("✅ No evidence items with status 'no_matches' found. Nothing to do.")
        return

    print(f"Found {len(docs_to_update)} items to reset. Starting update in batches...")

    total_updated = 0
    # Firestore batch limit is 500. Using a smaller size for safety and progress feedback.
    batch_size = 100

    for i in range(0, len(docs_to_update), batch_size):
        batch = db.batch()
        end_index = i + batch_size
        doc_batch = docs_to_update[i:end_index]

        for doc in doc_batch:
            batch.update(doc.reference, {'promise_linking_status': 'pending'})

        try:
            batch.commit()
            total_updated += len(doc_batch)
            print(f"  ...updated batch {i//batch_size + 1}, {total_updated}/{len(docs_to_update)} items processed.")
        except Exception as e:
            print(f"❌ Error committing batch: {e}")
            print("Aborting script.")
            return

    print("\n" + "="*30)
    print("🎉 Update Complete!")
    print(f"Total items reset to 'pending': {total_updated}")
    print("="*30)


if __name__ == "__main__":
    reset_evidence_status()
