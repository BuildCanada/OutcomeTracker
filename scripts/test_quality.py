#!/usr/bin/env python3
"""
Test Quality Script - Check and Reset Promises for Testing

This script will:
1. Find promises that are already enriched from any year
2. Reset enrichment fields for selected promises
3. Run enrichment and linking to test quality
"""

import sys
import os
sys.path.append('..')

import firebase_admin
from firebase_admin import credentials, firestore
import logging
from datetime import datetime
from collections import defaultdict

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def initialize_firebase():
    """Initialize Firebase if not already initialized."""
    try:
        app = firebase_admin.get_app()
        logger.info("Firebase already initialized")
    except ValueError:
        cred = credentials.ApplicationDefault()
        app = firebase_admin.initialize_app(cred)
        logger.info("Firebase initialized")
    
    return firestore.client()

def analyze_promise_database(db):
    """Analyze the promises database to understand what data we have."""
    logger.info("Analyzing promise database...")
    
    promises_ref = db.collection('promises')
    promises = promises_ref.limit(100).stream()  # Get a sample
    
    year_counts = defaultdict(int)
    party_counts = defaultdict(int)
    status_counts = defaultdict(int)
    enriched_count = 0
    total_count = 0
    
    sample_promises = []
    
    for promise in promises:
        data = promise.to_dict()
        total_count += 1
        
        # Count by year
        year = data.get('source_year', 'Unknown')
        year_counts[year] += 1
        
        # Count by party
        party = data.get('party', 'Unknown')
        party_counts[party] += 1
        
        # Count by status
        status = data.get('status', 'Unknown')
        status_counts[status] += 1
        
        # Check enrichment
        if data.get('explanation_enriched_at'):
            enriched_count += 1
        
        # Save sample for detailed view
        if len(sample_promises) < 10:
            promise_info = {
                'id': promise.id,
                'title': data.get('title', 'No title'),
                'party': data.get('party', 'Unknown'),
                'department': data.get('department', 'Unknown'),
                'status': data.get('status', 'Unknown'),
                'source_year': data.get('source_year', 'Unknown'),
                'enriched': bool(data.get('explanation_enriched_at')),
                'keywords_enriched': bool(data.get('keywords_enriched_at')),
                'action_type_enriched': bool(data.get('action_type_enriched_at')),
                'evidence_count': len(data.get('evidence_items', []))
            }
            sample_promises.append(promise_info)
    
    return {
        'total_count': total_count,
        'enriched_count': enriched_count,
        'year_counts': dict(year_counts),
        'party_counts': dict(party_counts),
        'status_counts': dict(status_counts),
        'sample_promises': sample_promises
    }

def find_2021_mandate_promises(db, limit=10):
    """Find 2021 LPC Mandate Letter promises."""
    logger.info("Finding 2021 LPC Mandate Letter promises...")
    
    promises_ref = db.collection('promises')
    promises = promises_ref.where('source_type', '==', '2021 LPC Mandate Letters').limit(limit).stream()
    
    promise_list = []
    for promise in promises:
        data = promise.to_dict()
        promise_info = {
            'id': promise.id,
            'title': data.get('title', 'No title'),
            'party': data.get('party', 'Unknown'),
            'department': data.get('department', 'Unknown'),
            'status': data.get('status', 'Unknown'),
            'source_type': data.get('source_type', 'Unknown'),
            'enriched': bool(data.get('explanation_enriched_at')),
            'keywords_enriched': bool(data.get('keywords_enriched_at')),
            'action_type_enriched': bool(data.get('action_type_enriched_at')),
            'evidence_count': len(data.get('evidence_items', []))
        }
        promise_list.append(promise_info)
    
    logger.info(f"Found {len(promise_list)} 2021 LPC Mandate Letter promises")
    return promise_list

def find_enriched_promises(db, limit=10):
    """Find promises that are already enriched."""
    logger.info("Finding enriched promises...")
    
    promises_ref = db.collection('promises')
    promises = promises_ref.where('explanation_enriched_at', '>', '').limit(limit).stream()
    
    promise_list = []
    for promise in promises:
        data = promise.to_dict()
        promise_info = {
            'id': promise.id,
            'title': data.get('title', 'No title'),
            'party': data.get('party', 'Unknown'),
            'department': data.get('department', 'Unknown'),
            'status': data.get('status', 'Unknown'),
            'source_year': data.get('source_year', 'Unknown'),
            'enriched': bool(data.get('explanation_enriched_at')),
            'keywords_enriched': bool(data.get('keywords_enriched_at')),
            'action_type_enriched': bool(data.get('action_type_enriched_at')),
            'evidence_count': len(data.get('evidence_items', []))
        }
        promise_list.append(promise_info)
    
    logger.info(f"Found {len(promise_list)} enriched promises")
    return promise_list

def display_database_summary(analysis):
    """Display database analysis summary."""
    print("\n=== Promise Database Analysis ===")
    print(f"Total promises sampled: {analysis['total_count']}")
    print(f"Enriched promises: {analysis['enriched_count']}")
    
    print(f"\nBy Year:")
    for year, count in sorted(analysis['year_counts'].items()):
        print(f"  {year}: {count}")
    
    print(f"\nBy Party:")
    for party, count in analysis['party_counts'].items():
        print(f"  {party}: {count}")
    
    print(f"\nBy Status:")
    for status, count in analysis['status_counts'].items():
        print(f"  {status}: {count}")

