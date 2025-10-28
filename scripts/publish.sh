#!/usr/bin/env bash
set -euo pipefail

# Publish to the uv index defined in pyproject.toml
# Default index name comes from [[tool.uv.index]] name in pyproject: "neuro-deploy"
INDEX_NAME=${UV_INDEX_NAME:-neuro-deploy}

command -v uv >/dev/null 2>&1 || {
  echo "Error: uv is not installed or not on PATH." >&2
  echo "Install: curl -LsSf https://astral.sh/uv/install.sh | sh" >&2
  exit 1
}

command -v gcloud >/dev/null 2>&1 || {
  echo "Error: gcloud is not installed or not on PATH." >&2
  echo "Install the Google Cloud SDK and authenticate with: gcloud auth application-default login" >&2
  exit 1
}

# Acquire short-lived access token from ADC
if ! ARTIFACT_REGISTRY_TOKEN=$(gcloud auth application-default print-access-token 2>/dev/null); then
  echo "Error: failed to obtain access token. Run: gcloud auth application-default login" >&2
  exit 1
fi

export UV_PUBLISH_USERNAME=oauth2accesstoken
export UV_PUBLISH_PASSWORD="${ARTIFACT_REGISTRY_TOKEN}"

echo "Publishing with uv to index '${INDEX_NAME}'..."
uv publish --index "${INDEX_NAME}" "$@"


