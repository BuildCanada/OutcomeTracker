#!/usr/bin/env python3
"""
Test script for the updated progress_scorer.py

Tests that the progress scorer works correctly with the frontend-compatible
data structure where evidence_items have promise_ids arrays.
"""

import asyncio
import os
import sys
import json
import logging
from pathlib import Path
from typing import Dict, Any, List
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
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

async def test_progress_scorer_data_structure():
    """Test that progress scorer works with the updated data structure"""
    
    # Initialize Firebase Admin SDK
    try:
        # Try to get existing app first
        app = firebase_admin.get_app()
        db = firestore.client(app)
    except ValueError:
        # No app exists, create one
        service_account_path = os.getenv('GOOGLE_APPLICATION_CREDENTIALS')
        if not service_account_path:
            logger.error("GOOGLE_APPLICATION_CREDENTIALS environment variable not set")
            return
        
        cred = credentials.Certificate(service_account_path)
        app = firebase_admin.initialize_app(cred)
        db = firestore.client()
    
    logger.info("Firebase Admin SDK initialized successfully")
    
    # Test 1: Check that we can query evidence_items with promise_ids arrays
    logger.info("Test 1: Querying evidence_items with promise_ids arrays...")
    
    try:
        # Get a sample promise ID
        promises_query = db.collection('promises').where('status', '==', 'active').limit(5)
        promises = list(promises_query.stream())
        
        if not promises:
            logger.warning("No active promises found for testing")
            return
        
        test_promise_id = promises[0].id
        logger.info(f"Testing with promise ID: {test_promise_id}")
        
        # Query evidence_items that link to this promise
        evidence_query = db.collection('evidence_items').where('promise_ids', 'array_contains', test_promise_id)
        evidence_items = list(evidence_query.stream())
        
        logger.info(f"Found {len(evidence_items)} evidence items linked to promise {test_promise_id}")
        
        # Display evidence structure
        for i, evidence_doc in enumerate(evidence_items[:3]):  # Show first 3
            evidence_data = evidence_doc.to_dict()
            logger.info(f"Evidence {i+1}: {evidence_doc.id}")
            logger.info(f"  - promise_ids: {evidence_data.get('promise_ids', [])}")
            logger.info(f"  - evidence_type: {evidence_data.get('evidence_source_type', 'unknown')}")
            logger.info(f"  - evidence_date: {evidence_data.get('evidence_date', 'unknown')}")
    
    except Exception as e:
        logger.error(f"Error in Test 1: {e}")
        return
    
    # Test 2: Create and test ProgressScorer with new data structure
    logger.info("Test 2: Testing ProgressScorer with updated data structure...")
    
    try:
        # Create progress scorer instance
        config = {
            'batch_size': 5,
            'max_promises_per_run': 3
        }
        
        scorer = ProgressScorer('test_progress_scorer', config)
        
        # Test getting evidence items for a promise
        evidence_items = scorer._get_promise_evidence_items(test_promise_id)
        logger.info(f"ProgressScorer found {len(evidence_items)} evidence items for promise {test_promise_id}")
        
        if evidence_items:
            # Test analysis
            score_breakdown = scorer._analyze_evidence_links(evidence_items)
            logger.info(f"Score breakdown: {json.dumps(score_breakdown, indent=2, default=str)}")
            
            # Test latest evidence date calculation
            latest_date = scorer._get_latest_evidence_date(evidence_items)
            logger.info(f"Latest evidence date: {latest_date}")
        
    except Exception as e:
        logger.error(f"Error in Test 2: {e}")
        return
    
    # Test 3: Check promises collection structure
    logger.info("Test 3: Checking promises collection structure...")
    
    try:
        promise_doc = promises[0]
        promise_data = promise_doc.to_dict()
        
        logger.info(f"Promise {promise_doc.id} structure:")
        logger.info(f"  - linked_evidence_ids: {promise_data.get('linked_evidence_ids', [])}")
        logger.info(f"  - progress_score: {promise_data.get('progress_score', 'not set')}")
        logger.info(f"  - last_scored_at: {promise_data.get('last_scored_at', 'not set')}")
        logger.info(f"  - evidence_count: {promise_data.get('evidence_count', 'not set')}")
        
    except Exception as e:
        logger.error(f"Error in Test 3: {e}")
        return
    
    logger.info("All tests completed successfully!")

if __name__ == "__main__":
    asyncio.run(test_progress_scorer_data_structure()) 