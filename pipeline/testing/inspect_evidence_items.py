#!/usr/bin/env python3
"""
Inspect Evidence Items

Check the evidence items that were recently created by the processing pipeline.
"""

import sys
from pathlib import Path
from datetime import datetime, timezone, timedelta

# Add pipeline directory to path
pipeline_dir = Path(__file__).parent.parent
sys.path.insert(0, str(pipeline_dir))

import firebase_admin
from firebase_admin import firestore


def inspect_evidence_items():
    """Inspect recently created evidence items"""
    
    # Initialize Firebase
    if not firebase_admin._apps:
        firebase_admin.initialize_app()
    db = firestore.client()
    
    print("🔍 INSPECTING RECENTLY CREATED EVIDENCE ITEMS")
    print("=" * 60)
    
    # Look for items created in the last hour
    cutoff_time = datetime.now(timezone.utc) - timedelta(hours=1)
    print(f"Looking for evidence items created after: {cutoff_time}")
    print()
    
    try:
        # Check total evidence items count
        all_items = list(db.collection('evidence_items').limit(10).stream())
        print(f"📊 Total evidence items (sample): {len(all_items)}")
        
        # Check for Canada news items specifically
        canada_items = list(db.collection('evidence_items')
                          .where(filter=firestore.FieldFilter('evidence_source_type', '==', 'news_release_canada'))
                          .limit(10).stream())
        print(f"📰 Canada news evidence items: {len(canada_items)}")
        
        # Check recent job executions
        print("\n📋 RECENT JOB EXECUTIONS:")
        print("-" * 40)
        recent_jobs = list(db.collection('job_executions')
                         .order_by('start_time', direction=firestore.Query.DESCENDING)
                         .limit(5).stream())
        
        for job in recent_jobs:
            job_data = job.to_dict()
            job_name = job_data.get('job_name', 'Unknown')
            status = job_data.get('status', 'Unknown')
            created = job_data.get('items_created', 0)
            start_time = job_data.get('start_time')
            
            if start_time:
                time_str = start_time.strftime('%H:%M:%S') if hasattr(start_time, 'strftime') else str(start_time)
            else:
                time_str = 'Unknown'
                
            print(f"  {time_str} | {job_name:<30} | {status:<8} | Created: {created}")
        
        # Display sample evidence items if any exist
        if canada_items:
            print(f"\n📄 SAMPLE CANADA NEWS EVIDENCE ITEMS:")
            print("-" * 60)
            
            for i, item in enumerate(canada_items[:3]):  # Show first 3
                item_data = item.to_dict()
                print(f"\n🔸 Evidence Item #{i+1} (ID: {item.id})")
                print(f"   Title: {item_data.get('title_or_summary', 'No title')[:80]}...")
                print(f"   Source Type: {item_data.get('evidence_source_type', 'Unknown')}")
                print(f"   Created: {item_data.get('created_at', 'Unknown')}")
                print(f"   Parliament Session: {item_data.get('parliament_session_id', 'Unknown')}")
                print(f"   Processing Status: {item_data.get('promise_linking_status', 'Unknown')}")
                
                # Show LLM analysis if present
                llm_analysis = item_data.get('llm_analysis')
                if llm_analysis:
                    summary = llm_analysis.get('summary', 'No summary')
                    topics = llm_analysis.get('key_topics', [])
                    print(f"   LLM Summary: {summary[:100]}...")
                    print(f"   Topics: {topics}")
                else:
                    print(f"   LLM Analysis: Not present")
            
            # Show detailed structure of first item
            if canada_items:
                print(f"\n🔬 DETAILED STRUCTURE OF FIRST EVIDENCE ITEM:")
                print("-" * 60)
                first_item = canada_items[0].to_dict()
                
                # Show all top-level fields
                for key, value in sorted(first_item.items()):
                    if key == 'llm_analysis' and isinstance(value, dict):
                        print(f"   {key}:")
                        for subkey, subval in value.items():
                            val_preview = str(subval)[:100] + "..." if len(str(subval)) > 100 else str(subval)
                            print(f"     {subkey}: {val_preview}")
                    else:
                        val_preview = str(value)[:100] + "..." if len(str(value)) > 100 else str(value)
                        print(f"   {key}: {val_preview}")
        
        elif all_items:
            print(f"\n📄 SAMPLE EVIDENCE ITEMS (ANY TYPE):")
            print("-" * 60)
            
            for i, item in enumerate(all_items[:2]):
                item_data = item.to_dict()
                print(f"\n🔸 Evidence Item #{i+1} (ID: {item.id})")
                print(f"   Title: {item_data.get('title_or_summary', 'No title')[:80]}...")
                print(f"   Source Type: {item_data.get('evidence_source_type', 'Unknown')}")
                print(f"   Created: {item_data.get('created_at', 'Unknown')}")
        
        else:
            print("\n⚠️  No evidence items found in the database")
            
    except Exception as e:
        print(f"❌ Error inspecting evidence items: {e}")
        return False
    
    return True


if __name__ == "__main__":
    inspect_evidence_items() 