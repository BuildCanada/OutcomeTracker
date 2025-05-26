#!/usr/bin/env python3
"""
Test script for the fixed enrichment to validate field structure.
"""

import sys
import os
sys.path.append('..')

import firebase_admin
from firebase_admin import credentials, firestore
import logging
import json
from datetime import datetime
import subprocess

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

def reset_promise_enrichment(db, promise_id):
    """Reset enrichment fields for a promise."""
    fields_to_reset = [
        'explanation_enriched_at',
        'explanation_enrichment_model',
        'explanation_enrichment_status',
        'what_it_means_for_canadians',
        'background_and_context',
        'description',
        'concise_title',
        'keywords_enriched_at',
        'keywords_enrichment_model', 
        'keywords_enrichment_status',
        'extracted_keywords_concepts',
        'action_type_enriched_at',
        'action_type_enrichment_model',
        'action_type_enrichment_status',
        'implied_action_type',
        'last_enrichment_at'
    ]
    
    logger.info(f"Resetting enrichment fields for promise {promise_id}")
    
    promise_ref = db.collection('promises').document(promise_id)
    
    # Create update dict to remove fields
    update_data = {}
    for field in fields_to_reset:
        update_data[field] = firestore.DELETE_FIELD
    
    promise_ref.update(update_data)
    logger.info(f"Reset {len(fields_to_reset)} fields for promise {promise_id}")

def get_promise_data(db, promise_id):
    """Get promise data for inspection."""
    doc = db.collection('promises').document(promise_id).get()
    if not doc.exists:
        return None
    
    data = doc.to_dict()
    
    # Extract key fields for structure inspection
    return {
        "id": promise_id,
        "text": data.get('text', 'N/A'),
        "concise_title": data.get('concise_title', 'N/A'),
        "what_it_means_for_canadians": data.get('what_it_means_for_canadians', 'N/A'),
        "description": data.get('description', 'N/A'),
        "background_and_context": data.get('background_and_context', 'N/A'),
        "extracted_keywords_concepts": data.get('extracted_keywords_concepts', 'N/A'),
        "implied_action_type": data.get('implied_action_type', 'N/A'),
        "explanation_enriched_at": str(data.get('explanation_enriched_at', 'N/A')),
        "keywords_enriched_at": str(data.get('keywords_enriched_at', 'N/A')),
        "action_type_enriched_at": str(data.get('action_type_enriched_at', 'N/A'))
    }

def run_fixed_enrichment():
    """Run the fixed enrichment script."""
    logger.info("Running fixed enrichment script...")
    
    cmd = [
        'python', 'consolidated_promise_enrichment_fixed.py',
        '--parliament_session_id', '44',
        '--source_type', '2021 LPC Mandate Letters',
        '--limit', '2',
        '--force_reprocessing',
        '--enrichment_types', 'explanation',
        '--batch_size', '2'
    ]
    
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
        if result.returncode == 0:
            logger.info("Fixed enrichment completed successfully")
            return True
        else:
            logger.error(f"Fixed enrichment failed: {result.stderr}")
            logger.error(f"Stdout: {result.stdout}")
            return False
    except subprocess.TimeoutExpired:
        logger.error("Fixed enrichment timed out")
        return False

def main():
    """Main function."""
    db = initialize_firebase()
    
    # Test promises
    test_promise_ids = [
        "20211216_MANDL_00638bafc9",  # NATO Climate Security Centre
        "20211216_MANDL_00f67326c0"   # Second promise
    ]
    
    print("=== TESTING FIXED ENRICHMENT SCRIPT ===")
    print(f"Testing {len(test_promise_ids)} promises")
    
    # Step 1: Get original data for comparison
    print("\n=== STEP 1: Getting Original Promise Data ===")
    original_data = []
    for promise_id in test_promise_ids:
        data = get_promise_data(db, promise_id)
        if data:
            original_data.append(data)
        else:
            logger.error(f"Could not find promise {promise_id}")
    
    # Step 2: Reset enrichment fields
    print("\n=== STEP 2: Resetting Enrichment Fields ===")
    for promise_id in test_promise_ids:
        reset_promise_enrichment(db, promise_id)
    
    # Step 3: Run fixed enrichment
    print("\n=== STEP 3: Running Fixed Enrichment ===")
    enrichment_success = run_fixed_enrichment()
    
    if not enrichment_success:
        print("❌ Fixed enrichment failed. Cannot continue with test.")
        return
    
    # Step 4: Get enriched data
    print("\n=== STEP 4: Getting Enriched Promise Data ===")
    enriched_data = []
    for promise_id in test_promise_ids:
        data = get_promise_data(db, promise_id)
        if data:
            enriched_data.append(data)
        else:
            logger.error(f"Could not find enriched promise {promise_id}")
    
    # Step 5: Analyze field structure
    print("\n=== STEP 5: Field Structure Analysis ===")
    
    for i, promise_id in enumerate(test_promise_ids):
        if i < len(enriched_data):
            enriched = enriched_data[i]
            
            print(f"\n--- Promise: {promise_id} ---")
            print(f"Text: {enriched['text'][:100]}...")
            print(f"Concise Title: {enriched['concise_title']}")
            print(f"What it Means Type: {type(enriched['what_it_means_for_canadians'])}")
            print(f"Description Type: {type(enriched['description'])}")
            print(f"Background Type: {type(enriched['background_and_context'])}")
            print(f"Keywords Type: {type(enriched['extracted_keywords_concepts'])}")
            print(f"Action Type: {enriched['implied_action_type']}")
            
            # Check if fields are proper types
            issues = []
            if enriched['what_it_means_for_canadians'] != 'N/A':
                if not isinstance(enriched['what_it_means_for_canadians'], list):
                    issues.append("❌ what_it_means_for_canadians should be an array")
                else:
                    print(f"✅ what_it_means_for_canadians is array with {len(enriched['what_it_means_for_canadians'])} items")
            
            if enriched['description'] != 'N/A':
                if not isinstance(enriched['description'], str):
                    issues.append("❌ description should be a string")
                else:
                    print(f"✅ description is string ({len(enriched['description'])} chars)")
            
            if enriched['extracted_keywords_concepts'] != 'N/A':
                if not isinstance(enriched['extracted_keywords_concepts'], list):
                    issues.append("❌ extracted_keywords_concepts should be an array")
                else:
                    print(f"✅ extracted_keywords_concepts is array with {len(enriched['extracted_keywords_concepts'])} items")
            
            if issues:
                print("⚠️ Field Structure Issues:")
                for issue in issues:
                    print(f"  {issue}")
            else:
                print("✅ All fields have correct structure!")
    
    # Output detailed JSON for inspection
    output_file = f"fixed_enrichment_test_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump({
            "test_timestamp": datetime.now().isoformat(),
            "promises_tested": len(test_promise_ids),
            "enriched_promises": enriched_data
        }, f, indent=2, ensure_ascii=False)
    
    print(f"\n📄 Detailed test results saved to: {output_file}")
    print("\n✅ Fixed enrichment test complete!")

if __name__ == "__main__":
    main() 