import tempfile
import unittest
from pathlib import Path

from scripts.docs_rendered_assets import RenderedAssetsError, validate_rendered_assets


class DocsRenderedAssetsTest(unittest.TestCase):
    def make_assets(self) -> tuple[Path, Path]:
        tmp_handle = tempfile.TemporaryDirectory(prefix="conbench-docs-rendered-assets-test-")
        self.addCleanup(tmp_handle.cleanup)
        root = Path(tmp_handle.name)
        source = root / "docs" / "site" / "assets"
        rendered = root / "site" / "assets"
        (source / "screenshots").mkdir(parents=True)
        (rendered / "screenshots").mkdir(parents=True)
        return source, rendered

    def test_accepts_matching_rendered_assets(self) -> None:
        source, rendered = self.make_assets()
        (source / "screenshots" / "dashboard-home-desktop.png").write_bytes(b"source-png")
        (rendered / "screenshots" / "dashboard-home-desktop.png").write_bytes(b"source-png")

        count = validate_rendered_assets(source, rendered)

        self.assertEqual(count, 1)

    def test_accepts_missing_source_assets_directory(self) -> None:
        source, rendered = self.make_assets()
        (source / "screenshots").rmdir()
        source.rmdir()

        count = validate_rendered_assets(source, rendered)

        self.assertEqual(count, 0)

    def test_accepts_empty_source_assets_directory(self) -> None:
        source, rendered = self.make_assets()
        (source / "screenshots").rmdir()

        count = validate_rendered_assets(source, rendered)

        self.assertEqual(count, 0)

    def test_rejects_missing_rendered_asset(self) -> None:
        source, rendered = self.make_assets()
        (source / "screenshots" / "dashboard-home-desktop.png").write_bytes(b"source-png")

        with self.assertRaisesRegex(
            RenderedAssetsError,
            r"missing rendered asset\(s\): screenshots/dashboard-home-desktop\.png",
        ):
            validate_rendered_assets(source, rendered)

    def test_rejects_changed_rendered_asset(self) -> None:
        source, rendered = self.make_assets()
        (source / "screenshots" / "dashboard-home-desktop.png").write_bytes(b"source-png")
        (rendered / "screenshots" / "dashboard-home-desktop.png").write_bytes(b"changed-png")

        with self.assertRaisesRegex(
            RenderedAssetsError,
            r"rendered asset differs from source: screenshots/dashboard-home-desktop\.png",
        ):
            validate_rendered_assets(source, rendered)

    def test_rejects_untracked_rendered_asset(self) -> None:
        source, rendered = self.make_assets()
        (source / "screenshots" / "dashboard-home-desktop.png").write_bytes(b"source-png")
        (rendered / "screenshots" / "dashboard-home-desktop.png").write_bytes(b"source-png")
        (rendered / "screenshots" / "stale.png").write_bytes(b"stale")

        with self.assertRaisesRegex(RenderedAssetsError, r"unexpected rendered asset\(s\): screenshots/stale\.png"):
            validate_rendered_assets(source, rendered)
