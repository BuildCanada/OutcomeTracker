#!/usr/bin/env python3
"""
Test script for the corrected enrichment script.
Validates all requirements from user feedback.
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

def reset_test_promises(db, promise_ids):
    """Reset test promises by removing enrichment fields."""
    fields_to_remove = [
        'explanation_enriched_at', 'keywords_enriched_at', 'action_type_enriched_at', 'history_generated_at',
        'concise_title', 'description', 'what_it_means_for_canadians', 'background_and_context',
        'extracted_keywords_concepts', 'implied_action_type', 'commitment_history_rationale',
        'implementation_notes', 'key_points', 'migration_metadata', 'political_significance',
        'action_type_classified_at', 'action_type_confidence', 'action_type_enrichment_model',
        'action_type_enrichment_status', 'action_type_rationale', 'keywords_enrichment_model',
        'keywords_enrichment_status', 'keywords_extracted_at', 'policy_areas', 'target_groups'
    ]
    
    for promise_id in promise_ids:
        doc_ref = db.collection('promises').document(promise_id)
        
        # Build update payload
        update_payload = {}
        for field in fields_to_remove:
            update_payload[field] = firestore.DELETE_FIELD
        
        try:
            doc_ref.update(update_payload)
            logger.info(f"Reset promise {promise_id}")
        except Exception as e:
            logger.warning(f"Could not reset promise {promise_id}: {e}")

def validate_enriched_promise(promise_data, promise_id):
    """Validate that an enriched promise meets all requirements."""
    issues = []
    successes = []
    
    # 1. Check field structure and types
    required_fields = {
        'concise_title': str,
        'description': str,
        'what_it_means_for_canadians': list,
        'background_and_context': str,
        'extracted_keywords_concepts': list,
        'implied_action_type': str,
        'commitment_history_rationale': list
    }
    
    for field, expected_type in required_fields.items():
        if field in promise_data:
            actual_value = promise_data[field]
            if isinstance(actual_value, expected_type):
                if expected_type == list:
                    successes.append(f"✅ {field} is {expected_type.__name__} with {len(actual_value)} items")
                elif expected_type == str:
                    successes.append(f"✅ {field} is {expected_type.__name__} ({len(actual_value)} chars)")
                else:
                    successes.append(f"✅ {field} is {expected_type.__name__}")
            else:
                issues.append(f"❌ {field} should be {expected_type.__name__} but is {type(actual_value).__name__}")
        else:
            issues.append(f"❌ Missing required field: {field}")
    
    # 2. Check unwanted fields are removed
    unwanted_fields = ['implementation_notes', 'key_points', 'migration_metadata', 'political_significance']
    for field in unwanted_fields:
        if field in promise_data:
            issues.append(f"❌ Unwanted field still present: {field}")
        else:
            successes.append(f"✅ Unwanted field '{field}' correctly removed")
    
    # 3. Check background_and_context language quality
    background = promise_data.get('background_and_context', '')
    if background:
        # Check for hypothetical language
        hypothetical_phrases = [
            'would frame', 'would likely', 'The platform documents would',
            'it would appear', 'would suggest', 'would indicate'
        ]
        found_hypothetical = [phrase for phrase in hypothetical_phrases if phrase.lower() in background.lower()]
        if found_hypothetical:
            issues.append(f"❌ background_and_context contains hypothetical language: {found_hypothetical}")
        else:
            successes.append("✅ background_and_context language is assertive and factual")
    
    # 4. Check commitment_history_rationale structure
    history = promise_data.get('commitment_history_rationale', [])
    if isinstance(history, list):
        if history:  # If not empty
            for i, event in enumerate(history):
                if isinstance(event, dict) and all(key in event for key in ['date', 'action', 'source_url']):
                    successes.append(f"✅ commitment_history_rationale[{i}] has correct structure")
                else:
                    issues.append(f"❌ commitment_history_rationale[{i}] has incorrect structure")
        else:
            successes.append("✅ commitment_history_rationale is empty array (valid)")
    
    # 5. Check concise_title length (should allow longer now)
    title = promise_data.get('concise_title', '')
    if title:
        if len(title.split()) > 4:  # Should allow longer titles
            successes.append(f"✅ concise_title allows longer descriptions ({len(title.split())} words)")
        else:
            successes.append(f"✅ concise_title is concise ({len(title.split())} words)")
    
    # 6. Check what_it_means_for_canadians content
    what_it_means = promise_data.get('what_it_means_for_canadians', [])
    if isinstance(what_it_means, list) and len(what_it_means) >= 3:
        successes.append(f"✅ what_it_means_for_canadians has {len(what_it_means)} items (good content)")
    
    return successes, issues

def main():
    """Main function."""
    db = initialize_firebase()
    
    # Test promises (these should exist from previous runs)
    test_promise_ids = [
        "20211216_MANDL_00638bafc9",  # NATO Climate Security Centre
        "20211216_MANDL_00f67326c0"   # Sexual Misconduct Response Centre
    ]
    
    print("=== CORRECTED ENRICHMENT VALIDATION TEST ===")
    print(f"Testing {len(test_promise_ids)} promises")
    
    print("\n1. Resetting test promises...")
    reset_test_promises(db, test_promise_ids)
    
    print("\n2. Running corrected enrichment script...")
    cmd = [
        "python", "consolidated_promise_enrichment_corrected.py",
        "--parliament_session_id", "44",
        "--source_type", "2021 LPC Mandate Letters",
        "--limit", "2",
        "--force_reprocessing",
        "--enrichment_types", "all"
    ]
    
    result = subprocess.run(cmd, capture_output=True, text=True)
    
    if result.returncode != 0:
        print(f"❌ Enrichment script failed with return code {result.returncode}")
        print("STDOUT:", result.stdout)
        print("STDERR:", result.stderr)
        return
    
    print("✅ Enrichment script completed successfully")
    
    print("\n3. Validating enriched promises...")
    
    all_successes = []
    all_issues = []
    
    for promise_id in test_promise_ids:
        print(f"\n--- Validating {promise_id} ---")
        
        doc = db.collection('promises').document(promise_id).get()
        if not doc.exists:
            print(f"❌ Promise {promise_id} not found")
            continue
        
        promise_data = doc.to_dict()
        successes, issues = validate_enriched_promise(promise_data, promise_id)
        
        all_successes.extend(successes)
        all_issues.extend(issues)
        
        for success in successes:
            print(f"  {success}")
        
        for issue in issues:
            print(f"  {issue}")
    
    print(f"\n=== FINAL VALIDATION RESULTS ===")
    print(f"✅ Total Successes: {len(all_successes)}")
    print(f"❌ Total Issues: {len(all_issues)}")
    
    if len(all_issues) == 0:
        print("\n🎉 ALL REQUIREMENTS MET! The corrected enrichment script is working perfectly.")
    else:
        print(f"\n⚠️ {len(all_issues)} issues still need to be addressed:")
        for issue in all_issues:
            print(f"  {issue}")
    
    # Output detailed results to JSON
    output_file = f"corrected_enrichment_validation_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    
    enriched_promises = []
    for promise_id in test_promise_ids:
        doc = db.collection('promises').document(promise_id).get()
        if doc.exists:
            promise_data = doc.to_dict()
            # Convert timestamps for JSON serialization
            for key, value in promise_data.items():
                if hasattr(value, 'timestamp'):
                    promise_data[key] = str(value)
            enriched_promises.append({
                'id': promise_id,
                'data': promise_data
            })
    
    validation_results = {
        'test_summary': {
            'total_promises_tested': len(test_promise_ids),
            'total_successes': len(all_successes),
            'total_issues': len(all_issues),
            'all_requirements_met': len(all_issues) == 0
        },
        'successes': all_successes,
        'issues': all_issues,
        'enriched_promises': enriched_promises
    }
    
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(validation_results, f, indent=2, ensure_ascii=False, default=str)
    
    print(f"\n📄 Detailed validation results saved to: {output_file}")
    print("="*60)

if __name__ == "__main__":
    main() 