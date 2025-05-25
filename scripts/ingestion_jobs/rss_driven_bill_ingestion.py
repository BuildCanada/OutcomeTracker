"""
RSS-driven bill ingestion scheduler for optimal daily runs.
Combines RSS feed checking with the existing two-stage LEGISinfo ingestion system.

This script:
1. Checks RSS feed for recently updated bills
2. Runs Stage 1 (raw ingestion) only on bills with recent RSS activity
3. Runs Stage 2 (processing to evidence) on any pending bills
4. Provides fallback to full ingestion if RSS has issues

CLI arguments:
--hours_threshold: Check RSS for bills updated within this many hours (default: 24)
--parliament_filter: Only process bills from this parliament (default: 44)
--fallback_full_run: If RSS finds no updates, run full ingestion anyway (default: False)
--dry_run: Perform dry run for all stages (default: False)
--skip_stage2: Skip Stage 2 processing (default: False)
--log_level: Set logging level (default: INFO)

This is the recommended approach for daily scheduled runs as it:
- Only processes bills that actually had recent activity (RSS-driven efficiency)
- Maintains comprehensive coverage with optional fallback
- Preserves all existing functionality of the two-stage system
"""

import os
import logging
import argparse
import subprocess
import sys
import tempfile
from datetime import datetime
from dotenv import load_dotenv

# --- Configuration ---
load_dotenv()

# --- Logger Setup ---
logging.basicConfig(level=logging.INFO,
                    format='%(asctime)s - %(levelname)s - %(filename)s:%(lineno)d - %(message)s',
                    datefmt='%Y-%m-%d %H:%M:%S')
logger = logging.getLogger("rss_driven_bill_ingestion")
# --- End Logger Setup ---

# --- Constants ---
DEFAULT_HOURS_THRESHOLD = 24
DEFAULT_PARLIAMENT_FILTER = 44
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
RSS_CHECKER_SCRIPT = os.path.join(SCRIPT_DIR, "check_legisinfo_rss_updates.py")
STAGE1_SCRIPT = os.path.join(SCRIPT_DIR, "ingest_legisinfo_raw_bills.py")
STAGE2_SCRIPT = os.path.join(SCRIPT_DIR, "..", "processing_jobs", "process_raw_legisinfo_to_evidence.py")
# --- End Constants ---

def run_command(cmd_args, description):
    """Run a subprocess command and handle logging"""
    logger.info(f"Running: {description}")
    logger.debug(f"Command: {' '.join(cmd_args)}")
    
    try:
        result = subprocess.run(
            cmd_args,
            capture_output=True,
            text=True,
            check=True
        )
        
        # Log stdout if present
        if result.stdout.strip():
            logger.info(f"{description} output:\n{result.stdout}")
        
        logger.info(f"{description} completed successfully")
        return True, result.stdout
        
    except subprocess.CalledProcessError as e:
        logger.error(f"{description} failed with exit code {e.returncode}")
        if e.stdout:
            logger.error(f"Stdout: {e.stdout}")
        if e.stderr:
            logger.error(f"Stderr: {e.stderr}")
        return False, None
    except Exception as e:
        logger.error(f"Error running {description}: {e}")
        return False, None

def check_rss_updates(hours_threshold, parliament_filter, temp_file):
    """Check RSS feed for recent updates and save to temp file"""
    cmd_args = [
        sys.executable,
        RSS_CHECKER_SCRIPT,
        "--hours_threshold", str(hours_threshold),
        "--parliament_filter", str(parliament_filter),
        "--output_file", temp_file,
        "--output_format", "json"
    ]
    
    success, output = run_command(cmd_args, "RSS update check")
    
    if not success:
        return False, 0
    
    # Parse the output to count bills found
    import json
    try:
        with open(temp_file, 'r') as f:
            rss_data = json.load(f)
        return True, len(rss_data)
    except Exception as e:
        logger.error(f"Error reading RSS results from {temp_file}: {e}")
        return False, 0

def run_stage1_ingestion(rss_file=None, dry_run=False, fallback_full_run=False, extra_args=None):
    """Run Stage 1 (raw bill ingestion)"""
    # Import monitoring
    try:
        from .rss_monitoring_logger import rss_monitor
    except ImportError:
        rss_monitor = None
    
    cmd_args = [sys.executable, STAGE1_SCRIPT]
    
    if rss_file:
        cmd_args.extend(["--rss_filter_file", rss_file])
        description = "Stage 1 (RSS-filtered raw ingestion)"
    elif fallback_full_run:
        cmd_args.extend(["--min_parliament", str(DEFAULT_PARLIAMENT_FILTER)])
        description = "Stage 1 (fallback full ingestion)"
    else:
        logger.info("Skipping Stage 1 - no RSS updates and fallback disabled")
        return True
    
    if dry_run:
        cmd_args.append("--dry_run")
    
    if extra_args:
        cmd_args.extend(extra_args)
    
    success, output = run_command(cmd_args, description)
    return success

