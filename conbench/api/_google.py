import json
import os

import flask as f
import requests


def get_google_config():
    client_id = os.environ.get("GOOGLE_CLIENT_ID", None)
    client_secret = os.environ.get("GOOGLE_CLIENT_SECRET", None)
    discovery_url = "https://accounts.google.com/.well-known/openid-configuration"
    return discovery_url, client_id, client_secret


def get_google_client():
    from oauthlib.oauth2 import WebApplicationClient

    discovery_url, client_id, _ = get_google_config()
    google = requests.get(discovery_url).json()
    client = WebApplicationClient(client_id)
    return client, google


def auth_google_user():
    client, google = get_google_client()
    redirect_uri = f.url_for("api.callback", _external=True, _scheme="https")
    return client.prepare_request_uri(
        google["authorization_endpoint"],
        redirect_uri=redirect_uri,
        scope=["openid", "email", "profile"],
    )


def get_google_user():
    client, google = get_google_client()
    _, client_id, client_secret = get_google_config()

    token_url, headers, body = client.prepare_token_request(
        google["token_endpoint"],
        authorization_response=f.request.url.replace("http://", "https://"),
        redirect_url=f.request.base_url.replace("http://", "https://"),
        code=f.request.args.get("code"),
    )
    token_response = requests.post(
        token_url,
        headers=headers,
        data=body,
        auth=(client_id, client_secret),
    )
    client.parse_request_body_response(json.dumps(token_response.json()))

    uri, headers, body = client.add_token(google["userinfo_endpoint"])
    return requests.get(
        uri,
        headers=headers,
        data=body,
    ).json()
