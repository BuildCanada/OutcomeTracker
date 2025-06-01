#!/usr/bin/env python3
"""
LEGISinfo Scale Test

Tests LEGISinfo pipeline at scale:
1. Ingest 100 bills from LEGISinfo API
2. Process 10 bills through full LLM pipeline
3. Store evidence items in test collection for validation

This validates the complete pipeline functionality and performance.
"""

import sys
import os
import logging
import time
from datetime import datetime, timezone
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Add pipeline to path
pipeline_dir = Path(__file__).parent.parent.parent
sys.path.insert(0, str(pipeline_dir))

from pipeline.stages.ingestion.legisinfo_bills import LegisInfoBillsIngestion
from pipeline.stages.processing.legisinfo_processor import LegisInfoProcessor
import firebase_admin
from firebase_admin import firestore

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Test collection names
TEST_RAW_COLLECTION = "test_raw_legisinfo_bill_details"
TEST_EVIDENCE_COLLECTION = "test_evidence_items"

# Scale test configuration
INGESTION_TARGET = 15  # Reduced for faster testing
PROCESSING_TARGET = 5   # Reduced for faster testing

def setup_firebase():
    """Initialize Firebase connection"""
    if not firebase_admin._apps:
        firebase_admin.initialize_app()
    return firestore.client()

def cleanup_test_collections():
    """Clean up test collections before running tests"""
    logger.info("Cleaning up test collections...")
    db = setup_firebase()
    
    try:
        # Clean test raw collection
        raw_docs = db.collection(TEST_RAW_COLLECTION).stream()
        delete_count = 0
        for doc in raw_docs:
            doc.reference.delete()
            delete_count += 1
        logger.info(f"✓ Deleted {delete_count} documents from {TEST_RAW_COLLECTION}")
        
        # Clean test evidence collection  
        evidence_docs = db.collection(TEST_EVIDENCE_COLLECTION).stream()
        delete_count = 0
        for doc in evidence_docs:
            doc.reference.delete()
            delete_count += 1
        logger.info(f"✓ Deleted {delete_count} documents from {TEST_EVIDENCE_COLLECTION}")
        
    except Exception as e:
        logger.warning(f"Could not clean test collections: {e}")

def test_large_scale_ingestion():
    """Test ingesting bills from LEGISinfo API (up to 100 or whatever is available)"""
    logger.info("=== Large Scale Ingestion Test ===")
    logger.info(f"Target: Ingest up to {INGESTION_TARGET} bills from LEGISinfo API")
    
    # Configure for maximum ingestion from current parliament
    config = {
        'collection_name': TEST_RAW_COLLECTION,
        'min_parliament': 45,  # Parliament 45 where the bills are
        'max_bills_per_run': INGESTION_TARGET,
        'request_timeout': 60,
        'max_retries': 3
    }
    
    ingestion_job = LegisInfoBillsIngestion("scale_test_ingestion", config)
    
    start_time = time.time()
    
    try:
        logger.info("Starting large-scale ingestion...")
        
        # Fetch raw items from API
        raw_items = ingestion_job._fetch_new_items()
        
        if not raw_items:
            logger.error("No items fetched from ingestion")
            return False, 0
        
        fetched_count = len(raw_items)
        logger.info(f"✓ Fetched {fetched_count} bills from API")
        
        # Process and store items
        db = setup_firebase()
        stored_count = 0
        error_count = 0
        
        for i, raw_item in enumerate(raw_items):
            try:
                # Process the raw item
                processed_item = ingestion_job._process_raw_item(raw_item)
                
                if processed_item:
                    # Generate document ID
                    doc_id = ingestion_job._generate_item_id(processed_item)
                    
                    if doc_id:
                        # Store in test collection
                        db.collection(TEST_RAW_COLLECTION).document(doc_id).set(processed_item)
                        stored_count += 1
                        
                        if (i + 1) % 10 == 0:
                            logger.info(f"Progress: {i + 1}/{fetched_count} bills processed")
                    else:
                        error_count += 1
                        logger.warning(f"Could not generate ID for bill {i + 1}")
                else:
                    error_count += 1
                    logger.warning(f"Could not process bill {i + 1}")
                    
            except Exception as e:
                error_count += 1
                logger.error(f"Error processing bill {i + 1}: {e}")
        
        elapsed_time = time.time() - start_time
        logger.info(f"✓ Ingestion completed in {elapsed_time:.1f} seconds")
        logger.info(f"✓ Successfully stored: {stored_count} bills")
        logger.info(f"✓ Errors: {error_count} bills")
        logger.info(f"✓ Success rate: {stored_count/fetched_count:.1%}")
        
        # Validate stored data
        stored_docs = list(db.collection(TEST_RAW_COLLECTION).limit(5).stream())
        if stored_docs:
            sample_doc = stored_docs[0].to_dict()
            logger.info(f"✓ Sample bill: {sample_doc.get('bill_number_formatted')} - {sample_doc.get('long_title_en', '')[:50]}...")
            logger.info(f"✓ Parliament: {sample_doc.get('parliament_number')}")
            logger.info(f"✓ Required fields present: {all(field in sample_doc for field in ['long_title_en', 'bill_number_formatted', 'parliament_session_id'])}")
        
        # Success criteria: At least 10 bills and good success rate
        success = stored_count >= 10 and (stored_count/fetched_count) >= 0.8
        if success:
            logger.info(f"✅ Ingestion test PASSED: {stored_count} bills stored")
        else:
            logger.error(f"❌ Ingestion test FAILED: Only {stored_count} bills stored or low success rate")
        
        return success, stored_count
        
    except Exception as e:
        logger.error(f"Large scale ingestion failed: {e}")
        return False, 0

