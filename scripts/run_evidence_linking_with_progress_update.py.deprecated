#!/usr/bin/env python3
"""
Combined Evidence Linking and Progress Score Update Pipeline

This script runs the complete evidence linking and progress scoring pipeline:
1. Runs consolidated_evidence_linking.py to link new evidence to promises
2. Immediately follows with update_promise_progress_scores.py to update progress scores

This ensures that progress scores are always up-to-date after evidence linking.

Usage:
    python run_evidence_linking_with_progress_update.py --parliament_session_id "45" [options]
"""

import asyncio
import argparse
import logging
import sys
import os
from pathlib import Path

# Add parent directory to path
sys.path.append(str(Path(__file__).parent))

# Import the pipeline classes
from consolidated_evidence_linking import ConsolidatedEvidenceLinking
from update_promise_progress_scores import PromiseProgressScoreUpdater

# Logger setup
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(filename)s:%(lineno)d - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger("combined_pipeline")

class CombinedEvidenceLinkingPipeline:
    """Runs evidence linking followed by progress score updates."""
    
    def __init__(self):
        """Initialize the combined pipeline."""
        self.evidence_linker = ConsolidatedEvidenceLinking()
        self.progress_updater = PromiseProgressScoreUpdater()
    
    async def run_combined_pipeline(self, 
                                  parliament_session_id: str,
                                  evidence_types: list = None,
                                  party_codes: list = None,
                                  promise_ranks: list = None,
                                  limit: int = None,
                                  min_confidence: float = 0.7,
                                  force_reprocessing: bool = False,
                                  dry_run: bool = False,
                                  max_promises_per_evidence: int = None,
                                  min_similarity: float = 0.1,
                                  max_candidates: int = 50,
                                  skip_progress_update: bool = False) -> dict:
        """Run the complete combined pipeline."""
        
        logger.info("🚀 Starting Combined Evidence Linking and Progress Update Pipeline")
        logger.info("=" * 80)
        
        # Step 1: Run Evidence Linking
        logger.info("📋 STEP 1: Running Evidence Linking Pipeline")
        logger.info("-" * 50)
        
        evidence_stats = await self.evidence_linker.run_evidence_linking_pipeline(
            parliament_session_id=parliament_session_id,
            evidence_types=evidence_types,
            party_codes=party_codes,
            promise_ranks=promise_ranks,
            limit=limit,
            min_confidence=min_confidence,
            force_reprocessing=force_reprocessing,
            dry_run=dry_run,
            max_promises_per_evidence=max_promises_per_evidence,
            min_similarity=min_similarity,
            max_candidates=max_candidates
        )
        
        logger.info("✅ Evidence linking pipeline completed")
        logger.info(f"   Links created: {evidence_stats.get('links_created', 0)}")
        logger.info(f"   Evidence processed: {evidence_stats.get('evidence_processed', 0)}")
        
        # Step 2: Run Progress Score Updates (if not skipped and links were created)
        progress_stats = {}
        if not skip_progress_update and evidence_stats.get('links_created', 0) > 0:
            logger.info("\n📊 STEP 2: Running Progress Score Update Pipeline")
            logger.info("-" * 50)
            
            # Run progress updates for promises that may have been updated in the last hour
            # (since we just ran evidence linking)
            progress_stats = await self.progress_updater.run_progress_score_update_pipeline(
                parliament_session_id=parliament_session_id,
                since_hours=1,  # Look for very recent updates
                force_all=False,  # Only update promises with recent evidence links
                dry_run=dry_run
            )
            
            logger.info("✅ Progress score update pipeline completed")
            logger.info(f"   Progress scores updated: {progress_stats.get('progress_scores_updated', 0)}")
        elif skip_progress_update:
            logger.info("\n⏭️  STEP 2: Skipping progress score updates (--skip_progress_update)")
        else:
            logger.info("\n⏭️  STEP 2: Skipping progress score updates (no new links created)")
        
        # Combined results
        combined_stats = {
            'evidence_linking': evidence_stats,
            'progress_scoring': progress_stats,
            'total_links_created': evidence_stats.get('links_created', 0),
            'total_progress_scores_updated': progress_stats.get('progress_scores_updated', 0)
        }
        
        logger.info("\n🎉 Combined Pipeline Complete!")
        logger.info("=" * 80)
        logger.info(f"📊 Final Summary:")
        logger.info(f"   Evidence items processed: {evidence_stats.get('evidence_processed', 0)}")
        logger.info(f"   New evidence links created: {evidence_stats.get('links_created', 0)}")
        logger.info(f"   Progress scores updated: {progress_stats.get('progress_scores_updated', 0)}")
        logger.info(f"   Total errors: {evidence_stats.get('errors', 0) + progress_stats.get('errors', 0)}")
        
        return combined_stats

async def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(description='Combined Evidence Linking and Progress Score Update Pipeline')
    
    # Evidence linking arguments
    parser.add_argument(
        '--parliament_session_id',
        type=str,
        required=True,
        help='Parliament session ID (e.g., "45")'
    )
    parser.add_argument(
        '--evidence_types',
        nargs='+',
        choices=['OIC', 'Canada Gazette Part II', 'Bill Event (LEGISinfo)', 'News'],
        help='Types of evidence to process'
    )
    parser.add_argument(
        '--party_codes',
        nargs='+',
        choices=['LPC', 'CPC', 'NDP', 'BQ', 'GPC'],
        help='Party codes to process promises for'
    )
    parser.add_argument(
        '--limit',
        type=int,
        help='Limit number of evidence items to process'
    )
    parser.add_argument(
        '--min_confidence',
        type=float,
        default=0.7,
        help='Minimum confidence score for creating links (default: 0.7)'
    )
    parser.add_argument(
        '--force_reprocessing',
        action='store_true',
        help='Force reprocessing even if evidence already processed'
    )
    parser.add_argument(
        '--dry_run',
        action='store_true',
        help='Run without making changes to Firestore'
    )
    parser.add_argument(
        '--max_promises_per_evidence',
        type=int,
        help='Limit number of promises to evaluate per evidence item (for testing)'
    )
    parser.add_argument(
        '--promise_ranks',
        nargs='+',
        choices=['strong', 'medium', 'weak'],
        default=['strong', 'medium'],
        help='Promise rank types to process (default: strong, medium)'
    )
    parser.add_argument(
        '--min_similarity',
        type=float,
        default=0.1,
        help='Minimum Jaccard similarity for prefiltering (default: 0.1)'
    )
    parser.add_argument(
        '--max_candidates',
        type=int,
        default=50,
        help='Maximum candidate promises to send to LLM after prefiltering (default: 50)'
    )
    parser.add_argument(
        '--skip_progress_update',
        action='store_true',
        help='Skip the progress score update step (only run evidence linking)'
    )
    
    args = parser.parse_args()
    
    # Run combined pipeline
    pipeline = CombinedEvidenceLinkingPipeline()
    stats = await pipeline.run_combined_pipeline(
        parliament_session_id=args.parliament_session_id,
        evidence_types=args.evidence_types,
        party_codes=args.party_codes,
        promise_ranks=args.promise_ranks,
        limit=args.limit,
        min_confidence=args.min_confidence,
        force_reprocessing=args.force_reprocessing,
        dry_run=args.dry_run,
        max_promises_per_evidence=args.max_promises_per_evidence,
        min_similarity=args.min_similarity,
        max_candidates=args.max_candidates,
        skip_progress_update=args.skip_progress_update
    )
    
    logger.info("Combined evidence linking and progress update pipeline completed successfully!")

if __name__ == "__main__":
    asyncio.run(main()) 