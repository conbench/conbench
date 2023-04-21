import abc
from json import dumps
from typing import Optional

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from .logging import log


class BaseClient(abc.ABC):
    """A client to interact with an API.

    Parameters
    ----------
    adapter
        A requests adapter to mount to the requests session. If not given, one will be
        created with a backoff retry strategy.
    """

    base_url: str
    # Note(JP): I have bumped this from 10 to 75 seconds to err on side of
    # caution (remove stress from DB, at the cost of potentially longer-running
    # jobs, and at the cost of time-between-useful-logmsgs). This needs more
    # context-specific timeout constants, also see
    # https://github.com/conbench/conbench/issues/801 and
    # https://github.com/conbench/conbench/issues/806
    timeout_s = 75

    def __init__(self, adapter: Optional[HTTPAdapter]):
        if not adapter:
            retry_strategy = Retry(
                total=5,
                status_forcelist=frozenset((429, 502, 503, 504)),
                backoff_factor=4,  # will retry in 2, 4, 8, 16, 32 seconds
            )
            adapter = HTTPAdapter(max_retries=retry_strategy)

        self.session = requests.Session()
        self.session.mount("https://", adapter)

    def get(self, path: str, params: Optional[dict] = None) -> dict:
        """Make a GET request"""
        url = self.base_url + path

        req_string = f"GET {url} {params=}"
        log.debug(req_string)

        res = self.session.get(url=url, params=params, timeout=self.timeout_s)
        self._maybe_raise(req_string=req_string, res=res)

        return res.json()

    def post(self, path: str, json: Optional[dict] = None) -> Optional[dict]:
        """Make a POST request"""
        json = json or {}
        url = self.base_url + path

        req_string = f"POST {url} {dumps(json)}"
        log.debug(req_string)

        res = self.session.post(url=url, json=json, timeout=self.timeout_s)
        self._maybe_raise(req_string=req_string, res=res)

        if res.content:
            return res.json()

    def put(self, path: str, json: dict) -> Optional[dict]:
        """Make a PUT request"""
        url = self.base_url + path

        req_string = f"PUT {url} {dumps(json)}"
        log.debug(req_string)

        res = self.session.put(url=url, json=json, timeout=self.timeout_s)
        self._maybe_raise(req_string=req_string, res=res)

        if res.content:
            return res.json()

    @staticmethod
    def _maybe_raise(req_string: str, res: requests.Response):
        try:
            res.raise_for_status()
        except requests.HTTPError as e:
            try:
                res_content = e.response.content.decode()
            except AttributeError:
                res_content = e.response.content
            log.error(f"Failed request: {req_string}")
            log.error(f"Response content: {res_content}")
            raise
