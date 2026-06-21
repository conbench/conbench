#!/usr/bin/env python3
from __future__ import annotations

import argparse
from datetime import datetime, timezone
from itertools import groupby
import json
import os
import platform
import subprocess
import sys
import uuid
from pathlib import Path
from typing import Any

from conbench.migration import ConbenchCLIError, submit_results, write_result_payloads


DEFAULT_FIXTURE = Path(__file__).with_name("gbench.json")


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    if args.ci_report and not args.submit:
        raise SystemExit("--ci-report requires --submit")
    if args.submit and (not args.server or not args.token):
        raise SystemExit("--submit requires CONBENCH_SERVER_URL/--server and CONBENCH_TOKEN/--token")

    out_dir = args.out_dir
    out_dir.mkdir(parents=True, exist_ok=True)

    payloads = build_payloads(
        fixture=args.fixture,
        repository=args.repository,
        commit=args.commit,
        run_id=args.run_id,
        run_reason=args.run_reason,
    )
    files = write_result_payloads(payloads, out_dir)
    run_ids = sorted({payload["run_id"] for payload in payloads})

    submit_command = [
        args.cli,
        "results",
        "submit",
        str(out_dir / "*.json"),
        "--server",
        args.server or "$CONBENCH_SERVER_URL",
    ]
    summary = {
        "result_count": len(payloads),
        "run_ids": run_ids,
        "files": [str(path) for path in files],
        "submit_env": {"CONBENCH_TOKEN": "<redacted>"},
        "submit_command": submit_command,
    }
    print(json.dumps(summary, indent=2, sort_keys=True))

    if not args.submit:
        return 0

    try:
        submit_result = submit_results(
            [str(out_dir / "*.json")],
            server=args.server,
            token=args.token,
            conbench_bin=args.cli,
        )
    except ConbenchCLIError as exc:
        write_cli_result(exc.stdout, exc.stderr)
        return exc.returncode
    write_cli_result(submit_result.stdout, submit_result.stderr)

    if args.ci_report:
        return run_ci_report_command(args, run_ids)
    return 0


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Transform a saved Google Benchmark JSON file into Conbench payloads and optionally submit them with the Go CLI."
    )
    parser.add_argument("--fixture", type=Path, default=DEFAULT_FIXTURE)
    parser.add_argument("--out-dir", type=Path, required=True)
    parser.add_argument("--repository", default=default_repository())
    parser.add_argument("--commit", default=os.environ.get("GITHUB_SHA", "demo-commit"))
    parser.add_argument("--run-id", default="demo-" + uuid.uuid4().hex)
    parser.add_argument("--run-reason", default="pull request")
    parser.add_argument("--server", default=os.environ.get("CONBENCH_SERVER_URL", ""))
    parser.add_argument("--token", default=os.environ.get("CONBENCH_TOKEN", ""))
    parser.add_argument("--cli", default=os.environ.get("CONBENCH_CLI", "conbench"))
    parser.add_argument("--submit", action="store_true", help="Submit generated payloads with the Go conbench CLI.")
    parser.add_argument("--ci-report", action="store_true", help="Run conbench ci report after a successful submit.")
    return parser.parse_args(argv)


def default_repository() -> str:
    server = os.environ.get("GITHUB_SERVER_URL")
    repository = os.environ.get("GITHUB_REPOSITORY")
    if server and repository:
        return f"{server.rstrip('/')}/{repository}"
    return "https://github.com/example/project"


def build_payloads(
    *,
    fixture: Path,
    repository: str,
    commit: str,
    run_id: str,
    run_reason: str,
) -> list[dict[str, Any]]:
    raw_results = json.loads(fixture.read_text(encoding="utf-8"))
    gbench_context = raw_results.get("context", {})
    payloads: list[dict[str, Any]] = []
    github = github_metadata(repository, commit)
    machine = current_machine_info()
    timestamp = conbench_timestamp(gbench_context)

    non_aggregate = [
        result for result in raw_results["benchmarks"] if result.get("run_type") != "aggregate"
    ]
    benchmark_groups = groupby(
        sorted(non_aggregate, key=lambda result: result["name"]),
        lambda result: parse_benchmark_name(result["name"])[0],
    )
    for _, group in benchmark_groups:
        batch_id = uuid.uuid4().hex
        cases = groupby(sorted(group, key=lambda result: result["name"]), lambda result: result["name"])
        for _, observations_iter in cases:
            observations = list(observations_iter)
            payloads.append(
                gbench_case_payload(
                    observations=observations,
                    batch_id=batch_id,
                    gbench_context=gbench_context,
                    github=github,
                    machine_info=machine,
                    run_id=run_id,
                    run_reason=run_reason,
                    timestamp=timestamp,
                )
            )
    return payloads


