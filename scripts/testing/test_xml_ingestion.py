"""
Test script for validating XML ingestion and processing improvements.

This script tests:
1. XML URL construction for bills
2. XML content fetching 
3. LLM synthesis of XML content
"""

import logging
import sys
from pathlib import Path
from typing import Dict, Any

# Setup path for imports
pipeline_dir = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(pipeline_dir))

from pipeline.stages.ingestion.legisinfo_bills import LegisInfoBillsIngestion
from pipeline.stages.processing.legisinfo_processor import LegisInfoProcessor

def test_xml_ingestion():
    """Test the XML ingestion functionality"""
    print("=" * 60)
    print("🧪 Testing XML Ingestion")
    print("=" * 60)
    
    # Create test ingestion job
    config = {
        'max_bills_per_run': 2,  # Test with just 2 bills
        'collection_name': None  # We won't actually save anything
    }
    
    ingestion_job = LegisInfoBillsIngestion("test_xml_ingestion", config)
    
    try:
        # Test fetching bill list
        print("📋 Fetching bill list...")
        bill_list = ingestion_job._fetch_bill_list()
        
        if not bill_list:
            print("❌ Failed to fetch bill list")
            return False, []
            
        print(f"✅ Fetched {len(bill_list)} bills from API")
        
        # Filter to recent bills
        filtered_bills = ingestion_job._filter_bills_by_parliament(bill_list)
        
        if not filtered_bills:
            print("❌ No bills found after filtering")
            return False, []
            
        print(f"✅ Filtered to {len(filtered_bills)} bills")
        
        # Test XML fetching on first few bills
        test_bills = filtered_bills[:2]
        
        # Store successfully fetched XML for synthesis testing
        fetched_xml_content = []
        
        for i, bill in enumerate(test_bills):
            bill_code = bill.get('BillNumberFormatted', 'Unknown')
            print(f"\n📄 Testing bill {i+1}: {bill_code}")
            
            # Test XML URL construction
            xml_url = ingestion_job._construct_xml_url(bill)
            if xml_url:
                print(f"✅ Constructed XML URL: {xml_url}")
                
                # Test XML fetching
                xml_content = ingestion_job._fetch_bill_xml(bill)
                if xml_content:
                    content_length = len(xml_content)
                    print(f"✅ Fetched XML content ({content_length:,} characters)")
                    
                    # Show a sample of the content
                    sample = xml_content[:200].replace('\n', ' ')
                    print(f"📝 Sample: {sample}...")
                    
                    # Store for synthesis testing
                    fetched_xml_content.append({
                        'bill_code': bill_code,
                        'xml_content': xml_content
                    })
                else:
                    print(f"⚠️  Could not fetch XML content (this is normal for some bills)")
            else:
                print(f"❌ Could not construct XML URL for {bill_code}")
                
        print("\n✅ XML ingestion test completed successfully!")
        return True, fetched_xml_content
        
    except Exception as e:
        print(f"❌ XML ingestion test failed: {e}")
        logging.error("XML ingestion test error", exc_info=True)
        return False, []

def test_xml_synthesis(real_xml_content=None):
    """Test the XML synthesis functionality"""
    print("\n" + "=" * 60)
    print("🤖 Testing XML Synthesis")
    print("=" * 60)
    
    try:
        # Create test processor
        config = {
            'source_collection': None,  # We won't read from database
            'target_collection': None   # We won't write to database
        }
        
        processor = LegisInfoProcessor("test_xml_synthesis", config)
        
        synthesis_success = True
        
        # Test with real XML content if available
        if real_xml_content:
            for item in real_xml_content:
                bill_code = item['bill_code']
                xml_content = item['xml_content']
                
                print(f"\n🤖 Synthesizing real XML content for {bill_code}...")
                synthesized_summary = processor._synthesize_bill_xml(xml_content)
                
                if synthesized_summary:
                    print(f"✅ Successfully synthesized {bill_code} XML content!")
                    print(f"\n📄 Synthesized Summary for {bill_code}:")
                    print("-" * 40)
                    print(synthesized_summary)
                    print("-" * 40)
                    
                    # Check length constraint
                    word_count = len(synthesized_summary.split())
                    print(f"\n📊 Word count: {word_count} words")
                    if word_count <= 200:
                        print("✅ Within 200-word limit")
                    else:
                        print("⚠️  Exceeds 200-word limit")
                        synthesis_success = False
                else:
                    print(f"❌ XML synthesis returned no content for {bill_code}")
                    synthesis_success = False
        
        # Also test with sample XML as before
        test_xml = """
        <Bill bill-origin="commons" bill-type="govt-public" xml:lang="en">
            <Identification>
                <BillNumber>C-4</BillNumber>
            </Identification>
            <LongTitle>An Act respecting certain affordability measures for Canadians and another measure</LongTitle>
            <ShortTitle>Making Life More Affordable for Canadians Act</ShortTitle>
            <Preamble>
                <Text>Her Excellency the Governor General recommends to the House of Commons the appropriation of public revenue under the circumstances, in the manner and for the purposes set out in a measure entitled "An Act respecting certain affordability measures for Canadians and another measure".</Text>
            </Preamble>
            <Text>
                Part 1 amends the Income Tax Act to reduce the marginal personal income tax rate on the lowest tax bracket to 14.5% for the 2025 taxation year and to 14% for the 2026 and subsequent taxation years.
                Part 2 amends the Excise Tax Act and other related Regulations to implement a temporary GST new housing rebate for first-time home buyers.
                Part 3 repeals Part 1 of the Greenhouse Gas Pollution Pricing Act and the Fuel Charge Regulations.
            </Text>
        </Bill>
        """
        
        print("\n🤖 Synthesizing sample XML content...")
        synthesized_summary = processor._synthesize_bill_xml(test_xml)
        
        if synthesized_summary:
            print("✅ Successfully synthesized sample XML content!")
            print("\n📄 Synthesized Summary for Sample:")
            print("-" * 40)
            print(synthesized_summary)
            print("-" * 40)
            
            # Check length constraint
            word_count = len(synthesized_summary.split())
            print(f"\n📊 Word count: {word_count} words")
            if word_count <= 200:
                print("✅ Within 200-word limit")
            else:
                print("⚠️  Exceeds 200-word limit")
                synthesis_success = False
        else:
            print("❌ XML synthesis returned no content for sample")
            synthesis_success = False
            
        return synthesis_success
            
    except Exception as e:
        print(f"❌ XML synthesis test failed: {e}")
        logging.error("XML synthesis test error", exc_info=True)
        return False

def main():
    """Run all tests"""
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
    
    print("🧪 Starting XML Ingestion and Processing Tests")
    
    # Test 1: XML Ingestion (now returns fetched content)
    ingestion_success, fetched_xml_content = test_xml_ingestion()
    
    # Test 2: XML Synthesis (now uses real content if available)
    synthesis_success = test_xml_synthesis(fetched_xml_content)
    
    # Summary
    print("\n" + "=" * 60)
    print("📊 Test Results")
    print("=" * 60)
    print(f"XML Ingestion: {'✅ PASS' if ingestion_success else '❌ FAIL'}")
    print(f"XML Synthesis: {'✅ PASS' if synthesis_success else '❌ FAIL'}")
    
    if ingestion_success and synthesis_success:
        print("\n🎉 All tests passed! Ready for production deployment.")
    else:
        print("\n⚠️  Some tests failed. Review the output above.")

if __name__ == "__main__":
    main() 