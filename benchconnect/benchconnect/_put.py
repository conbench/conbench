from benchclients.conbench import ConbenchClient

from .utils import load_json


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
