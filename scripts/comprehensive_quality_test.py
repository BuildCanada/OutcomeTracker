#!/usr/bin/env python3
"""
Comprehensive quality test for the fixed enrichment script.
Tests all enrichment types: explanation, keywords, action types.
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
        "text": data.get('text', 'N/A')[:100] + "..." if len(data.get('text', '')) > 100 else data.get('text', 'N/A'),
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

def run_fixed_enrichment_comprehensive():
    """Run the fixed enrichment script with all enrichment types."""
    logger.info("Running comprehensive fixed enrichment script...")
    
    cmd = [
        'python', 'consolidated_promise_enrichment_fixed.py',
        '--parliament_session_id', '44',
        '--source_type', '2021 LPC Mandate Letters',
        '--limit', '2',
        '--force_reprocessing',
        '--enrichment_types', 'all',
        '--batch_size', '2'
    ]
    
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
        if result.returncode == 0:
            logger.info("Comprehensive fixed enrichment completed successfully")
            logger.info(f"Output: {result.stdout}")
            return True
        else:
            logger.error(f"Comprehensive fixed enrichment failed: {result.stderr}")
            logger.error(f"Stdout: {result.stdout}")
            return False
    except subprocess.TimeoutExpired:
        logger.error("Comprehensive fixed enrichment timed out")
        return False

def validate_field_structure(enriched):
    """Validate the field structure of an enriched promise."""
    issues = []
    successes = []
    
    # Check what_it_means_for_canadians
    if enriched['what_it_means_for_canadians'] != 'N/A':
        if not isinstance(enriched['what_it_means_for_canadians'], list):
            issues.append("❌ what_it_means_for_canadians should be an array")
        else:
            successes.append(f"✅ what_it_means_for_canadians is array with {len(enriched['what_it_means_for_canadians'])} items")
    
    # Check description
    if enriched['description'] != 'N/A':
        if not isinstance(enriched['description'], str):
            issues.append("❌ description should be a string")
        else:
            successes.append(f"✅ description is string ({len(enriched['description'])} chars)")
    
    # Check background_and_context
    if enriched['background_and_context'] != 'N/A':
        if not isinstance(enriched['background_and_context'], str):
            issues.append("❌ background_and_context should be a string")
        else:
            successes.append(f"✅ background_and_context is string ({len(enriched['background_and_context'])} chars)")
    
    # Check extracted_keywords_concepts
    if enriched['extracted_keywords_concepts'] != 'N/A':
        if not isinstance(enriched['extracted_keywords_concepts'], list):
            issues.append("❌ extracted_keywords_concepts should be an array")
        else:
            successes.append(f"✅ extracted_keywords_concepts is array with {len(enriched['extracted_keywords_concepts'])} items")
    
    # Check implied_action_type
    if enriched['implied_action_type'] != 'N/A':
        if not isinstance(enriched['implied_action_type'], str):
            issues.append("❌ implied_action_type should be a string")
        else:
            successes.append(f"✅ implied_action_type is string: '{enriched['implied_action_type']}'")
    
    return issues, successes

def main():
    """Main function."""
    db = initialize_firebase()
    
    # Test promises
    test_promise_ids = [
        "20211216_MANDL_00638bafc9",  # NATO Climate Security Centre
        "20211216_MANDL_00f67326c0"   # Sexual Misconduct Response Centre
    ]
    
    print("=== COMPREHENSIVE QUALITY TEST FOR FIXED ENRICHMENT ===")
    print(f"Testing {len(test_promise_ids)} promises with ALL enrichment types")
    
    # Step 1: Reset enrichment fields
    print("\n=== STEP 1: Resetting Enrichment Fields ===")
    for promise_id in test_promise_ids:
        reset_promise_enrichment(db, promise_id)
    
    # Step 2: Run comprehensive fixed enrichment
    print("\n=== STEP 2: Running Comprehensive Fixed Enrichment ===")
    enrichment_success = run_fixed_enrichment_comprehensive()
    
    if not enrichment_success:
        print("❌ Comprehensive fixed enrichment failed. Cannot continue with test.")
        return
    
    # Step 3: Get enriched data
    print("\n=== STEP 3: Getting Enriched Promise Data ===")
    enriched_data = []
    for promise_id in test_promise_ids:
        data = get_promise_data(db, promise_id)
        if data:
            enriched_data.append(data)
        else:
            logger.error(f"Could not find enriched promise {promise_id}")
    
    # Step 4: Comprehensive field structure analysis
    print("\n=== STEP 4: Comprehensive Field Structure Analysis ===")
    
    overall_issues = []
    overall_successes = []
    
    for i, promise_id in enumerate(test_promise_ids):
        if i < len(enriched_data):
            enriched = enriched_data[i]
            
            print(f"\n--- Promise: {promise_id} ---")
            print(f"Text: {enriched['text']}")
            print(f"Concise Title: {enriched['concise_title']}")
            
            # Validate structure
            issues, successes = validate_field_structure(enriched)
            
            for success in successes:
                print(f"  {success}")
                overall_successes.append(success)
            
            if issues:
                print("⚠️ Field Structure Issues:")
                for issue in issues:
                    print(f"  {issue}")
                    overall_issues.append(issue)
            
            # Check enrichment timestamps
            enrichment_status = []
            if enriched['explanation_enriched_at'] != 'N/A':
                enrichment_status.append("✅ Explanation processed")
            else:
                enrichment_status.append("❌ Explanation NOT processed")
            
            if enriched['keywords_enriched_at'] != 'N/A':
                enrichment_status.append("✅ Keywords processed")
            else:
                enrichment_status.append("❌ Keywords NOT processed")
            
            if enriched['action_type_enriched_at'] != 'N/A':
                enrichment_status.append("✅ Action type processed")
            else:
                enrichment_status.append("❌ Action type NOT processed")
            
            print(f"Processing Status: {', '.join(enrichment_status)}")
    
    # Step 5: Overall assessment
    print("\n=== STEP 5: Overall Quality Assessment ===")
    
    print(f"✅ Total Successes: {len(overall_successes)}")
    print(f"❌ Total Issues: {len(overall_issues)}")
    
    if len(overall_issues) == 0:
        print("🎉 PERFECT! All field structures are correct!")
    elif len(overall_issues) <= 2:
        print("✨ GOOD! Minor issues that can be easily fixed.")
    else:
        print("⚠️ NEEDS WORK! Multiple structural issues detected.")
    
    # Output detailed JSON for inspection
    output_file = f"comprehensive_quality_test_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump({
            "test_timestamp": datetime.now().isoformat(),
            "promises_tested": len(test_promise_ids),
            "enriched_promises": enriched_data,
            "overall_successes": overall_successes,
            "overall_issues": overall_issues,
            "quality_score": f"{len(overall_successes)} successes / {len(overall_issues)} issues"
        }, f, indent=2, ensure_ascii=False)
    
    print(f"\n📄 Detailed test results saved to: {output_file}")
    print("\n✅ Comprehensive quality test complete!")

if __name__ == "__main__":
    main() 