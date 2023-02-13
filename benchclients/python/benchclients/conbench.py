import os
from typing import Optional

from requests.adapters import HTTPAdapter

from .base import BaseClient
from .logging import fatal_and_log


class ConbenchClient(BaseClient):
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
            fatal_and_log("Environment variable CONBENCH_URL not found")

        super().__init__(adapter=adapter)
        self.base_url = url + "/api"

        login_creds = {
            "email": os.getenv("CONBENCH_EMAIL"),
            "password": os.getenv("CONBENCH_PASSWORD"),
        }
        if login_creds["email"] and login_creds["password"]:
            self.post("/login/", json=login_creds)
