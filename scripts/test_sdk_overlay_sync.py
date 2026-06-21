import tempfile
import unittest
from pathlib import Path

from scripts.sdk_overlay_sync import OverlaySyncError, validate_overlay_sync


class SDKOverlaySyncTest(unittest.TestCase):
    def make_sdk_tree(self) -> Path:
        tmp_handle = tempfile.TemporaryDirectory(prefix="conbench-sdk-overlay-sync-test-")
        self.addCleanup(tmp_handle.cleanup)
        root = Path(tmp_handle.name)
        (root / "sdk" / "python" / "overlays" / "conbench").mkdir(parents=True)
        (root / "sdk" / "python" / "conbench").mkdir(parents=True)
        return root

    def write_manifest(self, root: Path, *entries: str) -> None:
        (root / "sdk" / "python" / "overlays" / "manifest.txt").write_text(
            "\n".join(entries) + "\n",
            encoding="utf-8",
        )
        self.write_managed_targets(root, *entries)

    def write_managed_targets(self, root: Path, *entries: str) -> None:
        (root / "sdk" / "python" / "overlays" / "managed-targets.txt").write_text(
            "\n".join(entries) + "\n",
            encoding="utf-8",
        )

    def test_accepts_matching_overlay_files(self) -> None:
        root = self.make_sdk_tree()
        self.write_manifest(root, "conbench/migration.py")
        (root / "sdk" / "python" / "overlays" / "conbench" / "migration.py").write_text(
            "def helper():\n    return 'ok'\n",
            encoding="utf-8",
        )
        (root / "sdk" / "python" / "conbench" / "migration.py").write_text(
            "def helper():\n    return 'ok'\n",
            encoding="utf-8",
        )

        count = validate_overlay_sync(root)

        self.assertEqual(count, 1)

    def test_rejects_missing_generated_copy(self) -> None:
        root = self.make_sdk_tree()
        self.write_manifest(root, "conbench/migration.py")
        (root / "sdk" / "python" / "overlays" / "conbench" / "migration.py").write_text(
            "def helper():\n    return 'ok'\n",
            encoding="utf-8",
        )

        with self.assertRaisesRegex(
            OverlaySyncError,
            r"missing generated SDK overlay copy: conbench/migration\.py",
        ):
            validate_overlay_sync(root)

    def test_rejects_changed_generated_copy(self) -> None:
        root = self.make_sdk_tree()
        self.write_manifest(root, "conbench/migration.py")
        (root / "sdk" / "python" / "overlays" / "conbench" / "migration.py").write_text(
            "def helper():\n    return 'ok'\n",
            encoding="utf-8",
        )
        (root / "sdk" / "python" / "conbench" / "migration.py").write_text(
            "def helper():\n    return 'changed'\n",
            encoding="utf-8",
        )

        with self.assertRaisesRegex(
            OverlaySyncError,
            r"generated SDK overlay copy differs: conbench/migration\.py",
        ):
            validate_overlay_sync(root)

    def test_rejects_stale_generated_copy_after_overlay_source_is_removed(self) -> None:
        root = self.make_sdk_tree()
        self.write_manifest(root, "conbench/migration.py")
        (root / "sdk" / "python" / "conbench" / "migration.py").write_text(
            "def helper():\n    return 'stale'\n",
            encoding="utf-8",
        )

        with self.assertRaisesRegex(
            OverlaySyncError,
            r"stale generated SDK overlay copy without source: conbench/migration\.py",
        ):
            validate_overlay_sync(root)

    def test_rejects_stale_generated_copy_after_overlay_is_retired(self) -> None:
        root = self.make_sdk_tree()
        self.write_manifest(root, "conbench/__init__.py")
        self.write_managed_targets(root, "conbench/__init__.py", "conbench/migration.py")
        (root / "sdk" / "python" / "overlays" / "conbench" / "__init__.py").write_text(
            "from .migration import helper\n",
            encoding="utf-8",
        )
        (root / "sdk" / "python" / "conbench" / "__init__.py").write_text(
            "from .migration import helper\n",
            encoding="utf-8",
        )
        (root / "sdk" / "python" / "conbench" / "migration.py").write_text(
            "def helper():\n    return 'retired-but-stale'\n",
            encoding="utf-8",
        )

        with self.assertRaisesRegex(
            OverlaySyncError,
            r"stale generated SDK overlay copy without active source: conbench/migration\.py",
        ):
            validate_overlay_sync(root)

    def test_rejects_overlay_source_not_listed_in_manifest(self) -> None:
        root = self.make_sdk_tree()
        self.write_manifest(root, "conbench/migration.py")
        (root / "sdk" / "python" / "overlays" / "conbench" / "migration.py").write_text(
            "def helper():\n    return 'ok'\n",
            encoding="utf-8",
        )
        (root / "sdk" / "python" / "conbench" / "migration.py").write_text(
            "def helper():\n    return 'ok'\n",
            encoding="utf-8",
        )
        (root / "sdk" / "python" / "overlays" / "conbench" / "extra.py").write_text(
            "def extra():\n    return 'ok'\n",
            encoding="utf-8",
        )

        with self.assertRaisesRegex(
            OverlaySyncError,
            r"overlay source missing from manifest: conbench/extra\.py",
        ):
            validate_overlay_sync(root)
