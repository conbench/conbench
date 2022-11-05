from json import load, loads
from pathlib import Path

import click
from benchclients.conbench import ConbenchClient


def put_blob(json: dict, endpoint: str, client: ConbenchClient) -> None:
    "Put a JSON blob to Conbench"
    # `id` must be in the URL and not in the blob
    id = json.pop("id")
    client.put(path=f"{endpoint}/{id}/", json=json)


def put_file(path: str, client: ConbenchClient, endpoint: str) -> None:
    "Load a JSON file and put the blob to Conbench"
    with open(Path(path).resolve(), "r") as f:
        json = load(f)

    put_blob(json=json, endpoint=endpoint, client=client)


# This is more abstract than we presently need, but it's easily extensible to
# new PUT methods we might wrap in the future
def putter(json: str, path: str, endpoint: str) -> None:
    "Take either a blob or a path and put the resulting JSON to Conbench"
    client = ConbenchClient()

    if json:
        put_blob(json=loads(json), endpoint=endpoint, client=client)

    elif path and Path(path).resolve().is_file():
        put_file(path=path, client=client)

    elif path and Path(path).resolve().is_dir():
        for file in Path(path).resolve().glob("*.json"):
            put_file(path=file, endpoint=endpoint, client=client)

    else:
        click.echo("No data to put found!")


@click.command(
    help="""
Put JSON[s] to update a run to a Conbench API

Specify either `--json` or `--path`.

For Conbench environment variables, see `benchconnect post --help`.

`id` must correspond to an existing benchmark run record; other fields
will be updated. To create a new run, see `benchconnect post run --help`.
"""
)
@click.option(
    "--json", default=None, help="A JSON dict suitable for sending to a Conbench API"
)
@click.option(
    "--path",
    default=None,
    help="Path to a JSON file or directory of JSON files containing runs to send to a Conbench API",
)
def run(json: dict, path: str):
    putter(json=json, path=path, endpoint="/runs/")
