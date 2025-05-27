# PrimaryEnergyChart Format Update

## Summary of Changes

The `primary-energy.json` file format was updated, requiring changes to the PrimaryEnergyChart component to maintain compatibility.

## Old vs New JSON Structure

### Old Format
```json
{
  "data": {
    "Production": {
      "Primary energy": [
        ["2024-10", 2028794.0],
        ["2024-11", 2052127.0]
      ],
      "Coal": [...],
      "Crude oil": [...]
    }
  }
}
```

### New Format
```json
{
  "data": {
    "Primary energy": {
      "Production": [
        ["2024-10", 2028794.0],
        ["2024-11", 2052127.0]
      ],
      "Availability": [...],
      "Exports": [...]
    },
    "Coal": {
      "Production": [...],
      "Availability": [...]
    }
  }
}
```

## Code Changes Made

### PrimaryEnergyChart.tsx
**Line 60**: Changed data access pattern
- **Before**: `energyDataObj.data.Production[category]`
- **After**: `energyDataObj.data[category]?.Production`

### PrimaryEnergyChart.stories.ts
**Lines 24-36**: Updated category options to reflect new available energy sources:
- Added: 'Coke', 'Secondary electricity, thermal', 'Secondary energy', 'Total primary and secondary energy'
- Maintained: All existing categories

## Available Energy Categories

The new format supports the following energy categories:
- Primary energy
- Coal
- Coke
- Crude oil
- Natural gas
- Natural gas liquids
- Primary electricity, hydro, nuclear, and other renewables
- Refined petroleum products
- Renewable fuels
- Secondary electricity, thermal
- Secondary energy
- Total primary and secondary energy

## Data Points Available

Each energy category now includes multiple data points:
- **Production**: Energy production values
- **Availability**: Available energy supply
- **Exports**: Energy export volumes
- **Imports**: Energy import volumes
- **Net supply**: Net energy supply after imports/exports
- **Stock variation**: Changes in energy stocks
- **Other adjustments**: Statistical adjustments

## Impact on Functionality

- ✅ Chart rendering: No impact
- ✅ Data visualization: No impact
- ✅ Trend analysis: No impact
- ✅ Target lines: No impact
- ✅ Storybook stories: Updated with new categories
- ✅ Build process: Successful compilation

## Testing Status

- ✅ Component diagnostics: No errors or warnings
- ✅ Story diagnostics: No errors or warnings
- ✅ Build process: Successful (216 kB bundle)
- ✅ DepartmentMetrics integration: Working correctly

## Future Considerations

The new format provides access to additional data points beyond just production values. Future enhancements could include:
- Export vs production comparison charts
- Net supply analysis
- Import dependency tracking
- Stock variation monitoring