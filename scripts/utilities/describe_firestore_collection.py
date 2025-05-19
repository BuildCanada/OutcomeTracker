import os
import sys
import firebase_admin
from firebase_admin import credentials, firestore
from dotenv import load_dotenv

load_dotenv()

# --- Firebase Initialization ---
if not firebase_admin._apps:
    if os.getenv('FIRESTORE_EMULATOR_HOST'):
        options = {'projectId': os.getenv('FIREBASE_PROJECT_ID', 'promisetrackerapp')}
        firebase_admin.initialize_app(options=options)
    else:
        cred_path = os.getenv('GOOGLE_APPLICATION_CREDENTIALS')
        if not cred_path:
            print("GOOGLE_APPLICATION_CREDENTIALS not set.")
            sys.exit(1)
        cred = credentials.Certificate(cred_path)
        firebase_admin.initialize_app(cred)

db = firestore.client()

def collect_fields(doc, prefix=""):
    fields = set()
    if isinstance(doc, dict):
        for k, v in doc.items():
            full_key = f"{prefix}.{k}" if prefix else k
            fields.add(full_key)
            if isinstance(v, dict):
                fields |= collect_fields(v, full_key)
            elif isinstance(v, list):
                for item in v:
                    if isinstance(item, dict):
                        fields |= collect_fields(item, full_key)
    return fields

def scan_collection_recursive(collection_ref, path_prefix=""):
    all_fields = set()
    doc_count = 0
    for doc in collection_ref.stream():
        doc_count += 1
        doc_path = f"{path_prefix}/{doc.id}" if path_prefix else doc.id
        data = doc.to_dict()
        all_fields |= {f"{doc_path}:{field}" for field in collect_fields(data)}
        # Recursively scan all subcollections of this document
        for subcol_ref in doc.reference.collections():
            subcol_path = f"{doc_path}/{subcol_ref.id}"
            sub_fields, sub_docs = scan_collection_recursive(subcol_ref, subcol_path)
            all_fields |= sub_fields
            doc_count += sub_docs
    return all_fields, doc_count

def main():
    if len(sys.argv) < 2:
        print("Usage: python describe_firestore_collection.py <collection_path>")
        sys.exit(1)
    collection_path = sys.argv[1]
    print(f"Describing Firestore collection (with all nested subcollections): {collection_path}")
    # Start from the root collection
    collection_ref = db.collection(collection_path)
    all_fields, doc_count = scan_collection_recursive(collection_ref, collection_path)
    print(f"\nTotal documents (including all nested subcollections) scanned: {doc_count}")
    print(f"Unique fields (including nested, with path prefixes):")
    for field in sorted(all_fields):
        print(f"- {field}")

if __name__ == "__main__":
    main() 