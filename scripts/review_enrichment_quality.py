#!/usr/bin/env python3
"""
Review Enrichment Quality Script

This script will:
1. Reset specific promises
2. Run enrichment on them
3. Output the results in clear JSON format for quality review
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
        'explanation',
        'background_and_context',
        'what_it_means_for_canadians',
        'keywords_enriched_at',
        'keywords_enrichment_model', 
        'keywords_enrichment_status',
        'keywords',
        'extracted_keywords_concepts',
        'action_type_enriched_at',
        'action_type_enrichment_model',
        'action_type_enrichment_status',
        'action_type',
        'implied_action_type',
        'action_type_rationale',
        'action_type_confidence',
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

def get_promise_data(db, promise_id, label=""):
    """Get promise data and return in structured format."""
    doc = db.collection('promises').document(promise_id).get()
    if not doc.exists:
        return None
    
    data = doc.to_dict()
    
    # Extract key fields for review
    promise_data = {
        "id": promise_id,
        "label": label,
        "basic_info": {
            "concise_title": data.get('concise_title', 'N/A'),
            "description": data.get('description', 'N/A'),
            "department": data.get('department', 'N/A'),
            "party": data.get('party', 'N/A'),
            "source_type": data.get('source_type', 'N/A'),
            "parliament_session_id": data.get('parliament_session_id', 'N/A')
        },
        "enrichment": {
            "explanation": {
                "what_it_means_for_canadians": data.get('what_it_means_for_canadians', 'N/A'),
                "background_and_context": data.get('background_and_context', 'N/A'),
                "enriched_at": str(data.get('explanation_enriched_at', 'N/A')),
                "model": data.get('explanation_enrichment_model', 'N/A'),
                "status": data.get('explanation_enrichment_status', 'N/A')
            },
            "keywords": {
                "extracted_keywords_concepts": data.get('extracted_keywords_concepts', 'N/A'),
                "enriched_at": str(data.get('keywords_enriched_at', 'N/A')),
                "model": data.get('keywords_enrichment_model', 'N/A'),
                "status": data.get('keywords_enrichment_status', 'N/A')
            },
            "action_type": {
                "implied_action_type": data.get('implied_action_type', 'N/A'),
                "action_type_rationale": data.get('action_type_rationale', 'N/A'),
                "action_type_confidence": data.get('action_type_confidence', 'N/A'),
                "enriched_at": str(data.get('action_type_enriched_at', 'N/A')),
                "model": data.get('action_type_enrichment_model', 'N/A'),
                "status": data.get('action_type_enrichment_status', 'N/A')
            }
        },
        "metadata": {
            "last_enrichment_at": str(data.get('last_enrichment_at', 'N/A')),
            "evidence_items_count": len(data.get('evidence_items', [])),
            "status": data.get('status', 'N/A')
        }
    }
    
    return promise_data

def run_enrichment(promise_ids):
    """Run the enrichment script on specific promise IDs."""
    logger.info(f"Running enrichment on promises: {promise_ids}")
    
    cmd = [
        'python', 'consolidated_promise_enrichment.py',
        '--parliament_session_id', '44',
        '--source_type', '2021 LPC Mandate Letters',
        '--limit', str(len(promise_ids)),
        '--force_reprocessing',
        '--enrichment_types', 'all'
    ]
    
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
        if result.returncode == 0:
            logger.info("Enrichment completed successfully")
            return True
        else:
            logger.error(f"Enrichment failed: {result.stderr}")
            return False
    except subprocess.TimeoutExpired:
        logger.error("Enrichment timed out")
        return False

def main():
    """Main function."""
    db = initialize_firebase()
    
    # Select specific promises for quality review
    test_promise_ids = [
        "20211216_MANDL_00638bafc9",  # NATO Climate Security Centre
        "20211216_MANDL_00f67326c0",  # Second promise
        "20211216_MANDL_01193789f1"   # Third promise
    ]
    
    print("=== ENRICHMENT QUALITY REVIEW ===")
    print(f"Testing {len(test_promise_ids)} promises")
    print(f"Promise IDs: {test_promise_ids}")
    
    # Step 1: Get original data
    print("\n=== STEP 1: Getting Original Promise Data ===")
    original_data = []
    for promise_id in test_promise_ids:
        data = get_promise_data(db, promise_id, "ORIGINAL")
        if data:
            original_data.append(data)
        else:
            logger.error(f"Could not find promise {promise_id}")
    
    # Step 2: Reset enrichment fields
    print("\n=== STEP 2: Resetting Enrichment Fields ===")
    for promise_id in test_promise_ids:
        reset_promise_enrichment(db, promise_id)
    
    # Step 3: Run enrichment
    print("\n=== STEP 3: Running Enrichment ===")
    enrichment_success = run_enrichment(test_promise_ids)
    
    if not enrichment_success:
        print("❌ Enrichment failed. Cannot continue with quality review.")
        return
    
    # Step 4: Get enriched data
    print("\n=== STEP 4: Getting Enriched Promise Data ===")
    enriched_data = []
    for promise_id in test_promise_ids:
        data = get_promise_data(db, promise_id, "ENRICHED")
        if data:
            enriched_data.append(data)
        else:
            logger.error(f"Could not find enriched promise {promise_id}")
    
    # Step 5: Output results
    print("\n=== STEP 5: Quality Review Results ===")
    
    results = {
        "review_timestamp": datetime.now().isoformat(),
        "promises_tested": len(test_promise_ids),
        "enrichment_results": []
    }
    
    for i, promise_id in enumerate(test_promise_ids):
        if i < len(enriched_data):
            enriched = enriched_data[i]
            
            # Create comparison
            result = {
                "promise_id": promise_id,
                "basic_info": enriched["basic_info"],
                "enrichment_quality": {
                    "explanation": {
                        "what_it_means": enriched["enrichment"]["explanation"]["what_it_means_for_canadians"],
                        "background": enriched["enrichment"]["explanation"]["background_and_context"],
                        "quality_indicators": {
                            "has_content": enriched["enrichment"]["explanation"]["what_it_means_for_canadians"] != "N/A",
                            "word_count": len(str(enriched["enrichment"]["explanation"]["what_it_means_for_canadians"]).split()) if enriched["enrichment"]["explanation"]["what_it_means_for_canadians"] != "N/A" else 0,
                            "model_used": enriched["enrichment"]["explanation"]["model"],
                            "processing_status": enriched["enrichment"]["explanation"]["status"]
                        }
                    },
                    "keywords": {
                        "extracted_concepts": enriched["enrichment"]["keywords"]["extracted_keywords_concepts"],
                        "quality_indicators": {
                            "has_keywords": enriched["enrichment"]["keywords"]["extracted_keywords_concepts"] != "N/A",
                            "keyword_count": len(enriched["enrichment"]["keywords"]["extracted_keywords_concepts"]) if isinstance(enriched["enrichment"]["keywords"]["extracted_keywords_concepts"], list) else 0,
                            "model_used": enriched["enrichment"]["keywords"]["model"],
                            "processing_status": enriched["enrichment"]["keywords"]["status"]
                        }
                    },
                    "action_type": {
                        "classified_type": enriched["enrichment"]["action_type"]["implied_action_type"],
                        "rationale": enriched["enrichment"]["action_type"]["action_type_rationale"],
                        "confidence": enriched["enrichment"]["action_type"]["action_type_confidence"],
                        "quality_indicators": {
                            "has_classification": enriched["enrichment"]["action_type"]["implied_action_type"] != "N/A",
                            "has_rationale": enriched["enrichment"]["action_type"]["action_type_rationale"] != "N/A",
                            "confidence_score": enriched["enrichment"]["action_type"]["action_type_confidence"],
                            "model_used": enriched["enrichment"]["action_type"]["model"],
                            "processing_status": enriched["enrichment"]["action_type"]["status"]
                        }
                    }
                },
                "metadata": enriched["metadata"]
            }
            
            results["enrichment_results"].append(result)
    
    # Output formatted JSON
    output_file = f"enrichment_quality_review_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(results, f, indent=2, ensure_ascii=False)
    
    print(f"\n✅ Quality review complete!")
    print(f"📄 Detailed results saved to: {output_file}")
    print(f"\n=== SUMMARY ===")
    
    for result in results["enrichment_results"]:
        print(f"\nPromise: {result['promise_id']}")
        print(f"Title: {result['basic_info']['concise_title'][:80]}...")
        print(f"✅ Explanation: {'✓' if result['enrichment_quality']['explanation']['quality_indicators']['has_content'] else '✗'} ({result['enrichment_quality']['explanation']['quality_indicators']['word_count']} words)")
        print(f"✅ Keywords: {'✓' if result['enrichment_quality']['keywords']['quality_indicators']['has_keywords'] else '✗'} ({result['enrichment_quality']['keywords']['quality_indicators']['keyword_count']} keywords)")
        print(f"✅ Action Type: {'✓' if result['enrichment_quality']['action_type']['quality_indicators']['has_classification'] else '✗'} ({result['enrichment_quality']['action_type']['classified_type']})")
    
    print(f"\n📋 For detailed review, see: {output_file}")

if __name__ == "__main__":
    main() 