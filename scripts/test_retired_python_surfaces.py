import unittest
from pathlib import Path

from scripts import python_sdk_artifact_hygiene, repo_hygiene
from scripts.retired_python_surfaces import RETIRED_PYTHON_MODULE_FILES, RETIRED_PYTHON_PACKAGE_ROOTS


class RetiredPythonSurfacesTest(unittest.TestCase):
    def test_retired_python_package_roots_are_the_shared_contract(self) -> None:
        self.assertEqual(
            RETIRED_PYTHON_PACKAGE_ROOTS,
            (
                "benchadapt",
                "benchalerts",
                "benchclients",
                "benchconnect",
                "benchrun",
                "conbench_client",
                "conbenchlegacy",
            ),
        )

    def test_python_guard_modules_use_the_shared_package_roots(self) -> None:
        self.assertIs(repo_hygiene.RETIRED_IMPORT_ROOTS, RETIRED_PYTHON_PACKAGE_ROOTS)
        self.assertIs(python_sdk_artifact_hygiene.RETIRED_PACKAGE_DIRS, RETIRED_PYTHON_PACKAGE_ROOTS)

    def test_python_guard_modules_use_the_shared_module_files(self) -> None:
        self.assertIs(repo_hygiene.RETIRED_MODULE_FILES, RETIRED_PYTHON_MODULE_FILES)
        self.assertIs(python_sdk_artifact_hygiene.RETIRED_MODULE_FILES, RETIRED_PYTHON_MODULE_FILES)

    def test_migration_example_import_guard_uses_shared_package_roots(self) -> None:
        test_path = Path("examples/migration/test_gbench_to_cli_submit.py")
        source = test_path.read_text(encoding="utf-8")

        self.assertIn(
            "from scripts.retired_python_surfaces import RETIRED_PYTHON_PACKAGE_ROOTS",
            source,
        )
        self.assertIn("for package in RETIRED_PYTHON_PACKAGE_ROOTS:", source)


if __name__ == "__main__":
    unittest.main()
