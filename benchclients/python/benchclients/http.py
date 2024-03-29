import logging
import time
from abc import ABC, abstractmethod
from json import dumps as jsondumps
from typing import Dict, List, Literal, Optional, Tuple, Union

import requests

log = logging.getLogger(__name__)


TypeHTTPMethods = Literal["GET", "PUT", "POST", "DELETE", "HEAD", "OPTIONS", "HEAD"]


class RetryingHTTPClientException(Exception):
    """
    Base exception type used by RetryingHTTPClient.
    """


class RetryingHTTPClientLoginError(RetryingHTTPClientException):
    """
    Base exception for login errors, raise directly when login failed as of any
    non-401 error (network problem, other unexpected response, ...).
    """


class RetryingHTTPClientBadCredentials(RetryingHTTPClientLoginError):
    """
    Raise when login fails as of a 401 error (bad credentials).
    """


class RetryingHTTPClientDeadlineReached(RetryingHTTPClientException):
    """
    Raise when giving up after retrying as of a per-request retrying
    deadline/timeout criterion, usually shortly before reaching the deadline
    (rarely exceeding).
    """


class RetryingHTTPClientNonRetryableResponse(RetryingHTTPClientException):
    """
    Raise when within a retry loop and when receiving an HTTP response that
    should not be repeated.
    """

    def __init__(self, message, error_response: requests.Response):
        super().__init__(message)
        self.error_response = error_response


