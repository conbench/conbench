from json import dumps, load, loads
from pathlib import Path
from typing import Any, Dict, List

import click
from benchclients.logging import fatal_and_log, log

ENV_VAR_HELP = """

\b
Environment variables:
  CONBENCH_URL: The URL of the Conbench server. Required.
  CONBENCH_EMAIL: The email to use for Conbench login. Only required if the server is private.
  CONBENCH_PASSWORD: The password to use for Conbench login. Only required if the server is private.
"""


def load_json(json: str, path: str, ndjson: str) -> List[Dict[str, Any]]:
    "Load JSON from a string, file path, directory path, or stdin"

    stdin = click.get_text_stream("stdin")
    if not ndjson and not stdin.isatty():
        ndjson = stdin.read()

    if json:
        if path or ndjson:
            log.warning("Multiple inputs supplied! Using `--json`")

        return [loads(json)]

    elif ndjson:
        if path:
            log.warning("Multiple inputs supplied! Using `NDJSON`")

        return [loads(blob) for blob in ndjson.strip().splitlines()]

    elif path and Path(path).resolve().is_file():
        with open(Path(path).resolve(), "r") as f:
            return [load(f)]

    elif path and Path(path).resolve().is_dir():
        json_list = []
        for filepath in Path(path).resolve().glob("*.json"):
            with open(filepath, "r") as f:
                json_list.append(load(f))

        return json_list

    else:
        fatal_and_log("No JSON data found!", click.BadParameter)


def print_json(json: dict) -> None:
    "Print JSON nicely"
    click.echo(dumps(json))
