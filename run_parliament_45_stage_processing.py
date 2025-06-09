#!/usr/bin/env python3
"""
Run Parliament 45 Stage-Based Processing

This script processes Parliament 45 bills using the new stage-based approach
that creates separate evidence items for each parliamentary stage.
"""

import logging
import sys
from pathlib import Path
from datetime import datetime, timezone

# Add pipeline directory to path
pipeline_dir = Path(__file__).parent / "pipeline"
sys.path.insert(0, str(pipeline_dir))

from stages.processing.legisinfo_processor import LegisInfoProcessor

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(name)s - %(message)s'
)

def main():
    """Run Parliament 45 stage-based processing"""
    
    print("🏛️  PARLIAMENT 45 STAGE-BASED PROCESSING")
    print("=" * 50)
    
    # Configuration for Parliament 45 processing
    config = {
        'batch_size': 10,  # Process in batches of 10
        'include_private_bills': True,  # Include private member bills
        'min_relevance_threshold': 0.1,  # Lower threshold for relevance
        'force_reprocessing': False  # Don't force reprocess existing items
    }
    
    print(f"📊 Configuration:")
    print(f"   - Batch size: {config['batch_size']}")
    print(f"   - Include private bills: {config['include_private_bills']}")
    print(f"   - Min relevance threshold: {config['min_relevance_threshold']}")
    print(f"   - Force reprocessing: {config['force_reprocessing']}")
    print()
    
    # Create processor with configuration
    processor = LegisInfoProcessor(job_name="parliament_45_stage_processing", config=config)
    
    print("🚀 Starting Parliament 45 stage-based processing...")
    print(f"⏰ Started at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print()
    
    # Execute the processor
    result = processor.execute()
    
    print()
    print("✅ PROCESSING COMPLETED")
    print("=" * 30)
    print(f"📊 Status: {result.status.value}")
    print(f"⏰ Completed at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    if result.metadata:
        print(f"📈 Statistics:")
        for key, value in result.metadata.items():
            print(f"   - {key}: {value}")
    
    if result.status.value == 'success':
        print()
        print("🎉 Parliament 45 bills now have stage-based evidence items!")
        print("   Each bill stage (First Reading, Second Reading, etc.) is now")
        print("   represented as a separate evidence item for timeline display.")
    else:
        print()
        print("⚠️  Processing completed with issues. Check logs for details.")

if __name__ == "__main__":
    main() 