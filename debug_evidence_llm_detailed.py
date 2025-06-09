#!/usr/bin/env python3
"""
Detailed debug script to show which Parliament 45 bills got LLM synthesis
"""

import firebase_admin
from firebase_admin import firestore

# Initialize Firebase
if not firebase_admin._apps:
    firebase_admin.initialize_app()

db = firestore.client()

print("🔍 DETAILED analysis of Parliament 45 LEGISinfo evidence items:")
print("=" * 80)

# Get all LEGISinfo evidence items for Parliament 45
query = db.collection('evidence_items').where(
    'evidence_source_type', '==', 'Bill Event (LEGISinfo)'
).where('parliament_session_id', '==', '45')

docs = list(query.stream())
print(f"Found {len(docs)} LEGISinfo evidence items for Parliament 45")

bills_with_llm = []
bills_without_llm = []

print(f"\n📋 ALL Parliament 45 bills:")
print("-" * 80)

for i, doc in enumerate(docs, 1):
    data = doc.to_dict()
    title = data.get('title_or_summary', 'No title')
    desc = data.get('description_or_details', '')
    desc_length = len(desc) if desc else 0
    
    # Extract bill number from title
    bill_number = "Unknown"
    if 'Bill ' in title:
        # Extract bill number like "C-204", "S-2", etc.
        parts = title.split('Bill ')
        if len(parts) > 1:
            bill_part = parts[1].split(':')[0].strip()
            bill_number = bill_part
    
    # Check if has LLM synthesis (>500 chars indicates rich LLM content)
    has_llm = desc_length > 500
    status = "✅ LLM Enhanced" if has_llm else "❌ No LLM"
    
    print(f"{i:2d}. {bill_number:8s} | {status:15s} | {desc_length:4d} chars | {title[:50]}...")
    
    if has_llm:
        bills_with_llm.append((bill_number, desc_length, title))
    else:
        bills_without_llm.append((bill_number, desc_length, title))

print(f"\n📊 SUMMARY:")
print(f"   ✅ Bills WITH LLM synthesis: {len(bills_with_llm)}")
print(f"   ❌ Bills WITHOUT LLM synthesis: {len(bills_without_llm)}")

if bills_with_llm:
    print(f"\n✅ BILLS WITH LLM SYNTHESIS:")
    for bill_number, length, title in bills_with_llm:
        print(f"   • {bill_number}: {length:,} chars")
        print(f"     {title}")

# Check the specific 7 bills that should have XML content
xml_bills = ['C-201', 'C-202', 'C-203', 'C-204', 'S-1001', 'S-2', 'S-221']
print(f"\n🎯 Status of the 7 bills with XML content:")
for expected_bill in xml_bills:
    found = False
    for bill_number, length, title in bills_with_llm + bills_without_llm:
        if expected_bill in bill_number:
            status = "✅ LLM Enhanced" if length > 500 else "❌ Missing LLM"
            print(f"   {expected_bill}: {status} ({length} chars)")
            found = True
            break
    if not found:
        print(f"   {expected_bill}: ❌ No evidence item found")

# Show sample descriptions
print(f"\n📝 SAMPLE DESCRIPTIONS:")
print("=" * 50)
if bills_with_llm:
    bill_number, length, title = bills_with_llm[0]
    print(f"✅ ENHANCED ({bill_number}):")
    # Get the actual description
    for doc in docs:
        data = doc.to_dict()
        if bill_number in data.get('title_or_summary', ''):
            sample_desc = data.get('description_or_details', '')[:300]
            print(f"   {sample_desc}...")
            break

if bills_without_llm:
    bill_number, length, title = bills_without_llm[0]
    print(f"\n❌ NOT ENHANCED ({bill_number}):")
    # Get the actual description
    for doc in docs:
        data = doc.to_dict()
        if bill_number in data.get('title_or_summary', ''):
            sample_desc = data.get('description_or_details', '')
            print(f"   {sample_desc}")
            break 