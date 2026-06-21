"""Small migration helpers for legacy benchmark jobs.

This module is intentionally narrow: it helps Python benchmark jobs write
Conbench JSON payload files and call the Go ``conbench`` CLI. It is not a
source-compatible replacement for the retired ``benchadapt`` or ``benchconnect``
packages.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
import json
import os
from pathlib import Path
import subprocess
from typing import Any


PathLike = str | os.PathLike[str]


def _is_helper_payload_file(path: Path, prefix: str) -> bool:
    if not path.is_file():
        return False
    name = path.name
    prefix_part = f"{prefix}-"
    if not name.startswith(prefix_part) or not name.endswith(".json"):
        return False
    ordinal = name[len(prefix_part) : -len(".json")]
    if not ordinal or any(char < "0" or char > "9" for char in ordinal):
        return False
    if len(ordinal) < 6:
        return False
    if len(ordinal) == 6:
        return ordinal != "000000"
    return ordinal[0] != "0"


def _validate_payload_prefix(prefix: str) -> None:
    allowed = set("abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789._-")
    if not prefix or prefix in {".", ".."} or any(char not in allowed for char in prefix):
        raise ValueError("prefix must be a filename prefix without path separators")


@dataclass(frozen=True)
class CLIResult:
    """Result from a completed ``conbench`` CLI invocation.

    ``command``, ``stdout``, and ``stderr`` are redacted before they are exposed
    to callers so API tokens do not leak into test failures or logs.
    """

    command: tuple[str, ...]
    returncode: int
    stdout: str
    stderr: str


class ConbenchCLIError(RuntimeError):
    """Raised when a helper-managed ``conbench`` CLI command exits non-zero."""

    def __init__(self, result: CLIResult) -> None:
        self.result = result
        self.command = result.command
        self.returncode = result.returncode
        self.stdout = result.stdout
        self.stderr = result.stderr
        super().__init__(
            "conbench CLI failed with exit code "
            f"{result.returncode}: {' '.join(result.command)}"
        )


def write_result_payloads(
    payloads: Sequence[Mapping[str, Any]],
    out_dir: PathLike,
    *,
    prefix: str = "result",
) -> list[Path]:
    """Write result payload objects to ``out_dir`` as one JSON file per result.

    The Go CLI accepts one object per file. This helper deliberately rejects
    array-shaped payload entries so migrations fail before producing files the
    CLI would not submit as intended. Files previously written by this helper
    with the same prefix are removed first so a submit glob does not include
    stale payloads from an earlier run.
    """

    _validate_payload_prefix(prefix)

    checked_payloads: list[Mapping[str, Any]] = []
    for index, payload in enumerate(payloads, start=1):
        if not isinstance(payload, Mapping):
            raise TypeError(f"payload {index} must be a JSON object")
        checked_payloads.append(payload)

    destination = Path(out_dir)
    destination.mkdir(parents=True, exist_ok=True)
    for stale in destination.iterdir():
        if _is_helper_payload_file(stale, prefix):
            stale.unlink()

    files: list[Path] = []
    for index, payload in enumerate(checked_payloads, start=1):
        path = destination / f"{prefix}-{index:06d}.json"
        tmp_path = path.with_name(path.name + ".tmp")
        tmp_path.write_text(
            json.dumps(payload, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        tmp_path.replace(path)
        files.append(path)
    return files


def submit_results(
    paths: Sequence[PathLike],
    *,
    server: str,
    token: str | None = None,
    conbench_bin: PathLike = "conbench",
    timeout: float | None = None,
    env: Mapping[str, str] | None = None,
) -> CLIResult:
    """Submit payload files with ``conbench results submit``.

    ``paths`` may include quoted glob strings such as ``"bench-results/*.json"``;
    Python does not expand them, so the Go CLI performs its normal internal glob
    expansion.
    """

    if isinstance(paths, (str, os.PathLike)):
        raise TypeError("paths must be a sequence of path strings, not a single path")
    if not paths:
        raise ValueError("at least one payload path or glob is required")
    if not server:
        raise ValueError("server is required")

    command = [
        str(conbench_bin),
        "results",
        "submit",
        *[str(path) for path in paths],
        "--server",
        server,
    ]
    child_env = merged_env(env, token=token)
    secrets = token_secrets(child_env)

    try:
        completed = subprocess.run(
            command,
            capture_output=True,
            check=False,
            env=child_env,
            text=True,
            timeout=timeout,
        )
    except subprocess.TimeoutExpired as exc:
        result = CLIResult(
            command=tuple(redact_args(command, secrets)),
            returncode=124,
            stdout=redact_text(timeout_output(exc.stdout), secrets),
            stderr=redact_text(timeout_output(exc.stderr), secrets),
        )
        raise ConbenchCLIError(result) from exc
    result = CLIResult(
        command=tuple(redact_args(command, secrets)),
        returncode=completed.returncode,
        stdout=redact_text(completed.stdout, secrets),
        stderr=redact_text(completed.stderr, secrets),
    )
    if completed.returncode != 0:
        raise ConbenchCLIError(result)
    return result


def merged_env(extra: Mapping[str, str] | None, *, token: str | None = None) -> dict[str, str] | None:
    if extra is None and not token and not os.environ.get("CONBENCH_TOKEN"):
        return None
    merged = os.environ.copy()
    if extra is not None:
        merged.update(extra)
    if token:
        merged["CONBENCH_TOKEN"] = token
    return merged


def token_secrets(env: Mapping[str, str] | None) -> list[str]:
    if env is None:
        return []
    token = env.get("CONBENCH_TOKEN")
    if not token:
        return []
    return [token]


def redact_args(args: Sequence[str], secrets: Sequence[str]) -> list[str]:
    return [redact_text(arg, secrets) for arg in args]


def timeout_output(value: str | bytes | None) -> str:
    if value is None:
        return ""
    if isinstance(value, bytes):
        return value.decode(errors="replace")
    return value


def redact_text(value: str, secrets: Sequence[str]) -> str:
    redacted = value
    for secret in secrets:
        if secret:
            redacted = redacted.replace(secret, "<redacted>")
    return redacted


__all__ = (
    "CLIResult",
    "ConbenchCLIError",
    "submit_results",
    "write_result_payloads",
)
