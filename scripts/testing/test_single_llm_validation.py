#!/usr/bin/env python3
"""
Minimal test for LLM validation debugging

Tests a single evidence-promise pair to debug JSON parsing issues.
"""

import sys
import logging
from pathlib import Path
import json
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Add paths for imports
sys.path.append(str(Path(__file__).parent.parent.parent))
sys.path.append(str(Path(__file__).parent.parent.parent / 'lib'))

# Setup logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger("llm_debug")

try:
    from pipeline.stages.linking.llm_evidence_validator import LLMEvidenceValidator
    logger.info("Imported LLM validator successfully")
except ImportError as e:
    logger.error(f"Failed to import: {e}")
    sys.exit(1)

def test_single_validation():
    """Test a single evidence-promise validation to debug JSON issues."""
    
    # Initialize validator
    validator = LLMEvidenceValidator(validation_threshold=0.7)
    validator.initialize()
    
    # Create simple test data
    evidence_item = {
        'parliament_session_id': '44',
        'evidence_source_type': 'Regulation (Canada Gazette P2)',
        'evidence_date': '2021-10-13',
        'title_or_summary': 'Test regulation about agricultural products',
        'description_or_details': 'A regulation affecting agricultural marketing in Canada',
        'key_concepts': ['agriculture', 'regulation', 'marketing'],
        'linked_departments': ['Agriculture and Agri-Food Canada']
    }
    
    promise_item = {
        'promise_id': 'test_promise_1',
        'text': 'Support agricultural development in Canada',
        'description': 'Provide support for agricultural sectors',
        'background_and_context': 'Agricultural policy framework',
        'intended_impact_and_objectives': ['Support farmers', 'Improve food security'],
        'responsible_department_lead': 'Agriculture and Agri-Food Canada'
    }
    
    semantic_similarity_score = 0.6
    
    logger.info("Testing single evidence-promise validation...")
    
    try:
        # Test the validation
        result = validator.validate_match(evidence_item, promise_item, semantic_similarity_score)
        
        logger.info(f"Validation successful!")
        logger.info(f"Confidence: {result.confidence_score}")
        logger.info(f"Category: {result.category}")
        logger.info(f"Reasoning: {result.reasoning}")
        
        return True
        
    except Exception as e:
        logger.error(f"Validation failed: {e}")
        return False

if __name__ == "__main__":
    success = test_single_validation()
    if success:
        print("✅ Single validation test passed!")
    else:
        print("❌ Single validation test failed!") 