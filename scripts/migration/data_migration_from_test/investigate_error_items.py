#!/usr/bin/env python3
"""
Investigate Error Items Script

This script investigates specific error items in raw collections to understand
what went wrong and provide recommendations for fixing them.

Usage:
    python investigate_error_items.py [--fix-errors] [--dry-run]
"""

import os
import sys
import json
from datetime import datetime
from typing import Dict, List, Any

# Add the parent directory to the path to import common utilities
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

try:
    import firebase_admin
    from firebase_admin import credentials, firestore
    from dotenv import load_dotenv
    
    # Load environment variables
    load_dotenv()
except ImportError as e:
    print(f"Error: Could not import required modules: {e}")
    sys.exit(1)


class ErrorItemInvestigator:
    """Investigates and potentially fixes error items in raw collections."""
    
    def __init__(self):
        """Initialize the investigator."""
        self.db = self._init_firebase()
        self.timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        
        # Define error status patterns to look for
        self.error_patterns = [
            'error_llm_processing',
            'error_processing_script', 
            'error_missing_fields',
            'error_llm_missing_summary'
        ]
        
        self.investigation_report = {
            'investigation_timestamp': self.timestamp,
            'investigation_date': datetime.now().isoformat(),
            'error_items': {},
            'recommendations': []
        }
    
    def _init_firebase(self):
        """Initialize Firebase connection."""
        if not firebase_admin._apps:
            try:
                firebase_admin.initialize_app()
                project_id = os.getenv('FIREBASE_PROJECT_ID', '[Not Set - Using Default]')
                print(f"Connected to Cloud Firestore (Project: {project_id}) using default credentials.")
            except Exception as e_default:
                print(f"Cloud Firestore init with default creds failed: {e_default}. Attempting service account.")
                cred_path = os.getenv('FIREBASE_SERVICE_ACCOUNT_KEY_PATH')
                if cred_path:
                    try:
                        print(f"Attempting Firebase init with service account key from env var: {cred_path}")
                        cred = credentials.Certificate(cred_path)
                        firebase_admin.initialize_app(cred)
                        project_id_sa = os.getenv('FIREBASE_PROJECT_ID', '[Not Set - Using Service Account]')
                        print(f"Connected to Cloud Firestore (Project: {project_id_sa}) via service account.")
                    except Exception as e_sa:
                        print(f"Firebase init with service account key from {cred_path} failed: {e_sa}")
                        raise
                else:
                    print("FIREBASE_SERVICE_ACCOUNT_KEY_PATH environment variable not set, and default creds failed.")
                    raise e_default
        
        return firestore.client()
    
    def investigate_collection_errors(self, collection_name: str, status_field: str) -> List[Dict]:
        """Find and investigate all error items in a collection."""
        error_items = []
        
        print(f"\n🔍 Investigating errors in {collection_name}...")
        
        try:
            # Get all documents and filter for error statuses
            docs = self.db.collection(collection_name).stream()
            
            for doc in docs:
                doc_data = doc.to_dict()
                status = doc_data.get(status_field, 'missing_status_field')
                
                # Check if this is an error status
                if any(error_pattern in status.lower() for error_pattern in self.error_patterns):
                    error_item = {
                        'collection': collection_name,
                        'document_id': doc.id,
                        'status': status,
                        'error_details': self._extract_error_details(doc_data),
                        'document_data': self._sanitize_document_data(doc_data)
                    }
                    error_items.append(error_item)
                    
                    print(f"  ❌ Found error: {doc.id} - Status: {status}")
                    
                    # Print key details
                    if 'processing_error_message' in doc_data:
                        print(f"     Error Message: {doc_data['processing_error_message']}")
                    if 'title_raw' in doc_data:
                        print(f"     Title: {doc_data['title_raw'][:100]}...")
                    if 'bill_number_code_feed' in doc_data:
                        print(f"     Bill: {doc_data['bill_number_code_feed']}")
                    if 'publication_date' in doc_data:
                        pub_date = doc_data['publication_date']
                        if hasattr(pub_date, 'strftime'):
                            print(f"     Date: {pub_date.strftime('%Y-%m-%d')}")
                        else:
                            print(f"     Date: {pub_date}")
        
        except Exception as e:
            print(f"Error investigating {collection_name}: {e}")
        
        return error_items
    
    def _extract_error_details(self, doc_data: Dict) -> Dict:
        """Extract relevant error details from document data."""
        error_details = {}
        
        # Common error fields
        error_fields = [
            'processing_error_message',
            'llm_model_name_last_attempt',
            'last_updated_at',
            'error_timestamp'
        ]
        
        for field in error_fields:
            if field in doc_data:
                value = doc_data[field]
                if hasattr(value, 'isoformat'):
                    error_details[field] = value.isoformat()
                else:
                    error_details[field] = str(value)
        
        return error_details
    
    def _sanitize_document_data(self, doc_data: Dict) -> Dict:
        """Sanitize document data for JSON serialization and readability."""
        sanitized = {}
        
        # Key fields to include
        key_fields = [
            'raw_item_id', 'title_raw', 'bill_number_code_feed', 'oic_number',
            'publication_date', 'source_url', 'ingested_at', 'evidence_processing_status',
            'processing_status', 'processing_error_message', 'llm_model_name_last_attempt'
        ]
        
        for field in key_fields:
            if field in doc_data:
                value = doc_data[field]
                if hasattr(value, 'isoformat'):
                    sanitized[field] = value.isoformat()
                elif isinstance(value, str) and len(value) > 200:
                    sanitized[field] = value[:200] + "..."
                else:
                    sanitized[field] = value
        
        return sanitized
    
    def analyze_error_patterns(self, error_items: List[Dict]) -> List[str]:
        """Analyze error patterns and generate recommendations."""
        recommendations = []
        
        # Group errors by type
        error_by_type = {}
        for item in error_items:
            status = item['status']
            if status not in error_by_type:
                error_by_type[status] = []
            error_by_type[status].append(item)
        
        print(f"\n📊 Error Analysis:")
        for error_type, items in error_by_type.items():
            print(f"  {error_type}: {len(items)} items")
            
            # Analyze specific error types
            if error_type == 'error_llm_processing':
                recommendations.append(f"🔧 {len(items)} LLM processing errors - try reprocessing with --force_reprocessing")
                
                # Check if there are common patterns
                models_used = set()
                for item in items:
                    model = item['error_details'].get('llm_model_name_last_attempt')
                    if model:
                        models_used.add(model)
                
                if models_used:
                    recommendations.append(f"   Models involved: {', '.join(models_used)}")
            
            elif error_type == 'error_processing_script':
                recommendations.append(f"🔧 {len(items)} script processing errors - investigate error messages")
                
                # Look for common error messages
                error_messages = set()
                for item in items:
                    msg = item['error_details'].get('processing_error_message')
                    if msg:
                        error_messages.add(msg[:100])  # First 100 chars
                
                for msg in error_messages:
                    recommendations.append(f"   Common error: {msg}")
            
            elif error_type == 'error_missing_fields':
                recommendations.append(f"🔧 {len(items)} missing fields errors - check data quality")
        
        return recommendations
    
    def suggest_fixes(self, error_items: List[Dict]) -> List[str]:
        """Suggest specific fixes for the error items."""
        fixes = []
        
        for item in error_items:
            collection = item['collection']
            doc_id = item['document_id']
            status = item['status']
            
            if status == 'error_llm_processing':
                fixes.append(f"🔄 {collection}/{doc_id}: Retry with force reprocessing")
                
            elif status == 'error_processing_script':
                error_msg = item['error_details'].get('processing_error_message', '')
                if '400 Nested arrays' in error_msg:
                    fixes.append(f"🔧 {collection}/{doc_id}: Data structure issue - may need manual review")
                else:
                    fixes.append(f"🔄 {collection}/{doc_id}: Retry with force reprocessing")
            
            elif status == 'error_missing_fields':
                fixes.append(f"🔍 {collection}/{doc_id}: Check data completeness before reprocessing")
        
        return fixes
    
    def reset_error_items_for_reprocessing(self, error_items: List[Dict], dry_run: bool = True) -> int:
        """Reset error items to pending status for reprocessing."""
        reset_count = 0
        
        print(f"\n{'[DRY RUN] ' if dry_run else ''}Resetting error items for reprocessing...")
        
        for item in error_items:
            collection = item['collection']
            doc_id = item['document_id']
            status = item['status']
            
            # Determine the correct pending status for each collection
            if collection == 'raw_news_releases':
                new_status = 'pending_evidence_creation'
            elif collection == 'raw_legisinfo_bill_details':
                new_status = 'pending_processing'
            elif collection == 'raw_orders_in_council':
                new_status = 'pending_evidence_creation'
            elif collection == 'raw_gazette_p2_notices':
                new_status = 'pending_evidence_creation'
            else:
                print(f"  ⚠️ Unknown collection {collection}, skipping {doc_id}")
                continue
            
            if dry_run:
                print(f"  [DRY RUN] Would reset {collection}/{doc_id}: {status} → {new_status}")
            else:
                try:
                    # Determine the status field name
                    if collection == 'raw_legisinfo_bill_details':
                        status_field = 'processing_status'
                    else:
                        status_field = 'evidence_processing_status'
                    
                    # Reset the status
                    doc_ref = self.db.collection(collection).document(doc_id)
                    doc_ref.update({
                        status_field: new_status,
                        'error_reset_at': firestore.SERVER_TIMESTAMP,
                        'error_reset_by': 'investigate_error_items.py'
                    })
                    
                    print(f"  ✅ Reset {collection}/{doc_id}: {status} → {new_status}")
                    reset_count += 1
                    
                except Exception as e:
                    print(f"  ❌ Failed to reset {collection}/{doc_id}: {e}")
        
        return reset_count
    
    def run_investigation(self, fix_errors: bool = False, dry_run: bool = True):
        """Run the complete error investigation."""
        print(f"{'='*60}")
        print(f"ERROR ITEMS INVESTIGATION")
        print(f"Timestamp: {self.timestamp}")
        print(f"{'='*60}")
        
        all_error_items = []
        
        # Collections to check
        collections_config = {
            'raw_gazette_p2_notices': 'evidence_processing_status',
            'raw_legisinfo_bill_details': 'processing_status', 
            'raw_news_releases': 'evidence_processing_status',
            'raw_orders_in_council': 'evidence_processing_status'
        }
        
        # Investigate each collection
        for collection_name, status_field in collections_config.items():
            error_items = self.investigate_collection_errors(collection_name, status_field)
            all_error_items.extend(error_items)
        
        # Store in report
        self.investigation_report['error_items'] = all_error_items
        
        # Analyze patterns
        recommendations = self.analyze_error_patterns(all_error_items)
        self.investigation_report['recommendations'] = recommendations
        
        # Generate fix suggestions
        fixes = self.suggest_fixes(all_error_items)
        
        # Print summary
        print(f"\n{'='*60}")
        print(f"INVESTIGATION SUMMARY")
        print(f"{'='*60}")
        print(f"Total error items found: {len(all_error_items)}")
        
        if all_error_items:
            print(f"\n📋 Recommendations:")
            for rec in recommendations:
                print(f"  {rec}")
            
            print(f"\n🔧 Suggested Fixes:")
            for fix in fixes:
                print(f"  {fix}")
            
            # Offer to reset errors for reprocessing
            if fix_errors:
                print(f"\n🔄 Resetting error items for reprocessing...")
                reset_count = self.reset_error_items_for_reprocessing(all_error_items, dry_run)
                
                if dry_run:
                    print(f"\n[DRY RUN] Would reset {reset_count} error items")
                else:
                    print(f"\n✅ Reset {reset_count} error items for reprocessing")
        else:
            print("🎉 No error items found!")
        
        return len(all_error_items) == 0
    
    def save_investigation_report(self):
        """Save the investigation report to a JSON file."""
        report_filename = f"error_investigation_report_{self.timestamp}.json"
        report_path = os.path.join(
            os.path.dirname(__file__), 
            report_filename
        )
        
        try:
            with open(report_path, 'w') as f:
                json.dump(self.investigation_report, f, indent=2)
            print(f"\n✓ Investigation report saved to: {report_path}")
        except Exception as e:
            print(f"\n✗ Error saving investigation report: {e}")


