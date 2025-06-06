# Hardcoded Path Issues - RESOLVED ✅

## Problem Summary
The Cloud Run deployment was failing due to hardcoded local file paths in the pipeline code. Two critical issues were identified from Google Cloud logs:

1. **Hardcoded prompt template path**: `/Users/tscheidt/promise-tracker/PromiseTracker/prompts/prompt_bill_evidence.md`
2. **Method signature mismatch**: `'str' object has no attribute 'get'` error in status update

## Root Causes & Fixes Applied

### 1. ✅ Fixed Hardcoded Prompt Template Paths
**Problem:** Several processors were using hardcoded local paths instead of relative paths
**Files Fixed:**
- `pipeline/stages/processing/legisinfo_processor.py` - Line 249
- `pipeline/stages/processing/orders_in_council_processor.py` - Line 82

**Changes Made:**
```python
# BEFORE (hardcoded):
prompt_file = Path("/Users/tscheidt/promise-tracker/PromiseTracker/prompts/prompt_bill_evidence.md")

# AFTER (relative):
prompt_file = Path(__file__).parent.parent.parent.parent / "prompts" / "prompt_bill_evidence.md"
```

### 2. ✅ Fixed Method Signature Mismatch
**Problem:** Multiple processors had different signatures than base class
- **Base class**: `_update_processing_status(self, doc_id: str, status: str)`
- **LegisInfo class**: `_update_processing_status(self, raw_item: Dict[str, Any], status: str)` ❌
- **Orders in Council class**: `_update_processing_status(self, raw_item: Dict[str, Any], status: str)` ❌

**Fix Applied:**
1. **Changed method signatures** to match base class: `_update_processing_status(self, doc_id: str, status: str)`
2. **Updated all method calls** to pass `raw_item.get('_doc_id', '')` instead of full `raw_item` dictionary

**Fixed call sites in `legisinfo_processor.py` (5 locations):**
   - Line 131: Error processing script
   - Line 142: Error processing script  
   - Line 147: Skipped not relevant
   - Line 157: Processed successfully
   - Line 163: Error processing script

**Fixed call sites in `orders_in_council_processor.py` (5 locations):**
   - Line 139: Skipped missing data
   - Line 145: Skipped insufficient content
   - Line 153: Error processing script
   - Line 160: Evidence created
   - Line 166: Error processing script

### 3. ✅ Standardized Relative Path Patterns
**Verified consistent path depth** across all processors:

**Correct Pattern (4 levels up from `stages/processing/` or `stages/linking/`):**
```python
Path(__file__).parent.parent.parent.parent / "prompts" / "template.md"
```

**Files Verified/Corrected:**
- ✅ `pipeline/stages/processing/legisinfo_processor.py` - Fixed to 4 levels
- ✅ `pipeline/stages/processing/orders_in_council_processor.py` - Fixed to 4 levels  
- ✅ `pipeline/stages/linking/progress_scorer.py` - Already correct (4 levels)
- ✅ `pipeline/stages/linking/llm_evidence_validator.py` - Already correct (4 levels)

### 4. ✅ Verified Prompt Files Exist
**Confirmed all required prompt templates exist** in `PromiseTracker/prompts/`:
- `prompt_bill_evidence.md` ✅ (4.3KB, 48 lines)
- `prompt_oic_evidence.md` ✅ (4.9KB, 47 lines)
- `prompt_evidence_promise_validation.md` ✅ (6.9KB, 122 lines)
- `prompt_progress_scoring.md` ✅ (4.2KB, 83 lines)

## Directory Structure Reference
Understanding the path traversal:
```
PromiseTracker/                           # Target directory
├── pipeline/
│   └── stages/
│       ├── processing/                   # __file__.parent.parent.parent.parent
│       │   ├── legisinfo_processor.py    # Need 4 levels up to reach PromiseTracker/
│       │   └── orders_in_council_processor.py
│       └── linking/                      # __file__.parent.parent.parent.parent  
│           ├── progress_scorer.py        # Need 4 levels up to reach PromiseTracker/
│           └── llm_evidence_validator.py
└── prompts/                             # Target: PromiseTracker/prompts/
    ├── prompt_bill_evidence.md
    ├── prompt_oic_evidence.md
    └── ...
```

## Testing Verification
**Methods to verify fixes work in Cloud Run:**

1. **Path Resolution Test:**
   ```python
   from pathlib import Path
   prompt_file = Path(__file__).parent.parent.parent.parent / "prompts" / "prompt_bill_evidence.md"
   print(f"Prompt file exists: {prompt_file.exists()}")
   print(f"Resolved path: {prompt_file.resolve()}")
   ```

2. **Method Signature Test:**
   ```python
   # This should now work without 'str' object errors:
   processor._update_processing_status(doc_id="test_id", status="processed")
   ```

## Expected Results Post-Fix
With these fixes, the pipeline should:
1. ✅ **Load prompt templates successfully** in Cloud Run environment
2. ✅ **Update processing status correctly** without 'str' object errors  
3. ✅ **Process bills through LLM analysis** using proper prompt templates
4. ✅ **Create evidence items** with complete LLM-generated analysis
5. ✅ **Trigger downstream linking** automatically after evidence creation

## Error Prevention
**Going forward, use this pattern for ALL file paths in the pipeline:**
```python
# For files in PromiseTracker/ directory:
file_path = Path(__file__).parent.parent.parent.parent / "relative" / "path" / "file.ext"

# Always verify the file exists:
if file_path.exists():
    content = file_path.read_text()
else:
    logger.error(f"Required file not found: {file_path}")
```

**Never use:**
- Hardcoded absolute paths like `/Users/...`
- Environment-specific paths
- Paths that assume specific directory structures outside the codebase 