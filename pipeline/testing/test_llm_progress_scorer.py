#!/usr/bin/env python3
"""
Test Script for LLM-Based Progress Scorer

This script tests the updated progress scorer to ensure:
1. LLM integration works correctly
2. 1-5 scale scoring produces valid results
3. Progress summaries are generated
4. Fallback to rule-based scoring works
5. Database updates are properly formatted
"""

import os
import sys
import asyncio
import logging
from pathlib import Path
from datetime import datetime
from dotenv import load_dotenv

# Add project paths
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))
sys.path.insert(0, str(project_root / 'pipeline'))

from pipeline.stages.linking.progress_scorer import ProgressScorer

# Load environment
load_dotenv()

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

async def test_llm_progress_scorer():
    """Test the LLM-based progress scorer"""
    
    logger.info("=== Testing LLM-Based Progress Scorer ===")
    
    # Initialize progress scorer with simple config dict
    config = {
        'batch_size': 3,  # Very small batch for testing
        'max_promises_per_run': 5,  # Small limit for testing
        'use_llm_scoring': True,
        'max_evidence_per_promise': 10  # Reduced for testing
    }
    
    try:
        scorer = ProgressScorer('test_progress_scorer', config)
        logger.info("✅ Progress Scorer initialized successfully")
        
        # Test LangChain initialization
        if scorer.langchain:
            logger.info("✅ LangChain integration working")
        else:
            logger.warning("⚠️ LangChain not available, will test rule-based fallback")
        
        # Test prompt loading
        if scorer.progress_prompt:
            logger.info(f"✅ Progress scoring prompt loaded ({len(scorer.progress_prompt)} characters)")
        else:
            logger.warning("⚠️ Progress scoring prompt not loaded")
        
        # Test getting promises to score
        promises = scorer._get_promises_to_score()
        logger.info(f"✅ Found {len(promises)} promises for scoring")
        
        if not promises:
            logger.warning("No promises found for testing. Make sure database has active promises.")
            return
        
        # Test scoring a single promise
        test_promise = promises[0]
        promise_id = test_promise['_doc_id']
        logger.info(f"Testing scoring for promise: {promise_id}")
        
        # Get evidence for the promise
        evidence_items = scorer._get_promise_evidence_items(promise_id)
        logger.info(f"Found {len(evidence_items)} evidence items for promise")
        
        if evidence_items:
            # Test LLM-based scoring if available
            if scorer.use_llm_scoring and scorer.langchain and scorer.progress_prompt:
                logger.info("Testing LLM-based scoring...")
                try:
                    llm_result = scorer._llm_based_scoring(test_promise, evidence_items[:5])  # Limit evidence for faster testing
                    if llm_result:
                        logger.info("✅ LLM-based scoring successful:")
                        logger.info(f"  - Score: {llm_result['overall_score']}/5")
                        logger.info(f"  - Status: {llm_result['fulfillment_status']}")
                        logger.info(f"  - Summary: {llm_result['progress_summary'][:100]}...")
                        logger.info(f"  - Used LLM: {llm_result.get('used_llm', False)}")
                    else:
                        logger.error("❌ LLM-based scoring returned None")
                except Exception as e:
                    logger.error(f"❌ LLM-based scoring failed: {e}")
            
            # Test rule-based scoring fallback
            logger.info("Testing rule-based scoring fallback...")
            try:
                rule_result = scorer._rule_based_scoring(test_promise, evidence_items)
                if rule_result:
                    logger.info("✅ Rule-based scoring successful:")
                    logger.info(f"  - Score: {rule_result['overall_score']}/5")
                    logger.info(f"  - Status: {rule_result['fulfillment_status']}")
                    logger.info(f"  - Summary: {rule_result['progress_summary'][:100]}...")
                    logger.info(f"  - Used LLM: {rule_result.get('used_llm', False)}")
                else:
                    logger.error("❌ Rule-based scoring returned None")
            except Exception as e:
                logger.error(f"❌ Rule-based scoring failed: {e}")
        
        else:
            logger.info("Testing scoring for promise with no evidence...")
            try:
                no_evidence_result = scorer._calculate_promise_score(test_promise)
                if no_evidence_result:
                    logger.info("✅ No-evidence scoring successful:")
                    logger.info(f"  - Score: {no_evidence_result['overall_score']}/5")
                    logger.info(f"  - Status: {no_evidence_result['fulfillment_status']}")
                    logger.info(f"  - Summary: {no_evidence_result['progress_summary']}")
                else:
                    logger.error("❌ No-evidence scoring returned None")
            except Exception as e:
                logger.error(f"❌ No-evidence scoring failed: {e}")
        
        # Test score to status conversion
        logger.info("Testing score to status conversion...")
        test_scores = [1, 2, 3, 4, 5]
        for score in test_scores:
            status = scorer._score_to_status(score)
            logger.info(f"  Score {score} -> Status: {status}")
        
        # Test batch processing (dry run)
        logger.info("Testing batch processing (limited to 2 promises)...")
        try:
            test_batch = promises[:2]  # Even smaller batch for testing
            batch_stats = scorer._score_promise_batch(test_batch)
            logger.info("✅ Batch processing successful:")
            logger.info(f"  - Promises processed: {batch_stats['promises_processed']}")
            logger.info(f"  - Scores updated: {batch_stats['scores_updated']}")
            logger.info(f"  - Status changes: {batch_stats['status_changes']}")
            logger.info(f"  - Errors: {batch_stats['errors']}")
            logger.info(f"  - LLM calls: {batch_stats['llm_calls']}")
        except Exception as e:
            logger.error(f"❌ Batch processing failed: {e}")
        
        # Test cost tracking if LLM was used
        if scorer.langchain:
            try:
                cost_summary = scorer.langchain.get_cost_summary()
                logger.info("✅ Cost tracking working:")
                logger.info(f"  - Total estimated cost: ${cost_summary.get('total_cost_usd', 0):.4f}")
                logger.info(f"  - Total tokens: {cost_summary.get('total_tokens', {})}")
            except Exception as e:
                logger.error(f"❌ Cost tracking failed: {e}")
        
        logger.info("=== Progress Scorer Test Complete ===")
        
    except Exception as e:
        logger.error(f"❌ Progress Scorer initialization failed: {e}")
        raise

