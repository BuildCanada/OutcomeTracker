#!/usr/bin/env python3
"""
Test processor with correct configuration to include private bills
"""

import logging
import sys
from pathlib import Path

# Setup logging to see all details
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)

# Add pipeline directory to path
pipeline_dir = Path(__file__).parent
sys.path.insert(0, str(pipeline_dir))

from pipeline.stages.processing.legisinfo_processor import LegisInfoProcessor

def test_processor_with_config():
    """Test the processor with correct configuration"""
    print("🧪 Starting processor test with private bills enabled...")
    
    # Configure to include private bills and lower relevance threshold
    config = {
        'max_items_per_run': 10,
        'batch_size': 1,
        'include_private_bills': True,  # ← ENABLE PRIVATE BILLS!
        'min_relevance_threshold': 0.1  # ← LOWER THRESHOLD!
    }
    
    processor = LegisInfoProcessor("test_with_config", config)
    
    try:
        # Run the processor
        result = processor.execute()
        
        print(f"\n📊 RESULTS:")
        print(f"  Items processed: {result.items_processed}")
        print(f"  Items created: {result.items_created}")
        print(f"  Items updated: {result.items_updated}")
        print(f"  Items skipped: {result.items_skipped}")
        print(f"  Errors: {result.errors}")
        print(f"  Status: {result.status}")
        
        if hasattr(result, 'metadata'):
            print(f"  Metadata: {result.metadata}")
        
        return result
        
    except Exception as e:
        print(f"❌ FATAL ERROR: {e}")
        import traceback
        traceback.print_exc()
        return None

if __name__ == "__main__":
    test_processor_with_config() 