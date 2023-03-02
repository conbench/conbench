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

import benchalerts.pipeline_steps as steps
from benchalerts import AlertPipeline


@pytest.mark.parametrize("github_auth", ["pat", "app"], indirect=True)
def test_update_github_status_based_on_regressions(
    monkeypatch: pytest.MonkeyPatch, github_auth: str
):
    """While this test is running, you can watch
    https://github.com/conbench/benchalerts/pull/5 to see the statuses change!
    """
    if github_auth == "pat" and os.getenv("CI"):
        pytest.skip("The CI PAT does not work with this test")

    # note: something *might* go wrong if we go past 1000 statuses on this test commit?
    # https://docs.github.com/en/rest/commits/statuses#create-a-commit-status
    test_status_repo = "conbench/benchalerts"
    test_status_commit = "4b9543876e8c1cee54c56980c3b2363aad71a8d4"

    monkeypatch.setenv("CONBENCH_URL", "https://velox-conbench.voltrondata.run/")
    velox_commit = "c76715c9db1eea7cf3f32dca6fe78fc35c4f3ecd"

    github_run_id = os.getenv("GITHUB_RUN_ID", "2974120883")
    build_url = f"https://github.com/{test_status_repo}/actions/runs/{github_run_id}"

    # first, test error handlers
    error_handlers = [
        steps.GitHubStatusErrorHandler(
            commit_hash=test_status_commit, repo=test_status_repo, build_url=build_url
        )
    ]
    if github_auth == "app":
        error_handlers.append(
            steps.GitHubCheckErrorHandler(
                commit_hash=test_status_commit,
                repo=test_status_repo,
                build_url=build_url,
            )
        )

    pipeline = AlertPipeline(
        steps=[
            steps.GitHubStatusStep(
                repo=test_status_repo, comparison_step_name="doesnt_exist"
            )
        ],
        error_handlers=error_handlers,
    )
    with pytest.raises(KeyError):
        pipeline.run_pipeline()

    # sleep to see the updated statuses on the PR
    time.sleep(1)

    # now a real pipeline
    pipeline_steps = [
        steps.GetConbenchZComparisonStep(
            commit_hash=velox_commit, z_score_threshold=None, step_name="z_none"
        ),
        steps.GetConbenchZComparisonStep(
            commit_hash=velox_commit, z_score_threshold=500, step_name="z_500"
        ),
        steps.GitHubStatusStep(
            repo=test_status_repo,
            commit_hash=test_status_commit,
            comparison_step_name="z_500",
        ),
    ]
    if github_auth == "app":
        pipeline_steps.append(
            steps.GitHubCheckStep(
                repo=test_status_repo,
                commit_hash=test_status_commit,
                comparison_step_name="z_none",
            )
        )

    pipeline = AlertPipeline(pipeline_steps)
    outputs = pipeline.run_pipeline()

    assert outputs["GitHubStatusStep"]["state"] == "success"
    if github_auth == "pat":
        assert outputs["GitHubStatusStep"]["creator"]["type"] == "User"
    if github_auth == "app":
        assert outputs["GitHubStatusStep"]["creator"]["type"] == "Bot"
        assert outputs["GitHubCheckStep"]["conclusion"] == "failure"

    # sleep to see the updated statuses on the PR
    time.sleep(1)
