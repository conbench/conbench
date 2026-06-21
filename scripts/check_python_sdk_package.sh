#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SDK="$ROOT/sdk/python"

keep_dist="${CONBENCH_PYTHON_SDK_KEEP_DIST:-0}"
scratch="$(mktemp -d)"
tmp_dirs=()

cleanup_artifacts() {
	local preserve_dist="${1:-0}"
	if [ "$preserve_dist" != "1" ]; then
		rm -rf "$SDK/dist"
	fi
	rm -rf "$SDK/build" "$SDK/.pytest_cache" "$SDK/.ruff_cache" "$SDK/.venv"
	rm -rf "$SDK"/*.egg-info
	find "$SDK" -type d \( -name "__pycache__" -o -name ".ruff_cache" \) -prune -exec rm -rf {} +
}

cleanup() {
	status=$?
	for dir in "${tmp_dirs[@]}"; do
		rm -rf "$dir"
	done
	rm -rf "$scratch"
	cleanup_artifacts "$keep_dist"
	exit "$status"
}
trap cleanup EXIT

cd "$SDK"
cleanup_artifacts
export PYTHONDONTWRITEBYTECODE=1
export UV_PROJECT_ENVIRONMENT="$scratch/uv-project-env"

uv run --locked python -m build --no-isolation --sdist --wheel
uv run --locked twine check dist/*

shopt -s nullglob
artifacts=(dist/*.whl dist/*.tar.gz)
if [ "${#artifacts[@]}" -eq 0 ]; then
	echo "no Python SDK artifacts found in dist/" >&2
	exit 1
fi

for artifact in "${artifacts[@]}"; do
	artifact_path="$SDK/$artifact"
	uv run --locked python "$ROOT/scripts/python_sdk_artifact_hygiene.py" "$artifact_path"
	venv="$(mktemp -d)"
	tmp_dirs+=("$venv")
	constraints="$venv/build-constraints.txt"

	echo "checking Python SDK artifact: $artifact"
	uv run --locked python -m venv "$venv"
	uv run --locked python - <<'PY' >"$constraints"
from importlib.metadata import version

for package in ("setuptools", "wheel"):
    print(f"{package}=={version(package)}")
PY
	if [[ "$artifact" == *.tar.gz ]]; then
		"$venv/bin/python" -m pip install -c "$constraints" setuptools wheel
		"$venv/bin/python" -m pip install --no-build-isolation "$artifact_path"
	else
		"$venv/bin/python" -m pip install "$artifact_path"
	fi
	(cd "$venv" && PYTHONPATH= "$venv/bin/python" - <<'PY'
from importlib.metadata import metadata
from conbench import Client, AuthenticatedClient
from conbench.api.default import compare_benchmark_results, get_ci_report, list_series
from conbench.migration import submit_results, write_result_payloads
from conbench.models import CIReport, CIReportSummary, CompareResult, SeriesPage

meta = metadata("conbench")
assert meta["Name"] == "conbench"
project_urls = set(meta.get_all("Project-URL") or [])
assert "Documentation, https://conbench.github.io/conbench/" in project_urls
assert "Migration Guide, https://conbench.github.io/conbench/migration/python-app/" in project_urls
description = meta.get_payload()
normalized_description = " ".join(description.split())
assert "conbench_client" not in description
assert "python -m pip install conbench" in description
assert "https://conbench.github.io/conbench/migration/python-app/" in description
assert "https://conbench.github.io/conbench/migration/legacy-parity-roadmap/" in description
assert "https://github.com/conbench/conbench/blob/main/examples/migration/gbench_to_cli_submit.py" in description
assert "Use the Go `conbench` CLI for writes" in normalized_description
assert "Do not install the retired Flask application package" in normalized_description
assert "Migration from the retired Python/Flask application" in normalized_description

assert Client is not None
assert AuthenticatedClient is not None
assert hasattr(compare_benchmark_results, "sync_detailed")
assert hasattr(get_ci_report, "sync_detailed")
assert hasattr(list_series, "sync_detailed")
assert callable(submit_results)
assert callable(write_result_payloads)
assert CIReport is not None
assert CIReportSummary is not None
assert CompareResult is not None
assert SeriesPage is not None
PY
	)
done
