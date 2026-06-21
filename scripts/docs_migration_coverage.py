#!/usr/bin/env python3
from __future__ import annotations

import re
import sys
from pathlib import Path


class MigrationCoverageError(Exception):
    pass


REQUIRED_MIGRATION_GUIDE_PHRASES: tuple[str, ...] = (
    "# Migrating From The Legacy Python Conbench App",
    "The new system is not a source-compatible Python port.",
    "`benchconnect submit` and direct POST helpers | `conbench results submit`",
    "`benchalerts` PR checks/comments | `conbench ci report`",
    "There is no new `conbench_client` package.",
    "`benchadapt` package code is deleted",
    "`conbench.migration` helper",
    "`benchconnect` and `benchclients` are deleted",
    "`benchclients.ConbenchClient` is retired",
    "This replaces `benchalerts` for synchronous PR diagnostics",
    "`benchrun` package code is deleted",
    "`conbenchlegacy` package code is deleted",
    "examples/migration/gbench_to_cli_submit.py",
    "the repository root and `sdk/python` on `PYTHONPATH`",
    "## Package-By-Package Outcome",
    "Any compatibility shim, import alias, or replacement helper",
)

REQUIRED_DEPRECATION_NOTICE_PHRASES: tuple[str, ...] = (
    "# Legacy Package Deprecation Notices",
    "without promising source-compatible shims for retired packages",
    "There is no new `conbench_client` package.",
    "## `benchadapt`",
    "Submit with `conbench results submit \"bench-results/*.json\"`.",
    "## `benchconnect`",
    "`benchconnect` is retired.",
    "## `benchclients`",
    "`benchclients` is retired.",
    "## `benchalerts`",
    "`benchalerts` is retired as a maintained Python client package.",
    "## `benchrun` And `conbenchlegacy`",
    "`benchrun` and `conbenchlegacy` are retired.",
    "## Retired Flask App Package",
    "## Publication Runbook",
    "Use the package-specific block above as the package README/PyPI long-description notice.",
    "Post-publication verification",
    "confirm every notice links back to the migration guide, parity roadmap, and runnable migration recipe",
    "the supported Python read client: generated SDK package `conbench`",
)

REQUIRED_ROOT_README_PHRASES: tuple[str, ...] = (
    "# Conbench",
    "For existing Python/Flask Conbench deployments",
    "migration guide",
    "legacy parity roadmap",
    "legacy deprecation notices",
    "The legacy Flask application and old Python client stack have been",
    "submit result JSON with `conbench results submit`",
    "The generated Python SDK installs and imports as `conbench`",
    "there is no supported `conbench_client` import",
    "Do not install it beside the retired Flask application package",
    "`conbench/` (the Flask app), `benchadapt/`, `benchclients/`, `benchconnect/`",
    "`benchrun/`, `benchalerts/`, and the old `legacy/conbenchlegacy` runner",
    "examples/migration/",
    "retired Python app/package paths and single-file module names stay untracked",
    "Legacy package publishing is retired",
)

REQUIRED_SDK_README_PHRASES: tuple[str, ...] = (
    "# conbench Python SDK",
    "Install and import this package as `conbench`",
    "Do not install the retired Flask application package",
    "Use the Go `conbench` CLI for writes",
    "CI jobs should pass the API token through `CONBENCH_TOKEN`",
    "## Migration from the retired Python/Flask application",
    "The retired Flask application and old Python packages are not source-compatible",
    "`conbench.migration`",
    "The helper does not replace `benchadapt` or `benchconnect`",
    "https://conbench.github.io/conbench/migration/python-app/",
    "https://conbench.github.io/conbench/migration/deprecation-notices/",
    "https://conbench.github.io/conbench/migration/legacy-parity-roadmap/",
    "examples/migration/gbench_to_cli_submit.py",
)