def run_stage2_processing(dry_run=False):
    """Run Stage 2 (processing to evidence)"""
    cmd_args = [sys.executable, STAGE2_SCRIPT]
    
    if dry_run:
        cmd_args.append("--dry_run")
    
    success, output = run_command(cmd_args, "Stage 2 (evidence processing)")
    return success

def main():
    parser = argparse.ArgumentParser(description="RSS-driven bill ingestion for optimal daily runs.")
    parser.add_argument("--hours_threshold", type=int, default=DEFAULT_HOURS_THRESHOLD,
                       help=f"Check RSS for bills updated within this many hours (default: {DEFAULT_HOURS_THRESHOLD})")
    parser.add_argument("--parliament_filter", type=int, default=DEFAULT_PARLIAMENT_FILTER,
                       help=f"Only process bills from this parliament (default: {DEFAULT_PARLIAMENT_FILTER})")
    parser.add_argument("--fallback_full_run", action="store_true",
                       help="If RSS finds no updates, run full ingestion anyway (default: False)")
    parser.add_argument("--dry_run", action="store_true",
                       help="Perform dry run for all stages (default: False)")
    parser.add_argument("--skip_stage2", action="store_true",
                       help="Skip Stage 2 processing (default: False)")
    parser.add_argument("--log_level", type=str, default="INFO",
                       choices=['DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL'],
                       help="Set the logging level")
    parser.add_argument("--limit", type=int,
                       help="Limit number of bills to process (for testing)")
    
    args = parser.parse_args()
    logger.setLevel(getattr(logging, args.log_level.upper()))
    
    start_time = datetime.now()
    logger.info("=== Starting RSS-Driven Bill Ingestion ===")
    logger.info(f"Configuration:")
    logger.info(f"  Hours threshold: {args.hours_threshold}")
    logger.info(f"  Parliament filter: {args.parliament_filter}")
    logger.info(f"  Fallback full run: {args.fallback_full_run}")
    logger.info(f"  Dry run: {args.dry_run}")
    logger.info(f"  Skip Stage 2: {args.skip_stage2}")
    
    overall_success = True
    bills_from_rss = 0
    
    # Create temporary file for RSS results
    with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as temp_file:
        temp_filename = temp_file.name
    
    try:
        # Step 1: Check RSS for recent updates
        logger.info("--- Step 1: Checking RSS for Recent Updates ---")
        rss_success, bills_from_rss = check_rss_updates(
            args.hours_threshold, 
            args.parliament_filter, 
            temp_filename
        )
        
        if not rss_success:
            logger.error("RSS check failed")
            overall_success = False
            bills_from_rss = 0
        else:
            logger.info(f"RSS check found {bills_from_rss} recently updated bills")
        
        # Step 2: Run Stage 1 (Raw Ingestion)
        logger.info("--- Step 2: Stage 1 Raw Bill Ingestion ---")
        
        # Prepare extra arguments for Stage 1 (for testing purposes)
        stage1_extra_args = []
        if hasattr(args, 'limit') and args.limit:
            stage1_extra_args.extend(["--limit", str(args.limit)])
        
        if bills_from_rss > 0:
            stage1_success = run_stage1_ingestion(
                rss_file=temp_filename, 
                dry_run=args.dry_run,
                extra_args=stage1_extra_args
            )
        else:
            stage1_success = run_stage1_ingestion(
                rss_file=None, 
                dry_run=args.dry_run, 
                fallback_full_run=args.fallback_full_run,
                extra_args=stage1_extra_args
            )
        
        if not stage1_success:
            logger.error("Stage 1 ingestion failed")
            overall_success = False
        
        # Step 3: Run Stage 2 (Processing to Evidence)
        if not args.skip_stage2:
            logger.info("--- Step 3: Stage 2 Evidence Processing ---")
            stage2_success = run_stage2_processing(dry_run=args.dry_run)
            
            if not stage2_success:
                logger.error("Stage 2 processing failed")
                overall_success = False
        else:
            logger.info("--- Step 3: Skipped (Stage 2 disabled) ---")
    
    finally:
        # Clean up temporary file
        try:
            os.unlink(temp_filename)
        except Exception as e:
            logger.warning(f"Failed to clean up temporary file {temp_filename}: {e}")
    
    # Summary
    end_time = datetime.now()
    duration = end_time - start_time
    
    logger.info("=== RSS-Driven Bill Ingestion Summary ===")
    logger.info(f"Start time: {start_time}")
    logger.info(f"End time: {end_time}")
    logger.info(f"Duration: {duration}")
    logger.info(f"Bills from RSS: {bills_from_rss}")
    logger.info(f"Overall success: {overall_success}")
    
    if overall_success:
        logger.info("✅ RSS-driven ingestion completed successfully")
        sys.exit(0)
    else:
        logger.error("❌ RSS-driven ingestion completed with errors")
        sys.exit(1)

if __name__ == "__main__":
    main() 