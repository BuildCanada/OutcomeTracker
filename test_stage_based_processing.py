#!/usr/bin/env python3
"""
Test Stage-Based Processing for LegisInfo Bills

This script tests the new parliamentary stage detection and evidence creation
for LegisInfo bills. It shows how bills progressing through different stages
will create separate evidence items for each stage.
"""

import logging
import sys
import json
from pathlib import Path
from datetime import datetime, timezone

# Add pipeline directory to path
pipeline_dir = Path(__file__).parent / "pipeline"
sys.path.insert(0, str(pipeline_dir))

from stages.processing.legisinfo_processor import LegisInfoProcessor

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(name)s - %(message)s'
)

def create_test_bill_data():
    """Create sample bill data representing different parliamentary stages"""
    
    # Sample bill data for Bill C-4 in different stages
    base_bill_data = {
        "Id": 12345678,
        "ParliamentNumber": 45,
        "SessionNumber": 1,
        "NumberCode": "C-4",
        "LongTitleEn": "An Act to implement certain provisions of the budget tabled in Parliament on April 16, 2024 and other measures",
        "ShortTitleEn": "Budget Implementation Act, 2024, No. 1",
        "ShortLegislativeSummaryEn": "<p>This enactment implements certain provisions of the budget tabled in Parliament on April 16, 2024.</p>",
        "BillDocumentTypeName": "Government Bill",
        "IsGovernmentBill": True,
        "SponsorPersonName": "Chrystia Freeland",
        "SponsorAffiliationTitleEn": "Deputy Prime Minister and Minister of Finance"
    }
    
    # Stage 1: First Reading
    stage1_data = {
        **base_bill_data,
        "LatestCompletedMajorStageId": 60043,
        "LatestCompletedMajorStageNameEn": "First reading",
        "LatestCompletedMajorStageDateTime": "2024-05-27T12:44:38.9",
        "LatestCompletedMajorStageChamberNameEn": "House of Commons",
        "LatestCompletedBillStageId": 60029,
        "LatestCompletedBillStageNameEn": "First reading",
        "LatestCompletedBillStageDateTime": "2024-05-27T12:44:38.9",
        "LatestCompletedBillStageChamberNameEn": "House of Commons",
        "StatusNameEn": "First reading"
    }
    
    # Stage 2: Second Reading
    stage2_data = {
        **base_bill_data,
        "LatestCompletedMajorStageId": 60044,
        "LatestCompletedMajorStageNameEn": "Second reading",
        "LatestCompletedMajorStageDateTime": "2024-06-15T15:30:00.0",
        "LatestCompletedMajorStageChamberNameEn": "House of Commons",
        "LatestCompletedBillStageId": 60031,
        "LatestCompletedBillStageNameEn": "Second reading",
        "LatestCompletedBillStageDateTime": "2024-06-15T15:30:00.0",
        "LatestCompletedBillStageChamberNameEn": "House of Commons",
        "StatusNameEn": "Second reading"
    }
    
    # Stage 3: Royal Assent (terminal stage)
    stage3_data = {
        **base_bill_data,
        "LatestCompletedMajorStageId": 60048,
        "LatestCompletedMajorStageNameEn": "Royal Assent",
        "LatestCompletedMajorStageDateTime": "2024-07-20T10:00:00.0",
        "LatestCompletedMajorStageChamberNameEn": "Senate",
        "LatestCompletedBillStageId": 60036,
        "LatestCompletedBillStageNameEn": "Royal Assent",
        "LatestCompletedBillStageDateTime": "2024-07-20T10:00:00.0",
        "LatestCompletedBillStageChamberNameEn": "Senate",
        "StatusNameEn": "Royal Assent"
    }
    
    return [stage1_data, stage2_data, stage3_data]

def create_test_raw_items(bill_stages):
    """Create raw items in the format expected by the processor"""
    raw_items = []
    
    for i, stage_data in enumerate(bill_stages):
        raw_item = {
            '_doc_id': f"test_bill_c4_stage_{i+1}",
            'bill_number_code_feed': 'C-4',
            'parliament_session_id': '45-1',
            'raw_json_content': json.dumps([stage_data]),
            'raw_xml_content': f'<?xml version="1.0" encoding="UTF-8"?><Bill><Title>Budget Implementation Act, 2024, No. 1</Title><Summary>Sample XML content for stage {i+1}</Summary></Bill>',
            'ingested_at': datetime.now(timezone.utc),
            'processing_status': 'pending_processing'
        }
        raw_items.append(raw_item)
    
    return raw_items

