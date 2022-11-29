import json
import logging
import time

import flask as f
import requests

from ..config import Config

log = logging.getLogger(__name__)


def get_oidc_config():
    # Rely on three config parameters to be set in a meaningful way:
    # Config.OIDC_ISSUER_URL, Config.OIDC_CLIENT_ID,Config.OIDC_CLIENT_SECRET
    discovery_url = Config.OIDC_ISSUER_URL + "/.well-known/openid-configuration"
    return discovery_url, Config.OIDC_CLIENT_ID, Config.OIDC_CLIENT_SECRET


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
    """
    Generate and return a URL that will be sent to the user agent in an HTTP
    redirect response.

    That URL represents a so-called authorization request against the identity
    provider.

    This function here is expected to be called in the context of processing an
    incoming HTTP request.

    As part of constructing the authorization request details: build an
    absolute URL to the OIDC callback endpoint served by this app. That
    absolute URL is deployment-specific. Two examples:

        http://127.0.0.1:5000/api/google/callback
        https://conbench.ursa.dev/api/google/callback

    Scheme, host, port information depend on the deployment and cannot
    generally be determined by the app itself (requires human input). Hence,
    the least error-prone method is to construct the callback URL via
    Config.INTENDED_BASE_URL.

    However, Config.INTENDED_BASE_URL is not yet required to be set by Conbench
    operators (as that would break compatibility with legacy deployments). For
    those deployments, keep using Flask's url_for(..., _external=True,
    https=true) to construct the base URL using the host from the currently
    incoming HTTP request (from the HOST header field). Keep hard-coding the
    scheme to HTTPS, otherwise those legacy environments may break, too.
    Further analysis and discussion can be found at
    https://github.com/conbench/conbench/pull/454#issuecomment-1326338524 and
    in https://github.com/conbench/conbench/issues/464

    If either redirect URL or the authorization endpoint (at the OP) do not use
    the HTTPS scheme then the oauthlib method `prepare_request_uri()` below is
    expected to throw `InsecureTransportError`. For testing, this can be
    changed by setting the environment variable OAUTHLIB_INSECURE_TRANSPORT.
    """

    client, oidc_provider_config = get_oidc_client()

    # INTENDED_BASE_URL takes precedence.
    if Config.INTENDED_BASE_URL is not None:
        abs_oidc_callback_url = Config.INTENDED_BASE_URL + "api/google/callback"
    else:
        # Fallback method for legacy deployments that do not set
        # INTENDED_BASE_URL. Code path is not executed by the test suite.
        abs_oidc_callback_url = f.url_for("api.callback", _external=True, https=True)

    return client.prepare_request_uri(
        oidc_provider_config["authorization_endpoint"],
        redirect_uri=abs_oidc_callback_url,
        scope=["openid", "email", "profile"],
    )


def get_google_user():
    client, oidc_provider_config = get_oidc_client()
    _, client_id, client_secret = get_oidc_config()

    token_url, headers, body = client.prepare_token_request(
        oidc_provider_config["token_endpoint"],
        authorization_response=f.request.url,
        redirect_url=f.request.base_url,
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
