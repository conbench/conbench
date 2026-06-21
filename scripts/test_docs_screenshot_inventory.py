import json
import struct
import tempfile
import unittest
import zlib
from pathlib import Path

from scripts.docs_screenshot_inventory import InventoryError, validate_inventory


def write_png(path: Path, width: int, height: int, rows: list[list[tuple[int, int, int, int]]]) -> None:
    def chunk(kind: bytes, data: bytes) -> bytes:
        return (
            struct.pack(">I", len(data))
            + kind
            + data
            + struct.pack(">I", zlib.crc32(kind + data) & 0xFFFFFFFF)
        )

    raw = bytearray()
    for row in rows:
        raw.append(0)
        for rgba in row:
            raw.extend(rgba)

    path.write_bytes(
        b"\x89PNG\r\n\x1a\n"
        + chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 6, 0, 0, 0))
        + chunk(b"IDAT", zlib.compress(bytes(raw)))
        + chunk(b"IEND", b"")
    )


class DocsScreenshotInventoryTest(unittest.TestCase):
    def make_inventory(self, pixels: list[list[tuple[int, int, int, int]]]) -> tuple[Path, Path, Path]:
        tmp_handle = tempfile.TemporaryDirectory(prefix="conbench-docs-screenshot-test-")
        self.addCleanup(tmp_handle.cleanup)
        tmp = Path(tmp_handle.name)
        manifest = tmp / "screenshots.json"
        docs_page = tmp / "dashboard-screenshots.md"
        asset_dir = tmp / "assets" / "screenshots"
        asset_dir.mkdir(parents=True)

        manifest.write_text(
            json.dumps(
                {
                    "viewports": {"desktop": {"width": len(pixels[0]), "height": len(pixels)}},
                    "screenshots": [
                        {
                            "id": "home",
                            "title": "Recent runs",
                            "path": "/",
                            "purpose": "Start from recent benchmark activity",
                        }
                    ],
                }
            ),
            encoding="utf-8",
        )
        docs_page.write_text(
            "Recent runs\n\n"
            "`/`\n\n"
            "Start from recent benchmark activity\n\n"
            "![Recent runs](assets/screenshots/dashboard-home-desktop.png)\n",
            encoding="utf-8",
        )
        write_png(asset_dir / "dashboard-home-desktop.png", len(pixels[0]), len(pixels), pixels)
        return manifest, docs_page, asset_dir

    def test_rejects_flat_single_color_png(self) -> None:
        manifest, docs_page, asset_dir = self.make_inventory(
            [[(255, 255, 255, 255) for _ in range(8)] for _ in range(8)]
        )

        with self.assertRaisesRegex(InventoryError, "appears blank"):
            validate_inventory(manifest, docs_page, asset_dir)

    def test_accepts_nonblank_expected_png(self) -> None:
        pixels = []
        for y in range(8):
            row = []
            for x in range(8):
                row.append((34, 34, 34, 255) if (x + y) % 2 == 0 else (250, 250, 250, 255))
            pixels.append(row)
        manifest, docs_page, asset_dir = self.make_inventory(pixels)

        validate_inventory(manifest, docs_page, asset_dir)

    def test_accepts_docs_only_inventory_without_local_pngs(self) -> None:
        pixels = []
        for y in range(8):
            row = []
            for x in range(8):
                row.append((34, 34, 34, 255) if (x + y) % 2 == 0 else (250, 250, 250, 255))
            pixels.append(row)
        manifest, docs_page, _asset_dir = self.make_inventory(pixels)

        validate_inventory(manifest, docs_page)

    def test_accepts_artifact_branch_screenshot_urls(self) -> None:
        pixels = []
        for y in range(8):
            row = []
            for x in range(8):
                row.append((34, 34, 34, 255) if (x + y) % 2 == 0 else (250, 250, 250, 255))
            pixels.append(row)
        manifest, docs_page, _asset_dir = self.make_inventory(pixels)
        docs_page.write_text(
            "Recent runs\n\n"
            "`/`\n\n"
            "Start from recent benchmark activity\n\n"
            "![Recent runs](https://raw.githubusercontent.com/conbench/conbench/docs-screenshots/latest/dashboard-home-desktop.png)\n",
            encoding="utf-8",
        )

        validate_inventory(manifest, docs_page)

    def test_reports_missing_screenshots_without_committed_assumption(self) -> None:
        pixels = []
        for y in range(8):
            row = []
            for x in range(8):
                row.append((34, 34, 34, 255) if (x + y) % 2 == 0 else (250, 250, 250, 255))
            pixels.append(row)
        manifest, docs_page, asset_dir = self.make_inventory(pixels)
        (asset_dir / "dashboard-home-desktop.png").unlink()

        with self.assertRaisesRegex(InventoryError, r"missing screenshot\(s\): dashboard-home-desktop.png") as ctx:
            validate_inventory(manifest, docs_page, asset_dir)
        self.assertNotIn("committed", str(ctx.exception))

    def test_reports_missing_manifest_titles_from_docs_page(self) -> None:
        pixels = []
        for y in range(8):
            row = []
            for x in range(8):
                row.append((34, 34, 34, 255) if (x + y) % 2 == 0 else (250, 250, 250, 255))
            pixels.append(row)
        manifest, docs_page, asset_dir = self.make_inventory(pixels)
        manifest.write_text(
            json.dumps(
                {
                    "viewports": {"desktop": {"width": len(pixels[0]), "height": len(pixels)}},
                    "screenshots": [
                        {
                            "id": "compare",
                            "title": "Compare",
                            "path": "/compare",
                            "purpose": "Inspect benchmark deltas",
                        }
                    ],
                }
            ),
            encoding="utf-8",
        )
        (asset_dir / "dashboard-home-desktop.png").rename(asset_dir / "dashboard-compare-desktop.png")
        docs_page.write_text(
            "`/compare`\n\nInspect benchmark deltas\n\n![Dashboard](assets/screenshots/dashboard-compare-desktop.png)\n",
            encoding="utf-8",
        )

        with self.assertRaisesRegex(InventoryError, "screenshot title\\(s\\) missing from docs page: Compare"):
            validate_inventory(manifest, docs_page, asset_dir)

    def test_requires_manifest_path_and_purpose(self) -> None:
        pixels = []
        for y in range(8):
            row = []
            for x in range(8):
                row.append((34, 34, 34, 255) if (x + y) % 2 == 0 else (250, 250, 250, 255))
            pixels.append(row)
        manifest, docs_page, asset_dir = self.make_inventory(pixels)
        manifest.write_text(
            json.dumps(
                {
                    "viewports": {"desktop": {"width": len(pixels[0]), "height": len(pixels)}},
                    "screenshots": [{"id": "home", "title": "Recent runs"}],
                }
            ),
            encoding="utf-8",
        )

        with self.assertRaisesRegex(InventoryError, r"screenshot 'home' must define a non-empty path"):
            validate_inventory(manifest, docs_page, asset_dir)

    def test_reports_missing_manifest_purpose_from_docs_page(self) -> None:
        pixels = []
        for y in range(8):
            row = []
            for x in range(8):
                row.append((34, 34, 34, 255) if (x + y) % 2 == 0 else (250, 250, 250, 255))
            pixels.append(row)
        manifest, docs_page, asset_dir = self.make_inventory(pixels)
        docs_page.write_text("Recent runs\n\n`/`\n\n![Recent runs](assets/screenshots/dashboard-home-desktop.png)\n", encoding="utf-8")

        with self.assertRaisesRegex(
            InventoryError,
            "screenshot purpose\\(s\\) missing from docs page: Start from recent benchmark activity",
        ):
            validate_inventory(manifest, docs_page, asset_dir)

    def test_reports_missing_home_route_when_only_image_url_contains_slash(self) -> None:
        pixels = []
        for y in range(8):
            row = []
            for x in range(8):
                row.append((34, 34, 34, 255) if (x + y) % 2 == 0 else (250, 250, 250, 255))
            pixels.append(row)
        manifest, docs_page, asset_dir = self.make_inventory(pixels)
        docs_page.write_text(
            "Recent runs\n\n"
            "Start from recent benchmark activity\n\n"
            "![Recent runs](assets/screenshots/dashboard-home-desktop.png)\n",
            encoding="utf-8",
        )

        with self.assertRaisesRegex(InventoryError, r"screenshot path\(s\) missing from docs page: /"):
            validate_inventory(manifest, docs_page, asset_dir)

    def test_real_manifest_covers_core_dashboard_surfaces(self) -> None:
        root = Path(__file__).resolve().parents[1]
        manifest = json.loads((root / "web" / "docs-screenshots" / "screenshots.json").read_text(encoding="utf-8"))
        actual = {item["id"] for item in manifest["screenshots"]}

        required = {"account", "batch", "ci-report", "compare", "home", "result", "results", "run", "series", "trend"}

        self.assertEqual([], sorted(required - actual))


if __name__ == "__main__":
    unittest.main()