def gbench_case_payload(
    *,
    observations: list[dict[str, Any]],
    batch_id: str,
    gbench_context: dict[str, Any],
    github: dict[str, Any],
    machine_info: dict[str, Any],
    run_id: str,
    run_reason: str,
    timestamp: str,
) -> dict[str, Any]:
    first = observations[0]
    name, tags = parse_benchmark_name(first["name"])
    tags["name"] = name
    values, unit = gbench_values_and_unit(observations)
    return {
        "batch_id": batch_id,
        "context": {
            "benchmark_language": "C++",
            "migration_path": "legacy-gbench-to-cli",
        },
        "github": github,
        "info": {},
        "machine_info": machine_info,
        "optional_benchmark_info": {
            "gbench_context": gbench_context,
        },
        "run_id": run_id,
        "run_reason": run_reason,
        "run_tags": {
            "source": "legacy-gbench",
            "migration_demo": "true",
        },
        "stats": {
            "data": values,
            "unit": unit,
            "times": [float(obs["real_time"]) for obs in observations],
            "time_unit": first["time_unit"],
            "iterations": len(observations),
        },
        "tags": tags,
        "timestamp": timestamp,
    }


def conbench_timestamp(gbench_context: dict[str, Any]) -> str:
    value = gbench_context.get("date")
    if isinstance(value, str) and value:
        return value
    return datetime.now(timezone.utc).isoformat()


def gbench_values_and_unit(observations: list[dict[str, Any]]) -> tuple[list[float], str]:
    first = observations[0]
    if "bytes_per_second" in first:
        return [float(obs["bytes_per_second"]) for obs in observations], "B/s"
    if "items_per_second" in first:
        return [float(obs["items_per_second"]) for obs in observations], "i/s"
    time_key = "real_time" if "/real_time" in first["name"] else "cpu_time"
    return [float(obs[time_key]) for obs in observations], first["time_unit"]


def parse_benchmark_name(full_name: str) -> tuple[str, dict[str, str]]:
    parts = full_name.split("/", 1)
    name, params = parts[0], ""
    if len(parts) == 2:
        params = parts[1]

    parts = name.split("<", 1)
    if len(parts) == 2:
        if params:
            name, params = parts[0], f"<{parts[1]}/{params}"
        else:
            name, params = parts[0], f"<{parts[1]}"

    tags = {}
    if params:
        tags["params"] = params
    return name, tags


def current_machine_info() -> dict[str, Any]:
    return {
        "name": os.environ.get("CONBENCH_MACHINE_INFO_NAME") or platform.node() or "unknown",
        "architecture_name": platform.machine() or None,
        "kernel_name": platform.system() or None,
        "os_name": platform.system() or None,
        "os_version": platform.release() or None,
    }


def github_metadata(repository: str, commit: str) -> dict[str, Any]:
    github: dict[str, Any] = {"repository": repository, "commit": commit}
    pr_number = os.environ.get("GITHUB_PR_NUMBER")
    if pr_number:
        try:
            github["pr_number"] = int(pr_number)
        except ValueError:
            pass
    branch = os.environ.get("GITHUB_HEAD_REF") or os.environ.get("GITHUB_REF_NAME")
    if branch and "pr_number" not in github:
        github["branch"] = branch
    return github


def run_ci_report_command(args: argparse.Namespace, run_ids: list[str]) -> int:
    return run_command(
        [
            args.cli,
            "ci",
            "report",
            "--server",
            args.server,
            "--repository",
            args.repository,
            "--commit",
            args.commit,
            "--run-ids",
            ",".join(run_ids),
            "--format",
            "markdown",
        ],
        env=token_env(args.token),
    )


def write_cli_result(stdout: str, stderr: str) -> None:
    if stdout:
        print(stdout, end="")
    if stderr:
        print(stderr, end="", file=sys.stderr)


def token_env(token: str) -> dict[str, str] | None:
    if not token:
        return None
    env = os.environ.copy()
    env["CONBENCH_TOKEN"] = token
    return env


def run_command(cmd: list[str], *, env: dict[str, str] | None = None) -> int:
    completed = subprocess.run(cmd, check=False, env=env)
    return completed.returncode


if __name__ == "__main__":
    raise SystemExit(main())
