#!/usr/bin/env python3
"""
Debug script to check raw_xml_content field for bills
"""

import firebase_admin
from firebase_admin import firestore

# Initialize Firebase
if not firebase_admin._apps:
    firebase_admin.initialize_app()

db = firestore.client()

# Bills to check
bills_to_check = ['C-204', 'S-227', 'S-2', 'C-2', 'C-3', 'C-4', 'C-5']

print("🔍 Checking raw_xml_content for bills:")
print("=" * 50)

for bill_code in bills_to_check:
    query = db.collection('raw_legisinfo_bill_details').where(
        'bill_number_code_feed', '==', bill_code
    ).limit(1)
    
    docs = list(query.stream())
    if docs:
        bill_data = docs[0].to_dict()
        xml_content = bill_data.get('raw_xml_content')
        
        if xml_content is None:
            print(f"❌ {bill_code}: raw_xml_content = None")
        elif xml_content == "":
            print(f"⚠️  {bill_code}: raw_xml_content = empty string")
        else:
            xml_len = len(xml_content)
            print(f"✅ {bill_code}: raw_xml_content = {xml_len:,} characters")
            print(f"   First 100 chars: {repr(xml_content[:100])}")
    else:
        print(f"❓ {bill_code}: Not found in database")

print("\n🔍 Summary of all Parliament 45-1 bills with XML content:")
query = db.collection('raw_legisinfo_bill_details').where(
    'parliament_session_id', '==', '45-1'
)
docs = list(query.stream())

bills_with_xml = 0
bills_with_empty_xml = 0
bills_with_null_xml = 0

for doc in docs:
    bill_data = doc.to_dict()
    xml_content = bill_data.get('raw_xml_content')
    
    if xml_content is None:
        bills_with_null_xml += 1
    elif xml_content == "":
        bills_with_empty_xml += 1
    else:
        bills_with_xml += 1

print(f"📊 Out of {len(docs)} Parliament 45-1 bills:")
print(f"   ✅ Bills with XML content: {bills_with_xml}")
print(f"   ⚠️  Bills with empty XML: {bills_with_empty_xml}")
print(f"   ❌ Bills with null XML: {bills_with_null_xml}") 