def main():
    """Main function."""
    import argparse
    
    parser = argparse.ArgumentParser(description='Investigate error items in raw collections')
    parser.add_argument('--fix-errors', action='store_true',
                       help='Reset error items to pending status for reprocessing')
    parser.add_argument('--dry-run', action='store_true', default=True,
                       help='Show what would be done without making changes (default: True)')
    parser.add_argument('--live', action='store_true',
                       help='Actually make changes (overrides --dry-run)')
    
    args = parser.parse_args()
    
    # Handle dry-run logic
    if args.live:
        dry_run = False
    else:
        dry_run = True
    
    try:
        investigator = ErrorItemInvestigator()
        no_errors = investigator.run_investigation(fix_errors=args.fix_errors, dry_run=dry_run)
        investigator.save_investigation_report()
        
        if no_errors:
            print(f"\n🎉 No error items found - collections are healthy!")
            sys.exit(0)
        else:
            if args.fix_errors and not dry_run:
                print(f"\n✅ Error items have been reset for reprocessing.")
                print(f"   Run the processing scripts to retry them.")
            elif args.fix_errors and dry_run:
                print(f"\n🔍 This was a dry run. Use --live to actually reset errors.")
            else:
                print(f"\n💡 Use --fix-errors --live to reset error items for reprocessing.")
            sys.exit(1)
            
    except KeyboardInterrupt:
        print("\n\n⚠ Investigation interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ Unexpected error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main() 