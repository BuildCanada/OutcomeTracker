#!/usr/bin/env python3
"""
Demo Pipeline Script

Demonstrates the complete promise processing pipeline:
1. Document ingestion with LLM extraction
2. Promise creation and storage in test collection
3. Complete enrichment using tested prompts
4. Priority ranking
5. Cost tracking

This script uses the test collection and sample data for safe testing.
"""

import asyncio
import json
import logging
from pathlib import Path
import sys

# Add lib directory to path
sys.path.append(str(Path(__file__).parent.parent / 'lib'))
sys.path.append(str(Path(__file__).parent))

from promise_pipeline import PromisePipeline

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

async def demo_complete_pipeline():
    """Demonstrate the complete pipeline from document to enriched promises."""
    
    print("🚀 Starting Promise Tracker Pipeline Demo")
    print("=" * 60)
    
    # Initialize pipeline with test collection
    pipeline = PromisePipeline(use_test_collection=True)
    
    # Sample document path
    sample_doc_path = Path(__file__).parent.parent / "sample_documents" / "test_mandate_2025.txt"
    
    if not sample_doc_path.exists():
        print(f"❌ Sample document not found at: {sample_doc_path}")
        return
    
    print(f"📄 Using sample document: {sample_doc_path}")
    
    try:
        # Step 1: Document Ingestion
        print("\n📥 Step 1: Document Ingestion and Promise Extraction")
        print("-" * 50)
        
        stored_ids = await pipeline.ingest_document(
            document_path=str(sample_doc_path),
            source_type="2025 LPC Platform",
            source_url="https://example.com/2025-lpc-platform",
            date_issued="2025-01-01",
            entity="Liberal Party of Canada",
            parliament_session_id="44",
            party_code="LPC"
        )
        
        print(f"✅ Extracted and stored {len(stored_ids)} promises:")
        for i, doc_id in enumerate(stored_ids[:5]):  # Show first 5
            print(f"   {i+1}. {doc_id}")
        if len(stored_ids) > 5:
            print(f"   ... and {len(stored_ids) - 5} more")
        
        if not stored_ids:
            print("❌ No promises extracted. Check document content and LLM response.")
            return
            
        # Step 2: Individual Promise Enrichment Demo
        print(f"\n🔍 Step 2: Individual Promise Enrichment Demo")
        print("-" * 50)
        
        # Enrich the first promise as a demo
        first_promise_id = stored_ids[0]
        print(f"📝 Enriching promise: {first_promise_id}")
        
        success = await pipeline.enrich_promise(first_promise_id, force=True)
        
        if success:
            print("✅ Promise enrichment successful")
            
            # Retrieve and display enriched promise
            enriched_promise = await pipeline.firebase_manager.get_promise(first_promise_id)
            if enriched_promise:
                print(f"\n📋 Enriched Promise Details:")
                print(f"   Original Text: {enriched_promise.text}")
                print(f"   Concise Title: {enriched_promise.concise_title}")
                print(f"   Action Type: {enriched_promise.implied_action_type}")
                print(f"   Keywords: {enriched_promise.extracted_keywords_concepts}")
                if enriched_promise.what_it_means_for_canadians:
                    print(f"   What it means for Canadians:")
                    for meaning in enriched_promise.what_it_means_for_canadians[:2]:  # Show first 2
                        print(f"     • {meaning}")
                if enriched_promise.bc_promise_rank:
                    print(f"   Priority Rank: {enriched_promise.bc_promise_rank}")
                    print(f"   Priority Direction: {enriched_promise.bc_promise_direction}")
        else:
            print("❌ Promise enrichment failed")
        
        # Step 3: Batch Enrichment Demo  
        print(f"\n⚡ Step 3: Batch Enrichment Demo")
        print("-" * 50)
        
        print(f"🔄 Enriching ALL remaining {len(stored_ids)-1} promises in batch...")
        
        # Enrich ALL remaining promises - no artificial limits
        batch_results = await pipeline.batch_enrich_promises(limit=None, force=False)
        
        print(f"✅ Batch enrichment results: {batch_results}")
        
        # Step 4: Cost Summary
        print(f"\n💰 Step 4: Cost and Usage Summary")
        print("-" * 50)
        
        cost_summary = pipeline.get_cost_summary()
        print(f"📊 Pipeline Performance:")
        print(f"   Total LLM Calls: {cost_summary['total_calls']}")
        print(f"   Total Tokens: {cost_summary['total_tokens']}")
        print(f"   Estimated Cost: ${cost_summary['total_cost_usd']:.4f}")
        print(f"   Model Used: {cost_summary['model_name']}")
        
        # Step 5: Verification
        print(f"\n✅ Step 5: Verification")
        print("-" * 50)
        
        print("🔍 Verifying promises in test collection...")
        
        # Check a few enriched promises
        verified_count = 0
        for doc_id in stored_ids[:3]:
            promise = await pipeline.firebase_manager.get_promise(doc_id)
            if promise and promise.concise_title and promise.extracted_keywords_concepts:
                verified_count += 1
        
        print(f"✅ Verified {verified_count}/{min(3, len(stored_ids))} promises are properly enriched")
        
        # Final Summary
        print(f"\n🎉 Demo Pipeline Complete!")
        print("=" * 60)
        print(f"📈 Summary:")
        print(f"   • Documents processed: 1")
        print(f"   • Promises extracted: {len(stored_ids)}")
        print(f"   • Promises enriched: {batch_results.get('enriched', 0) + (1 if success else 0)}")
        print(f"   • Total cost: ${cost_summary['total_cost_usd']:.4f}")
        print(f"   • Collection used: promises_test (safe for testing)")
        
        return stored_ids
        
    except Exception as e:
        logger.error(f"Demo pipeline error: {e}", exc_info=True)
        print(f"❌ Demo failed with error: {e}")
        return []

