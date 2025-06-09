import firebase_admin
from firebase_admin import firestore
import os
import json

def initialize_firestore():
    """Initializes the Firestore client."""
    project_id = os.getenv('FIREBASE_PROJECT_ID', 'promisetrackerapp')
    if not firebase_admin._apps:
        firebase_admin.initialize_app(options={'projectId': project_id})
    return firestore.client()

def check_promise_for_evidence(db, promise_id: str, expected_evidence_doc_id: str):
    """Checks if a promise document contains a link to a specific evidence item."""
    print(f"\n--- Checking Promise: {promise_id} ---")
    print(f"Expecting to find evidence: {expected_evidence_doc_id}")

    promise_ref = db.collection('promises').document(promise_id)
    promise_doc = promise_ref.get()

    if not promise_doc.exists:
        print("❌ ERROR: Promise document not found.")
        return

    promise_data = promise_doc.to_dict()
    linked_evidence_ids = promise_data.get('linked_evidence_ids', [])
    
    # The new evidence linker doesn't add to linked_evidence_ids directly.
    # It adds to the evidence_item's promise_ids.
    # A downstream job (progress scorer) is responsible for updating the promise.
    
    # For now, we will just check the evidence item itself.
    evidence_ref = db.collection('evidence_items').document(expected_evidence_doc_id)
    evidence_doc = evidence_ref.get()
    
    if not evidence_doc.exists:
        print(f"❌ ERROR: Evidence document {expected_evidence_doc_id} not found.")
        return

    evidence_data = evidence_doc.to_dict()
    linked_promise_ids = evidence_data.get('promise_ids', [])

    print(f"\n--- Checking Evidence: {expected_evidence_doc_id} ---")
    print(f"Found {len(linked_promise_ids)} linked promise(s).")

    if promise_id in linked_promise_ids:
        print(f"  ✅ SUCCESS: Evidence item '{expected_evidence_doc_id}' is correctly linked to promise '{promise_id}'.")
        print("\nNOTE: The promise document itself has not been updated yet. This is expected.")
        print("The next step in the pipeline is to run the progress scoring job, which will update the promise.")
    else:
        print(f"  ❌ FAILED: Evidence item '{expected_evidence_doc_id}' is NOT linked to promise '{promise_id}'.")

def main():
    """Main function to run the verification."""
    db = initialize_firestore()

    # Bill C-5, which should be linked to the promise below
    evidence_id = '20250606_45_LegisInfo_2668e088'
    
    # The promise that should be linked to Bill C-5
    promise_id = 'LPC_20250419_OTHER_21670141'

    check_promise_for_evidence(db, promise_id, evidence_id)

if __name__ == "__main__":
    main() 