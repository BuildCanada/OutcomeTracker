#!/usr/bin/env python3
"""
Reset C-4 and C-5 to pending processing status
"""

import firebase_admin
from firebase_admin import firestore
from datetime import datetime, timezone

# Initialize Firebase
if not firebase_admin._apps:
    firebase_admin.initialize_app()

db = firestore.client()

bills = ['C-4', 'C-5']
for bill in bills:
    query = db.collection('raw_legisinfo_bill_details').where(
        'bill_number_code_feed', '==', bill
    ).where('parliament_session_id', '==', '45-1').limit(1)
    
    docs = list(query.stream())
    if docs:
        doc_id = docs[0].id
        db.collection('raw_legisinfo_bill_details').document(doc_id).update({
            'processing_status': 'pending_processing',
            'last_attempted_processing_at': datetime.now(timezone.utc)
        })
        print(f'✅ Reset {bill} to pending_processing')
    else:
        print(f'❌ {bill} not found')

print("🔄 Bills reset successfully!") 