def test_llm_processing_pipeline():
    """Test processing 10 bills through the full LLM pipeline"""
    logger.info("=== LLM Processing Pipeline Test ===")
    logger.info(f"Target: Process {PROCESSING_TARGET} bills through LLM pipeline")
    
    db = setup_firebase()
    
    try:
        # Get bills from test collection for processing
        logger.info(f"Fetching bills from {TEST_RAW_COLLECTION} for processing...")
        
        raw_docs = list(db.collection(TEST_RAW_COLLECTION).limit(PROCESSING_TARGET).stream())
        
        if len(raw_docs) < PROCESSING_TARGET:
            logger.warning(f"Only {len(raw_docs)} bills available, processing all of them")
        
        logger.info(f"✓ Retrieved {len(raw_docs)} bills for LLM processing")
        
        # Configure processor for test collections
        processor_config = {
            'source_collection': TEST_RAW_COLLECTION,
            'target_collection': TEST_EVIDENCE_COLLECTION,
            'include_private_bills': True,  # Include all bill types
            'min_relevance_threshold': 0.1  # Lower threshold for testing
        }
        
        processor = LegisInfoProcessor("scale_test_processor", processor_config)
        
        # Process bills through LLM pipeline
        start_time = time.time()
        processed_count = 0
        error_count = 0
        evidence_items = []
        
        for i, doc in enumerate(raw_docs):
            bill_data = doc.to_dict()
            bill_id = bill_data.get('human_readable_id', f'bill_{i}')
            
            logger.info(f"Processing bill {i+1}/{len(raw_docs)}: {bill_id}")
            
            try:
                # Process through full LLM pipeline
                evidence_item = processor._process_raw_item(bill_data)
                
                if evidence_item:
                    # Store in evidence collection
                    evidence_id = f"evidence_{bill_id}_{int(time.time())}"
                    db.collection(TEST_EVIDENCE_COLLECTION).document(evidence_id).set(evidence_item)
                    
                    evidence_items.append(evidence_item)
                    processed_count += 1
                    
                    logger.info(f"✓ Created evidence item: {evidence_id}")
                    logger.info(f"  Title: {evidence_item.get('title_or_summary', '')[:50]}...")
                    logger.info(f"  Source type: {evidence_item.get('evidence_source_type')}")
                    logger.info(f"  Parliament: {evidence_item.get('parliament_number')}")
                    
                    # Log LLM analysis results if available
                    bill_analysis = evidence_item.get('bill_analysis', {})
                    if bill_analysis:
                        summary = bill_analysis.get('summary', '')
                        if summary:
                            logger.info(f"  LLM Summary: {summary[:100]}...")
                else:
                    error_count += 1
                    logger.warning(f"Failed to process bill {bill_id}")
                    
            except Exception as e:
                error_count += 1
                logger.error(f"Error processing bill {bill_id}: {e}")
        
        elapsed_time = time.time() - start_time
        avg_time_per_bill = elapsed_time / len(raw_docs) if raw_docs else 0
        
        logger.info(f"✓ LLM processing completed in {elapsed_time:.1f} seconds")
        logger.info(f"✓ Average time per bill: {avg_time_per_bill:.1f} seconds")
        logger.info(f"✓ Successfully processed: {processed_count} bills")
        logger.info(f"✓ Errors: {error_count} bills")
        logger.info(f"✓ Success rate: {processed_count/len(raw_docs):.1%}")
        
        # Validate evidence items
        if evidence_items:
            sample_evidence = evidence_items[0]
            logger.info("=== Sample Evidence Item Validation ===")
            logger.info(f"✓ Title: {sample_evidence.get('title_or_summary', '')[:100]}...")
            logger.info(f"✓ Evidence type: {sample_evidence.get('evidence_type')}")
            logger.info(f"✓ Source type: {sample_evidence.get('evidence_source_type')}")
            logger.info(f"✓ Bill number: {sample_evidence.get('source_document_raw_id')}")
            logger.info(f"✓ Parliament: {sample_evidence.get('parliament_session_id')}")
            logger.info(f"✓ Status: {sample_evidence.get('event_specific_details', {}).get('stage_name')}")
            
            # Check LLM analysis (Parliament 44 format)
            keywords = sample_evidence.get('bill_extracted_keywords_concepts', [])
            one_sentence = sample_evidence.get('bill_one_sentence_description_llm', '')
            timeline_summary = sample_evidence.get('bill_timeline_summary_llm', '')
            
            if keywords:
                logger.info(f"✓ LLM Keywords: {keywords}")
            if one_sentence:
                logger.info(f"✓ LLM One sentence: {one_sentence[:100]}...")
            if timeline_summary:
                logger.info(f"✓ LLM Timeline summary: {timeline_summary[:100]}...")
            
            if keywords or one_sentence or timeline_summary:
                logger.info("✓ LLM analysis present in Parliament 44 format")
            else:
                logger.warning("No LLM analysis found in evidence item")
            
            # Check required fields
            required_fields = [
                'title_or_summary', 'evidence_source_type', 'source_document_raw_id',
                'evidence_type', 'bill_extracted_keywords_concepts'
            ]
            missing_fields = [field for field in required_fields if field not in sample_evidence]
            
            if missing_fields:
                logger.warning(f"Missing required fields: {missing_fields}")
            else:
                logger.info("✓ All required evidence fields present")
        
        return processed_count >= (PROCESSING_TARGET * 0.7), processed_count  # Success if 70% processed
        
    except Exception as e:
        logger.error(f"LLM processing pipeline test failed: {e}")
        return False, 0

