import json
import tempfile
import unittest
from pathlib import Path

from scripts.docs_screenshot_pins import PinError, validate_docs_screenshot_pins


class DocsScreenshotPinsTest(unittest.TestCase):
    def make_root(
        self,
        package_playwright: str = "1.60.0",
        dockerfile_playwright: str = "1.60.0",
        compose_playwright: str = "1.60.0",
        image_line: str = "FROM mcr.microsoft.com/playwright:v${PLAYWRIGHT_VERSION}-noble",
    ) -> Path:
        tmp_handle = tempfile.TemporaryDirectory(prefix="conbench-docs-screenshot-pins-")
        self.addCleanup(tmp_handle.cleanup)
        root = Path(tmp_handle.name)
        (root / "web").mkdir()
        (root / "web" / "package.json").write_text(
            json.dumps({"devDependencies": {"@playwright/test": package_playwright}}),
            encoding="utf-8",
        )
        (root / "Dockerfile.docs-screenshots").write_text(
            f"ARG PLAYWRIGHT_VERSION={dockerfile_playwright}\n{image_line}\n",
            encoding="utf-8",
        )
        (root / "docker-compose.docs-screenshots.yml").write_text(
            "services:\n"
            "  docs-screenshots-runner:\n"
            "    build:\n"
            "      args:\n"
            f"        PLAYWRIGHT_VERSION: \"{compose_playwright}\"\n",
            encoding="utf-8",
        )
        return root

    def test_accepts_matching_playwright_pins(self) -> None:
        validate_docs_screenshot_pins(self.make_root())

    def test_rejects_non_exact_package_pin(self) -> None:
        with self.assertRaisesRegex(PinError, "exact @playwright/test version"):
            validate_docs_screenshot_pins(self.make_root(package_playwright="^1.60.0"))

    def test_rejects_dockerfile_playwright_arg_mismatch(self) -> None:
        with self.assertRaisesRegex(PinError, "Dockerfile.docs-screenshots"):
            validate_docs_screenshot_pins(self.make_root(dockerfile_playwright="1.61.0"))

    def test_rejects_compose_playwright_arg_mismatch(self) -> None:
        with self.assertRaisesRegex(PinError, "docker-compose.docs-screenshots.yml"):
            validate_docs_screenshot_pins(self.make_root(compose_playwright="1.61.0"))

    def test_rejects_image_not_derived_from_playwright_arg(self) -> None:
        with self.assertRaisesRegex(PinError, "must use PLAYWRIGHT_VERSION"):
            validate_docs_screenshot_pins(
                self.make_root(image_line="FROM mcr.microsoft.com/playwright:v1.60.0-noble")
            )


if __name__ == "__main__":
    unittest.main()
