#!/usr/bin/env python3
"""
Data Structure Explorer Script
Explores the actual data structure and field contents of promises and evidence

This script:
1. Examines actual field names and content in promises and evidence
2. Identifies which fields contain usable text content
3. Provides recommendations for data extraction strategies
"""

import asyncio
import json
import os
from datetime import datetime, timezone
from collections import defaultdict, Counter
from typing import Dict, List, Any, Optional

# Firebase imports
import firebase_admin
from firebase_admin import credentials, firestore

# Initialize Firebase Admin if not already done
try:
    firebase_admin.get_app()
except ValueError:
    firebase_admin.initialize_app()

db = firestore.client()

class DataStructureExplorer:
    """Explores the actual data structure of promises and evidence."""
    
    def __init__(self):
        self.db = db
        self.exploration_results = {
            'timestamp': datetime.now(timezone.utc).isoformat(),
            'promises_structure': {},
            'evidence_structure': {},
            'usable_fields': {},
            'recommendations': []
        }
        
    async def run_exploration(self) -> Dict[str, Any]:
        """Run the complete data structure exploration."""
        print("🔍 Starting Data Structure Exploration...")
        print("=" * 60)
        
        # Step 1: Explore promises structure
        print("📋 Step 1: Exploring promises data structure...")
        await self.explore_promises_structure()
        
        # Step 2: Explore evidence structure
        print("📊 Step 2: Exploring evidence data structure...")
        await self.explore_evidence_structure()
        
        # Step 3: Identify usable fields
        print("🔧 Step 3: Identifying usable fields for linking...")
        await self.identify_usable_fields()
        
        # Step 4: Generate recommendations
        print("💡 Step 4: Generating data extraction recommendations...")
        await self.generate_recommendations()
        
        # Step 5: Export results
        print("💾 Step 5: Exporting exploration results...")
        await self.export_results()
        
        print("✅ Data structure exploration complete!")
        return self.exploration_results
    
    async def explore_promises_structure(self):
        """Explore the structure of promises data."""
        print("  📥 Fetching promises sample...")
        
        try:
            promises_ref = self.db.collection('promises')
            promises_docs = promises_ref.limit(20).stream()  # Get sample
            
            promises_sample = []
            field_usage = defaultdict(int)
            field_types = defaultdict(set)
            field_content_samples = defaultdict(list)
            
            for doc in promises_docs:
                data = doc.to_dict()
                data['id'] = doc.id
                promises_sample.append(data)
                
                # Analyze field usage and types
                for field, value in data.items():
                    field_usage[field] += 1
                    field_types[field].add(type(value).__name__)
                    
                    # Store content samples for text fields
                    if isinstance(value, str) and len(value.strip()) > 0:
                        if len(field_content_samples[field]) < 3:  # Store up to 3 samples
                            sample = value[:100] + "..." if len(value) > 100 else value
                            field_content_samples[field].append(sample)
            
            total_promises = len(promises_sample)
            
            # Calculate field usage percentages
            field_stats = {}
            for field, count in field_usage.items():
                field_stats[field] = {
                    'usage_count': count,
                    'usage_percentage': (count / total_promises * 100) if total_promises > 0 else 0,
                    'data_types': list(field_types[field]),
                    'content_samples': field_content_samples.get(field, [])
                }
            
            self.exploration_results['promises_structure'] = {
                'total_sample_size': total_promises,
                'field_statistics': field_stats,
                'sample_documents': promises_sample[:3]  # Store 3 full samples
            }
            
            print(f"  ✅ Analyzed {total_promises} promises")
            print(f"  📊 Found {len(field_usage)} unique fields")
            
            # Show top fields with content
            text_fields = [(field, stats) for field, stats in field_stats.items() 
                          if stats['content_samples'] and stats['usage_percentage'] > 50]
            text_fields.sort(key=lambda x: x[1]['usage_percentage'], reverse=True)
            
            print("  📝 Top text fields:")
            for field, stats in text_fields[:5]:
                print(f"    - {field}: {stats['usage_percentage']:.1f}% usage")
                if stats['content_samples']:
                    print(f"      Sample: \"{stats['content_samples'][0][:50]}...\"")
            
        except Exception as e:
            print(f"  ❌ Error exploring promises: {e}")
    
    async def explore_evidence_structure(self):
        """Explore the structure of evidence data."""
        print("  📥 Fetching evidence sample...")
        
        try:
            evidence_ref = self.db.collection('evidence_items')
            evidence_docs = evidence_ref.limit(20).stream()  # Get sample
            
            evidence_sample = []
            field_usage = defaultdict(int)
            field_types = defaultdict(set)
            field_content_samples = defaultdict(list)
            
            for doc in evidence_docs:
                data = doc.to_dict()
                data['id'] = doc.id
                evidence_sample.append(data)
                
                # Analyze field usage and types
                for field, value in data.items():
                    field_usage[field] += 1
                    field_types[field].add(type(value).__name__)
                    
                    # Store content samples for text fields
                    if isinstance(value, str) and len(value.strip()) > 0:
                        if len(field_content_samples[field]) < 3:  # Store up to 3 samples
                            sample = value[:100] + "..." if len(value) > 100 else value
                            field_content_samples[field].append(sample)
            
            total_evidence = len(evidence_sample)
            
            # Calculate field usage percentages
            field_stats = {}
            for field, count in field_usage.items():
                field_stats[field] = {
                    'usage_count': count,
                    'usage_percentage': (count / total_evidence * 100) if total_evidence > 0 else 0,
                    'data_types': list(field_types[field]),
                    'content_samples': field_content_samples.get(field, [])
                }
            
            self.exploration_results['evidence_structure'] = {
                'total_sample_size': total_evidence,
                'field_statistics': field_stats,
                'sample_documents': evidence_sample[:3]  # Store 3 full samples
            }
            
            print(f"  ✅ Analyzed {total_evidence} evidence items")
            print(f"  📊 Found {len(field_usage)} unique fields")
            
            # Show top fields with content
            text_fields = [(field, stats) for field, stats in field_stats.items() 
                          if stats['content_samples'] and stats['usage_percentage'] > 50]
            text_fields.sort(key=lambda x: x[1]['usage_percentage'], reverse=True)
            
            print("  📝 Top text fields:")
            for field, stats in text_fields[:5]:
                print(f"    - {field}: {stats['usage_percentage']:.1f}% usage")
                if stats['content_samples']:
                    print(f"      Sample: \"{stats['content_samples'][0][:50]}...\"")
            
        except Exception as e:
            print(f"  ❌ Error exploring evidence: {e}")
    
    async def identify_usable_fields(self):
        """Identify which fields contain usable text content for linking."""
        print("  🔧 Identifying usable fields...")
        
        usable_fields = {
            'promises': {
                'primary_content': [],
                'secondary_content': [],
                'metadata': []
            },
            'evidence': {
                'primary_content': [],
                'secondary_content': [],
                'metadata': []
            }
        }
        
        # Analyze promises fields
        promises_fields = self.exploration_results.get('promises_structure', {}).get('field_statistics', {})
        for field, stats in promises_fields.items():
            if stats['content_samples'] and stats['usage_percentage'] > 0:
                content_length = sum(len(sample) for sample in stats['content_samples']) / len(stats['content_samples'])
                
                if content_length > 50 and stats['usage_percentage'] > 80:
                    usable_fields['promises']['primary_content'].append({
                        'field': field,
                        'usage_percentage': stats['usage_percentage'],
                        'avg_content_length': content_length,
                        'sample': stats['content_samples'][0] if stats['content_samples'] else ""
                    })
                elif content_length > 20 and stats['usage_percentage'] > 50:
                    usable_fields['promises']['secondary_content'].append({
                        'field': field,
                        'usage_percentage': stats['usage_percentage'],
                        'avg_content_length': content_length,
                        'sample': stats['content_samples'][0] if stats['content_samples'] else ""
                    })
                elif stats['usage_percentage'] > 30:
                    usable_fields['promises']['metadata'].append({
                        'field': field,
                        'usage_percentage': stats['usage_percentage'],
                        'avg_content_length': content_length,
                        'sample': stats['content_samples'][0] if stats['content_samples'] else ""
                    })
        
        # Analyze evidence fields
        evidence_fields = self.exploration_results.get('evidence_structure', {}).get('field_statistics', {})
        for field, stats in evidence_fields.items():
            if stats['content_samples'] and stats['usage_percentage'] > 0:
                content_length = sum(len(sample) for sample in stats['content_samples']) / len(stats['content_samples'])
                
                if content_length > 50 and stats['usage_percentage'] > 80:
                    usable_fields['evidence']['primary_content'].append({
                        'field': field,
                        'usage_percentage': stats['usage_percentage'],
                        'avg_content_length': content_length,
                        'sample': stats['content_samples'][0] if stats['content_samples'] else ""
                    })
                elif content_length > 20 and stats['usage_percentage'] > 50:
                    usable_fields['evidence']['secondary_content'].append({
                        'field': field,
                        'usage_percentage': stats['usage_percentage'],
                        'avg_content_length': content_length,
                        'sample': stats['content_samples'][0] if stats['content_samples'] else ""
                    })
                elif stats['usage_percentage'] > 30:
                    usable_fields['evidence']['metadata'].append({
                        'field': field,
                        'usage_percentage': stats['usage_percentage'],
                        'avg_content_length': content_length,
                        'sample': stats['content_samples'][0] if stats['content_samples'] else ""
                    })
        
        # Sort by usage percentage
        for collection in usable_fields.values():
            for category in collection.values():
                category.sort(key=lambda x: x['usage_percentage'], reverse=True)
        
        self.exploration_results['usable_fields'] = usable_fields
        
        # Print summary
        print(f"  📊 Promises - Primary content fields: {len(usable_fields['promises']['primary_content'])}")
        print(f"  📊 Promises - Secondary content fields: {len(usable_fields['promises']['secondary_content'])}")
        print(f"  📊 Evidence - Primary content fields: {len(usable_fields['evidence']['primary_content'])}")
        print(f"  📊 Evidence - Secondary content fields: {len(usable_fields['evidence']['secondary_content'])}")
    
    async def generate_recommendations(self):
        """Generate recommendations for data extraction and linking strategies."""
        print("  💡 Generating recommendations...")
        
        recommendations = []
        usable_fields = self.exploration_results.get('usable_fields', {})
        
        # Analyze promises content availability
        promises_primary = usable_fields.get('promises', {}).get('primary_content', [])
        promises_secondary = usable_fields.get('promises', {}).get('secondary_content', [])
        
        if not promises_primary and not promises_secondary:
            recommendations.append("CRITICAL: No usable text content found in promises. Data quality issues prevent linking.")
            recommendations.append("Investigate promise data ingestion and field mapping issues.")
        elif not promises_primary:
            recommendations.append("WARNING: No primary content fields in promises. Rely on secondary fields for linking.")
            recommendations.append(f"Use secondary fields: {', '.join([f['field'] for f in promises_secondary[:3]])}")
        else:
            recommendations.append(f"Use primary promise fields: {', '.join([f['field'] for f in promises_primary[:3]])}")
        
        # Analyze evidence content availability
        evidence_primary = usable_fields.get('evidence', {}).get('primary_content', [])
        evidence_secondary = usable_fields.get('evidence', {}).get('secondary_content', [])
        
        if not evidence_primary and not evidence_secondary:
            recommendations.append("CRITICAL: No usable text content found in evidence. Data quality issues prevent linking.")
            recommendations.append("Investigate evidence data ingestion and field mapping issues.")
        elif not evidence_primary:
            recommendations.append("WARNING: No primary content fields in evidence. Rely on secondary fields for linking.")
            recommendations.append(f"Use secondary evidence fields: {', '.join([f['field'] for f in evidence_secondary[:3]])}")
        else:
            recommendations.append(f"Use primary evidence fields: {', '.join([f['field'] for f in evidence_primary[:3]])}")
        
        # Content length analysis
        if promises_primary:
            avg_promise_length = sum(f['avg_content_length'] for f in promises_primary) / len(promises_primary)
            if avg_promise_length < 50:
                recommendations.append("Promise content is short. Consider combining multiple fields for better matching.")
        
        if evidence_primary:
            avg_evidence_length = sum(f['avg_content_length'] for f in evidence_primary) / len(evidence_primary)
            if avg_evidence_length < 50:
                recommendations.append("Evidence content is short. Consider combining multiple fields for better matching.")
        
        # Linking strategy recommendations
        if promises_primary and evidence_primary:
            recommendations.append("Implement multi-field text extraction combining primary and secondary content.")
            recommendations.append("Use semantic similarity algorithms due to sufficient text content.")
        elif (promises_primary or promises_secondary) and (evidence_primary or evidence_secondary):
            recommendations.append("Implement keyword-based matching due to limited text content.")
            recommendations.append("Lower similarity thresholds to account for shorter content.")
        else:
            recommendations.append("CRITICAL: Insufficient text content for automated linking.")
            recommendations.append("Focus on manual linking and data quality improvement first.")
        
        # Field-specific recommendations
        promises_metadata = usable_fields.get('promises', {}).get('metadata', [])
        evidence_metadata = usable_fields.get('evidence', {}).get('metadata', [])
        
        if promises_metadata and evidence_metadata:
            recommendations.append("Leverage metadata fields for department/category-based pre-filtering.")
        
        self.exploration_results['recommendations'] = recommendations
        
        print(f"  💡 Generated {len(recommendations)} recommendations")
    
    async def export_results(self):
        """Export exploration results."""
        print("  💾 Exporting exploration results...")
        
        # Create output directory
        os.makedirs('data_structure_exploration_results', exist_ok=True)
        
        # 1. JSON export
        with open('data_structure_exploration_results/data_structure_exploration.json', 'w') as f:
            json.dump(self.exploration_results, f, indent=2, default=str)
        
        # 2. Generate exploration report
        await self.generate_exploration_report()
        
        print("    ✅ Results exported to data_structure_exploration_results/")
    
    async def generate_exploration_report(self):
        """Generate comprehensive exploration report."""
        promises_structure = self.exploration_results.get('promises_structure', {})
        evidence_structure = self.exploration_results.get('evidence_structure', {})
        usable_fields = self.exploration_results.get('usable_fields', {})
        recommendations = self.exploration_results.get('recommendations', [])
        
        # Helper function to serialize datetime objects
        def serialize_sample_doc(doc):
            """Convert datetime objects to strings for JSON serialization."""
            if not doc:
                return {}
            
            serialized = {}
            for key, value in doc.items():
                if hasattr(value, 'isoformat'):  # datetime object
                    serialized[key] = value.isoformat()
                elif isinstance(value, list):
                    serialized[key] = [v.isoformat() if hasattr(v, 'isoformat') else v for v in value]
                else:
                    serialized[key] = value
            return serialized
        
        report = f"""
# Data Structure Exploration Report
Generated: {self.exploration_results['timestamp']}

## Executive Summary

This report explores the actual data structure and field contents of promises and evidence collections to identify usable content for linking algorithms.

### Key Findings

**Promises Collection**:
- Sample size: {promises_structure.get('total_sample_size', 0)} documents
- Total fields: {len(promises_structure.get('field_statistics', {}))} unique fields
- Primary content fields: {len(usable_fields.get('promises', {}).get('primary_content', []))}
- Secondary content fields: {len(usable_fields.get('promises', {}).get('secondary_content', []))}

**Evidence Collection**:
- Sample size: {evidence_structure.get('total_sample_size', 0)} documents  
- Total fields: {len(evidence_structure.get('field_statistics', {}))} unique fields
- Primary content fields: {len(usable_fields.get('evidence', {}).get('primary_content', []))}
- Secondary content fields: {len(usable_fields.get('evidence', {}).get('secondary_content', []))}

## Promises Data Structure

### Field Usage Statistics

"""
        
        promises_fields = promises_structure.get('field_statistics', {})
        # Sort fields by usage percentage
        sorted_promise_fields = sorted(promises_fields.items(), key=lambda x: x[1]['usage_percentage'], reverse=True)
        
        for field, stats in sorted_promise_fields[:15]:  # Show top 15 fields
            report += f"""
**{field}**:
- Usage: {stats['usage_percentage']:.1f}% ({stats['usage_count']} documents)
- Data types: {', '.join(stats['data_types'])}
"""
            if stats['content_samples']:
                report += f"- Sample content: \"{stats['content_samples'][0][:100]}...\"\n"
        
        report += f"""

### Usable Content Fields

#### Primary Content Fields (>50 chars, >80% usage)
"""
        
        for field_info in usable_fields.get('promises', {}).get('primary_content', []):
            report += f"""
- **{field_info['field']}**: {field_info['usage_percentage']:.1f}% usage, {field_info['avg_content_length']:.0f} avg chars
  - Sample: "{field_info['sample'][:80]}..."
"""
        
        report += f"""

#### Secondary Content Fields (>20 chars, >50% usage)
"""
        
        for field_info in usable_fields.get('promises', {}).get('secondary_content', []):
            report += f"""
- **{field_info['field']}**: {field_info['usage_percentage']:.1f}% usage, {field_info['avg_content_length']:.0f} avg chars
  - Sample: "{field_info['sample'][:80]}..."
"""
        
        report += f"""

## Evidence Data Structure

### Field Usage Statistics

"""
        
        evidence_fields = evidence_structure.get('field_statistics', {})
        # Sort fields by usage percentage
        sorted_evidence_fields = sorted(evidence_fields.items(), key=lambda x: x[1]['usage_percentage'], reverse=True)
        
        for field, stats in sorted_evidence_fields[:15]:  # Show top 15 fields
            report += f"""
**{field}**:
- Usage: {stats['usage_percentage']:.1f}% ({stats['usage_count']} documents)
- Data types: {', '.join(stats['data_types'])}
"""
            if stats['content_samples']:
                report += f"- Sample content: \"{stats['content_samples'][0][:100]}...\"\n"
        
        report += f"""

### Usable Content Fields

#### Primary Content Fields (>50 chars, >80% usage)
"""
        
        for field_info in usable_fields.get('evidence', {}).get('primary_content', []):
            report += f"""
- **{field_info['field']}**: {field_info['usage_percentage']:.1f}% usage, {field_info['avg_content_length']:.0f} avg chars
  - Sample: "{field_info['sample'][:80]}..."
"""
        
        report += f"""

#### Secondary Content Fields (>20 chars, >50% usage)
"""
        
        for field_info in usable_fields.get('evidence', {}).get('secondary_content', []):
            report += f"""
- **{field_info['field']}**: {field_info['usage_percentage']:.1f}% usage, {field_info['avg_content_length']:.0f} avg chars
  - Sample: "{field_info['sample'][:80]}..."
"""
        
        report += f"""

## Data Quality Assessment

### Content Availability

**Promises**:
- Primary content fields available: {"✅ Yes" if usable_fields.get('promises', {}).get('primary_content') else "❌ No"}
- Secondary content fields available: {"✅ Yes" if usable_fields.get('promises', {}).get('secondary_content') else "❌ No"}
- Metadata fields available: {"✅ Yes" if usable_fields.get('promises', {}).get('metadata') else "❌ No"}

**Evidence**:
- Primary content fields available: {"✅ Yes" if usable_fields.get('evidence', {}).get('primary_content') else "❌ No"}
- Secondary content fields available: {"✅ Yes" if usable_fields.get('evidence', {}).get('secondary_content') else "❌ No"}
- Metadata fields available: {"✅ Yes" if usable_fields.get('evidence', {}).get('metadata') else "❌ No"}

### Linking Feasibility

"""
        
        promises_has_content = bool(usable_fields.get('promises', {}).get('primary_content') or 
                                   usable_fields.get('promises', {}).get('secondary_content'))
        evidence_has_content = bool(usable_fields.get('evidence', {}).get('primary_content') or 
                                   usable_fields.get('evidence', {}).get('secondary_content'))
        
        if promises_has_content and evidence_has_content:
            report += "✅ **Linking Feasible**: Both collections have usable text content\n"
        elif promises_has_content or evidence_has_content:
            report += "⚠️ **Linking Challenging**: Only one collection has usable content\n"
        else:
            report += "❌ **Linking Not Feasible**: Neither collection has sufficient usable content\n"
        
        report += f"""

## Recommendations

### Data Extraction Strategy

"""
        
        for i, rec in enumerate(recommendations, 1):
            report += f"{i}. {rec}\n"
        
        report += f"""

### Implementation Priorities

1. **Immediate**: Fix data quality issues preventing content extraction
2. **Short-term**: Implement multi-field text extraction strategy
3. **Medium-term**: Develop field-specific processing algorithms
4. **Long-term**: Optimize linking algorithms based on actual content patterns

## Sample Documents

### Promise Sample
```json
{json.dumps(serialize_sample_doc(promises_structure.get('sample_documents', [{}])[0] if promises_structure.get('sample_documents') else {}), indent=2)[:500]}...
```

### Evidence Sample
```json
{json.dumps(serialize_sample_doc(evidence_structure.get('sample_documents', [{}])[0] if evidence_structure.get('sample_documents') else {}), indent=2)[:500]}...
```

## Files Generated
- `data_structure_exploration.json`: Complete exploration data
- `data_structure_exploration_report.md`: This comprehensive report

---
*Report generated by Promise Tracker Data Structure Explorer*
"""
        
        with open('data_structure_exploration_results/data_structure_exploration_report.md', 'w') as f:
            f.write(report)
        
        print("    📄 Exploration report saved to data_structure_exploration_results/data_structure_exploration_report.md")

