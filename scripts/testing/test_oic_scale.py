#!/usr/bin/env python3
"""
Orders in Council Scale Test

Test script to validate the OIC ingestion and processing pipeline at scale.
Tests both ingestion from orders-in-council.canada.ca and LLM processing.
"""

import sys
import logging
import time
from datetime import datetime, timezone
from pathlib import Path

# Add the PromiseTracker directory to Python path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

# Now import our modules
from pipeline.stages.ingestion.orders_in_council import OrdersInCouncilIngestion
from pipeline.stages.processing.orders_in_council_processor import OrdersInCouncilProcessor
import firebase_admin
from firebase_admin import firestore
from google.cloud import firestore as firestore_client

# Test configuration
INGESTION_TARGET = 10  # Target number of OICs to ingest
PROCESSING_TARGET = 5  # Target number to process through LLM

# Collection names for testing
TEST_RAW_COLLECTION = "test_raw_orders_in_council"
TEST_EVIDENCE_COLLECTION = "test_evidence_items"

def setup_logging():
    """Configure logging for the test"""
    logging.basicConfig(
        level=logging.INFO,  # Back to INFO level for cleaner output
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    return logging.getLogger(__name__)

def test_oic_ingestion(logger):
    """Test OIC ingestion at scale"""
    logger.info("=== Phase 1: OIC Ingestion Test ===")
    
    # Initialize ingestion job with test collection
    config = {
        'collection_name': TEST_RAW_COLLECTION,
        'max_items_per_run': INGESTION_TARGET,
        'start_attach_id': 47280,  # Recent OICs based on production data
        'max_consecutive_misses': 50,  # Use the same default as the deprecated script
        'iteration_delay_seconds': 1  # Faster for testing
    }
    
    ingestion_job = OrdersInCouncilIngestion("test_oic_ingestion", config)
    
    start_time = time.time()
    
    try:
        logger.info("Starting OIC ingestion...")
        
        # Fetch raw items from scraping
        raw_items = ingestion_job._fetch_new_items()
        
        if not raw_items:
            logger.error("No items fetched from ingestion")
            return False, 0
        
        fetched_count = len(raw_items)
        logger.info(f"✓ Fetched {fetched_count} OICs from scraping")
        
        # Process and store items
        db = firestore.client()
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
                        # Store in test collection (don't store _doc_id in the document)
                        db.collection(TEST_RAW_COLLECTION).document(doc_id).set(processed_item)
                        stored_count += 1
                        
                        if (i + 1) % 5 == 0:
                            logger.info(f"Progress: {i + 1}/{fetched_count} OICs processed")
                    else:
                        error_count += 1
                        logger.warning(f"Could not generate ID for OIC {i + 1}")
                else:
                    error_count += 1
                    logger.warning(f"Could not process OIC {i + 1}")
                    
            except Exception as e:
                error_count += 1
                logger.error(f"Error processing OIC {i + 1}: {e}")
        
        end_time = time.time()
        duration = end_time - start_time
        rate = stored_count / duration * 60 if duration > 0 else 0
        
        logger.info(f"✅ Ingestion completed in {duration:.1f} seconds")
        logger.info(f"✅ Ingested {stored_count} OICs ({rate:.1f} OICs/minute)")
        logger.info(f"✅ Success rate: {stored_count/fetched_count:.1%}" if fetched_count > 0 else "")
        
        # Validate data quality
        success = validate_ingested_data(logger, stored_count)
        
        return success, stored_count
        
    except Exception as e:
        logger.error(f"❌ Ingestion failed: {e}")
        return False, 0

def test_oic_processing(logger):
    """Test OIC processing through LLM pipeline"""
    logger.info("=== Phase 2: OIC Processing Test ===")
    
    # Initialize processing job with test collections
    config = {
        'source_collection': TEST_RAW_COLLECTION,
        'target_collection': TEST_EVIDENCE_COLLECTION,
        'max_items_per_run': PROCESSING_TARGET
    }
    
    processor = OrdersInCouncilProcessor("test_oic_processing", config)
    
    start_time = time.time()
    
    try:
        logger.info(f"Fetching OICs from {TEST_RAW_COLLECTION} for processing...")
        
        # Get OICs from test collection for processing
        db = firestore.client()
        raw_docs = list(db.collection(TEST_RAW_COLLECTION).limit(PROCESSING_TARGET).stream())
        
        if len(raw_docs) < PROCESSING_TARGET:
            logger.warning(f"Only {len(raw_docs)} OICs available, processing all of them")
        
        logger.info(f"✓ Retrieved {len(raw_docs)} OICs for LLM processing")
        
        # Process OICs through LLM pipeline
        processed_count = 0
        error_count = 0
        evidence_items = []
        
        for i, doc in enumerate(raw_docs):
            oic_data = doc.to_dict()
            oic_data['_doc_id'] = doc.id  # Add document ID for status updates
            oic_id = oic_data.get('raw_oic_id', f'oic_{i}')
            
            logger.info(f"Processing OIC {i+1}/{len(raw_docs)}: {oic_id}")
            
            try:
                # Process through full LLM pipeline
                evidence_item = processor._process_raw_item(oic_data)
                
                if evidence_item:
                    # Use the evidence_id that was generated by the processor
                    evidence_id = evidence_item.get('evidence_id', f"evidence_{oic_id}_{int(time.time())}")
                    db.collection(TEST_EVIDENCE_COLLECTION).document(evidence_id).set(evidence_item)
                    
                    evidence_items.append(evidence_item)
                    processed_count += 1
                    
                    logger.info(f"✓ Created evidence item: {evidence_id}")
                    logger.info(f"  Title: {evidence_item.get('title_or_summary', '')[:50]}...")
                    logger.info(f"  Relevance: {evidence_item.get('potential_relevance_score')}")
                    
                else:
                    error_count += 1
                    logger.warning(f"Failed to process OIC {oic_id}")
                    
            except Exception as e:
                error_count += 1
                logger.error(f"Error processing OIC {oic_id}: {e}")
        
        end_time = time.time()
        duration = end_time - start_time
        rate = processed_count / duration * 60 if duration > 0 else 0
        
        logger.info(f"✅ Processing completed in {duration:.1f} seconds")
        logger.info(f"✅ Processed {processed_count} evidence items ({rate:.1f} items/minute)")
        logger.info(f"✅ Success rate: {processed_count/len(raw_docs):.1%}" if raw_docs else "")
        
        # Validate evidence quality
        success = validate_evidence_data(logger, processed_count)
        
        return success, processed_count
        
    except Exception as e:
        logger.error(f"❌ Processing failed: {e}")
        return False, 0

def validate_ingested_data(logger, expected_count):
    """Validate the quality of ingested OIC data"""
    logger.info("=== Ingested Data Validation ===")
    
    try:
        # Connect to Firebase
        db = firestore.client()
        
        # Get ingested documents
        docs = list(db.collection(TEST_RAW_COLLECTION).limit(50).stream())
        
        if not docs:
            logger.error("❌ No ingested documents found")
            return False
        
        logger.info(f"Found {len(docs)} ingested OICs")
        
        # Validate field completeness
        sample_doc = docs[0].to_dict()
        required_fields = [
            'attach_id', 'oic_number_full_raw', 'full_text_scraped', 
            'source_url_oic_detail_page', 'ingested_at', 'evidence_processing_status'
        ]
        
        field_completeness = {}
        for doc in docs:
            data = doc.to_dict()
            for field in required_fields:
                if field not in field_completeness:
                    field_completeness[field] = 0
                if data.get(field):
                    field_completeness[field] += 1
        
        logger.info("=== Field Completeness ===")
        all_complete = True
        for field, count in field_completeness.items():
            percentage = (count / len(docs)) * 100
            status = "✓" if percentage >= 90 else "⚠"
            logger.info(f"{status} {field}: {percentage:.1f}% ({count}/{len(docs)})")
            if percentage < 90:
                all_complete = False
        
        # Show sample data
        logger.info("=== Sample OIC ===")
        logger.info(f"✓ Attach ID: {sample_doc.get('attach_id')}")
        logger.info(f"✓ OIC Number: {sample_doc.get('oic_number_full_raw')}")
        logger.info(f"✓ Title: {sample_doc.get('title_or_summary_raw', '')[:100]}...")
        logger.info(f"✓ Parliament: {sample_doc.get('parliament_session_id_assigned')}")
        logger.info(f"✓ Status: {sample_doc.get('evidence_processing_status')}")
        
        return all_complete and len(docs) >= (expected_count * 0.7)
        
    except Exception as e:
        logger.error(f"❌ Validation failed: {e}")
        return False

def validate_evidence_data(logger, expected_count):
    """Validate the quality of processed evidence data"""
    logger.info("=== Evidence Data Validation ===")
    
    try:
        # Connect to Firebase
        db = firestore.client()
        
        # Get evidence documents - use the correct source type
        evidence_docs = list(db.collection(TEST_EVIDENCE_COLLECTION).where(
            filter=firestore_client.FieldFilter('evidence_source_type', '==', 'OrderInCouncil (PCO)')
        ).limit(50).stream())
        
        if not evidence_docs:
            logger.error("❌ No evidence items found")
            return False
        
        logger.info(f"Found {len(evidence_docs)} evidence items")
        
        # Validate field completeness
        sample_evidence = evidence_docs[0].to_dict()
        required_evidence_fields = [
            'title_or_summary', 'evidence_source_type', 'source_document_raw_id',
            'key_concepts', 'potential_relevance_score', 'description_or_details'
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
            
            # Check LLM analysis quality
            if (data.get('key_concepts') and 
                data.get('potential_relevance_score') and 
                data.get('description_or_details')):
                llm_analysis_count += 1
        
        logger.info("=== Evidence Field Completeness ===")
        all_complete = True
        for field, count in evidence_completeness.items():
            percentage = (count / len(evidence_docs)) * 100
            status = "✓" if percentage >= 90 else "⚠"
            logger.info(f"{status} {field}: {percentage:.1f}% ({count}/{len(evidence_docs)})")
            if percentage < 90:
                all_complete = False
        
        # LLM analysis coverage
        llm_percentage = (llm_analysis_count / len(evidence_docs)) * 100
        logger.info(f"✓ Complete LLM analysis: {llm_percentage:.1f}% ({llm_analysis_count}/{len(evidence_docs)})")
        
        # Show sample evidence
        logger.info("=== Sample Evidence Item ===")
        logger.info(f"✓ Title: {sample_evidence.get('title_or_summary', '')[:100]}...")
        logger.info(f"✓ Source type: {sample_evidence.get('evidence_source_type')}")
        logger.info(f"✓ OIC ID: {sample_evidence.get('source_document_raw_id')}")
        logger.info(f"✓ Parliament: {sample_evidence.get('parliament_session_id')}")
        logger.info(f"✓ Relevance: {sample_evidence.get('potential_relevance_score')}")
        
        # Check LLM analysis
        concepts = sample_evidence.get('key_concepts', [])
        departments = sample_evidence.get('linked_departments', [])
        logger.info(f"✓ Key concepts: {len(concepts)} concepts")
        logger.info(f"✓ Departments: {len(departments)} departments")
        
        if concepts:
            logger.info(f"  - Sample concepts: {', '.join(concepts[:3])}")
        
        # Check for important evidence fields (not the raw collection fields)
        evidence_fields = [
            'evidence_id', 'title_or_summary', 'evidence_source_type', 
            'key_concepts', 'potential_relevance_score'
        ]
        missing_fields = [field for field in evidence_fields if field not in sample_evidence]
        
        if missing_fields:
            logger.warning(f"Missing evidence fields: {missing_fields}")
        else:
            logger.info("✓ All required evidence fields present")
        
        # Success criteria: reasonable completeness and analysis quality
        return (len(evidence_docs) >= (expected_count * 0.6) and 
                all_complete and 
                llm_percentage >= 50)  # At least 50% should have complete LLM analysis
        
    except Exception as e:
        logger.error(f"❌ Evidence validation failed: {e}")
        return False

def test_processing_status_updates(logger):
    """Test that processing status is properly updated"""
    logger.info("=== Processing Status Check ===")
    
    try:
        # Connect to Firebase
        db = firestore.client()
        
        # Check processing status updates
        processed_docs = list(db.collection(TEST_RAW_COLLECTION).where(
            filter=firestore_client.FieldFilter('evidence_processing_status', '==', 'evidence_created')
        ).limit(5).stream())
        
        for doc in processed_docs:
            data = doc.to_dict()
            oic_number = data.get('oic_number_full_raw', 'unknown')
            status = data.get('evidence_processing_status')
            model_name = data.get('llm_model_name_last_attempt', 'none')
            logger.info(f"OIC {oic_number}: Status={status}, Model={model_name}")
        
        return len(processed_docs) > 0
        
    except Exception as e:
        logger.error(f"❌ Status check failed: {e}")
        return False

def cleanup_test_data(logger):
    """Clean up test collections"""
    logger.info("=== Cleanup Test Data ===")
    
    try:
        # Connect to Firebase
        db = firestore.client()
        
        # Delete test documents
        for collection_name in [TEST_RAW_COLLECTION, TEST_EVIDENCE_COLLECTION]:
            docs = db.collection(collection_name).limit(100).stream()
            deleted_count = 0
            for doc in docs:
                doc.reference.delete()
                deleted_count += 1
            
            if deleted_count > 0:
                logger.info(f"✓ Deleted {deleted_count} documents from {collection_name}")
        
    except Exception as e:
        logger.warning(f"⚠ Cleanup failed: {e}")

def main():
    """Main test execution"""
    logger = setup_logging()
    
    # Initialize Firebase if not already done
    try:
        if not firebase_admin._apps:
            firebase_admin.initialize_app()
        logger.info("Firebase initialized successfully")
    except Exception as e:
        logger.error(f"Failed to initialize Firebase: {e}")
        return 1
    
    logger.info("🚀 Starting Orders in Council Pipeline Scale Test")
    logger.info(f"Target: {INGESTION_TARGET} ingestion, {PROCESSING_TARGET} processing")
    
    # Phase 1: Test ingestion
    ingestion_success, ingested_count = test_oic_ingestion(logger)
    
    if not ingestion_success:
        logger.error("❌ Ingestion test failed. Stopping.")
        return 1
    
    # Phase 2: Test processing
    processing_success, processed_count = test_oic_processing(logger)
    
    if not processing_success:
        logger.error("❌ Processing test failed")
        return 1
    
    # Phase 3: Test status updates
    status_success = test_processing_status_updates(logger)
    
    # Summary
    logger.info("=== FINAL RESULTS ===")
    logger.info(f"✅ Ingestion: {ingested_count} OICs")
    logger.info(f"✅ Processing: {processed_count} evidence items")
    logger.info(f"✅ Status tracking: {'Working' if status_success else 'Issues'}")
    logger.info("✅ Orders in Council pipeline validated successfully!")
    
    # Cleanup (optional - comment out to keep test data)
    # cleanup_test_data(logger)
    
    return 0

if __name__ == "__main__":
    exit(main()) 