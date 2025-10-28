# Environment Variables Reference

This document lists all environment variables used by Neurosim.

## Required Variables

### Google Cloud Storage

```bash
# Your GCS bucket name for storing evaluation results
GCS_BUCKET_NAME=your-gcs-bucket-name

# Path to your GCP service account JSON key file
# Create at: https://console.cloud.google.com/iam-admin/serviceaccounts
# Required permissions: Storage Object Admin
GOOGLE_APPLICATION_CREDENTIALS=/path/to/your/service-account-key.json
```

## Optional Variables

### Google Cloud Project

```bash
# Your GCP project ID
GCP_PROJECT_ID=your-gcp-project-id
```

### Firestore Configuration

```bash
# Firestore database name (default: "(default)")
FIRESTORE_DATABASE=(default)

# Firestore collection name for evaluation tracking
FIRESTORE_COLLECTION=evaluations
```

### LLM Judge Configuration

```bash
# OpenAI API key for GPT models
OPENAI_API_KEY=your_openai_api_key

# Google AI API key for Gemini models
GOOGLE_API_KEY=your_google_api_key

# Judge concurrency (default: 50)
JUDGE_MAX_CONCURRENCY=50

# Judge timeout per task in seconds (optional)
JUDGE_TASK_TIMEOUT_SECONDS=300
```

### Logging

```bash
# Log level: DEBUG, INFO, WARNING, ERROR, CRITICAL (default: INFO)
LOG_LEVEL=INFO
```

### Evaluation Parameters

```bash
# Job identifier
JOB_ID=example-job-001

# Task description
TASK=Navigate to example.com

# Task identifier
TASK_ID=task_001

# Browser channel: CHROME, CHROMIUM, MSEDGE
BROWSER=CHROME

# Episode number
EPISODE=0

# User identifier
USER_NAME=example_user

# Model to use
MODEL=gpt-4o

# Advanced settings (JSON string)
ADVANCED_SETTINGS={"max_steps": 50, "use_vision": true}
```

### Cloud Run

```bash
# Task index for parallel execution
CLOUD_RUN_TASK_INDEX=0

# Total number of tasks
CLOUD_RUN_TASK_COUNT=1
```

## Creating a .env File

Create a `.env` file in your project root:

```bash
# Copy the variables above and fill in your values
GCS_BUCKET_NAME=my-bucket
GOOGLE_APPLICATION_CREDENTIALS=/path/to/key.json
LOG_LEVEL=INFO
```

Then load it in your code:

```python
from dotenv import load_dotenv
load_dotenv()
```

Or export in your shell:

```bash
export GCS_BUCKET_NAME=my-bucket
export GOOGLE_APPLICATION_CREDENTIALS=/path/to/key.json
```

