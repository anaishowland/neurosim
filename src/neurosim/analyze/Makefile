# Makefile for building and pushing Docker images for neurosim-post-process services.

# --- Configuration ---
# Pass a custom tag to any command, e.g.,
# make both-sentinel TAG=v1.0.0
TAG ?=

# --- Service Definitions ---
SENTINEL_DIR := sentinel
SENTINEL_REPO := YOUR_REGION-docker.pkg.dev/YOUR_PROJECT_ID/YOUR_REPO
SENTINEL_NAME := monitor
SENTINEL_FULL_IMAGE_NAME := $(SENTINEL_REPO)/$(SENTINEL_NAME)

AGGREGATOR_DIR := reduce
AGGREGATOR_REPO := YOUR_REGION-docker.pkg.dev/YOUR_PROJECT_ID/YOUR_REPO
AGGREGATOR_NAME := neurosim-aggregator
AGGREGATOR_FULL_IMAGE_NAME := $(AGGREGATOR_REPO)/$(AGGREGATOR_NAME)


.PHONY: all build-all push-all both-all \
        build-sentinel push-sentinel both-sentinel \
        build-aggregator push-aggregator both-aggregator

# --- High-Level Targets ---

# Build and push all services.
all: build-all push-all

# Build all services.
build-all: build-sentinel build-aggregator

# Push all services ('latest' and optional TAG).
push-all: push-sentinel push-aggregator


# --- Sentinel Targets ---

# Build the Sentinel image (tags as 'latest' and optionally with TAG).
build-sentinel:
	@echo "--> Building Sentinel image..."
	docker build -t $(SENTINEL_FULL_IMAGE_NAME):latest ./$(SENTINEL_DIR)
	@if [ -n "$(TAG)" ]; then \
		echo "    Tagging Sentinel with: $(TAG)"; \
		docker tag $(SENTINEL_FULL_IMAGE_NAME):latest $(SENTINEL_FULL_IMAGE_NAME):$(TAG); \
	fi

# Push the Sentinel image ('latest' and optional TAG).
push-sentinel:
	@echo "--> Pushing Sentinel image..."
	docker push $(SENTINEL_FULL_IMAGE_NAME):latest
	@if [ -n "$(TAG)" ]; then \
		echo "    Pushing Sentinel tag: $(TAG)"; \
		docker push $(SENTINEL_FULL_IMAGE_NAME):$(TAG); \
	fi

# Build and push the Sentinel image.
both-sentinel: build-sentinel push-sentinel


# --- Aggregator Targets ---

# Build the Aggregator image (tags as 'latest' and optionally with TAG).
build-aggregator:
	@echo "--> Building Aggregator image..."
	docker build -t $(AGGREGATOR_FULL_IMAGE_NAME):latest ./$(AGGREGATOR_DIR)
	@if [ -n "$(TAG)" ]; then \
		echo "    Tagging Aggregator with: $(TAG)"; \
		docker tag $(AGGREGATOR_FULL_IMAGE_NAME):latest $(AGGREGATOR_FULL_IMAGE_NAME):$(TAG); \
	fi

# Push the Aggregator image ('latest' and optional TAG).
push-aggregator:
	@echo "--> Pushing Aggregator image..."
	docker push $(AGGREGATOR_FULL_IMAGE_NAME):latest
	@if [ -n "$(TAG)" ]; then \
		echo "    Pushing Aggregator tag: $(TAG)"; \
		docker push $(AGGREGATOR_FULL_IMAGE_NAME):$(TAG); \
	fi

# Build and push the Aggregator image.
both-aggregator: build-aggregator push-aggregator