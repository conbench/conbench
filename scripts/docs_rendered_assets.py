#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import sys
from pathlib import Path


class RenderedAssetsError(Exception):
    pass


def validate_rendered_assets(source_assets: Path, rendered_assets: Path) -> int:
    if not source_assets.exists():
        return 0
    if not source_assets.is_dir():
        raise RenderedAssetsError(f"missing source docs asset directory: {source_assets}")
    source_files = sorted(path for path in source_assets.rglob("*") if path.is_file())
    if not source_files:
        return 0
    if not rendered_assets.is_dir():
        raise RenderedAssetsError(f"missing rendered docs asset directory: {rendered_assets}")

    source_names = {path.relative_to(source_assets).as_posix() for path in source_files}
    source_roots = {Path(name).parts[0] for name in source_names}
    rendered_names = {
        relative.as_posix()
        for path in rendered_assets.rglob("*")
        if path.is_file()
        for relative in [path.relative_to(rendered_assets)]
        if relative.parts and relative.parts[0] in source_roots
    }
    missing: list[str] = []
    changed: list[str] = []
    for source in source_files:
        relative = source.relative_to(source_assets)
        rendered = rendered_assets / relative
        label = relative.as_posix()
        if not rendered.is_file():
            missing.append(label)
            continue
        if file_digest(source) != file_digest(rendered):
            changed.append(label)

    if missing:
        raise RenderedAssetsError("missing rendered asset(s): " + ", ".join(missing))
    extra = sorted(rendered_names - source_names)
    if extra:
        raise RenderedAssetsError("unexpected rendered asset(s): " + ", ".join(extra))
    if changed:
        raise RenderedAssetsError("rendered asset differs from source: " + ", ".join(changed))
    return len(source_files)


def file_digest(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def main(argv: list[str]) -> int:
    if len(argv) != 3:
        print("usage: docs_rendered_assets.py <source-assets-dir> <rendered-assets-dir>", file=sys.stderr)
        return 2
    try:
        count = validate_rendered_assets(Path(argv[1]), Path(argv[2]))
    except RenderedAssetsError as exc:
        print(str(exc), file=sys.stderr)
        return 1
    print(f"rendered docs assets OK ({count} files)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
