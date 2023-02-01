import base64
import logging
import time
from typing import Optional

import flask as f
import requests
from oauthlib.oauth2 import WebApplicationClient

from ..config import Config

log = logging.getLogger(__name__)


OIDC_CALLBACK_URL = Config.INTENDED_BASE_URL + "api/google/callback"


def get_oidc_config():
    # Rely on three config parameters to be set in a meaningful way:
    # Config.OIDC_ISSUER_URL, Config.OIDC_CLIENT_ID, Config.OIDC_CLIENT_SECRET
    discovery_url = Config.OIDC_ISSUER_URL + "/.well-known/openid-configuration"
    return discovery_url, Config.OIDC_CLIENT_ID, Config.OIDC_CLIENT_SECRET


def get_oidc_client():
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
    callback URL is by using Config.INTENDED_BASE_URL set by the operator. Note
    that we cannot rely on the WSGI information on the URL scheme that the user
    used to reach the application. Further analysis and discussion can be found
    at https://github.com/conbench/conbench/pull/454#issuecomment-1326338524
    and in https://github.com/conbench/conbench/issues/464

    If either redirect URL or the authorization endpoint (at the OP) do not use
    the HTTPS scheme then the oauthlib method `prepare_request_uri()` below is
    expected to throw `InsecureTransportError`. For testing, this can be
    changed by setting the environment variable OAUTHLIB_INSECURE_TRANSPORT.
    """

    client, oidc_provider_config = get_oidc_client()

    log.debug("Initiate OIDC SSO flow. redirect_uri: %s", OIDC_CALLBACK_URL)
    log.debug("user_came_from_url: %s", user_came_from_url)

    state: Optional[str] = encode_target_url(user_came_from_url)
    if not state:
        # In case `encode_target_url()` returned a zero-length string pass
        # state=None into `prepare_request_uri()` below, resulting in oauthlib
        # to generate random state -- although there does not seem to be a
        # security gain (there is no validation at the end of the flow) that
        # enhances compatiblity (and also resembles legacy behavior).
        state = None

    url_to_redirect_user_to = client.prepare_request_uri(
        oidc_provider_config["authorization_endpoint"],
        redirect_uri=OIDC_CALLBACK_URL,
        # The `openid` scope is an essential ingredient to make this OAuth2
        # flow be an OpenID Connect (OIDC) flow.
        scope=["openid", "email", "profile"],
        # Additional parameter to carry across the flow. Usually this parameter
        # has a security purpose. For the time being we do not use it for that,
        # but we use it for communicating the target URL across the flow.
        # Discussion can be found in
        # https://github.com/conbench/conbench/pull/462.
        state=state,
    )

    return url_to_redirect_user_to


def conclude_oidc_flow():
    """
    Note(JP): I'd prefer to have this part of the flow implemented with the
    help of a more appropriate library than oauthlib. oauthlib is a generic
    OAuth2 library and mainly intended to build identity providers. It's
    difficult to use its primitives in a correct, secure way, and the outcome
    is hard to read and maintain.

    Relevant docs:
    https://oauthlib.readthedocs.io/en/latest/oauth2/clients/baseclient.html
    https://oauthlib.readthedocs.io/en/latest/oauth2/clients/webapplicationclient.html

    After all, I think in the current implementation we're doing more HTTP
    requests than necessary (we should be OK with just getting an ID token,
    maybe do not need to do the /userinfo request).

    In the current iteration it's about adding some code comments, and about
    covering what we have in tests. It will then be easier to potentially
    transition to a different library.
    """

    client, oidc_provider_config = get_oidc_client()
    _, client_id, client_secret = get_oidc_config()

    # Prepare a token creation request. Note that this is executed as part of
    # processing an HTTP request to the callback endpoint. The URL used for
    # reaching that callback endpoint contains the so-called authorization
    # response sent by the identity provider, via query parameters. Among this
    # is the short-lived OAuth2 authorization code, because we're in the middle
    # of a so-called authorization code flow. That is, all the juicy detail to
    # continue the flow is in the query parameter section of `f.request.url`.

    # Note that authorization response parsing is done by oauthlib according to
    # specs, and that requires that last redirect (to here) to have happened
    # via TLS. However, in some legacy deployments the URL scheme communicated
    # via WSGI is not actual. See
    # https://github.com/conbench/conbench/issues/480. That is, `f.request.url`
    # might start with HTTP although the actual user agent used HTTPS.
    #
    # As a result, do not rely on oauthlib to perform this kind of security
    # validation on the scheme of `f.request.url`. Pragmatically disable this
    # validation by always rewriting the scheme from http to https. A note on
    # security: for serious deployments, operators are required to expose
    # Conbench exclusively via HTTPS and we do not need oauthlib to try to
    # confirm that (it cannot reliably know).
    cur_request_url_abs = f.request.url.replace("http://", "https://")

    # Parse target URL from state parameter in authorization response. If it's
    # not an empty string then treat this as the URL the user actually wanted
    # to visit before going into the login flow.
    user_came_from_url = parse_state_from_authorization_response(
        client, cur_request_url_abs
    )
    log.info("user_came_from_url: %s", user_came_from_url)

    try:
        token_url, headers, body = client.prepare_token_request(
            oidc_provider_config["token_endpoint"],
            authorization_response=cur_request_url_abs,
            # This is included in the token request to the identity provider,
            # and the identity provider actually compares that to the redirect
            # URL it has seen in the initial authorization request.
            redirect_url=OIDC_CALLBACK_URL,
        )
    except Exception as exc:
        log.info("prepare_token_request() failed: %s", exc)
        raise exc from None

    log.debug("token_url (for fetching access token): %s", token_url)

    # Get an access token. The response is expected to also contain an
    # ID Token, though.
    token_response = requests.post(
        token_url,
        headers=headers,
        data=body,
        auth=(client_id, client_secret),
    )

    log.debug("access token response: %s, %s", token_response, token_response.text)

    try:
        # Expect token_response.text to be a JSON document
        client.parse_request_body_response(token_response.text)
    except Exception as exc:
        log.info("parse_request_body_response err: %s", exc)
        raise exc from None

    userinfo_url, headers, body = client.add_token(
        oidc_provider_config["userinfo_endpoint"]
    )

    userinfo = requests.get(
        userinfo_url,
        headers=headers,
        data=body,
    ).json()

    # For the consumer of this 2-tuple: expect `user_came_from_url` to always
    # be a string. It has length 0 in case no target URL was communicated or if
    # there was a decoding issue along the way.
    return user_came_from_url, userinfo


def parse_state_from_authorization_response(c: WebApplicationClient, url: str) -> str:
    """
    Parse target URL from state parameter in authorization response.

    Raise exception or return the target URL as a string (may be of length 0).

    url: absolute URL that the user agent used to get here (modulo scheme, it's
    always expected to be HTTPS, see considerations above).

    Extract authorization response structure from incoming URL. Response is
    expected to have retained the `state` parameter. Extract that, and then
    decode
    """
    try:
        # This performs standards-compliant parsing of the so-called
        # authorization response and can therefore raise various oauthlib
        # exceptions. `url` is expected to always start with https:// which is
        # why this is not expected raise an exception related to insecure
        # transport.
        authorization_resp = c.parse_request_uri_response(url)
    except Exception as exc:
        log.info("parse_request_uri_response() failed: %s", exc)
        raise exc from None

    log.debug("authorization response: %s", authorization_resp)

    # Parse encoded target URL from state.
    user_came_from_url = ""
    if "state" in authorization_resp:
        user_came_from_url = decode_target_url_from_oidc_state(
            authorization_resp["state"]
        )

    return user_came_from_url


def encode_target_url(u: str) -> str:
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
