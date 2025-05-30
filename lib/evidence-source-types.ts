/**
 * Centralized Evidence Source Types Configuration
 * 
 * This file defines the canonical list of evidence source types used throughout
 * the Promise Tracker system. It provides both machine-readable keys and 
 * human-readable labels for consistent use across:
 * - Frontend UI components
 * - Backend API processing
 * - Database storage
 * - Processing pipeline scripts
 */

export interface EvidenceSourceType {
  key: string;              // Machine-readable identifier (used in database)
  label: string;            // Human-readable label (used in UI)
  description?: string;     // Optional description for admin/dev use
  category: 'government' | 'legislative' | 'news' | 'manual' | 'other';
  processorType?: string;   // Optional: which processor creates this type
}

/**
 * Canonical list of evidence source types
 * 
 * IMPORTANT: Changes to this list should be coordinated across:
 * - Frontend components (dropdowns, filters, displays)
 * - Backend API mapping and validation
 * - Processing scripts standardization
 * - Database migration if keys change
 */
export const EVIDENCE_SOURCE_TYPES: EvidenceSourceType[] = [
  // Government Sources
  {
    key: 'news_release_canada',
    label: 'News Release (Canada.ca)',
    description: 'Official news releases from Government of Canada websites',
    category: 'government',
    processorType: 'canada_news'
  },
  {
    key: 'government_announcement',
    label: 'Government Announcement',
    description: 'Official government announcements and statements',
    category: 'government'
  },
  {
    key: 'ministerial_statement',
    label: 'Ministerial Statement',
    description: 'Official statements from government ministers',
    category: 'government'
  },
  {
    key: 'policy_document',
    label: 'Policy Document',
    description: 'Government policy papers and strategy documents',
    category: 'government'
  },
  {
    key: 'budget_document',
    label: 'Budget Document',
    description: 'Federal, provincial, or territorial budget documents',
    category: 'government'
  },

  // Legislative Sources
  {
    key: 'bill_status_legisinfo',
    label: 'Bill Status (LEGISinfo)',
    description: 'Parliamentary bill information from LEGISinfo',
    category: 'legislative',
    processorType: 'legisinfo'
  },
  {
    key: 'legislation',
    label: 'Legislation',
    description: 'Acts, regulations, and other legislative documents',
    category: 'legislative'
  },
  {
    key: 'canada_gazette',
    label: 'Canada Gazette',
    description: 'Official publication of Government of Canada regulations',
    category: 'legislative',
    processorType: 'canada_gazette'
  },
  {
    key: 'orders_in_council',
    label: 'Orders in Council',
    description: 'Government regulatory and administrative orders',
    category: 'legislative',
    processorType: 'orders_in_council'
  },

  // News and Media
  {
    key: 'news_release',
    label: 'News Release',
    description: 'News releases from media organizations',
    category: 'news'
  },
  {
    key: 'media_report',
    label: 'Media Report',
    description: 'News articles and media coverage',
    category: 'news'
  },

  // Manual and Other
  {
    key: 'manual_entry',
    label: 'Manual Entry',
    description: 'Manually added evidence items',
    category: 'manual',
    processorType: 'manual'
  },
  {
    key: 'report',
    label: 'Report',
    description: 'Government or third-party reports and studies',
    category: 'other'
  },
  {
    key: 'other',
    label: 'Other',
    description: 'Other types of evidence not covered above',
    category: 'other'
  }
];

/**
 * Helper functions for working with evidence source types
 */

// Get all source types as key-value pairs for form dropdowns
export const getSourceTypeOptions = () => {
  return EVIDENCE_SOURCE_TYPES.map(type => ({
    value: type.key,
    label: type.label
  }));
};

// Get source type by key
export const getSourceTypeByKey = (key: string): EvidenceSourceType | undefined => {
  return EVIDENCE_SOURCE_TYPES.find(type => type.key === key);
};

// Get human-readable label by key
export const getSourceTypeLabel = (key: string): string => {
  const sourceType = getSourceTypeByKey(key);
  return sourceType ? sourceType.label : key; // Fallback to key if not found
};

// Get source types by category
export const getSourceTypesByCategory = (category: EvidenceSourceType['category']) => {
  return EVIDENCE_SOURCE_TYPES.filter(type => type.category === category);
};

// Get mapping for backend processing (key -> label)
export const getSourceTypeMappingForBackend = (): { [key: string]: string } => {
  const mapping: { [key: string]: string } = {};
  EVIDENCE_SOURCE_TYPES.forEach(type => {
    mapping[type.key] = type.label;
  });
  return mapping;
};

// Get legacy mapping for existing processor types
export const getLegacyProcessorMapping = (): { [key: string]: string } => {
  return {
    'canada_news': 'news_release_canada',
    'legisinfo_bill': 'bill_status_legisinfo',
    'canada_gazette': 'canada_gazette',
    'orders_in_council': 'orders_in_council',
    'manual_evidence': 'manual_entry'
  };
};

// Get reverse mapping for backend processing (label -> key)
export const getReverseSourceTypeMapping = (): { [label: string]: string } => {
  const mapping: { [label: string]: string } = {};
  EVIDENCE_SOURCE_TYPES.forEach(type => {
    mapping[type.label] = type.key;
  });
  return mapping;
};

// Get source type key by label (reverse lookup)
export const getSourceTypeKeyByLabel = (label: string): string => {
  const sourceType = EVIDENCE_SOURCE_TYPES.find(type => type.label === label);
  return sourceType ? sourceType.key : 'other'; // Fallback to 'other' if not found
};

// Validation function
export const isValidSourceType = (key: string): boolean => {
  return EVIDENCE_SOURCE_TYPES.some(type => type.key === key);
}; 