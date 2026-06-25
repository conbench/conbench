#!/usr/bin/env bash
set -euo pipefail

root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
failures=0
cd "$root"

record_failure() {
	local message="$1"
	echo "$message" >&2
	failures=$((failures + 1))
}

require_file() {
	local path="$1"
	if [ ! -f "$path" ]; then
		record_failure "missing expected workflow file: $path"
	fi
}

require_missing() {
	local path="$1"
	if [ -e "$path" ]; then
		record_failure "unexpected legacy workflow path exists: $path"
	fi
}

require_contains() {
	local file="$1"
	local pattern="$2"
	if ! grep -Fq "$pattern" "$file"; then
		record_failure "missing expected pattern in $file: $pattern"
	fi
}

require_artifact_path() {
	local file="$1"
	local path="$2"
	if ! python3 - "$file" "$path" <<'PY'
import sys

file_path = sys.argv[1]
expected_path = sys.argv[2]

with open(file_path, encoding="utf-8") as f:
    lines = f.readlines()

for idx, line in enumerate(lines):
    if line.lstrip().startswith("#"):
        continue
    if "uses: actions/upload-artifact" not in line:
        continue
    action_indent = len(line) - len(line.lstrip(" "))
    in_with = False
    in_path_block = False
    path_indent = None
    for raw in lines[idx + 1:]:
        stripped = raw.strip()
        indent = len(raw) - len(raw.lstrip(" "))
        if stripped and not stripped.startswith("#") and indent <= action_indent:
            break
        if not in_with:
            if stripped == "with:":
                in_with = True
            continue
        if in_path_block:
            if stripped and indent <= path_indent:
                break
            if stripped == expected_path:
                raise SystemExit(0)
            continue
        if stripped.startswith("path:"):
            value = stripped.split(":", 1)[1].strip().strip("\"'")
            if value == expected_path:
                raise SystemExit(0)
            in_path_block = True
            path_indent = indent

raise SystemExit(f"missing upload-artifact path: {expected_path}")
PY
	then
		record_failure "missing expected artifact path in $file: $path"
	fi
}

require_absent() {
	local file="$1"
	local pattern="$2"
	if grep -Fq "$pattern" "$file"; then
		record_failure "unexpected pattern in $file: $pattern"
	fi
}

require_workflows_absent() {
	local pattern="$1"
	local matches
	matches="$(
		grep -R -F -n \
			--include="*.yml" \
			--include="*.yaml" \
			-- "$pattern" "$root/.github/workflows" || true
	)"
	if [[ -n "$matches" ]]; then
		record_failure "unexpected active workflow path contains $pattern"
		echo "$matches" >&2
	fi
}

require_job_contains() {
	local file="$1"
	local job="$2"
	local pattern="$3"
	if ! python3 - "$file" "$job" "$pattern" <<'PY'
import sys

file_path, job_name, pattern = sys.argv[1:4]
with open(file_path, encoding="utf-8") as f:
    lines = f.readlines()

job_header = f"  {job_name}:"
in_job = False
for line in lines:
    if line.startswith("  ") and not line.startswith("    ") and line.strip().endswith(":"):
        in_job = line.rstrip("\n") == job_header
        continue
    if in_job and pattern in line:
        raise SystemExit(0)

raise SystemExit(1)
PY
	then
		record_failure "missing expected pattern in $job job of $file: $pattern"
	fi
}

ci="$root/.github/workflows/ci.yml"
release="$root/.github/workflows/release.yml"
publish_docs="$root/.github/workflows/publish_docs.yml"
docs_screenshot_script="$root/scripts/capture_docs_screenshots.sh"
docs_screenshot_page="$root/docs/site/dashboard-screenshots.md"
makefile="$root/Makefile"
gitignore="$root/.gitignore"