def display_promises(promises):
    """Display promise information."""
    print("\n=== Sample Promises ===")
    for i, p in enumerate(promises):
        print(f"\n{i+1}. ID: {p['id']}")
        print(f"   Title: {p['title'][:80]}...")
        print(f"   Party: {p['party']}")
        print(f"   Department: {p['department']}")
        print(f"   Source: {p.get('source_type', p.get('source_year', 'Unknown'))}")
        print(f"   Status: {p['status']}")
        print(f"   Enriched: {p['enriched']}")
        print(f"   Keywords: {p['keywords_enriched']}")
        print(f"   Action Type: {p['action_type_enriched']}")
        print(f"   Evidence Items: {p['evidence_count']}")

def reset_promise_enrichment(db, promise_id, fields_to_reset=None):
    """Reset enrichment fields for a promise."""
    if fields_to_reset is None:
        fields_to_reset = [
            'explanation_enriched_at',
            'explanation_enrichment_model',
            'explanation_enrichment_status',
            'explanation',
            'background_and_context',
            'keywords_enriched_at',
            'keywords_enrichment_model', 
            'keywords_enrichment_status',
            'keywords',
            'action_type_enriched_at',
            'action_type_enrichment_model',
            'action_type_enrichment_status',
            'action_type'
        ]
    
    logger.info(f"Resetting enrichment fields for promise {promise_id}")
    
    promise_ref = db.collection('promises').document(promise_id)
    
    # Create update dict to remove fields
    update_data = {}
    for field in fields_to_reset:
        update_data[field] = firestore.DELETE_FIELD
    
    promise_ref.update(update_data)
    logger.info(f"Reset {len(fields_to_reset)} fields for promise {promise_id}")

def main():
    """Main function."""
    db = initialize_firebase()
    
    # Analyze database
    analysis = analyze_promise_database(db)
    display_database_summary(analysis)
    
    # Show sample promises
    if analysis['sample_promises']:
        display_promises(analysis['sample_promises'])
    
    # Focus on 2021 LPC Mandate Letter promises
    mandate_promises = find_2021_mandate_promises(db, limit=15)
    
    if mandate_promises:
        print(f"\n=== Found {len(mandate_promises)} 2021 LPC Mandate Letter Promises ===")
        display_promises(mandate_promises[:10])  # Show first 10
        
        # Find enriched ones to reset
        enriched_mandate_promises = [p for p in mandate_promises if p['enriched']]
        
        if enriched_mandate_promises:
            print(f"\n=== Found {len(enriched_mandate_promises)} Enriched 2021 Mandate Promises ===")
            
            # Reset first 3 enriched promises for testing
            test_promises = enriched_mandate_promises[:3]
            
            print(f"\nResetting enrichment for {len(test_promises)} promises:")
            for p in test_promises:
                print(f"- {p['id']}: {p['title'][:60]}...")
                reset_promise_enrichment(db, p['id'])
            
            print(f"\n✅ Reset complete! You can now test enrichment quality on these {len(test_promises)} promises:")
            for p in test_promises:
                print(f"- {p['id']}")
                
            print(f"\nTo test enrichment, run:")
            print(f"python consolidated_promise_enrichment.py --promise-ids {','.join([p['id'] for p in test_promises])}")
        else:
            # No enriched promises, so let's test enrichment on raw ones
            unenriched_promises = [p for p in mandate_promises if not p['enriched']][:3]
            
            if unenriched_promises:
                print(f"\n=== Found {len(unenriched_promises)} Unenriched 2021 Mandate Promises ===")
                print(f"These can be used to test enrichment quality:")
                for p in unenriched_promises:
                    print(f"- {p['id']}")
                    
                print(f"\nTo test enrichment, run:")
                print(f"python consolidated_promise_enrichment.py --promise-ids {','.join([p['id'] for p in unenriched_promises])}")
            else:
                print("\nNo 2021 mandate promises available for testing.")
    else:
        print("\nNo 2021 LPC Mandate Letter promises found!")
        
        # Fallback to general enriched promises
        enriched_promises = find_enriched_promises(db, limit=10)
        
        if enriched_promises:
            print(f"\n=== Fallback: Found {len(enriched_promises)} General Enriched Promises ===")
            display_promises(enriched_promises)
            
            # Reset first 3 enriched promises for testing
            test_promises = enriched_promises[:3]
            
            print(f"\nResetting enrichment for {len(test_promises)} promises:")
            for p in test_promises:
                print(f"- {p['id']}: {p['title'][:60]}...")
                reset_promise_enrichment(db, p['id'])
            
            print(f"\n✅ Reset complete! You can now test enrichment quality on these {len(test_promises)} promises:")
            for p in test_promises:
                print(f"- {p['id']}")
                
            print(f"\nTo test enrichment, run:")
            print(f"python consolidated_promise_enrichment.py --promise-ids {','.join([p['id'] for p in test_promises])}")
            
        else:
            print("\nNo enriched promises found to reset. All promises are already in their base state.")

if __name__ == "__main__":
    main() 