#!/usr/bin/env python3
"""
Focused test of evidence linking specifically for Bill C-4 to diagnose linking accuracy
"""

import logging
import sys
import firebase_admin
from firebase_admin import firestore
from pathlib import Path
from datetime import datetime, timezone

# Load environment variables
try:
    from dotenv import load_dotenv
    env_path = Path(__file__).parent / '.env'
    load_dotenv(env_path)
    print(f"📋 Loaded environment from: {env_path}")
except ImportError:
    print("📋 python-dotenv not available")
except Exception as e:
    print(f"📋 Could not load .env file: {e}")

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(name)s - %(message)s',
    handlers=[logging.StreamHandler(sys.stdout)]
)

# Add pipeline directory to path
pipeline_dir = Path(__file__).parent
sys.path.insert(0, str(pipeline_dir))

from pipeline.stages.linking.evidence_linker import EvidenceLinker

def test_c4_linking():
    """Test evidence linking specifically for Bill C-4"""
    
    # Initialize Firebase
    if not firebase_admin._apps:
        firebase_admin.initialize_app()
    
    db = firestore.client()
    
    print("🔍 TESTING EVIDENCE LINKING FOR BILL C-4")
    print("=" * 60)
    
    # First, let's find the C-4 evidence item and reset its linking status
    query = db.collection('evidence_items').where(
        filter=firestore.FieldFilter('evidence_source_type', '==', 'Bill Event (LEGISinfo)')
    ).where(
        filter=firestore.FieldFilter('parliament_session_id', '==', '45')
    ).where(
        filter=firestore.FieldFilter('source_document_raw_id', '==', 'C-4')
    ).limit(1)
    
    docs = list(query.stream())
    if not docs:
        print("❌ Could not find Bill C-4 evidence item")
        return
    
    evidence_doc = docs[0]
    evidence_data = evidence_doc.to_dict()
    evidence_id = evidence_data.get('evidence_id', evidence_doc.id)
    
    print(f"📋 Found Bill C-4 evidence item: {evidence_id}")
    print(f"   Current promise_ids: {len(evidence_data.get('promise_ids', []))}")
    print(f"   Current linking status: {evidence_data.get('promise_linking_status', 'unknown')}")
    
    # Store current state for comparison
    current_promise_ids = evidence_data.get('promise_ids', [])
    
    # Reset linking status to pending so the linker will process it
    print("\n🔄 Resetting linking status to pending...")
    db.collection('evidence_items').document(evidence_doc.id).update({
        'promise_linking_status': 'pending',
        'promise_ids': [],  # Clear existing links for fresh test
        'hybrid_linking_method': None,
        'hybrid_linking_avg_confidence': None,
        'promise_links_found': 0
    })
    
    # Configure the linker with current settings
    config = {
        'batch_size': 1,
        'max_items_per_run': 1,
        'semantic_threshold': 0.47,  # Current threshold
        'high_similarity_bypass_threshold': 0.50,
        'llm_validation_threshold': 0.5,
        'max_llm_candidates': 5,
        'include_private_bills': True,
        'min_relevance_threshold': 0.1
    }
    
    print(f"\n🔗 Running evidence linker with current configuration...")
    print(f"   Semantic threshold: {config['semantic_threshold']}")
    print(f"   LLM validation threshold: {config['llm_validation_threshold']}")
    print(f"   High similarity bypass: {config['high_similarity_bypass_threshold']}")
    
    # Run the linker
    linker = EvidenceLinker("test_c4_linker", config)
    
    try:
        result = linker.execute(
            limit=1,
            validation_threshold=0.5,
            parliament_session_id='45'
        )
        
        print(f"\n📊 LINKING RESULTS:")
        print(f"   Status: {result.status.value}")
        print(f"   Items processed: {result.items_processed}")
        print(f"   Items updated: {result.items_updated}")
        print(f"   Errors: {result.errors}")
        
        # Get the updated evidence item
        updated_doc = db.collection('evidence_items').document(evidence_doc.id).get()
        updated_data = updated_doc.to_dict()
        
        new_promise_ids = updated_data.get('promise_ids', [])
        linking_method = updated_data.get('hybrid_linking_method', 'unknown')
        avg_confidence = updated_data.get('hybrid_linking_avg_confidence', 0)
        
        print(f"\n🎯 NEW LINKING RESULTS:")
        print(f"   New promise_ids count: {len(new_promise_ids)}")
        print(f"   Linking method: {linking_method}")
        print(f"   Average confidence: {avg_confidence:.3f}" if avg_confidence is not None else "   Average confidence: None")
        
        # Compare with previous results
        print(f"\n📊 COMPARISON:")
        print(f"   Previous links: {len(current_promise_ids)}")
        print(f"   New links: {len(new_promise_ids)}")
        print(f"   Same results: {set(current_promise_ids) == set(new_promise_ids)}")
        
        if set(current_promise_ids) != set(new_promise_ids):
            added = set(new_promise_ids) - set(current_promise_ids)
            removed = set(current_promise_ids) - set(new_promise_ids)
            print(f"   Added: {len(added)} promises")
            print(f"   Removed: {len(removed)} promises")
        
        # Show detailed promise information if we got new links
        if new_promise_ids:
            print(f"\n📋 DETAILED PROMISE ANALYSIS:")
            print(f"   Fetching details for {len(new_promise_ids)} linked promises...")
            
            # Get promise details in batches
            promises_data = []
            for i in range(0, len(new_promise_ids), 10):
                batch = new_promise_ids[i:i+10]
                for promise_id in batch:
                    try:
                        promise_doc = db.collection('promises').document(promise_id).get()
                        if promise_doc.exists:
                            promise_data = promise_doc.to_dict()
                            promise_data['promise_id'] = promise_id
                            promises_data.append(promise_data)
                    except Exception as e:
                        print(f"   Error fetching promise {promise_id}: {e}")
            
            # Group by category for analysis
            categories = {}
            for promise in promises_data:
                category = promise.get('category', 'Unknown')
                if category not in categories:
                    categories[category] = []
                categories[category].append(promise)
            
            print(f"\n🏷️  PROMISES BY CATEGORY:")
            for category, category_promises in categories.items():
                print(f"\n   {category.upper()} ({len(category_promises)} promises):")
                for promise in category_promises[:5]:  # Show first 5 per category
                    promise_num = promise.get('promise_number', 'N/A')
                    title = promise.get('promise_title', 'No title')[:80]
                    print(f"     • {promise_num}: {title}")
                if len(category_promises) > 5:
                    print(f"     ... and {len(category_promises) - 5} more")
        
        # Recommendations based on results
        print(f"\n💡 DIAGNOSIS:")
        if set(current_promise_ids) == set(new_promise_ids):
            print("   ❌ SAME RESULTS: The linking logic itself is producing the same")
            print("      false positives. We need to tighten the semantic/LLM thresholds.")
        else:
            print("   ⚠️  DIFFERENT RESULTS: The issue may be in how we write evidence")
            print("      to promises collection, not the linking logic itself.")
        
        if len(new_promise_ids) > 15:
            print("   ❌ TOO MANY LINKS: Current thresholds are too permissive.")
            print("      Recommend increasing semantic_threshold and LLM validation_threshold.")
        
        return {
            'current_links': len(current_promise_ids),
            'new_links': len(new_promise_ids),
            'same_results': set(current_promise_ids) == set(new_promise_ids),
            'method': linking_method,
            'confidence': avg_confidence,
            'categories': categories if new_promise_ids else {}
        }
        
    except Exception as e:
        print(f"❌ Error running linker: {e}")
        logging.error("Linker test failed", exc_info=True)
        return None

if __name__ == "__main__":
    result = test_c4_linking()
    
    if result:
        print(f"\n" + "=" * 60)
        print(f"🎯 TEST COMPLETE")
        print(f"   Results indicate: {'LINKING LOGIC ISSUE' if result['same_results'] else 'PROMISE WRITING ISSUE'}")
        if result['categories']:
            print(f"   Categories found: {list(result['categories'].keys())}") 