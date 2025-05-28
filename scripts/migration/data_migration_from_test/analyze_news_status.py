#!/usr/bin/env python3
"""
Analyze News Status Script

This script provides a detailed breakdown of evidence_processing_status 
values in the raw_news_releases collection.

Usage:
    python analyze_news_status.py [--show-samples]
"""

import os
import sys
from datetime import datetime
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
    sys.exit(1)


class NewsStatusAnalyzer:
    """Analyzes the status of news releases."""
    
    def __init__(self):
        """Initialize the analyzer."""
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
    
    def analyze_news_status(self, show_samples=False):
        """Analyze the status breakdown of news releases."""
        print(f"{'='*60}")
        print(f"NEWS RELEASES STATUS ANALYSIS")
        print(f"Collection: raw_news_releases")
        print(f"{'='*60}")
        
        try:
            # Get all documents
            collection_ref = self.db.collection('raw_news_releases')
            docs = list(collection_ref.stream())
            
            print(f"\n📊 Total Documents: {len(docs)}")
            
            # Count by status
            status_counts = defaultdict(int)
            status_samples = defaultdict(list)
            missing_status_count = 0
            
            for doc in docs:
                doc_data = doc.to_dict()
                status = doc_data.get('evidence_processing_status')
                
                if status is None:
                    missing_status_count += 1
                    status = '[MISSING_STATUS]'
                
                status_counts[status] += 1
                
                # Collect samples if requested
                if show_samples and len(status_samples[status]) < 3:
                    sample_info = {
                        'id': doc.id,
                        'title': doc_data.get('title_raw', '')[:50] + '...' if doc_data.get('title_raw') else '[No Title]',
                        'publication_date': doc_data.get('publication_date'),
                        'ingested_at': doc_data.get('ingested_at'),
                        'source_url': doc_data.get('source_url', '')[:80] + '...' if doc_data.get('source_url') else '[No URL]'
                    }
                    status_samples[status].append(sample_info)
            
            # Display status breakdown
            print(f"\n📋 Status Breakdown:")
            print(f"{'Status':<35} {'Count':<8} {'Percentage':<12}")
            print(f"{'-'*55}")
            
            # Sort by count (descending)
            sorted_statuses = sorted(status_counts.items(), key=lambda x: x[1], reverse=True)
            
            for status, count in sorted_statuses:
                percentage = (count / len(docs)) * 100
                print(f"{status:<35} {count:<8} {percentage:>8.1f}%")
            
            # Show samples if requested
            if show_samples:
                print(f"\n📝 Sample Documents by Status:")
                for status, samples in status_samples.items():
                    if samples:
                        print(f"\n  {status} (showing {len(samples)} samples):")
                        for sample in samples:
                            print(f"    - ID: {sample['id']}")
                            print(f"      Title: {sample['title']}")
                            if sample['publication_date']:
                                pub_date = sample['publication_date']
                                if hasattr(pub_date, 'isoformat'):
                                    print(f"      Publication Date: {pub_date.isoformat()}")
                                else:
                                    print(f"      Publication Date: {pub_date}")
                            if sample['ingested_at']:
                                ing_date = sample['ingested_at']
                                if hasattr(ing_date, 'isoformat'):
                                    print(f"      Ingested At: {ing_date.isoformat()}")
                                else:
                                    print(f"      Ingested At: {ing_date}")
                            print(f"      Source: {sample['source_url']}")
                            print()
            
            # Analysis and recommendations
            print(f"\n🔍 Analysis:")
            
            pending_count = status_counts.get('pending_evidence_creation', 0)
            created_count = status_counts.get('evidence_created', 0)
            skipped_count = status_counts.get('skipped_low_relevance_score', 0)
            error_count = sum(count for status, count in status_counts.items() if 'error' in status.lower())
            
            print(f"  ✅ Successfully processed: {created_count}")
            print(f"  ⚠️ Skipped (low relevance): {skipped_count}")
            print(f"  🔄 Pending processing: {pending_count}")
            print(f"  ❌ Errors: {error_count}")
            print(f"  ❓ Missing status field: {missing_status_count}")
            
            total_processed = created_count + skipped_count + error_count
            processing_rate = (total_processed / len(docs)) * 100 if len(docs) > 0 else 0
            
            print(f"\n📈 Processing Progress:")
            print(f"  Total processed: {total_processed} / {len(docs)} ({processing_rate:.1f}%)")
            print(f"  Remaining to process: {pending_count}")
            
            if pending_count > 0:
                print(f"\n💡 Recommendation:")
                print(f"  Run: python process_news_to_evidence.py --limit 100")
                print(f"  This will process the next 100 pending news releases.")
            
        except Exception as e:
            print(f"❌ Error analyzing news status: {e}")


def main():
    """Main function."""
    import argparse
    
    parser = argparse.ArgumentParser(description="Analyze news releases status breakdown")
    parser.add_argument("--show-samples", action="store_true", help="Show sample documents for each status")
    args = parser.parse_args()
    
    try:
        analyzer = NewsStatusAnalyzer()
        analyzer.analyze_news_status(show_samples=args.show_samples)
        
    except KeyboardInterrupt:
        print("\n\n⚠ Analysis interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ Unexpected error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main() 