#!/usr/bin/env python3
"""
Check if the 14 recently introduced bills from the image are in our database
"""

import firebase_admin
from firebase_admin import firestore

# Initialize Firebase
if not firebase_admin._apps:
    firebase_admin.initialize_app()

db = firestore.client()

# Bills from the image (14 recently introduced bills)
expected_bills = [
    # Senate bills
    'S-226', 'S-227', 'S-228',  # June 5, 2025
    'S-223', 'S-224', 'S-225', 'S-1001',  # June 3, 2025
    'S-2', 'S-222',  # May 29, 2025
    
    # House bills  
    'C-5',  # June 6, 2025
    'C-3', 'C-4',  # June 5, 2025
    'C-203', 'C-204'  # June 4, 2025
]

print("✅ Checking 14 recently introduced bills from image:")
print("=" * 60)

found_bills = []
missing_bills = []

for bill in expected_bills:
    query = db.collection('raw_legisinfo_bill_details').where(
        'bill_number_code_feed', '==', bill
    ).where('parliament_session_id', '==', '45-1').limit(1)
    
    docs = list(query.stream())
    if docs:
        found_bills.append(bill)
        print(f"   ✅ {bill}: Found")
    else:
        missing_bills.append(bill)
        print(f"   ❌ {bill}: Missing")

print(f"\n📊 Summary: {len(found_bills)}/14 bills found, {len(missing_bills)} missing")

if missing_bills:
    print("\n❌ Missing bills:")
    for bill in missing_bills:
        print(f"  - {bill}")
else:
    print("  🎉 All 14 recent bills are in the database!")

# Also show total count
query = db.collection('raw_legisinfo_bill_details').where('parliament_session_id', '==', '45-1')
total_docs = len(list(query.stream()))
print(f"\n📈 Total Parliament 45-1 bills in database: {total_docs}") 