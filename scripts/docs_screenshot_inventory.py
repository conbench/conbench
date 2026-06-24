#!/usr/bin/env python3
from __future__ import annotations

import json
import re
import struct
import sys
import zlib
from collections import Counter
from pathlib import Path
from urllib.parse import urlsplit


class InventoryError(Exception):
    pass


IMAGE_LINK_RE = re.compile(r"!\[[^\]\n]*\]\(([^)\n]+)\)")
DASHBOARD_SCREENSHOT_RE = re.compile(r"^dashboard-[a-z0-9-]+\.png$")


def validate_inventory(manifest_path: Path, docs_page: Path, asset_dir: Path | None = None) -> int:
    if not manifest_path.is_file():
        raise InventoryError(f"missing screenshot manifest: {manifest_path}")
    if not docs_page.is_file():
        raise InventoryError(f"missing screenshot documentation page: {docs_page}")

    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    viewports = manifest.get("viewports")
    screenshots = manifest.get("screenshots")
    if not isinstance(viewports, dict) or not viewports:
        raise InventoryError("screenshot manifest must define non-empty viewports")
    if not isinstance(screenshots, list) or not screenshots:
        raise InventoryError("screenshot manifest must define non-empty screenshots")

    seen_ids: set[str] = set()
    expected_files: dict[str, tuple[int, int]] = {}
    expected_titles: set[str] = set()
    expected_paths: set[str] = set()
    expected_purposes: set[str] = set()
    for item in screenshots:
        if not isinstance(item, dict):
            raise InventoryError("each screenshot manifest entry must be an object")
        screenshot_id = item.get("id")
        if not isinstance(screenshot_id, str) or not re.fullmatch(r"[a-z0-9]+(?:-[a-z0-9]+)*", screenshot_id):
            raise InventoryError(f"invalid screenshot id: {screenshot_id!r}")
        if screenshot_id in seen_ids:
            raise InventoryError(f"duplicate screenshot id: {screenshot_id}")
        seen_ids.add(screenshot_id)
        title = item.get("title")
        if not isinstance(title, str) or title.strip() == "":
            raise InventoryError(f"screenshot {screenshot_id!r} must define a non-empty title")
        expected_titles.add(title.strip())
        path = item.get("path")
        if not isinstance(path, str) or path.strip() == "":
            raise InventoryError(f"screenshot {screenshot_id!r} must define a non-empty path")
        expected_paths.add(path.strip())
        purpose = item.get("purpose")
        if not isinstance(purpose, str) or purpose.strip() == "":
            raise InventoryError(f"screenshot {screenshot_id!r} must define a non-empty purpose")
        expected_purposes.add(purpose.strip())

        for viewport_name, viewport in viewports.items():
            if not isinstance(viewport, dict):
                raise InventoryError(f"viewport {viewport_name!r} must be an object")
            try:
                width = int(viewport["width"])
                height = int(viewport["height"])
            except (KeyError, TypeError, ValueError) as exc:
                raise InventoryError(f"viewport {viewport_name!r} must define integer width and height") from exc
            expected_files[f"dashboard-{screenshot_id}-{viewport_name}.png"] = (width, height)

    expected_names = set(expected_files)
    if asset_dir is not None:
        if not asset_dir.is_dir():
            raise InventoryError(f"missing screenshot asset directory: {asset_dir}")

        pngs = {path.name for path in asset_dir.glob("dashboard-*.png")}
        missing = sorted(expected_names - pngs)
        extra = sorted(pngs - expected_names)
        if missing:
            raise InventoryError("missing screenshot(s): " + ", ".join(missing))
        if extra:
            raise InventoryError("unexpected screenshot(s): " + ", ".join(extra))

        for filename, expected_size in sorted(expected_files.items()):
            png = read_png(asset_dir / filename)
            if (png.width, png.height) != expected_size:
                raise InventoryError(f"{filename} has size {(png.width, png.height)}, expected {expected_size}")
            assert_nonblank_png(filename, png)

    docs = docs_page.read_text(encoding="utf-8")
    referenced = referenced_dashboard_screenshots(docs)
    missing_refs = sorted(expected_names - referenced)
    unknown_refs = sorted(referenced - expected_names)
    if missing_refs:
        raise InventoryError("screenshot(s) missing from docs page: " + ", ".join(missing_refs))
    if unknown_refs:
        raise InventoryError("docs page references unknown screenshot(s): " + ", ".join(unknown_refs))

    visible_labels = "\n".join(
        label
        for match in re.findall(r"^#+\s+(.+)$|!\[([^\]]*)\]\([^)]*\)", docs, flags=re.MULTILINE)
        for label in match
        if label
    )
    visible_labels_casefolded = visible_labels.casefold()
    missing_titles = sorted(title for title in expected_titles if title.casefold() not in visible_labels_casefolded)
    if missing_titles:
        raise InventoryError("screenshot title(s) missing from docs page: " + ", ".join(missing_titles))
    code_spans = set(re.findall(r"`([^`\n]+)`", docs))
    missing_paths = sorted(path for path in expected_paths if path not in code_spans)
    if missing_paths:
        raise InventoryError("screenshot path(s) missing from docs page: " + ", ".join(missing_paths))
    docs_casefolded = docs.casefold()
    missing_purposes = sorted(purpose for purpose in expected_purposes if purpose.casefold() not in docs_casefolded)
    if missing_purposes:
        raise InventoryError("screenshot purpose(s) missing from docs page: " + ", ".join(missing_purposes))

    return len(expected_names)


