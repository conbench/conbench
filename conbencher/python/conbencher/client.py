import abc
import os
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
        res.raise_for_status()
        return res.json()

    def post(self, path: str, json: dict) -> Optional[dict]:
        url = self.base_url + path
        log.debug(f"POST {url} {json}")
        res = self.session.post(url=url, json=json, timeout=self.timeout_s)
        res.raise_for_status()
        if res.content:
            return res.json()


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
        The URL of the Conbench server.
    CONBENCH_EMAIL
        The email to use for Conbench login.
    CONBENCH_PASSWORD
        The password to use for Conbench login.
    """

    def __init__(self, adapter: Optional[HTTPAdapter] = None):
        login_creds = {
            "url": os.getenv("CONBENCH_URL"),
            "email": os.getenv("CONBENCH_EMAIL"),
            "password": os.getenv("CONBENCH_PASSWORD"),
        }
        for cred in login_creds:
            if not login_creds[cred]:
                fatal_and_log(f"Environment variable CONBENCH_{cred.upper()} not found")

        super().__init__(adapter=adapter)
        self.base_url = login_creds.pop("url") + "/api"
        self.post("/login/", json=login_creds)
