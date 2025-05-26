#!/usr/bin/env python

import firebase_admin
from firebase_admin import firestore

firebase_admin.initialize_app()
db = firestore.client()

print('=== Evidence Items Test Collection Summary ===')
evidence_query = db.collection('evidence_items_test').where('parliament_session_id', '==', '44').limit(10)
evidence_docs = list(evidence_query.stream())

print(f'Total found (first 10): {len(evidence_docs)}')
print()

for i, doc in enumerate(evidence_docs):
    data = doc.to_dict()
    linking_status = data.get('linking_status', 'NULL')
    evidence_type = data.get('evidence_source_type', 'N/A')
    title = data.get('title_or_summary', 'N/A')[:60]
    print(f'{i+1}. {doc.id[:20]}... | Status: {linking_status} | Type: {evidence_type} | Title: {title}...')

print()
print('=== Linking Status Distribution ===')
all_evidence = list(db.collection('evidence_items_test').where('parliament_session_id', '==', '44').stream())
status_counts = {}
for doc in all_evidence:
    status = doc.to_dict().get('linking_status', 'NULL')
    status_counts[status] = status_counts.get(status, 0) + 1

print(f'Total evidence items: {len(all_evidence)}')
for status, count in sorted(status_counts.items()):
    print(f'{status}: {count}') 