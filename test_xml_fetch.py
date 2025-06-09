#!/usr/bin/env python3
"""
Test script to debug XML fetching for C-4 and C-5
"""

import requests
import json
import firebase_admin
from firebase_admin import firestore

# Initialize Firebase
if not firebase_admin._apps:
    firebase_admin.initialize_app()

db = firestore.client()

def test_xml_fetch():
    """Test XML fetching for C-4 and C-5"""
    
    bills = ['C-4', 'C-5']
    
    for bill_code in bills:
        print(f"\n🔍 Testing XML fetch for {bill_code}:")
        print("=" * 50)
        
        # Get the bill data from Firestore
        query = db.collection('raw_legisinfo_bill_details').where(
            'bill_number_code_feed', '==', bill_code
        ).where('parliament_session_id', '==', '45-1').limit(1)
        
        docs = list(query.stream())
        if not docs:
            print(f"❌ No bill found for {bill_code}")
            continue
            
        bill_doc = docs[0].to_dict()
        
        # Parse the raw JSON content to get bill details
        raw_json = bill_doc.get('raw_json_content', '[]')
        bill_details_list = json.loads(raw_json)
        
        if not bill_details_list:
            print(f"❌ No bill details found for {bill_code}")
            continue
            
        bill_details = bill_details_list[0]
        
        # Extract data for URL construction
        parl = bill_details.get('ParliamentNumber')
        session = bill_details.get('SessionNumber')
        number_code = bill_details.get('NumberCode')
        is_govt_bill = bill_details.get('IsGovernmentBill', True)
        
        print(f"📊 Bill Data:")
        print(f"   Parliament: {parl}")
        print(f"   Session: {session}")
        print(f"   Number Code: {number_code}")
        print(f"   Is Government Bill: {is_govt_bill}")
        
        # Construct XML URL
        bill_type = 'Government' if is_govt_bill else 'Private'
        xml_url = f"https://www.parl.ca/Content/Bills/{parl}{session}/{bill_type}/{number_code}/{number_code}_1/{number_code}_E.xml"
        
        print(f"🔗 Constructed URL: {xml_url}")
        
        # Test fetching XML
        try:
            headers = {'User-Agent': 'Promise Tracker Pipeline/2.0 (Government Data Ingestion)'}
            response = requests.get(xml_url, headers=headers, timeout=60)
            response.raise_for_status()
            
            xml_content = response.text
            print(f"✅ XML fetch successful!")
            print(f"   XML length: {len(xml_content)} characters")
            print(f"   Content preview: {xml_content[:200]}...")
            
            # Check if this bill already has XML content in Firestore
            existing_xml = bill_doc.get('raw_xml_content')
            if existing_xml:
                print(f"   📄 Bill already has XML content: {len(existing_xml)} characters")
            else:
                print(f"   ❌ Bill missing XML content in Firestore!")
                
                # Update the bill with XML content
                doc_id = docs[0].id
                db.collection('raw_legisinfo_bill_details').document(doc_id).update({
                    'raw_xml_content': xml_content
                })
                print(f"   ✅ Updated bill {bill_code} with XML content")
            
        except Exception as e:
            print(f"❌ XML fetch failed: {e}")

if __name__ == "__main__":
    test_xml_fetch() 