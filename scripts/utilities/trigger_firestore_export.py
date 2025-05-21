#!/usr/bin/env python
# scripts/trigger_firestore_export.py

import os
import argparse
import logging
from dotenv import load_dotenv

from google.cloud import firestore_admin_v1
from google.api_core.operation import Operation
import google.auth

# --- Load Environment Variables ---
load_dotenv()
# --- End Load Environment Variables ---

# --- Logger Setup ---
logging.basicConfig(level=logging.INFO,
                    format='%(asctime)s - %(levelname)s - %(filename)s:%(lineno)d - %(message)s',
                    datefmt='%Y-%m-%d %H:%M:%S')
logger = logging.getLogger(__name__)
# --- End Logger Setup ---

def trigger_firestore_export(project_id: str, output_uri_prefix: str, collection_ids: list[str] = None):
    """
    Triggers a Firestore export operation.

    Args:
        project_id: The ID of the Google Cloud project.
        output_uri_prefix: The GCS path prefix where the export will be stored. 
                           Must start with "gs://". For example, "gs://your-bucket/backups/my-export-folder".
                           A timestamped subfolder will usually be created by Firestore under this prefix.
        collection_ids: A list of collection IDs to export. If None or empty, all collections are exported.
    """
    try:
        # Authenticate and get default credentials.
        # This works for local development if you've run `gcloud auth application-default login`.
        # It also works in GCP environments (e.g., Cloud Functions, Cloud Run, GCE) with service accounts.
        credentials, _ = google.auth.default(scopes=['https://www.googleapis.com/auth/cloud-platform', 'https://www.googleapis.com/auth/datastore'])
        
        admin_client = firestore_admin_v1.FirestoreAdminClient(credentials=credentials)

        database_name = f"projects/{project_id}/databases/(default)"
        
        # Ensure output_uri_prefix starts with gs://
        if not output_uri_prefix.startswith("gs://"):
            logger.error(f"Output URI prefix must start with 'gs://'. Provided: {output_uri_prefix}")
            raise ValueError("Output URI prefix must start with 'gs://'.")

        logger.info(f"Starting Firestore export for project '{project_id}'.")
        logger.info(f"Database: {database_name}")
        logger.info(f"Output GCS Prefix: {output_uri_prefix}")
        if collection_ids:
            logger.info(f"Collections to export: {', '.join(collection_ids)}")
        else:
            logger.info("Exporting all collections (full database).")

        request = firestore_admin_v1.ExportDocumentsRequest(
            name=database_name,
            output_uri_prefix=output_uri_prefix,
            collection_ids=collection_ids if collection_ids else [], # API expects a list, even if empty for full export
        )

        operation: Operation = admin_client.export_documents(request=request)

        logger.info(f"Export operation started. Operation name: {operation.operation.name}")
        logger.info("Waiting for export to complete (this may take a while)...")
        
        # operation.result() blocks until the operation is complete.
        # The timeout can be adjusted if needed, but default is usually sufficient.
        result = operation.result() 
        
        logger.info(f"Export completed successfully.")
        logger.info(f"Output URI Prefix from result: {result.output_uri_prefix}")
        if result.collection_ids:
             logger.info(f"Collections exported from result: {list(result.collection_ids)}")


    except google.auth.exceptions.DefaultCredentialsError as e:
        logger.critical("Could not determine default credentials. "
                        "Ensure you have authenticated via `gcloud auth application-default login` "
                        "or that the GOOGLE_APPLICATION_CREDENTIALS environment variable is set correctly.", exc_info=True)
    except Exception as e:
        logger.critical(f"An error occurred during the Firestore export process: {e}", exc_info=True)

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Trigger a Firestore export to Google Cloud Storage.")
    parser.add_argument("--project_id", required=True, help="Your Google Cloud Project ID.")
    parser.add_argument("--bucket_name", required=True, help="The GCS bucket name (e.g., 'my-firestore-backups').")
    parser.add_argument("--path_prefix", default="backups", help="Optional path prefix within the bucket (e.g., 'daily/promises_export'). Defaults to 'backups'. Firestore will create a timestamped folder under this.")
    # nargs='?' makes it optional, None if not present. nargs='*' would be an empty list if flag present but no args.
    # For explicit "export all" vs "default to promises", let's keep nargs='*' and handle None vs []
    parser.add_argument("--collection_ids", nargs='*', default=None, help="Optional. Space-separated list of collection IDs to export (e.g., promises users). If flag is used with no IDs, all collections are exported. If flag is omitted, defaults to 'promises' collection.")
    
    args = parser.parse_args()

    full_output_uri_prefix = f"gs://{args.bucket_name}"
    if args.path_prefix:
        full_output_uri_prefix += f"/{args.path_prefix.strip('/')}"

    logger.info(f"--- Firestore Export Utility --- ")
    
    collections_to_export = [] # Default to ALL if flag is present but empty

    if args.collection_ids is None: # Flag --collection_ids was not used at all
        logger.info("No --collection_ids flag used, defaulting to export the 'promises' collection.")
        collections_to_export = ["promises"]
    elif len(args.collection_ids) == 0: # Flag --collection_ids was used, but no specific IDs were provided (e.g. --collection_ids)
        logger.info("--collection_ids flag used with no specific IDs. Will export ALL collections.")
        collections_to_export = [] # Empty list means export all to the API
    else: # Flag --collection_ids was used with specific IDs
        collections_to_export = args.collection_ids
        logger.info(f"Exporting specified collections: {collections_to_export}")
        if "promises" not in collections_to_export:
            logger.warning("The 'promises' collection was not specified. " 
                           "This script is primarily intended for the 'promises' collection, but proceeding with specified IDs.")

    trigger_firestore_export(
        project_id=args.project_id,
        output_uri_prefix=full_output_uri_prefix,
        collection_ids=collections_to_export
    )

    logger.info(f"--- Firestore Export Utility Finished ---") 