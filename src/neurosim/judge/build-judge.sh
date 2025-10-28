#!/usr/bin/env bash
set -euo pipefail

IMAGE_NAME="neurosim-judge"
DOCKERFILE="Dockerfile"

# 1. Get a short-lived token for the build process
echo "[INFO] Getting GCP access token for build..."
if ! TOKEN=$(gcloud auth application-default print-access-token 2>/dev/null); then
    echo "[ERROR] Failed to get GCP access token. Please run 'gcloud auth application-default login' first."
    exit 1
fi

if [ -z "$TOKEN" ]; then
    echo "[ERROR] Empty access token received"
    exit 1
fi

# 2. Build the Docker image using a build secret
echo "[INFO] Building image: $IMAGE_NAME using secure build secret"
DOCKER_BUILDKIT=1 docker build \
    --build-arg GCLOUD_ACCESS_TOKEN="$TOKEN" \
    -t "$IMAGE_NAME" \
    -f "$DOCKERFILE" \
    .

echo "[INFO] Build completed successfully!"

# # Run the container with GCP credentials mounted (if arguments provided)
# if [ $# -gt 0 ]; then
#     echo "[INFO] Running container with credentials..."
#     docker run -it --rm \
#         -v "$HOME/.config/gcloud/application_default_credentials.json:/root/.config/gcloud/application_default_credentials.json:ro" \
#         -e GOOGLE_APPLICATION_CREDENTIALS=/root/.config/gcloud/application_default_credentials.json \
#         "$IMAGE_NAME" "$@"
# else
#     echo "[INFO] Build only mode - container not started"
# fi