import json
import logging
import time
import urllib.parse

import flask as f
import requests

from ..config import Config

log = logging.getLogger(__name__)


def get_oidc_config():
    # Rely on three config parameters to be set in a meaningful way:
    # Config.OIDC_ISSUER_URL, Config.OIDC_CLIENT_ID, Config.OIDC_CLIENT_SECRET
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


def gen_oidc_authz_req_url(user_came_from_url: str) -> str:
    """
    Generate and return a URL that will be sent to the user agent in an HTTP
    redirect response. That URL represents a so-called authorization request
    against the identity provider.

    This function here is expected to be called in the context of processing an
    incoming HTTP request.

    As part of constructing the authorization request details: build an
    absolute URL to the OIDC callback endpoint served by this app. That
    absolute URL is deployment-specific. Two examples:

        http://127.0.0.1:5000/api/google/callback
        https://conbench.ursa.dev/api/google/callback

    Scheme, host, port information depend on the deployment and cannot
    generally be determined by the app itself (requires human input). Hence,
    the most maintainable (controlled, predictable) way to construct the
    callback URL would be using Config.INTENDED_BASE_URL.

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
        abs_oidc_callback_url = f.url_for(
            "api.callback", _external=True, _scheme="https"
        )

    log.debug("Initiate OIDC SSO flow. redirect_uri: %s", abs_oidc_callback_url)
    log.debug("user_came_from_url: %s", user_came_from_url)

    camefrom_encoded = ""
    try:
        camefrom_encoded = urllib.parse.quote(user_came_from_url)
    except Exception as exc:
        # Continue with the login flow w/o carrying the target URL around.
        # NOTE: maybe emit a 400 Bad Request response instead, showing err
        # detail.
        log.info("drop target URL: encoding failed with: %s", exc)

    url_to_redirect_user_to = client.prepare_request_uri(
        oidc_provider_config["authorization_endpoint"],
        redirect_uri=abs_oidc_callback_url,
        # The `openid` scope renders this OAuth2 flow to be an OpenIDConnect
        # (OIDC) flow.
        scope=["openid", "email", "profile"],
        # Additional parameter to carry across the flow. Usually security
        # purpose. TODO: combine with non-guessable state.
        state="RANDOM" + camefrom_encoded,
    )

    return url_to_redirect_user_to


def conclude_oidc_flow():
    client, oidc_provider_config = get_oidc_client()
    _, client_id, client_secret = get_oidc_config()

    # Prepare a token creation request. Note that this is executed as part of
    # the HTTP request to the callback endpoint, and the URL contains the
    # so-called authorization response sent by the identity provider, via query
    # parameters. Among this is the OAuth2 authorization code, because we're in
    # the middle of a so-called authorization code flow. That is, all the juicy
    # detail to continue the flow is in the query parameter section of
    # `f.request.url`, and that also helps understanding
    # `authorization_response=f.request.url`. Note that authorization response
    # parsing is done according to specs, and that requires that last redirect
    # (to here) to have happened via TLS.
    token_url, headers, body = client.prepare_token_request(
        oidc_provider_config["token_endpoint"],
        authorization_response=f.request.url,
        redirect_url=f.request.base_url,
        # code=f.request.args.get("code"),
    )

    log.debug("token_url: %s", token_url)

    # Extract authorization response structure from incoming URL.
    # Response is expected to have retained the `state` parameter which we're
    # using to store the URL the user actually wanted to visit before going
    # into the login flow.
    authorization_response = client.parse_request_uri_response(f.request.url)
    log.debug("authorization_response: %s", authorization_response)

    # Parse encoded target URL from state (i.e. separate the OIDC state from
    # application-logic state). TODO: actually use OIDC state, then adjust this
    # here. Expect random state of length 6.
    camefrom_encoded = authorization_response["state"][6:]

    # Inverse operation of urllib.parse.quote(), i.e. URL-decode the URL.
    try:
        user_came_from_url = urllib.parse.unquote(camefrom_encoded)
    except Exception as exc:
        # Continue with the login flow w/o using the target URL around.
        log.info("drop target URL: decoding failed with: %s", exc)
        log.debug("camefrom_encoded: %s", camefrom_encoded)

    log.info("user_came_from_url: %s", user_came_from_url)

    # Get an access token. The response is expected to also contain an
    # ID Token, though.
    token_response = requests.post(
        token_url,
        headers=headers,
        data=body,
        auth=(client_id, client_secret),
    )

    log.debug("access token response: %s, %s", token_response, token_response.text)

    client.parse_request_body_response(json.dumps(token_response.json()))

    userinfo_url, headers, body = client.add_token(
        oidc_provider_config["userinfo_endpoint"]
    )

    userinfo = requests.get(
        userinfo_url,
        headers=headers,
        data=body,
    ).json()

    return user_came_from_url, userinfo
    """
    Return empty string upon encoding error or zero-length input.

    Return encoded input otherwise.

    Never raise an exception.

    The return value can/should be used straight as the `state` string for the
    OIDC flow.
    """

    if not u:
        return ""

    try:
        return "target-" + base64.urlsafe_b64encode(u.encode("utf8")).decode("utf8")
    except Exception as exc:
        # Continue with the login flow w/o carrying the target URL around.
        # Maybe some would consider it nicer to emit a 400 Bad Request response
        # instead, showing err detail. However, at this time I think that it's
        # better UX to at least make the flow succeed.
        log.info("target URL: encoding failed with: %s (ignore)", exc)

    return ""


def decode_target_url_from_oidc_state(state: str) -> str:
    """
    `state` is supposed to the exact state string as communicated in the OIDC
    flow.

    Never raise an exception.
    """

    # Empty input or unexpected input:
    if not state.startswith("target-"):
        return ""

    # Remove prefix, turn into byte sequence.
    encoded = state[7:].encode("utf8")

    try:
        return base64.urlsafe_b64decode(encoded).decode("utf8")
    except Exception as exc:
        log.info("state: %s, decoding target URL failed with: %s (ignore)", state, exc)

    return ""