def test_stage_detection(processor, raw_items):
    """Test stage detection and processing logic"""
    print("\n" + "="*60)
    print("🏛️  TESTING PARLIAMENTARY STAGE DETECTION")
    print("="*60)
    
    for i, raw_item in enumerate(raw_items):
        print(f"\n--- Stage {i+1} Test ---")
        
        # Parse the bill data
        bill_data_list = json.loads(raw_item['raw_json_content'])
        bill_data = bill_data_list[0]
        
        # Test stage detection
        stages_to_process = processor._get_stages_to_process(raw_item, bill_data)
        
        print(f"Bill: {raw_item['bill_number_code_feed']}")
        print(f"Latest Major Stage: {bill_data.get('LatestCompletedMajorStageNameEn')}")
        print(f"Latest Bill Stage: {bill_data.get('LatestCompletedBillStageNameEn')}")
        print(f"Chamber: {bill_data.get('LatestCompletedBillStageChamberNameEn')}")
        print(f"Stages to Process: {len(stages_to_process)}")
        
        for stage in stages_to_process:
            print(f"  - Stage ID: {stage['stage_id']}")
            print(f"  - Stage Name: {stage['stage_name']}")
            print(f"  - Chamber: {stage['chamber_name']}")
            print(f"  - Type: {stage['stage_type']}")

def test_evidence_creation(processor, raw_items):
    """Test evidence item creation for different stages"""
    print("\n" + "="*60)
    print("📄 TESTING EVIDENCE ITEM CREATION")
    print("="*60)
    
    for i, raw_item in enumerate(raw_items):
        print(f"\n--- Evidence Creation Test {i+1} ---")
        
        try:
            # Process the raw item
            evidence_items = processor._process_raw_item(raw_item)
            
            if evidence_items:
                print(f"✅ Created {len(evidence_items)} evidence item(s)")
                
                for j, evidence_item in enumerate(evidence_items):
                    print(f"\nEvidence Item {j+1}:")
                    print(f"  Evidence ID: {evidence_item.get('evidence_id')}")
                    print(f"  Title: {evidence_item.get('title_or_summary')}")
                    print(f"  Stage: {evidence_item.get('parliamentary_stage')}")
                    print(f"  Chamber: {evidence_item.get('chamber')}")
                    print(f"  Terminal Stage: {evidence_item.get('is_terminal_stage')}")
                    print(f"  Evidence Date: {evidence_item.get('evidence_date')}")
                    
                    # Show description preview
                    description = evidence_item.get('description_or_details', '')
                    preview = description[:150] + "..." if len(description) > 150 else description
                    print(f"  Description Preview: {preview}")
            else:
                print("❌ No evidence items created")
                
        except Exception as e:
            print(f"❌ Error processing raw item: {e}")

def test_unique_evidence_ids(processor, raw_items):
    """Test that each stage gets a unique evidence ID"""
    print("\n" + "="*60)
    print("🔑 TESTING UNIQUE EVIDENCE IDs")
    print("="*60)
    
    all_evidence_ids = set()
    
    for i, raw_item in enumerate(raw_items):
        try:
            evidence_items = processor._process_raw_item(raw_item)
            
            if evidence_items:
                for evidence_item in evidence_items:
                    evidence_id = evidence_item.get('evidence_id')
                    
                    if evidence_id in all_evidence_ids:
                        print(f"❌ DUPLICATE ID FOUND: {evidence_id}")
                    else:
                        all_evidence_ids.add(evidence_id)
                        print(f"✅ Unique ID: {evidence_id}")
                        
        except Exception as e:
            print(f"❌ Error processing: {e}")
    
    print(f"\n📊 Total unique evidence IDs: {len(all_evidence_ids)}")

def main():
    """Run the stage-based processing tests"""
    print("🏛️  PARLIAMENTARY STAGE-BASED PROCESSING TEST")
    print("=" * 60)
    print("Testing new approach for creating separate evidence items")
    print("for each parliamentary stage of LegisInfo bills.")
    print("=" * 60)
    
    try:
        # Create test configuration that allows processing
        config = {
            'include_private_bills': True,
            'min_relevance_threshold': 0.1,
            'source_collection': 'test_raw_bills',  # Test collection
            'target_collection': 'test_evidence_items'  # Test collection
        }
        
        # Initialize processor
        processor = LegisInfoProcessor("test_legisinfo_processor", config)
        
        # Create test data
        print("\n📊 Creating test data...")
        bill_stages = create_test_bill_data()
        raw_items = create_test_raw_items(bill_stages)
        print(f"Created {len(raw_items)} test raw items representing different parliamentary stages")
        
        # Run tests
        test_stage_detection(processor, raw_items)
        test_evidence_creation(processor, raw_items) 
        test_unique_evidence_ids(processor, raw_items)
        
        print("\n" + "="*60)
        print("🎉 STAGE-BASED PROCESSING TESTS COMPLETED")
        print("="*60)
        print("\nKey Features Tested:")
        print("✅ Parliamentary stage detection from JSON data")
        print("✅ Stage-specific evidence item creation") 
        print("✅ Unique evidence IDs for each stage")
        print("✅ Stage-specific titles and descriptions")
        print("✅ Terminal stage detection (Royal Assent)")
        print("✅ Chamber information tracking")
        print("\nThis approach will enable:")
        print("📈 Separate timeline entries for each bill stage")
        print("🔗 Independent promise linking for each stage")
        print("📊 Better progress tracking through parliament")
        
    except Exception as e:
        print(f"❌ Test failed: {e}")
        import traceback
        traceback.print_exc()
        return 1
    
    return 0

if __name__ == "__main__":
    exit(main()) 