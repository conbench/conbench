import base64
import logging
import os
import time

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

    state = encode_target_url(user_came_from_url)
    if not state:
        # In case `encode_target_url()` returned a zero-length string pass
        # state=None into `prepare_request_uri()` below, resulting in oauthlib
        # to generate random state -- although there does not seem to be a
        # security gain (there is no validation at the end of the flow) that
        # enhances compatiblity (and also resembles legacy behavior).
        state = None

    url_to_redirect_user_to = client.prepare_request_uri(
        oidc_provider_config["authorization_endpoint"],
        redirect_uri=abs_oidc_callback_url,
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
    # the HTTP request to the callback endpoint, and the URL contains the
    # so-called authorization response sent by the identity provider, via query
    # parameters. Among this is the OAuth2 authorization code, because we're in
    # the middle of a so-called authorization code flow. That is, all the juicy
    # detail to continue the flow is in the query parameter section of
    # `f.request.url` (which is the URL used by the user agent to get here).
    # Note that authorization response parsing is done by oauthlib according to
    # specs, and that requires that last redirect (to here) to have happened
    # via TLS. However, in some legacy deployments the URL scheme communicated
    # via WSGI is not actual. See
    # https://github.com/conbench/conbench/issues/480. That is, `f.request.url`
    # might start with HTTP although the actual user agent used HTTPS. That's
    # why in legacy code we always did .replace("http://", "https://").
    # However, since introduction of local tests this needs differentiated
    # handling. See below.

    # Never rely on oauthlib to perform 'security validation' on the scheme of
    # the URL that is passed in as `authorization_response` argument. That's
    # the URL where it parses the authorization code etc from (i.e. short-lived
    # credentials emitted by the identity provider). That security mechanism is
    # not needed: for serious deployments, operators are required to expose
    # Conbench exclusively via HTTPS.
    cur_request_url_abs = f.request.url.replace("http://", "https://")

    # For the dynamically reconstructed redirect URL, for now do the
    # replacement from http:// to https:// only when _not_ in a testing
    # environment. That allows tests to be built with ease, while still keeping
    # this legacy hack in place for legacy deployments. This test-specific
    # logic can disappear once INTENDED_BASE_URL becomes required.
    cur_request_url_wo_query = f.request.base_url
    if not Config.TESTING:
        cur_request_url_wo_query = cur_request_url_wo_query.replace(
            "http://", "https://"
        )

    try:
        token_url, headers, body = client.prepare_token_request(
            oidc_provider_config["token_endpoint"],
            authorization_response=cur_request_url_abs,
            # This is included in the token request to the identity provider,
            # and the identity provider actually compares that to the redirect
            # URL it has seen in the initial authorization request.
            redirect_url=cur_request_url_wo_query,
            # Note(JP): the code arg is not documented at
            # https://oauthlib.readthedocs.io/en/latest/oauth2/clients/baseclient.html
            # code=f.request.args.get("code"),
        )
    except Exception as exc:
        log.info("prepare_token_request() failed: %s", exc)
        raise exc from None

    log.debug("token_url: %s", token_url)

    # Extract authorization response structure from incoming URL.
    # Response is expected to have retained the `state` parameter which we're
    # using to store the URL the user actually wanted to visit before going
    # into the login flow.
    try:
        authorization_response = client.parse_request_uri_response(f.request.url)
    except Exception as exc:
        log.info("parse_request_uri_response() failed: %s", exc)
        raise exc from None

    log.debug("authorization_response: %s", authorization_response)

    # Parse encoded target URL from state.
    user_came_from_url = ""
    if "state" in authorization_response:
        user_came_from_url = decode_target_url_from_oidc_state(
            authorization_response["state"]
        )

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
