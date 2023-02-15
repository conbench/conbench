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

import os
import time

import pytest

import benchalerts.workflows as flows
from benchalerts.clients import GitHubRepoClient


@pytest.mark.parametrize(
    "arrow_commit",
    [
        # no errors
        "13a7b605ede88ca15b053f119909c48d0919c6f8",
        # errors
        "9fa34df27eb1445ac11b0ab0298d421b04be80f7",
    ],
)
@pytest.mark.parametrize(
    "workflow",
    [
        flows.update_github_status_based_on_regressions,
        flows.update_github_check_based_on_regressions,
    ],
)
@pytest.mark.parametrize("github_auth", ["pat", "app"], indirect=True)
@pytest.mark.parametrize("z_score_threshold", [None, 500])
def test_update_github_status_based_on_regressions(
    monkeypatch: pytest.MonkeyPatch,
    github_auth: str,
    z_score_threshold,
    workflow,
    arrow_commit: str,
):
    """While this test is running, you can watch
    https://github.com/conbench/benchalerts/pull/5 to see the statuses change!
    """
    if (
        workflow == flows.update_github_status_based_on_regressions
        and not arrow_commit.startswith("13a")
    ):
        pytest.skip("Skipping redundant tests to cut down on test time")

    if (
        workflow == flows.update_github_check_based_on_regressions
        and github_auth == "pat"
    ):
        pytest.skip("Can't use the Checks API with a PAT")

    # note: something *might* go wrong if we go past 1000 statuses on this test SHA?
    # https://docs.github.com/en/rest/commits/statuses#create-a-commit-status
    test_status_repo = "conbench/benchalerts"
    test_status_commit = "4b9543876e8c1cee54c56980c3b2363aad71a8d4"

    arrow_conbench_url = "https://conbench.ursa.dev/"

    github_run_id = os.getenv("GITHUB_RUN_ID", "2974120883")
    build_url = f"https://github.com/{test_status_repo}/actions/runs/{github_run_id}"
    monkeypatch.setenv("BUILD_URL", build_url)

    # first, test an error
    monkeypatch.delenv("CONBENCH_URL", raising=False)
    with pytest.raises(ValueError, match="CONBENCH_URL not found"):
        workflow(contender_sha=test_status_commit, repo=test_status_repo)

    # sleep to see the updated status on the PR
    time.sleep(1)

    # next, a success if z_score_threshold=500, or failure if z_score_threshold=None
    monkeypatch.setenv("CONBENCH_URL", arrow_conbench_url)

    # Even though we're grabbing Arrow benchmarks, we want to post to our own repo for
    # testing. This class overrides the methods to post statuses to a different commit.
    class GitHubDifferentRepoClient(GitHubRepoClient):
        def update_commit_status(self, commit_sha, **kwargs):
            return super().update_commit_status(commit_sha=test_status_commit, **kwargs)

        def update_check(self, commit_sha, **kwargs):
            return super().update_check(commit_sha=test_status_commit, **kwargs)

    github = GitHubDifferentRepoClient(repo=test_status_repo)

    res = workflow(
        contender_sha=arrow_commit, z_score_threshold=z_score_threshold, github=github
    )
    if workflow == flows.update_github_status_based_on_regressions:
        if z_score_threshold is None:
            assert res["state"] == "failure"
        else:
            assert res["state"] == "success"

        if github_auth == "pat":
            assert res["creator"]["type"] == "User"
        elif github_auth == "app":
            assert res["creator"]["type"] == "Bot"

    elif workflow == flows.update_github_check_based_on_regressions:
        if arrow_commit.startswith("9fa"):
            assert res["conclusion"] == "action_required"
        elif z_score_threshold is None:
            assert res["conclusion"] == "failure"
        else:
            assert res["conclusion"] == "success"

    # sleep to see the updated status on the PR
    time.sleep(1)
