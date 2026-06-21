import tempfile
import unittest
from types import SimpleNamespace
from unittest import mock
from pathlib import Path

from scripts.docs_links import (
    DocsLinkError,
    load_toml,
    validate_docs_links,
    validate_documented_bun_scripts,
    validate_documented_make_targets,
    validate_zensical_nav,
    verify_generated_screenshots,
)


class DocsLinksTest(unittest.TestCase):
    def make_docs(self) -> Path:
        tmp_handle = tempfile.TemporaryDirectory(prefix="conbench-docs-links-test-")
        self.addCleanup(tmp_handle.cleanup)
        root = Path(tmp_handle.name)
        docs = root / "docs"
        (docs / "migration").mkdir(parents=True)
        (docs / "assets").mkdir()
        (docs / "index.md").write_text(
            "\n".join(
                [
                    "# Heading",
                    "",
                    "[quickstart](quickstart.md)",
                    "[migration](migration/python-app.md#submit-results)",
                    "![diagram](assets/diagram.png)",
                    "[external](https://example.com/path)",
                    "[mailto](mailto:maintainers@example.com)",
                    "[same page](#heading)",
                ]
            ),
            encoding="utf-8",
        )
        (docs / "quickstart.md").write_text("# Quickstart\n", encoding="utf-8")
        (docs / "migration" / "python-app.md").write_text("# Migration\n\n## Submit Results\n", encoding="utf-8")
        (docs / "assets" / "diagram.png").write_bytes(b"png")
        return docs

    def make_zensical_config(self, root: Path, pages: list[str]) -> Path:
        nav_items = ", ".join(f'"{page}"' for page in pages)
        config = root / "zensical.toml"
        config.write_text(
            "\n".join(
                [
                    "[project]",
                    'docs_dir = "docs"',
                    "nav = [",
                    f'  {{ "Guide" = [{nav_items}] }},',
                    "]",
                    "",
                ]
            ),
            encoding="utf-8",
        )
        return config

    def test_accepts_existing_relative_links_and_ignores_external_links(self) -> None:
        docs = self.make_docs()

        validate_docs_links([docs])

    def test_accepts_generated_screenshot_links_without_checked_in_pngs(self) -> None:
        docs = self.make_docs()
        (docs / "dashboard-screenshots.md").write_text(
            "# Dashboard Screenshots\n\n"
            "![Recent runs](assets/screenshots/dashboard-home-desktop.png)\n",
            encoding="utf-8",
        )

        validate_docs_links([docs / "dashboard-screenshots.md"])

    def test_accepts_allowlisted_non_dashboard_screenshot_link(self) -> None:
        docs = self.make_docs()
        (docs / "dashboard-screenshots.md").write_text(
            "# Dashboard Screenshots\n\n"
            "![Arrow](assets/screenshots/prod-clone-series-arrow-toucharea.png)\n",
            encoding="utf-8",
        )

        validate_docs_links([docs / "dashboard-screenshots.md"])

    def test_rejects_unknown_non_dashboard_screenshot_link(self) -> None:
        docs = self.make_docs()
        (docs / "dashboard-screenshots.md").write_text(
            "# Dashboard Screenshots\n\n"
            "![Typo](assets/screenshots/prod-clone-series-arrow-typo.png)\n",
            encoding="utf-8",
        )

        with self.assertRaisesRegex(DocsLinkError, r"missing local link target"):
            validate_docs_links([docs / "dashboard-screenshots.md"])

    def test_verify_generated_screenshots_requires_files(self) -> None:
        tmp_handle = tempfile.TemporaryDirectory(prefix="conbench-docs-links-assets-")
        self.addCleanup(tmp_handle.cleanup)
        asset_dir = Path(tmp_handle.name)

        with self.assertRaisesRegex(DocsLinkError, r"missing generated screenshot"):
            verify_generated_screenshots(asset_dir)

        (asset_dir / "prod-clone-series-arrow-toucharea.png").write_bytes(b"png")
        self.assertEqual(verify_generated_screenshots(asset_dir), 1)

    def test_rejects_missing_relative_link_target(self) -> None:
        docs = self.make_docs()
        (docs / "index.md").write_text("[missing](missing.md)\n", encoding="utf-8")

        with self.assertRaisesRegex(DocsLinkError, r"index\.md: missing local link target: missing\.md"):
            validate_docs_links([docs])

    def test_rejects_missing_cross_page_anchor(self) -> None:
        docs = self.make_docs()
        (docs / "index.md").write_text("[bad anchor](quickstart.md#missing-heading)\n", encoding="utf-8")

        with self.assertRaisesRegex(
            DocsLinkError,
            r"index\.md: missing local link anchor: quickstart\.md#missing-heading",
        ):
            validate_docs_links([docs])

    def test_rejects_missing_anchor_after_query_string(self) -> None:
        docs = self.make_docs()
        (docs / "index.md").write_text("[bad anchor](quickstart.md?plain=1#missing-heading)\n", encoding="utf-8")

        with self.assertRaisesRegex(
            DocsLinkError,
            r"index\.md: missing local link anchor: quickstart\.md\?plain=1#missing-heading",
        ):
            validate_docs_links([docs])

    def test_rejects_missing_same_page_anchor(self) -> None:
        docs = self.make_docs()
        (docs / "index.md").write_text("# Heading\n\n[bad anchor](#missing-heading)\n", encoding="utf-8")

        with self.assertRaisesRegex(
            DocsLinkError,
            r"index\.md: missing local link anchor: #missing-heading",
        ):
            validate_docs_links([docs])

    def test_rejects_markdown_page_without_top_level_title(self) -> None:
        docs = self.make_docs()
        (docs / "untitled.md").write_text("## Untitled\n\nBody\n", encoding="utf-8")

        with self.assertRaisesRegex(DocsLinkError, r"untitled\.md: first non-empty line must be an H1 title"):
            validate_docs_links([docs / "untitled.md"])

    def test_rejects_docs_page_with_code_fence_before_h1(self) -> None:
        docs = self.make_docs()
        (docs / "code-first.md").write_text("```text\nnot a title\n```\n\n# Title\n", encoding="utf-8")

        with self.assertRaisesRegex(DocsLinkError, r"code-first\.md: first non-empty line must be an H1 title"):
            validate_docs_links([docs / "code-first.md"])

    def test_accepts_readme_badge_preamble_before_h1(self) -> None:
        docs = self.make_docs()
        readme = docs.parent / "README.md"
        readme.write_text("[![CI](https://example.com/badge.svg)](https://example.com)\n\n# Project\n", encoding="utf-8")

        validate_docs_links([readme])

    def test_rejects_readme_with_h1_only_inside_code_fence(self) -> None:
        docs = self.make_docs()
        readme = docs.parent / "README.md"
        readme.write_text("```md\n# Not A Real Title\n```\n", encoding="utf-8")

        with self.assertRaisesRegex(DocsLinkError, r"README\.md: must contain an H1 title"):
            validate_docs_links([readme])

    def test_rejects_readme_with_h1_inside_nested_markdown_fence_example(self) -> None:
        docs = self.make_docs()
        readme = docs.parent / "README.md"
        readme.write_text("````md\n```md\n# Not A Real Title\n```\n````\n", encoding="utf-8")

        with self.assertRaisesRegex(DocsLinkError, r"README\.md: must contain an H1 title"):
            validate_docs_links([readme])

    def test_rejects_readme_with_h1_after_inner_fence_opener_with_info_string(self) -> None:
        docs = self.make_docs()
        readme = docs.parent / "README.md"
        readme.write_text("```md\n```python\n# Not A Real Title\n```\n", encoding="utf-8")

        with self.assertRaisesRegex(DocsLinkError, r"README\.md: must contain an H1 title"):
            validate_docs_links([readme])

    def test_custom_heading_anchor_replaces_generated_slug(self) -> None:
        docs = self.make_docs()
        (docs / "quickstart.md").write_text("## Custom Title {#stable-id}\n", encoding="utf-8")
        (docs / "index.md").write_text("[bad anchor](quickstart.md#custom-title)\n", encoding="utf-8")

        with self.assertRaisesRegex(
            DocsLinkError,
            r"index\.md: missing local link anchor: quickstart\.md#custom-title",
        ):
            validate_docs_links([docs])

    def test_accepts_docs_pages_listed_in_zensical_nav(self) -> None:
        docs = self.make_docs()
        config = self.make_zensical_config(
            docs.parent,
            ["index.md", "quickstart.md", "migration/python-app.md"],
        )

        validate_zensical_nav(config)

    def test_rejects_docs_page_missing_from_zensical_nav(self) -> None:
        docs = self.make_docs()
        unlisted = docs / "unlisted.md"
        unlisted.write_text("# Unlisted\n", encoding="utf-8")
        config = self.make_zensical_config(
            docs.parent,
            ["index.md", "quickstart.md", "migration/python-app.md"],
        )

        with self.assertRaisesRegex(DocsLinkError, r"docs page missing from zensical nav: unlisted\.md"):
            validate_zensical_nav(config)

    def test_load_toml_falls_back_to_tomli(self) -> None:
        fake_tomli = SimpleNamespace(loads=lambda text: {"loaded": text})

        def import_module(name: str):
            if name == "tomllib":
                raise ModuleNotFoundError(name)
            if name == "tomli":
                return fake_tomli
            raise AssertionError(f"unexpected import: {name}")

        with mock.patch("scripts.docs_links.importlib.import_module", side_effect=import_module):
            self.assertEqual(load_toml("payload"), {"loaded": "payload"})

    def test_rejects_documented_missing_make_target(self) -> None:
        docs = self.make_docs()
        makefile = docs.parent / "Makefile"
        makefile.write_text(".PHONY: build\nbuild:\n\ttrue\n", encoding="utf-8")
        (docs / "quickstart.md").write_text("# Quickstart\n\nRun `make missing-target`.\n", encoding="utf-8")

        with self.assertRaisesRegex(DocsLinkError, r"quickstart\.md: unknown Makefile target: make missing-target"):
            validate_documented_make_targets([docs], makefile)

    def test_rejects_missing_second_make_target(self) -> None:
        docs = self.make_docs()
        makefile = docs.parent / "Makefile"
        makefile.write_text(".PHONY: build\nbuild:\n\ttrue\n", encoding="utf-8")
        (docs / "quickstart.md").write_text("# Quickstart\n\nRun `make build missing-target`.\n", encoding="utf-8")

        with self.assertRaisesRegex(DocsLinkError, r"quickstart\.md: unknown Makefile target: make missing-target"):
            validate_documented_make_targets([docs], makefile)

    def test_accepts_documented_existing_make_target(self) -> None:
        docs = self.make_docs()
        makefile = docs.parent / "Makefile"
        makefile.write_text(".PHONY: build\nbuild:\n\ttrue\n", encoding="utf-8")
        (docs / "quickstart.md").write_text("# Quickstart\n\nRun `make build`.\n", encoding="utf-8")

        validate_documented_make_targets([docs], makefile)

    def test_rejects_documented_missing_bun_script(self) -> None:
        docs = self.make_docs()
        package_json = docs.parent / "web" / "package.json"
        package_json.parent.mkdir()
        package_json.write_text('{"scripts": {"test": "vitest run"}}\n', encoding="utf-8")
        (docs / "quickstart.md").write_text("# Quickstart\n\nRun `cd web && bun run missing`.\n", encoding="utf-8")

        with self.assertRaisesRegex(DocsLinkError, r"quickstart\.md: unknown web package script: bun run missing"):
            validate_documented_bun_scripts([docs], package_json)

    def test_accepts_documented_existing_bun_script(self) -> None:
        docs = self.make_docs()
        package_json = docs.parent / "web" / "package.json"
        package_json.parent.mkdir()
        package_json.write_text('{"scripts": {"test": "vitest run"}}\n', encoding="utf-8")
        (docs / "quickstart.md").write_text("# Quickstart\n\nRun `cd web && bun run test`.\n", encoding="utf-8")

        validate_documented_bun_scripts([docs], package_json)


if __name__ == "__main__":
    unittest.main()
