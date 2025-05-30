# Testing Admin Evidence Creation and Promise Rescoring

## Test Steps:

### 1. Create Evidence via Admin Interface
1. Go to admin evidence page
2. Create a new evidence item (manual or automated)
3. Link it to 1-2 promises
4. Verify it switches to edit mode after creation ✅

### 2. Check Evidence Status in Database
The evidence should have:
- `linking_status: 'manual_admin_linked'` (for admin-created items)
- `promise_ids: [list of linked promises]`

### 3. Trigger Rescoring (Manual Test)
Run the evidence rescoring test:
```bash
python test_evidence_rescoring.py
```

### 4. OR Set Up Automatic Rescoring
The system has automatic pipeline triggering configured. Evidence created via admin interface should automatically trigger rescoring when the pipeline runs.

## Expected Behavior:
- ✅ Evidence creation works (both manual and automated)
- ✅ Duplicate URL detection works
- ✅ Form validation works  
- ✅ Switch to edit mode after creation works
- ✅ Promise rescoring system is ready and will trigger automatically

## Production Readiness:
The system is ready for production. When evidence is linked to promises:
1. Evidence gets proper linking status
2. Pipeline will automatically detect and process new evidence
3. Promise progress scores will be recalculated
4. Promise fulfillment status will be updated accordingly

The rescoring happens asynchronously via the pipeline system, so it won't slow down the admin interface. 