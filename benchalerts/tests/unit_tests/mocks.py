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
from typing import List, Tuple

import pytest
import requests
from benchclients.conbench import ConbenchClient
from requests.adapters import HTTPAdapter

from benchclients import log

response_dir = pathlib.Path(__file__).parent / "mocked_responses"


class MockResponse(requests.Response):
    """Construct a mocked requests.Response object by reading a specially-formatted
    JSON file.
    """

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
    """Mount this adapter to a requests session to intercept all requests and
    return mocked responses, constructed from JSON files.

    All JSON files are in the tests/unit_tests/mocked_responses/ directory. The first
    part of the filename is the HTTP method, the second is a key referring to a certain
    base URL, and the rest is the path of the request URL, with special characters
    replaced by underscores. Examples:

    - GET https://conbench.biz/api/runs/?sha=abc -> GET_conbench_runs_sha_abc.json
    - POST https://api.github.com/repos/some/repo/issues/1/comments ->
        POST_github_issues_1_comments.json

    This is intended to intercept ALL requests, and will raise an exception if the
    request does not match any JSON file following the above format.
    """

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

        # to help with check_posted_markdown(), log the markdowns that were posted
        if req.url.endswith("check-runs"):
            body = json.loads(req.body)
            log.info("Summary: " + body["output"]["summary"])
            log.info("Details: " + str(body["output"].get("text")))

        # to help with check_posted_comment(), log the comments that were posted
        if req.url.endswith("comments"):
            body = json.loads(req.body)
            log.info("Comment: " + body["body"])

        method = req.method
        clean_url = self.clean_base_url(req.url)
        response_path = response_dir / f"{method}_{clean_url}.json"

        if not response_path.exists():
            raise Exception(f"Mock response not found at {response_path}")

        return MockResponse.from_file(response_path)


class MockConbenchClient(ConbenchClient):
    """A ConbenchClient that uses MockAdapter to intercept all requests and return
    mocked responses, constructed from JSON files.
    """

    def __init__(self):
        super().__init__()
        self.session.mount("https://", MockAdapter())

    def _login_or_raise(self) -> None:
        # Since we mock all requests, logging in won't change any state, so let's skip
        # logging in. Logging in should be tested in the benchclients library already.
        #
        # (Also, as of this comment, the parent method sets up a new requests session,
        # which would mean we'd lose our MockAdapter.)
        pass


def check_posted_markdown(
    caplog: pytest.LogCaptureFixture, expected_markdowns: List[Tuple[str, str]]
):
    """After we run a test, search through the logs for what markdowns we
    mock-posted to GitHub, and assert they are what we expected.
    expected_markdowns should look like [(summary0, details0), (summary1, details1), ]
    """
    actual_summaries = [
        log_record.message[9:]
        for log_record in caplog.records
        if log_record.levelname == "INFO"
        and log_record.filename == "mocks.py"
        and log_record.message.startswith("Summary: ")
    ]
    actual_detailses = [
        log_record.message[9:]
        for log_record in caplog.records
        if log_record.levelname == "INFO"
        and log_record.filename == "mocks.py"
        and log_record.message.startswith("Details: ")
    ]
    assert len(expected_markdowns) == len(actual_summaries) == len(actual_detailses)

    for (
        (expected_summary_filename, expected_details_filename),
        (actual_summary, actual_details),
    ) in zip(expected_markdowns, zip(actual_summaries, actual_detailses)):
        base_dir = pathlib.Path(__file__).parent / "expected_md"

        with open(base_dir / (expected_summary_filename + ".md"), "r") as f:
            expected_summary = f.read()
        assert (
            expected_summary.strip() == actual_summary.strip()
        ), f"see tests/unit_tests/expected_md/{expected_summary_filename}.md"

        if expected_details_filename is None:
            assert actual_details == "None"
        else:
            with open(base_dir / (expected_details_filename + ".md"), "r") as f:
                expected_details = f.read()
            assert (
                expected_details.strip() == actual_details.strip()
            ), f"see tests/unit_tests/expected_md/{expected_details_filename}.md"


def check_posted_comment(
    caplog: pytest.LogCaptureFixture, expected_comments: List[str]
):
    """After we run a test, search through the logs for what comments we
    mock-posted to GitHub, and assert they are what we expected.
    """
    actual_comments = [
        log_record.message[9:]
        for log_record in caplog.records
        if log_record.levelname == "INFO"
        and log_record.filename == "mocks.py"
        and log_record.message.startswith("Comment: ")
    ]
    assert len(expected_comments) == len(actual_comments)

    for expected_comment_filename, actual_comment in zip(
        expected_comments, actual_comments
    ):
        base_dir = pathlib.Path(__file__).parent / "expected_md"

        with open(base_dir / (expected_comment_filename + ".md"), "r") as f:
            expected_comment = f.read()
        assert (
            expected_comment.strip() == actual_comment.strip()
        ), f"see tests/unit_tests/expected_md/{expected_comment_filename}.md"
