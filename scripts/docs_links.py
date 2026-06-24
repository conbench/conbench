#!/usr/bin/env python3
from __future__ import annotations

import re
import sys
import importlib
import json
import shlex
from html import unescape
from pathlib import Path
from urllib.parse import urlsplit


class DocsLinkError(Exception):
    pass


LINK_RE = re.compile(r"!?\[[^\]\n]*\]\(([^)\n]+)\)")
SCHEME_RE = re.compile(r"^[A-Za-z][A-Za-z0-9+.-]*:")
GENERATED_SCREENSHOT_RE = re.compile(r"^assets/screenshots/[A-Za-z0-9_.-]+\.png$")
DASHBOARD_SCREENSHOT_RE = re.compile(r"^dashboard-[A-Za-z0-9-]+\.png$")
# Non-dashboard generated screenshots live on the orphan docs-screenshots branch
# and are restored at docs-build time, so they are absent from this branch. List
# them here so a typo'd or unknown reference still fails the link check;
# restore_docs_screenshot_artifacts.sh verifies each one exists after restore.
KNOWN_GENERATED_SCREENSHOTS = frozenset({"prod-clone-series-arrow-toucharea.png"})
HEADING_RE = re.compile(r"^(#{1,6})[ \t]+(.+?)[ \t]*#*[ \t]*$")
CUSTOM_ANCHOR_RE = re.compile(r"\{#([A-Za-z0-9_.:-]+)\}[ \t]*$")
MAKE_TARGET_RE = re.compile(r"^[A-Za-z0-9_.-]+$")
INLINE_CODE_RE = re.compile(r"`([^`\n]+)`")
MAKE_COMMAND_RE = re.compile(r"(?:^|[\s;&|])make(?:[ \t]+([^;&|\n`]+))?")
MAKE_LINE_RE = re.compile(
    r"^[ \t]*(?:\$[ \t]+)?(?:[A-Z_][A-Z0-9_]*=(?:\"[^\"]*\"|'[^']*'|\S+)[ \t]+)*make"
    r"(?:[ \t]+([^;&|\n]+))?"
)
BUN_SCRIPT_RE = re.compile(r"^[A-Za-z0-9_.:-]+$")
BUN_COMMAND_RE = re.compile(r"(?:^|[\s;&|])bun[ \t]+run[ \t]+([A-Za-z0-9][A-Za-z0-9_.:-]*)\b")
BUN_LINE_RE = re.compile(
    r"^[ \t]*(?:\$[ \t]+)?(?:cd[ \t]+web[ \t]+&&[ \t]+)?bun[ \t]+run[ \t]+"
    r"([A-Za-z0-9][A-Za-z0-9_.:-]*)\b"
)


def validate_docs_links(paths: list[Path]) -> int:
    failures: list[str] = []
    checked = 0
    for markdown in iter_markdown_files(paths):
        checked += 1
        validate_markdown_file(markdown, failures)

    if failures:
        raise DocsLinkError("\n".join(failures))
    return checked


def validate_zensical_nav(config_path: Path) -> int:
    config = load_toml(config_path.read_text(encoding="utf-8"))
    project = config.get("project")
    if not isinstance(project, dict):
        raise DocsLinkError(f"{config_path}: missing [project] table")

    docs_dir_value = project.get("docs_dir")
    if not isinstance(docs_dir_value, str) or not docs_dir_value:
        raise DocsLinkError(f"{config_path}: project.docs_dir must be set")
    docs_dir = (config_path.parent / docs_dir_value).resolve()
    if not docs_dir.is_dir():
        raise DocsLinkError(f"{config_path}: project.docs_dir does not exist: {docs_dir_value}")

    nav = project.get("nav")
    nav_pages = flatten_nav_pages(nav)
    if not nav_pages:
        raise DocsLinkError(f"{config_path}: project.nav must list at least one docs page")

    docs_pages = {path.relative_to(docs_dir).as_posix() for path in docs_dir.rglob("*.md")}
    nav_page_set = set(nav_pages)
    failures: list[str] = []
    for page in sorted(docs_pages - nav_page_set):
        failures.append(f"{config_path}: docs page missing from zensical nav: {page}")
    for page in sorted(nav_page_set - docs_pages):
        failures.append(f"{config_path}: zensical nav references missing docs page: {page}")
    if failures:
        raise DocsLinkError("\n".join(failures))
    return len(nav_page_set)


def validate_documented_make_targets(paths: list[Path], makefile: Path) -> int:
    targets = makefile_targets(makefile)
    failures: list[str] = []
    checked = 0
    for markdown in iter_markdown_files(paths):
        for target in documented_make_targets(markdown):
            checked += 1
            if target not in targets:
                failures.append(f"{markdown}: unknown Makefile target: make {target}")
    if failures:
        raise DocsLinkError("\n".join(failures))
    return checked


