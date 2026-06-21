#!/usr/bin/env python3
from __future__ import annotations

import sys
import tarfile
import zipfile
from pathlib import Path

try:
    from scripts.retired_python_surfaces import (
        RETIRED_PYTHON_MODULE_FILES,
        RETIRED_PYTHON_PACKAGE_ROOTS,
    )
except ModuleNotFoundError:
    from retired_python_surfaces import (  # type: ignore[no-redef]
        RETIRED_PYTHON_MODULE_FILES,
        RETIRED_PYTHON_PACKAGE_ROOTS,
    )


class ArtifactHygieneError(Exception):
    pass


RETIRED_PACKAGE_DIRS: tuple[str, ...] = RETIRED_PYTHON_PACKAGE_ROOTS
RETIRED_MODULE_FILES: tuple[str, ...] = RETIRED_PYTHON_MODULE_FILES


def find_retired_payload_members(names: list[str]) -> list[str]:
    leaked: list[str] = []
    for name in names:
        normalized = name.replace("\\", "/")
        parts = [part for part in normalized.split("/") if part]
        if any(part in RETIRED_PACKAGE_DIRS for part in parts):
            leaked.append(normalized)
            continue
        if parts and parts[-1] in RETIRED_MODULE_FILES:
            leaked.append(normalized)
    return sorted(set(leaked))


def archive_members(artifact: Path) -> list[str]:
    artifact_text = artifact.as_posix()
    if artifact_text.endswith(".whl"):
        with zipfile.ZipFile(artifact) as archive:
            return archive.namelist()
    if artifact_text.endswith(".tar.gz"):
        with tarfile.open(artifact, "r:gz") as archive:
            return archive.getnames()
    raise ArtifactHygieneError(f"unsupported SDK artifact type: {artifact}")


def validate_python_sdk_artifact(artifact: Path) -> int:
    leaked = find_retired_payload_members(archive_members(artifact))
    if leaked:
        joined = "\n".join(leaked)
        raise ArtifactHygieneError(f"retired legacy package payload leaked into {artifact}:\n{joined}")
    return 0


def main(argv: list[str]) -> int:
    if len(argv) < 2:
        print("usage: python_sdk_artifact_hygiene.py <artifact> [<artifact> ...]", file=sys.stderr)
        return 2
    try:
        for artifact in argv[1:]:
            validate_python_sdk_artifact(Path(artifact))
    except ArtifactHygieneError as exc:
        print(str(exc), file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