require_file "$ci"
require_file "$release"
require_file "$publish_docs"
require_file "$root/Dockerfile.docs-screenshots"
require_file "$root/docker-compose.docs-screenshots.yml"
require_file "$docs_screenshot_page"
require_file "$root/scripts/docs_screenshot_inventory.py"
require_file "$root/scripts/test_docs_screenshot_inventory.py"
require_file "$root/scripts/docs_screenshot_pins.py"
require_file "$root/scripts/test_docs_screenshot_pins.py"
require_file "$root/scripts/publish_docs_screenshot_artifacts.sh"
require_file "$root/scripts/restore_docs_screenshot_artifacts.sh"
require_file "$root/scripts/docs_rendered_assets.py"
require_file "$root/scripts/test_docs_rendered_assets.py"
require_file "$root/scripts/docs_links.py"
require_file "$root/scripts/test_docs_links.py"
require_file "$root/scripts/docs_migration_coverage.py"
require_file "$root/scripts/test_docs_migration_coverage.py"
require_file "$root/scripts/test_check_migration_examples.py"
require_file "$root/scripts/retired_python_surfaces.py"
require_file "$root/scripts/test_retired_python_surfaces.py"
require_file "$root/scripts/python_sdk_artifact_hygiene.py"
require_file "$root/scripts/test_python_sdk_artifact_hygiene.py"
require_file "$root/scripts/repo_hygiene.py"
require_file "$root/scripts/test_repo_hygiene.py"
require_file "$root/scripts/test_check_workflows.py"
require_file "$root/scripts/openapi_emit.go"
require_missing "$root/.github/workflows/actions.yml"
require_missing "$root/.github/workflows/new-vision.yml"
require_missing "$root/cmd/conbench-server"
require_missing "$root/cmd/conbench-openapi"

retired_workflow_terms=()
while IFS= read -r term; do
	retired_workflow_terms+=("$term")
done < <(
	python3 - <<'PY'
from scripts.retired_python_surfaces import RETIRED_PYTHON_PACKAGE_ROOTS

for term in RETIRED_PYTHON_PACKAGE_ROOTS:
    print(term)
PY
)
for term in "${retired_workflow_terms[@]}"; do
	require_workflows_absent "$term"
done

