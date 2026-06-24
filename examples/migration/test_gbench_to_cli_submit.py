from __future__ import annotations

import json
import contextlib
import io
import os
import subprocess
import sys
import tempfile
import types
import unittest
from unittest import mock
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "sdk" / "python"))

import gbench_to_cli_submit as demo

from scripts.retired_python_surfaces import RETIRED_PYTHON_PACKAGE_ROOTS


SCRIPT = Path(__file__).with_name("gbench_to_cli_submit.py")


class GbenchToCLISubmitTest(unittest.TestCase):
    def test_gbench_demo_does_not_import_retired_legacy_packages(self) -> None:
        text = SCRIPT.read_text(encoding="utf-8")
        for package in RETIRED_PYTHON_PACKAGE_ROOTS:
            with self.subTest(package=package):
                self.assertNotIn(package, text)

    def test_gbench_demo_dry_run_writes_cli_payloads(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            out_dir = Path(tmp)
            env = os.environ.copy()
            env["CONBENCH_TOKEN"] = "secret-token-value"
            env["PYTHONPATH"] = str(ROOT / "sdk" / "python")

            proc = subprocess.run(
                [
                    sys.executable,
                    str(SCRIPT),
                    "--out-dir",
                    str(out_dir),
                    "--repository",
                    "https://github.com/example/project",
                    "--commit",
                    "abc123",
                    "--run-id",
                    "demo-run",
                ],
                capture_output=True,
                check=False,
                env=env,
                text=True,
            )

            self.assertEqual(proc.returncode, 0, proc.stderr)
            self.assertNotIn("secret-token-value", proc.stdout)
            self.assertNotIn("secret-token-value", proc.stderr)

            summary = json.loads(proc.stdout)
            self.assertEqual(summary["result_count"], 2)
            self.assertEqual(summary["run_ids"], ["demo-run"])
            self.assertNotIn("--token", summary["submit_command"])
            self.assertEqual(summary["submit_env"], {"CONBENCH_TOKEN": "<redacted>"})
            self.assertNotIn("secret-token-value", json.dumps(summary))

            files = [Path(path) for path in summary["files"]]
            self.assertEqual(len(files), 2)
            for path in files:
                payload = json.loads(path.read_text(encoding="utf-8"))
                self.assertIsInstance(payload, dict)
                self.assertEqual(payload["run_id"], "demo-run")
                self.assertEqual(payload["run_reason"], "pull request")
                self.assertEqual(payload["github"]["repository"], "https://github.com/example/project")
                self.assertEqual(payload["github"]["commit"], "abc123")
                self.assertEqual(payload["run_tags"]["source"], "legacy-gbench")
                self.assertEqual(payload["context"]["benchmark_language"], "C++")
                self.assertEqual(payload["context"]["migration_path"], "legacy-gbench-to-cli")
                self.assertEqual(payload["timestamp"], "2026-06-16T12:00:00Z")
                self.assertEqual(payload["stats"]["iterations"], 2)

    def test_gbench_demo_uses_supported_migration_helper_for_submit(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            out_dir = Path(tmp)
            submitted = []

            def fake_submit_results(paths, *, server, token, conbench_bin):
                submitted.append(
                    {
                        "paths": list(paths),
                        "server": server,
                        "token": token,
                        "conbench_bin": conbench_bin,
                    }
                )
                return types.SimpleNamespace(stdout="", stderr="")

            with (
                mock.patch.object(demo, "submit_results", side_effect=fake_submit_results),
                mock.patch.object(demo, "run_ci_report_command") as ci_report,
                contextlib.redirect_stdout(io.StringIO()),
            ):
                rc = demo.main(
                    [
                        "--out-dir",
                        str(out_dir),
                        "--repository",
                        "https://github.com/example/project",
                        "--commit",
                        "abc123",
                        "--run-id",
                        "demo-run",
                        "--server",
                        "https://conbench.example",
                        "--token",
                        "secret-token-value",
                        "--cli",
                        "custom-conbench",
                        "--submit",
                    ]
                )

            self.assertEqual(rc, 0)
            self.assertEqual(
                submitted,
                [
                    {
                        "paths": [str(out_dir / "*.json")],
                        "server": "https://conbench.example",
                        "token": "secret-token-value",
                        "conbench_bin": "custom-conbench",
                    }
                ],
            )
            ci_report.assert_not_called()

    def test_gbench_demo_uses_env_token_for_ci_report_command(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            out_dir = Path(tmp)
            ci_report_commands = []

            def fake_submit_results(_paths, *, server, token, conbench_bin):
                return types.SimpleNamespace(stdout="", stderr="")

            def fake_run_command(cmd, *, env=None):
                ci_report_commands.append({"cmd": list(cmd), "env": env})
                return 0

            with (
                mock.patch.object(demo, "submit_results", side_effect=fake_submit_results),
                mock.patch.object(demo, "run_command", side_effect=fake_run_command),
                contextlib.redirect_stdout(io.StringIO()),
            ):
                rc = demo.main(
                    [
                        "--out-dir",
                        str(out_dir),
                        "--repository",
                        "https://github.com/example/project",
                        "--commit",
                        "abc123",
                        "--run-id",
                        "demo-run",
                        "--server",
                        "https://conbench.example",
                        "--token",
                        "secret-token-value",
                        "--cli",
                        "custom-conbench",
                        "--submit",
                        "--ci-report",
                    ]
                )

            self.assertEqual(rc, 0)
            self.assertEqual(len(ci_report_commands), 1)
            command = ci_report_commands[0]["cmd"]
            self.assertNotIn("--token", command)
            self.assertEqual(ci_report_commands[0]["env"]["CONBENCH_TOKEN"], "secret-token-value")
            self.assertEqual(
                command,
                [
                    "custom-conbench",
                    "ci",
                    "report",
                    "--server",
                    "https://conbench.example",
                    "--repository",
                    "https://github.com/example/project",
                    "--commit",
                    "abc123",
                    "--run-ids",
                    "demo-run",
                    "--format",
                    "markdown",
                ],
            )

    def test_github_metadata_omits_invalid_pr_number_and_uses_branch(self) -> None:
        with mock.patch.dict(
            os.environ,
            {
                "GITHUB_PR_NUMBER": "not-a-number",
                "GITHUB_HEAD_REF": "feature/branch",
                "GITHUB_REF_NAME": "main",
            },
        ):
            github = demo.github_metadata("https://github.com/example/project", "abc123")

        self.assertEqual(github["repository"], "https://github.com/example/project")
        self.assertEqual(github["commit"], "abc123")
        self.assertNotIn("pr_number", github)
        self.assertEqual(github["branch"], "feature/branch")

    def test_conbench_timestamp_falls_back_for_missing_gbench_date(self) -> None:
        timestamp = demo.conbench_timestamp({})

        self.assertRegex(timestamp, r"^\d{4}-\d{2}-\d{2}T")


if __name__ == "__main__":
    unittest.main()
