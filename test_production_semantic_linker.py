#!/usr/bin/env python3
"""
Test script for production semantic evidence linker
"""

from pipeline.stages.linking.semantic_evidence_linker import link_evidence_semantically
import json

def test_production_linker():
    """Test the production semantic linker with test collections."""
    
    print("=== Production Semantic Evidence Linker Test ===")
    print("Testing with test collections and JSON debug output...")
    
    # Test the production linker with debug file generation
    result = link_evidence_semantically(
        parliament_session_id='44',
        evidence_collection='evidence_items_test',
        promise_collection='promises_test',
        similarity_threshold=0.4,
        max_links_per_evidence=20,
        limit=3,
        dry_run=True,
        generate_debug_files=True  # Enable JSON debug files
    )
    
    print("\nResults:")
    print(json.dumps(result, indent=2, default=str))
    
    if result.get('success'):
        print(f"\n✅ SUCCESS! Processed {result.get('evidence_processed', 0)} evidence items")
        print(f"   Links created: {result.get('total_links_created', 0)}")
        print(f"   Processing time: {result.get('processing_time', 0):.2f} seconds")
        if 'stats' in result:
            stats = result['stats']
            print(f"   Embeddings generated: {stats.get('embeddings_generated', 0)}")
            print(f"   Similarities calculated: {stats.get('similarities_calculated', 0)}")
        
        # Check for debug files
        if 'debug_files' in result:
            print(f"\n📄 Debug files generated:")
            for file_type, file_path in result['debug_files'].items():
                print(f"   {file_type}: {file_path}")
    else:
        print(f"\n❌ FAILED: {result.get('error', 'Unknown error')}")

if __name__ == "__main__":
    test_production_linker() 