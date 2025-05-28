#!/usr/bin/env python3
"""
Detailed Link Analysis Script
Examines specific examples of successful links from backup data and finds corresponding items in current data

This script:
1. Finds specific successful bill-promise links from backup
2. Locates the same promises and evidence in current data
3. Compares the data structures in detail
4. Tests the linking algorithms on these specific cases
5. Identifies why the linking is failing
"""

import asyncio
import json
import os
from datetime import datetime, timezone
from typing import Dict, List, Any, Optional
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

class DetailedLinkAnalyzer:
    """Analyzes specific link examples in detail."""
    
    def __init__(self):
        self.db = db
        self.analysis_results = {
            'timestamp': datetime.now(timezone.utc).isoformat(),
            'backup_examples': [],
            'current_matches': [],
            'field_comparisons': [],
            'linking_tests': [],
            'recommendations': []
        }
        
    async def run_detailed_analysis(self) -> Dict[str, Any]:
        """Run the detailed link analysis."""
        print("🔍 Starting Detailed Link Analysis...")
        print("=" * 60)
        
        # Step 1: Get specific successful link examples from backup
        print("📊 Step 1: Getting successful link examples from backup...")
        backup_examples = await self.get_backup_link_examples()
        
        # Step 2: Find corresponding items in current data
        print("🔍 Step 2: Finding corresponding items in current data...")
        current_matches = await self.find_current_data_matches(backup_examples)
        
        # Step 3: Compare data structures in detail
        print("⚖️ Step 3: Comparing data structures in detail...")
        await self.compare_data_structures_detailed(current_matches)
        
        # Step 4: Test linking algorithms
        print("🧪 Step 4: Testing linking algorithms...")
        await self.test_linking_algorithms(current_matches)
        
        # Step 5: Export detailed results
        print("💾 Step 5: Exporting detailed results...")
        await self.export_detailed_results()
        
        print("✅ Detailed analysis complete!")
        return self.analysis_results
    
    async def get_backup_link_examples(self) -> List[Dict[str, Any]]:
        """Get specific examples of successful links from backup data."""
        print("  📥 Fetching backup link examples...")
        
        # Get backup evidence with promise links
        backup_evidence_ref = self.db.collection('evidence_items_backup_20250527_212346')
        backup_evidence_docs = backup_evidence_ref.limit(100).stream()  # Sample first 100
        
        backup_examples = []
        
        for evidence_doc in backup_evidence_docs:
            evidence_data = evidence_doc.to_dict()
            evidence_id = evidence_doc.id
            promise_ids = evidence_data.get('promise_ids', [])
            
            if promise_ids:
                # Get the first linked promise for this evidence
                promise_id = promise_ids[0]
                
                # Fetch the corresponding promise from backup
                try:
                    backup_promise_ref = self.db.collection('promises_backup_20250527_212346').document(promise_id)
                    backup_promise_doc = backup_promise_ref.get()
                    
                    if backup_promise_doc.exists:
                        promise_data = backup_promise_doc.to_dict()
                        
                        example = {
                            'backup_evidence_id': evidence_id,
                            'backup_promise_id': promise_id,
                            'evidence_data': evidence_data,
                            'promise_data': promise_data,
                            'evidence_type': evidence_data.get('evidence_source_type', ''),
                            'evidence_title': evidence_data.get('title_or_summary', ''),
                            'promise_text': promise_data.get('text', ''),
                            'parliament_session': evidence_data.get('parliament_session_id', ''),
                            'evidence_departments': evidence_data.get('linked_departments', []),
                            'promise_department': promise_data.get('responsible_department_lead', '')
                        }
                        
                        backup_examples.append(example)
                        
                        # Focus on bill events first, then other types
                        if len(backup_examples) >= 20:
                            break
                            
                except Exception as e:
                    print(f"    ⚠️ Error fetching promise {promise_id}: {e}")
                    continue
        
        # Sort by evidence type (bills first)
        backup_examples.sort(key=lambda x: (
            0 if 'Bill Event' in x['evidence_type'] else 1,
            x['evidence_type']
        ))
        
        self.analysis_results['backup_examples'] = backup_examples[:10]  # Top 10 examples
        
        print(f"  ✅ Found {len(backup_examples)} backup link examples")
        return backup_examples[:10]
    
    async def find_current_data_matches(self, backup_examples: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Find corresponding items in current data."""
        print("  🔍 Finding matches in current data...")
        
        current_matches = []
        
        for example in backup_examples:
            print(f"    🔍 Looking for: {example['evidence_title'][:50]}...")
            
            # Try to find matching evidence by title
            current_evidence = await self.find_evidence_by_title(example['evidence_title'])
            
            # Try to find matching promise by text
            current_promise = await self.find_promise_by_text(example['promise_text'])
            
            match_info = {
                'backup_example': example,
                'current_evidence': current_evidence,
                'current_promise': current_promise,
                'evidence_match_found': current_evidence is not None,
                'promise_match_found': current_promise is not None,
                'both_found': current_evidence is not None and current_promise is not None
            }
            
            if current_evidence:
                print(f"      ✅ Found evidence: {current_evidence['id']}")
            else:
                print(f"      ❌ Evidence not found")
                
            if current_promise:
                print(f"      ✅ Found promise: {current_promise['id']}")
            else:
                print(f"      ❌ Promise not found")
            
            current_matches.append(match_info)
        
        self.analysis_results['current_matches'] = current_matches
        
        matches_with_both = len([m for m in current_matches if m['both_found']])
        print(f"  📊 Found {matches_with_both} complete matches out of {len(backup_examples)} examples")
        
        return current_matches
    
    async def find_evidence_by_title(self, title: str) -> Optional[Dict[str, Any]]:
        """Find evidence item by title in current data."""
        try:
            # Try exact match first
            current_evidence_ref = self.db.collection('evidence_items')
            query = current_evidence_ref.where('title_or_summary', '==', title).limit(1)
            docs = list(query.stream())
            
            if docs:
                doc = docs[0]
                data = doc.to_dict()
                data['id'] = doc.id
                return data
            
            # Try partial match if exact fails
            # This is less efficient but necessary for finding matches
            all_evidence_ref = self.db.collection('evidence_items')
            all_docs = all_evidence_ref.stream()
            
            for doc in all_docs:
                data = doc.to_dict()
                current_title = data.get('title_or_summary', '')
                
                # Check if titles are similar (remove extra whitespace, etc.)
                if self.titles_similar(title, current_title):
                    data['id'] = doc.id
                    return data
            
            return None
            
        except Exception as e:
            print(f"      ⚠️ Error searching for evidence: {e}")
            return None
    
    async def find_promise_by_text(self, text: str) -> Optional[Dict[str, Any]]:
        """Find promise by text in current data."""
        try:
            # Try exact match first
            current_promises_ref = self.db.collection('promises')
            query = current_promises_ref.where('text', '==', text).limit(1)
            docs = list(query.stream())
            
            if docs:
                doc = docs[0]
                data = doc.to_dict()
                data['id'] = doc.id
                return data
            
            # Try partial match if exact fails
            all_promises_ref = self.db.collection('promises')
            all_docs = all_promises_ref.stream()
            
            for doc in all_docs:
                data = doc.to_dict()
                current_text = data.get('text', '')
                
                # Check if texts are similar
                if self.texts_similar(text, current_text):
                    data['id'] = doc.id
                    return data
            
            return None
            
        except Exception as e:
            print(f"      ⚠️ Error searching for promise: {e}")
            return None
    
    def titles_similar(self, title1: str, title2: str) -> bool:
        """Check if two titles are similar enough to be considered the same."""
        if not title1 or not title2:
            return False
        
        # Normalize titles
        t1 = re.sub(r'\s+', ' ', title1.strip().lower())
        t2 = re.sub(r'\s+', ' ', title2.strip().lower())
        
        # Exact match
        if t1 == t2:
            return True
        
        # Check if one contains the other (for truncated titles)
        if len(t1) > 20 and len(t2) > 20:
            if t1 in t2 or t2 in t1:
                return True
        
        return False
    
    def texts_similar(self, text1: str, text2: str) -> bool:
        """Check if two promise texts are similar enough to be considered the same."""
        if not text1 or not text2:
            return False
        
        # Normalize texts
        t1 = re.sub(r'\s+', ' ', text1.strip().lower())
        t2 = re.sub(r'\s+', ' ', text2.strip().lower())
        
        # Exact match
        if t1 == t2:
            return True
        
        # Check if texts are very similar (allowing for minor differences)
        if len(t1) > 50 and len(t2) > 50:
            # Calculate simple similarity
            words1 = set(t1.split())
            words2 = set(t2.split())
            
            if len(words1) > 0 and len(words2) > 0:
                intersection = len(words1.intersection(words2))
                union = len(words1.union(words2))
                similarity = intersection / union
                
                if similarity > 0.8:  # 80% word overlap
                    return True
        
        return False
    
    async def compare_data_structures_detailed(self, current_matches: List[Dict[str, Any]]):
        """Compare data structures in detail for matched items."""
        print("  ⚖️ Comparing data structures in detail...")
        
        field_comparisons = []
        
        for match in current_matches:
            if not match['both_found']:
                continue
                
            backup_evidence = match['backup_example']['evidence_data']
            backup_promise = match['backup_example']['promise_data']
            current_evidence = match['current_evidence']
            current_promise = match['current_promise']
            
            # Compare evidence fields
            evidence_comparison = {
                'backup_evidence_id': match['backup_example']['backup_evidence_id'],
                'current_evidence_id': current_evidence['id'],
                'evidence_title': backup_evidence.get('title_or_summary', ''),
                'fields_comparison': {
                    'promise_ids': {
                        'backup': backup_evidence.get('promise_ids', []),
                        'current': current_evidence.get('promise_ids', []),
                        'backup_count': len(backup_evidence.get('promise_ids', [])),
                        'current_count': len(current_evidence.get('promise_ids', []))
                    },
                    'evidence_source_type': {
                        'backup': backup_evidence.get('evidence_source_type', ''),
                        'current': current_evidence.get('evidence_source_type', ''),
                        'match': backup_evidence.get('evidence_source_type', '') == current_evidence.get('evidence_source_type', '')
                    },
                    'linked_departments': {
                        'backup': backup_evidence.get('linked_departments', []),
                        'current': current_evidence.get('linked_departments', []),
                        'backup_count': len(backup_evidence.get('linked_departments', [])),
                        'current_count': len(current_evidence.get('linked_departments', []))
                    },
                    'parliament_session_id': {
                        'backup': backup_evidence.get('parliament_session_id', ''),
                        'current': current_evidence.get('parliament_session_id', ''),
                        'match': backup_evidence.get('parliament_session_id', '') == current_evidence.get('parliament_session_id', '')
                    }
                }
            }
            
            # Compare promise fields
            promise_comparison = {
                'backup_promise_id': match['backup_example']['backup_promise_id'],
                'current_promise_id': current_promise['id'],
                'promise_text': backup_promise.get('text', '')[:100],
                'fields_comparison': {
                    'linked_evidence_ids': {
                        'backup': backup_promise.get('linked_evidence_ids', []),
                        'current': current_promise.get('linked_evidence_ids', []),
                        'backup_count': len(backup_promise.get('linked_evidence_ids', [])),
                        'current_count': len(current_promise.get('linked_evidence_ids', []))
                    },
                    'responsible_department_lead': {
                        'backup': backup_promise.get('responsible_department_lead', ''),
                        'current': current_promise.get('responsible_department_lead', ''),
                        'match': backup_promise.get('responsible_department_lead', '') == current_promise.get('responsible_department_lead', '')
                    },
                    'parliament_session_id': {
                        'backup': backup_promise.get('parliament_session_id', ''),
                        'current': current_promise.get('parliament_session_id', ''),
                        'match': backup_promise.get('parliament_session_id', '') == current_promise.get('parliament_session_id', '')
                    },
                    'extracted_keywords_concepts': {
                        'backup': backup_promise.get('extracted_keywords_concepts', []),
                        'current': current_promise.get('extracted_keywords_concepts', []),
                        'backup_count': len(backup_promise.get('extracted_keywords_concepts', [])),
                        'current_count': len(current_promise.get('extracted_keywords_concepts', []))
                    }
                }
            }
            
            field_comparison = {
                'evidence': evidence_comparison,
                'promise': promise_comparison,
                'link_status': {
                    'backup_had_link': match['backup_example']['backup_evidence_id'] in backup_promise.get('linked_evidence_ids', []),
                    'current_has_link': current_evidence['id'] in current_promise.get('linked_evidence_ids', []),
                    'bidirectional_backup': (
                        match['backup_example']['backup_evidence_id'] in backup_promise.get('linked_evidence_ids', []) and
                        match['backup_example']['backup_promise_id'] in backup_evidence.get('promise_ids', [])
                    ),
                    'bidirectional_current': (
                        current_evidence['id'] in current_promise.get('linked_evidence_ids', []) and
                        current_promise['id'] in current_evidence.get('promise_ids', [])
                    )
                }
            }
            
            field_comparisons.append(field_comparison)
        
        self.analysis_results['field_comparisons'] = field_comparisons
        
        print(f"  📊 Compared {len(field_comparisons)} matched pairs")
        
        # Analyze patterns
        current_with_links = len([fc for fc in field_comparisons if fc['link_status']['current_has_link']])
        backup_with_links = len([fc for fc in field_comparisons if fc['link_status']['backup_had_link']])
        
        print(f"  📊 Backup had links: {backup_with_links}/{len(field_comparisons)}")
        print(f"  📊 Current has links: {current_with_links}/{len(field_comparisons)}")
    
    async def test_linking_algorithms(self, current_matches: List[Dict[str, Any]]):
        """Test linking algorithms on the matched data."""
        print("  🧪 Testing linking algorithms...")
        
        # For now, just analyze what the algorithms would need to work
        linking_tests = []
        
        for match in current_matches:
            if not match['both_found']:
                continue
                
            current_evidence = match['current_evidence']
            current_promise = match['current_promise']
            
            # Simulate keyword matching
            evidence_keywords = self.extract_keywords(current_evidence)
            promise_keywords = self.extract_keywords(current_promise)
            
            keyword_overlap = self.calculate_keyword_overlap(evidence_keywords, promise_keywords)
            
            # Check department matching
            evidence_departments = current_evidence.get('linked_departments', [])
            promise_department = current_promise.get('responsible_department_lead', '')
            department_match = promise_department in evidence_departments if evidence_departments else True
            
            test_result = {
                'evidence_id': current_evidence['id'],
                'promise_id': current_promise['id'],
                'evidence_title': current_evidence.get('title_or_summary', '')[:100],
                'promise_text': current_promise.get('text', '')[:100],
                'keyword_overlap': keyword_overlap,
                'department_match': department_match,
                'evidence_departments': evidence_departments,
                'promise_department': promise_department,
                'would_pass_prefilter': keyword_overlap['jaccard'] >= 0.1 or keyword_overlap['common_count'] >= 2,
                'parliament_session_match': current_evidence.get('parliament_session_id') == current_promise.get('parliament_session_id')
            }
            
            linking_tests.append(test_result)
        
        self.analysis_results['linking_tests'] = linking_tests
        
        would_pass = len([t for t in linking_tests if t['would_pass_prefilter']])
        print(f"  📊 {would_pass}/{len(linking_tests)} would pass prefiltering")
        
        # Generate recommendations
        recommendations = []
        
        if len(current_matches) == 0:
            recommendations.append("No matching items found between backup and current data - data migration may have changed IDs or content")
        
        complete_matches = len([m for m in current_matches if m['both_found']])
        if complete_matches < len(current_matches) * 0.5:
            recommendations.append(f"Only {complete_matches}/{len(current_matches)} complete matches found - data structure may have changed significantly")
        
        if would_pass < len(linking_tests) * 0.5:
            recommendations.append(f"Only {would_pass}/{len(linking_tests)} would pass current prefiltering - thresholds may be too strict")
        
        no_current_links = all(fc['link_status']['current_has_link'] == False for fc in self.analysis_results.get('field_comparisons', []))
        if no_current_links:
            recommendations.append("No current data has links despite backup having links - linking system is not populating link fields")
        
        self.analysis_results['recommendations'] = recommendations
    
    def extract_keywords(self, item: Dict[str, Any]) -> List[str]:
        """Extract keywords from an item (promise or evidence)."""
        keywords = []
        
        # For promises
        if 'text' in item:
            extracted = item.get('extracted_keywords_concepts', [])
            if isinstance(extracted, list):
                keywords.extend([str(k) for k in extracted if k])
        
        # For evidence
        if 'title_or_summary' in item:
            key_concepts = item.get('key_concepts', [])
            if isinstance(key_concepts, list):
                keywords.extend([str(k) for k in key_concepts if k])
        
        return keywords
    
    def calculate_keyword_overlap(self, keywords1: List[str], keywords2: List[str]) -> Dict[str, Any]:
        """Calculate keyword overlap between two lists."""
        if not keywords1 or not keywords2:
            return {"jaccard": 0.0, "common_count": 0}
        
        set1 = set(k.lower().strip() for k in keywords1 if k and isinstance(k, str))
        set2 = set(k.lower().strip() for k in keywords2 if k and isinstance(k, str))
        
        intersection = len(set1.intersection(set2))
        union = len(set1.union(set2))
        
        jaccard = intersection / union if union > 0 else 0.0
        
        return {
            "jaccard": jaccard,
            "common_count": intersection,
            "keywords1_count": len(set1),
            "keywords2_count": len(set2)
        }
    
    async def export_detailed_results(self):
        """Export detailed analysis results."""
        print("  💾 Exporting detailed results...")
        
        # Create output directory
        os.makedirs('detailed_analysis_results', exist_ok=True)
        
        # 1. JSON export
        with open('detailed_analysis_results/detailed_link_analysis.json', 'w') as f:
            json.dump(self.analysis_results, f, indent=2, default=str)
        
        # 2. Generate detailed report
        await self.generate_detailed_report()
        
        print("    ✅ Detailed results exported to detailed_analysis_results/")
    
    async def generate_detailed_report(self):
        """Generate detailed analysis report."""
        backup_examples = self.analysis_results['backup_examples']
        current_matches = self.analysis_results['current_matches']
        field_comparisons = self.analysis_results['field_comparisons']
        linking_tests = self.analysis_results['linking_tests']
        recommendations = self.analysis_results['recommendations']
        
        report = f"""
# Detailed Link Analysis Report
Generated: {self.analysis_results['timestamp']}

## Executive Summary

### Data Matching Results
- **Backup Examples Analyzed**: {len(backup_examples)}
- **Complete Matches Found**: {len([m for m in current_matches if m['both_found']])}
- **Evidence Matches**: {len([m for m in current_matches if m['evidence_match_found']])}
- **Promise Matches**: {len([m for m in current_matches if m['promise_match_found']])}

### Linking Algorithm Tests
- **Items Tested**: {len(linking_tests)}
- **Would Pass Prefiltering**: {len([t for t in linking_tests if t.get('would_pass_prefilter', False)])}

## Detailed Findings

### Backup Examples Analyzed
"""
        
        for i, example in enumerate(backup_examples[:5], 1):
            report += f"""
**Example {i}**:
- **Evidence Type**: {example['evidence_type']}
- **Evidence Title**: {example['evidence_title'][:100]}...
- **Promise Text**: {example['promise_text'][:100]}...
- **Parliament Session**: {example['parliament_session']}
- **Evidence Departments**: {example['evidence_departments']}
- **Promise Department**: {example['promise_department']}
"""
        
        report += f"""

### Current Data Matching Results
"""
        
        complete_matches = [m for m in current_matches if m['both_found']]
        for i, match in enumerate(complete_matches[:5], 1):
            report += f"""
**Match {i}**:
- **Evidence Found**: ✅ {match['current_evidence']['id']}
- **Promise Found**: ✅ {match['current_promise']['id']}
- **Evidence Title**: {match['current_evidence'].get('title_or_summary', '')[:100]}...
- **Promise Text**: {match['current_promise'].get('text', '')[:100]}...
"""
        
        report += f"""

### Field Comparison Analysis
"""
        
        for i, fc in enumerate(field_comparisons[:3], 1):
            evidence = fc['evidence']
            promise = fc['promise']
            link_status = fc['link_status']
            
            report += f"""
**Comparison {i}**:

**Evidence Fields**:
- **Promise IDs**: Backup: {evidence['fields_comparison']['promise_ids']['backup_count']}, Current: {evidence['fields_comparison']['promise_ids']['current_count']}
- **Departments**: Backup: {evidence['fields_comparison']['linked_departments']['backup_count']}, Current: {evidence['fields_comparison']['linked_departments']['current_count']}
- **Session Match**: {evidence['fields_comparison']['parliament_session_id']['match']}

**Promise Fields**:
- **Linked Evidence IDs**: Backup: {promise['fields_comparison']['linked_evidence_ids']['backup_count']}, Current: {promise['fields_comparison']['linked_evidence_ids']['current_count']}
- **Keywords**: Backup: {promise['fields_comparison']['extracted_keywords_concepts']['backup_count']}, Current: {promise['fields_comparison']['extracted_keywords_concepts']['current_count']}
- **Department Match**: {promise['fields_comparison']['responsible_department_lead']['match']}

**Link Status**:
- **Backup Had Link**: {link_status['backup_had_link']}
- **Current Has Link**: {link_status['current_has_link']}
- **Bidirectional Backup**: {link_status['bidirectional_backup']}
- **Bidirectional Current**: {link_status['bidirectional_current']}
"""
        
        report += f"""

### Linking Algorithm Test Results
"""
        
        for i, test in enumerate(linking_tests[:5], 1):
            report += f"""
**Test {i}**:
- **Evidence**: {test['evidence_title']}
- **Promise**: {test['promise_text']}
- **Keyword Overlap**: Jaccard: {test['keyword_overlap']['jaccard']:.3f}, Common: {test['keyword_overlap']['common_count']}
- **Department Match**: {test['department_match']}
- **Would Pass Prefilter**: {test['would_pass_prefilter']}
- **Session Match**: {test['parliament_session_match']}
"""
        
        report += f"""

## Key Issues Identified

### Critical Problems
"""
        
        for i, rec in enumerate(recommendations, 1):
            report += f"{i}. {rec}\n"
        
        report += f"""

### Specific Issues Found

#### Link Field Population
- **Current promises with linked_evidence_ids**: {len([fc for fc in field_comparisons if fc['promise']['fields_comparison']['linked_evidence_ids']['current_count'] > 0])} / {len(field_comparisons)}
- **Current evidence with promise_ids**: {len([fc for fc in field_comparisons if fc['evidence']['fields_comparison']['promise_ids']['current_count'] > 0])} / {len(field_comparisons)}

#### Algorithm Compatibility
- **Items that would pass prefiltering**: {len([t for t in linking_tests if t.get('would_pass_prefilter', False)])} / {len(linking_tests)}
- **Department matches**: {len([t for t in linking_tests if t.get('department_match', False)])} / {len(linking_tests)}
- **Session matches**: {len([t for t in linking_tests if t.get('parliament_session_match', False)])} / {len(linking_tests)}

## Recommendations

### Immediate Actions
1. **Verify Link Field Population**: Check if linking scripts are actually writing to linked_evidence_ids and promise_ids fields
2. **Test Specific Cases**: Use the complete matches found to test linking algorithms
3. **Check Data Migration**: Verify if link fields were preserved during data migration

### Algorithm Adjustments
1. **Lower Thresholds**: Consider reducing similarity thresholds if too few items pass prefiltering
2. **Keyword Extraction**: Verify that keywords are being extracted properly in current data
3. **Department Matching**: Review department matching logic for current data structure

### Testing Protocol
1. **Manual Link Creation**: Manually create a few test links to verify the system works
2. **Algorithm Testing**: Run linking algorithms on the complete matches found
3. **Validation**: Compare results with backup data expectations

## Files Generated
- `detailed_link_analysis.json`: Complete analysis data
- `detailed_analysis_report.md`: This report
"""
        
        with open('detailed_analysis_results/detailed_analysis_report.md', 'w') as f:
            f.write(report)
        
        print("    📄 Detailed report saved to detailed_analysis_results/detailed_analysis_report.md")

async def main():
    """Main execution function."""
    analyzer = DetailedLinkAnalyzer()
    results = await analyzer.run_detailed_analysis()
    
    print("\n" + "=" * 60)
    print("🎉 DETAILED ANALYSIS COMPLETE!")
    print("=" * 60)
    
    backup_examples = results['backup_examples']
    current_matches = results['current_matches']
    field_comparisons = results['field_comparisons']
    linking_tests = results['linking_tests']
    
    complete_matches = len([m for m in current_matches if m['both_found']])
    would_pass_prefilter = len([t for t in linking_tests if t.get('would_pass_prefilter', False)])
    
    print(f"📊 Backup examples analyzed: {len(backup_examples)}")
    print(f"📊 Complete matches found: {complete_matches}")
    print(f"📊 Field comparisons made: {len(field_comparisons)}")
    print(f"📊 Would pass prefiltering: {would_pass_prefilter}/{len(linking_tests)}")
    print("\n📁 Results saved to: detailed_analysis_results/")
    print("📄 Full report: detailed_analysis_results/detailed_analysis_report.md")

if __name__ == "__main__":
    asyncio.run(main()) 