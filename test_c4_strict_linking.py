#!/usr/bin/env python3
"""
Test stricter linking thresholds for the enhanced C-4 evidence item
"""

import logging
import sys
import firebase_admin
from firebase_admin import firestore
from pathlib import Path

# Load environment variables
try:
    from dotenv import load_dotenv
    env_path = Path(__file__).parent / '.env'
    load_dotenv(env_path)
except ImportError:
    pass

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# Add pipeline directory to path
pipeline_dir = Path(__file__).parent
sys.path.insert(0, str(pipeline_dir))

from pipeline.stages.linking.evidence_linker import EvidenceLinker

def test_strict_thresholds():
    """Test stricter thresholds on the enhanced C-4 evidence item"""
    
    if not firebase_admin._apps:
        firebase_admin.initialize_app()
    
    db = firestore.client()
    
    print("🔧 TESTING STRICTER LINKING THRESHOLDS FOR ENHANCED C-4")
    print("=" * 70)
    
    # Get the enhanced C-4 evidence item (the one with 26 links)
    enhanced_c4_id = "20250606_45_LegisInfo_1cbf1484"
    
    # Test different threshold combinations
    threshold_tests = [
        {"name": "Current (Too Loose)", "semantic": 0.47, "llm": 0.5, "bypass": 0.50},
        {"name": "Moderate Tightening", "semantic": 0.55, "llm": 0.65, "bypass": 0.60}, 
        {"name": "Strict", "semantic": 0.60, "llm": 0.75, "bypass": 0.65},
        {"name": "Very Strict", "semantic": 0.65, "llm": 0.80, "bypass": 0.70},
    ]
    
    results = []
    
    for test in threshold_tests:
        print(f"\n🧪 Testing: {test['name']}")
        print(f"   Semantic: {test['semantic']}, LLM: {test['llm']}, Bypass: {test['bypass']}")
        
        # Reset the evidence item
        db.collection('evidence_items').document(enhanced_c4_id).update({
            'promise_linking_status': 'pending',
            'promise_ids': [],
            'hybrid_linking_method': None,
            'hybrid_linking_avg_confidence': None,
            'promise_links_found': 0
        })
        
        # Configure linker with test thresholds
        config = {
            'batch_size': 1,
            'max_items_per_run': 1,
            'semantic_threshold': test['semantic'],
            'high_similarity_bypass_threshold': test['bypass'],
            'llm_validation_threshold': test['llm'],
            'max_llm_candidates': 3  # Reduce for speed
        }
        
        try:
            linker = EvidenceLinker("test_strict_linker", config)
            result = linker.execute(
                limit=1,
                validation_threshold=test['llm'],
                parliament_session_id='45'
            )
            
            # Get results
            updated_doc = db.collection('evidence_items').document(enhanced_c4_id).get()
            updated_data = updated_doc.to_dict()
            
            link_count = len(updated_data.get('promise_ids', []))
            method = updated_data.get('hybrid_linking_method', 'unknown')
            confidence = updated_data.get('hybrid_linking_avg_confidence', 0)
            
            results.append({
                'test': test['name'],
                'thresholds': f"S:{test['semantic']}, L:{test['llm']}, B:{test['bypass']}",
                'links': link_count,
                'method': method,
                'confidence': confidence
            })
            
            print(f"   → {link_count} links (method: {method}, conf: {confidence:.3f})")
            
        except Exception as e:
            print(f"   → ERROR: {e}")
            results.append({
                'test': test['name'],
                'thresholds': f"S:{test['semantic']}, L:{test['llm']}, B:{test['bypass']}",
                'links': 'ERROR',
                'method': 'ERROR',
                'confidence': 0
            })
    
    # Print summary
    print(f"\n" + "=" * 70)
    print(f"📊 THRESHOLD TESTING RESULTS:")
    print(f"{'Test Name':<20} {'Thresholds':<18} {'Links':<6} {'Method':<20} {'Conf':<6}")
    print(f"-" * 70)
    
    for result in results:
        links_str = str(result['links'])
        conf_str = f"{result['confidence']:.3f}" if isinstance(result['confidence'], (int, float)) else "N/A"
        print(f"{result['test']:<20} {result['thresholds']:<18} {links_str:<6} {result['method']:<20} {conf_str:<6}")
    
    # Recommendations
    print(f"\n💡 RECOMMENDATIONS:")
    
    best_result = None
    for result in results:
        if isinstance(result['links'], int) and 1 <= result['links'] <= 8:  # Sweet spot
            best_result = result
            break
    
    if best_result:
        print(f"✅ OPTIMAL: '{best_result['test']}' produces {best_result['links']} links")
        print(f"   Recommended thresholds: {best_result['thresholds']}")
    else:
        high_precision_results = [r for r in results if isinstance(r['links'], int) and r['links'] <= 5]
        if high_precision_results:
            rec = high_precision_results[0]
            print(f"✅ HIGH PRECISION: '{rec['test']}' produces {rec['links']} links")
            print(f"   Recommended for high precision: {rec['thresholds']}")
        else:
            print(f"❌ All thresholds still produce too many links or errors")
            print(f"   Need even stricter thresholds or different approach")

if __name__ == "__main__":
    test_strict_thresholds() 