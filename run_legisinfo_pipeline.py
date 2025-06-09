#!/usr/bin/env python3
"""
LEGISinfo Production Pipeline Runner

Runs the LEGISinfo Bills ingestion and processing jobs in sequence to fetch
bills with XML content and process them with LLM synthesis.
"""

import logging
import sys
import argparse
from datetime import datetime, timezone
from pathlib import Path

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(name)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)

def run_ingestion(max_bills=None, since_hours=24):
    """Run the LEGISinfo Bills ingestion job"""
    logger = logging.getLogger("legisinfo_ingestion")
    logger.info("Starting LEGISinfo Bills ingestion...")
    
    try:
        from pipeline.stages.ingestion.legisinfo_bills import LegisInfoBillsIngestion
        
        # Configure the job
        config = {}
        if max_bills:
            config['max_bills_per_run'] = max_bills
        
        # Create and run the job
        job = LegisInfoBillsIngestion("legisinfo_bills_production", config)
        result = job._execute_job(since_hours=since_hours)
        
        logger.info("Ingestion completed successfully!")
        logger.info(f"  Items processed: {result['items_processed']}")
        logger.info(f"  Items created: {result['items_created']}")
        logger.info(f"  Items updated: {result['items_updated']}")
        logger.info(f"  Items skipped: {result['items_skipped']}")
        logger.info(f"  Errors: {result['errors']}")
        
        return result
        
    except Exception as e:
        logger.error(f"Ingestion failed: {e}", exc_info=True)
        raise

def run_processing(max_items=None):
    """Run the LEGISinfo Processing job"""
    logger = logging.getLogger("legisinfo_processing")
    logger.info("Starting LEGISinfo Bills processing...")
    
    try:
        from pipeline.stages.processing.legisinfo_processor import LegisInfoProcessor
        
        # Configure the job
        config = {}
        if max_items:
            config['max_items_per_run'] = max_items
        
        # Create and run the job
        job = LegisInfoProcessor("legisinfo_processor_production", config)
        result = job._execute_job()
        
        logger.info("Processing completed successfully!")
        logger.info(f"  Items processed: {result['items_processed']}")
        logger.info(f"  Items created: {result['items_created']}")
        logger.info(f"  Items updated: {result['items_updated']}")
        logger.info(f"  Items skipped: {result['items_skipped']}")
        logger.info(f"  Errors: {result['errors']}")
        
        return result
        
    except Exception as e:
        logger.error(f"Processing failed: {e}", exc_info=True)
        raise

def main():
    """Main function to orchestrate the pipeline"""
    parser = argparse.ArgumentParser(description="Run LEGISinfo Bills ingestion and processing pipeline")
    parser.add_argument("--max_bills", type=int, help="Maximum number of bills to ingest (default: no limit)")
    parser.add_argument("--max_items", type=int, help="Maximum number of items to process (default: no limit)")
    parser.add_argument("--since_hours", type=int, default=24, help="Only fetch bills updated in last N hours (default: 24)")
    parser.add_argument("--ingestion_only", action="store_true", help="Run only ingestion, skip processing")
    parser.add_argument("--processing_only", action="store_true", help="Run only processing, skip ingestion")
    parser.add_argument("--log_level", choices=["DEBUG", "INFO", "WARNING", "ERROR"], default="INFO", help="Set logging level")
    
    args = parser.parse_args()
    
    # Set logging level
    logging.getLogger().setLevel(getattr(logging, args.log_level))
    
    logger = logging.getLogger("legisinfo_pipeline")
    
    logger.info("🚀 Starting LEGISinfo Production Pipeline")
    logger.info(f"Configuration:")
    logger.info(f"  Max bills to ingest: {args.max_bills or 'unlimited'}")
    logger.info(f"  Max items to process: {args.max_items or 'unlimited'}")
    logger.info(f"  Since hours: {args.since_hours}")
    logger.info(f"  Ingestion only: {args.ingestion_only}")
    logger.info(f"  Processing only: {args.processing_only}")
    
    start_time = datetime.now()
    ingestion_result = None
    processing_result = None
    
    try:
        # Run ingestion
        if not args.processing_only:
            logger.info("\n" + "="*60)
            logger.info("PHASE 1: INGESTION")
            logger.info("="*60)
            ingestion_result = run_ingestion(args.max_bills, args.since_hours)
        
        # Run processing
        if not args.ingestion_only:
            logger.info("\n" + "="*60)
            logger.info("PHASE 2: PROCESSING")
            logger.info("="*60)
            processing_result = run_processing(args.max_items)
        
        # Final summary
        total_time = datetime.now() - start_time
        logger.info("\n" + "="*60)
        logger.info("🎉 PIPELINE COMPLETED SUCCESSFULLY")
        logger.info("="*60)
        logger.info(f"Total runtime: {total_time}")
        
        if ingestion_result:
            logger.info(f"Ingestion: {ingestion_result['items_created']} created, {ingestion_result['items_updated']} updated")
        
        if processing_result:
            logger.info(f"Processing: {processing_result['items_created']} created, {processing_result['items_updated']} updated")
        
        logger.info("All bills now include LLM-synthesized XML content for improved evidence linking!")
        
    except Exception as e:
        logger.error(f"Pipeline failed: {e}", exc_info=True)
        sys.exit(1)

if __name__ == "__main__":
    main() 