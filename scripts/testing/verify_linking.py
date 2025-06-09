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

def verify_document_links(db, collection, doc_id):
    """Fetches a document and prints its linking status and promise IDs."""
    print(f"--- Verifying: {doc_id} ---")
    doc_ref = db.collection(collection).document(doc_id)
    doc = doc_ref.get()
    
    if not doc.exists:
        print(f"ERROR: Document not found.")
        return False

    data = doc.to_dict()
    status = data.get('promise_linking_status', 'N/A')
    links_found = data.get('promise_links_found', 0)
    promise_ids = data.get('promise_ids', [])
    
    print(f"  Status: {status}")
    print(f"  Links Found: {links_found}")
    print(f"  Promise IDs: {json.dumps(promise_ids, indent=2)}")
    
    if status == 'processed' and links_found > 0 and promise_ids:
        print("  ✅ VERIFICATION SUCCESS: Document appears to be linked correctly.")
        return True
    else:
        print("  ❌ VERIFICATION FAILED: Document is not linked as expected.")
        return False

def main():
    """Fetches specific evidence documents to verify linking."""
    db = initialize_firestore()
    evidence_collection = 'evidence_items'

    # Evidence IDs to verify
    bill_c4_id = '20250606_45-1_LegisInfo_1cbf1484'
    bill_c5_id = '20250606_45_LegisInfo_2668e088'

    print("Running verification for evidence linking...")
    c4_success = verify_document_links(db, evidence_collection, bill_c4_id)
    c5_success = verify_document_links(db, evidence_collection, bill_c5_id)
    
    print("\n--- Summary ---")
    if c4_success and c5_success:
        print("✅ Great success! Both evidence items were successfully processed and linked.")
    else:
        print("❌ One or more evidence items were not linked correctly. Please review the logs above.")

if __name__ == "__main__":
    main() 