async def demo_query_enriched_promises():
    """Demonstrate querying enriched promises from the test collection."""
    print("\n🔍 Bonus: Querying Enriched Promises")
    print("-" * 50)
    
    try:
        pipeline = PromisePipeline(use_test_collection=True)
        
        # Query promises from test collection
        collection_ref = pipeline.firebase_manager.db.collection("promises_test")
        docs = await asyncio.to_thread(list, collection_ref.limit(5).stream())
        
        print(f"📋 Found {len(docs)} promises in test collection:")
        
        for i, doc in enumerate(docs):
            data = doc.to_dict()
            print(f"\n   {i+1}. Promise ID: {doc.id}")
            print(f"      Text: {data.get('text', 'N/A')[:60]}...")
            print(f"      Title: {data.get('concise_title', 'Not enriched')}")
            print(f"      Action Type: {data.get('implied_action_type', 'Not enriched')}")
            keywords = data.get('extracted_keywords_concepts', [])
            print(f"      Keywords Count: {len(keywords) if keywords else 0}")
            
            meanings = data.get('what_it_means_for_canadians')
            if meanings and len(meanings) > 0:
                print(f"      Impact Summary: {meanings[0][:50]}...")
                
    except Exception as e:
        logger.error(f"Query demo error: {e}")
        print(f"❌ Query demo failed: {e}")

if __name__ == "__main__":
    print("🧪 Promise Tracker - Pipeline Demo")
    print("This demo uses the test collection for safe testing.")
    print("\nPress Ctrl+C to cancel at any time.\n")
    
    try:
        # Run the complete demo
        stored_ids = asyncio.run(demo_complete_pipeline())
        
        if stored_ids:
            print("\n" + "="*60)
            # Run the query demo
            asyncio.run(demo_query_enriched_promises())
            
            print(f"\n💡 Next Steps:")
            print(f"   • Review enriched promises in Firebase Console (promises_test collection)")
            print(f"   • Test individual promise enrichment with specific IDs")
            print(f"   • Integrate with admin frontend for promise management")
            print(f"   • Scale up to production collection when ready")
        
    except KeyboardInterrupt:
        print("\n\n🛑 Demo cancelled by user")
    except Exception as e:
        print(f"\n❌ Demo failed: {e}")
        logger.error("Demo failed", exc_info=True) 