require_contains "$release" "name: Build and upload Python SDK to PyPI"
require_contains "$release" "SDK_VERSION="
require_contains "$release" "GITHUB_RUN_NUMBER"
require_contains "$release" "GITHUB_RUN_ATTEMPT"
require_contains "$release" "sdk/python/pyproject.toml"
require_contains "$release" "sdk/python/uv.lock"
require_contains "$release" "expected exactly one conbench lock version"
require_contains "$release" "legacy_floor = (2023, 4, 10)"
require_contains "$release" 'conbench-python-sdk-${{ env.SDK_VERSION }}'
require_contains "$release" "packages-dir: sdk/python/dist"
require_contains "$release" "CONBENCH_PYTHON_SDK_KEEP_DIST: \"1\""
require_contains "$publish_docs" "Build and upload Python SDK to PyPI"
require_contains "$publish_docs" "scripts/restore_docs_screenshot_artifacts.sh"
require_contains "$ci" "make docs-link-check"
require_job_contains "$ci" "workflows" "astral-sh/setup-uv"
require_job_contains "$ci" "sdk-python" "make migration-examples-test"
require_contains "$ci" "make docs-screenshots-check"
require_contains "$ci" "docs-screenshots:"
require_job_contains "$ci" "docs-screenshots" "contents: write"
require_absent "$ci" "continue-on-error: true"
require_contains "$ci" "make docs-screenshots"
require_job_contains "$ci" "docs-screenshots" "make docs-screenshots-check"
require_job_contains "$ci" "docs-screenshots" "scripts/publish_docs_screenshot_artifacts.sh"
require_job_contains "$ci" "docs-screenshots" "github.event_name == 'push'"
require_contains "$ci" "CONBENCH_DOCS_SCREENSHOT_OUT_DIR"
require_contains "$ci" "bun run check:docs-screenshots"
require_absent "$ci" "CONBENCH_DOCS_SCREENSHOT_INSTALL_BROWSER"
require_artifact_path "$ci" "bin/conbench"
require_artifact_path "$ci" '${{ runner.temp }}/conbench-dashboard-screenshots/*.png'
require_artifact_path "$ci" '${{ runner.temp }}/conbench-dashboard-screenshots/dashboard-screenshots-evidence.json'
require_contains "$makefile" "go run ./scripts/openapi_emit.go > api/openapi.yaml"
require_contains "$makefile" "go run ./scripts/openapi_emit.go --downgrade > api/openapi-3.0.yaml"
require_contains "$makefile" "build-docs: check-zensical-version docs-link-check docs-screenshots-check"
require_contains "$makefile" "workflow-shape-check: repo-hygiene-check"
require_contains "$makefile" "PYTHONDONTWRITEBYTECODE=1 uv run --with tomli python -B -m unittest scripts.test_repo_hygiene"
require_contains "$makefile" "PYTHONDONTWRITEBYTECODE=1 uv run --with tomli python -B scripts/repo_hygiene.py ."
require_contains "$makefile" "PYTHONDONTWRITEBYTECODE=1 uv run --with tomli python -B -m unittest scripts.test_check_workflows"
require_contains "$makefile" "PYTHONDONTWRITEBYTECODE=1 uv run --with tomli python -B -m unittest scripts.test_retired_python_surfaces"
require_contains "$makefile" "PYTHONDONTWRITEBYTECODE=1 uv run --with tomli python -B -m unittest scripts.test_python_sdk_artifact_hygiene"
require_contains "$makefile" "PYTHONDONTWRITEBYTECODE=1 uv run --with tomli python -B -m unittest scripts.test_docs_links"
require_contains "$makefile" "PYTHONDONTWRITEBYTECODE=1 uv run --with tomli python -B -m unittest scripts.test_docs_rendered_assets"
require_contains "$makefile" "PYTHONDONTWRITEBYTECODE=1 uv run --with tomli python -B -m unittest scripts.test_docs_migration_coverage"
require_contains "$makefile" "PYTHONDONTWRITEBYTECODE=1 uv run --with tomli python -B -m unittest scripts.test_check_migration_examples"
require_contains "$makefile" "PYTHONDONTWRITEBYTECODE=1 uv run --with tomli python -B scripts/docs_links.py"
require_contains "$makefile" "PYTHONDONTWRITEBYTECODE=1 uv run --with tomli python -B scripts/docs_migration_coverage.py docs/site sdk/python/README.md README.md"
require_contains "$makefile" "PYTHONDONTWRITEBYTECODE=1 uv run --with tomli python -B scripts/docs_rendered_assets.py docs/site/assets site/assets"
require_absent "$makefile" "cmd/conbench-openapi"
require_contains "$root/scripts/openapi_emit.go" "github.com/conbench/conbench/internal/server"
require_absent "$root/scripts/openapi_emit.go" "sdk/go/conbench"
require_contains "$docs_screenshot_script" "docker-compose.docs-screenshots.yml"
require_contains "$docs_screenshot_script" "docs-screenshots-runner"
require_contains "$docs_screenshot_script" "check_docs_screenshots.sh"
require_contains "$docs_screenshot_script" "https://conbench.example"
require_absent "$docs_screenshot_script" "bunx playwright install"
require_contains "$root/scripts/check_docs_screenshots.sh" "python3 -B -m unittest scripts.test_docs_screenshot_inventory"
require_contains "$root/scripts/check_docs_screenshots.sh" "python3 -B scripts/docs_screenshot_inventory.py"
require_contains "$root/scripts/check_docs_screenshots.sh" "python3 -B -m unittest scripts.test_docs_screenshot_pins"
require_contains "$root/scripts/check_docs_screenshots.sh" "python3 -B scripts/docs_screenshot_pins.py"
require_contains "$root/scripts/check_docs_screenshots.sh" "python3 -B -m unittest scripts.test_docs_screenshot_evidence"
require_contains "$root/scripts/check_docs_screenshots.sh" "python3 -B scripts/docs_screenshot_evidence.py check"
require_contains "$root/scripts/check_docs_screenshots.sh" 'CONBENCH_DOCS_SCREENSHOT_OUT_DIR:-'
require_contains "$root/scripts/check_docs_screenshots.sh" "docs screenshot artifact checks skipped"
require_contains "$root/scripts/docs_screenshot_inventory.py" "appears blank"
require_contains "$root/scripts/docs_screenshot_inventory.py" "referenced_dashboard_screenshots"
require_file "$root/scripts/docs_screenshot_evidence.py"
require_file "$root/web/docs-screenshots/screenshots.json"
require_contains "$gitignore" "/docs/site/assets/screenshots/*.png"
require_contains "$gitignore" "/docs/site/assets/screenshots/dashboard-screenshots-evidence.json"
require_contains "$docs_screenshot_page" "deterministic demo database"
require_contains "$docs_screenshot_page" "web/docs-screenshots/screenshots.json"
require_contains "$docs_screenshot_page" "pinned Playwright container"
require_contains "$docs_screenshot_page" "dashboard-screenshots-evidence.json"
require_contains "$docs_screenshot_page" "https://conbench.example"
require_contains "$docs_screenshot_page" 'orphan `docs-screenshots` branch'
require_contains "$docs_screenshot_page" "chart canvases must be painted"
require_contains "$docs_screenshot_page" "mobile primary navigation must remain visible"
require_contains "$docs_screenshot_page" "single flat color"
require_contains "$docs_screenshot_page" "not committed to"
require_contains "$docs_screenshot_page" "publishes the latest deterministic dashboard PNGs"
require_workflows_absent "bin/conbench-server"
require_workflows_absent "/usr/local/bin/conbench-server"
require_workflows_absent "cmd/conbench-server"

if [ "$failures" -ne 0 ]; then
	echo "workflow shape check failed with $failures issue(s)" >&2
	exit 1
fi

echo "workflow shape check OK"