async def main():
    """Main execution function."""
    explorer = DataStructureExplorer()
    results = await explorer.run_exploration()
    
    print("\n" + "=" * 60)
    print("🎉 DATA STRUCTURE EXPLORATION COMPLETE!")
    print("=" * 60)
    
    usable_fields = results.get('usable_fields', {})
    recommendations = results.get('recommendations', [])
    
    promises_primary = len(usable_fields.get('promises', {}).get('primary_content', []))
    promises_secondary = len(usable_fields.get('promises', {}).get('secondary_content', []))
    evidence_primary = len(usable_fields.get('evidence', {}).get('primary_content', []))
    evidence_secondary = len(usable_fields.get('evidence', {}).get('secondary_content', []))
    
    print(f"📊 Promises - Primary: {promises_primary}, Secondary: {promises_secondary}")
    print(f"📊 Evidence - Primary: {evidence_primary}, Secondary: {evidence_secondary}")
    print(f"💡 Recommendations: {len(recommendations)}")
    
    # Show linking feasibility
    if (promises_primary or promises_secondary) and (evidence_primary or evidence_secondary):
        print("✅ LINKING FEASIBILITY: Possible with available content")
    else:
        print("❌ LINKING FEASIBILITY: Insufficient content for automated linking")
    
    print("\n📁 Results saved to: data_structure_exploration_results/")
    print("📄 Full report: data_structure_exploration_results/data_structure_exploration_report.md")

if __name__ == "__main__":
    asyncio.run(main()) 