async def test_prompt_format():
    """Test that the progress scoring prompt is properly formatted"""
    
    logger.info("=== Testing Progress Scoring Prompt Format ===")
    
    prompt_path = Path(__file__).parent / 'prompts' / 'prompt_progress_scoring.md'
    
    if not prompt_path.exists():
        logger.error(f"❌ Progress scoring prompt not found: {prompt_path}")
        return
    
    prompt_content = prompt_path.read_text()
    
    # Check for key components
    required_sections = [
        'Progress Scoring Scale (1-5)',
        'Score 1 - No Progress',
        'Score 2 - Initial Steps', 
        'Score 3 - Meaningful Action',
        'Score 4 - Major Progress',
        'Score 5 - Complete/Fully Implemented',
        'Output Format',
        'progress_score',
        'progress_summary'
    ]
    
    missing_sections = []
    for section in required_sections:
        if section not in prompt_content:
            missing_sections.append(section)
    
    if missing_sections:
        logger.error(f"❌ Prompt missing required sections: {missing_sections}")
    else:
        logger.info("✅ Prompt contains all required sections")
    
    logger.info(f"Prompt length: {len(prompt_content)} characters")
    
    # Check JSON format example
    if '{"progress_score":' in prompt_content or '"progress_score":' in prompt_content:
        logger.info("✅ Prompt contains JSON format example")
    else:
        logger.warning("⚠️ Prompt may be missing JSON format example")

if __name__ == "__main__":
    # Test prompt format first
    asyncio.run(test_prompt_format())
    
    # Test the progress scorer
    asyncio.run(test_llm_progress_scorer()) 