REQUIRED_API_AND_SDK_PHRASES: tuple[str, ...] = (
    "# API And SDK",
    "The generated Python SDK distribution and import package are both `conbench`",
    "During a Python-app migration, do not install the retired Flask application package and the new generated SDK",
    "The SDK is intended for reads and automation. Writes should use the Go CLI",
    "`conbench.migration` helper",
    "The `conbench.migration` helper is intentionally not a source-compatible `benchadapt` or `benchconnect` replacement.",
    "There is no supported `conbench_client` import.",
    "Benchmark jobs that only submit results do not need the Python SDK at all; they can emit JSON files and call the Go CLI.",
    "[Python app migration guide](migration/python-app.md)",
    "[legacy package deprecation notices](migration/deprecation-notices.md)",
    "[legacy parity roadmap](migration/legacy-parity-roadmap.md)",
)

REQUIRED_CONTRIBUTING_PHRASES: tuple[str, ...] = (
    "# Contributing",
    "`make repo-hygiene-check` verifies that retired top-level Python package paths, single-file module names",
    "`scripts/retired_python_surfaces.py` is the shared source of truth for retired Python package names, single-file module names, and path prefixes",
    "rejects imports from retired legacy packages",
    "rejects split command directories such as `cmd/conbench-server` and `cmd/conbench-openapi`",
    "rejects retired package directories and single-file modules from built wheel and sdist artifacts",
    "migration coverage for the public migration pages, API and SDK page, SDK README, and root README",
    "Durable product, migration, and operations decisions should be recorded in `docs/site/`",
    "Tracked documentation content belongs under `docs/site/`",
    "`.superpowers/` is local scratch state",
)


def normalize_markdown(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def validate_required_phrases(path: Path, phrases: tuple[str, ...]) -> int:
    if not path.is_file():
        raise MigrationCoverageError(f"missing migration docs page: {path}")
    text = normalize_markdown(path.read_text(encoding="utf-8"))
    missing = [phrase for phrase in phrases if normalize_markdown(phrase) not in text]
    if missing:
        label = coverage_label(path)
        raise MigrationCoverageError(f"{label} missing migration coverage: " + ", ".join(missing))
    return len(phrases)


def coverage_label(path: Path) -> str:
    if not path.is_absolute():
        return path.as_posix()
    try:
        return path.relative_to(Path.cwd()).as_posix()
    except ValueError:
        return path.as_posix()


def validate_migration_docs(
    docs_dir: Path,
    *,
    root_readme: Path | None = None,
    sdk_readme: Path | None = None,
) -> int:
    guide_count = validate_required_phrases(
        docs_dir / "migration" / "python-app.md",
        REQUIRED_MIGRATION_GUIDE_PHRASES,
    )
    notices_count = validate_required_phrases(
        docs_dir / "migration" / "deprecation-notices.md",
        REQUIRED_DEPRECATION_NOTICE_PHRASES,
    )
    api_and_sdk_count = validate_required_phrases(
        docs_dir / "api-and-sdk.md",
        REQUIRED_API_AND_SDK_PHRASES,
    )
    contributing_count = validate_required_phrases(
        docs_dir / "contributing.md",
        REQUIRED_CONTRIBUTING_PHRASES,
    )
    readme_count = 0
    if root_readme is not None:
        readme_count = validate_required_phrases(root_readme, REQUIRED_ROOT_README_PHRASES)
    sdk_count = 0
    if sdk_readme is not None:
        sdk_count = validate_required_phrases(sdk_readme, REQUIRED_SDK_README_PHRASES)
    return guide_count + notices_count + api_and_sdk_count + contributing_count + readme_count + sdk_count


def main(argv: list[str]) -> int:
    docs_dir = Path(argv[1]) if len(argv) >= 2 else Path("docs/site")
    sdk_readme = Path(argv[2]) if len(argv) >= 3 else Path("sdk/python/README.md")
    root_readme = Path(argv[3]) if len(argv) >= 4 else Path("README.md")
    try:
        count = validate_migration_docs(
            docs_dir,
            root_readme=root_readme,
            sdk_readme=sdk_readme,
        )
    except MigrationCoverageError as exc:
        print(str(exc), file=sys.stderr)
        return 1
    print(f"docs migration coverage OK ({count} required phrases)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
