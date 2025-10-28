#!/bin/bash

# Neurosim Development Environment Setup Script
# This script creates a virtual environment using uv and installs the neurosim project in development mode

set -e  # Exit on any error

echo "🚀 Setting up neurosim development environment with uv..."

# Check if uv is installed
if ! command -v uv &> /dev/null; then
    echo "❌ Error: uv is not installed. Please install uv first:"
    echo "   curl -LsSf https://astral.sh/uv/install.sh | sh"
    echo "   or visit: https://docs.astral.sh/uv/getting-started/installation/"
    exit 1
fi

echo "✅ uv is available: $(uv --version)"

# Check if Python 3.11+ is available
python_version=$(python3 --version 2>&1 | cut -d' ' -f2 | cut -d'.' -f1,2)
required_version="3.11"

if [ "$(printf '%s\n' "$required_version" "$python_version" | sort -V | head -n1)" != "$required_version" ]; then
    echo "❌ Error: Python 3.11+ is required, but found Python $python_version"
    exit 1
fi

echo "✅ Python version check passed: $python_version"

# Create virtual environment if it doesn't exist
if [ ! -d ".venv" ]; then
    echo "📦 Creating virtual environment with uv..."
    uv venv --python python3
    echo "✅ Virtual environment created"
else
    echo "✅ Virtual environment already exists"
fi

# Temporarily move pyproject.toml to avoid private index issues
echo "⬆️  Installing build tools from PyPI..."
if [ -f "pyproject.toml" ]; then
    mv pyproject.toml pyproject.toml.tmp
fi

uv pip install --index-url https://pypi.org/simple/ build wheel hatchling

# Restore pyproject.toml
if [ -f "pyproject.toml.tmp" ]; then
    mv pyproject.toml.tmp pyproject.toml
fi

# Install the project in development mode using uv
echo "📥 Installing neurosim in development mode with uv..."
# Temporarily remove private index configuration from pyproject.toml
if [ -f "pyproject.toml" ]; then
    # Create a backup and remove the private index section
    cp pyproject.toml pyproject.toml.backup
    sed '/\[\[tool\.uv\.index\]\]/,/publish-url = /d' pyproject.toml > pyproject.toml.tmp
    mv pyproject.toml.tmp pyproject.toml
fi

# Install the project
if uv pip install --index-url https://pypi.org/simple/ -e .; then
    echo "✅ Project installed successfully"
else
    echo "⚠️  Project installation had issues, but continuing..."
fi

# Restore original pyproject.toml
if [ -f "pyproject.toml.backup" ]; then
    mv pyproject.toml.backup pyproject.toml
fi

# Install optional dependencies if needed
echo "🔍 Installing optional dependencies..."
if [ -f "requirements-dev.txt" ]; then
    echo "   Installing development requirements..."
    uv pip install --index-url https://pypi.org/simple/ -r requirements-dev.txt
fi

# Check for monitor installation flag
if [ "$1" = "--monitor" ] || [ "$2" = "--monitor" ]; then
    echo "📊 Installing monitor dependencies..."
    uv pip install --index-url https://pypi.org/simple/ -e ".[monitor]"
    echo "✅ Monitor dependencies installed"
fi

# Check for core installation flag
if [ "$1" = "--core" ] || [ "$2" = "--core" ]; then
    echo "📊 Installing core dependencies..."
    uv pip install --index-url https://pypi.org/simple/ -e ".[core]"
    echo "✅ Core dependencies installed"
fi

# Check for judge installation flag
if [ "$1" = "--judge" ] || [ "$2" = "--judge" ]; then
    echo "📊 Installing core dependencies..."
    uv pip install --index-url https://pypi.org/simple/ -e ".[judge]"
    echo "✅ Judge dependencies installed"
fi

echo ""
echo "🎉 Setup complete!"
echo ""
echo "Your virtual environment is ready. To use it:"
echo "   source .venv/bin/activate"
echo ""
echo "Or run commands directly with uv:"
echo "   uv run python your_script.py"
echo "   uv run pytest"
echo ""
echo "To install additional packages from PyPI:"
echo "   uv pip install --index-url https://pypi.org/simple/ package_name"
echo ""
echo "Note: This setup uses PyPI to avoid authentication issues."
echo "If you need packages from the private neuro-deploy index, ensure"
echo "you have proper authentication configured first."
echo ""
echo "To install with monitor dependencies:"
echo "   ./setup.sh --monitor"
echo ""
echo "To install with core dependencies:"
echo "   ./setup.sh --core"
echo ""
echo "To install with judge dependencies:"
echo "   ./setup.sh --judge"
echo ""
echo "To deactivate the virtual environment:"
echo "   deactivate"
echo ""
echo "To clean build artifacts:"
echo "   make clean"
