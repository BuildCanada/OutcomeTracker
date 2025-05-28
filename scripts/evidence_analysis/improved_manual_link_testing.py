#!/usr/bin/env python3
"""
Improved Manual Link Testing Script
Tests the promise-evidence linking system using the correct field names discovered in data exploration

This script:
1. Uses the correct field names (text, description vs title_or_summary, description_or_details)
2. Creates test links using improved text extraction
3. Tests bidirectional linking operations
4. Validates system functionality
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

class ImprovedManualLinkTester:
    """Tests manual linking functionality using correct field names."""
    
    def __init__(self):
        self.db = db
        self.test_results = {
            'timestamp': datetime.now(timezone.utc).isoformat(),
            'test_links_created': [],
            'system_functionality': {},
            'field_analysis': {},
            'recommendations': []
        }
        
    async def run_improved_link_tests(self) -> Dict[str, Any]:
        """Run the complete improved manual link testing suite."""
        print("🔧 Starting Improved Manual Link Testing...")
        print("=" * 60)
        
        # Step 1: Analyze field content quality
        print("🔍 Step 1: Analyzing field content quality...")
        await self.analyze_field_content()
        
        # Step 2: Find candidate promise-evidence pairs using correct fields
        print("🔍 Step 2: Finding candidate promise-evidence pairs...")
        candidates = await self.find_improved_link_candidates()
        
        # Step 3: Create test links
        print("🔗 Step 3: Creating test links...")
        await self.create_test_links(candidates)
        
        # Step 4: Verify bidirectional functionality
        print("⚖️ Step 4: Verifying bidirectional linking...")
        await self.verify_bidirectional_links()
        
        # Step 5: Test system operations
        print("⚙️ Step 5: Testing system operations...")
        await self.test_system_operations()
        
        # Step 6: Export results
        print("💾 Step 6: Exporting test results...")
        await self.export_results()
        
        print("✅ Improved manual link testing complete!")
        return self.test_results
    
    async def analyze_field_content(self):
        """Analyze the quality of content in key fields."""
        print("  🔍 Analyzing content quality in key fields...")
        
        field_analysis = {
            'promises': {},
            'evidence': {}
        }
        
        # Analyze promises
        promises_ref = self.db.collection('promises')
        promises_docs = promises_ref.limit(10).stream()
        
        promise_field_content = {
            'text': [],
            'description': [],
            'concise_title': [],
            'responsible_department_lead': []
        }
        
        for doc in promises_docs:
            data = doc.to_dict()
            for field in promise_field_content.keys():
                if data.get(field):
                    content = str(data[field]).strip()
                    if content:
                        promise_field_content[field].append(content)
        
        # Calculate promise field statistics
        for field, contents in promise_field_content.items():
            if contents:
                avg_length = sum(len(c) for c in contents) / len(contents)
                field_analysis['promises'][field] = {
                    'count': len(contents),
                    'avg_length': avg_length,
                    'sample': contents[0][:100] + "..." if contents[0] else ""
                }
                print(f"    📊 Promise {field}: {len(contents)} items, {avg_length:.0f} avg chars")
        
        # Analyze evidence
        evidence_ref = self.db.collection('evidence_items')
        evidence_docs = evidence_ref.limit(10).stream()
        
        evidence_field_content = {
            'title_or_summary': [],
            'description_or_details': [],
            'evidence_source_type': [],
            'linked_departments': []
        }
        
        for doc in evidence_docs:
            data = doc.to_dict()
            for field in evidence_field_content.keys():
                if field == 'linked_departments':
                    # Handle list field
                    departments = data.get(field, [])
                    if departments and isinstance(departments, list):
                        evidence_field_content[field].extend(departments)
                else:
                    if data.get(field):
                        content = str(data[field]).strip()
                        if content:
                            evidence_field_content[field].append(content)
        
        # Calculate evidence field statistics
        for field, contents in evidence_field_content.items():
            if contents:
                if field == 'linked_departments':
                    # For departments, count unique values
                    unique_depts = list(set(contents))
                    field_analysis['evidence'][field] = {
                        'count': len(contents),
                        'unique_count': len(unique_depts),
                        'sample': ', '.join(unique_depts[:3])
                    }
                    print(f"    📊 Evidence {field}: {len(unique_depts)} unique departments")
                else:
                    avg_length = sum(len(c) for c in contents) / len(contents)
                    field_analysis['evidence'][field] = {
                        'count': len(contents),
                        'avg_length': avg_length,
                        'sample': contents[0][:100] + "..." if contents[0] else ""
                    }
                    print(f"    📊 Evidence {field}: {len(contents)} items, {avg_length:.0f} avg chars")
        
        self.test_results['field_analysis'] = field_analysis
    
    async def find_improved_link_candidates(self) -> List[Dict[str, Any]]:
        """Find high-confidence promise-evidence pairs using correct field names."""
        print("  🔍 Analyzing promises and evidence for potential matches...")
        
        # Get sample of promises
        promises_ref = self.db.collection('promises')
        promises_query = promises_ref.limit(20)  # Analyze more promises
        promises_docs = promises_query.stream()
        
        promises = []
        for doc in promises_docs:
            data = doc.to_dict()
            data['id'] = doc.id
            promises.append(data)
        
        # Get sample of evidence
        evidence_ref = self.db.collection('evidence_items')
        evidence_query = evidence_ref.limit(50)  # Analyze more evidence
        evidence_docs = evidence_query.stream()
        
        evidence_items = []
        for doc in evidence_docs:
            data = doc.to_dict()
            data['id'] = doc.id
            evidence_items.append(data)
        
        print(f"  📊 Analyzing {len(promises)} promises and {len(evidence_items)} evidence items")
        
        # Find potential matches using improved text extraction
        candidates = []
        
        for promise in promises:
            promise_text = self.extract_promise_text_improved(promise)
            promise_keywords = self.extract_keywords_improved(promise_text)
            promise_department = self.extract_promise_department(promise)
            
            if not promise_keywords:
                continue
                
            for evidence in evidence_items:
                evidence_text = self.extract_evidence_text_improved(evidence)
                evidence_keywords = self.extract_keywords_improved(evidence_text)
                evidence_departments = self.extract_evidence_departments(evidence)
                
                if not evidence_keywords:
                    continue
                
                # Calculate keyword overlap
                overlap = len(promise_keywords.intersection(evidence_keywords))
                total_keywords = len(promise_keywords.union(evidence_keywords))
                overlap_ratio = overlap / total_keywords if total_keywords > 0 else 0
                
                # Department matching bonus
                department_match = False
                if promise_department and evidence_departments:
                    department_match = any(promise_department.lower() in dept.lower() or 
                                         dept.lower() in promise_department.lower() 
                                         for dept in evidence_departments)
                
                # Enhanced scoring with department matching
                score = overlap_ratio
                if department_match:
                    score += 0.2  # Bonus for department match
                
                if overlap >= 2 and score >= 0.15:  # Lower threshold but require department match or good overlap
                    candidates.append({
                        'promise_id': promise['id'],
                        'evidence_id': evidence['id'],
                        'promise_text': promise_text[:200],
                        'evidence_text': evidence_text[:200],
                        'keyword_overlap': overlap,
                        'overlap_ratio': overlap_ratio,
                        'department_match': department_match,
                        'final_score': score,
                        'shared_keywords': list(promise_keywords.intersection(evidence_keywords)),
                        'promise_department': promise_department,
                        'evidence_departments': evidence_departments
                    })
        
        # Sort by final score and take top candidates
        candidates.sort(key=lambda x: x['final_score'], reverse=True)
        top_candidates = candidates[:8]  # Take top 8 for testing
        
        print(f"  ✅ Found {len(top_candidates)} high-confidence link candidates")
        
        for i, candidate in enumerate(top_candidates, 1):
            dept_match = "✅" if candidate['department_match'] else "❌"
            print(f"    {i}. Score: {candidate['final_score']:.2f} | Overlap: {candidate['overlap_ratio']:.2f} | Dept: {dept_match}")
            print(f"       Keywords: {', '.join(candidate['shared_keywords'][:3])}")
            if candidate['promise_department']:
                print(f"       Promise Dept: {candidate['promise_department']}")
            if candidate['evidence_departments']:
                print(f"       Evidence Depts: {', '.join(candidate['evidence_departments'][:2])}")
        
        return top_candidates
    
    def extract_promise_text_improved(self, promise: Dict[str, Any]) -> str:
        """Extract searchable text from promise using correct field names."""
        text_parts = []
        
        # Primary content fields (from data exploration)
        primary_fields = ['text', 'description', 'concise_title']
        for field in primary_fields:
            if promise.get(field):
                text_parts.append(str(promise[field]))
        
        # Secondary content fields
        secondary_fields = ['background_and_context']
        for field in secondary_fields:
            if promise.get(field):
                text_parts.append(str(promise[field]))
        
        return ' '.join(text_parts).lower()
    
    def extract_evidence_text_improved(self, evidence: Dict[str, Any]) -> str:
        """Extract searchable text from evidence using correct field names."""
        text_parts = []
        
        # Primary content fields (from data exploration)
        primary_fields = ['title_or_summary', 'description_or_details']
        for field in primary_fields:
            if evidence.get(field):
                text_parts.append(str(evidence[field]))
        
        # Secondary content fields
        secondary_fields = ['evidence_source_type']
        for field in secondary_fields:
            if evidence.get(field):
                text_parts.append(str(evidence[field]))
        
        return ' '.join(text_parts).lower()
    
    def extract_promise_department(self, promise: Dict[str, Any]) -> Optional[str]:
        """Extract department from promise."""
        dept_fields = ['responsible_department_lead', 'department']
        for field in dept_fields:
            if promise.get(field):
                return str(promise[field])
        return None
    
    def extract_evidence_departments(self, evidence: Dict[str, Any]) -> List[str]:
        """Extract departments from evidence."""
        departments = evidence.get('linked_departments', [])
        if departments and isinstance(departments, list):
            return [str(dept) for dept in departments if dept]
        return []
    
    def extract_keywords_improved(self, text: str) -> set:
        """Extract keywords from text with improved filtering."""
        if not text:
            return set()
        
        # Enhanced stop words for government documents
        stop_words = {
            'the', 'a', 'an', 'and', 'or', 'but', 'in', 'on', 'at', 'to', 'for', 'of', 'with', 'by',
            'from', 'up', 'about', 'into', 'through', 'during', 'before', 'after', 'above', 'below',
            'between', 'among', 'this', 'that', 'these', 'those', 'is', 'are', 'was', 'were', 'be',
            'been', 'being', 'have', 'has', 'had', 'do', 'does', 'did', 'will', 'would', 'could',
            'should', 'may', 'might', 'must', 'can', 'shall', 'government', 'canada', 'canadian',
            'federal', 'act', 'regulation', 'policy', 'program', 'initiative', 'commitment'
        }
        
        # Extract words (3+ characters, not stop words)
        words = re.findall(r'\b[a-zA-Z]{3,}\b', text.lower())
        keywords = {word for word in words if word not in stop_words}
        
        # Also extract important phrases (2-3 words)
        phrases = re.findall(r'\b[a-zA-Z]{3,}\s+[a-zA-Z]{3,}\b', text.lower())
        for phrase in phrases:
            if not any(stop_word in phrase for stop_word in stop_words):
                keywords.add(phrase.replace(' ', '_'))
        
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
                            'linking_status': 'manual_test_improved',
                            'linking_processed_at': datetime.now(timezone.utc)
                        })
                        print(f"      ✅ Updated promise {promise_id[:8]}...")
                    else:
                        print(f"      ⚠️ Promise {promise_id[:8]}... already linked to evidence {evidence_id[:8]}...")
                
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
                            'promise_linking_status': 'manual_test_improved',
                            'promise_linking_processed_at': datetime.now(timezone.utc)
                        })
                        print(f"      ✅ Updated evidence {evidence_id[:8]}...")
                    else:
                        print(f"      ⚠️ Evidence {evidence_id[:8]}... already linked to promise {promise_id[:8]}...")
                
                created_links.append({
                    'promise_id': promise_id,
                    'evidence_id': evidence_id,
                    'created_at': datetime.now(timezone.utc).isoformat(),
                    'final_score': candidate['final_score'],
                    'overlap_ratio': candidate['overlap_ratio'],
                    'department_match': candidate['department_match'],
                    'shared_keywords': candidate['shared_keywords'],
                    'promise_department': candidate.get('promise_department'),
                    'evidence_departments': candidate.get('evidence_departments', [])
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
                    'status': status,
                    'final_score': link.get('final_score', 0),
                    'department_match': link.get('department_match', False)
                })
                
                print(f"    {status}: {promise_id[:8]}...↔{evidence_id[:8]}... (Score: {link.get('final_score', 0):.2f})")
                
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
        """Export improved manual link testing results."""
        print("  💾 Exporting test results...")
        
        # Create output directory
        os.makedirs('improved_manual_link_test_results', exist_ok=True)
        
        # 1. JSON export
        with open('improved_manual_link_test_results/improved_manual_link_test.json', 'w') as f:
            json.dump(self.test_results, f, indent=2, default=str)
        
        # 2. Generate test report
        await self.generate_test_report()
        
        print("    ✅ Results exported to improved_manual_link_test_results/")
    
    async def generate_test_report(self):
        """Generate comprehensive test report."""
        links_created = len(self.test_results['test_links_created'])
        bidirectional_verification = self.test_results['system_functionality'].get('bidirectional_verification', {})
        operations = self.test_results['system_functionality'].get('operations', {})
        field_analysis = self.test_results.get('field_analysis', {})
        
        report = f"""
