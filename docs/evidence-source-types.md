# Evidence Source Types System

## Overview

The Promise Tracker system uses a centralized configuration for evidence source types to ensure consistency across all components. This system standardizes how evidence types are defined, stored, and displayed throughout the application.

## Architecture

### Centralized Configuration

**TypeScript Configuration**: `lib/evidence-source-types.ts`
- Used by frontend components (React/Next.js)
- Used by backend API routes
- Provides TypeScript types and helper functions

**Python Configuration**: `pipeline/config/evidence_source_types.py`
- Used by processing pipeline scripts
- Mirrors the TypeScript configuration
- Provides Python types and helper functions

### Source Type Structure

Each evidence source type has:
- **Key**: Machine-readable identifier (stored in database)
- **Label**: Human-readable name (displayed in UI)
- **Description**: Optional description for documentation
- **Category**: Classification (government, legislative, news, manual, other)
- **Processor Type**: Optional mapping to which processor creates this type

## Current Source Types

### Government Sources
- `news_release_canada` - News Release (Canada.ca)
- `government_announcement` - Government Announcement
- `ministerial_statement` - Ministerial Statement
- `policy_document` - Policy Document
- `budget_document` - Budget Document

### Legislative Sources
- `bill_status_legisinfo` - Bill Status (LEGISinfo)
- `legislation` - Legislation
- `canada_gazette` - Canada Gazette
- `orders_in_council` - Orders in Council

### News and Media
- `news_release` - News Release
- `media_report` - Media Report

### Manual and Other
- `manual_entry` - Manual Entry
- `report` - Report
- `other` - Other

## Usage Guidelines

### Frontend Components

```typescript
import { getSourceTypeOptions, getSourceTypeLabel } from '@/lib/evidence-source-types';

// For dropdowns
const options = getSourceTypeOptions();

// For displaying labels
const label = getSourceTypeLabel(evidenceItem.evidence_source_type);
```

### Backend API Routes

```typescript
import { getSourceTypeMappingForBackend, isValidSourceType } from '@/lib/evidence-source-types';

// Get mapping for processing
const mapping = getSourceTypeMappingForBackend();

// Validate source types
if (!isValidSourceType(sourceType)) {
  throw new Error('Invalid source type');
}
```

### Processing Scripts

```python
from config.evidence_source_types import get_standardized_source_type_for_processor

# Use standardized source type
evidence_item = {
    'evidence_source_type': get_standardized_source_type_for_processor('canada_news'),
    # ... other fields
}
```

## Maintenance

### Adding New Source Types

1. **Update TypeScript Configuration** (`lib/evidence-source-types.ts`):
   ```typescript
   {
     key: 'new_source_type',
     label: 'New Source Type',
     description: 'Description of the new source type',
     category: 'government', // or appropriate category
     processorType: 'processor_name' // if applicable
   }
   ```

2. **Update Python Configuration** (`pipeline/config/evidence_source_types.py`):
   ```python
   EvidenceSourceType(
       key='new_source_type',
       label='New Source Type',
       description='Description of the new source type',
       category=SourceTypeCategory.GOVERNMENT,
       processor_type='processor_name'
   )
   ```

3. **Update Processor Mapping** (if needed):
   - Add mapping in `get_standardized_source_type_for_processor()` function
   - Update any relevant processing scripts

### Modifying Existing Types

1. **Change Labels**: Update both TypeScript and Python configurations
2. **Change Keys**: Requires database migration plan
3. **Add Categories**: Update enum definitions in both configurations

### Database Migration

When changing source type keys:
1. Plan migration strategy for existing evidence items
2. Update all references in codebase
3. Test thoroughly before deployment
4. Consider backward compatibility

## Consistency Checks

### Automated Validation

The system includes helper functions to ensure consistency:
- `isValidSourceType()` - Validates source type keys
- `getSourceTypeLabel()` - Provides fallback for unknown types
- Type definitions prevent invalid configurations

### Manual Verification

Regularly verify:
- TypeScript and Python configurations match
- All processors use standardized types
- Frontend components use helper functions
- Database contains only valid source types

## Best Practices

1. **Always use helper functions** instead of hardcoding source types
2. **Keep configurations synchronized** between TypeScript and Python
3. **Test changes thoroughly** across all components
4. **Document any new source types** with clear descriptions
5. **Consider migration impact** when changing existing types

## Troubleshooting

### Common Issues

1. **Source type not found**: Check if key exists in configuration
2. **Inconsistent display**: Verify using `getSourceTypeLabel()` function
3. **Processing errors**: Ensure processor uses standardized types
4. **Frontend/backend mismatch**: Verify both use same configuration

### Debugging

Use browser dev tools and server logs to verify:
- Source types being sent/received match configuration
- Helper functions are being used correctly
- No hardcoded source type strings remain in code 