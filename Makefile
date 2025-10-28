.PHONY: publish build clean venv test sentinel neurosim monitor judge publish-core publish-monitor publish-judge

publish:
	@bash scripts/publish.sh

build: venv
	uv run python -m build

clean:
	rm -rf .venv
	rm -rf dist build *.egg-info
	find . -type d -name "__pycache__" -exec rm -rf {} +
	find . -type d -name ".pytest_cache" -exec rm -rf {} +
	find . -type d -name ".mypy_cache" -exec rm -rf {} +
	find . -type d -name "htmlcov" -exec rm -rf {} +
	find . -type d -name ".tox" -exec rm -rf {} +
	find . -type f -name "*.pyc" -delete
	find . -type f -name "*.pyo" -delete
	find . -type f -name "*.log" -delete
	find . -type f -name ".coverage" -delete
	find . -type f -name "coverage.xml" -delete

venv:
	@test -d .venv || uv venv

test: venv
	uv run python -m pytest tests/ -v $(ARGS)

sentinel:
	DOCKER_BUILDKIT=1 docker build --build-arg GCLOUD_ACCESS_TOKEN=$$(gcloud auth application-default print-access-token) -f src/neurosim/analyze/sentinel/Dockerfile -t neurosim-monitor .

# Docker build targets
neurosim:
	@bash docker/core/neurosim-base.sh

monitor:
	@echo "[INFO] Building monitor image..."
	DOCKER_BUILDKIT=1 docker build --build-arg GCLOUD_ACCESS_TOKEN=$$(gcloud auth application-default print-access-token) -f src/neurosim/analyze/sentinel/Dockerfile -t neurosim-monitor .

judge:
	@echo "[INFO] Building judge image..."
	cd src/neurosim/judge && DOCKER_BUILDKIT=1 docker build --build-arg GCLOUD_ACCESS_TOKEN=$$(gcloud auth application-default print-access-token) -f Dockerfile -t neurosim-judge .

# Docker publish targets
publish-core:
	@echo "[INFO] Publishing neurosim-base image..."
	sudo docker tag neurosim-base:latest us-central1-docker.pkg.dev/evaluation-deployment/neurosim-base/neurosim-base:latest
	sudo docker push us-central1-docker.pkg.dev/evaluation-deployment/neurosim-base/neurosim-base:latest

publish-monitor:
	@echo "[INFO] Publishing monitor image..."
	sudo docker tag neurosim-monitor us-central1-docker.pkg.dev/evaluation-deployment/neurosim-monitor/monitor:latest
	sudo docker push us-central1-docker.pkg.dev/evaluation-deployment/neurosim-monitor/monitor:latest

publish-judge:
	@echo "[INFO] Publishing judge image..."
	sudo docker tag neurosim-judge us-central1-docker.pkg.dev/evaluation-deployment/neurosim-judge/neurosim-judge:latest
	sudo docker push us-central1-docker.pkg.dev/evaluation-deployment/neurosim-judge/neurosim-judge:latest


publish-sentinel:
	@echo "Pushing Docker image to repository..."
	sudo docker tag neurosim-monitor:latest us-central1-docker.pkg.dev/evaluation-deployment/neurosim-monitor/monitor:latest
	sudo docker push us-central1-docker.pkg.dev/evaluation-deployment/neurosim-monitor/monitor:latest
	@echo "Docker image pushed"