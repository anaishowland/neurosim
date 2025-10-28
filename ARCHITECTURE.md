# Neurosim Architecture

This document describes the architecture and design of the Neurosim framework.

## Overview

Neurosim is a modular framework for evaluating AI agents, particularly web browsing agents. It provides:

1. **Evaluation Framework**: Abstract base classes for implementing agent evaluations
2. **Storage Layer**: GCS integration for persisting results and artifacts
3. **Judge System**: LLM-based evaluation of agent performance
4. **Monitoring**: Real-time tracking of evaluation jobs

## High-Level Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                     Agent Implementation                     │
│                (extends Evaluation base class)               │
│  ┌────────────────────────────────────────────────────────┐ │
│  │  • get_llm()        - Configure LLM                    │ │
│  │  • run()            - Execute agent task               │ │
│  │  • compute_steps()  - Process trajectory               │ │
│  │  • compute_tokens() - Calculate token usage            │ │
│  └────────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                    Neurosim Core Layer                       │
│  ┌────────────────────────────────────────────────────────┐ │
│  │  Evaluation (Abstract Base Class)                      │ │
│  │  • execute()     - Orchestrates evaluation             │ │
│  │  • from_cli()    - CLI argument parsing                │ │
│  │  • save_*()      - Result persistence                  │ │
│  └────────────────────────────────────────────────────────┘ │
│                                                              │
│  ┌────────────────────────────────────────────────────────┐ │
│  │  Storage Layer (GCSUploader)                           │ │
│  │  • upload_json()    - Upload results (with zstd)       │ │
│  │  • upload_png()     - Upload screenshots               │ │
│  │  • download_json()  - Retrieve results                 │ │
│  └────────────────────────────────────────────────────────┘ │
│                                                              │
│  ┌────────────────────────────────────────────────────────┐ │
│  │  Data Models (Pydantic)                                │ │
│  │  • EvaluationRequest  - Input configuration            │ │
│  │  • AgentResult        - Output format                  │ │
│  │  • EvaluationConfig   - Runtime config                 │ │
│  └────────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                    External Services                         │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐      │
│  │     GCS      │  │  Firestore   │  │  Cloud Run   │      │
│  │   (Results)  │  │   (Status)   │  │ (Execution)  │      │
│  └──────────────┘  └──────────────┘  └──────────────┘      │
└─────────────────────────────────────────────────────────────┘
```

## Core Components

### 1. Evaluation Base Class

**Location**: `src/neurosim/evaluation.py`

The abstract `Evaluation` class provides the contract for agent implementations:

```python
class Evaluation(ABC):
    def __init__(self, request: EvaluationRequest) -> None:
        # Initialize config, storage, results
    
    @abstractmethod
    async def run(self) -> AgentResult:
        # Execute agent task
    
    @abstractmethod
    def get_llm(self) -> LLMType:
        # Configure LLM
    
    @abstractmethod
    def compute_steps(self) -> None:
        # Process agent steps
    
    @abstractmethod
    def compute_tokens(self) -> None:
        # Calculate token usage
    
    async def execute(self):
        # Orchestrate: run -> compute_steps -> compute_tokens -> save
```

**Key Features**:
- CLI argument parsing via `from_cli()`
- Automatic result directory creation
- Context-aware logging with job/task metadata
- Integration with GCS storage layer

**Extension Points**:
Subclasses must implement:
1. `get_llm()`: Return LLM configuration
2. `run()`: Execute the agent and populate `self.result`
3. `compute_steps()`: Extract trajectory and screenshots
4. `compute_tokens()`: Track token usage

### 2. Storage Layer

**Location**: `src/neurosim/core/storage.py`

The `GCSUploader` class handles all Google Cloud Storage interactions:

```python
class GCSUploader:
    def __init__(self, client=None, bucket_name=None):
        # Initialize GCS client
    
    def upload_json(self, blob_path, data, compress_zstd=True):
        # Upload JSON with optional zstd compression
    
    def upload_png(self, data, blob_path):
        # Upload PNG screenshots
    
    def download_json(self, blob_path):
        # Download JSON results
    
    def download_zstd_json(self, blob_path):
        # Download and decompress zstd JSON
```

**Features**:
- Automatic Zstandard compression (configurable)
- Content type and encoding handling
- Public/private ACL support
- URI-based result references

**Storage Structure**:
```
gs://bucket/
├── {userid}/
│   ├── {jobid}/
│   │   ├── {episode}/
│   │   │   ├── {taskid}/
│   │   │   │   ├── result.json.zst  (compressed result)
│   │   │   │   ├── screenshot_1.png
│   │   │   │   ├── screenshot_2.png
│   │   │   │   └── ...
```

### 3. Data Models

**Location**: `src/neurosim/utils/models.py`

Pydantic models provide structure and validation:

**EvaluationRequest**: Input configuration
```python
class EvaluationRequest(BaseModel):
    userid: str
    model: str
    jobid: str
    task: str                    # Task description
    taskid: str
    browser_channel: str
    episode: int
    advanced_settings: Dict[str, Any]
    bucket_name: str
```

**AgentResult**: Output format
```python
class AgentResult(BaseModel):
    jobId: str
    success: bool = False
    latency: float = 0.0
    tokens: List[Dict[str, int]]
    task: Dict[str, Any]
    steps: List[Dict[str, Any]]  # Agent trajectory
    results: str                 # Final output
    error: Optional[AgentErrors]
