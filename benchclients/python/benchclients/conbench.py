import logging
import os
from typing import Optional

import requests
from requests.adapters import HTTPAdapter

from .base import BaseClient
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
    # applies to all requests unless specified otherwise.
    timeout_long_running_requests = (120, 3.5)

    timeout_login_request = (10, 3.5)

    def __init__(self, default_retry_for_seconds=None, adapter=None):
        # If this library is embedded into a Python program that has stdlib
        # logging not set up yet (no root logger configured) then this call
        # sets up a root logger with handlers. This is a noop if the calling
        # program has a root logger already configured.
        logging.basicConfig(
            level=logging.INFO,
            format="%(asctime)s.%(msecs)03d [%(name)s] %(levelname)s: %(message)s",
            datefmt="%y%m%d-%H:%M:%S",
        )

        url = self._read_base_url_from_env_or_raise()

        if adapter:
            # Let's phase this out.
            log.info("ignoring adapter: %s", adapter)

        # Construct the HTTP API base URL without a trailing slash, something
        # like https://conbench.ursa.dev/api
        self._url = url + "/api"

        super().__init__()

        if default_retry_for_seconds:
            assert isinstance(default_retry_for_seconds, (float, int))
            self.default_retry_for_seconds = default_retry_for_seconds

        if "CONBENCH_EMAIL" in os.environ:
            # The logic would attempt to perform login automatically after
            # receiving the first 401 response. When this env var is set,
            # anticipate that login is needed (this might do more harm than
            # use)
            self._login_or_raise()
        else:
            log.info("CONBENCH_EMAIL not in environment, skipping login")

        log.info("%s: initialized", self.__class__.__name__)

    # This method is required by parent class
    @property
    def _base_url(self) -> str:
        return self._url

    def _read_base_url_from_env_or_raise(self) -> str:
        """
        The return value is guaranteed to not have a trailing slash.
        """
        # Maybe rename to CONBENCH_BASE_URL.
        url = os.getenv("CONBENCH_URL")
        if url:
            # Strip leading and trailing whitespace
            url = url.strip()

        if not url:
            raise ConbenchClientException(
                "Environment variable CONBENCH_URL not set or empty"
            )

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
            "email": os.getenv("CONBENCH_EMAIL"),
            "password": os.getenv("CONBENCH_PASSWORD"),
        }

        for k, v in creds.items():
            if not v:
                log.error("not set: %s", k)
                raise ConbenchClientException("credentials not set via environment")

        self.session = requests.Session()

        login_result = self._make_request_retry_until_deadline(
            method="POST",
            url=self._base_url + "/login",
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


class LegacyConbenchClient(BaseClient):
    """A client to interact with a Conbench server.
    Parameters
    ----------
    adapter
        A requests adapter to mount to the requests session. If not given, one will be
        created with a backoff retry strategy.
    Environment variables
    ---------------------
    CONBENCH_URL
        The URL of the Conbench server. Required.
    CONBENCH_EMAIL
        The email to use for Conbench login. Only required for GETting if the server is private.
    CONBENCH_PASSWORD
        The password to use for Conbench login. Only required for GETting if the server is private.
    """

    def __init__(self, adapter: Optional[HTTPAdapter] = None):
        url = os.getenv("CONBENCH_URL")
        if not url:
            raise Exception("Environment variable CONBENCH_URL not found")

        super().__init__(adapter=adapter)
        self.base_url = url + "/api"

        login_creds = {
            "email": os.getenv("CONBENCH_EMAIL"),
            "password": os.getenv("CONBENCH_PASSWORD"),
        }
        if login_creds["email"] and login_creds["password"]:
            self.post("/login/", json=login_creds)
