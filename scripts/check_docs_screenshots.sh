#!/usr/bin/env bash
set -euo pipefail

root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
manifest="$root/web/docs-screenshots/screenshots.json"
docs_page="$root/docs/site/dashboard-screenshots.md"
asset_dir="${CONBENCH_DOCS_SCREENSHOT_OUT_DIR:-$root/docs/site/assets/screenshots}"
evidence="$asset_dir/dashboard-screenshots-evidence.json"
artifact_checks=0
if [ -n "${CONBENCH_DOCS_SCREENSHOT_OUT_DIR:-}" ] || [ -d "$asset_dir" ]; then
	artifact_checks=1
fi

cleanup_artifacts() {
	rm -rf "$root/scripts/__pycache__"
}

cleanup() {
	status=$?
	cleanup_artifacts
	exit "$status"
}
trap cleanup EXIT

cd "$root"
cleanup_artifacts
export PYTHONDONTWRITEBYTECODE=1
python3 -B -m unittest scripts.test_docs_screenshot_pins
python3 -B scripts/docs_screenshot_pins.py "$root"
python3 -B -m unittest scripts.test_docs_screenshot_preflight
python3 -B -m unittest scripts.test_docs_screenshot_inventory
python3 -B -m unittest scripts.test_docs_screenshot_evidence
python3 -B scripts/docs_screenshot_inventory.py "$manifest" "$docs_page"
if [ "$artifact_checks" = "1" ]; then
	python3 -B scripts/docs_screenshot_inventory.py "$manifest" "$docs_page" "$asset_dir"
	python3 -B scripts/docs_screenshot_evidence.py check "$manifest" "$asset_dir" "$evidence"
else
	echo "docs screenshot artifact checks skipped; set CONBENCH_DOCS_SCREENSHOT_OUT_DIR or run make docs-screenshots"
fi
