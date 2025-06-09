#!/usr/bin/env python3
"""
Test script to validate the fixed XML URL construction
"""

import requests
import json
import firebase_admin
from firebase_admin import firestore

# Initialize Firebase
if not firebase_admin._apps:
    firebase_admin.initialize_app()

db = firestore.client()

def test_fixed_url_construction():
    """Test XML URL construction with the fixed logic"""
    
    print("🔍 Testing XML URL construction with FIXED logic:")
    print("=" * 60)
    
    # Test with Parliament 45 bills
    test_bills = ['C-1', 'C-2', 'C-3', 'S-2', 'C-201', 'C-204', 'S-227']
    
    for bill_code in test_bills:
        print(f"\n📄 Testing {bill_code}:")
        
        # Get bill data from database
        query = db.collection('raw_legisinfo_bill_details').where(
            'bill_number_code_feed', '==', bill_code
        ).where('parliament_session_id', '==', '45-1').limit(1)
        
        docs = list(query.stream())
        if not docs:
            print(f"   ❌ Bill not found in Parliament 45-1")
            continue
            
        bill_data = docs[0].to_dict()
        raw_json_content = bill_data.get('raw_json_content', '[]')
        
        try:
            bill_details = json.loads(raw_json_content)[0] if json.loads(raw_json_content) else {}
        except:
            print(f"   ❌ Could not parse raw_json_content")
            continue
            
        # Use the FIXED field extraction logic
        parl = bill_details.get('ParliamentNumber')
        session = bill_details.get('SessionNumber') 
        bill_code_from_data = bill_details.get('NumberCode')
        is_government_bill = bill_details.get('IsGovernmentBill', True)
        
        print(f"   ParliamentNumber: {parl}")
        print(f"   SessionNumber: {session}")
        print(f"   NumberCode: {bill_code_from_data}")
        print(f"   IsGovernmentBill: {is_government_bill}")
        
        if parl and session and bill_code_from_data:
            # Use the same logic as the fixed _construct_xml_url
            bill_type_url_part = 'Government' if is_government_bill else 'Private'
            url = f"https://www.parl.ca/Content/Bills/{parl}{session}/{bill_type_url_part}/{bill_code_from_data}/{bill_code_from_data}_1/{bill_code_from_data}_E.xml"
            print(f"   Constructed URL: {url}")
            
            # Test the URL
            try:
                response = requests.get(url, timeout=10)
                if response.status_code == 200:
                    print(f"   ✅ SUCCESS: {len(response.text):,} characters")
                    print(f"   First 100 chars: {repr(response.text[:100])}")
                else:
                    print(f"   ❌ HTTP {response.status_code}")
            except Exception as e:
                print(f"   ❌ Exception: {e}")
        else:
            print(f"   ❌ Missing required fields for URL construction")

if __name__ == "__main__":
    test_fixed_url_construction() 