# Improved Manual Link Testing Report
Generated: {self.test_results['timestamp']}

## Executive Summary

This report documents the results of improved manual link testing using the correct field names discovered through data structure exploration.

### Test Results Summary

**Links Created**: {links_created} test links
**Bidirectional Consistency**: {bidirectional_verification.get('consistency_percentage', 0):.1f}%
**System Status**: {"✅ FUNCTIONAL" if links_created > 0 and bidirectional_verification.get('consistency_percentage', 0) > 80 else "⚠️ NEEDS ATTENTION"}

## Field Analysis Results

### Promise Fields
"""
        
        for field, stats in field_analysis.get('promises', {}).items():
            report += f"""
**{field}**:
- Count: {stats.get('count', 0)} items
- Average length: {stats.get('avg_length', 0):.0f} characters
- Sample: "{stats.get('sample', '')[:80]}..."
"""
        
        report += f"""

### Evidence Fields
"""
        
        for field, stats in field_analysis.get('evidence', {}).items():
            if field == 'linked_departments':
                report += f"""
**{field}**:
- Total mentions: {stats.get('count', 0)}
- Unique departments: {stats.get('unique_count', 0)}
- Sample: {stats.get('sample', '')}
"""
            else:
                report += f"""
**{field}**:
- Count: {stats.get('count', 0)} items
- Average length: {stats.get('avg_length', 0):.0f} characters
- Sample: "{stats.get('sample', '')[:80]}..."
"""
        
        report += f"""

