from json import dump, dumps
from pathlib import Path

import click
from benchadapt.run import BenchmarkRun
from benchclients.logging import fatal_and_log

from ._augment import augment_blob
from ._post import poster
from .utils import ENV_VAR_HELP, load_json

STATEFILE = "benchconnect-state.json"


RUN_TO_RESULT_MAPPING = {
    "id": "run_id",
    "name": "run_name",
    "reason": "run_reason",
    "github": "github",
    "machine_info": "machine_info",
    "cluster_info": "cluster_info",
}


def initialize_run(json: dict):
    """Augment a run, post it, and save template result data to statefile"""
    statefile_path = Path(".", STATEFILE).resolve()

    if statefile_path.exists():
        fatal_and_log(
            f"Active run exists! Call `benchconnect finish` or if stale, delete {statefile_path}.",
            FileExistsError,
        )

    augmented = augment_blob(json=json, cls=BenchmarkRun)
    poster(json=dumps(augmented), path=None, ndjson=None, endpoint="/runs/")

    # only write statefile if posting succeeds
    abstract_result = {}
    for run_key, result_key in RUN_TO_RESULT_MAPPING.items():
        if augmented.get(run_key):
            abstract_result[result_key] = augmented[run_key]

    with open(statefile_path, "w") as f:
        dump(abstract_result, f)

    click.echo(f"Run initialized. ID: {augmented['id']}")


@click.command(
    help=f"""
Start a benchmarking run

This method is the beginning of a workflow for posting a set of results to a
Conbench API. It takes (directly via a blob or from a path) JSON corresponding
to the POST /api/runs/ schema. Before posting to Conbench, the data will be
augmented with `benchadapt.BenchmarkRun`; see `benchmark augment run --help`
to debug and augment without posting.

When successful, this command will store a statefile called {STATEFILE} in the
current working directory which will be used to align metadata on subsequent
data. Accordingly, only one run can be active at a time, and changing the
working directory or deleting the statefile during a run will cause future
calls to fail.

\b
Other methods in this workflow:
  benchconnect submit result
  benchconnect finish run
"""
    + ENV_VAR_HELP
)
@click.option(
    "--json",
    default=None,
    help="A JSON dict suitable for augmenting and sending to a Conbench API",
)
@click.option(
    "--path",
    default=None,
    type=click.Path(exists=True, resolve_path=True),
    help="Path to a JSON file containing a run to augment and send to a Conbench API",
)
@click.argument("ndjson", required=False)
def start_run(json: str, path: str, ndjson: str):
    "Load JSON, augment a run, post it, and save a template result to a statefile"
    blob_list = load_json(json=json, path=path, ndjson=ndjson)

    if len(blob_list) == 1:
        initialize_run(json=blob_list[0])
    else:
        click.echo("Invalid path value!")
