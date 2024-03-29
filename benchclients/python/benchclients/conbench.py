import logging
import os
from typing import List, Optional

import requests

from .http import (
    RetryingHTTPClient,
    RetryingHTTPClientBadCredentials,
    RetryingHTTPClientLoginError,
)

log = logging.getLogger(__name__)


class ConbenchClientException(Exception):
    """
    Base exception type used by ConbenchClient.
    """


class ConbenchClient(RetryingHTTPClient):
    """
    HTTP client abstraction for interacting with a Conbench HTTP API server.

    Environment variables
    ---------------------
    CONBENCH_URL
        Required. Base URL of the Conbench API server. Must not end with /api.
    CONBENCH_EMAIL
        The email address to use for Conbench login. Required for submitting
        data.
    CONBENCH_PASSWORD
        The password to use for Conbench login. Required for submitting data.

    Credentials can be left undefined when only reading state from a 'public
    mode' API server.
    """

    # We want each request to be retried for up to ~30 minutes, also
    # see https://github.com/conbench/conbench/issues/800
    default_retry_for_seconds = 30 * 60

    # Note(JP): we bumped the recv timeout from 10 to 75 seconds to err on side
    # of caution (remove stress from DB, at the cost of potentially
    # longer-running jobs, and at the cost of time-between-useful-logmsgs). Now
    # bumped further to adjust to newer timeout constants in API
    # implementation. Generally, this this needs more context-specific timeout
    # constants, also see https://github.com/conbench/conbench/issues/801 and
    # https://github.com/conbench/conbench/issues/806. One such
    # context-specific timeout constant is for a login request, see below.
    # Note: for now, this `timeout_long_running_requests` timeout constant
    # applies to all requests unless specified otherwise. This should be
    # aligned with other timeout constants:
    # https://github.com/conbench/conbench/issues/1384
    timeout_long_running_requests = (3.5, 150)

    timeout_login_request = (3.5, 10)

    def __init__(
        self,
        url: Optional[str] = None,
        email: Optional[str] = None,
        password: Optional[str] = None,
        default_retry_for_seconds=None,
    ):
        # If this library is embedded into a Python program that has stdlib
        # logging not set up yet (no root logger configured) then this call
        # sets up a root logger with handlers. This is a noop if the calling
        # program has a root logger already configured.
        logging.basicConfig(
            level=logging.INFO,
            format="%(asctime)s.%(msecs)03d [%(name)s] %(levelname)s: %(message)s",
            datefmt="%y%m%d-%H:%M:%S",
        )

        # Set the URL from the environment if not provided
        if url is None:
            url = os.environ.get("CONBENCH_URL")

        url = self._validate_url(url=url)

        # Construct the HTTP API base URL without a trailing slash, something
        # like https://conbench.ursa.dev/api
        self._url = url + "/api"

        super().__init__()

        if default_retry_for_seconds:
            assert isinstance(default_retry_for_seconds, (float, int))
            self.default_retry_for_seconds = default_retry_for_seconds

        # Set the email and password from the environment if not provided
        self._email = email if email is not None else os.environ.get("CONBENCH_EMAIL")
        self._password = (
            password if password is not None else os.environ.get("CONBENCH_PASSWORD")
        )

        if self._email:
            # The logic would attempt to perform login automatically after
            # receiving the first 401 response. When this env var is set,
            # anticipate that login is needed (this might do more harm than
            # use)
            self._login_or_raise()
        else:
            log.info("Conbench email not specified, skipping login")

        log.info("%s: initialized", self.__class__.__name__)

    # This method is required by parent class
    @property
    def _base_url(self) -> str:
        return self._url

    @property
    def url(self) -> str:
        """
        Return the base URL of the Conbench API server.
        """
        return self._url

    def _validate_url(self, url: str) -> str:
        """
        The return value is guaranteed to not have a trailing slash.
        """
        # Maybe rename to CONBENCH_BASE_URL.
        if url:
            # Strip leading and trailing whitespace
            url = url.strip()

        if not url:
            raise ConbenchClientException("CONBENCH_URL not set or empty")

        url = url.rstrip("/")

        # Try to catch a common user error.
        if url.endswith("/api"):
            raise ConbenchClientException("CONBENCH_URL must not end with /api")

        return url

    def _login_or_raise(self) -> None:
        """
        Perform login.

        Require credentials to be set via environment.

        Set or mutate self.session (as demanded by parent class).

        Raise an exception when login fails with a 401 error, i.e. when the
        login credentials are bad (required human intervention, no point in
        retrying).
        """
        # Log in: exchange long-lived primary credential (uid/pw) into
        # short-lived secondary credential (session id/auth token, wrapped
        # in Cookie, persisted in requests Session).
        log.info("try to perform login")

        creds = {
            "email": self._email,
            "password": self._password,
        }

        for k, v in creds.items():
            if not v:
                log.error("not set: %s", k)
                raise ConbenchClientException(
                    "credentials not set via parameters or the environment"
                )

        self.session = requests.Session()

        login_result = self._make_request_retry_until_deadline(
            method="POST",
            # Trailing slash is important so that we do not get redirected.
            # Some systems might redirect a POST to GET here.
            # Interesting topic:
            # https://github.com/galaxyproject/bioblend/pull/336
            # https://github.com/aio-libs/aiohttp/issues/6764
            url=self._base_url + "/login/",
            json=creds,
            expected_status_code=204,
            timeout=self.timeout_login_request,
        )

        if login_result == "401":
            raise RetryingHTTPClientBadCredentials(
                "bad credentials: got 401 status code in response to login request"
            )

        if isinstance(login_result, requests.Response):
            # That's the precise signal for success.
            return

        # Rely on the details to have been logged previously
        raise RetryingHTTPClientLoginError("login failed (see logs), giving up")

    def get_all(self, path: str, params: Optional[dict] = None) -> List[dict]:
        """
        Make GET requests to a paginated Conbench endpoint. Expect responses with status
        code 200, expect a JSON document in the response body of the form
        {"data": List[dict], "metadata": {"next_page_cursor": Optional[str]}}.

        Return the deserialized concatenation of the JSON data or raise an exception.

        `params` can be used to pass URL query parameters, including `"page_size"`. If
        `"cursor"` is given in `params`, it will be overwritten after the first request.
        """
        params = params or {}
        resp_json = super().get(path, params)
        data = resp_json["data"]
        while resp_json["metadata"]["next_page_cursor"]:
            params["cursor"] = resp_json["metadata"]["next_page_cursor"]
            resp_json = super().get(path, params)
            data += resp_json["data"]
        return data
