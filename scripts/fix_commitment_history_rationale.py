#!/usr/bin/env python3
"""
Migration Script: Fix Commitment History Rationale Format

This script converts commitment_history_rationale fields from string format to array format.
The frontend expects an array of RationaleEvent objects, but some records have string data.

String format (current):
"2017-06-07: Action description\n2019-09-10: Another action\n..."

Array format (expected):
[
  {"date": "2017-06-07", "action": "Action description", "source_url": ""},
  {"date": "2019-09-10", "action": "Another action", "source_url": ""},
  ...
]
"""

import firebase_admin
from firebase_admin import firestore, credentials
import os
import sys
import asyncio
import logging
import traceback
from dotenv import load_dotenv
import re
from datetime import datetime

# Load environment variables
load_dotenv()

# Logger setup
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(filename)s:%(lineno)d - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger("fix_commitment_history")

# Firebase Configuration
db = None
if not firebase_admin._apps:
    try:
        firebase_admin.initialize_app()
        project_id = os.getenv('FIREBASE_PROJECT_ID', '[Not Set - Using Default]')
        logger.info(f"Connected to CLOUD Firestore (Project: {project_id}) using default credentials.")
        db = firestore.client()
    except Exception as e_default:
        logger.warning(f"Cloud Firestore init with default creds failed: {e_default}. Attempting service account.")
        cred_path = os.getenv('FIREBASE_SERVICE_ACCOUNT_KEY_PATH')
        if cred_path:
            try:
                logger.info(f"Attempting Firebase init with service account key from env var: {cred_path}")
                cred = credentials.Certificate(cred_path)
                app_name = 'fix_history_app'
                try:
                    firebase_admin.initialize_app(cred, name=app_name)
                except ValueError:
                    app_name_unique = f"{app_name}_{str(datetime.now().timestamp())}"
                    firebase_admin.initialize_app(cred, name=app_name_unique)
                    app_name = app_name_unique

                project_id_sa = os.getenv('FIREBASE_PROJECT_ID', '[Not Set - Using Service Account]')
                logger.info(f"Connected to CLOUD Firestore (Project: {project_id_sa}) via service account.")
                db = firestore.client(app=firebase_admin.get_app(name=app_name))
            except Exception as e_sa:
                logger.critical(f"Firebase init with service account key from {cred_path} failed: {e_sa}", exc_info=True)
        else:
            logger.warning("FIREBASE_SERVICE_ACCOUNT_KEY_PATH environment variable not set, and default creds failed.")

if db is None:
    logger.critical("CRITICAL: Failed to obtain Firestore client. Exiting.")
    exit("Exiting: Firestore client not available.")

# Constants
PROMISES_COLLECTION_ROOT = os.getenv("TARGET_PROMISES_COLLECTION", "promises")

def parse_string_rationale(rationale_string: str) -> list[dict]:
    """
    Parse a string-based rationale into an array of RationaleEvent objects.
    
    Expected string format:
    "2017-06-07: Action description\n2019-09-10: Another action\n..."
    
    Returns:
    [
      {"date": "2017-06-07", "action": "Action description", "source_url": ""},
      {"date": "2019-09-10", "action": "Another action", "source_url": ""},
      ...
    ]
    """
    if not rationale_string or not isinstance(rationale_string, str):
        return []
    
    events = []
    lines = rationale_string.strip().split('\n')
    
    for line in lines:
        line = line.strip()
        if not line:
            continue
            
        # Try to match date pattern at the beginning: YYYY-MM-DD: action
        date_match = re.match(r'^(\d{4}-\d{2}-\d{2}):\s*(.+)$', line)
        if date_match:
            date = date_match.group(1)
            action = date_match.group(2).strip()
            events.append({
                "date": date,
                "action": action,
                "source_url": ""
            })
        else:
            # If no date pattern found, treat as action with unknown date
            logger.warning(f"Could not parse date from line: {line}")
            events.append({
                "date": "Unknown date",
                "action": line,
                "source_url": ""
            })
    
    return events

