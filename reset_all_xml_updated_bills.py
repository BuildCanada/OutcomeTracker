#!/usr/bin/env python3
"""
Reset all Parliament 45 bills that have XML content to pending processing status
"""

import firebase_admin
from firebase_admin import firestore
from datetime import datetime, timezone

# Initialize Firebase
if not firebase_admin._apps:
    firebase_admin.initialize_app()

db = firestore.client()

def reset_xml_bills():
    """Reset all bills with XML content to pending processing"""
    
    # Get all Parliament 45-1 bills
    query = db.collection('raw_legisinfo_bill_details').where(
        filter=firestore.FieldFilter('parliament_session_id', '==', '45-1')
    )
    
    reset_count = 0
    
    print("🔄 Resetting Parliament 45 bills with XML content to pending processing...")
    
    for doc in query.stream():
        bill_data = doc.to_dict()
        bill_code = bill_data.get('bill_number_code_feed', 'Unknown')
        xml_content = bill_data.get('raw_xml_content')
        
        # Only reset bills that have substantial XML content
        if xml_content and len(xml_content) > 1000:
            db.collection('raw_legisinfo_bill_details').document(doc.id).update({
                'processing_status': 'pending_processing',
                'last_attempted_processing_at': datetime.now(timezone.utc)
            })
            print(f"✅ Reset {bill_code} to pending_processing ({len(xml_content)} chars XML)")
            reset_count += 1
        else:
            print(f"⏭️  Skipped {bill_code} (no XML content)")
    
    print(f"\n🎯 Reset complete! Updated {reset_count} bills to pending_processing")
    print("🔄 Now run the processor to create evidence items with LLM-enhanced descriptions!")

if __name__ == "__main__":
    reset_xml_bills() 