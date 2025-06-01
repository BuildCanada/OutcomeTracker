#!/usr/bin/env python3
"""
Test script for the updated progress_scorer.py

This script tests that the progress scorer works correctly with the 
actual database structure where evidence is linked via promise_ids arrays.
"""

import asyncio
import os
import sys
import json
import logging
from pathlib import Path
from typing import Dict, Any
import firebase_admin
from firebase_admin import firestore, credentials
from dotenv import load_dotenv

# Setup path for imports
sys.path.append(str(Path(__file__).parent / 'pipeline'))

try:
    from stages.linking.progress_scorer import ProgressScorer
except ImportError as e:
    print(f"Import error: {e}")
    print("Please ensure the pipeline modules are available")
    sys.exit(1)

# Load environment
load_dotenv()

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(name)s - %(message)s'
)
logger = logging.getLogger(__name__)

async def test_progress_scorer():
    """Test the progress scorer with real data."""
    logger.info("Testing Progress Scorer with updated logic")
    
    try:
        # Initialize Firebase if needed
        if not firebase_admin._apps:
            firebase_admin.initialize_app()
        
        # Create the progress scorer
        scorer = ProgressScorer(
            job_name="test_scorer",
            config={
                'batch_size': 5,
                'max_promises_per_run': 10
            }
        )
        
        logger.info("Progress scorer initialized successfully")
        
        # Run the scorer
        result = await asyncio.to_thread(scorer._execute_job)
        
        print("\n" + "="*60)
        print("PROGRESS SCORER TEST RESULTS")
        print("="*60)
        print(f"Promises Processed: {result['promises_processed']}")
        print(f"Scores Updated: {result['scores_updated']}")
        print(f"Status Changes: {result['status_changes']}")
        print(f"Errors: {result['errors']}")
        print(f"Collections Used: {result['metadata']}")
        
        if result['errors'] == 0:
            print("\n✅ Progress scorer test completed successfully!")
            return True
        else:
            print(f"\n❌ Progress scorer test completed with {result['errors']} errors")
            return False
            
    except Exception as e:
        logger.error(f"Test failed with exception: {e}")
        print(f"\n❌ Test failed: {e}")
        return False

async def main():
    """Run the progress scorer test."""
    success = await test_progress_scorer()
    sys.exit(0 if success else 1)

if __name__ == "__main__":
    asyncio.run(main()) 