```

**EvaluationConfig**: Runtime configuration
```python
class EvaluationConfig(BaseModel):
    model: str                   # LLM identifier
    episode: int
    temperature: float
    tasks: List[Dict[str, str]]
    save_path: str              # Local result directory
```

### 4. LLM Judge System

**Location**: `src/neurosim/judge/`

The judge system evaluates agent results using GPT or Gemini:

**Components**:
1. `evaluate_results.py`: CLI for batch evaluation
2. `judge_system.py`: Scoring and reasoning logic
3. `adapter/`: LLM provider adapters (OpenAI, Gemini)
4. `messages.py`: System/user prompts

**Workflow**:
```
1. Read result.json (or .zst) from task folder
2. Load screenshots (up to max_images)
3. Send to LLM with judge prompt
4. Parse response (score, reasoning, issues, suggestions)
5. Aggregate results across tasks
6. Write llm_judge.json
```

**Scoring**:
- Score: 0-100 (≥70 = success, <70 = failure)
- Reasoning: Explanation of score
- Issues: List of observed problems
- Suggestions: Improvement recommendations

### 5. Monitoring System

**Location**: `src/neurosim/analyze/sentinel/`

Real-time monitoring of Cloud Run jobs:

**Features**:
- Poll Cloud Run job status
- Update Firestore with progress
- Track success/failure rates
- Handle job completion/timeout

**Status Flow**:
```
QUEUED -> RUNNING -> POST_PROCESS -> COMPLETED/FAILED
```

## Data Flow

### Evaluation Execution

```
1. CLI Arguments
   ↓
2. EvaluationRequest (parsed)
   ↓
3. Evaluation.__init__()
   - Create save_path
   - Initialize GCSUploader
   - Create AgentResult
   ↓
4. execute()
   - Call run() → AgentResult
   - Call compute_steps() → Extract trajectory
   - Call compute_tokens() → Track usage
   - Call save_results() → Upload to GCS
   ↓
5. GCS Storage
   - result.json.zst (compressed)
   - screenshot_*.png
```

### Judge Evaluation

```
1. Task Folder
   ├── result.json[.zst]
   └── screenshot_*.png
   ↓
2. Judge System
   - Load result
   - Load screenshots
   - Format prompt
   ↓
3. LLM API
   - GPT-4o / Gemini
   ↓
4. Parse Response
   - score (0-100)
   - reasoning
   - issues
   - suggestions
   ↓
5. Aggregate
   - llm_judge.json
```

## Extension Points

### Adding a New Agent

1. **Create Agent Class**:
```python
from neurosim.evaluation import Evaluation

class MyAgentEvaluation(Evaluation):
    def __init__(self, request: EvaluationRequest):
        super().__init__(request)
        self.agent_name = "MyAgent"
        self.agent_version = "1.0.0"
    
    def get_llm(self):
        return ChatGPT(model="gpt-4o")
    
    async def run(self) -> AgentResult:
        # Implement agent logic
        pass
    
    def compute_steps(self):
        # Extract steps
        pass
    
    def compute_tokens(self):
        # Track tokens
        pass
```

2. **CLI Entry Point**:
```python
if __name__ == "__main__":
    import asyncio
    eval = MyAgentEvaluation.from_cli()
    asyncio.run(eval.execute())
```

3. **Run**:
```bash
python main.py --jobId job_001 --task "..." --taskId task_001 --user user --episode 0
```

### Adding a New Judge Model

1. **Create Adapter**:
```python
# src/neurosim/judge/adapter/my_adapter.py
from neurosim.judge.adapter.adapter import Adapter

class MyAdapter(Adapter):
    def __init__(self, model: str, **kwargs):
        # Initialize client
    
    def run(self, messages, **kwargs):
        # Call API and return response
```

2. **Register in `judge_system.py`**:
```python
if model.startswith("my-model"):
    return MyAdapter(model)
```

## Design Principles

1. **Separation of Concerns**: Core framework, storage, and judge are decoupled
2. **Extensibility**: Abstract base classes with well-defined extension points
3. **Type Safety**: Pydantic models for validation and serialization
4. **Cloud Native**: GCS for storage, Cloud Run for execution, Firestore for state
5. **Observability**: Structured logging with context (jobId, taskId, userId)
6. **Compression**: Zstandard for efficient result storage

## Dependencies

### Core
- `pydantic`: Data validation and serialization
- `google-cloud-storage`: GCS integration
- `google-cloud-firestore`: Status tracking
- `zstandard`: Result compression
- `python-dotenv`: Environment configuration

### Judge
- `openai`: GPT models
- `google-genai`: Gemini models
- `Pillow`: Image processing

### Optional
- `google-cloud-run`: Job monitoring
- `requests`: Webhooks
- `schedule`: Periodic tasks

## Security Considerations

1. **Credentials**: Use service accounts with minimal permissions
2. **Bucket ACLs**: Results stored as private by default
3. **API Keys**: Loaded from environment, never committed
4. **Input Validation**: Pydantic models validate all inputs

## Performance

- **Compression**: 60-80% size reduction with Zstandard
- **Concurrency**: Judge system supports up to 100 concurrent tasks
- **Streaming**: Large files can be processed in chunks
- **Caching**: Docker layer caching for faster builds
