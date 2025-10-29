# Neurosim

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python](https://img.shields.io/badge/python-%3E%3D3.11-blue)](https://www.python.org/downloads/)

**Neurosim** is a Python framework for building, running, and evaluating AI agent systems. It provides core primitives for agent evaluation, cloud storage integration, and an LLM-as-a-judge system for automated scoring.

**Created by**: Anais Howland, Ashwin Thinnappan, Vaibhav Gupta at Paradigm Shift AI

## Architecture Overview

```
┌─────────────────────────────────────────────────┐
│         Your Agent Implementation               │
│         (extends Evaluation class)              │
│                                                 │
│  async def run() -> AgentResult                │
│  def compute_steps()                           │
│  def compute_tokens()                          │
└─────────────────────────────────────────────────┘
                    │
                    ▼
┌─────────────────────────────────────────────────┐
│           Neurosim Framework                    │
│  ┌───────────────────────────────────────────┐ │
│  │  Evaluation Base Class                    │ │
│  │  • execute() orchestration                │ │
│  │  • CLI argument parsing                   │ │
│  │  • Result persistence                     │ │
│  └───────────────────────────────────────────┘ │
│  ┌───────────────────────────────────────────┐ │
│  │  GCSUploader                              │ │
│  │  • upload_json() - Results (zstd)         │ │
│  │  • upload_png() - Screenshots             │ │
│  └───────────────────────────────────────────┘ │
│  ┌───────────────────────────────────────────┐ │
│  │  LLM Judge                                │ │
│  │  • Score: 0-100 (≥70 = success)           │ │
│  │  • Reasoning & suggestions                │ │
│  └───────────────────────────────────────────┘ │
└─────────────────────────────────────────────────┘
                    │
                    ▼
┌─────────────────────────────────────────────────┐
│        Google Cloud Storage                     │
│  results/{user}/{job}/{episode}/{task}/        │
│    ├── result.json.zst (compressed)            │
│    └── screenshot_*.png                        │
└─────────────────────────────────────────────────┘
```

## Features

- **Agent Evaluation Framework**: Abstract base class for implementing custom agent evaluations
- **Cloud Storage Integration**: Upload agent results, screenshots, and artifacts to Google Cloud Storage (GCS)
- **LLM Judge System**: Automated evaluation of agent performance using GPT or Gemini models
- **Result Management**: Structured result format with Zstandard compression support
- **Firestore Integration**: Track evaluation status and metrics
- **Monitoring**: Real-time monitoring of agent execution jobs

## Table of Contents

- [Installation](#installation)
- [Quick Start](#quick-start)
- [Core Components](#core-components)
- [Usage Examples](#usage-examples)
- [LLM Judge](#llm-judge)
- [Configuration](#configuration)
- [Development](#development)
- [Contributing](#contributing)
- [License](#license)
- [Citation](#citation)

## Installation

### Prerequisites

- Python 3.11 or higher
- Google Cloud Platform account (for GCS storage features)
- Google Cloud SDK (optional, for GCS authentication)

### Install from Source

```bash
# Clone the repository
git clone https://github.com/anaishowland/neurosim.git
cd neurosim

# Create virtual environment
python3 -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate

# Install the package
pip install -e .

# Install with optional dependencies
pip install -e ".[core]"      # Core evaluation features
pip install -e ".[judge]"     # LLM judge system
pip install -e ".[monitor]"   # Job monitoring features
```

### Using uv (Recommended)

```bash
# Install uv (if not already installed)
curl -LsSf https://astral.sh/uv/install.sh | sh

# Create virtual environment and install
uv venv --python python3.11
source .venv/bin/activate
uv pip install -e ".[core,judge,monitor]"
```

## Quick Start

### 1. Set Up Environment Variables

Create a `.env` file in your project:

```bash
# Required for GCS storage
GCS_BUCKET_NAME=your-gcs-bucket-name
GOOGLE_APPLICATION_CREDENTIALS=/path/to/your/service-account-key.json

# Optional: Firestore configuration
GCP_PROJECT_ID=your-gcp-project-id
FIRESTORE_DATABASE=(default)
FIRESTORE_COLLECTION=evaluations

# Optional: Logging
LOG_LEVEL=INFO
```

### 2. Authenticate with Google Cloud

```bash
# Option 1: Using service account key
export GOOGLE_APPLICATION_CREDENTIALS=/path/to/service-account-key.json

# Option 2: Using gcloud CLI
gcloud auth application-default login
```

### 3. Create Your First Evaluation

```python
from neurosim.evaluation import Evaluation
from neurosim.utils.models import EvaluationRequest, AgentResult

class MyAgentEvaluation(Evaluation):
    def __init__(self, request: EvaluationRequest):
        super().__init__(request)
        self.agent_name = "MyAgent"
        self.agent_version = "1.0.0"
    
    def get_llm(self):
        return "gpt-4"
    
    async def run(self) -> AgentResult:
        # Implement your agent logic here
        self.result.success = True
        self.result.results = "Task completed successfully"
        return self.result
    
    def compute_steps(self):
        # Process agent steps/trajectory
        self.result.steps = []
    
    def compute_tokens(self):
        # Track token usage
        self.result.tokens = [{"prompt_tokens": 100, "completion_tokens": 50}]

# Run evaluation
import asyncio

request = EvaluationRequest(
    userid="user123",
    model="gpt-4",
    jobid="job001",
    task="Open google.com and search for 'AI agents'",
    taskid="task001",
    browser_channel="chrome",
    episode=0,
    advanced_settings={},
    bucket_name="your-bucket"
)

eval_instance = MyAgentEvaluation(request)
asyncio.run(eval_instance.execute())
```

## Core Components

### 1. Evaluation Base Class

The `Evaluation` abstract class provides the foundation for implementing agent evaluations:

```python
from neurosim.evaluation import Evaluation

class YourEvaluation(Evaluation):
    async def run(self) -> AgentResult:
        """Execute the agent task"""
        pass
    
    def get_llm(self):
        """Return the LLM model identifier"""
        pass
    
    def compute_steps(self):
        """Process agent steps/trajectory"""
        pass
    
    def compute_tokens(self):
        """Calculate token usage"""
        pass
```

### 2. GCS Storage

Upload evaluation results and screenshots to Google Cloud Storage:

```python
from neurosim.core.storage import GCSUploader

uploader = GCSUploader(bucket_name="your-bucket")

# Upload JSON results (with optional compression)
uri = uploader.upload_json(
    blob_path="results/task_001/result.json",
    data={"success": True, "score": 95},
    compress_zstd=True,
    zstd_level=3
)

# Upload screenshots
with open("screenshot.png", "rb") as f:
    uri = uploader.upload_png(
        data=f.read(),
        blob_path="results/task_001/screenshot.png"
    )
```

### 3. Data Models

Structured data models using Pydantic:

```python
from neurosim.utils.models import (
    EvaluationRequest,    # Input configuration
    AgentResult,          # Evaluation output
    AgentErrors,          # Error tracking
    EvaluationConfig      # Runtime config
)
```

## Usage Examples

### Running the Notte Example

```bash
cd examples/NotteEvaluation

# Set up environment
cp .env.example .env
# Edit .env with your GCS bucket and credentials

# Run the evaluation
bash scripts/basic.sh
```

### Custom Evaluation with CLI

```python
# your_eval.py
from neurosim.evaluation import Evaluation

class CustomEvaluation(Evaluation):
    # ... implementation ...
    pass

if __name__ == "__main__":
    import asyncio
    eval = CustomEvaluation.from_cli()
    asyncio.run(eval.execute())
```

Run from command line:

```bash
python your_eval.py \
    --jobId job_123 \
    --task "Navigate to example.com" \
    --taskId task_001 \
    --user user_001 \
    --episode 0 \
    --model gpt-4 \
    --advanced_settings '{"max_steps": 50}'
```

## LLM Judge

Evaluate agent performance automatically using GPT or Gemini models.

### Judge System Overview

The LLM judge analyzes agent execution results and assigns a score (0-100) with detailed reasoning:
- **Score ≥70**: Success
- **Score <70**: Failure

### Running the Judge

```bash
# Set API key
export OPENAI_API_KEY=your_openai_key
# or
export GOOGLE_API_KEY=your_google_key

# Run judge on evaluation results
export JUDGE_MAX_CONCURRENCY=50
python -m neurosim.judge.evaluate_results \
    /path/to/evaluation/folder \
    --model gpt-4o \
    --max-images 10 \
    --output llm_judge.json
```

### Judge Output

```json
{
  "task_001": {
    "score": 85,
    "success": true,
    "reasoning": "Agent successfully completed the task...",
    "issues": ["minor_navigation_delay"],
    "suggestions": ["Optimize element selection"]
  }
}
```

## Configuration

### Environment Variables

| Variable | Required | Description |
|----------|----------|-------------|
| `GCS_BUCKET_NAME` | Yes | Google Cloud Storage bucket name |
| `GOOGLE_APPLICATION_CREDENTIALS` | Yes* | Path to GCP service account key JSON |
| `GCP_PROJECT_ID` | No | GCP project ID for Firestore |
| `FIRESTORE_DATABASE` | No | Firestore database name (default: `(default)`) |
| `LOG_LEVEL` | No | Logging level: DEBUG, INFO, WARNING, ERROR (default: INFO) |
| `OPENAI_API_KEY` | No** | Required for OpenAI judge models |
| `GOOGLE_API_KEY` | No** | Required for Gemini judge models |

\* Or use `gcloud auth application-default login`  
\** Required when using LLM judge

## Development

### Building from Source

```bash
# Install build tools
pip install build wheel hatchling

# Build distribution
python -m build
# or
make build
```

### Running Tests

```bash
# Install test dependencies
pip install pytest pytest-asyncio pytest-cov

# Run tests
pytest

# With coverage
pytest --cov=src/neurosim --cov-report=html
```

### Code Quality

```bash
# Format code
black src/ examples/

# Sort imports
isort src/ examples/

# Type checking
mypy src/neurosim
```

## Contributing

We welcome contributions! Please see [CONTRIBUTING.md](CONTRIBUTING.md) for guidelines.

### Quick Contribution Guide

1. Fork the repository
2. Create a feature branch (`git checkout -b feat/amazing-feature`)
3. Make your changes
4. Run tests and linting
5. Commit your changes (`git commit -m 'feat: add amazing feature'`)
6. Push to the branch (`git push origin feat/amazing-feature`)
7. Open a Pull Request

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## Citation

If you use this work in your research or projects, please cite:

```bibtex
@software{neurosim2025,
  author = {Howland, Anais and Thinnappan, Ashwin and Gupta, Vaibhav},
  title = {Neurosim: Core Evaluation Framework for AI Agents},
  year = {2025},
  publisher = {Paradigm Shift AI},
  url = {https://github.com/anaishowland/neurosim}
}
```

**Developed at Paradigm Shift AI**

## Acknowledgments

This project was developed at Paradigm Shift AI to provide a robust framework for evaluating AI agent systems. 

## Related Projects

- [Agent-CE](https://github.com/anaishowland/agent-CE): Continuous Evaluation platform with pre-built agent integrations (Browser Use, Notte, Anthropic/OpenAI Computer Use)
