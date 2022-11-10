import datetime
from json import dumps, load
from pathlib import Path

import click
from benchclients.logging import fatal_and_log

from ._put import putter
from ._start import STATEFILE
from .utils import ENV_VAR_HELP, load_json


def finalize_run(json: dict) -> None:
    """Augment run metadata from statefile, put it, and delete statefile"""
    statefile_path = Path(STATEFILE).resolve()
    with open(statefile_path, "r") as f:
        abstract_result = load(f)

    if "id" in json and json["id"] != abstract_result["id"]:
        fatal_and_log(
            f"Run ID {json['id']} does not match statefile {statefile_path} value {abstract_result['id']}"
        )

    json["id"] = abstract_result["run_id"]

    if "finished_timestamp" not in json:
        json["finished_timestamp"] = datetime.datetime.now(
            datetime.timezone.utc
        ).isoformat()

    putter(json=dumps(json), path=None, ndjson=None, endpoint="/runs/")

    statefile_path.unlink()


@click.command(
    help=f"""
Finalize and close a run

This method is part of a workflow for posting a set of results to a Conbench
API as a run. It takes (directly via a blob or from a path) JSON corresponding
to the PUT /api/runs/ schema. Before putting to Conbench, the run ID will be
inserted as required from the run metadata stored in a statefile called
{STATEFILE} in the current working directory created by a call to
`benchconnect start run`. If not supplied, `finished_timestamp` will be
inserted at the current time. Because only `run_id` is required, this method
can be called without supplying any data if there is no need to adjust fields
like `error_type` and `error_info`.

`benchconnect start run` must be called before this method. Because this method
requires the statefile, changing working directories or deleting the statefile
will cause this method to fail.

\b
Other methods in this workflow:
  benchconnect start run
  benchconnect submit result
"""
    + ENV_VAR_HELP
)
@click.option(
    "--json",
    default=None,
    help="A JSON dict with values to adjust when finalizing the run",
)
@click.option(
    "--path",
    default=None,
    type=click.Path(exists=True, resolve_path=True),
    help="Path to a JSON file containing values to adjust when finalizing the run",
)
@click.argument("ndjson", required=False)
def finish_run(json: str, path: str, ndjson: str) -> None:
    "Load JSON, augment run metadata from statefile, put it, and delete statefile"
    blob_list = load_json(json=json, path=path, ndjson=ndjson)

    if len(blob_list) == 0:
        finalize_run(json={})
    elif len(blob_list) == 1:
        finalize_run(json=blob_list[0])
    else:
        click.echo("Invalid path value!")
