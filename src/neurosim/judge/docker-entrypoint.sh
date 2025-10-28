#!/bin/bash
set -euo pipefail

# Check for EPISODE_NUMBER first, as it defines the working directory
if [ -z "${EPISODE_NUMBER:-}" ]; then
    echo "Error: EPISODE_NUMBER environment variable must be set." >&2
    exit 1
fi

EVAL_FOLDER="/tmp/${EPISODE_NUMBER}"
OUTPUT_FILE="/tmp/judge_results_${EPISODE_NUMBER}.json"

echo "🚀 Starting Neurosim Judge System for Episode: ${EPISODE_NUMBER}"
echo "   Evaluation Folder: ${EVAL_FOLDER}"

# Function to download data from a single episode path in GCS
download_gcs_data() {
    if [[ -n "${GCS_BUCKET_NAME:-}" && -n "${GCS_DATA_PATH:-}" ]]; then
        echo "📥 Downloading data for a single episode from GCS..."
        
        # Ensure the target directory exists
        mkdir -p "${EVAL_FOLDER}"
        
        # Pass eval_folder as an argument to the inline python script
        python3 -c "
import os
import sys
from google.cloud import storage
from pathlib import Path

bucket_name = os.environ.get('GCS_BUCKET_NAME')
data_path = os.environ.get('GCS_DATA_PATH')
project_id = os.environ.get('GCP_PROJECT_ID')
local_download_dir = Path(sys.argv[1]) # Read from command line arg

if bucket_name and data_path:
    client = storage.Client(project=project_id)
    bucket = client.bucket(bucket_name)

    if not data_path.endswith('/'):
        data_path += '/'

    blobs = bucket.list_blobs(prefix=data_path)
    for blob in blobs:
        if blob.name.endswith('/'):
            continue

        relative_path = blob.name[len(data_path):]
        local_file_path = local_download_dir / relative_path
        
        local_file_path.parent.mkdir(parents=True, exist_ok=True)
        
        blob.download_to_filename(str(local_file_path))
        print(f'Downloaded: {blob.name} -> {str(local_file_path)}')
" "${EVAL_FOLDER}" # Pass the folder as an argument

        # FIX: Rename plural 'results.zst' to singular 'result.zst' as expected by the script.
        echo "Fixing result filenames to match script expectations..."
        find "${EVAL_FOLDER}" -type f -name 'results.zst' -execdir mv {} result.zst \;
        echo "File renaming complete."
        
        if find "${EVAL_FOLDER}" -type f -print -quit | grep -q .; then
            echo "✅ Data downloaded successfully."
        else
            echo "⚠️  No files downloaded from GCS (prefix: ${GCS_DATA_PATH})."
        fi
    else
        echo "ℹ️  GCS_BUCKET_NAME or GCS_DATA_PATH not set, skipping data download"
    fi
}

# Function to run the judge evaluation for a single episode
run_judge() {
    echo "🔍 Running judge evaluation for episode..."
    echo "   Evaluation folder: $EVAL_FOLDER"
    echo "   Output: $OUTPUT_FILE"
    
    python3 evaluate_results.py \
        "$EVAL_FOLDER" \
        --output "$OUTPUT_FILE"
    
    echo "✅ Evaluation completed. Results for this episode are in: $OUTPUT_FILE"
}

# Function to upload the result
upload_result() {
    local gcs_path="${GCS_DATA_PATH}/llm_judge.json" # Append the desired filename

    echo "📤 Uploading results to GCS..."
    echo "   Source: $OUTPUT_FILE"
    echo "   Destination: gs://${GCS_BUCKET_NAME}/${gcs_path}"

    python3 upload_to_gcs.py "$OUTPUT_FILE" "$gcs_path"

    echo "✅ Results uploaded successfully."
}

# Main execution
main() {
    download_gcs_data
    run_judge
    upload_result
    
    echo "🎉 Neurosim Judge Job for this episode completed successfully!"
}

main
