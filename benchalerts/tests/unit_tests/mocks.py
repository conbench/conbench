# Copyright (c) 2022, Voltron Data.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import json
import pathlib

import requests
from requests.adapters import HTTPAdapter

from benchalerts.log import log

response_dir = pathlib.Path(__file__).parent / "mocked_responses"


class MockResponse(requests.Response):
    def __init__(self, status_code, data=None):
        super().__init__()
        self.status_code = status_code
        if data is not None:
            self._content = str.encode(json.dumps(data))

    @classmethod
    def from_file(cls, file: pathlib.Path):
        with open(file, "r") as f:
            response: dict = json.load(f)
        return cls(status_code=response["status_code"], data=response.get("data"))


class MockAdapter(HTTPAdapter):
    @staticmethod
    def clean_base_url(url: str) -> str:
        bases = {
            "https://api.github.com/repos/some/repo": "github",
            "https://api.github.com/app": "github_app",
            "https://conbench.biz/api": "conbench",
        }
        for base_url, base_name in bases.items():
            if url.startswith(base_url):
                clean_path = url.split(base_url + "/")[1]
                for char in ["/", "&", "?", "=", ".", "__", "__"]:
                    clean_path = clean_path.replace(char, "_")
                if clean_path.endswith("_"):
                    clean_path = clean_path[:-1]
                return base_name + "_" + clean_path if clean_path else base_name

        raise Exception(f"No base URL was mocked for this request: {url}")

    def send(self, *args, **kwargs):
        req: requests.PreparedRequest = args[0]
        log.info(f"Sent request {req}({req.__dict__}) with kwargs {kwargs}")

        # to help with test_workflows.py, log the markdowns that were posted
        if req.url.endswith("check-runs"):
            body = json.loads(req.body)
            log.info("Summary: " + body["output"]["summary"])
            log.info("Details: " + str(body["output"].get("text")))

        method = req.method
        clean_url = self.clean_base_url(req.url)
        response_path = response_dir / f"{method}_{clean_url}.json"

        if not response_path.exists():
            raise Exception(f"Mock response not found at {response_path}")

        return MockResponse.from_file(response_path)
