"""
Centralized Evidence Source Types Configuration for Python Pipeline

This module defines the canonical list of evidence source types used throughout
the Promise Tracker system. It mirrors the TypeScript configuration and provides
standardized types for processing scripts.

This ensures consistency between:
- Frontend UI components
- Backend API processing  
- Database storage
- Processing pipeline scripts
"""

from enum import Enum
from typing import Dict, List, Optional, NamedTuple


class SourceTypeCategory(Enum):
    """Categories for evidence source types"""
    GOVERNMENT = "government"
    LEGISLATIVE = "legislative" 
    NEWS = "news"
    MANUAL = "manual"
    OTHER = "other"


class EvidenceSourceType(NamedTuple):
    """Represents an evidence source type configuration"""
    key: str                                    # Machine-readable identifier (used in database)
    label: str                                  # Human-readable label (used in UI)
    description: Optional[str] = None           # Optional description for admin/dev use
    category: SourceTypeCategory = SourceTypeCategory.OTHER
    processor_type: Optional[str] = None        # Optional: which processor creates this type


# Canonical list of evidence source types
# IMPORTANT: Changes to this list should be coordinated with TypeScript configuration
EVIDENCE_SOURCE_TYPES: List[EvidenceSourceType] = [
    # Government Sources
    EvidenceSourceType(
        key='news_release_canada',
        label='News Release (Canada.ca)',
        description='Official news releases from Government of Canada websites',
        category=SourceTypeCategory.GOVERNMENT,
        processor_type='canada_news'
    ),
    EvidenceSourceType(
        key='government_announcement',
        label='Government Announcement',
        description='Official government announcements and statements',
        category=SourceTypeCategory.GOVERNMENT
    ),
    EvidenceSourceType(
        key='ministerial_statement',
        label='Ministerial Statement',
        description='Official statements from government ministers',
        category=SourceTypeCategory.GOVERNMENT
    ),
    EvidenceSourceType(
        key='policy_document',
        label='Policy Document',
        description='Government policy papers and strategy documents',
        category=SourceTypeCategory.GOVERNMENT
    ),
    EvidenceSourceType(
        key='budget_document',
        label='Budget Document',
        description='Federal, provincial, or territorial budget documents',
        category=SourceTypeCategory.GOVERNMENT
    ),

    # Legislative Sources
    EvidenceSourceType(
        key='bill_status_legisinfo',
        label='Bill Status (LEGISinfo)',
        description='Parliamentary bill information from LEGISinfo',
        category=SourceTypeCategory.LEGISLATIVE,
        processor_type='legisinfo'
    ),
    EvidenceSourceType(
        key='legislation',
        label='Legislation',
        description='Acts, regulations, and other legislative documents',
        category=SourceTypeCategory.LEGISLATIVE
    ),
    EvidenceSourceType(
        key='canada_gazette',
        label='Canada Gazette',
        description='Official publication of Government of Canada regulations',
        category=SourceTypeCategory.LEGISLATIVE,
        processor_type='canada_gazette'
    ),
    EvidenceSourceType(
        key='orders_in_council',
        label='Orders in Council',
        description='Government regulatory and administrative orders',
        category=SourceTypeCategory.LEGISLATIVE,
        processor_type='orders_in_council'
    ),

    # News and Media
    EvidenceSourceType(
        key='news_release',
        label='News Release',
        description='News releases from media organizations',
        category=SourceTypeCategory.NEWS
    ),
    EvidenceSourceType(
        key='media_report',
        label='Media Report',
        description='News articles and media coverage',
        category=SourceTypeCategory.NEWS
    ),

    # Manual and Other
    EvidenceSourceType(
        key='manual_entry',
        label='Manual Entry',
        description='Manually added evidence items',
        category=SourceTypeCategory.MANUAL,
        processor_type='manual'
    ),
    EvidenceSourceType(
        key='report',
        label='Report',
        description='Government or third-party reports and studies',
        category=SourceTypeCategory.OTHER
    ),
    EvidenceSourceType(
        key='other',
        label='Other',
        description='Other types of evidence not covered above',
        category=SourceTypeCategory.OTHER
    )
]


# Helper functions for working with evidence source types

def get_source_type_by_key(key: str) -> Optional[EvidenceSourceType]:
    """Get source type configuration by key"""
    for source_type in EVIDENCE_SOURCE_TYPES:
        if source_type.key == key:
            return source_type
    return None


def get_source_type_label(key: str) -> str:
    """Get human-readable label by key"""
    source_type = get_source_type_by_key(key)
    return source_type.label if source_type else key  # Fallback to key if not found


def get_source_types_by_category(category: SourceTypeCategory) -> List[EvidenceSourceType]:
    """Get source types by category"""
    return [st for st in EVIDENCE_SOURCE_TYPES if st.category == category]


def get_source_types_by_processor(processor_type: str) -> List[EvidenceSourceType]:
    """Get source types that match a processor type"""
    return [st for st in EVIDENCE_SOURCE_TYPES if st.processor_type == processor_type]


def get_source_type_mapping() -> Dict[str, str]:
    """Get mapping for backend processing (key -> label)"""
    return {st.key: st.label for st in EVIDENCE_SOURCE_TYPES}


def get_legacy_processor_mapping() -> Dict[str, str]:
    """Get legacy mapping for existing processor types to new standardized keys"""
    return {
        'canada_news': 'news_release_canada',
        'legisinfo_bill': 'bill_status_legisinfo',
        'canada_gazette': 'canada_gazette',
        'orders_in_council': 'orders_in_council',
        'manual_evidence': 'manual_entry'
    }


def is_valid_source_type(key: str) -> bool:
    """Validate that a source type key exists"""
    return any(st.key == key for st in EVIDENCE_SOURCE_TYPES)


def get_standardized_source_type_for_processor(processor_name: str) -> str:
    """
    Get the standardized source type key for a given processor.
    
    This function helps processors use the correct standardized source type
    instead of their legacy internal names.
    
    Args:
        processor_name: Name of the processor (e.g., 'canada_news', 'legisinfo')
        
    Returns:
        Standardized source type key
    """
    # Map processor names to standardized source types
    processor_mapping = {
        'canada_news': 'news_release_canada',
        'legisinfo': 'bill_status_legisinfo', 
        'canada_gazette': 'canada_gazette',
        'orders_in_council': 'orders_in_council',
        'manual': 'manual_entry',
        'manual_evidence': 'manual_entry'
    }
    
    return processor_mapping.get(processor_name, 'other')


# Constants for easy access to common source types
class StandardSourceTypes:
    """Constants for commonly used source types"""
    NEWS_RELEASE_CANADA = 'news_release_canada'
    BILL_STATUS_LEGISINFO = 'bill_status_legisinfo'
    CANADA_GAZETTE = 'canada_gazette'
    ORDERS_IN_COUNCIL = 'orders_in_council'
    MANUAL_ENTRY = 'manual_entry'
    GOVERNMENT_ANNOUNCEMENT = 'government_announcement'
    POLICY_DOCUMENT = 'policy_document'
    OTHER = 'other' 