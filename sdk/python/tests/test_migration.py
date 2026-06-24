import json
import stat
import subprocess
from pathlib import Path

import pytest


def test_write_result_payloads_writes_object_per_file_json(tmp_path: Path) -> None:
    from conbench.migration import write_result_payloads

    payloads = [
        {
            "run_id": "run-1",
            "github": {"repository": "https://github.com/example/project", "commit": "abc123"},
            "stats": {"data": [1.0], "unit": "ns"},
            "tags": {"name": "benchmark-a"},
        },
        {
            "run_id": "run-1",
            "github": {"repository": "https://github.com/example/project", "commit": "abc123"},
            "stats": {"data": [2.0], "unit": "ns"},
            "tags": {"name": "benchmark-b"},
        },
    ]

    files = write_result_payloads(payloads, tmp_path / "bench-results")

    assert [path.name for path in files] == ["result-000001.json", "result-000002.json"]
    for path, payload in zip(files, payloads, strict=True):
        assert json.loads(path.read_text(encoding="utf-8")) == payload
        assert path.read_text(encoding="utf-8").endswith("\n")


def test_write_result_payloads_rejects_array_payloads(tmp_path: Path) -> None:
    from conbench.migration import write_result_payloads

    with pytest.raises(TypeError, match="payload 1 must be a JSON object"):
        write_result_payloads([[{"run_id": "run-1"}]], tmp_path)


def test_write_result_payloads_rejects_path_like_prefix(tmp_path: Path) -> None:
    from conbench.migration import write_result_payloads

    out_dir = tmp_path / "bench-results"
    payload = {"run_id": "run-1", "stats": {"data": [1.0], "unit": "ns"}, "tags": {"name": "a"}}

    for prefix in ("../outside", r"nested\outside", "D:outside"):
        with pytest.raises(ValueError, match="prefix must be a filename prefix"):
            write_result_payloads([payload], out_dir, prefix=prefix)

        assert not out_dir.exists()
        assert not (tmp_path / "outside-000001.json").exists()


def test_write_result_payloads_removes_stale_helper_owned_files(tmp_path: Path) -> None:
    from conbench.migration import write_result_payloads

    out_dir = tmp_path / "bench-results"
    out_dir.mkdir()
    stale = out_dir / "result-000003.json"
    stale.write_text('{"run_id":"stale"}\n', encoding="utf-8")
    manual_prefixed = out_dir / "result-manual.json"
    manual_prefixed.write_text('{"run_id":"manual-prefixed"}\n', encoding="utf-8")
    zero_index = out_dir / "result-000000.json"
    zero_index.write_text('{"run_id":"zero"}\n', encoding="utf-8")
    overflow_width_stale = out_dir / "result-1000000.json"
    overflow_width_stale.write_text('{"run_id":"overflow"}\n', encoding="utf-8")
    unicode_digit_like = out_dir / "result-\u00b2\u00b2\u00b2\u00b2\u00b2\u00b2.json"
    unicode_digit_like.write_text('{"run_id":"unicode"}\n', encoding="utf-8")
    unrelated = out_dir / "manual.json"
    unrelated.write_text('{"run_id":"manual"}\n', encoding="utf-8")

    files = write_result_payloads(
        [
            {"run_id": "run-1", "stats": {"data": [1.0], "unit": "ns"}, "tags": {"name": "a"}},
            {"run_id": "run-1", "stats": {"data": [2.0], "unit": "ns"}, "tags": {"name": "b"}},
        ],
        out_dir,
    )

    assert [path.name for path in files] == ["result-000001.json", "result-000002.json"]
    assert not stale.exists()
    assert not overflow_width_stale.exists()
    assert manual_prefixed.exists()
    assert zero_index.exists()
    assert unicode_digit_like.exists()
    assert unrelated.exists()
    assert set(path.name for path in out_dir.glob("*.json")) == {
        "manual.json",
        "result-000000.json",
        "result-000001.json",
        "result-000002.json",
        "result-manual.json",
        unicode_digit_like.name,
    }


def test_submit_results_invokes_cli_without_leaking_token(tmp_path: Path) -> None:
    from conbench.migration import submit_results

    capture = tmp_path / "argv.json"
    capture_env = tmp_path / "env.json"
    fake_cli = fake_conbench_cli(tmp_path)
    token = "secret-token-value"

    result = submit_results(
        ["bench-results/*.json"],
        server="https://conbench.example",
        token=token,
        conbench_bin=fake_cli,
        env={
            "CONBENCH_FAKE_CLI_CAPTURE": str(capture),
            "CONBENCH_FAKE_CLI_CAPTURE_ENV": str(capture_env),
        },
    )

    assert result.returncode == 0
    assert result.command == (
        str(fake_cli),
        "results",
        "submit",
        "bench-results/*.json",
        "--server",
        "https://conbench.example",
    )
    assert token not in result.stdout
    assert token not in result.stderr

    argv = json.loads(capture.read_text(encoding="utf-8"))
    assert argv == [
        str(fake_cli),
        "results",
        "submit",
        "bench-results/*.json",
        "--server",
        "https://conbench.example",
    ]
    captured_env = json.loads(capture_env.read_text(encoding="utf-8"))
    assert captured_env["CONBENCH_TOKEN"] == token


