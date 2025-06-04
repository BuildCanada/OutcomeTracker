#!/usr/bin/env python3
"""
Analyze title field usage in evidence_items

Check how many evidence_items have 'title' vs 'title_or_summary' and 
'description' vs 'description_or_details' fields.
"""

import firebase_admin
from firebase_admin import firestore, credentials
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Firebase Configuration
if not firebase_admin._apps:
    try:
        firebase_admin.initialize_app()
        print("Connected to Cloud Firestore using default credentials.")
        db = firestore.client()
    except Exception as e:
        print(f"Error connecting to Firestore: {e}")
        exit(1)

def analyze_field_usage():
    """Analyze field usage in evidence_items collections."""
    
    collections_to_check = ['evidence_items_test', 'evidence_items']
    
    for collection_name in collections_to_check:
        print(f"\n=== Analyzing {collection_name} ===")
        
        try:
            # Get all documents in collection (limit to avoid overwhelming)
            docs = db.collection(collection_name).limit(1000).stream()
            
            title_count = 0
            title_or_summary_count = 0
            description_count = 0 
            description_or_details_count = 0
            total_count = 0
            
            for doc in docs:
                data = doc.to_dict()
                total_count += 1
                
                # Check title fields
                if data.get('title') and isinstance(data.get('title'), str) and data.get('title').strip():
                    title_count += 1
                    
                if data.get('title_or_summary') and isinstance(data.get('title_or_summary'), str) and data.get('title_or_summary').strip():
                    title_or_summary_count += 1
                
                # Check description fields
                if data.get('description') and isinstance(data.get('description'), str) and data.get('description').strip():
                    description_count += 1
                    
                if data.get('description_or_details') and isinstance(data.get('description_or_details'), str) and data.get('description_or_details').strip():
                    description_or_details_count += 1
            
            print(f"Total documents analyzed: {total_count}")
            print(f"'title' field populated: {title_count} ({title_count/max(total_count,1)*100:.1f}%)")
            print(f"'title_or_summary' field populated: {title_or_summary_count} ({title_or_summary_count/max(total_count,1)*100:.1f}%)")
            print(f"'description' field populated: {description_count} ({description_count/max(total_count,1)*100:.1f}%)")
            print(f"'description_or_details' field populated: {description_or_details_count} ({description_or_details_count/max(total_count,1)*100:.1f}%)")
            
        except Exception as e:
            print(f"Error analyzing {collection_name}: {e}")

if __name__ == "__main__":
    analyze_field_usage() 