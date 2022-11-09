import click
from benchclients.conbench import ConbenchClient

from .utils import ENV_VAR_HELP, load_json


def put_blob(json: dict, endpoint: str, client: ConbenchClient) -> None:
    "Put a JSON blob to Conbench"
    # `id` must be in the URL and not in the blob
    id = json.pop("id")
    client.put(path=f"{endpoint}/{id}/", json=json)


# This is more abstract than we presently need, but it's easily extensible to
# new PUT methods we might wrap in the future
def putter(json: str, path: str, ndjson: str, endpoint: str) -> None:
    "Take either a blob or a path and put the resulting JSON to Conbench"
    client = ConbenchClient()

    blob_list = load_json(json=json, path=path, ndjson=ndjson)

    for blob in blob_list:
        put_blob(json=blob, endpoint=endpoint, client=client)


@click.command(
    help="""
Put JSON[s] to update a run to a Conbench API

Specify either `--json` or `--path`.

`id` must correspond to an existing benchmark run record; other fields
will be updated. To create a new run, see `benchconnect post run --help`.
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
    help="Path to a JSON file or directory of JSON files containing runs to send to a Conbench API",
)
@click.argument("ndjson", required=False)
def run(json: dict, path: str, ndjson: str):
    putter(json=json, path=path, ndjson=ndjson, endpoint="/runs/")
