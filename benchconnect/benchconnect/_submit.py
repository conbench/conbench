from json import load
from pathlib import Path

import click
from benchadapt.result import BenchmarkResult
from benchclients.conbench import ConbenchClient
from benchclients.logging import fatal_and_log

from ._augment import augment_blob
from ._post import post_blob
from ._start import STATEFILE
from .utils import ENV_VAR_HELP, load_json


def augment_and_post_result(json: dict, client: ConbenchClient) -> None:
    "Augment a result from the statefile and class, then post it"
    statefile_path = Path(STATEFILE).resolve()

    if not statefile_path.exists():
        fatal_and_log(
            f"Statefile not found at {statefile_path}! Call `benchconnect start run` first.",
            FileNotFoundError,
        )

    with open(statefile_path, "r") as f:
        abstract_result = load(f)

    for result_key in abstract_result:
        if result_key in json and abstract_result[result_key] != json[result_key]:
            fatal_and_log(
                "Result metadata does not match run metadata! "
                f"Key: {result_key} "
                f"Run: {abstract_result[result_key]} "
                f"Result: {json[result_key]}",
                click.BadParameter,
            )

        json[result_key] = abstract_result[result_key]

    augmented = augment_blob(json=json, cls=BenchmarkResult)

    post_blob(json=augmented, endpoint="/benchmarks/", client=client)


@click.command(
    help=f"""
Submit benchmark result[s] to an active run

This method is part of a workflow for posting a set of results to a Conbench
API as a run. It takes (directly via a blob or from a path) JSON corresponding
to the POST /api/benchmarks/ schema. Before posting to Conbench, the data will be
augmented both from the run metadata stored in a statefile called {STATEFILE} in
the current working directory created by a call to `benchconnect start run`, and
also with `benchadapt.BenchmarkResult`. See `benchmark augment result --help`
to debug and augment without posting.

`benchconnect start run` must be called before this method, which can be called
as many times as necessary, with a single blob or multiple. Because it requires
the statefile, changing working directories or deleting the statefile will cause
this method to fail.

When all benchmarks are submitted, run `benchconnect finish run` to close the run
and delete the statefile.

\b
Other methods in this workflow:
  benchconnect start run
  benchconnect finish run
"""
    + ENV_VAR_HELP
)
@click.option(
    "--json", default=None, help="A JSON dict suitable for sending to a Conbench API"
)
@click.option(
    "--path",
    default=None,
    type=click.Path(exists=True, resolve_path=True),
    help="Path to a JSON file or directory of JSON files containing results to augment and send to a Conbench API",
)
@click.argument("ndjson", required=False)
def submit_result(json: str, path: str, ndjson: str):
    blob_list = load_json(json=json, path=path, ndjson=ndjson)
    client = ConbenchClient()

    for blob in blob_list:
        augment_and_post_result(json=blob, client=client)
