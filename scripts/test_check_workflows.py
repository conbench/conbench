import unittest
from pathlib import Path


class CheckWorkflowsTest(unittest.TestCase):
    def test_workflow_guard_uses_shared_retired_python_package_contract(self) -> None:
        script = Path("scripts/check_workflows.sh").read_text(encoding="utf-8")

        self.assertIn("from scripts.retired_python_surfaces import RETIRED_PYTHON_PACKAGE_ROOTS", script)
        self.assertIn("for term in RETIRED_PYTHON_PACKAGE_ROOTS:", script)

    def test_workflow_guard_avoids_non_portable_bash_builtins(self) -> None:
        script = Path("scripts/check_workflows.sh").read_text(encoding="utf-8")

        self.assertNotIn("mapfile", script)

    def test_clean_local_removes_python_cache_artifacts(self) -> None:
        makefile = Path("Makefile").read_text(encoding="utf-8")

        self.assertIn("web/node_modules", makefile)
        self.assertIn("sdk/python/dist", makefile)
        self.assertIn("sdk/python/build", makefile)
        self.assertIn("sdk/python/*.egg-info", makefile)
        self.assertIn("__pycache__", makefile)
        self.assertIn(".pytest_cache", makefile)
        self.assertIn(".ruff_cache", makefile)
        self.assertIn("go clean -cache", makefile)

    def test_deploy_guard_excludes_hygiene_scripts_from_runtime_path_scan(self) -> None:
        script = Path("scripts/check_go_deploy_manifests.sh").read_text(encoding="utf-8")

        self.assertIn("--exclude=docs_migration_coverage.py", script)
        self.assertIn("--exclude=repo_hygiene.py", script)
        self.assertIn("--exclude=test_repo_hygiene.py", script)


if __name__ == "__main__":
    unittest.main()