def test_submit_results_failure_redacts_token(tmp_path: Path) -> None:
    from conbench.migration import ConbenchCLIError, submit_results

    fake_cli = fake_conbench_cli(tmp_path)
    token = "secret-token-value"

    with pytest.raises(ConbenchCLIError) as exc_info:
        submit_results(
            [tmp_path / "result.json"],
            server="https://conbench.example",
            token=token,
            conbench_bin=fake_cli,
            env={"CONBENCH_FAKE_CLI_EXIT": "2"},
        )

    err = exc_info.value
    assert err.returncode == 2
    assert token not in str(err)
    assert token not in err.stdout
    assert token not in err.stderr
    assert "<redacted>" in err.stdout
    assert "<redacted>" in err.stderr


def test_submit_results_redacts_token_from_env_mapping(tmp_path: Path) -> None:
    from conbench.migration import submit_results

    fake_cli = fake_conbench_cli(tmp_path)
    token = "secret-token-value"

    result = submit_results(
        [tmp_path / "result.json"],
        server="https://conbench.example",
        conbench_bin=fake_cli,
        env={"CONBENCH_TOKEN": token},
    )

    assert token not in result.stdout
    assert token not in result.stderr
    assert "<redacted>" in result.stdout
    assert "<redacted>" in result.stderr


def test_submit_results_redacts_ambient_env_token(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    from conbench.migration import submit_results

    fake_cli = fake_conbench_cli(tmp_path)
    token = "secret-token-value"
    monkeypatch.setenv("CONBENCH_TOKEN", token)

    result = submit_results(
        [tmp_path / "result.json"],
        server="https://conbench.example",
        conbench_bin=fake_cli,
    )

    assert token not in result.stdout
    assert token not in result.stderr
    assert "<redacted>" in result.stdout
    assert "<redacted>" in result.stderr


def test_submit_results_rejects_single_path_string() -> None:
    from conbench.migration import submit_results

    with pytest.raises(TypeError, match="paths must be a sequence"):
        submit_results("bench-results/*.json", server="https://conbench.example")


def test_submit_results_timeout_redacts_token(monkeypatch: pytest.MonkeyPatch) -> None:
    from conbench import migration
    from conbench.migration import ConbenchCLIError

    token = "secret-token-value"

    def timeout(*_args: object, **_kwargs: object) -> subprocess.CompletedProcess[str]:
        raise subprocess.TimeoutExpired(
            cmd=["conbench", "results", "submit"],
            timeout=1.0,
            output=f"stdout {token}",
            stderr=f"stderr {token}",
        )

    monkeypatch.setattr(migration.subprocess, "run", timeout)

    with pytest.raises(ConbenchCLIError) as exc_info:
        migration.submit_results(
            ["bench-results/*.json"],
            server="https://conbench.example",
            token=token,
            timeout=1.0,
        )

    err = exc_info.value
    assert err.returncode == 124
    assert token not in str(err)
    assert token not in err.stdout
    assert token not in err.stderr
    assert "<redacted>" in err.stdout
    assert "<redacted>" in err.stderr


def fake_conbench_cli(tmp_path: Path) -> Path:
    script = tmp_path / "fake-conbench"
    script.write_text(
        "\n".join(
            [
                "#!/usr/bin/env python3",
                "import json",
                "import os",
                "import sys",
                "capture = os.environ.get('CONBENCH_FAKE_CLI_CAPTURE')",
                "if capture:",
                "    open(capture, 'w', encoding='utf-8').write(json.dumps(sys.argv))",
                "capture_env = os.environ.get('CONBENCH_FAKE_CLI_CAPTURE_ENV')",
                "if capture_env:",
                "    open(capture_env, 'w', encoding='utf-8').write(json.dumps({'CONBENCH_TOKEN': os.environ.get('CONBENCH_TOKEN')}))",
                "token = os.environ.get('CONBENCH_TOKEN', '')",
                "print('stdout ' + ' '.join(sys.argv) + ' ' + token)",
                "print('stderr ' + ' '.join(sys.argv) + ' ' + token, file=sys.stderr)",
                "raise SystemExit(int(os.environ.get('CONBENCH_FAKE_CLI_EXIT', '0')))",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    script.chmod(script.stat().st_mode | stat.S_IXUSR)
    return script
