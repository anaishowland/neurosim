# neurosim

[![Tag](https://img.shields.io/github/v/tag/ParadigmShift-AI-Corp/neurosim?sort=semver)](https://github.com/ParadigmShift-AI-Corp/neurosim/tags)
[![License](https://img.shields.io/github/license/ParadigmShift-AI-Corp/neurosim)](https://github.com/ParadigmShift-AI-Corp/neurosim/blob/main/LICENSE)
[![Python](https://img.shields.io/badge/python-%3E%3D3.11-blue)](https://www.python.org/downloads/)
[![Registry](https://img.shields.io/badge/registry-GAR%20neuro--deploy-orange)](https://us-west1-python.pkg.dev/evaluation-deployment/neuro-deploy/)
[![Status](https://img.shields.io/badge/status-internal%20use%20only-red)](https://github.com/ParadigmShift-AI-Corp/neurosim/blob/main/LICENSE)

Neurosim: core primitives and evaluation utilities.

## Installation

Build from source:

```bash
python -m pip install --upgrade build
python -m build
# Then install the wheel that appears in dist/
```

Alternatively, using uv/Makefile:

```bash
uv build
# or
make build
```

## Usage

```python
from neurosim.evaluation import Evaluation
from neurosim.core.pipeline import PipelineDB
from neurosim.core.storage import GCSUploader

evaluation = Evaluation()
db = PipelineDB()

# Optional: upload a JSON payload to GCS (requires `pip install neurosim[gcs]`)
# Ensure `GCS_BUCKET_NAME` is set in your environment or pass bucket_name to GCSUploader(...)
uploader = GCSUploader()
uri = uploader.upload_json("path/to/object.json", {"ok": True})
print(uri)
```

## Examples

### Run the NotteEvaluation demo script

- You must run from the `examples/NotteEvaluation` directory.
- Requires an `.env` file with at least `GCS_BUCKET_NAME` set (used for saving results/screenshots to GCS). Ensure Google Cloud auth is configured (e.g., set `GOOGLE_APPLICATION_CREDENTIALS` or use `gcloud auth application-default login`).

Example `examples/.env`:

```bash
# Required
GCS_BUCKET_NAME=your-gcs-bucket
GOOGLE_APPLICATION_CREDENTIALS=
FIRESTORE_COLLECTION=
GCP_PROJECT_ID=
FIRESTORE_DATABASE=

# Optional
LOG_LEVEL=INFO
JOB_ID=test-job-notte
TASK="open apple.com"
TASK_ID=task_001
BROWSER=CHROME
EPISODE=0
USER_NAME=userid
MODEL=gemini-2.5-flash-preview-05-20
ADVANCED_SETTINGS='{"max_steps": 10, "use_vision": true}'
```

```bash
cd examples/NotteEvaluation
bash scripts/basic.sh
```

Optional: customize via environment variables (either export them in your shell or place them in `examples/.env`). For example:

```bash
export TASK="open apple.com"
export MODEL="gemini-2.5-flash-preview-05-20"
bash scripts/basic.sh
```

The script will also load variables from an `.env` file if present (set `ENV_FILE=/absolute/path/to/.env` to override).

## Development

- Source code lives under `src/` using the modern "src layout".
- Build backend is Hatchling via `pyproject.toml`.

### Docker

Build the sentinel monitor Docker image:

```bash
make sentinel
```

This builds a Docker image (`neurosim-monitor`) for the job monitoring service with Google Cloud authentication support.

## Contributing

See `CONTRIBUTING.md` for guidelines on developing, testing, and opening pull requests.

## Publishing (private registry)

- Requires `uv` and `gcloud` on PATH
- Authenticate with Google Cloud (Application Default Credentials):

```bash
gcloud auth application-default login
```

- Publish to the configured uv index (defaults to `neuro-deploy` from `pyproject.toml`):

```bash
make publish
```

- Or run the script directly:

```bash
scripts/publish.sh
```

- Override the index name if needed:

```bash
UV_INDEX_NAME=neuro-deploy make publish
# or
UV_INDEX_NAME=neuro-deploy scripts/publish.sh
```

- Pass extra flags through to `uv publish`:

```bash
scripts/publish.sh --no-build
```

## License

Paradigm Shift AI Internal Use Only. See `LICENSE` for terms.
