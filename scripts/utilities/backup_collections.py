import argparse
from google.cloud import firestore_admin_v1
from google.api_core.operation import Operation
import google.auth
from datetime import datetime

def export_firestore_collection(project_id: str, bucket_name: str, collection_ids: list[str] = None):
    # Auth + client
    credentials, _ = google.auth.default()
    client = firestore_admin_v1.FirestoreAdminClient(credentials=credentials)

    # Unique export path with timestamp
    timestamp = datetime.utcnow().strftime("%Y%m%dT%H%M%SZ")
    output_uri_prefix = f"gs://{bucket_name}/backups/{timestamp}"

    # Path to Firestore default DB
    database_name = f"projects/{project_id}/databases/(default)"

    # Trigger export
    operation: Operation = client.export_documents(
        request={
            "name": database_name,
            "output_uri_prefix": output_uri_prefix,
            "collection_ids": collection_ids or [],
        }
    )

    print(f"📦 Export started: {operation.operation.name}")
    print(f"🪣 Exporting to: {output_uri_prefix}")
    print("⏳ Waiting for export to complete...")
    result = operation.result()
    print("✅ Export complete:", result)



if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Export Firestore collections to GCS.")
    parser.add_argument(
        "--collections",
        type=str,
        help="Comma-separated list of collection IDs to export, or 'all' to export the entire database.",
        required=True
    )
    parser.add_argument(
        "--project",
        type=str,
        default="promisetrackerapp",
        help="GCP project ID"
    )
    parser.add_argument(
        "--bucket",
        type=str,
        default="promisetracker-backup",
        help="GCS bucket name (without gs://)"
    )

    args = parser.parse_args()

    if args.collections.lower() == "all":
        collection_ids = None
    else:
        collection_ids = [c.strip() for c in args.collections.split(",")]

    export_firestore_collection(
        project_id=args.project,
        bucket_name=args.bucket,
        collection_ids=collection_ids
    )