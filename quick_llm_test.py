#!/usr/bin/env python3
"""Quick test of LLM scoring functionality"""

import sys
from pathlib import Path

# Add paths
sys.path.insert(0, str(Path(__file__).parent))
sys.path.insert(0, str(Path(__file__).parent / 'pipeline'))

from pipeline.stages.linking.progress_scorer import ProgressScorer
from dotenv import load_dotenv

load_dotenv()

config = {'use_llm_scoring': True, 'max_evidence_per_promise': 5}
scorer = ProgressScorer('test', config)

# Get first promise for testing
promises = scorer._get_promises_to_score()
if promises:
    promise = promises[0]
    evidence = scorer._get_promise_evidence_items(promise['_doc_id'])[:3]  # Limit for testing
    print(f'Testing LLM scoring for promise with {len(evidence)} evidence items...')
    
    if evidence:
        result = scorer._llm_based_scoring(promise, evidence)
        if result:
            print(f'✅ LLM Score: {result["overall_score"]}/5')
            print(f'Status: {result["fulfillment_status"]}')
            print(f'Summary: {result["progress_summary"][:150]}...')
            print(f'Used LLM: {result.get("used_llm", False)}')
        else:
            print('❌ LLM scoring returned None')
    else:
        print('No evidence available for testing')
else:
    print('No promises available for testing') 