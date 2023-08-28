from pathlib import Path

import click

from ._start import STATEFILE
from .utils import ENV_VAR_HELP


@click.command(
    help=f"""
Finalize and close a run

This method is part of a workflow for posting a set of results to a Conbench
API as a run. It removes a statefile called {STATEFILE} in the current working
directory created by a call to `benchconnect start run`, closing a run.

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
    help="Deprecated; ignored.",
)
@click.option(
    "--path",
    default=None,
    type=click.Path(exists=True, resolve_path=True),
    help="Deprecated; ignored.",
)
@click.argument("ndjson", required=False)
def finish_run(json: str, path: str, ndjson: str) -> None:
    "Close a run by deleting statefile"
    statefile_path = Path(STATEFILE).resolve()
    statefile_path.unlink()
