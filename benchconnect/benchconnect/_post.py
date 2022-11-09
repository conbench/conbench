import click
from benchclients.conbench import ConbenchClient

from .utils import ENV_VAR_HELP, load_json


def post_blob(json: dict, endpoint: str, client: ConbenchClient) -> None:
    "Post a blob of JSON to Conbench"
    client.post(path=endpoint, json=json)


def poster(json: str, path: str, ndjson: str, endpoint: str) -> None:
    "Take either a blob or a path and post the resulting JSON to Conbench"
    client = ConbenchClient()

    blob_list = load_json(json=json, path=path, ndjson=ndjson)

    for blob in blob_list:
        post_blob(json=blob, endpoint=endpoint, client=client)


@click.command(
    help="""
Post benchmark result JSON[s] to a Conbench API

Specify either `--json` or `--path`.

JSON will not be altered before posting; to fill in missing fields, see
`benchconnect augment result --help`.
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
    help="Path to a JSON file or directory of JSON files containing results to send to a Conbench API",
)
@click.argument(
    "ndjson",
    required=False,
    default=None,  # help="Newline-delimited JSON of results to post"
)
def result(json: dict, path: str, ndjson: str):
    poster(json=json, path=path, ndjson=ndjson, endpoint="/benchmarks/")


@click.command(
    help="""
Post JSON[s] for a new run to a Conbench API

Specify either `--json` or `--path`.

JSON will not be altered before posting; to fill in missing fields, see
`benchconnect augment run --help`.
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
    poster(json=json, path=path, ndjson=ndjson, endpoint="/runs/")
