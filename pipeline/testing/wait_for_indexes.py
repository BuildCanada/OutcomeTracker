#!/usr/bin/env python3
"""
Wait for Firestore Indexes to be Ready

This script polls the Firestore indexes until they're ready, then automatically
proceeds to test the processing pipeline.

Usage:
    python wait_for_indexes.py [--max-wait=300]
"""

import sys
import time
import argparse
from pathlib import Path

# Add pipeline directory to path
pipeline_dir = Path(__file__).parent.parent
sys.path.insert(0, str(pipeline_dir))

from check_firestore_indexes import check_all_indexes


def wait_for_indexes(max_wait_seconds: int = 300):
    """
    Wait for all required indexes to be ready.
    
    Args:
        max_wait_seconds: Maximum time to wait in seconds (default: 5 minutes)
    """
    print("⏳ Waiting for Firestore indexes to be ready...")
    print(f"Will check every 30 seconds for up to {max_wait_seconds // 60} minutes")
    print("=" * 60)
    
    start_time = time.time()
    check_interval = 30  # Check every 30 seconds
    
    while True:
        elapsed = time.time() - start_time
        
        if elapsed > max_wait_seconds:
            print(f"\n⏰ Timeout reached ({max_wait_seconds}s). Indexes may still be building.")
            print("You can check manually with: python check_firestore_indexes.py")
            return False
        
        print(f"\n🔄 Checking indexes... ({elapsed:.0f}s elapsed)")
        
        # Check if all indexes are ready
        if check_all_indexes():
            print("\n🎉 All indexes are ready! Proceeding to next steps...")
            return True
        
        print(f"⏳ Still building... will check again in {check_interval}s")
        time.sleep(check_interval)


def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(description='Wait for Firestore indexes to be ready')
    parser.add_argument('--max-wait', type=int, default=300,
                       help='Maximum time to wait in seconds (default: 300)')
    
    args = parser.parse_args()
    
    try:
        if wait_for_indexes(args.max_wait):
            print("\n🚀 Ready to proceed to Step 2: Testing Processing Pipeline")
            print("Run: python pipeline_validation.py --component processing --verbose")
            sys.exit(0)
        else:
            sys.exit(1)
            
    except KeyboardInterrupt:
        print("\n🛑 Wait interrupted by user")
        print("You can check index status with: python check_firestore_indexes.py")
        sys.exit(130)
    except Exception as e:
        print(f"💥 Wait failed with error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main() 