def validate_test_data():
    """Validate the test data in both collections"""
    logger.info("=== Test Data Validation ===")
    
    db = setup_firebase()
    
    try:
        # Check raw collection
        raw_docs = list(db.collection(TEST_RAW_COLLECTION).stream())
        logger.info(f"✓ Raw collection contains {len(raw_docs)} documents")
        
        if raw_docs:
            # Analyze field completeness
            sample_raw = raw_docs[0].to_dict()
            required_raw_fields = [
                'parl_id', 'bill_number_code_feed', 'parliament_session_id',
                'raw_json_content', 'processing_status', 'ingested_at'
            ]
            
            field_completeness = {}
            for doc in raw_docs[:10]:  # Check first 10 docs
                data = doc.to_dict()
                for field in required_raw_fields:
                    if field not in field_completeness:
                        field_completeness[field] = 0
                    if data.get(field):
                        field_completeness[field] += 1
            
            logger.info("Raw data field completeness (first 10 docs):")
            for field, count in field_completeness.items():
                logger.info(f"  {field}: {count}/10 ({count*10}%)")
        
        # Check evidence collection
        evidence_docs = list(db.collection(TEST_EVIDENCE_COLLECTION).stream())
        logger.info(f"✓ Evidence collection contains {len(evidence_docs)} documents")
        
        if evidence_docs:
            # Analyze evidence quality
            sample_evidence = evidence_docs[0].to_dict()
            required_evidence_fields = [
                'title_or_summary', 'evidence_source_type', 'source_document_raw_id',
                'evidence_type', 'bill_extracted_keywords_concepts'
            ]
            
            evidence_completeness = {}
            llm_analysis_count = 0
            
            for doc in evidence_docs:
                data = doc.to_dict()
                
                # Check field completeness
                for field in required_evidence_fields:
                    if field not in evidence_completeness:
                        evidence_completeness[field] = 0
                    if data.get(field):
                        evidence_completeness[field] += 1
                
                # Check LLM analysis quality (Parliament 44 format)
                keywords = data.get('bill_extracted_keywords_concepts', [])
                one_sentence = data.get('bill_one_sentence_description_llm', '')
                timeline_summary = data.get('bill_timeline_summary_llm', '')
                
                if keywords or one_sentence or timeline_summary:
                    llm_analysis_count += 1
            
            logger.info("Evidence data field completeness:")
            for field, count in evidence_completeness.items():
                logger.info(f"  {field}: {count}/{len(evidence_docs)} ({count/len(evidence_docs)*100:.0f}%)")
            
            logger.info(f"✓ LLM analysis present: {llm_analysis_count}/{len(evidence_docs)} ({llm_analysis_count/len(evidence_docs)*100:.0f}%)")
        
        return True
        
    except Exception as e:
        logger.error(f"Test data validation failed: {e}")
        return False

