#!/usr/bin/env python3
"""
Run Parliament 45 Bill Ingestion

This script runs the LegisInfo bill ingestion for Parliament 45 session 1.
"""

import logging
import sys
from pathlib import Path
from datetime import datetime, timezone

# Add pipeline directory to path
pipeline_dir = Path(__file__).parent / "pipeline"
sys.path.insert(0, str(pipeline_dir))

from stages.ingestion.legisinfo_bills import LegisInfoBillsIngestion

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(name)s - %(message)s'
)

def main():
    """Run Parliament 45 bill ingestion"""
    
    # Configuration for Parliament 45 ingestion
    config = {
        'min_parliament': 45,
        'max_parliament': 45,
        'include_xml': True,
        'batch_size': 10
    }
    
    # Create and run the ingestion job
    ingestion_job = LegisInfoBillsIngestion(
        job_name="parliament_45_bill_ingestion",
        config=config
    )
    
    print("🚀 Starting Parliament 45 Bill Ingestion...")
    print(f"Configuration: {config}")
    
    # Execute the job with a large since_hours to force re-ingestion
    # 365 * 24 = 8760 hours = 1 year
    result = ingestion_job.execute(since_hours=8760)
    
    # Display results
    print(f"\n✅ Ingestion completed with status: {result.status.value}")
    print(f"📊 Items processed: {result.items_processed}")
    print(f"➕ Items created: {result.items_created}")
    print(f"🔄 Items updated: {result.items_updated}")
    print(f"⏭️  Items skipped: {result.items_skipped}")
    print(f"❌ Errors: {result.errors}")
    print(f"⏱️  Duration: {result.duration_seconds:.2f} seconds")
    
    if result.metadata:
        print(f"\n📝 Additional Details:")
        for key, value in result.metadata.items():
            print(f"  {key}: {value}")

if __name__ == "__main__":
    main() 