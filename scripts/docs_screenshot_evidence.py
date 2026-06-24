#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scripts.docs_screenshot_inventory import InventoryError, assert_nonblank_png, read_png


class EvidenceError(Exception):
    pass


def write_evidence(manifest_path: Path, asset_dir: Path, evidence_path: Path) -> int:
    evidence = build_evidence(manifest_path, asset_dir)
    evidence_path.write_text(json.dumps(evidence, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return len(evidence["screenshots"])


def validate_evidence(manifest_path: Path, asset_dir: Path, evidence_path: Path) -> int:
    if not evidence_path.is_file():
        raise EvidenceError(f"missing screenshot evidence: {evidence_path}")
    try:
        actual = json.loads(evidence_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise EvidenceError(f"invalid screenshot evidence JSON: {evidence_path}") from exc
    expected = build_evidence(manifest_path, asset_dir)
    if actual != expected:
        raise EvidenceError(f"{evidence_path} does not match current screenshot evidence")
    return len(expected["screenshots"])


def build_evidence(manifest_path: Path, asset_dir: Path) -> dict:
    if not manifest_path.is_file():
        raise EvidenceError(f"missing screenshot manifest: {manifest_path}")
    if not asset_dir.is_dir():
        raise EvidenceError(f"missing screenshot asset directory: {asset_dir}")

    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    viewports = manifest.get("viewports")
    screenshots = manifest.get("screenshots")
    if not isinstance(viewports, dict) or not viewports:
        raise EvidenceError("screenshot manifest must define non-empty viewports")
    if not isinstance(screenshots, list) or not screenshots:
        raise EvidenceError("screenshot manifest must define non-empty screenshots")

    evidence_screenshots: list[dict] = []
    for item in screenshots:
        if not isinstance(item, dict):
            raise EvidenceError("each screenshot manifest entry must be an object")
        screenshot_id = required_string(item, "id")
        title = required_string(item, "title")
        route = required_string(item, "path")
        purpose = required_string(item, "purpose")
        for viewport_name, viewport in viewports.items():
            if not isinstance(viewport, dict):
                raise EvidenceError(f"viewport {viewport_name!r} must be an object")
            expected_width = int(viewport["width"])
            expected_height = int(viewport["height"])
            filename = f"dashboard-{screenshot_id}-{viewport_name}.png"
            screenshot_path = asset_dir / filename
            png = read_png(screenshot_path)
            try:
                assert_nonblank_png(filename, png)
            except InventoryError as exc:
                raise EvidenceError(str(exc)) from exc
            if (png.width, png.height) != (expected_width, expected_height):
                raise EvidenceError(
                    f"{filename} has size {(png.width, png.height)}, expected {(expected_width, expected_height)}"
                )
            evidence_screenshots.append(
                {
                    "bytes": screenshot_path.stat().st_size,
                    "file": filename,
                    "height": png.height,
                    "id": screenshot_id,
                    "purpose": purpose,
                    "route": route,
                    "sha256": hashlib.sha256(screenshot_path.read_bytes()).hexdigest(),
                    "title": title,
                    "viewport": viewport_name,
                    "width": png.width,
                }
            )

    return {
        "artifact": "conbench-dashboard-screenshots",
        "data_source": "deterministic demo database seeded by the Go server container",
        "isolation": [
            "docker-compose.server.yml",
            "docker-compose.docs-screenshots.yml",
            "Dockerfile.docs-screenshots pinned Playwright container",
        ],
        "quality_checks": [
            "manifest routes and viewport inventory are checked",
            "PNG dimensions match the screenshot manifest",
            "PNG pixels are nonblank and not a single flat color",
            "chart canvases are painted before capture",
            "desktop pages have no document-level horizontal overflow",
            "mobile primary navigation remains visible",
            "volatile generated result IDs are normalized",
            "internal screenshot server origins are scrubbed",
            "pinned Playwright container version matches web/package.json",
        ],
        "schema_version": 1,
        "screenshots": evidence_screenshots,
        "viewports": viewports,
    }


def required_string(item: dict, key: str) -> str:
    value = item.get(key)
    if not isinstance(value, str) or value.strip() == "":
        raise EvidenceError(f"screenshot {item.get('id')!r} must define a non-empty {key}")
    return value.strip()


def main(argv: list[str]) -> int:
    if len(argv) != 5 or argv[1] not in {"write", "check"}:
        print("usage: docs_screenshot_evidence.py <write|check> <manifest> <asset-dir> <evidence-file>", file=sys.stderr)
        return 2
    command = argv[1]
    manifest = Path(argv[2])
    asset_dir = Path(argv[3])
    evidence = Path(argv[4])
    try:
        if command == "write":
            count = write_evidence(manifest, asset_dir, evidence)
            print(f"docs screenshot evidence written ({count} screenshots)")
        else:
            count = validate_evidence(manifest, asset_dir, evidence)
            print(f"docs screenshot evidence OK ({count} screenshots)")
    except (EvidenceError, InventoryError, json.JSONDecodeError, OSError, ValueError) as exc:
        print(str(exc), file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
