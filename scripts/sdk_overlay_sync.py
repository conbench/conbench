#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import sys
from pathlib import Path, PurePosixPath


class OverlaySyncError(Exception):
    pass


def validate_overlay_sync(root: Path) -> int:
    manifest_path = root / "sdk/python/overlays/manifest.txt"
    managed_targets_path = root / "sdk/python/overlays/managed-targets.txt"
    overlay_root = manifest_path.parent
    generated_root = root / "sdk" / "python"
    if not overlay_root.is_dir():
        raise OverlaySyncError(f"missing Python SDK overlay directory: {overlay_root}")
    manifest = read_manifest(manifest_path)
    managed_targets = read_manifest(managed_targets_path)
    manifest_set = set(manifest)
    managed_target_set = set(managed_targets)
    unmanaged_active = sorted(manifest_set - managed_target_set)
    if unmanaged_active:
        raise OverlaySyncError("active overlay missing from managed targets: " + ", ".join(unmanaged_active))

    source_names = {
        path.relative_to(overlay_root).as_posix()
        for path in overlay_root.rglob("*")
        if path.is_file() and path not in {manifest_path, managed_targets_path}
    }
    untracked = sorted(source_names - manifest_set)
    if untracked:
        raise OverlaySyncError("overlay source missing from manifest: " + ", ".join(untracked))

    retired_stale = sorted(label for label in managed_target_set - manifest_set if (generated_root / label).is_file())
    if retired_stale:
        raise OverlaySyncError("stale generated SDK overlay copy without active source: " + ", ".join(retired_stale))

    stale: list[str] = []
    missing_source: list[str] = []
    missing: list[str] = []
    changed: list[str] = []
    for label in manifest:
        relative = Path(label)
        overlay = overlay_root / relative
        generated = generated_root / relative
        if not overlay.is_file():
            if generated.is_file():
                stale.append(label)
            else:
                missing_source.append(label)
            continue
        if not generated.is_file():
            missing.append(label)
            continue
        if file_digest(overlay) != file_digest(generated):
            changed.append(label)

    if stale:
        raise OverlaySyncError("stale generated SDK overlay copy without source: " + ", ".join(stale))
    if missing_source:
        raise OverlaySyncError("missing SDK overlay source: " + ", ".join(missing_source))
    if missing:
        raise OverlaySyncError("missing generated SDK overlay copy: " + ", ".join(missing))
    if changed:
        raise OverlaySyncError("generated SDK overlay copy differs: " + ", ".join(changed))
    return len(manifest)


def read_manifest(manifest_path: Path) -> list[str]:
    if not manifest_path.is_file():
        raise OverlaySyncError(f"missing Python SDK overlay manifest: {manifest_path}")
    entries: list[str] = []
    seen: set[str] = set()
    for line_number, raw in enumerate(manifest_path.read_text(encoding="utf-8").splitlines(), start=1):
        line = raw.split("#", 1)[0].strip()
        if not line:
            continue
        path = PurePosixPath(line)
        if path.is_absolute() or any(part in {"", ".", ".."} for part in path.parts):
            raise OverlaySyncError(f"invalid overlay manifest path on line {line_number}: {raw}")
        label = path.as_posix()
        if label in seen:
            raise OverlaySyncError(f"duplicate overlay manifest path on line {line_number}: {label}")
        seen.add(label)
        entries.append(label)
    if not entries:
        raise OverlaySyncError(f"empty Python SDK overlay manifest: {manifest_path}")
    return entries


def file_digest(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def main(argv: list[str]) -> int:
    if len(argv) != 2:
        print("usage: sdk_overlay_sync.py <repo-root>", file=sys.stderr)
        return 2
    try:
        count = validate_overlay_sync(Path(argv[1]))
    except OverlaySyncError as exc:
        print(str(exc), file=sys.stderr)
        return 1
    print(f"Python SDK overlays synchronized ({count} files)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
