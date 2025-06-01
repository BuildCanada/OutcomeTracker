# Firestore Index Creation for Promise Tracker Pipeline

## Critical Indexes Required for Processing Pipeline

The processing pipeline requires composite indexes to efficiently query items by `evidence_processing_status` and `last_updated_at`. 

### Index Creation URLs (Click to Create)

**1. Raw News Releases Collection:**
```
https://console.firebase.google.com/v1/r/project/promisetrackerapp/firestore/indexes?create_composite=Cltwcm9qZWN0cy9wcm9taXNldHJhY2tlcmFwcC9kYXRhYmFzZXMvKGRlZmF1bHQpL2NvbGxlY3Rpb25Hcm91cHMvcmF3X25ld3NfcmVsZWFzZXMvaW5kZXhlcy9fEAEaHgoaZXZpZGVuY2VfcHJvY2Vzc2luZ19zdGF0dXMQARoTCg9sYXN0X3VwZGF0ZWRfYXQQARoMCghfX25hbWVfXxAB
```

**2. Raw LEGISinfo Bill Details Collection:**
```
https://console.firebase.google.com/v1/r/project/promisetrackerapp/firestore/indexes?create_composite=CmRwcm9qZWN0cy9wcm9taXNldHJhY2tlcmFwcC9kYXRhYmFzZXMvKGRlZmF1bHQpL2NvbGxlY3Rpb25Hcm91cHMvcmF3X2xlZ2lzaW5mb19iaWxsX2RldGFpbHMvaW5kZXhlcy9fEAEaHgoaZXZpZGVuY2VfcHJvY2Vzc2luZ19zdGF0dXMQARoTCg9sYXN0X3VwZGF0ZWRfYXQQARoMCghfX25hbWVfXxAB
```

**3. Raw Orders in Council Collection:**
```
https://console.firebase.google.com/v1/r/project/promisetrackerapp/firestore/indexes?create_composite=Cl9wcm9qZWN0cy9wcm9taXNldHJhY2tlcmFwcC9kYXRhYmFzZXMvKGRlZmF1bHQpL2NvbGxlY3Rpb25Hcm91cHMvcmF3X29yZGVyc19pbl9jb3VuY2lsL2luZGV4ZXMvXxABGh4KGmV2aWRlbmNlX3Byb2Nlc3Npbmdfc3RhdHVzEAEaEwoPbGFzdF91cGRhdGVkX2F0EAEaDAoIX19uYW1lX18QAQ
```

**4. Raw Gazette P2 Notices Collection:**
```
https://console.firebase.google.com/v1/r/project/promisetrackerapp/firestore/indexes?create_composite=CmBwcm9qZWN0cy9wcm9taXNldHJhY2tlcmFwcC9kYXRhYmFzZXMvKGRlZmF1bHQpL2NvbGxlY3Rpb25Hcm91cHMvcmF3X2dhemV0dGVfcDJfbm90aWNlcy9pbmRleGVzL18QARoeChpldmlkZW5jZV9wcm9jZXNzaW5nX3N0YXR1cxABGhMKD2xhc3RfdXBkYXRlZF9hdBABGgwKCF9fbmFtZV9fEAE
```

## Index Configuration Details

Each index contains the following fields in order:
1. `evidence_processing_status` (Ascending)
2. `last_updated_at` (Ascending) 
3. `__name__` (Ascending)

## Creation Process

1. Click each URL above (they will open Firebase Console)
2. Review the auto-populated index configuration
3. Click "Create Index" button
4. Wait for index to build (usually 1-5 minutes per index)

## Alternative: Firebase CLI Commands

If you prefer using Firebase CLI:

```bash
# Install Firebase CLI if not already installed
npm install -g firebase-tools

# Login to Firebase
firebase login

# Create indexes using firestore.indexes.json
firebase firestore:indexes
```

## Verification

After creating indexes, you can verify them in the Firebase Console:
- Go to Firestore → Indexes tab
- Look for the 4 new composite indexes
- Status should show "Ready" when complete

## Notes

- Index creation is asynchronous and may take several minutes
- Large collections take longer to index
- Queries will fail until indexes are ready
- These indexes are essential for the processing pipeline to function 