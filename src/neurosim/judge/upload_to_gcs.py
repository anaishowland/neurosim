"""
Minimal GCS Uploader Script

This script uploads a single local file to a specified Google Cloud Storage bucket and path.
It is designed to be called from a shell script within a container.

Usage:
    python upload_to_gcs.py <local_file_path> <gcs_destination_path>

Environment Variables:
    - GCS_BUCKET_NAME: The name of the GCS bucket.
    - GCP_PROJECT_ID: The GCP project ID (required for authentication with user credentials).
"""
import os
import sys
import logging
from pathlib import Path
from google.cloud import storage

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def upload_file_to_gcs(local_file_path: str, gcs_destination_path: str):
    """Uploads a file to the bucket."""
    bucket_name = os.getenv("GCS_BUCKET_NAME")
    project_id = os.getenv("GCP_PROJECT_ID")

    if not bucket_name:
        logger.error("GCS_BUCKET_NAME environment variable not set. Cannot upload.")
        sys.exit(1)

    if not Path(local_file_path).is_file():
        logger.error(f"Local file not found at: {local_file_path}")
        sys.exit(1)

    try:
        storage_client = storage.Client(project=project_id)
        bucket = storage_client.bucket(bucket_name)
        blob = bucket.blob(gcs_destination_path)

        blob.upload_from_filename(local_file_path)

        logger.info(f"File {local_file_path} uploaded to gs://{bucket_name}/{gcs_destination_path}")
    except Exception as e:
        logger.error(f"Failed to upload {local_file_path} to GCS: {e}")
        sys.exit(1)

if __name__ == "__main__":
    if len(sys.argv) != 3:
        print("Usage: python upload_to_gcs.py <local_file_path> <gcs_destination_path>")
        sys.exit(1)

    local_path = sys.argv[1]
    gcs_path = sys.argv[2]
    
    upload_file_to_gcs(local_path, gcs_path)