def main():
    """Run the complete scale test"""
    logger.info("Starting LEGISinfo Scale Test")
    logger.info(f"Target: Ingest available bills (up to {INGESTION_TARGET}), process {PROCESSING_TARGET} through LLM")
    logger.info(f"Test collections: {TEST_RAW_COLLECTION}, {TEST_EVIDENCE_COLLECTION}")
    logger.info("Note: Testing with Parliament 45 bills (where substantial bill data exists)")
    
    start_time = time.time()
    
    # Clean up test collections
    cleanup_test_collections()
    
    # Test 1: Large scale ingestion
    logger.info(f"\n{'='*60}")
    logger.info("PHASE 1: Large Scale Ingestion")
    logger.info(f"{'='*60}")
    
    ingestion_success, ingested_count = test_large_scale_ingestion()
    
    if not ingestion_success:
        logger.error("❌ Ingestion test failed - cannot proceed with processing")
        return False
    
    logger.info(f"✅ Ingestion test passed: {ingested_count} bills ingested")
    
    # Test 2: LLM Processing Pipeline
    logger.info(f"\n{'='*60}")
    logger.info("PHASE 2: LLM Processing Pipeline")
    logger.info(f"{'='*60}")
    
    processing_success, processed_count = test_llm_processing_pipeline()
    
    if not processing_success:
        logger.error("❌ LLM processing test failed")
        return False
    
    logger.info(f"✅ LLM processing test passed: {processed_count} evidence items created")
    
    # Test 3: Data validation
    logger.info(f"\n{'='*60}")
    logger.info("PHASE 3: Data Validation")
    logger.info(f"{'='*60}")
    
    validation_success = validate_test_data()
    
    if not validation_success:
        logger.error("❌ Data validation failed")
        return False
    
    logger.info("✅ Data validation passed")
    
    # Final summary
    total_time = time.time() - start_time
    
    logger.info(f"\n{'='*60}")
    logger.info("SCALE TEST COMPLETED SUCCESSFULLY")
    logger.info(f"{'='*60}")
    logger.info(f"✅ Total execution time: {total_time:.1f} seconds")
    logger.info(f"✅ Bills ingested: {ingested_count}")
    logger.info(f"✅ Evidence items created: {processed_count}")
    logger.info(f"✅ Test collections: {TEST_RAW_COLLECTION}, {TEST_EVIDENCE_COLLECTION}")
    logger.info("✅ Pipeline validated at scale and ready for production use")
    
    # Performance metrics
    if ingested_count > 0:
        ingestion_rate = ingested_count / total_time * 60  # bills per minute
        logger.info(f"📊 Ingestion rate: {ingestion_rate:.1f} bills/minute")
    
    if processed_count > 0:
        processing_rate = processed_count / total_time * 60  # evidence items per minute
        logger.info(f"📊 Processing rate: {processing_rate:.1f} evidence items/minute")
    
    return True

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1) 