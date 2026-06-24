import contextlib
import io
import tempfile
import unittest
from pathlib import Path

from scripts.repo_hygiene import RepoHygieneError, validate_repo_hygiene


class RepoHygieneTest(unittest.TestCase):
    def test_accepts_scoped_python_files_and_active_artifacts(self) -> None:
        validate_repo_hygiene(
            Path("."),
            tracked_files=[
                "cmd/conbench/main.go",
                "api/openapi.yaml",
                "scripts/docs_links.py",
                "sdk/python/conbench/client.py",
                "sdk/python/pyproject.toml",
                "examples/migration/gbench_to_cli_submit.py",
                "migrations/env.py",
                "migrations/versions/afc565181834_initial_schema.py",
                "requirements-docs.txt",
                "requirements-schema.txt",
            ],
        )

    def test_rejects_retired_top_level_legacy_package(self) -> None:
        with self.assertRaisesRegex(RepoHygieneError, r"retired legacy path is tracked: benchadapt/result.py"):
            validate_repo_hygiene(Path("."), tracked_files=["benchadapt/result.py"])

    def test_rejects_retired_conbench_client_package(self) -> None:
        with self.assertRaisesRegex(
            RepoHygieneError,
            r"retired legacy path is tracked: conbench_client/README.md",
        ):
            validate_repo_hygiene(Path("."), tracked_files=["conbench_client/README.md"])

    def test_rejects_retired_single_file_module_in_allowed_python_root(self) -> None:
        with self.assertRaisesRegex(
            RepoHygieneError,
            r"retired legacy path is tracked: scripts/conbench_client.py",
        ):
            validate_repo_hygiene(Path("."), tracked_files=["scripts/conbench_client.py"])

    def test_rejects_retired_conbenchlegacy_package(self) -> None:
        with self.assertRaisesRegex(
            RepoHygieneError,
            r"retired legacy path is tracked: conbenchlegacy/README.md",
        ):
            validate_repo_hygiene(Path("."), tracked_files=["conbenchlegacy/README.md"])

    def test_rejects_retired_top_level_legacy_tree(self) -> None:
        with self.assertRaisesRegex(RepoHygieneError, r"retired legacy path is tracked: legacy/notes.md"):
            validate_repo_hygiene(Path("."), tracked_files=["legacy/notes.md"])

    def test_rejects_retired_python_app_config(self) -> None:
        with self.assertRaisesRegex(RepoHygieneError, r"retired legacy path is tracked: pyproject.toml"):
            validate_repo_hygiene(Path("."), tracked_files=["pyproject.toml"])

    def test_rejects_retired_root_marketing_image(self) -> None:
        with self.assertRaisesRegex(RepoHygieneError, r"retired legacy path is tracked: conbench.png"):
            validate_repo_hygiene(Path("."), tracked_files=["conbench.png"])

    def test_rejects_retired_deploy_renderer_template(self) -> None:
        with self.assertRaisesRegex(RepoHygieneError, r"retired legacy path is tracked: conbench-config.yml"):
            validate_repo_hygiene(Path("."), tracked_files=["conbench-config.yml"])

    def test_rejects_retired_legacy_actions_workflow(self) -> None:
        with self.assertRaisesRegex(
            RepoHygieneError,
            r"retired legacy path is tracked: \.github/workflows/actions.yml",
        ):
            validate_repo_hygiene(Path("."), tracked_files=[".github/workflows/actions.yml"])

    def test_rejects_retired_sphinx_source_file(self) -> None:
        with self.assertRaisesRegex(RepoHygieneError, r"retired legacy path is tracked: docs/index.rst"):
            validate_repo_hygiene(Path("."), tracked_files=["docs/index.rst"])

    def test_rejects_documentation_outside_public_site_tree(self) -> None:
        with self.assertRaisesRegex(
            RepoHygieneError,
            r"documentation outside docs/site is tracked: docs/implementation-plan.md",
        ):
            validate_repo_hygiene(Path("."), tracked_files=["docs/implementation-plan.md"])

    def test_rejects_retired_conda_lock_file(self) -> None:
        with self.assertRaisesRegex(RepoHygieneError, r"retired legacy path is tracked: conda-lock.yml"):
            validate_repo_hygiene(Path("."), tracked_files=["conda-lock.yml"])

    def test_rejects_retired_dot_directory(self) -> None:
        with self.assertRaisesRegex(RepoHygieneError, r"retired legacy path is tracked: \.buildkite/pipeline.yml"):
            validate_repo_hygiene(Path("."), tracked_files=[".buildkite/pipeline.yml"])

    def test_rejects_retired_superpowers_scratch_directory(self) -> None:
        with self.assertRaisesRegex(RepoHygieneError, r"retired legacy path is tracked: \.superpowers/mockup.html"):
            validate_repo_hygiene(Path("."), tracked_files=[".superpowers/mockup.html"])

    def test_rejects_retired_kube_prometheus_tree(self) -> None:
        with self.assertRaisesRegex(
            RepoHygieneError,
            r"retired legacy path is tracked: k8s/kube-prometheus/grafana.jsonnet",
        ):
            validate_repo_hygiene(Path("."), tracked_files=["k8s/kube-prometheus/grafana.jsonnet"])

    def test_rejects_retired_buildinfo_package(self) -> None:
        with self.assertRaisesRegex(RepoHygieneError, r"retired legacy path is tracked: internal/buildinfo/info.go"):
            validate_repo_hygiene(Path("."), tracked_files=["internal/buildinfo/info.go"])

    def test_rejects_retired_split_command_directories(self) -> None:
        for path in ("cmd/conbench-server/main.go", "cmd/conbench-openapi/main.go"):
            with self.subTest(path=path), self.assertRaisesRegex(
                RepoHygieneError,
                rf"retired legacy path is tracked: {path}",
            ):
                validate_repo_hygiene(Path("."), tracked_files=[path])

    def test_rejects_retired_legacy_python_burndown_script(self) -> None:
        with self.assertRaisesRegex(
            RepoHygieneError,
            r"retired legacy path is tracked: scripts/check_legacy_python_burndown.sh",
        ):
            validate_repo_hygiene(Path("."), tracked_files=["scripts/check_legacy_python_burndown.sh"])

    def test_rejects_unscoped_python_file(self) -> None:
        with self.assertRaisesRegex(RepoHygieneError, r"Python file outside allowed roots: tools/helper.py"):
            validate_repo_hygiene(Path("."), tracked_files=["tools/helper.py"])

    def test_rejects_retired_import_in_allowed_python_root(self) -> None:
        with tempfile.TemporaryDirectory(prefix="conbench-repo-hygiene-") as tmp:
            root = Path(tmp)
            script = root / "scripts" / "helper.py"
            script.parent.mkdir()
            script.write_text("import benchconnect\n", encoding="utf-8")

            with self.assertRaisesRegex(
                RepoHygieneError,
                r"scripts/helper\.py:1: retired legacy import: benchconnect",
            ):
                validate_repo_hygiene(root, tracked_files=["scripts/helper.py"])

    def test_rejects_retired_from_import_in_allowed_python_root(self) -> None:
        with tempfile.TemporaryDirectory(prefix="conbench-repo-hygiene-") as tmp:
            root = Path(tmp)
            script = root / "sdk" / "python" / "helper.py"
            script.parent.mkdir(parents=True)
            script.write_text("from conbench_client.api import Client\n", encoding="utf-8")

            with self.assertRaisesRegex(
                RepoHygieneError,
                r"sdk/python/helper\.py:1: retired legacy import: conbench_client",
            ):
                validate_repo_hygiene(root, tracked_files=["sdk/python/helper.py"])

    def test_cli_uses_git_tracked_files(self) -> None:
        from scripts.repo_hygiene import main

        with tempfile.TemporaryDirectory(prefix="conbench-repo-hygiene-") as tmp:
            root = Path(tmp)
            (root / "scripts").mkdir()
            (root / "scripts" / "ok.py").write_text("print('ok')\n", encoding="utf-8")
            (root / "benchadapt").mkdir()
            (root / "benchadapt" / "local-only.py").write_text("print('ignored')\n", encoding="utf-8")

            with contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(main([str(root), "--tracked-file", "scripts/ok.py"]), 0)


if __name__ == "__main__":
    unittest.main()
