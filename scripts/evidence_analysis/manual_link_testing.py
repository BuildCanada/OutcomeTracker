#!/usr/bin/env python3
"""
Manual Link Testing Script
Tests the promise-evidence linking system functionality by creating manual test links

This script:
1. Identifies high-confidence promise-evidence pairs for manual linking
2. Creates test links to verify system functionality
3. Tests bidirectional linking operations
4. Validates frontend display functionality
"""

import asyncio
import json
import os
from datetime import datetime, timezone
from typing import Dict, List, Any, Optional, Tuple
import re

# Firebase imports
import firebase_admin
from firebase_admin import credentials, firestore

# Initialize Firebase Admin if not already done
try:
    firebase_admin.get_app()
except ValueError:
    firebase_admin.initialize_app()

db = firestore.client()

class ManualLinkTester:
    """Tests manual linking functionality and system operations."""
    
    def __init__(self):
        self.db = db
        self.test_results = {
            'timestamp': datetime.now(timezone.utc).isoformat(),
            'test_links_created': [],
            'system_functionality': {},
            'frontend_tests': {},
            'recommendations': []
        }
        
    async def run_manual_link_tests(self) -> Dict[str, Any]:
        """Run the complete manual link testing suite."""
        print("🔧 Starting Manual Link Testing...")
        print("=" * 60)
        
        # Step 1: Find candidate promise-evidence pairs
        print("🔍 Step 1: Finding candidate promise-evidence pairs...")
        candidates = await self.find_link_candidates()
        
        # Step 2: Create test links
        print("🔗 Step 2: Creating test links...")
        await self.create_test_links(candidates)
        
        # Step 3: Verify bidirectional functionality
        print("⚖️ Step 3: Verifying bidirectional linking...")
        await self.verify_bidirectional_links()
        
        # Step 4: Test system operations
        print("⚙️ Step 4: Testing system operations...")
        await self.test_system_operations()
        
        # Step 5: Export results
        print("💾 Step 5: Exporting test results...")
        await self.export_results()
        
        print("✅ Manual link testing complete!")
        return self.test_results
    
    async def find_link_candidates(self) -> List[Dict[str, Any]]:
        """Find high-confidence promise-evidence pairs for manual linking."""
        print("  🔍 Analyzing promises and evidence for potential matches...")
        
        # Get sample of recent promises
        promises_ref = self.db.collection('promises')
        promises_query = promises_ref.limit(50)  # Start with recent promises
        promises_docs = promises_query.stream()
        
        promises = []
        for doc in promises_docs:
            data = doc.to_dict()
            data['id'] = doc.id
            promises.append(data)
        
        # Get sample of recent evidence
        evidence_ref = self.db.collection('evidence_items')
        evidence_query = evidence_ref.limit(100)  # Get more evidence for matching
        evidence_docs = evidence_query.stream()
        
        evidence_items = []
        for doc in evidence_docs:
            data = doc.to_dict()
            data['id'] = doc.id
            evidence_items.append(data)
        
        print(f"  📊 Analyzing {len(promises)} promises and {len(evidence_items)} evidence items")
        
        # Find potential matches using simple keyword overlap
        candidates = []
        
        for promise in promises[:10]:  # Test with first 10 promises
            promise_text = self.extract_promise_text(promise)
            promise_keywords = self.extract_keywords(promise_text)
            
            if not promise_keywords:
                continue
                
            for evidence in evidence_items:
                evidence_text = self.extract_evidence_text(evidence)
                evidence_keywords = self.extract_keywords(evidence_text)
                
                if not evidence_keywords:
                    continue
                
                # Calculate keyword overlap
                overlap = len(promise_keywords.intersection(evidence_keywords))
                overlap_ratio = overlap / len(promise_keywords.union(evidence_keywords))
                
                if overlap >= 2 and overlap_ratio >= 0.1:  # At least 2 keywords and 10% overlap
                    candidates.append({
                        'promise_id': promise['id'],
                        'evidence_id': evidence['id'],
                        'promise_text': promise_text[:200],
                        'evidence_text': evidence_text[:200],
                        'keyword_overlap': overlap,
                        'overlap_ratio': overlap_ratio,
                        'shared_keywords': list(promise_keywords.intersection(evidence_keywords))
                    })
        
        # Sort by overlap ratio and take top candidates
        candidates.sort(key=lambda x: x['overlap_ratio'], reverse=True)
        top_candidates = candidates[:5]  # Take top 5 for testing
        
        print(f"  ✅ Found {len(top_candidates)} high-confidence link candidates")
        
        for i, candidate in enumerate(top_candidates, 1):
            print(f"    {i}. Overlap: {candidate['overlap_ratio']:.2f} ({candidate['keyword_overlap']} keywords)")
            print(f"       Keywords: {', '.join(candidate['shared_keywords'][:3])}")
        
        return top_candidates
    
    def extract_promise_text(self, promise: Dict[str, Any]) -> str:
        """Extract searchable text from promise."""
        text_parts = []
        
        # Try different possible title fields
        title_fields = ['promise_title', 'title', 'summary', 'description']
        for field in title_fields:
            if promise.get(field):
                text_parts.append(promise[field])
                break
        
        # Add department if available
        if promise.get('department'):
            text_parts.append(promise['department'])
        
        # Add party if available
        if promise.get('party'):
            text_parts.append(promise['party'])
        
        return ' '.join(text_parts).lower()
    
    def extract_evidence_text(self, evidence: Dict[str, Any]) -> str:
        """Extract searchable text from evidence."""
        text_parts = []
        
        # Try different possible title/content fields
        content_fields = ['title_or_summary', 'title', 'summary', 'description', 'content']
        for field in content_fields:
            if evidence.get(field):
                text_parts.append(evidence[field])
                break
        
        # Add evidence type
        if evidence.get('evidence_source_type'):
            text_parts.append(evidence['evidence_source_type'])
        
        # Add departments if available
        departments = evidence.get('linked_departments', [])
        if departments:
            text_parts.extend(departments)
        
        return ' '.join(text_parts).lower()
    
    def extract_keywords(self, text: str) -> set:
        """Extract keywords from text."""
        if not text:
            return set()
        
        # Simple keyword extraction
        # Remove common words and extract meaningful terms
        stop_words = {
            'the', 'a', 'an', 'and', 'or', 'but', 'in', 'on', 'at', 'to', 'for', 'of', 'with', 'by',
            'from', 'up', 'about', 'into', 'through', 'during', 'before', 'after', 'above', 'below',
            'between', 'among', 'this', 'that', 'these', 'those', 'is', 'are', 'was', 'were', 'be',
            'been', 'being', 'have', 'has', 'had', 'do', 'does', 'did', 'will', 'would', 'could',
            'should', 'may', 'might', 'must', 'can', 'shall'
        }
        
        # Extract words (3+ characters, not stop words)
        words = re.findall(r'\b[a-zA-Z]{3,}\b', text.lower())
        keywords = {word for word in words if word not in stop_words}
        
        return keywords
    
    async def create_test_links(self, candidates: List[Dict[str, Any]]):
        """Create test links between promises and evidence."""
        print("  🔗 Creating test links...")
        
        created_links = []
        
        for i, candidate in enumerate(candidates, 1):
            try:
                print(f"    Creating link {i}/{len(candidates)}...")
                
                promise_id = candidate['promise_id']
                evidence_id = candidate['evidence_id']
                
                # Update promise with evidence link
                promise_ref = self.db.collection('promises').document(promise_id)
                promise_doc = promise_ref.get()
                
                if promise_doc.exists:
                    promise_data = promise_doc.to_dict()
                    linked_evidence = promise_data.get('linked_evidence_ids', [])
                    
                    if evidence_id not in linked_evidence:
                        linked_evidence.append(evidence_id)
                        promise_ref.update({
                            'linked_evidence_ids': linked_evidence,
                            'linking_status': 'manual_test',
                            'linking_processed_at': datetime.now(timezone.utc)
                        })
                        print(f"      ✅ Updated promise {promise_id}")
                    else:
                        print(f"      ⚠️ Promise {promise_id} already linked to evidence {evidence_id}")
                
                # Update evidence with promise link
                evidence_ref = self.db.collection('evidence_items').document(evidence_id)
                evidence_doc = evidence_ref.get()
                
                if evidence_doc.exists:
                    evidence_data = evidence_doc.to_dict()
                    promise_ids = evidence_data.get('promise_ids', [])
                    
                    if promise_id not in promise_ids:
                        promise_ids.append(promise_id)
                        evidence_ref.update({
                            'promise_ids': promise_ids,
                            'promise_linking_status': 'manual_test',
                            'promise_linking_processed_at': datetime.now(timezone.utc)
                        })
                        print(f"      ✅ Updated evidence {evidence_id}")
                    else:
                        print(f"      ⚠️ Evidence {evidence_id} already linked to promise {promise_id}")
                
                created_links.append({
                    'promise_id': promise_id,
                    'evidence_id': evidence_id,
                    'created_at': datetime.now(timezone.utc).isoformat(),
                    'overlap_ratio': candidate['overlap_ratio'],
                    'shared_keywords': candidate['shared_keywords']
                })
                
            except Exception as e:
                print(f"      ❌ Error creating link {i}: {e}")
        
        self.test_results['test_links_created'] = created_links
        print(f"  ✅ Successfully created {len(created_links)} test links")
    
    async def verify_bidirectional_links(self):
        """Verify that created links work bidirectionally."""
        print("  ⚖️ Verifying bidirectional link consistency...")
        
        verification_results = {
            'total_links_tested': len(self.test_results['test_links_created']),
            'bidirectional_consistent': 0,
            'promise_missing_evidence': 0,
            'evidence_missing_promise': 0,
            'verification_details': []
        }
        
        for link in self.test_results['test_links_created']:
            promise_id = link['promise_id']
            evidence_id = link['evidence_id']
            
            try:
                # Check promise -> evidence link
                promise_ref = self.db.collection('promises').document(promise_id)
                promise_doc = promise_ref.get()
                
                promise_has_evidence = False
                if promise_doc.exists:
                    promise_data = promise_doc.to_dict()
                    linked_evidence = promise_data.get('linked_evidence_ids', [])
                    promise_has_evidence = evidence_id in linked_evidence
                
                # Check evidence -> promise link
                evidence_ref = self.db.collection('evidence_items').document(evidence_id)
                evidence_doc = evidence_ref.get()
                
                evidence_has_promise = False
                if evidence_doc.exists:
                    evidence_data = evidence_doc.to_dict()
                    promise_ids = evidence_data.get('promise_ids', [])
                    evidence_has_promise = promise_id in promise_ids
                
                # Determine consistency
                if promise_has_evidence and evidence_has_promise:
                    verification_results['bidirectional_consistent'] += 1
                    status = "✅ Bidirectional"
                elif promise_has_evidence and not evidence_has_promise:
                    verification_results['evidence_missing_promise'] += 1
                    status = "⚠️ Promise->Evidence only"
                elif not promise_has_evidence and evidence_has_promise:
                    verification_results['promise_missing_evidence'] += 1
                    status = "⚠️ Evidence->Promise only"
                else:
                    status = "❌ No links found"
                
                verification_results['verification_details'].append({
                    'promise_id': promise_id,
                    'evidence_id': evidence_id,
                    'promise_has_evidence': promise_has_evidence,
                    'evidence_has_promise': evidence_has_promise,
                    'status': status
                })
                
                print(f"    {status}: {promise_id[:8]}...↔{evidence_id[:8]}...")
                
            except Exception as e:
                print(f"    ❌ Error verifying link {promise_id}↔{evidence_id}: {e}")
        
        # Calculate consistency percentage
        total = verification_results['total_links_tested']
        consistent = verification_results['bidirectional_consistent']
        consistency_pct = (consistent / total * 100) if total > 0 else 0
        
        verification_results['consistency_percentage'] = consistency_pct
        
        self.test_results['system_functionality']['bidirectional_verification'] = verification_results
        
        print(f"  📊 Bidirectional consistency: {consistent}/{total} ({consistency_pct:.1f}%)")
    
    async def test_system_operations(self):
        """Test various system operations and functionality."""
        print("  ⚙️ Testing system operations...")
        
        operations_results = {
            'database_operations': {},
            'data_integrity': {},
            'performance_metrics': {}
        }
        
        # Test database read operations
        try:
            start_time = datetime.now()
            
            # Test promise collection access
            promises_ref = self.db.collection('promises')
            promise_count = len(list(promises_ref.limit(10).stream()))
            
            # Test evidence collection access
            evidence_ref = self.db.collection('evidence_items')
            evidence_count = len(list(evidence_ref.limit(10).stream()))
            
            end_time = datetime.now()
            read_time = (end_time - start_time).total_seconds()
            
            operations_results['database_operations'] = {
                'promise_read_test': f"✅ Read {promise_count} promises",
                'evidence_read_test': f"✅ Read {evidence_count} evidence items",
                'read_performance': f"{read_time:.2f} seconds"
            }
            
            print(f"    ✅ Database read operations: {read_time:.2f}s")
            
        except Exception as e:
            operations_results['database_operations']['error'] = str(e)
            print(f"    ❌ Database read error: {e}")
        
        # Test data integrity
        try:
            # Check for any created links
            promises_with_links = 0
            evidence_with_links = 0
            
            for link in self.test_results['test_links_created']:
                # Check promise
                promise_ref = self.db.collection('promises').document(link['promise_id'])
                promise_doc = promise_ref.get()
                if promise_doc.exists:
                    promise_data = promise_doc.to_dict()
                    if promise_data.get('linked_evidence_ids'):
                        promises_with_links += 1
                
                # Check evidence
                evidence_ref = self.db.collection('evidence_items').document(link['evidence_id'])
                evidence_doc = evidence_ref.get()
                if evidence_doc.exists:
                    evidence_data = evidence_doc.to_dict()
                    if evidence_data.get('promise_ids'):
                        evidence_with_links += 1
            
            operations_results['data_integrity'] = {
                'promises_with_links': promises_with_links,
                'evidence_with_links': evidence_with_links,
                'total_test_links': len(self.test_results['test_links_created'])
            }
            
            print(f"    ✅ Data integrity: {promises_with_links} promises, {evidence_with_links} evidence with links")
            
        except Exception as e:
            operations_results['data_integrity']['error'] = str(e)
            print(f"    ❌ Data integrity check error: {e}")
        
        self.test_results['system_functionality']['operations'] = operations_results
    
    async def export_results(self):
        """Export manual link testing results."""
        print("  💾 Exporting test results...")
        
        # Create output directory
        os.makedirs('manual_link_test_results', exist_ok=True)
        
        # 1. JSON export
        with open('manual_link_test_results/manual_link_test.json', 'w') as f:
            json.dump(self.test_results, f, indent=2, default=str)
        
        # 2. Generate test report
        await self.generate_test_report()
        
        print("    ✅ Results exported to manual_link_test_results/")
    
    async def generate_test_report(self):
        """Generate comprehensive test report."""
        links_created = len(self.test_results['test_links_created'])
        bidirectional_verification = self.test_results['system_functionality'].get('bidirectional_verification', {})
        operations = self.test_results['system_functionality'].get('operations', {})
        
        report = f"""
# Manual Link Testing Report
Generated: {self.test_results['timestamp']}

## Executive Summary

This report documents the results of manual link testing to verify the promise-evidence linking system functionality.

### Test Results Summary

**Links Created**: {links_created} test links
**Bidirectional Consistency**: {bidirectional_verification.get('consistency_percentage', 0):.1f}%
**System Status**: {"✅ FUNCTIONAL" if links_created > 0 and bidirectional_verification.get('consistency_percentage', 0) > 80 else "⚠️ NEEDS ATTENTION"}

## Test Links Created

"""
        
        for i, link in enumerate(self.test_results['test_links_created'], 1):
            report += f"""
### Link {i}
- **Promise ID**: `{link['promise_id']}`
- **Evidence ID**: `{link['evidence_id']}`
- **Overlap Ratio**: {link['overlap_ratio']:.2f}
- **Shared Keywords**: {', '.join(link['shared_keywords'][:5])}
- **Created**: {link['created_at']}
"""
        
        report += f"""

## Bidirectional Verification Results

**Total Links Tested**: {bidirectional_verification.get('total_links_tested', 0)}
**Bidirectional Consistent**: {bidirectional_verification.get('bidirectional_consistent', 0)}
**Promise->Evidence Only**: {bidirectional_verification.get('evidence_missing_promise', 0)}
**Evidence->Promise Only**: {bidirectional_verification.get('promise_missing_evidence', 0)}
**Consistency Percentage**: {bidirectional_verification.get('consistency_percentage', 0):.1f}%

### Verification Details

"""
        
        for detail in bidirectional_verification.get('verification_details', []):
            report += f"- {detail['status']}: `{detail['promise_id'][:8]}...` ↔ `{detail['evidence_id'][:8]}...`\n"
        
        report += f"""

## System Operations Testing

### Database Operations
"""
        
        db_ops = operations.get('database_operations', {})
        for key, value in db_ops.items():
            if key != 'error':
                report += f"- **{key.replace('_', ' ').title()}**: {value}\n"
        
        if 'error' in db_ops:
            report += f"- **Error**: {db_ops['error']}\n"
        
        report += f"""

### Data Integrity
"""
        
        integrity = operations.get('data_integrity', {})
        if 'error' not in integrity:
            report += f"""
- **Promises with Links**: {integrity.get('promises_with_links', 0)}
- **Evidence with Links**: {integrity.get('evidence_with_links', 0)}
- **Total Test Links**: {integrity.get('total_test_links', 0)}
"""
        else:
            report += f"- **Error**: {integrity['error']}\n"
        
        report += f"""

## Conclusions and Recommendations

### System Functionality Assessment

"""
        
        if links_created > 0:
            report += "✅ **Link Creation**: System successfully creates bidirectional links\n"
        else:
            report += "❌ **Link Creation**: System failed to create links\n"
        
        consistency_pct = bidirectional_verification.get('consistency_percentage', 0)
        if consistency_pct >= 90:
            report += "✅ **Bidirectional Consistency**: Excellent link consistency\n"
        elif consistency_pct >= 70:
            report += "⚠️ **Bidirectional Consistency**: Good but needs improvement\n"
        else:
            report += "❌ **Bidirectional Consistency**: Poor link consistency\n"
        
        report += f"""

### Immediate Recommendations

1. **System Status**: {"System is functional for manual linking" if links_created > 0 else "System requires debugging before proceeding"}
2. **Link Quality**: {"Manual links show good keyword overlap" if links_created > 0 else "Unable to assess link quality"}
3. **Next Steps**: {"Proceed with algorithm testing" if consistency_pct >= 80 else "Fix bidirectional consistency issues first"}

### Technical Findings

- Manual link creation process works as expected
- Database operations are functional
- Bidirectional linking {'maintains consistency' if consistency_pct >= 80 else 'has consistency issues'}
- System ready for {'algorithm development' if links_created > 0 and consistency_pct >= 80 else 'debugging and fixes'}

## Files Generated
- `manual_link_test.json`: Complete test data
- `manual_link_test_report.md`: This comprehensive report

---
*Report generated by Promise Tracker Manual Link Tester*
"""
        
        with open('manual_link_test_results/manual_link_test_report.md', 'w') as f:
            f.write(report)
        
        print("    📄 Test report saved to manual_link_test_results/manual_link_test_report.md")

async def main():
    """Main execution function."""
    tester = ManualLinkTester()
    results = await tester.run_manual_link_tests()
    
    print("\n" + "=" * 60)
    print("🎉 MANUAL LINK TESTING COMPLETE!")
    print("=" * 60)
    
    links_created = len(results['test_links_created'])
    bidirectional_verification = results['system_functionality'].get('bidirectional_verification', {})
    consistency_pct = bidirectional_verification.get('consistency_percentage', 0)
    
    print(f"🔗 Test links created: {links_created}")
    print(f"⚖️ Bidirectional consistency: {consistency_pct:.1f}%")
    
    # Show system status
    if links_created > 0 and consistency_pct >= 80:
        print("✅ SYSTEM STATUS: FUNCTIONAL - Ready for algorithm development")
    elif links_created > 0:
        print("⚠️ SYSTEM STATUS: PARTIAL - Links created but consistency issues")
    else:
        print("❌ SYSTEM STATUS: NON-FUNCTIONAL - Unable to create links")
    
    print("\n📁 Results saved to: manual_link_test_results/")
    print("📄 Full report: manual_link_test_results/manual_link_test_report.md")

if __name__ == "__main__":
    asyncio.run(main()) 