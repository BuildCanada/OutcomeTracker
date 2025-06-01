#!/usr/bin/env python3
"""
Fix linked_evidence_ids Synchronization Issue

This script fixes the critical synchronization problem where:
- Frontend expects promises.linked_evidence_ids (currently 2 items)
- Backend finds evidence via evidence_items.promise_ids (actually 38 items)

The script will:
1. Analyze the discrepancy between the two arrays
2. Update promises.linked_evidence_ids to match the evidence_items.promise_ids reality
3. Report on what was found and fixed
"""

import asyncio
import os
import sys
import json
import logging
from pathlib import Path
from typing import Dict, Any, List, Set
import firebase_admin
from firebase_admin import firestore, credentials
from dotenv import load_dotenv

# Load environment
load_dotenv()

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

async def analyze_and_fix_evidence_sync():
    """Analyze and fix the evidence synchronization issue"""
    
    # Initialize Firebase Admin SDK
    try:
        app = firebase_admin.get_app()
        db = firestore.client(app)
    except ValueError:
        service_account_path = os.getenv('GOOGLE_APPLICATION_CREDENTIALS')
        if not service_account_path:
            logger.error("GOOGLE_APPLICATION_CREDENTIALS environment variable not set")
            return
        
        cred = credentials.Certificate(service_account_path)
        app = firebase_admin.initialize_app(cred)
        db = firestore.client()
    
    logger.info("Firebase Admin SDK initialized successfully")
    
    # Get all active promises
    promises_query = db.collection('promises').where('status', '==', 'active').limit(50)
    promises = list(promises_query.stream())
    
    logger.info(f"Analyzing {len(promises)} active promises for evidence sync issues...")
    
    sync_issues = []
    
    for promise_doc in promises:
        promise_id = promise_doc.id
        promise_data = promise_doc.to_dict()
        
        # Get current linked_evidence_ids from promise
        frontend_evidence_ids = set(promise_data.get('linked_evidence_ids', []))
        
        # Query evidence_items to find what's actually linked via promise_ids
        evidence_query = db.collection('evidence_items').where('promise_ids', 'array_contains', promise_id)
        evidence_items = list(evidence_query.stream())
        backend_evidence_ids = set([doc.id for doc in evidence_items])
        
        # Check for discrepancy
        if frontend_evidence_ids != backend_evidence_ids:
            sync_issues.append({
                'promise_id': promise_id,
                'promise_title': promise_data.get('concise_title', 'Unknown'),
                'frontend_count': len(frontend_evidence_ids),
                'backend_count': len(backend_evidence_ids),
                'frontend_ids': list(frontend_evidence_ids),
                'backend_ids': list(backend_evidence_ids),
                'missing_from_frontend': list(backend_evidence_ids - frontend_evidence_ids),
                'extra_in_frontend': list(frontend_evidence_ids - backend_evidence_ids)
            })
    
    logger.info(f"Found {len(sync_issues)} promises with evidence synchronization issues")
    
    # Report detailed analysis
    for issue in sync_issues[:5]:  # Show first 5 issues
        logger.info(f"Promise: {issue['promise_id']} - {issue['promise_title']}")
        logger.info(f"  Frontend array: {issue['frontend_count']} items")
        logger.info(f"  Backend query:  {issue['backend_count']} items")
        logger.info(f"  Missing from frontend: {len(issue['missing_from_frontend'])} items")
        logger.info(f"  Extra in frontend: {len(issue['extra_in_frontend'])} items")
        
        if issue['missing_from_frontend']:
            logger.info(f"  Sample missing IDs: {issue['missing_from_frontend'][:3]}")
    
    # Save detailed analysis
    analysis_filename = f"evidence_sync_analysis_{len(sync_issues)}_issues.json"
    with open(analysis_filename, 'w') as f:
        json.dump(sync_issues, f, indent=2, default=str)
    logger.info(f"Detailed analysis saved to {analysis_filename}")
    
    # Ask user confirmation before fixing
    print(f"\nAnalysis complete:")
    print(f"- {len(promises)} promises analyzed")
    print(f"- {len(sync_issues)} promises have sync issues")
    print(f"- Detailed analysis saved to {analysis_filename}")
    
    if sync_issues:
        response = input(f"\nDo you want to fix these sync issues by updating linked_evidence_ids arrays? (y/N): ")
        
        if response.lower() == 'y':
            await fix_sync_issues(db, sync_issues)
        else:
            logger.info("Sync issues not fixed. Run script again with 'y' to fix.")
    else:
        logger.info("No sync issues found! All promises have synchronized evidence arrays.")

async def fix_sync_issues(db, sync_issues: List[Dict[str, Any]]):
    """Fix the synchronization issues by updating promises.linked_evidence_ids"""
    
    logger.info(f"Fixing {len(sync_issues)} promises with sync issues...")
    
    batch = db.batch()
    batch_count = 0
    
    for issue in sync_issues:
        promise_id = issue['promise_id']
        correct_evidence_ids = issue['backend_ids']
        
        # Update the promise document
        promise_ref = db.collection('promises').document(promise_id)
        batch.update(promise_ref, {
            'linked_evidence_ids': correct_evidence_ids,
            'evidence_sync_fixed_at': firestore.SERVER_TIMESTAMP,
            'evidence_count': len(correct_evidence_ids)
        })
        
        batch_count += 1
        
        # Commit in batches of 100 (Firestore limit is 500)
        if batch_count >= 100:
            await asyncio.to_thread(batch.commit)
            logger.info(f"Committed batch of {batch_count} promise updates")
            batch = db.batch()
            batch_count = 0
    
    # Commit final batch
    if batch_count > 0:
        await asyncio.to_thread(batch.commit)
        logger.info(f"Committed final batch of {batch_count} promise updates")
    
    logger.info(f"Successfully fixed sync issues for {len(sync_issues)} promises!")
    logger.info("All promises now have synchronized linked_evidence_ids arrays that match backend reality.")

if __name__ == "__main__":
    asyncio.run(analyze_and_fix_evidence_sync()) 