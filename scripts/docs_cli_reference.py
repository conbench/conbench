#!/usr/bin/env python3
from __future__ import annotations

import re
import sys
from pathlib import Path


class CLIReferenceError(Exception):
    pass


REQUIRED_CLI_REFERENCE_PHRASES: tuple[str, ...] = (
    "# CLI Reference",
    "The CLI uses Cobra",
    "conbench --help",
    "conbench results submit --help",
    "conbench ci report --help",
    "The command-specific `--help` output is the exact flag reference.",
    "conbench results submit <file-or-glob>... --server URL",
    'conbench results submit "bench-results/*.json" --server "$CONBENCH_SERVER_URL"',
    "conbench results get <id> --server URL",
    "conbench compare <baseline-id> <contender-id> --server URL",
    "conbench series list --server URL",
    "conbench history export <result-id> --server URL --output history.csv",
    "conbench ci report --server URL --repository REPO --commit SHA",
    "conbench ci report --server URL --repository REPO --commit SHA --run-ids RUN_IDS",
    "conbench ci report --server URL --run-ids CONTENDER_IDS --baseline-run-ids BASELINE_IDS",
    "Report exit codes are:",
    "conbench auth login --server URL",
    "conbench auth token list --server URL",
    "conbench auth token revoke <token-id> --server URL",
    "prefer `CONBENCH_TOKEN` over `--token`",
    "Credential resolution is:",
    "conbench admin repair-commits --format json",
    "conbench admin alerts evaluate --format json",
    "conbench admin alerts deliver --channel webhook --format json",
    "conbench admin alerts deliver --channel slack --format json",
    "conbench admin alerts deliver --channel github-check --format json",
    "conbench admin alerts deliver --channel github-comment --format json",
    "conbench admin alerts deliver --channel email --format json",
    "conbench admin prod-clone --help",
    "conbench admin prod-clone samples --help",
    "conbench openapi",
    "conbench openapi --downgrade",
    "conbench serve",
)


def normalize_markdown(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def validate_cli_reference(path: Path) -> int:
    if not path.is_file():
        raise CLIReferenceError(f"missing CLI reference page: {path}")
    text = normalize_markdown(path.read_text(encoding="utf-8"))
    missing = [
        phrase
        for phrase in REQUIRED_CLI_REFERENCE_PHRASES
        if normalize_markdown(phrase) not in text
    ]
    if missing:
        raise CLIReferenceError("missing CLI reference evidence: " + ", ".join(missing))
    return len(REQUIRED_CLI_REFERENCE_PHRASES)


def main(argv: list[str]) -> int:
    path = Path(argv[1]) if len(argv) == 2 else Path("docs/site/cli-reference.md")
    try:
        count = validate_cli_reference(path)
    except CLIReferenceError as exc:
        print(str(exc), file=sys.stderr)
        return 1
    print(f"docs CLI reference OK ({count} required phrases)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
