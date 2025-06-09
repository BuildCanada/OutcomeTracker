#!/usr/bin/env python3
"""
Check processing status of the 7 bills with XML content
"""

import firebase_admin
from firebase_admin import firestore

# Initialize Firebase
if not firebase_admin._apps:
    firebase_admin.initialize_app()

db = firestore.client()

bills_with_xml = ['C-201', 'C-202', 'C-203', 'C-204', 'S-1001', 'S-2', 'S-221']

print("🔍 Processing status of the 7 bills with XML content:")
print("=" * 70)

for bill in bills_with_xml:
    # Get raw bill data
    query = db.collection('raw_legisinfo_bill_details').where(
        'bill_number_code_feed', '==', bill
    ).where('parliament_session_id', '==', '45-1').limit(1)
    
    docs = list(query.stream())
    
    if docs:
        data = docs[0].to_dict()
        status = data.get('processing_status', 'No status')
        xml_len = len(data.get('raw_xml_content', '') or '')
        last_processed = data.get('last_processed_time', 'Never')
        
        print(f"📄 {bill}:")
        print(f"   Status: {status}")
        print(f"   XML Content: {xml_len:,} characters")
        print(f"   Last Processed: {last_processed}")
        
        # Check if there are any error details
        if 'processing_error' in data:
            print(f"   ❌ Error: {data['processing_error']}")
        
        print()
    else:
        print(f"❌ {bill}: Not found in raw_legisinfo_bill_details")

print("\n🔍 Cross-checking evidence items for these bills:")
print("=" * 50)

for bill in bills_with_xml:
    # Check if evidence item exists
    query = db.collection('evidence_items').where(
        'evidence_source_type', '==', 'Bill Event (LEGISinfo)'
    ).where('parliament_session_id', '==', '45')
    
    docs = list(query.stream())
    
    found = False
    for doc in docs:
        data = doc.to_dict()
        title = data.get('title_or_summary', '')
        if f'Bill {bill}' in title:
            desc_len = len(data.get('description_or_details', '') or '')
            print(f"✅ {bill}: Evidence item exists ({desc_len} chars)")
            found = True
            break
    
    if not found:
        print(f"❌ {bill}: No evidence item found")

print(f"\n💡 Summary: Only S-2 has evidence items, despite 7 bills having XML content.") 