class RetryingHTTPClient(ABC):
    """
    HTTP client abstraction tuned towards use cases in the context of
    continuous integration jobs.

    - focus on persistent retrying
    - detailed logging along the request/response retrying lifecycle
    - handle 401 response with re-login
    """

    default_retry_for_seconds: float
    timeout_login_request: Tuple[float, float]
    timeout_long_running_requests: Tuple[float, float]

    def __init__(self) -> None:
        # This is to retain state across request, mainly authentication state.
        # self._login_or_raise() has to persist its authentication state here,
        # via e.g. cookies.
        self.session = requests.Session()

    @property
    @abstractmethod
    def _base_url(self) -> str:
        """
        Base URL. Child class must implement this. I would have picked an
        actual abstract property (instead of a method), but this here seems
        to be stricter.
        """

    @abstractmethod
    def _login_or_raise(self) -> None:
        """
        Perform login.

        Is expected to set self.session to an instance of requests.Session.

        Persist authentication state in self.session.

        Raise RetryingHTTPClientBadCredentials or RetryingHTTPClientLoginError.

        The implementation should use

                _make_request_retry_until_deadline()

        for doing the login request (with persistent retrying).
        """

    def _abs_url_from_path(self, path) -> str:
        assert path.startswith("/")
        return self._base_url.rstrip("/") + path

    def get(self, path: str, params: Optional[dict] = None) -> Union[Dict, List]:
        """
        Make GET request. Expect response with status code 200, expect a JSON
        document in the response body.

        Return the deserialized JSON document or raise an exception.

        `params` can be used to pass URL query parameters.
        """
        resp = self._make_request(
            "GET", self._abs_url_from_path(path), 200, params=params
        )
        return resp.json()

    def put(self, path: str, json: Dict) -> Optional[Union[Dict, List]]:
        """
        Make PUT request. Send a JSON document in the request body. Expect
        response with status code 201.

        If the response has no body then return `None`.

        If the response has a body of non-zero length then expect a JSON
        document.

        Return the deserialized JSON document or raise an exception.

        Interface inherited from previous lib.
        """
        json = json or {}

        resp = self._make_request("PUT", self._abs_url_from_path(path), 201, json=json)

        if resp.content:
            return resp.json()

        return None

    def post(
        self, path: str, json: Optional[dict] = None
    ) -> Optional[Union[Dict, List]]:
        """
        Make POST request. Send a JSON document in the request body. Expect
        response with status code 201.

        If the response has no body then return `None`.

        If the response has a body of non-zero length then expect a JSON
        document.

        Return the deserialized JSON document or raise an exception.

        Interface inherited from previous lib.
        """
        json = json or {}

        if json:
            log.debug("POST request JSON body:\n%s", jsondumps(json, indent=2))
        else:
            log.debug("POST request without body. Hm.")

        resp = self._make_request("POST", self._abs_url_from_path(path), 201, json=json)

        if resp.content:
            return resp.json()

        return None

    def _make_request(
        self,
        method: TypeHTTPMethods,
        url: str,
        expected_status_code: int,
        # body: Optional[Union[Dict, List]] = None,
        **kwargs,
    ) -> requests.Response:
        """
        Emit HTTP request. Perform persistent retrying in view of typical
        retryable errors.

        Return `requests.Response` object when the request was sent out and
        responded to with an HTTP response with `expected_status_code`.

        Alternatively, raise one of the exceptions derived from
        RetryingHTTPClientException:

            - RetryingHTTPClientDeadlineReached
            - RetryingHTTPClientNonRetryableResponse
            - RetryingHTTPClientLoginError

        A typical case for `RetryingHTTPClientNonRetryableResponse` to be
        thrown is in view of a 400 Bad Request response. Note however that it
        might also be thrown for example for a 200 OK response if the caller
        didn't precisely and correctly predict the single
        `expected_status_code`.

        Error responses are not returned to the caller. The caller can rely on
        error response details to have been logged (that's the design trade-off
        of this client implementation: it does opinionated centralized error
        handling).
        """
        # Assume that authentication state is good (it might not be).
        result = self._make_request_retry_until_deadline(
            method, url, expected_status_code, **kwargs
        )

        if result != "401":
            return result

        # The other end just told us that authentication proof was not provided
        # or that that presented authentication proof was bad (e.g., expired).
        # Trigger machinery for obtaining fresh authentication proof.
        log.info("got a 401 response during non-login request, login (again)")
        self._login_or_raise()

        log.info("login succeeded, repeat earlier request")
        result = self._make_request_retry_until_deadline(
            method, url, expected_status_code, **kwargs
        )
        if result != "401":
            return result

        raise RetryingHTTPClientLoginError(
            "retried request after successful (re)login, but failed -- give up"
        )

    def _make_request_retry_until_deadline(
        self,
        method: TypeHTTPMethods,
        url: str,
        expected_status_code: int,
        # body: Optional[Union[Dict, List]] = None,
        **kwargs,
    ) -> Union[Literal["401"], requests.Response]:
        """
        Return `requests.Response` object when the request was sent out and
        responded to with an HTTP response with the expected status code.

        Return literal "401" when the API returned a 401 response, allowing for
        the caller to redo login.

        This implements the outer retry loop with deadline control.

        Interrupt the retry loop and raise
        RetryingHTTPClientNonRetryableResponse when an unexpected HTTP response
        was obtained that suggests a non-retryable error.

        Raise `RetryingHTTPClientDeadlineReached` when reaching the deadline
        (it might raise a minute early, or even be briefly exceeded).

        Remaining keyword arguments are passed through
        requests.session.request(...)
        """

        t0 = time.monotonic()
        deadline = t0 + self.default_retry_for_seconds  # 30 * 60
        cycle: int = 0

        log.info("try: %s to %s", method, url)

        while time.monotonic() < deadline:
            cycle += 1

            result = self._make_request_retry_guts(
                method, url, expected_status_code, **kwargs
            )

            if result != "retry":
                return result

            # The first retry cycles come quickly, then there is slow exp
            # growth, and a max: 0.66, 1.33, 2.66, 5.33, 10.66, 21.33, 42.66,
            # 60, 60, ....
            wait_seconds = min((2**cycle) / 3.0, 60)
            log.info(
                "cycle %s failed, wait for %.1f s, deadline in %.1f min",
                cycle,
                wait_seconds,
                (deadline - time.monotonic()) / 60.0,
            )

            # Would the next wait exceed the deadline?
            if (time.monotonic() + wait_seconds) > deadline:
                break

            time.sleep(wait_seconds)

        # Give up after retrying.
        raise RetryingHTTPClientDeadlineReached(
            f"{method} request to {url}: giving up after {time.monotonic() - t0:.3f} s"
        )

    def _make_request_retry_guts(
        self,
        method: TypeHTTPMethods,
        url: str,
        expected_status_code: int,
        # body: Optional[Union[Dict, List]] = None,
        **kwargs,
    ) -> Union[Literal["401"], Literal["retry"], requests.Response]:
        """
        Return `requests.Response` object when the request was sent out and
        responded to with an HTTP response with the expected status code.

        Return "retry" to indicate a retryable error to the caller.

        Return literal "401" when receiving 401 response, allowing for the
        caller to redo login.

        Raise RetryingHTTPClientNonRetryableResponse when an unexpected HTTP
        response was obtained reflecting a non-retryable error.
        """

        if "timeout" not in kwargs:
            # Default to longer timeout constants.
            # timeout = self.timeout_long_running_requests
            kwargs["timeout"] = self.timeout_long_running_requests

        t0 = time.monotonic()

        # The call to `request()` below is expected to raise exceptions
        # deriving from `requests.exceptions.RequestException`, all
        # corresponding to transient (assumed-to-be-retryable) errors on DNS or
        # TCP level. These can happen before sending the request, while sending
        # the request, while waiting for response, or while receiving the
        # response. (just a few) examples for common errors:
        # - DNS resolution error
        # - TCP connect() timeout
        # - Timeout while waiting for the other end to start sending the HTTP
        #   response`
        #
        # requests has a little bit of rather local retrying built-in by
        # default for some of these errors (e.g., there might be three quick
        # retries upon DNS resolution errors before it throws an exception.) In
        # general, it's not trying too hard.

        # Here, we want to have a tight connect() timeout and a meaningful
        # request/read timeout (allowing for long HTTP request processing time
        # in the API implementation).
        try:
            resp = self.session.request(method=method, url=url, **kwargs)
        except requests.exceptions.RequestException as exc:
            log.info(
                "error during request/response cycle (treat as retryable, retry soon): %s",
                exc,
            )
            return "retry"

        # Got an HTTP response. In the scope below, `resp` reflects that.
        log.info(
            "%s request to %s: took %.4f s, response status code: %s",
            method,
            url,
            time.monotonic() - t0,
            resp.status_code,
        )

        if resp.status_code == expected_status_code:
            return resp

        # Decide whether or not this is retryable based on the response status
        # code alone so that this decision can be put into the log message
        # before leaving this function.
        retryable_code = self._retryable_status_code(resp.status_code)

        # Log body prefix: sometimes this is critical for debuggability.
        log.info(
            "unexpected response. code: %s%s, body bytes: <%s ...>",
            resp.status_code,
            " (retryable)" if retryable_code else "",
            resp.text[:400],
        )

        if retryable_code:
            return "retry"

        # 401 has a distinct meaning.
        if resp.status_code == 401:
            return "401"

        # Consider all other states to be a non-retryable error. Example: A
        # variety of 4xx responses, in particular 400. Current code assumes
        # that 3xx responses do not show up here (that redirects are followed
        # automatically by requests' logic).

        msg = (
            f"{method} request to {url}: unexpected HTTP response. Expected code "
            f"{expected_status_code}, got {resp.status_code}. Leading bytes of body: <{resp.text[:150]} ...>"
        )

        raise RetryingHTTPClientNonRetryableResponse(message=msg, error_response=resp)

    def _retryable_status_code(self, code: int) -> bool:
        """
        Do we (want to) consider this response as retryable, based on the
        status code alone?
        """
        if code == 429:
            # Canonical way to signal "back off, retry soon".
            return True

        # Retry upon any 5xx response, later maybe fine-tune by specific status
        # code.
        if str(code).startswith("5"):
            return True

        return False
