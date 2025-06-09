#!/usr/bin/env python3
"""
Reset the 6 failed bills to pending_processing status for debugging
"""

import firebase_admin
from firebase_admin import firestore
from datetime import datetime, timezone

# Initialize Firebase
if not firebase_admin._apps:
    firebase_admin.initialize_app()

db = firestore.client()

# Reset the 6 failed bills to pending_processing
failed_bills = ['C-201', 'C-202', 'C-203', 'C-204', 'S-1001', 'S-221']
count = 0

print("🔄 Resetting failed bills to pending_processing status...")

for bill in failed_bills:
    query = db.collection('raw_legisinfo_bill_details').where(
        'bill_number_code_feed', '==', bill
    ).where('parliament_session_id', '==', '45-1').limit(1)
    
    docs = list(query.stream())
    
    if docs:
        doc_id = docs[0].id
        db.collection('raw_legisinfo_bill_details').document(doc_id).update({
            'processing_status': 'pending_processing',
            'last_attempted_processing_at': None
        })
        count += 1
        print(f'✅ Reset {bill} to pending_processing')
    else:
        print(f'❌ Bill {bill} not found')

print(f'\n🔄 Reset {count} bills to pending_processing status')
print("Ready to run processor to capture exact errors!") 