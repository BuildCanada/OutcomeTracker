#!/usr/bin/env python3
"""
Debug script to check which evidence items got LLM-enhanced descriptions
"""

import firebase_admin
from firebase_admin import firestore

# Initialize Firebase
if not firebase_admin._apps:
    firebase_admin.initialize_app()

db = firestore.client()

print("🔍 Checking LEGISinfo evidence items for Parliament 45-1:")
print("=" * 70)

# Get all LEGISinfo evidence items for Parliament 45 (short form)
query = db.collection('evidence_items').where(
    'evidence_source_type', '==', 'Bill Event (LEGISinfo)'
).where('parliament_session_id', '==', '45')

docs = list(query.stream())
print(f"Found {len(docs)} LEGISinfo evidence items for Parliament 45")

bills_with_llm = []
bills_without_llm = []

for doc in docs:
    data = doc.to_dict()
    title = data.get('title', 'Unknown')
    desc = data.get('description_or_details', '')
    desc_length = len(desc) if desc else 0
    
    # Consider it LLM-enhanced if it's longer than 500 characters
    # (our LLM synthesis should produce ~200 word summaries)
    if desc and desc_length > 500:
        bills_with_llm.append((title, desc_length))
    else:
        bills_without_llm.append((title, desc_length))

print(f"\n✅ Bills WITH LLM synthesis (>500 chars): {len(bills_with_llm)}")
for title, length in bills_with_llm:
    print(f"   {title}: {length:,} characters")

print(f"\n❌ Bills WITHOUT LLM synthesis (<500 chars): {len(bills_without_llm)}")
for title, length in bills_without_llm[:10]:  # Show first 10
    print(f"   {title}: {length} characters")

if len(bills_without_llm) > 10:
    print(f"   ... and {len(bills_without_llm) - 10} more")

# Also check the 7 bills we know have XML content
xml_bills = ['C-201', 'C-202', 'C-203', 'C-204', 'S-1001', 'S-2', 'S-221']
print(f"\n🎯 Checking the 7 bills that should have LLM synthesis:")
for bill_code in xml_bills:
    # Find evidence item for this bill
    bill_query = db.collection('evidence_items').where(
        'evidence_source_type', '==', 'Bill Event (LEGISinfo)'
    ).where('parliament_session_id', '==', '45')
    
    bill_docs = [doc for doc in query.stream() if bill_code in doc.to_dict().get('title', '')]
    if bill_docs:
        data = bill_docs[0].to_dict()
        desc_length = len(data.get('description_or_details', ''))
        status = "✅ LLM Enhanced" if desc_length > 500 else "❌ Missing LLM"
        print(f"   {bill_code}: {status} ({desc_length} chars)")
    else:
        print(f"   {bill_code}: ❌ No evidence item found") 