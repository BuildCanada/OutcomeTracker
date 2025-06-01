#!/usr/bin/env python3
"""
Check gazette evidence items for field migration needs.
This script identifies gazette evidence items that may need field updates
based on the recent prompt template changes.
"""

import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..'))

from pipeline.core.base_job import BaseJob
from google.cloud import firestore

class GazetteEvidenceMigrationChecker(BaseJob):
    """Check gazette evidence items for migration needs."""
    
    def __init__(self):
        super().__init__(job_name="gazette_evidence_migration_checker")
        
    def _execute_job(self, **kwargs):
        """Check gazette evidence items for field migration needs."""
        
        try:
            self.logger.info("Starting gazette evidence items migration check...")
            
            # Query all gazette evidence items
            query = self.db.collection('evidence_items').where(
                filter=firestore.FieldFilter('evidence_source_type', '==', 'Regulation (Canada Gazette P2)')
            )
            
            items_found = list(query.stream())
            self.logger.info(f"Found {len(items_found)} gazette evidence items to check")
            
            issues_found = []
            
            for doc in items_found:
                data = doc.to_dict()
                doc_id = doc.id
                
                # Check for issues
                current_issues = []
                
                # Check llm_analysis_raw structure
                if 'llm_analysis_raw' in data:
                    analysis = data['llm_analysis_raw']
                    
                    # Check if it has old rias_summary field
                    if 'rias_summary' in analysis:
                        if 'full_text_summary' not in analysis:
                            current_issues.append("Has 'rias_summary' but missing 'full_text_summary' in llm_analysis_raw")
                    
                    # Check if it's missing full_text_summary entirely  
                    if 'full_text_summary' not in analysis:
                        current_issues.append("Missing 'full_text_summary' field in llm_analysis_raw")
                        
                # Check additional_metadata structure
                if 'additional_metadata' in data:
                    metadata = data['additional_metadata']
                    
                    # Check if it has old field names
                    if 'rias_summary' in metadata:
                        current_issues.append("Has 'rias_summary' in additional_metadata")
                        
                if current_issues:
                    issues_found.append({
                        'doc_id': doc_id,
                        'evidence_id': data.get('evidence_id', 'Unknown'),
                        'evidence_date': data.get('evidence_date'),
                        'issues': current_issues
                    })
                    
                    self.logger.info(f"📋 {doc_id}: {', '.join(current_issues)}")
                
            # Report results
            self.logger.info(f"\n{'='*60}")
            self.logger.info("GAZETTE EVIDENCE MIGRATION CHECK RESULTS")
            self.logger.info(f"{'='*60}")
            
            if issues_found:
                self.logger.info(f"⚠️  Found {len(issues_found)} items with potential migration needs:")
                
                for item in issues_found:
                    self.logger.info(f"\n📄 Document: {item['doc_id']}")
                    self.logger.info(f"   Evidence ID: {item['evidence_id']}")
                    if item['evidence_date']:
                        self.logger.info(f"   Date: {item['evidence_date']}")
                    self.logger.info(f"   Issues:")
                    for issue in item['issues']:
                        self.logger.info(f"     • {issue}")
                        
                self.logger.info(f"\n🔧 Recommended action:")
                self.logger.info("   Consider creating a migration script to:")
                self.logger.info("   1. Move 'rias_summary' to 'full_text_summary' in llm_analysis_raw")
                self.logger.info("   2. Remove old 'rias_summary' from additional_metadata") 
                self.logger.info("   3. Ensure all gazette items have proper field structure")
                
            else:
                self.logger.info("✅ All gazette evidence items have correct field structure!")
                self.logger.info("   No migration needed.")
            
            self.logger.info(f"\n📊 Summary:")
            self.logger.info(f"   Total gazette items checked: {len(items_found)}")
            self.logger.info(f"   Items needing migration: {len(issues_found)}")
            self.logger.info(f"   Items with correct structure: {len(items_found) - len(issues_found)}")
            
            return {
                'items_processed': len(items_found),
                'items_created': 0,
                'items_updated': 0,
                'items_skipped': len(items_found) - len(issues_found),
                'errors': len(issues_found),
                'metadata': {
                    'issues_found': issues_found,
                    'migration_needed': len(issues_found) > 0
                }
            }
            
        except Exception as e:
            self.logger.error(f"Error checking gazette evidence items: {e}")
            raise

if __name__ == "__main__":
    checker = GazetteEvidenceMigrationChecker()
    result = checker.execute() 