def validate_documented_bun_scripts(paths: list[Path], package_json: Path) -> int:
    scripts = bun_scripts(package_json)
    failures: list[str] = []
    checked = 0
    for markdown in iter_markdown_files(paths):
        for script in documented_bun_scripts(markdown):
            checked += 1
            if script not in scripts:
                failures.append(f"{markdown}: unknown web package script: bun run {script}")
    if failures:
        raise DocsLinkError("\n".join(failures))
    return checked


def bun_scripts(package_json: Path) -> set[str]:
    data = json.loads(package_json.read_text(encoding="utf-8"))
    scripts = data.get("scripts", {}) if isinstance(data, dict) else {}
    if not isinstance(scripts, dict):
        return set()
    return {name for name in scripts if isinstance(name, str) and BUN_SCRIPT_RE.fullmatch(name)}


def documented_bun_scripts(markdown: Path) -> list[str]:
    text = markdown.read_text(encoding="utf-8")
    scripts: list[str] = []
    for code in INLINE_CODE_RE.findall(text):
        scripts.extend(match.group(1) for match in BUN_COMMAND_RE.finditer(code))
    for line in text.splitlines():
        match = BUN_LINE_RE.match(line)
        if match:
            scripts.append(match.group(1))
    return scripts


def makefile_targets(makefile: Path) -> set[str]:
    targets: set[str] = set()
    for line in makefile.read_text(encoding="utf-8").splitlines():
        if not line or line[0].isspace() or line.startswith("#") or ":" not in line:
            continue
        names, _separator, _rest = line.partition(":")
        if "=" in names:
            continue
        for name in names.split():
            if MAKE_TARGET_RE.fullmatch(name) and not name.startswith("."):
                targets.add(name)
    return targets


def documented_make_targets(markdown: Path) -> list[str]:
    text = markdown.read_text(encoding="utf-8")
    targets: list[str] = []
    for code in INLINE_CODE_RE.findall(text):
        for match in MAKE_COMMAND_RE.finditer(code):
            targets.extend(parse_make_goals(match.group(1) or ""))
    for line in text.splitlines():
        match = MAKE_LINE_RE.match(line)
        if match:
            targets.extend(parse_make_goals(match.group(1) or ""))
    return targets


def parse_make_goals(command_tail: str) -> list[str]:
    try:
        tokens = shlex.split(command_tail, comments=True, posix=True)
    except ValueError:
        tokens = command_tail.split()

    goals: list[str] = []
    skip_next = False
    for token in tokens:
        if skip_next:
            skip_next = False
            continue
        if not token or token == "--" or "=" in token:
            continue
        if token.startswith("-"):
            if token in {"-C", "-f", "-I", "-j", "-l", "-o", "-W"}:
                skip_next = True
            continue
        if MAKE_TARGET_RE.fullmatch(token):
            goals.append(token)
    return goals


def flatten_nav_pages(nav: object) -> list[str]:
    pages: list[str] = []
    if isinstance(nav, str):
        pages.append(nav)
    elif isinstance(nav, list):
        for item in nav:
            pages.extend(flatten_nav_pages(item))
    elif isinstance(nav, dict):
        for value in nav.values():
            pages.extend(flatten_nav_pages(value))
    return pages


def load_toml(text: str) -> object:
    try:
        parser = importlib.import_module("tomllib")
    except ModuleNotFoundError:
        parser = importlib.import_module("tomli")
    return parser.loads(text)


def iter_markdown_files(paths: list[Path]):
    for path in paths:
        if path.is_dir():
            yield from sorted(path.rglob("*.md"))
        elif path.is_file() and path.suffix == ".md":
            yield path
        else:
            raise DocsLinkError(f"not a markdown file or directory: {path}")


def validate_markdown_file(markdown: Path, failures: list[str]) -> None:
    raw_text = markdown.read_text(encoding="utf-8")
    validate_markdown_title(markdown, raw_text, failures)
    text = strip_fenced_code(raw_text)
    for match in LINK_RE.finditer(text):
        raw_target = normalize_target(match.group(1))
        if should_skip_target(raw_target):
            continue
        if is_generated_screenshot_target(raw_target):
            continue

        local_path, fragment = split_target(raw_target)
        target = (markdown.parent / local_path).resolve() if local_path else markdown.resolve()
        if not target.exists():
            failures.append(f"{markdown}: missing local link target: {raw_target}")
            continue
        if fragment and target.suffix == ".md" and fragment not in markdown_anchors(target):
            failures.append(f"{markdown}: missing local link anchor: {raw_target}")


def validate_markdown_title(markdown: Path, text: str, failures: list[str]) -> None:
    if markdown.name == "README.md":
        stripped_text = strip_fenced_code(text)
        if not any(re.match(r"^#[ \t]+\S", line) for line in stripped_text.splitlines()):
            failures.append(f"{markdown}: must contain an H1 title")
        return
    for line in text.splitlines():
        if not line.strip():
            continue
        if not re.match(r"^#[ \t]+\S", line):
            failures.append(f"{markdown}: first non-empty line must be an H1 title")
        return
    failures.append(f"{markdown}: first non-empty line must be an H1 title")


