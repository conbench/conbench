from json import load, loads
from pathlib import Path

import click
from benchclients.conbench import ConbenchClient


def post_blob(json: dict, endpoint: str, client: ConbenchClient) -> None:
    "Post a blob of JSON to Conbench"
    client.post(path=endpoint, json=json)


def post_file(path: str, client: ConbenchClient, endpoint: str) -> None:
    "Load a JSON file and post it to Conbench"
    with open(Path(path).resolve(), "r") as f:
        json = load(f)

    post_blob(json=json, endpoint=endpoint, client=client)


def poster(json: str, path: str, endpoint: str) -> None:
    "Take either a blob or a path and post the resulting JSON to Conbench"
    client = ConbenchClient()

    if json:
        post_blob(json=loads(json), endpoint=endpoint, client=client)

    elif path and Path(path).resolve().is_file():
        post_file(path=path, client=client)

    elif path and Path(path).resolve().is_dir():
        for file in Path(path).resolve().glob("*.json"):
            post_file(path=file, endpoint=endpoint, client=client)

    else:
        click.echo("No data to post found!")


@click.command(
    help="""
Post benchmark result JSON[s] to a Conbench API

Specify either `--json` or `--path`.

For Conbench environment variables, see `benchconnect post --help`.

JSON will not be altered before posting; to fill in missing fields, see
`benchconnect augment result --help`.
"""
)
@click.option(
    "--json", default=None, help="A JSON dict suitable for sending to a Conbench API"
)
@click.option(
    "--path",
    default=None,
    help="Path to a JSON file or directory of JSON files containing results to send to a Conbench API",
)
def result(json: dict, path: str):
    poster(json=json, path=path, endpoint="/benchmarks/")


@click.command(
    help="""
Post JSON[s] for a new run to a Conbench API

Specify either `--json` or `--path`.

For Conbench environment variables, see `benchconnect post --help`.

JSON will not be altered before posting; to fill in missing fields, see
`benchconnect augment run --help`.
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
    poster(json=json, path=path, endpoint="/runs/")
