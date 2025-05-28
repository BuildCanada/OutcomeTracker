#!/usr/bin/env python3
"""
Check Raw Collections Status Script

This script checks all raw collections for unprocessed items and errors
before proceeding with the migration from test to production collections.

Collections checked:
1. raw_gazette_p2_notices (from ingest_canada_gazette_p2.py -> process_gazette_p2_to_evidence.py)
2. raw_legisinfo_bill_details (from ingest_legisinfo_bills.py -> process_legisinfo_to_evidence.py)
3. raw_news_releases (from ingest_canada_news.py -> process_news_to_evidence.py)
4. raw_orders_in_council (from ingest_oic.py -> process_oic_to_evidence.py)

Usage:
    python check_raw_collections_status.py [--detailed] [--show-samples]
"""

import os
import sys
import json
from datetime import datetime, timezone
from typing import Dict, List, Any
from collections import defaultdict

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
    print("Make sure you have firebase-admin and python-dotenv installed")
    sys.exit(1)


class RawCollectionsStatusChecker:
    """Checks the status of all raw collections for unprocessed items and errors."""
    
    def __init__(self):
        """Initialize the status checker."""
        self.db = self._init_firebase()
        self.timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        
        # Define collections and their expected status fields
        self.collections_config = {
            'raw_gazette_p2_notices': {
                'status_field': 'evidence_processing_status',
                'ingestion_script': 'ingest_canada_gazette_p2.py',
                'processing_script': 'process_gazette_p2_to_evidence.py',
                'expected_statuses': [
                    'pending_evidence_creation',
                    'evidence_created',
                    'skipped_low_relevance_score',
                    'llm_processing_failed',
                    'processing_error'
                ]
            },
            'raw_legisinfo_bill_details': {
                'status_field': 'processing_status',
                'ingestion_script': 'ingest_legisinfo_bills.py',
                'processing_script': 'process_legisinfo_to_evidence.py',
                'expected_statuses': [
                    'pending_processing',
                    'processed',
                    'error_llm_processing',
                    'error_processing_script'
                ]
            },
            'raw_news_releases': {
                'status_field': 'evidence_processing_status',
                'ingestion_script': 'ingest_canada_news.py',
                'processing_script': 'process_news_to_evidence.py',
                'expected_statuses': [
                    'pending_evidence_creation',
                    'evidence_created',
                    'skipped_low_relevance_score',
                    'error_llm_processing',
                    'error_missing_fields',
                    'error_processing_script'
                ]
            },
            'raw_orders_in_council': {
                'status_field': 'evidence_processing_status',
                'ingestion_script': 'ingest_oic.py',
                'processing_script': 'process_oic_to_evidence.py',
                'expected_statuses': [
                    'pending_evidence_creation',
                    'evidence_created',
                    'skipped_low_relevance_score',
                    'error_llm_processing',
                    'error_processing_script'
                ]
            }
        }
        
        self.status_report = {
            'check_timestamp': self.timestamp,
            'check_date': datetime.now().isoformat(),
            'collections_status': {},
            'overall_summary': {},
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
    
    def count_documents_by_status(self, collection_name: str, status_field: str) -> Dict[str, int]:
        """Count documents by status in a collection."""
        status_counts = defaultdict(int)
        total_count = 0
        
        try:
            docs = self.db.collection(collection_name).stream()
            
            for doc in docs:
                total_count += 1
                doc_data = doc.to_dict()
                status = doc_data.get(status_field, 'missing_status_field')
                status_counts[status] += 1
            
            # Add total count
            status_counts['_total'] = total_count
            
        except Exception as e:
            print(f"Error counting documents in {collection_name}: {e}")
            status_counts['_error'] = str(e)
        
        return dict(status_counts)
    
    def get_sample_documents(self, collection_name: str, status_field: str, status_value: str, limit: int = 3) -> List[Dict]:
        """Get sample documents with a specific status."""
        samples = []
        
        try:
            if status_value == 'missing_status_field':
                # Query for documents where the status field doesn't exist
                docs = self.db.collection(collection_name).limit(limit * 2).stream()
                for doc in docs:
                    doc_data = doc.to_dict()
                    if status_field not in doc_data:
                        samples.append({
                            'id': doc.id,
                            'data': {k: (v.isoformat() if isinstance(v, datetime) else str(v)[:100]) 
                                   for k, v in doc_data.items() if k in ['title_raw', 'regulation_title', 'bill_number_code_feed', 'oic_number', 'ingested_at', 'publication_date']}
                        })
                        if len(samples) >= limit:
                            break
            else:
                # Query for documents with specific status
                query = self.db.collection(collection_name).where(status_field, '==', status_value).limit(limit)
                docs = query.stream()
                
                for doc in docs:
                    doc_data = doc.to_dict()
                    samples.append({
                        'id': doc.id,
                        'data': {k: (v.isoformat() if isinstance(v, datetime) else str(v)[:100]) 
                               for k, v in doc_data.items() if k in ['title_raw', 'regulation_title', 'bill_number_code_feed', 'oic_number', 'ingested_at', 'publication_date', 'processing_error_message']}
                    })
        
        except Exception as e:
            print(f"Error getting samples from {collection_name} with status {status_value}: {e}")
        
        return samples
    
    def analyze_collection_status(self, collection_name: str, config: Dict, show_samples: bool = False) -> Dict[str, Any]:
        """Analyze the status of a single collection."""
        print(f"\nAnalyzing collection: {collection_name}")
        
        status_field = config['status_field']
        status_counts = self.count_documents_by_status(collection_name, status_field)
        
        if '_error' in status_counts:
            return {
                'collection_name': collection_name,
                'error': status_counts['_error'],
                'status': 'error'
            }
        
        total_docs = status_counts.get('_total', 0)
        print(f"  Total documents: {total_docs}")
        
        if total_docs == 0:
            return {
                'collection_name': collection_name,
                'total_documents': 0,
                'status_breakdown': {},
                'issues': [],
                'status': 'empty'
            }
        
        # Remove total from status breakdown
        status_breakdown = {k: v for k, v in status_counts.items() if k != '_total'}
        
        # Identify issues
        issues = []
        samples = {}
        
        # Check for unprocessed items
        unprocessed_statuses = ['pending_evidence_creation', 'pending_processing']
        unprocessed_count = sum(status_breakdown.get(status, 0) for status in unprocessed_statuses)
        
        if unprocessed_count > 0:
            issues.append(f"{unprocessed_count} unprocessed items")
            if show_samples:
                for status in unprocessed_statuses:
                    if status_breakdown.get(status, 0) > 0:
                        samples[status] = self.get_sample_documents(collection_name, status_field, status)
        
        # Check for error statuses
        error_statuses = [status for status in status_breakdown.keys() 
                         if 'error' in status.lower() or 'failed' in status.lower()]
        error_count = sum(status_breakdown.get(status, 0) for status in error_statuses)
        
        if error_count > 0:
            issues.append(f"{error_count} items with errors")
            if show_samples:
                for status in error_statuses:
                    if status_breakdown.get(status, 0) > 0:
                        samples[status] = self.get_sample_documents(collection_name, status_field, status)
        
        # Check for missing status field
        missing_status_count = status_breakdown.get('missing_status_field', 0)
        if missing_status_count > 0:
            issues.append(f"{missing_status_count} items missing status field")
            if show_samples:
                samples['missing_status_field'] = self.get_sample_documents(collection_name, status_field, 'missing_status_field')
        
        # Check for unexpected statuses
        expected_statuses = set(config['expected_statuses'] + ['missing_status_field'])
        unexpected_statuses = set(status_breakdown.keys()) - expected_statuses
        if unexpected_statuses:
            issues.append(f"Unexpected statuses found: {list(unexpected_statuses)}")
            if show_samples:
                for status in unexpected_statuses:
                    samples[status] = self.get_sample_documents(collection_name, status_field, status)
        
        # Determine overall status
        if error_count > 0 or missing_status_count > 0 or unexpected_statuses:
            overall_status = 'has_issues'
        elif unprocessed_count > 0:
            overall_status = 'has_unprocessed'
        else:
            overall_status = 'healthy'
        
        result = {
            'collection_name': collection_name,
            'total_documents': total_docs,
            'status_breakdown': status_breakdown,
            'unprocessed_count': unprocessed_count,
            'error_count': error_count,
            'issues': issues,
            'status': overall_status,
            'ingestion_script': config['ingestion_script'],
            'processing_script': config['processing_script']
        }
        
        if show_samples and samples:
            result['sample_documents'] = samples
        
        return result
    
    def generate_recommendations(self, collections_analysis: Dict[str, Any]) -> List[str]:
        """Generate recommendations based on the analysis."""
        recommendations = []
        
        total_unprocessed = 0
        total_errors = 0
        collections_with_issues = []
        
        for collection_name, analysis in collections_analysis.items():
            if analysis.get('status') == 'error':
                recommendations.append(f"❌ {collection_name}: Collection access error - {analysis.get('error')}")
                continue
            
            if analysis.get('status') == 'empty':
                recommendations.append(f"ℹ️ {collection_name}: Collection is empty - this may be expected")
                continue
            
            unprocessed = analysis.get('unprocessed_count', 0)
            errors = analysis.get('error_count', 0)
            
            total_unprocessed += unprocessed
            total_errors += errors
            
            if analysis.get('status') in ['has_issues', 'has_unprocessed']:
                collections_with_issues.append(collection_name)
                
                if unprocessed > 0:
                    recommendations.append(
                        f"⚠️ {collection_name}: {unprocessed} unprocessed items - "
                        f"run {analysis.get('processing_script')} to process them"
                    )
                
                if errors > 0:
                    recommendations.append(
                        f"🔧 {collection_name}: {errors} items with errors - "
                        f"investigate and potentially reprocess with --force_reprocessing"
                    )
                
                issues = analysis.get('issues', [])
                for issue in issues:
                    if 'missing status field' in issue or 'Unexpected statuses' in issue:
                        recommendations.append(
                            f"🔍 {collection_name}: {issue} - may need data cleanup or script updates"
                        )
        
        # Overall recommendations
        if total_unprocessed == 0 and total_errors == 0 and not collections_with_issues:
            recommendations.insert(0, "✅ All raw collections are healthy - ready for migration!")
        else:
            recommendations.insert(0, f"⚠️ Found issues in {len(collections_with_issues)} collections before migration")
            
            if total_unprocessed > 0:
                recommendations.append(f"📊 Total unprocessed items across all collections: {total_unprocessed}")
            
            if total_errors > 0:
                recommendations.append(f"🚨 Total error items across all collections: {total_errors}")
            
            recommendations.append("🎯 Recommendation: Address these issues before proceeding with migration")
        
        return recommendations
    
    def run_status_check(self, detailed: bool = False, show_samples: bool = False) -> bool:
        """
        Run the complete status check.
        
        Args:
            detailed: If True, show detailed breakdown
            show_samples: If True, include sample documents
            
        Returns:
            True if all collections are healthy, False if issues found
        """
        print(f"{'='*60}")
        print(f"RAW COLLECTIONS STATUS CHECK")
        print(f"Timestamp: {self.timestamp}")
        print(f"{'='*60}")
        
        all_healthy = True
        collections_analysis = {}
        
        for collection_name, config in self.collections_config.items():
            analysis = self.analyze_collection_status(collection_name, config, show_samples)
            collections_analysis[collection_name] = analysis
            
            if analysis.get('status') not in ['healthy', 'empty']:
                all_healthy = False
            
            # Print summary for each collection
            total_docs = analysis.get('total_documents', 0)
            status = analysis.get('status', 'unknown')
            
            if status == 'error':
                print(f"  ❌ Error accessing collection")
            elif status == 'empty':
                print(f"  ℹ️ Collection is empty")
            elif status == 'healthy':
                print(f"  ✅ All {total_docs} documents processed successfully")
            else:
                issues = analysis.get('issues', [])
                print(f"  ⚠️ {total_docs} total documents, issues: {', '.join(issues)}")
            
            if detailed and analysis.get('status_breakdown'):
                print(f"    Status breakdown:")
                for status_name, count in analysis['status_breakdown'].items():
                    print(f"      - {status_name}: {count}")
        
        # Store analysis in report
        self.status_report['collections_status'] = collections_analysis
        
        # Generate recommendations
        recommendations = self.generate_recommendations(collections_analysis)
        self.status_report['recommendations'] = recommendations
        
        # Print recommendations
        print(f"\n{'='*60}")
        print("RECOMMENDATIONS")
        print(f"{'='*60}")
        
        for rec in recommendations:
            print(rec)
        
        # Print sample documents if requested
        if show_samples:
            print(f"\n{'='*60}")
            print("SAMPLE DOCUMENTS")
            print(f"{'='*60}")
            
            for collection_name, analysis in collections_analysis.items():
                samples = analysis.get('sample_documents', {})
                if samples:
                    print(f"\n{collection_name}:")
                    for status, docs in samples.items():
                        if docs:
                            print(f"  {status} (showing {len(docs)} samples):")
                            for doc in docs:
                                print(f"    - ID: {doc['id']}")
                                for key, value in doc['data'].items():
                                    print(f"      {key}: {value}")
        
        # Overall summary
        total_collections = len(self.collections_config)
        healthy_collections = sum(1 for a in collections_analysis.values() if a.get('status') == 'healthy')
        
        self.status_report['overall_summary'] = {
            'total_collections_checked': total_collections,
            'healthy_collections': healthy_collections,
            'collections_with_issues': total_collections - healthy_collections,
            'ready_for_migration': all_healthy
        }
        
        print(f"\n{'='*60}")
        print("OVERALL STATUS")
        print(f"{'='*60}")
        print(f"Collections checked: {total_collections}")
        print(f"Healthy collections: {healthy_collections}")
        print(f"Collections with issues: {total_collections - healthy_collections}")
        print(f"Ready for migration: {'YES' if all_healthy else 'NO'}")
        
        return all_healthy
    
    def save_status_report(self):
        """Save the status report to a JSON file."""
        report_filename = f"raw_collections_status_report_{self.timestamp}.json"
        report_path = os.path.join(
            os.path.dirname(__file__), 
            report_filename
        )
        
        try:
            with open(report_path, 'w') as f:
                json.dump(self.status_report, f, indent=2)
            print(f"\n✓ Status report saved to: {report_path}")
        except Exception as e:
            print(f"\n✗ Error saving status report: {e}")


def main():
    """Main function."""
    import argparse
    
    parser = argparse.ArgumentParser(description='Check raw collections status before migration')
    parser.add_argument('--detailed', action='store_true', 
                       help='Show detailed status breakdown for each collection')
    parser.add_argument('--show-samples', action='store_true',
                       help='Show sample documents for problematic statuses')
    
    args = parser.parse_args()
    
    try:
        checker = RawCollectionsStatusChecker()
        all_healthy = checker.run_status_check(detailed=args.detailed, show_samples=args.show_samples)
        checker.save_status_report()
        
        if all_healthy:
            print(f"\n🎉 All raw collections are healthy and ready for migration!")
            sys.exit(0)
        else:
            print(f"\n⚠️ Issues found in raw collections. Address these before migration.")
            sys.exit(1)
            
    except KeyboardInterrupt:
        print("\n\n⚠ Status check interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ Unexpected error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main() 