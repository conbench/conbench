from json import dumps, load, loads
from pathlib import Path
from typing import Callable

import click
from benchadapt.result import BenchmarkResult
from benchadapt.run import BenchmarkRun


def read_json_file(path: str) -> dict:
    "Read a JSON field into a Python object"
    with open(Path(path).resolve(), "r") as f:
        return load(f)


def augment_blob(json: dict, cls: Callable):
    "Use dataclass to append default fields to a parsed JSON blob"
    return cls(**json).to_publishable_dict()


def print_json(json: dict) -> None:
    "Print JSON nicely"
    click.echo(dumps(json))


def augment_and_print_blob(json: dict, cls: Callable) -> None:
    "Append default fields to a blob and print as JSON to stdout"
    augmented = augment_blob(json=json, cls=cls)
    print_json(augmented)


def augmentor(json: str, path: str, cls: Callable) -> None:
    "For a given class, load data, augment it, and print it"
    if json:
        blob = loads(json)
        augment_and_print_blob(json=blob, cls=cls)

    elif path and Path(path).resolve().is_file():
        blob = read_json_file(path=path)
        augment_and_print_blob(json=blob, cls=cls)

    elif path and Path(path).resolve().is_dir():
        for file in Path(path).resolve().glob("*.json"):
            blob = read_json_file(path=file)
            augment_and_print_blob(json=blob, cls=cls)

    else:
        click.echo("No data to augment found!")


@click.command(
    help="""
Fill in missing fields of a benchmark result

Specify either `--json` or `--path`.

JSON will be passed to `benchadapt.BenchmarkResult`, which will fill in default
values for missing keys and null values. Existing values will not be overridden.
Please make sure `run_id`, `run_reason`, `tags["name"]`, etc. are set how you
like before posting the results.

Augmented JSON will be printed one blob to a line, i.e. newline-delimited.
"""
)
@click.option(
    "--json", default=None, help="A JSON dict suitable for sending to augment"
)
@click.option(
    "--path",
    default=None,
    help="Path to a JSON file or directory of JSON files containing results to augment",
)
def result(json: str, path: str):
    augmentor(json=json, path=path, cls=BenchmarkResult)


@click.command(
    help="""
Fill in missing fields of a benchmark run

Specify either `--json` or `--path`.

JSON will be passed to `benchadapt.BenchmarkRun`, which will fill in default
values for missing keys and null values. Existing values will not be overridden.
Please make sure `reason`, etc. are set how you like before posting the results.

Augmented JSON will be printed one blob to a line, i.e. newline-delimited.
"""
)
@click.option("--json", default=None, help="A JSON dict to augment")
@click.option(
    "--path",
    default=None,
    help="Path to a JSON file or directory of JSON files containing runs to augment",
)
def run(json: str, path: str):
    augmentor(json=json, path=path, cls=BenchmarkRun)