def referenced_dashboard_screenshots(docs: str) -> set[str]:
    names: set[str] = set()
    for raw_target in IMAGE_LINK_RE.findall(docs):
        target = normalize_target(raw_target)
        filename = Path(urlsplit(target).path).name
        if DASHBOARD_SCREENSHOT_RE.fullmatch(filename):
            names.add(filename)
    return names


def normalize_target(raw_target: str) -> str:
    target = raw_target.strip()
    if target.startswith("<"):
        end = target.find(">")
        if end >= 0:
            return target[1:end]
    return target.split(None, 1)[0]


class PNG:
    def __init__(self, width: int, height: int, bit_depth: int, color_type: int, interlace: int, idat: bytes) -> None:
        self.width = width
        self.height = height
        self.bit_depth = bit_depth
        self.color_type = color_type
        self.interlace = interlace
        self.idat = idat


def read_png(path: Path) -> PNG:
    data = path.read_bytes()
    if not data.startswith(b"\x89PNG\r\n\x1a\n"):
        raise InventoryError(f"not a PNG file: {path}")

    offset = 8
    width = height = bit_depth = color_type = interlace = None
    idat_chunks: list[bytes] = []
    while offset < len(data):
        if offset + 8 > len(data):
            raise InventoryError(f"truncated PNG chunk header: {path}")
        size = struct.unpack(">I", data[offset : offset + 4])[0]
        kind = data[offset + 4 : offset + 8]
        chunk_start = offset + 8
        chunk_end = chunk_start + size
        if chunk_end + 4 > len(data):
            raise InventoryError(f"truncated PNG chunk data: {path}")
        chunk = data[chunk_start:chunk_end]
        if kind == b"IHDR":
            width, height, bit_depth, color_type, _, _, interlace = struct.unpack(">IIBBBBB", chunk)
        elif kind == b"IDAT":
            idat_chunks.append(chunk)
        elif kind == b"IEND":
            break
        offset = chunk_end + 4

    if None in (width, height, bit_depth, color_type, interlace) or not idat_chunks:
        raise InventoryError(f"PNG is missing IHDR or IDAT data: {path}")
    return PNG(width, height, bit_depth, color_type, interlace, b"".join(idat_chunks))


def assert_nonblank_png(filename: str, png: PNG) -> None:
    colors = Counter(iter_png_pixels(png))
    if len(colors) <= 1:
        raise InventoryError(f"{filename} appears blank: it contains a single flat color")

    total = sum(colors.values())
    dominant = colors.most_common(1)[0][1]
    if dominant / total > 0.995:
        raise InventoryError(f"{filename} appears blank: one color covers more than 99.5% of pixels")


def iter_png_pixels(png: PNG):
    if png.bit_depth != 8 or png.color_type not in (2, 6) or png.interlace != 0:
        raise InventoryError(
            f"unsupported screenshot PNG encoding: bit_depth={png.bit_depth} "
            f"color_type={png.color_type} interlace={png.interlace}"
        )

    bytes_per_pixel = 3 if png.color_type == 2 else 4
    row_len = png.width * bytes_per_pixel
    raw = zlib.decompress(png.idat)
    expected_len = png.height * (row_len + 1)
    if len(raw) != expected_len:
        raise InventoryError(f"unexpected decompressed PNG length {len(raw)}, expected {expected_len}")

    previous = bytearray(row_len)
    for row_index in range(png.height):
        row_start = row_index * (row_len + 1)
        filter_type = raw[row_start]
        filtered = raw[row_start + 1 : row_start + 1 + row_len]
        row = unfilter_row(filter_type, filtered, previous, bytes_per_pixel)
        previous = row
        for offset in range(0, row_len, bytes_per_pixel):
            yield tuple(row[offset : offset + bytes_per_pixel])


def unfilter_row(filter_type: int, filtered: bytes, previous: bytearray, bytes_per_pixel: int) -> bytearray:
    row = bytearray(filtered)
    for i, value in enumerate(filtered):
        left = row[i - bytes_per_pixel] if i >= bytes_per_pixel else 0
        up = previous[i]
        upper_left = previous[i - bytes_per_pixel] if i >= bytes_per_pixel else 0
        if filter_type == 0:
            recon = value
        elif filter_type == 1:
            recon = value + left
        elif filter_type == 2:
            recon = value + up
        elif filter_type == 3:
            recon = value + ((left + up) // 2)
        elif filter_type == 4:
            recon = value + paeth(left, up, upper_left)
        else:
            raise InventoryError(f"unsupported PNG filter type: {filter_type}")
        row[i] = recon & 0xFF
    return row


def paeth(left: int, up: int, upper_left: int) -> int:
    estimate = left + up - upper_left
    left_distance = abs(estimate - left)
    up_distance = abs(estimate - up)
    upper_left_distance = abs(estimate - upper_left)
    if left_distance <= up_distance and left_distance <= upper_left_distance:
        return left
    if up_distance <= upper_left_distance:
        return up
    return upper_left


def main(argv: list[str]) -> int:
    if len(argv) not in (3, 4):
        print("usage: docs_screenshot_inventory.py <manifest> <docs-page> [asset-dir]", file=sys.stderr)
        return 2
    asset_dir = Path(argv[3]) if len(argv) == 4 else None
    try:
        count = validate_inventory(Path(argv[1]), Path(argv[2]), asset_dir)
    except (InventoryError, json.JSONDecodeError, zlib.error, struct.error) as exc:
        print(str(exc), file=sys.stderr)
        return 1
    print(f"docs screenshot inventory OK ({count} screenshots)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
