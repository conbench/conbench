#!/usr/bin/env python3
from __future__ import annotations

import argparse
import ast
import subprocess
import sys
from pathlib import Path

try:
    from scripts.retired_python_surfaces import (
        RETIRED_PYTHON_MODULE_FILES,
        RETIRED_PYTHON_PACKAGE_ROOTS,
        RETIRED_PYTHON_PATH_PREFIXES,
    )
except ModuleNotFoundError:
    from retired_python_surfaces import (  # type: ignore[no-redef]
        RETIRED_PYTHON_MODULE_FILES,
        RETIRED_PYTHON_PACKAGE_ROOTS,
        RETIRED_PYTHON_PATH_PREFIXES,
    )


class RepoHygieneError(Exception):
    pass


RETIRED_PATH_PREFIXES: tuple[str, ...] = (
    ".buildkite",
    ".github/workflows/actions.yml",
    ".superpowers",
    "cmd/conbench-openapi",
    "cmd/conbench-server",
    *RETIRED_PYTHON_PATH_PREFIXES,
    "ci",
    "conbench",
    "docs/Makefile",
    "docs/_build",
    "docs/.doctrees",
    "docs/_static",
    "docs/_templates",
    "docs/api_docs",
    "docs/conf.py",
    "docs/dev",
    "docs/index.rst",
    "docs/pages",
    "docs/superpowers",
    "internal/buildinfo",
    "k8s/kube-prometheus",
    "legacy",
    "scripts/check_legacy_python_burndown.sh",
)

RETIRED_ROOT_FILES: tuple[str, ...] = (
    ".coveragerc",
    ".flaskenv",
    ".flake8",
    ".isort.cfg",
    ".pylintrc",
    ".python-version",
    ".readthedocs.yaml",
    ".readthedocs.yml",
    "Pipfile",
    "Pipfile.lock",
    "Procfile",
    "MANIFEST.in",
    "app.json",
    "conftest.py",
    "constraints.txt",
    "conda-lock.yml",
    "conda-lock.yaml",
    "conbench-config.yml",
    "conbench-secret.yml",
    "conbench.png",
    "environment.yml",
    "environment.yaml",
    "flit.ini",
    "hatch.toml",
    "mypy.ini",
    "noxfile.py",
    "pdm.lock",
    "pdm.toml",
    "pixi.lock",
    "pixi.toml",
    "poetry.lock",
    "poetry.toml",
    "pyproject.toml",
    "pytest.ini",
    "readthedocs.yaml",
    "readthedocs.yml",
    "requirements-dev.txt",
    "requirements-webapp.txt",
    "requirements.in",
    "requirements.txt",
    "runtime.txt",
    "setup.cfg",
    "setup.py",
    "tox.ini",
    "uv.lock",
    "uv.toml",
)

ALLOWED_PYTHON_PREFIXES: tuple[str, ...] = (
    "examples/migration/",
    "migrations/",
    "scripts/",
    "sdk/python/",
)

ALLOWED_DOCS_PREFIXES: tuple[str, ...] = (
    "docs/site/",
)

RETIRED_IMPORT_ROOTS: tuple[str, ...] = RETIRED_PYTHON_PACKAGE_ROOTS
RETIRED_MODULE_FILES: tuple[str, ...] = RETIRED_PYTHON_MODULE_FILES


def validate_repo_hygiene(root: Path, *, tracked_files: list[str] | None = None) -> int:
    files = tracked_files if tracked_files is not None else git_tracked_files(root)
    normalized = sorted(path for path in (normalize_path(path) for path in files) if path)
    failures: list[str] = []

    for path in normalized:
        if is_retired_path(path):
            failures.append(f"retired legacy path is tracked: {path}")
        if is_unscoped_docs_path(path):
            failures.append(f"documentation outside docs/site is tracked: {path}")
        if path.endswith(".py"):
            if not path.startswith(ALLOWED_PYTHON_PREFIXES):
                failures.append(f"Python file outside allowed roots: {path}")
            else:
                failures.extend(retired_import_failures(root, path))

    if failures:
        raise RepoHygieneError("\n".join(failures))
    return len(normalized)


def git_tracked_files(root: Path) -> list[str]:
    proc = subprocess.run(
        ["git", "-C", str(root), "ls-files", "-z"],
        check=False,
        capture_output=True,
        text=False,
    )
    if proc.returncode != 0:
        raise RepoHygieneError(proc.stderr.decode(errors="replace").strip() or "git ls-files failed")
    return [entry.decode() for entry in proc.stdout.split(b"\0") if entry]


def is_retired_path(path: str) -> bool:
    if path in RETIRED_ROOT_FILES:
        return True
    if Path(path).name in RETIRED_MODULE_FILES:
        return True
    for prefix in RETIRED_PATH_PREFIXES:
        if path == prefix or path.startswith(prefix + "/"):
            return True
    return False


def is_unscoped_docs_path(path: str) -> bool:
    return path.startswith("docs/") and not path.startswith(ALLOWED_DOCS_PREFIXES)


def retired_import_failures(root: Path, path: str) -> list[str]:
    source_path = root / path
    if not source_path.is_file():
        return []
    try:
        tree = ast.parse(source_path.read_text(encoding="utf-8"), filename=path)
    except SyntaxError as exc:
        line = exc.lineno or 1
        return [f"{path}:{line}: could not parse Python file for repo hygiene: {exc.msg}"]

    failures: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                root_name = import_root(alias.name)
                if root_name in RETIRED_IMPORT_ROOTS:
                    failures.append(f"{path}:{node.lineno}: retired legacy import: {root_name}")
        elif isinstance(node, ast.ImportFrom) and node.module:
            root_name = import_root(node.module)
            if root_name in RETIRED_IMPORT_ROOTS:
                failures.append(f"{path}:{node.lineno}: retired legacy import: {root_name}")
    return failures


def import_root(module: str) -> str:
    return module.split(".", 1)[0]


def normalize_path(path: str) -> str:
    normalized = path.replace("\\", "/")
    while normalized.startswith("./"):
        normalized = normalized[2:]
    return normalized


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Check that retired Conbench repository paths stay untracked.")
    parser.add_argument("root", nargs="?", default=".")
    parser.add_argument(
        "--tracked-file",
        action="append",
        default=None,
        help="Use an explicit tracked file entry instead of git ls-files; mainly for tests.",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(sys.argv[1:] if argv is None else argv)
    try:
        count = validate_repo_hygiene(Path(args.root), tracked_files=args.tracked_file)
    except RepoHygieneError as exc:
        print(str(exc), file=sys.stderr)
        return 1
    print(f"repo hygiene OK ({count} tracked files)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
