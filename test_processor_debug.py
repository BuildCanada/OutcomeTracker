#!/usr/bin/env python3
"""
Test processor on the 6 reset bills to capture exact errors
"""

import logging
import sys
from pathlib import Path

# Setup logging to see all details
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)

# Add pipeline directory to path
pipeline_dir = Path(__file__).parent
sys.path.insert(0, str(pipeline_dir))

from pipeline.stages.processing.legisinfo_processor import LegisInfoProcessor

def test_processor():
    """Test the processor on the reset bills"""
    print("🧪 Starting processor test on reset bills...")
    
    # Configure for test run
    config = {
        'max_items_per_run': 10,  # Limit to just our test bills
        'batch_size': 1  # Process one at a time for detailed logging
    }
    
    processor = LegisInfoProcessor("test_processor_debug", config)
    
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
    test_processor() 