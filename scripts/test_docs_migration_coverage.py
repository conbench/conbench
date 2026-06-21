import tempfile
import unittest
from contextlib import contextmanager
from os import chdir
from pathlib import Path
from typing import Iterator

from scripts.docs_migration_coverage import (
    MigrationCoverageError,
    REQUIRED_API_AND_SDK_PHRASES,
    REQUIRED_CONTRIBUTING_PHRASES,
    REQUIRED_DEPRECATION_NOTICE_PHRASES,
    REQUIRED_MIGRATION_GUIDE_PHRASES,
    REQUIRED_ROOT_README_PHRASES,
    REQUIRED_SDK_README_PHRASES,
    validate_migration_docs,
    validate_required_phrases,
)


@contextmanager
def temporary_cwd(path: Path) -> Iterator[None]:
    previous = Path.cwd()
    chdir(path)
    try:
        yield
    finally:
        chdir(previous)


class DocsMigrationCoverageTest(unittest.TestCase):
    def make_docs(
        self,
        *,
        omitted_guide: set[str] | None = None,
        omitted_notices: set[str] | None = None,
        omitted_root_readme: set[str] | None = None,
        omitted_sdk_readme: set[str] | None = None,
    ) -> Path:
        tmp_handle = tempfile.TemporaryDirectory(prefix="conbench-docs-migration-")
        self.addCleanup(tmp_handle.cleanup)
        root = Path(tmp_handle.name)
        migration = root / "migration"
        migration.mkdir()
        omitted_guide = omitted_guide or set()
        omitted_notices = omitted_notices or set()
        omitted_root_readme = omitted_root_readme or set()
        omitted_sdk_readme = omitted_sdk_readme or set()
        (migration / "python-app.md").write_text(
            "\n".join(
                phrase
                for phrase in REQUIRED_MIGRATION_GUIDE_PHRASES
                if phrase not in omitted_guide
            ),
            encoding="utf-8",
        )
        (migration / "deprecation-notices.md").write_text(
            "\n".join(
                phrase
                for phrase in REQUIRED_DEPRECATION_NOTICE_PHRASES
                if phrase not in omitted_notices
            ),
            encoding="utf-8",
        )
        (root / "sdk-readme.md").write_text(
            "\n".join(
                phrase
                for phrase in REQUIRED_SDK_README_PHRASES
                if phrase not in omitted_sdk_readme
            ),
            encoding="utf-8",
        )
        (root / "README.md").write_text(
            "\n".join(
                phrase
                for phrase in REQUIRED_ROOT_README_PHRASES
                if phrase not in omitted_root_readme
            ),
            encoding="utf-8",
        )
        (root / "api-and-sdk.md").write_text(
            "\n".join(phrase for phrase in REQUIRED_API_AND_SDK_PHRASES),
            encoding="utf-8",
        )
        (root / "contributing.md").write_text(
            "\n".join(phrase for phrase in REQUIRED_CONTRIBUTING_PHRASES),
            encoding="utf-8",
        )
        return root

    def test_accepts_migration_docs_with_required_phrases(self) -> None:
        root = self.make_docs()
        validate_migration_docs(
            root,
            root_readme=root / "README.md",
            sdk_readme=root / "sdk-readme.md",
        )

    def test_reports_missing_benchconnect_replacement(self) -> None:
        missing = "`benchconnect` and `benchclients` are deleted"

        with self.assertRaisesRegex(
            MigrationCoverageError,
            "migration/python-app\\.md missing migration coverage: " + missing,
        ):
            root = self.make_docs(omitted_guide={missing})
            validate_migration_docs(
                root,
                root_readme=root / "README.md",
                sdk_readme=root / "sdk-readme.md",
            )

    def test_migration_guide_contract_mentions_repository_root_pythonpath(self) -> None:
        self.assertIn(
            "the repository root and `sdk/python` on `PYTHONPATH`",
            REQUIRED_MIGRATION_GUIDE_PHRASES,
        )

    def test_reports_missing_conbench_client_deprecation_notice(self) -> None:
        missing = "There is no new `conbench_client` package."

        with self.assertRaisesRegex(
            MigrationCoverageError,
            "migration/deprecation-notices\\.md missing migration coverage: " + missing,
        ):
            root = self.make_docs(omitted_notices={missing})
            validate_migration_docs(
                root,
                root_readme=root / "README.md",
                sdk_readme=root / "sdk-readme.md",
            )

    def test_reports_missing_root_readme_migration_entrypoint(self) -> None:
        missing = "For existing Python/Flask Conbench deployments"
        root = self.make_docs(omitted_root_readme={missing})

        with self.assertRaisesRegex(
            MigrationCoverageError,
            "README\\.md missing migration coverage: " + missing,
        ):
            validate_migration_docs(
                root,
                root_readme=root / "README.md",
                sdk_readme=root / "sdk-readme.md",
            )

    def test_root_readme_contract_mentions_retired_single_file_modules(self) -> None:
        self.assertIn(
            "retired Python app/package paths and single-file module names stay untracked",
            REQUIRED_ROOT_README_PHRASES,
        )

    def test_reports_missing_top_level_relative_readme_phrase(self) -> None:
        missing = "For existing Python/Flask Conbench deployments"
        root = self.make_docs(omitted_root_readme={missing})

        with temporary_cwd(root), self.assertRaisesRegex(
            MigrationCoverageError,
            "README\\.md missing migration coverage: " + missing,
        ):
            validate_required_phrases(Path("README.md"), REQUIRED_ROOT_README_PHRASES)

    def test_reports_missing_sdk_readme_write_boundary(self) -> None:
        missing = "Use the Go `conbench` CLI for writes"
        root = self.make_docs(omitted_sdk_readme={missing})

        with self.assertRaisesRegex(
            MigrationCoverageError,
            "sdk-readme\\.md missing migration coverage: " + missing,
        ):
            validate_migration_docs(
                root,
                root_readme=root / "README.md",
                sdk_readme=root / "sdk-readme.md",
            )

    def test_requires_api_and_sdk_migration_page(self) -> None:
        root = self.make_docs()
        (root / "api-and-sdk.md").unlink()

        with self.assertRaisesRegex(
            MigrationCoverageError,
            "missing migration docs page: .*/api-and-sdk\\.md",
        ):
            validate_migration_docs(
                root,
                root_readme=root / "README.md",
                sdk_readme=root / "sdk-readme.md",
            )

    def test_requires_contributing_migration_coverage_contract(self) -> None:
        root = self.make_docs()
        (root / "contributing.md").unlink()

        with self.assertRaisesRegex(
            MigrationCoverageError,
            "missing migration docs page: .*/contributing\\.md",
        ):
            validate_migration_docs(
                root,
                root_readme=root / "README.md",
                sdk_readme=root / "sdk-readme.md",
            )

    def test_contributing_contract_mentions_sdk_artifact_hygiene(self) -> None:
        self.assertIn(
            "rejects retired package directories and single-file modules from built wheel and sdist artifacts",
            REQUIRED_CONTRIBUTING_PHRASES,
        )

    def test_contributing_contract_mentions_shared_retired_python_surface_list(self) -> None:
        self.assertIn(
            "`scripts/retired_python_surfaces.py` is the shared source of truth for retired Python package names, single-file module names, and path prefixes",
            REQUIRED_CONTRIBUTING_PHRASES,
        )


if __name__ == "__main__":
    unittest.main()
