# Contributing to neurosim

Thanks for your interest in contributing! This repository contains the neurosim Python package with core primitives and evaluation utilities for AI agent simulation and evaluation.

## Table of Contents

- [Prerequisites](#prerequisites)
- [Local Development Setup](#local-development-setup)
- [Project Structure](#project-structure)
- [Development Workflow](#development-workflow)
- [Code Quality](#code-quality)
- [Testing](#testing)
- [Examples and Demo](#examples-and-demo)
- [Contributing Guidelines](#contributing-guidelines)
- [Troubleshooting](#troubleshooting)

## Prerequisites

- **Python 3.11+** (required)
- **Git** (required)
- **uv** (recommended for fast dependency management) - [Installation guide](https://docs.astral.sh/uv/getting-started/installation/)
- **Google Cloud SDK** (optional, for GCS functionality and publishing)

## Local Development Setup

### Option 1: Quick Setup with uv (Recommended)

The fastest way to get started is using the provided setup script:

```bash
# Clone the repository
git clone <repository-url>
cd neurosim

# Run the automated setup script
bash setup.sh
```

This script will:
- Check for Python 3.11+ and uv
- Create a virtual environment
- Install the project in development mode
- Handle authentication issues with private registries

### Option 2: Manual Setup with uv

```bash
# Create and activate virtual environment
uv venv --python python3
source .venv/bin/activate  # On Windows: .venv\Scripts\activate

# Install build tools from PyPI (to avoid auth issues)
uv pip install --index-url https://pypi.org/simple/ build wheel hatchling

# Install the project in development mode
uv pip install --index-url https://pypi.org/simple/ -e .

# Install optional GCS dependencies if needed
uv pip install --index-url https://pypi.org/simple/ -e ".[gcs]"
```

### Option 3: Traditional Setup with pip

```bash
# Create virtual environment
python3 -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate

# Upgrade pip and install build tools
python -m pip install --upgrade pip build wheel

# Install the project in development mode
pip install -e .

# Install optional GCS dependencies if needed
pip install -e ".[gcs]"
```

### Development Dependencies

For a complete development environment, you may want to install additional tools:

```bash
# Using uv (recommended)
uv pip install --index-url https://pypi.org/simple/ \
    pytest pytest-cov pytest-asyncio \
    black isort mypy \
    pre-commit

# Using pip
pip install pytest pytest-cov pytest-asyncio black isort mypy pre-commit
```

## Project Structure

```
neurosim/
├── src/neurosim/          # Main package source code
│   ├── __init__.py        # Package initialization and version
│   ├── constants.py       # Global constants
│   ├── evaluation.py      # Core evaluation framework
│   ├── core/              # Core infrastructure
│   │   ├── pipeline.py    # Pipeline management
│   │   └── storage.py     # Storage utilities (GCS, etc.)
│   ├── judge/             # LLM judge system
│   │   ├── adapters.py    # LLM provider adapters (OpenAI, Gemini)
│   │   ├── evaluate_results.py  # Result evaluation logic
│   │   ├── judge_system.py      # Main judge orchestration
│   │   └── messages.py    # Message handling
│   └── utils/             # Utility modules
│       ├── colored_formatter.py  # Logging formatters
│       └── models.py      # Data models
├── examples/              # Example implementations
│   └── NotteEvaluation/   # Complete evaluation example
├── scripts/               # Build and deployment scripts
├── tests/                 # Test suite (if present)
├── pyproject.toml         # Project configuration
├── Makefile              # Build automation
└── setup.sh              # Development setup script
```

## Development Workflow

### 1. Create a Feature Branch

```bash
git checkout -b feat/your-feature-name
# or
git checkout -b fix/bug-description
```

### 2. Make Your Changes

- Follow the existing code style and patterns
- Add docstrings for new classes and functions
- Include type hints where appropriate
- Update relevant documentation

### 3. Test Your Changes

```bash
# Build the project to verify packaging
make build

# Run examples to ensure they still work
cd examples/NotteEvaluation
bash scripts/basic.sh  # (requires proper .env setup)
```

### 4. Code Quality Checks

```bash
# Format code (if you have black installed)
black src/ examples/

# Sort imports (if you have isort installed)
isort src/ examples/

# Type checking (if you have mypy installed)
mypy src/neurosim
```

### 5. Commit and Push

```bash
git add .
git commit -m "feat: add new evaluation metric"
git push origin feat/your-feature-name
```

## Code Quality

### Style Guidelines

- **Type Hints**: Use type hints for function parameters and return values
- **Docstrings**: Add docstrings for public classes and methods using Google style
- **Naming**: Use descriptive names; prefer `process_evaluation_results` over `proc_eval`
- **Functions**: Keep functions small and focused; use early returns for clarity
- **Error Handling**: Use specific exception types rather than generic `Exception`

### Example Good Code

```python
from typing import List, Optional
import logging

def process_evaluation_results(
    results: List[dict], 
    filter_incomplete: bool = True
) -> Optional[dict]:
    """
    Process evaluation results and return summary statistics.
    
    Args:
        results: List of evaluation result dictionaries
        filter_incomplete: Whether to exclude incomplete results
        
    Returns:
        Summary statistics dictionary, or None if no valid results
        
    Raises:
        ValueError: If results list is empty
    """
    if not results:
        raise ValueError("Results list cannot be empty")
    
    # ... implementation
```

### Avoid

- Large functions that do multiple things
- Generic `except Exception:` blocks without specific handling
- Importing entire modules when you only need specific functions
- Adding new runtime dependencies without justification

## Testing

### Running Tests

   ```bash
# If you have pytest installed
pytest

# With coverage
pytest --cov=src/neurosim

# Run specific test file
pytest tests/test_evaluation.py
```

### Writing Tests

- Place test files in a `tests/` directory
- Name test files with `test_` prefix
- Use descriptive test function names
- Include both unit tests and integration tests
- Mock external dependencies (API calls, file system, etc.)

## Examples and Demo

### NotteEvaluation Example

The `examples/NotteEvaluation` directory contains a complete working example:

1. **Setup Environment**: Create `examples/.env` with required variables:
   ```bash
   GCS_BUCKET_NAME=your-bucket-name
   GOOGLE_APPLICATION_CREDENTIALS=/path/to/credentials.json
   # Optional customizations
   MODEL=gemini-2.5-flash-preview-05-20
   TASK="open apple.com"
   ```

2. **Run the Example**:
   ```bash
   cd examples/NotteEvaluation
   bash scripts/basic.sh
   ```

3. **Customize Behavior**: Export environment variables or modify the `.env` file

## Contributing Guidelines

### Pull Request Process

1. **Fork and Branch**: Create a feature branch from `main`
2. **Small PRs**: Keep pull requests focused and small for easier review
3. **Description**: Include a clear description of changes and motivation
4. **Testing**: Ensure the project builds and examples run
5. **Review**: Address feedback promptly and thoughtfully

### Issue Reporting

When reporting bugs or requesting features:
- **Search First**: Check if the issue already exists
- **Reproduction Steps**: Provide clear steps to reproduce bugs
- **Environment**: Include OS, Python version, and dependency versions
- **Expected vs Actual**: Clearly describe what you expected vs what happened

### Commit Message Guidelines

- Use present tense ("Add feature" not "Added feature")
- Keep first line under 50 characters
- Reference issues when applicable (`fixes #123`)
- Use conventional commits when possible:
  - `feat:` for new features
  - `fix:` for bug fixes
  - `docs:` for documentation changes
  - `refactor:` for code refactoring

## Troubleshooting

### Common Issues

#### 1. Authentication Errors with Private Registry

**Problem**: Getting 401/403 errors when installing packages
**Solution**: Use PyPI for development:
```bash
uv pip install --index-url https://pypi.org/simple/ package-name
```

#### 2. Python Version Issues

**Problem**: "Python 3.11+ required" error
**Solution**: Install Python 3.11+ or use pyenv:
```bash
# Install pyenv (if not installed)
curl https://pyenv.run | bash

# Install and use Python 3.11
pyenv install 3.11.7
pyenv local 3.11.7
```

#### 3. Virtual Environment Issues

**Problem**: Commands not found or wrong Python version
**Solution**: Ensure virtual environment is activated:
  ```bash
source .venv/bin/activate
which python  # Should point to .venv/bin/python
```

#### 4. Build Failures

**Problem**: `make build` fails
**Solution**: Clean and retry:
  ```bash
make clean
make venv
make build
```

#### 5. GCS Authentication for Examples

**Problem**: Examples fail with GCS errors
**Solution**: Set up Google Cloud authentication:
   ```bash
# Option 1: Service account key
export GOOGLE_APPLICATION_CREDENTIALS=/path/to/service-account.json

# Option 2: Application default credentials
   gcloud auth application-default login
   ```

### Getting Help

- **Check the README**: Many common questions are answered there
- **Search Issues**: Look for similar problems in GitHub issues
- **Example Code**: Refer to `examples/NotteEvaluation` for working patterns
- **Debug Logging**: Set `LOG_LEVEL=DEBUG` in your environment for verbose output

## Versioning and Publishing (Maintainers)

### Version Management

```bash
# Check current version
make version-current

# Bump version
make version-bump-patch   # 1.0.0 -> 1.0.1
make version-bump-minor   # 1.0.0 -> 1.1.0
make version-bump-major   # 1.0.0 -> 2.0.0

# Rollback if needed
make version-rollback
```

### Publishing to Private Registry

```bash
# Authenticate with Google Cloud (one-time setup)
gcloud auth application-default login

# Publish to neuro-deploy registry
make publish

# Or with custom index
UV_INDEX_NAME=custom-index make publish
```

### Release Process

1. Update version using make targets
2. Update CHANGELOG.md with release notes
3. Create and push git tag:
   ```bash
   git tag v1.2.3
   git push origin v1.2.3
   ```
4. Publish to registry: `make publish`

## License

This project is for internal use only. See `LICENSE` for terms and conditions.

---

Thank you for contributing to neurosim! Your help makes this project better for everyone.