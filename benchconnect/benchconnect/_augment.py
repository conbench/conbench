from typing import Callable

import click
from benchadapt.result import BenchmarkResult
from benchadapt.run import BenchmarkRun

from .utils import load_json, print_json


def augment_blob(json: dict, cls: Callable) -> dict:
    "Use dataclass to append default fields to a parsed JSON blob"
    return cls(**json).to_publishable_dict()


def augmentor(json: str, path: str, ndjson: str, cls: Callable) -> None:
    "For a given class, load data, augment it, and print it"
    blob_list = load_json(json=json, path=path, ndjson=ndjson)

    for blob in blob_list:
        augmented = augment_blob(json=blob, cls=cls)
        print_json(augmented)


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
@click.option("--json", default=None, help="A JSON dict of a result to augment")
@click.option(
    "--path",
    default=None,
    type=click.Path(exists=True, resolve_path=True),
    help="Path to a JSON file or directory of JSON files containing results to augment",
)
@click.argument("ndjson", required=False)
def result(json: str, path: str, ndjson: str):
    augmentor(json=json, path=path, ndjson=ndjson, cls=BenchmarkResult)


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
    type=click.Path(exists=True, resolve_path=True),
    help="Path to a JSON file or directory of JSON files containing runs to augment",
)
@click.argument("ndjson", required=False)
def run(json: str, path: str, ndjson: str):
    augmentor(json=json, path=path, ndjson=ndjson, cls=BenchmarkRun)
