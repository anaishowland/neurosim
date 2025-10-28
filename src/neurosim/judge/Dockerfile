# Use Python 3.11 slim image as base
FROM python:3.11-slim

# Set environment variables
ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1
ENV DEBIAN_FRONTEND=noninteractive

# Build arguments for authentication
ARG GCLOUD_ACCESS_TOKEN

# Install system dependencies
RUN apt-get update && apt-get install -y \
    curl \
    wget \
    git \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Set working directory
WORKDIR /app

# Copy requirements.txt and install public dependencies
COPY requirements.txt ./
RUN pip install -r requirements.txt

# Install private neurosim package if token is provided
RUN if [ -n "$GCLOUD_ACCESS_TOKEN" ]; then \
        echo "Installing private neurosim package..." && \
        pip install --index-url "https://oauth2accesstoken:${GCLOUD_ACCESS_TOKEN}@us-west1-python.pkg.dev/evaluation-deployment/neuro-deploy/simple/" neurosim; \
    else \
        echo "No token provided, skipping private package installation"; \
    fi

# Copy only the judge application code
COPY . /app

# The entrypoint script is included in the source copy.
# We just need to make it executable and set the entrypoint.
RUN chmod +x /app/docker-entrypoint.sh

# Default command
ENTRYPOINT ["/app/docker-entrypoint.sh"]