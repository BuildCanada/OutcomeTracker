#!/usr/bin/env python3
"""
Show diff between expected 14 recent bills vs all 40 bills in database
"""

import firebase_admin
from firebase_admin import firestore

# Initialize Firebase
if not firebase_admin._apps:
    firebase_admin.initialize_app()

db = firestore.client()

# Expected 14 recent bills from the Parliamentary image
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

# Get all bills currently in database
query = db.collection('raw_legisinfo_bill_details').where('parliament_session_id', '==', '45-1')
docs = list(query.stream())
all_bills_in_db = sorted([doc.to_dict().get('bill_number_code_feed', 'Unknown') for doc in docs])

# Find bills that are in database but NOT in expected list
unexpected_bills = [bill for bill in all_bills_in_db if bill not in expected_bills]

print("📊 BILL DIFF ANALYSIS - Parliament Session 45-1")
print("=" * 70)

print(f"\n✅ Expected bills (from Parliamentary image): {len(expected_bills)}")
for i, bill in enumerate(sorted(expected_bills), 1):
    print(f"   {i:2d}. {bill}")

print(f"\n📦 All bills currently in database: {len(all_bills_in_db)}")
for i, bill in enumerate(all_bills_in_db, 1):
    marker = "✅" if bill in expected_bills else "❌"
    print(f"   {i:2d}. {bill} {marker}")

print(f"\n❌ UNEXPECTED bills in database (should be removed): {len(unexpected_bills)}")
if unexpected_bills:
    print("   These 26 bills are NOT in the recent Parliamentary list:")
    for i, bill in enumerate(unexpected_bills, 1):
        print(f"   {i:2d}. {bill}")
else:
    print("   None - database matches expected bills perfectly!")

print(f"\n📈 Summary:")
print(f"   • Expected bills: {len(expected_bills)}")
print(f"   • Total in database: {len(all_bills_in_db)}")
print(f"   • Unexpected bills: {len(unexpected_bills)}")
print(f"   • Should remove: {len(unexpected_bills)} bills")

# Show which bills are missing (should be 0)
missing_bills = [bill for bill in expected_bills if bill not in all_bills_in_db]
if missing_bills:
    print(f"\n⚠️  Missing expected bills: {len(missing_bills)}")
    for bill in missing_bills:
        print(f"     - {bill}")
else:
    print(f"\n✅ All {len(expected_bills)} expected bills are present in database") 