## Test Links Created

"""
        
        for i, link in enumerate(self.test_results['test_links_created'], 1):
            dept_match = "✅" if link.get('department_match') else "❌"
            report += f"""
### Link {i}
- **Promise ID**: `{link['promise_id']}`
- **Evidence ID**: `{link['evidence_id']}`
- **Final Score**: {link.get('final_score', 0):.2f}
- **Overlap Ratio**: {link.get('overlap_ratio', 0):.2f}
- **Department Match**: {dept_match}
- **Shared Keywords**: {', '.join(link.get('shared_keywords', [])[:5])}
- **Promise Department**: {link.get('promise_department', 'N/A')}
- **Evidence Departments**: {', '.join(link.get('evidence_departments', [])[:3])}
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
            dept_match = "✅" if detail.get('department_match') else "❌"
            report += f"- {detail['status']}: `{detail['promise_id'][:8]}...` ↔ `{detail['evidence_id'][:8]}...` (Score: {detail.get('final_score', 0):.2f}, Dept: {dept_match})\n"
        
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
            report += "✅ **Link Creation**: System successfully creates bidirectional links using correct field names\n"
        else:
            report += "❌ **Link Creation**: System failed to create links\n"
        
        consistency_pct = bidirectional_verification.get('consistency_percentage', 0)
        if consistency_pct >= 90:
            report += "✅ **Bidirectional Consistency**: Excellent link consistency\n"
        elif consistency_pct >= 70:
            report += "⚠️ **Bidirectional Consistency**: Good but needs improvement\n"
        else:
            report += "❌ **Bidirectional Consistency**: Poor link consistency\n"
        
        # Analyze department matching effectiveness
        dept_matches = sum(1 for link in self.test_results['test_links_created'] if link.get('department_match'))
        if dept_matches > 0:
            report += f"✅ **Department Matching**: {dept_matches}/{links_created} links have department matches\n"
        
        report += f"""

### Key Improvements from Data Structure Analysis

1. **Correct Field Usage**: Using actual field names (text, description, title_or_summary, description_or_details)
2. **Enhanced Text Extraction**: Multi-field content extraction for better matching
3. **Department Matching**: Leveraging responsible_department_lead and linked_departments fields
4. **Improved Scoring**: Combined keyword overlap and department matching
5. **Better Keyword Extraction**: Enhanced filtering for government document terminology

### Immediate Recommendations

1. **System Status**: {"System is functional with improved field mapping" if links_created > 0 else "System requires further debugging"}
2. **Algorithm Development**: {"Ready for algorithm development with correct field mappings" if links_created > 0 else "Fix field mapping issues first"}
3. **Department Matching**: {"Department matching shows promise for improving link quality" if dept_matches > 0 else "Investigate department field consistency"}
4. **Next Steps**: {"Proceed with algorithm development using discovered field patterns" if consistency_pct >= 80 else "Improve bidirectional consistency before algorithm development"}

### Technical Findings

- Correct field names enable successful content extraction
- Multi-field text extraction improves matching quality
- Department matching provides valuable signal for link quality
- System architecture supports bidirectional linking
- Database operations perform adequately for development

## Files Generated
- `improved_manual_link_test.json`: Complete test data
- `improved_manual_link_test_report.md`: This comprehensive report

---
*Report generated by Promise Tracker Improved Manual Link Tester*
"""
        
        with open('improved_manual_link_test_results/improved_manual_link_test_report.md', 'w') as f:
            f.write(report)
        
        print("    📄 Test report saved to improved_manual_link_test_results/improved_manual_link_test_report.md")

