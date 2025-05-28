#!/usr/bin/env python3
"""
Examine Specific Document Script

This script examines a specific document to understand its data structure
and identify potential issues that might cause processing failures.

Usage:
    python examine_specific_document.py <collection_name> <document_id>
"""

import os
import sys
import json
from datetime import datetime

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


class DocumentExaminer:
    """Examines specific documents for data quality issues."""
    
    def __init__(self):
        """Initialize the examiner."""
        self.db = self._init_firebase()
    
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
    
    def examine_document(self, collection_name: str, document_id: str):
        """Examine a specific document and analyze its data."""
        print(f"{'='*60}")
        print(f"DOCUMENT EXAMINATION")
        print(f"Collection: {collection_name}")
        print(f"Document ID: {document_id}")
        print(f"{'='*60}")
        
        try:
            # Get the document
            doc_ref = self.db.collection(collection_name).document(document_id)
            doc = doc_ref.get()
            
            if not doc.exists:
                print(f"❌ Document {document_id} does not exist in collection {collection_name}")
                return
            
            doc_data = doc.to_dict()
            
            # Basic document info
            print(f"\n📋 Basic Information:")
            print(f"  Document exists: ✅ Yes")
            print(f"  Total fields: {len(doc_data)}")
            
            # Print all fields and their types/sizes
            print(f"\n📊 Field Analysis:")
            for field_name, field_value in doc_data.items():
                field_type = type(field_value).__name__
                
                if isinstance(field_value, str):
                    field_size = len(field_value)
                    preview = field_value[:100] + "..." if len(field_value) > 100 else field_value
                    print(f"  {field_name}: {field_type} ({field_size} chars) = '{preview}'")
                elif isinstance(field_value, list):
                    field_size = len(field_value)
                    print(f"  {field_name}: {field_type} ({field_size} items) = {field_value[:3]}{'...' if field_size > 3 else ''}")
                elif isinstance(field_value, dict):
                    field_size = len(field_value)
                    print(f"  {field_name}: {field_type} ({field_size} keys) = {list(field_value.keys())[:5]}{'...' if field_size > 5 else ''}")
                elif hasattr(field_value, 'isoformat'):
                    print(f"  {field_name}: {field_type} = {field_value.isoformat()}")
                else:
                    print(f"  {field_name}: {field_type} = {field_value}")
            
            # Check for common issues
            print(f"\n🔍 Data Quality Checks:")
            
            # Check for required fields based on collection
            if collection_name == 'raw_legisinfo_bill_details':
                required_fields = ['bill_number_code_feed', 'bill_title', 'bill_summary']
                self._check_required_fields(doc_data, required_fields)
                self._check_text_content_quality(doc_data, ['bill_title', 'bill_summary', 'bill_text_content'])
            elif collection_name == 'raw_news_releases':
                required_fields = ['title_raw', 'publication_date', 'source_url']
                self._check_required_fields(doc_data, required_fields)
                self._check_text_content_quality(doc_data, ['title_raw', 'summary_or_snippet_raw', 'full_text_scraped'])
            
            # Check for empty or problematic content
            self._check_for_empty_content(doc_data)
            
            # Save detailed analysis
            self._save_document_analysis(collection_name, document_id, doc_data)
            
        except Exception as e:
            print(f"❌ Error examining document: {e}")
    
    def _check_required_fields(self, doc_data: dict, required_fields: list):
        """Check if required fields are present and non-empty."""
        print(f"  Required Fields Check:")
        for field in required_fields:
            if field not in doc_data:
                print(f"    ❌ Missing: {field}")
            elif not doc_data[field]:
                print(f"    ⚠️ Empty: {field}")
            elif isinstance(doc_data[field], str) and len(doc_data[field].strip()) == 0:
                print(f"    ⚠️ Whitespace only: {field}")
            else:
                print(f"    ✅ Present: {field}")
    
    def _check_text_content_quality(self, doc_data: dict, text_fields: list):
        """Check the quality of text content fields."""
        print(f"  Text Content Quality:")
        for field in text_fields:
            if field in doc_data and doc_data[field]:
                content = str(doc_data[field])
                content_length = len(content)
                
                if content_length == 0:
                    print(f"    ❌ {field}: Empty")
                elif content_length < 10:
                    print(f"    ⚠️ {field}: Very short ({content_length} chars)")
                elif content_length < 50:
                    print(f"    ⚠️ {field}: Short ({content_length} chars)")
                elif content_length > 50000:
                    print(f"    ⚠️ {field}: Very long ({content_length} chars) - may hit LLM limits")
                else:
                    print(f"    ✅ {field}: Good length ({content_length} chars)")
                
                # Check for problematic characters
                if '\x00' in content:
                    print(f"    ❌ {field}: Contains null bytes")
                if len(content.encode('utf-8')) != content_length:
                    print(f"    ⚠️ {field}: Contains non-ASCII characters")
            else:
                print(f"    ❌ {field}: Missing or empty")
    
    def _check_for_empty_content(self, doc_data: dict):
        """Check for various types of empty or problematic content."""
        print(f"  General Data Issues:")
        
        issues_found = []
        
        for field_name, field_value in doc_data.items():
            if field_value is None:
                issues_found.append(f"Null value in {field_name}")
            elif isinstance(field_value, str):
                if field_value.strip() == "":
                    issues_found.append(f"Empty string in {field_name}")
                elif field_value.lower() in ['null', 'none', 'n/a', 'na', 'undefined']:
                    issues_found.append(f"Placeholder value in {field_name}: '{field_value}'")
            elif isinstance(field_value, list) and len(field_value) == 0:
                issues_found.append(f"Empty list in {field_name}")
            elif isinstance(field_value, dict) and len(field_value) == 0:
                issues_found.append(f"Empty dict in {field_name}")
        
        if issues_found:
            for issue in issues_found:
                print(f"    ⚠️ {issue}")
        else:
            print(f"    ✅ No obvious data issues found")
    
    def _save_document_analysis(self, collection_name: str, document_id: str, doc_data: dict):
        """Save the document analysis to a JSON file."""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"document_analysis_{collection_name}_{document_id}_{timestamp}.json"
        filepath = os.path.join(os.path.dirname(__file__), filename)
        
        # Prepare data for JSON serialization
        analysis_data = {
            'collection_name': collection_name,
            'document_id': document_id,
            'analysis_timestamp': timestamp,
            'analysis_date': datetime.now().isoformat(),
            'document_data': {}
        }
        
        # Convert document data to JSON-serializable format
        for field_name, field_value in doc_data.items():
            if hasattr(field_value, 'isoformat'):
                analysis_data['document_data'][field_name] = field_value.isoformat()
            elif isinstance(field_value, (str, int, float, bool, list, dict)):
                analysis_data['document_data'][field_name] = field_value
            else:
                analysis_data['document_data'][field_name] = str(field_value)
        
        try:
            with open(filepath, 'w', encoding='utf-8') as f:
                json.dump(analysis_data, f, indent=2, ensure_ascii=False)
            print(f"\n✓ Document analysis saved to: {filepath}")
        except Exception as e:
            print(f"\n✗ Error saving document analysis: {e}")


def main():
    """Main function."""
    if len(sys.argv) != 3:
        print("Usage: python examine_specific_document.py <collection_name> <document_id>")
        print("\nExamples:")
        print("  python examine_specific_document.py raw_legisinfo_bill_details 44-1_C-291")
        print("  python examine_specific_document.py raw_news_releases 20220208_CANADANEWS_392df614d701")
        sys.exit(1)
    
    collection_name = sys.argv[1]
    document_id = sys.argv[2]
    
    try:
        examiner = DocumentExaminer()
        examiner.examine_document(collection_name, document_id)
        
    except KeyboardInterrupt:
        print("\n\n⚠ Examination interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ Unexpected error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main() 