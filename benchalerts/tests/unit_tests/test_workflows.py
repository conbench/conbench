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

import pathlib
from typing import List, Tuple

import pytest
from _pytest.logging import LogCaptureFixture

import benchalerts.workflows as flows
from benchalerts.clients import ConbenchClient, GitHubRepoClient

from .mocks import MockAdapter


def check_posted_markdown(
    caplog: LogCaptureFixture, expected_markdowns: List[Tuple[str, str]]
):
    """After we run a workflow, search through the logs for what markdowns we
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


@pytest.mark.parametrize("z_score_threshold", [None, 500])
@pytest.mark.parametrize("github_auth", ["pat", "app"], indirect=True)
@pytest.mark.parametrize(
    "workflow",
    [
        flows.update_github_status_based_on_regressions,
        flows.update_github_check_based_on_regressions,
    ],
)
def test_flows(
    github_auth, conbench_env, z_score_threshold, workflow, caplog: LogCaptureFixture
):
    caplog.set_level("DEBUG")
    gh = GitHubRepoClient("some/repo", adapter=MockAdapter())
    cb = ConbenchClient(adapter=MockAdapter())

    res = workflow(
        contender_sha="abc", z_score_threshold=z_score_threshold, github=gh, conbench=cb
    )
    if workflow == flows.update_github_status_based_on_regressions:
        assert res["description"] == "Testing something"
    elif workflow == flows.update_github_check_based_on_regressions:
        if z_score_threshold:
            expected_markdowns = [
                ("summary_pending", None),
                ("summary_workflow_noregressions", "details_workflow_noregressions"),
            ]
        else:
            expected_markdowns = [
                ("summary_pending", None),
                ("summary_workflow_regressions", "details_workflow_regressions"),
            ]
        check_posted_markdown(caplog, expected_markdowns)


@pytest.mark.parametrize("github_auth", ["pat", "app"], indirect=True)
@pytest.mark.parametrize(
    "workflow",
    [
        flows.update_github_status_based_on_regressions,
        flows.update_github_check_based_on_regressions,
    ],
)
def test_flows_failure(
    github_auth, missing_conbench_env, workflow, caplog: LogCaptureFixture
):
    caplog.set_level("DEBUG")
    gh = GitHubRepoClient("some/repo", adapter=MockAdapter())

    with pytest.raises(ValueError, match="not found"):
        workflow(contender_sha="abc", github=gh)

    if workflow == flows.update_github_check_based_on_regressions:
        expected_markdowns = [
            ("summary_pending", None),
            ("summary_error", "details_error"),
        ]
        check_posted_markdown(caplog, expected_markdowns)


@pytest.mark.parametrize("github_auth", ["pat", "app"], indirect=True)
@pytest.mark.parametrize(
    "workflow",
    [
        flows.update_github_status_based_on_regressions,
        flows.update_github_check_based_on_regressions,
    ],
)
def test_flows_no_baseline(
    github_auth, conbench_env, workflow, caplog: LogCaptureFixture
):
    caplog.set_level("DEBUG")
    gh = GitHubRepoClient("some/repo", adapter=MockAdapter())
    cb = ConbenchClient(adapter=MockAdapter())

    res = workflow(contender_sha="no_baseline", github=gh, conbench=cb)
    if workflow == flows.update_github_status_based_on_regressions:
        assert res["description"] == "Could not find any baseline runs to compare to"
    elif workflow == flows.update_github_check_based_on_regressions:
        expected_markdowns = [
            ("summary_pending_nobaseline", None),
            ("summary_nobaseline", None),
        ]
        check_posted_markdown(caplog, expected_markdowns)