async def query_promises_with_string_rationale(parliament_session_id: str = None, limit: int = None) -> list[dict]:
    """Query promises that have string-based commitment_history_rationale."""
    logger.info(f"Querying promises with string rationale: session '{parliament_session_id}', limit: {limit}")
    
    try:
        # Build query - simplified to avoid index requirements
        query = db.collection(PROMISES_COLLECTION_ROOT)
        
        # Get all promises that have commitment_history_rationale field
        query = query.where(filter=firestore.FieldFilter("commitment_history_rationale", "!=", None))
        
        if limit:
            query = query.limit(limit)
        
        # Execute query
        promise_docs = list(await asyncio.to_thread(query.stream))
        
        promises_to_fix = []
        for doc in promise_docs:
            data = doc.to_dict()
            rationale = data.get("commitment_history_rationale")
            
            # Filter by parliament_session_id if specified (after query)
            if parliament_session_id and data.get("parliament_session_id") != parliament_session_id:
                continue
            
            # Check if rationale is a string (needs fixing)
            if isinstance(rationale, str):
                promises_to_fix.append({
                    "id": doc.id,
                    "doc_ref": doc.reference,
                    "rationale": rationale,
                    "data": data
                })
            elif isinstance(rationale, list):
                logger.debug(f"Promise {doc.id} already has array format rationale")
            else:
                logger.warning(f"Promise {doc.id} has unexpected rationale type: {type(rationale)}")
        
        logger.info(f"Found {len(promises_to_fix)} promises with string rationale to fix")
        return promises_to_fix
        
    except Exception as e:
        logger.error(f"Error querying promises: {e}", exc_info=True)
        return []

async def fix_single_promise(promise: dict, dry_run: bool = False) -> bool:
    """Fix a single promise's commitment_history_rationale format."""
    try:
        promise_id = promise['id']
        rationale_string = promise['rationale']
        
        logger.info(f"Fixing promise {promise_id}")
        logger.debug(f"Original rationale: {rationale_string[:200]}...")
        
        # Parse string into array format
        rationale_array = parse_string_rationale(rationale_string)
        
        logger.info(f"Parsed {len(rationale_array)} events from string")
        for i, event in enumerate(rationale_array[:3]):  # Log first 3 events
            logger.debug(f"  Event {i+1}: {event['date']} - {event['action'][:50]}...")
        
        # Update the promise
        update_data = {
            "commitment_history_rationale": rationale_array,
            "rationale_format_fixed_at": firestore.SERVER_TIMESTAMP
        }
        
        if not dry_run:
            await asyncio.to_thread(promise['doc_ref'].update, update_data)
            logger.info(f"Successfully fixed promise {promise_id}")
        else:
            logger.info(f"[DRY RUN] Would fix promise {promise_id} with {len(rationale_array)} events")
        
        return True
        
    except Exception as e:
        logger.error(f"Error fixing promise {promise['id']}: {e}", exc_info=True)
        return False

async def run_migration(parliament_session_id: str = None, limit: int = None, dry_run: bool = False):
    """Run the migration to fix commitment_history_rationale format."""
    logger.info("=== Starting Commitment History Rationale Format Fix ===")
    logger.info(f"Parliament Session: {parliament_session_id or 'All'}")
    logger.info(f"Limit: {limit or 'None'}")
    logger.info(f"Dry Run: {dry_run}")
    
    if dry_run:
        logger.warning("*** DRY RUN MODE: No changes will be written to Firestore ***")
    
    # Query promises needing fixing
    promises = await query_promises_with_string_rationale(
        parliament_session_id=parliament_session_id,
        limit=limit
    )
    
    if not promises:
        logger.info("No promises found with string rationale format. Migration complete!")
        return
    
    logger.info(f"Processing {len(promises)} promises...")
    
    # Track statistics
    stats = {
        'total_processed': 0,
        'successful_fixes': 0,
        'errors': 0
    }
    
    # Process each promise
    for i, promise in enumerate(promises):
        logger.info(f"--- Processing promise {i+1}/{len(promises)}: {promise['id']} ---")
        
        success = await fix_single_promise(promise, dry_run)
        
        stats['total_processed'] += 1
        if success:
            stats['successful_fixes'] += 1
        else:
            stats['errors'] += 1
        
        # Small delay to avoid overwhelming Firestore
        if i < len(promises) - 1:
            await asyncio.sleep(0.1)
    
    # Log final statistics
    logger.info("=== Migration Complete ===")
    logger.info(f"Total promises processed: {stats['total_processed']}")
    logger.info(f"Successful fixes: {stats['successful_fixes']}")
    logger.info(f"Errors encountered: {stats['errors']}")

async def main():
    """Main entry point."""
    import argparse
    
    parser = argparse.ArgumentParser(description='Fix Commitment History Rationale Format')
    parser.add_argument(
        '--parliament_session_id',
        type=str,
        help='Parliament session ID to filter (optional)'
    )
    parser.add_argument(
        '--limit',
        type=int,
        help='Limit number of promises to process (optional)'
    )
    parser.add_argument(
        '--dry_run',
        action='store_true',
        help='Run without making changes to Firestore'
    )
    
    args = parser.parse_args()
    
    # Run migration
    await run_migration(
        parliament_session_id=args.parliament_session_id,
        limit=args.limit,
        dry_run=args.dry_run
    )
    
    logger.info("Migration script completed successfully!")

if __name__ == "__main__":
    asyncio.run(main()) 