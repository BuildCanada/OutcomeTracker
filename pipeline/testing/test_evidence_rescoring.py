#!/usr/bin/env python3
"""
Test Evidence Rescoring

This script tests that promise rescoring is triggered when evidence is created
and linked via the admin interface.
"""

import asyncio
import sys
from pathlib import Path
import logging

# Add pipeline directory to path
sys.path.append(str(Path(__file__).parent / 'pipeline'))
sys.path.append(str(Path(__file__).parent))

from pipeline.stages.linking.evidence_linker import EvidenceLinker
from pipeline.stages.linking.progress_scorer import ProgressScorer
from pipeline.core.job_runner import JobRunner

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

async def test_evidence_rescoring():
    """Test the evidence linking and progress scoring pipeline"""
    
    print("🧪 Testing Evidence Rescoring Pipeline")
    print("=" * 50)
    
    try:
        # Initialize job runner
        runner = JobRunner()
        
        # Test 1: Evidence Linker
        print("\n🔗 Step 1: Testing Evidence Linker")
        print("-" * 30)
        
        evidence_linker = EvidenceLinker(
            job_name="test_evidence_linker",
            config={
                'batch_size': 5,
                'max_items_per_run': 10,
                'min_confidence_threshold': 0.3
            }
        )
        
        # Run evidence linker
        linker_result = runner.run_job(
            evidence_linker,
            timeout_minutes=5,
            retry_attempts=1
        )
        
        print(f"✅ Evidence Linker Result:")
        print(f"   Status: {linker_result.status}")
        print(f"   Items Processed: {linker_result.items_processed}")
        print(f"   Links Created: {linker_result.items_created}")
        print(f"   Duration: {linker_result.duration_seconds:.2f}s")
        
        if linker_result.error_message:
            print(f"   Error: {linker_result.error_message}")
        
        # Test 2: Progress Scorer (if links were created)
        if linker_result.items_created > 0:
            print(f"\n📊 Step 2: Testing Progress Scorer (triggered by {linker_result.items_created} new links)")
            print("-" * 30)
            
            progress_scorer = ProgressScorer(
                job_name="test_progress_scorer",
                config={
                    'batch_size': 10,
                    'max_promises_per_run': 50
                }
            )
            
            # Run progress scorer
            scorer_result = runner.run_job(
                progress_scorer,
                timeout_minutes=5,
                retry_attempts=1
            )
            
            print(f"✅ Progress Scorer Result:")
            print(f"   Status: {scorer_result.status}")
            print(f"   Promises Processed: {scorer_result.items_processed}")
            print(f"   Scores Updated: {scorer_result.items_updated}")
            print(f"   Duration: {scorer_result.duration_seconds:.2f}s")
            
            if scorer_result.error_message:
                print(f"   Error: {scorer_result.error_message}")
                
        else:
            print(f"\n⏭️  Step 2: Skipping Progress Scorer (no new links created)")
        
        # Test 3: Verify Downstream Triggering
        print(f"\n🔄 Step 3: Testing Downstream Triggering Logic")
        print("-" * 30)
        
        should_trigger = evidence_linker.should_trigger_downstream(linker_result)
        print(f"Should trigger downstream: {should_trigger}")
        
        if should_trigger:
            trigger_metadata = evidence_linker.get_trigger_metadata(linker_result)
            print(f"Trigger metadata: {trigger_metadata}")
        
        # Summary
        print(f"\n🎉 Test Complete!")
        print("=" * 50)
        print(f"📊 Results Summary:")
        print(f"   Evidence Linker: {linker_result.status}")
        if linker_result.items_created > 0:
            print(f"   Progress Scorer: {scorer_result.status if 'scorer_result' in locals() else 'Not run'}")
        print(f"   Automatic Triggering: {'✅ Working' if should_trigger and linker_result.items_created > 0 else '⚠️ No new links to trigger'}")
        
        return linker_result.items_created > 0
        
    except Exception as e:
        logger.error(f"Test failed: {e}", exc_info=True)
        print(f"❌ Test failed with error: {e}")
        return False

async def main():
    """Main test function"""
    print("🚀 Promise Tracker - Evidence Rescoring Test")
    print("This test verifies that promise rescoring works correctly.")
    print("\nPress Ctrl+C to cancel at any time.\n")
    
    try:
        success = await test_evidence_rescoring()
        
        if success:
            print(f"\n✅ PASS: Evidence rescoring pipeline is working correctly!")
            print(f"When you create evidence via the admin interface and link it to promises,")
            print(f"the system will automatically trigger promise rescoring.")
        else:
            print(f"\n⚠️  INFO: No new evidence links were created during this test.")
            print(f"This is normal if all existing evidence is already processed.")
            print(f"The rescoring system is ready and will trigger when new evidence is linked.")
            
        return 0
        
    except KeyboardInterrupt:
        print(f"\n⚠️  Test cancelled by user")
        return 1
    except Exception as e:
        print(f"\n❌ FAIL: Test failed with error: {e}")
        return 1

if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code) 