def normalize_target(raw_target: str) -> str:
    target = raw_target.strip()
    if target.startswith("<"):
        end = target.find(">")
        if end >= 0:
            return target[1:end]
    return target.split(None, 1)[0]


def should_skip_target(target: str) -> bool:
    return not target or target.startswith("//") or SCHEME_RE.match(target) is not None


def is_generated_screenshot_target(target: str) -> bool:
    parsed = urlsplit(target)
    if GENERATED_SCREENSHOT_RE.fullmatch(parsed.path) is None:
        return False
    name = Path(parsed.path).name
    return DASHBOARD_SCREENSHOT_RE.fullmatch(name) is not None or name in KNOWN_GENERATED_SCREENSHOTS


def verify_generated_screenshots(asset_dir: Path) -> int:
    """Verify each known non-dashboard generated screenshot exists in asset_dir.

    Dashboard screenshots are validated against the manifest by
    docs_screenshot_inventory.py; this guards the orphan-branch extras restored
    by restore_docs_screenshot_artifacts.sh so a missing file fails the build.
    """
    missing = sorted(
        name for name in KNOWN_GENERATED_SCREENSHOTS if not (asset_dir / name).is_file()
    )
    if missing:
        raise DocsLinkError(
            f"{asset_dir}: missing generated screenshot(s): " + ", ".join(missing)
        )
    return len(KNOWN_GENERATED_SCREENSHOTS)


def split_target(target: str) -> tuple[str, str]:
    parsed = urlsplit(target)
    return parsed.path, parsed.fragment


def markdown_anchors(markdown: Path) -> set[str]:
    text = strip_fenced_code(markdown.read_text(encoding="utf-8"))
    anchors: set[str] = set()
    seen: dict[str, int] = {}
    for line in text.splitlines():
        match = HEADING_RE.match(line)
        if not match:
            continue
        heading = match.group(2)
        custom_anchor = CUSTOM_ANCHOR_RE.search(heading)
        if custom_anchor:
            anchors.add(custom_anchor.group(1))
            continue

        slug = slugify_heading(heading)
        if not slug:
            continue
        duplicate_count = seen.get(slug, 0)
        seen[slug] = duplicate_count + 1
        anchors.add(slug if duplicate_count == 0 else f"{slug}_{duplicate_count}")
    return anchors


def slugify_heading(heading: str) -> str:
    text = unescape(heading)
    text = re.sub(r"<[^>]+>", "", text)
    text = re.sub(r"`([^`]*)`", r"\1", text)
    text = re.sub(r"!\[([^\]]*)\]\([^)]+\)", r"\1", text)
    text = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", text)
    text = text.lower()
    text = re.sub(r"[^\w\s-]", "", text)
    text = re.sub(r"[\s-]+", "-", text.strip())
    return text.strip("-")


def strip_fenced_code(text: str) -> str:
    lines = []
    in_fence = False
    fence_char = ""
    fence_len = 0
    for line in text.splitlines(keepends=True):
        stripped = line.lstrip()
        fence_match = re.match(r"(```+|~~~+)([^\r\n]*)", stripped)
        if fence_match:
            marker = fence_match.group(1)
            suffix = fence_match.group(2)
            if not in_fence:
                in_fence = True
                fence_char = marker[0]
                fence_len = len(marker)
            elif marker[0] == fence_char and len(marker) >= fence_len and suffix.strip() == "":
                in_fence = False
                fence_char = ""
                fence_len = 0
            lines.append("\n")
            continue
        lines.append("\n" if in_fence else line)
    return "".join(lines)


def main(argv: list[str]) -> int:
    if len(argv) >= 2 and argv[1] == "--verify-generated-screenshots":
        if len(argv) != 3:
            print(
                "usage: docs_links.py --verify-generated-screenshots <asset-dir>",
                file=sys.stderr,
            )
            return 2
        try:
            verified = verify_generated_screenshots(Path(argv[2]))
        except DocsLinkError as exc:
            print(str(exc), file=sys.stderr)
            return 1
        print(f"generated screenshots OK ({verified} non-dashboard)")
        return 0

    paths = [Path(arg) for arg in argv[1:]] or [Path("docs/site"), Path("README.md"), Path("sdk/python/README.md")]
    try:
        count = validate_docs_links(paths)
        nav_count = validate_zensical_nav(Path("zensical.toml"))
        make_ref_count = validate_documented_make_targets(paths, Path("Makefile"))
        bun_ref_count = validate_documented_bun_scripts(paths, Path("web/package.json"))
    except DocsLinkError as exc:
        print(str(exc), file=sys.stderr)
        return 1
    print(
        f"docs links OK ({count} markdown files, {nav_count} nav pages, "
        f"{make_ref_count} make refs, {bun_ref_count} bun refs)"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
