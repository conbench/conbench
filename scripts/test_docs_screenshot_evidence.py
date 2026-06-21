import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from scripts.docs_screenshot_evidence import EvidenceError, validate_evidence, write_evidence
from scripts.test_docs_screenshot_inventory import write_png


class DocsScreenshotEvidenceTest(unittest.TestCase):
    def make_inputs(self) -> tuple[Path, Path, Path]:
        tmp_handle = tempfile.TemporaryDirectory(prefix="conbench-docs-screenshot-evidence-")
        self.addCleanup(tmp_handle.cleanup)
        root = Path(tmp_handle.name)
        manifest = root / "screenshots.json"
        asset_dir = root / "assets" / "screenshots"
        asset_dir.mkdir(parents=True)
        evidence = asset_dir / "dashboard-screenshots-evidence.json"

        manifest.write_text(
            json.dumps(
                {
                    "viewports": {
                        "desktop": {"width": 4, "height": 3},
                        "mobile": {"width": 2, "height": 2},
                    },
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
        write_png(
            asset_dir / "dashboard-home-desktop.png",
            4,
            3,
            [
                [(34, 34, 34, 255), (250, 250, 250, 255), (34, 34, 34, 255), (250, 250, 250, 255)],
                [(250, 250, 250, 255), (34, 34, 34, 255), (250, 250, 250, 255), (34, 34, 34, 255)],
                [(34, 34, 34, 255), (250, 250, 250, 255), (34, 34, 34, 255), (250, 250, 250, 255)],
            ],
        )
        write_png(
            asset_dir / "dashboard-home-mobile.png",
            2,
            2,
            [
                [(34, 34, 34, 255), (250, 250, 250, 255)],
                [(250, 250, 250, 255), (34, 34, 34, 255)],
            ],
        )
        return manifest, asset_dir, evidence

    def test_write_evidence_records_routes_viewports_dimensions_and_hashes(self) -> None:
        manifest, asset_dir, evidence = self.make_inputs()

        write_evidence(manifest, asset_dir, evidence)

        data = json.loads(evidence.read_text(encoding="utf-8"))
        self.assertEqual(1, data["schema_version"])
        self.assertEqual("conbench-dashboard-screenshots", data["artifact"])
        self.assertIn("pinned Playwright", " ".join(data["quality_checks"]))
        self.assertEqual({"width": 4, "height": 3}, data["viewports"]["desktop"])
        self.assertEqual({"width": 2, "height": 2}, data["viewports"]["mobile"])

        screenshots = {(item["id"], item["viewport"]): item for item in data["screenshots"]}
        self.assertEqual({("home", "desktop"), ("home", "mobile")}, set(screenshots))
        desktop = screenshots[("home", "desktop")]
        self.assertEqual("/", desktop["route"])
        self.assertEqual("dashboard-home-desktop.png", desktop["file"])
        self.assertEqual(4, desktop["width"])
        self.assertEqual(3, desktop["height"])
        self.assertRegex(desktop["sha256"], r"^[0-9a-f]{64}$")
        self.assertGreater(desktop["bytes"], 0)

        self.assertEqual(2, validate_evidence(manifest, asset_dir, evidence))

    def test_validate_evidence_rejects_stale_png_hashes(self) -> None:
        manifest, asset_dir, evidence = self.make_inputs()
        write_evidence(manifest, asset_dir, evidence)

        write_png(
            asset_dir / "dashboard-home-mobile.png",
            2,
            2,
            [
                [(10, 10, 10, 255), (240, 240, 240, 255)],
                [(240, 240, 240, 255), (10, 10, 10, 255)],
            ],
        )

        with self.assertRaisesRegex(EvidenceError, "does not match current screenshot evidence"):
            validate_evidence(manifest, asset_dir, evidence)

    def test_validate_evidence_rejects_missing_evidence_file(self) -> None:
        manifest, asset_dir, evidence = self.make_inputs()

        with self.assertRaisesRegex(EvidenceError, "missing screenshot evidence"):
            validate_evidence(manifest, asset_dir, evidence)

    def test_script_runs_directly_from_shell_checks(self) -> None:
        manifest, asset_dir, evidence = self.make_inputs()
        write_evidence(manifest, asset_dir, evidence)
        root = Path(__file__).resolve().parents[1]

        proc = subprocess.run(
            [
                sys.executable,
                "-B",
                str(root / "scripts" / "docs_screenshot_evidence.py"),
                "check",
                str(manifest),
                str(asset_dir),
                str(evidence),
            ],
            check=False,
            capture_output=True,
            text=True,
        )

        self.assertEqual("", proc.stderr)
        self.assertEqual(0, proc.returncode)


if __name__ == "__main__":
    unittest.main()
