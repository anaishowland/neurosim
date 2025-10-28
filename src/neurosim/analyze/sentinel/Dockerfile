# Multi-stage Dockerfile for Neurosim Sentinel Monitor
# Stage 1: Build stage with full Python image
FROM python:3.11-slim AS builder

# Set working directory
WORKDIR /app

# Install system dependencies needed for building
RUN apt-get update && apt-get install -y \
    gcc \
    g++ \
    git \
    && rm -rf /var/lib/apt/lists/*

# Upgrade pip and install uv for faster package management
RUN pip install --upgrade pip uv

# Copy the entire project structure for proper package installation
COPY . /app

# Build arguments for private repository access
ARG GCLOUD_ACCESS_TOKEN
# Optional: Replace with your own Python package registry URL
ARG PYTHON_REPO_URL="YOUR_REGION-python.pkg.dev/YOUR_PROJECT_ID/YOUR_REPO/simple/"

# Install neurosim with monitor dependencies
# Use uv for faster dependency resolution and installation
RUN if [ -n "$GCLOUD_ACCESS_TOKEN" ]; then \
    uv pip install --system --no-cache-dir \
    --extra-index-url="https://oauth2accesstoken:${GCLOUD_ACCESS_TOKEN}@${PYTHON_REPO_URL}" \
    neurosim[monitor] && \
    echo "neurosim installation completed"; \
    else \
    echo "Installing local version as fallback" && \
    uv pip install --system --no-cache-dir -e "/app[monitor]"; \
    fi

# Stage 2: Runtime stage with minimal image
FROM python:3.11-slim AS runtime

# Set working directory
WORKDIR /app

# Install runtime system dependencies (if any)
RUN apt-get update && apt-get install -y \
    && rm -rf /var/lib/apt/lists/*

# Copy installed packages from builder stage
COPY --from=builder /usr/local/lib/python3.11/site-packages /usr/local/lib/python3.11/site-packages
COPY --from=builder /usr/local/bin /usr/local/bin

# Copy the entire neurosim project structure
# Note: This assumes Docker build context is the project root
COPY src/ /app/src/
COPY pyproject.toml /app/

# Set environment variables
ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONPATH=/app/src
ENV GCP_PROJECT_ID=YOUR_GCP_PROJECT_ID
ENV GCP_REGION=us-central1

# Default command
CMD ["python", "-m", "neurosim.analyze.sentinel.monitor"]
