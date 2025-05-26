#!/usr/bin/env python3
"""
Full Document Inspection Script
Outputs ALL fields from processed promises for complete inspection.
"""

import sys
import os
sys.path.append('..')

import firebase_admin
from firebase_admin import credentials, firestore
import logging
import json
from datetime import datetime

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def initialize_firebase():
    """Initialize Firebase if not already initialized."""
    try:
        app = firebase_admin.get_app()
        logger.info("Firebase already initialized")
    except ValueError:
        cred = credentials.ApplicationDefault()
        app = firebase_admin.initialize_app(cred)
        logger.info("Firebase initialized")
    
    return firestore.client()

def get_full_promise_data(db, promise_id):
    """Get ALL promise data for complete inspection."""
    doc = db.collection('promises').document(promise_id).get()
    if not doc.exists:
        return None
    
    data = doc.to_dict()
    
    # Convert timestamps to strings for JSON serialization
    for key, value in data.items():
        if hasattr(value, 'timestamp'):  # Firestore timestamp
            data[key] = value.isoformat()
        elif str(type(value)) == "<class 'google.cloud.firestore_v1.base_document.DatetimeWithNanoseconds'>":
            data[key] = str(value)
    
    return data

def compare_with_reference(db, processed_ids, reference_id):
    """Compare processed documents with a reference document to see missing fields."""
    
    # Get reference document
    reference_doc = get_full_promise_data(db, reference_id)
    if not reference_doc:
        logger.error(f"Could not find reference document {reference_id}")
        return
    
    # Get processed documents
    processed_docs = []
    for promise_id in processed_ids:
        doc_data = get_full_promise_data(db, promise_id)
        if doc_data:
            processed_docs.append(doc_data)
    
    # Analyze field differences
    reference_fields = set(reference_doc.keys())
    
    print(f"\n=== REFERENCE DOCUMENT ANALYSIS ===")
    print(f"Reference: {reference_id}")
    print(f"Total fields in reference: {len(reference_fields)}")
    
    print(f"\n=== PROCESSED DOCUMENTS ANALYSIS ===")
    
    for i, doc in enumerate(processed_docs):
        doc_id = processed_ids[i]
        processed_fields = set(doc.keys())
        
        missing_fields = reference_fields - processed_fields
        extra_fields = processed_fields - reference_fields
        
        print(f"\n--- Document: {doc_id} ---")
        print(f"Total fields: {len(processed_fields)}")
        print(f"Missing fields ({len(missing_fields)}): {sorted(missing_fields)}")
        print(f"Extra fields ({len(extra_fields)}): {sorted(extra_fields)}")
        
        # Check for important Build Canada fields specifically
        bc_fields = [
            'bc_promise_direction',
            'bc_promise_rank', 
            'bc_promise_rank_rationale',
            'progress_score',
            'progress_summary',
            'intended_impact_and_objectives'
        ]
        
        missing_bc_fields = [f for f in bc_fields if f not in processed_fields]
        if missing_bc_fields:
            print(f"⚠️ Missing Build Canada fields: {missing_bc_fields}")
    
    return {
        "reference_document": reference_doc,
        "processed_documents": processed_docs,
        "field_analysis": {
            "reference_id": reference_id,
            "reference_field_count": len(reference_fields),
            "processed_comparisons": [
                {
                    "id": processed_ids[i],
                    "field_count": len(processed_docs[i].keys()),
                    "missing_fields": sorted(reference_fields - set(processed_docs[i].keys())),
                    "extra_fields": sorted(set(processed_docs[i].keys()) - reference_fields)
                }
                for i in range(len(processed_docs))
            ]
        }
    }

def main():
    """Main function."""
    db = initialize_firebase()
    
    # Documents to inspect
    processed_promise_ids = [
        "20211216_MANDL_00638bafc9",  # NATO Climate Security Centre
        "20211216_MANDL_00f67326c0"   # Sexual Misconduct Response Centre
    ]
    
    # Reference document with all expected fields
    reference_promise_id = "20211216_MANDL_0cebaddb7c"  # Critical minerals promise
    
    print("=== FULL DOCUMENT INSPECTION ===")
    print(f"Inspecting {len(processed_promise_ids)} processed documents")
    print(f"Reference document: {reference_promise_id}")
    
    # Perform comparison
    analysis = compare_with_reference(db, processed_promise_ids, reference_promise_id)
    
    if not analysis:
        print("❌ Analysis failed")
        return
    
    # Output comprehensive JSON
    output_file = f"full_document_inspection_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(analysis, f, indent=2, ensure_ascii=False)
    
    print(f"\n📄 Complete document analysis saved to: {output_file}")
    
    # Show key Build Canada fields from reference
    ref_doc = analysis["reference_document"]
    print(f"\n=== BUILD CANADA FIELDS IN REFERENCE ===")
    bc_fields = [
        'bc_promise_direction',
        'bc_promise_rank', 
        'bc_promise_rank_rationale',
        'progress_score',
        'progress_summary',
        'intended_impact_and_objectives'
    ]
    
    for field in bc_fields:
        if field in ref_doc:
            value = ref_doc[field]
            if isinstance(value, str) and len(value) > 100:
                value = value[:100] + "..."
            print(f"  {field}: {value}")
        else:
            print(f"  {field}: [NOT FOUND]")
    
    print("\n✅ Full document inspection complete!")

if __name__ == "__main__":
    main() 