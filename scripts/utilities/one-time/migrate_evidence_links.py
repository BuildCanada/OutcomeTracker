import firebase_admin
from firebase_admin import firestore
import os
from typing import List, Dict, Any

def initialize_firestore():
    """Initializes the Firestore client."""
    project_id = os.getenv('FIREBASE_PROJECT_ID', 'promisetrackerapp')
    if not firebase_admin._apps:
        firebase_admin.initialize_app(options={'projectId': project_id})
    return firestore.client()

def backfill_promise_links(db):
    """
    Goes through all evidence items and ensures their IDs are in the
    'linked_evidence_ids' field of the promises they link to.
    This version uses pagination to avoid timeouts on large collections.
    """
    print("--- Starting Step 1: Backfilling 'linked_evidence_ids' ---")
    evidence_collection = db.collection('evidence_items')
    promises_collection = db.collection('promises')
    
    page_size = 500
    last_doc = None
    total_evidence_count = 0
    total_updates_made = 0

    while True:
        query = evidence_collection.order_by('__name__').limit(page_size)
        if last_doc:
            query = query.start_after(last_doc)

        docs = list(query.stream())
        if not docs:
            break

        page_evidence_count = 0
        page_updates_made = 0

        for evidence in docs:
            total_evidence_count += 1
            page_evidence_count += 1
            last_doc = evidence # Set the cursor for the next page

            evidence_data = evidence.to_dict()
            evidence_id = evidence.id
            promise_ids = evidence_data.get('promise_ids', [])

            if not promise_ids:
                continue
            
            # Use a batch to update promises for this single evidence item
            batch = db.batch()
            for promise_id in promise_ids:
                try:
                    promise_ref = promises_collection.document(promise_id)
                    batch.update(promise_ref, {
                        'linked_evidence_ids': firestore.ArrayUnion([evidence_id])
                    })
                except Exception as e:
                    print(f"  -> ERROR queueing update for promise {promise_id}: {e}")
            
            try:
                batch.commit()
                page_updates_made += len(promise_ids)
                total_updates_made += len(promise_ids)
                print(f"  -> Processed evidence {evidence_id}, linking to {len(promise_ids)} promises.")
            except Exception as e:
                print(f"  -> ERROR committing batch for evidence {evidence_id}: {e}")

        print(f"\n--- Processed a page: {page_evidence_count} evidence items, {page_updates_made} promise links updated ---\n")
        if len(docs) < page_size:
            break # Reached the end

    print(f"\n--- Step 1 Complete ---")
    print(f"Processed {total_evidence_count} evidence items in total.")
    print(f"Performed {total_updates_made} promise update operations.")

def remove_old_linked_evidence_field(db):
    """
    Removes the old, inconsistent 'linked_evidence' field from all promise documents.
    """
    print("\n--- Starting Step 2: Removing 'linked_evidence' field ---")
    promises_collection = db.collection('promises')
    
    # We can't query for field existence directly in a way that's efficient for deletion.
    # We will iterate through all promises and delete the field if it exists.
    # This is slow but necessary for a one-time migration.
    
    page_size = 500
    last_doc = None
    promises_processed = 0
    deletions_made = 0

    while True:
        query = promises_collection.order_by('__name__').limit(page_size)
        if last_doc:
            query = query.start_after(last_doc)

        docs = list(query.stream())
        if not docs:
            break
        
        last_doc = docs[-1]
        batch = db.batch()
        batch_counter = 0

        for promise_doc in docs:
            promises_processed += 1
            promise_data = promise_doc.to_dict()
            if 'linked_evidence' in promise_data:
                promise_ref = promises_collection.document(promise_doc.id)
                batch.update(promise_ref, {
                    'linked_evidence': firestore.DELETE_FIELD
                })
                batch_counter += 1
                deletions_made += 1
        
        if batch_counter > 0:
            batch.commit()
            print(f"  -> Processed page: checked {len(docs)} promises, removed field from {batch_counter}.")

    print(f"\n--- Step 2 Complete ---")
    print(f"Scanned {promises_processed} documents and removed 'linked_evidence' field from {deletions_made} of them.")

def main():
    """Main function to run the migration."""
    db = initialize_firestore()
    
    print("Starting data migration for evidence links. This is a two-step process.")
    
    # Step 1: Ensure all links are correctly backfilled into 'linked_evidence_ids'
    backfill_promise_links(db)
    
    # Step 2: Remove the old 'linked_evidence' field
    remove_old_linked_evidence_field(db)
    
    print("\n✅ Migration complete. The `linked_evidence_ids` field is now the source of truth.")

if __name__ == "__main__":
    main() 