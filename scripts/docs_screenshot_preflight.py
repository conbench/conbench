#!/usr/bin/env python3
from __future__ import annotations

import json
import sys
import urllib.error
import urllib.request
from collections.abc import Mapping
from pathlib import Path


class PreflightError(Exception):
    pass


def validate_capabilities(capabilities: Mapping[str, object]) -> None:
    auth_disabled = capabilities.get("auth_disabled")
    can_write_results = capabilities.get("can_write_results")
    if auth_disabled is not False:
        raise PreflightError(
            "docs screenshots expected auth_disabled=false from /api/auth/capabilities; "
            "set CONBENCH_AUTH_DISABLED=false so captures use public read-only product mode"
        )
    if can_write_results is not False:
        raise PreflightError(
            "docs screenshots expected can_write_results=false from /api/auth/capabilities; "
            "target must be in public read-only product mode"
        )


def fetch_capabilities(base_url: str) -> dict[str, object]:
    url = base_url.rstrip("/") + "/api/auth/capabilities"
    try:
        with urllib.request.urlopen(url, timeout=10) as response:
            payload = response.read()
    except urllib.error.URLError as exc:
        raise PreflightError(f"fetch auth capabilities from {url}: {exc}") from exc

    try:
        decoded = json.loads(payload.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise PreflightError(f"decode auth capabilities from {url}: {exc}") from exc
    if not isinstance(decoded, dict):
        raise PreflightError(f"auth capabilities from {url} was not a JSON object")
    return decoded


def main(argv: list[str]) -> int:
    if len(argv) != 2:
        print(f"usage: {Path(argv[0]).name} BASE_URL", file=sys.stderr)
        return 2
    try:
        validate_capabilities(fetch_capabilities(argv[1]))
    except PreflightError as exc:
        print(str(exc), file=sys.stderr)
        return 1
    print("docs screenshot preflight OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
