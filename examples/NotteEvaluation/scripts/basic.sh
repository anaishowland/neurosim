#!/usr/bin/env bash
set -Eeuo pipefail

# Resolve project paths
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
EXAMPLES_DIR="$(dirname "$(dirname "$SCRIPT_DIR")")"
cd "$EXAMPLES_DIR"

# Load environment from .env (ENV_FILE > examples/.env > project-root/.env)
PROJECT_ROOT="$(dirname "$EXAMPLES_DIR")"
ENV_FILE="${ENV_FILE:-}"
if [[ -z "${ENV_FILE}" ]]; then
  if [[ -f "$EXAMPLES_DIR/.env" ]]; then
    ENV_FILE="$EXAMPLES_DIR/.env"
  elif [[ -f "$PROJECT_ROOT/.env" ]]; then
    ENV_FILE="$PROJECT_ROOT/.env"
  fi
fi
if [[ -n "${ENV_FILE}" && -f "${ENV_FILE}" ]]; then
  # Export all vars defined in the .env
  set -a
  # shellcheck disable=SC1090
  source "${ENV_FILE}"
  set +a
fi

# Defaults (override via env exports before running)
JOB_ID="${JOB_ID:-test-job-notte}"
TASK="${TASK:-open apple.com}"
TASK_ID="${TASK_ID:-task_001}"
BROWSER="${BROWSER:-CHROME}"
EPISODE="${EPISODE:-0}"
USER_NAME="${USER_NAME:-ashwin}"
MODEL="${MODEL:-gemini-2.5-flash-preview-05-20}"
ADVANCED_SETTINGS_DEFAULT='{"max_steps": 10, "use_vision": true}'
ADVANCED_SETTINGS="${ADVANCED_SETTINGS:-$ADVANCED_SETTINGS_DEFAULT}"
LOG_LEVEL="${LOG_LEVEL:-INFO}"

export LOG_LEVEL

# Run evaluation
PYTHONPATH=.:.. xvfb-run -a python -m NotteEvaluation.main \
  --jobId "$JOB_ID" \
  --task "$TASK" \
  --taskId "$TASK_ID" \
  --browser "$BROWSER" \
  --episode "$EPISODE" \
  --user "$USER_NAME" \
  --model "$MODEL" \
  --advanced_settings "$ADVANCED_SETTINGS"