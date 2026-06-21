#!/usr/bin/env bash
set -euo pipefail

root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
sdk="$root/sdk/python"
tmp="$(mktemp -d)"

cleanup_artifacts() {
	rm -rf "$root/scripts/__pycache__"
	rm -rf "$sdk/.pytest_cache" "$sdk/.ruff_cache" "$sdk/.venv"
	find "$sdk" -type d \( -name "__pycache__" -o -name ".ruff_cache" \) -prune -exec rm -rf {} +
}

cleanup() {
	status=$?
	cleanup_artifacts
	rm -rf "$tmp"
	exit "$status"
}
trap cleanup EXIT

cleanup_artifacts
export PYTHONDONTWRITEBYTECODE=1
cd "$root"
python3 -B -m unittest scripts.test_sdk_overlay_sync
python3 -B scripts/sdk_overlay_sync.py "$root"

cd "$sdk"
export UV_PROJECT_ENVIRONMENT="$tmp/uv-project-env"
uv run --locked pytest -q
