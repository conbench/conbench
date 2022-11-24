import json
import logging
import os
import time

import flask as f
import requests

from ..config import Config

log = logging.getLogger(__name__)

# Rely on INTENDED_BASE_URL to have a trailing slash.
OIDC_CALLBACK_URL = Config.INTENDED_BASE_URL + "api/google/callback"


def get_oidc_config():
    client_id = os.environ.get("GOOGLE_CLIENT_ID", None)
    client_secret = os.environ.get("GOOGLE_CLIENT_SECRET", None)
    discovery_url = Config.OIDC_ISSUER_URL + "/.well-known/openid-configuration"
    return discovery_url, client_id, client_secret


def get_oidc_client():
    from oauthlib.oauth2 import WebApplicationClient

    discovery_url, client_id, _ = get_oidc_config()

    # Pragmatic healing for transient errors. Better: cache OP config across
    # login requests. Also, if we want to retry here in the future: consider
    # using tenacity.
    for attempt in range(4):
        try:
            oidc_provider_config = requests.get(discovery_url).json()
            break
        except requests.exceptions.RequestException as exc:
            log.info("err getting OP config (attempt %s): %s -- retry", attempt, exc)
            time.sleep(2)

    client = WebApplicationClient(client_id)
    return client, oidc_provider_config


def auth_google_user():
    client, oidc_provider_config = get_oidc_client()

    # http://127.0.0.1:5000/api/google/callback
    # redirect_uri = f.url_for("api.callback", _external=True, _scheme="https")

    # If either redirect URL or the authorization endpoint (at the OP) do not
    # use the HTTPS scheme then the function below is expected to throw
    # `InsecureTransportError`. For testing, this can be changed by setting
    # the environment variable OAUTHLIB_INSECURE_TRANSPORT.

    return client.prepare_request_uri(
        oidc_provider_config["authorization_endpoint"],
        redirect_uri=OIDC_CALLBACK_URL,
        scope=["openid", "email", "profile"],
    )


def get_google_user():
    client, oidc_provider_config = get_oidc_client()
    _, client_id, client_secret = get_oidc_config()

    token_url, headers, body = client.prepare_token_request(
        oidc_provider_config["token_endpoint"],
        authorization_response=f.request.url,  # .replace("http://", "https://"),
        redirect_url=f.request.base_url,  # replace("http://", "https://"),
        code=f.request.args.get("code"),
    )
    token_response = requests.post(
        token_url,
        headers=headers,
        data=body,
        auth=(client_id, client_secret),
    )
    client.parse_request_body_response(json.dumps(token_response.json()))

    uri, headers, body = client.add_token(oidc_provider_config["userinfo_endpoint"])
    return requests.get(
        uri,
        headers=headers,
        data=body,
    ).json()