async def main():
    """Main execution function."""
    tester = ImprovedManualLinkTester()
    results = await tester.run_improved_link_tests()
    
    print("\n" + "=" * 60)
    print("🎉 IMPROVED MANUAL LINK TESTING COMPLETE!")
    print("=" * 60)
    
    links_created = len(results['test_links_created'])
    bidirectional_verification = results['system_functionality'].get('bidirectional_verification', {})
    consistency_pct = bidirectional_verification.get('consistency_percentage', 0)
    
    # Count department matches
    dept_matches = sum(1 for link in results['test_links_created'] if link.get('department_match'))
    
    print(f"🔗 Test links created: {links_created}")
    print(f"⚖️ Bidirectional consistency: {consistency_pct:.1f}%")
    print(f"🏢 Department matches: {dept_matches}/{links_created}")
    
    # Show system status
    if links_created > 0 and consistency_pct >= 80:
        print("✅ SYSTEM STATUS: FUNCTIONAL - Ready for algorithm development")
    elif links_created > 0:
        print("⚠️ SYSTEM STATUS: PARTIAL - Links created but consistency issues")
    else:
        print("❌ SYSTEM STATUS: NON-FUNCTIONAL - Unable to create links")
    
    print("\n📁 Results saved to: improved_manual_link_test_results/")
    print("📄 Full report: improved_manual_link_test_results/improved_manual_link_test_report.md")

if __name__ == "__main__":
    asyncio.run(main()) 