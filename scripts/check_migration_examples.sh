#!/usr/bin/env bash
set -euo pipefail

root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

cleanup_artifacts() {
	find "$root/examples/migration" "$root/migrations" -type d -name "__pycache__" -prune -exec rm -rf {} +
}

cleanup() {
	status=$?
	cleanup_artifacts
	exit "$status"
}
trap cleanup EXIT

cleanup_artifacts
export PYTHONDONTWRITEBYTECODE=1
export PYTHONPATH="$root:$root/sdk/python"
python3 -B -m unittest discover -s "$root/examples/migration" -p 'test_*.py'
python3 -B -m unittest discover -s "$root/migrations" -p 'test_*.py'
