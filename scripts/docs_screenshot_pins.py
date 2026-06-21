#!/usr/bin/env python3
from __future__ import annotations

import json
import re
import sys
from pathlib import Path


class PinError(Exception):
    pass


def validate_docs_screenshot_pins(root: Path) -> None:
    playwright_version = read_package_playwright_version(root / "web" / "package.json")
    dockerfile_version = read_dockerfile_playwright_version(root / "Dockerfile.docs-screenshots")
    compose_version = read_compose_playwright_version(root / "docker-compose.docs-screenshots.yml")

    if dockerfile_version != playwright_version:
        raise PinError(
            "Dockerfile.docs-screenshots PLAYWRIGHT_VERSION "
            f"{dockerfile_version!r} must match web/package.json @playwright/test {playwright_version!r}"
        )
    if compose_version != playwright_version:
        raise PinError(
            "docker-compose.docs-screenshots.yml PLAYWRIGHT_VERSION "
            f"{compose_version!r} must match web/package.json @playwright/test {playwright_version!r}"
        )


def read_package_playwright_version(package_json: Path) -> str:
    package = json.loads(package_json.read_text(encoding="utf-8"))
    version = package.get("devDependencies", {}).get("@playwright/test")
    if not isinstance(version, str) or not re.fullmatch(r"\d+\.\d+\.\d+", version):
        raise PinError("web/package.json must pin an exact @playwright/test version")
    return version


def read_dockerfile_playwright_version(dockerfile: Path) -> str:
    text = dockerfile.read_text(encoding="utf-8")
    match = re.search(r"^ARG\s+PLAYWRIGHT_VERSION=([^\s#]+)", text, re.MULTILINE)
    if match is None:
        raise PinError("Dockerfile.docs-screenshots must define ARG PLAYWRIGHT_VERSION")
    if "FROM mcr.microsoft.com/playwright:v${PLAYWRIGHT_VERSION}-" not in text:
        raise PinError("Dockerfile.docs-screenshots must use PLAYWRIGHT_VERSION in the Playwright base image")
    return match.group(1)


def read_compose_playwright_version(compose_file: Path) -> str:
    text = compose_file.read_text(encoding="utf-8")
    match = re.search(r"^\s+PLAYWRIGHT_VERSION:\s*[\"']?([^\"'\s#]+)", text, re.MULTILINE)
    if match is None:
        raise PinError("docker-compose.docs-screenshots.yml must pass PLAYWRIGHT_VERSION as a build arg")
    return match.group(1)


def main(argv: list[str]) -> int:
    root = Path(argv[1]) if len(argv) == 2 else Path(".")
    try:
        validate_docs_screenshot_pins(root)
    except (PinError, FileNotFoundError, json.JSONDecodeError) as exc:
        print(str(exc), file=sys.stderr)
        return 1
    print("docs screenshot pins OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
