# All copied from https://github.com/conbench/benchalerts/blob/main/benchalerts/clients.py
# TODO: extract client into a package and have both packages use it as a dep (or otherwise
# use the same code somehow)

import abc
import os
from json import dumps
from typing import Optional

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from .log import fatal_and_log, log


class _BaseClient(abc.ABC):
    """A client to interact with an API.
    Parameters
    ----------
    adapter
        A requests adapter to mount to the requests session. If not given, one will be
        created with a backoff retry strategy.
    """

    base_url: str
    timeout_s = 10

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

    def get(self, path: str) -> dict:
        url = self.base_url + path
        log.debug(f"GET {url}")
        res = self.session.get(url=url, timeout=self.timeout_s)
        self._maybe_raise(res=res)

        return res.json()

    def post(self, path: str, json: dict) -> Optional[dict]:
        url = self.base_url + path
        log.debug(f"POST {url} {dumps(json)}")
        res = self.session.post(url=url, json=json, timeout=self.timeout_s)
        self._maybe_raise(res=res)

        if res.content:
            return res.json()

    @staticmethod
    def _maybe_raise(res: requests.Response):
        try:
            res.raise_for_status()
        except requests.HTTPError as e:
            try:
                res_content = e.response.content.decode()
            except AttributeError:
                res_content = e.response.content
            log.error(f"Response content: {res_content}")
            raise


class ConbenchClient(_BaseClient):
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
        The email to use for Conbench login. Only required if the server is private.
    CONBENCH_PASSWORD
        The password to use for Conbench login. Only required if the server is private.
    """

    def __init__(self, adapter: Optional[HTTPAdapter] = None):
        url = os.getenv("CONBENCH_URL")
        if not url:
            fatal_and_log("Environment variable CONBENCH_URL not found")

        super().__init__(adapter=adapter)
        self.base_url = url + "/api"

        login_creds = {
            "email": os.getenv("CONBENCH_EMAIL"),
            "password": os.getenv("CONBENCH_PASSWORD"),
        }
        if login_creds["email"] and login_creds["password"]:
            self.post("/login/", json=login_creds)
