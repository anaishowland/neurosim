#!/usr/bin/env bash
set -euo pipefail

# Activate project venv if present (user-specific path)
if [ -f "/home/anaishowland/venvs/judge/bin/activate" ]; then
  source "/home/anaishowland/venvs/judge/bin/activate"
fi

if [ $# -lt 1 ]; then
  echo "Usage: $0 <eval_folder> [--model MODEL] [--max-images N] [--output FILE]"
  exit 1
fi

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

cd "$SCRIPT_DIR"

python "$SCRIPT_DIR/evaluate_results.py" "$@"

