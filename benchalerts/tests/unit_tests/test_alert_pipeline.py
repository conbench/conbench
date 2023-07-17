import pytest

import benchalerts.pipeline_steps as steps
from benchalerts import AlertPipeline
from benchalerts.integrations.github import GitHubRepoClient

from .mocks import MockAdapter, MockConbenchClient


@pytest.mark.parametrize("github_auth", ["app"], indirect=True)
def test_reasonable_pipeline(conbench_env, github_auth):
    commit_hash = "abc"
    repo = "some/repo"
    build_url = "https://google.com"

    conbench_client = MockConbenchClient()
    github_client = GitHubRepoClient(repo=repo, adapter=MockAdapter())

    pipeline = AlertPipeline(
        steps=[
            steps.GetConbenchZComparisonStep(
                commit_hash=commit_hash,
                baseline_run_type=steps.BaselineRunCandidates.fork_point,
                z_score_threshold=None,
                conbench_client=conbench_client,
                step_name="z_none",
            ),
            steps.GetConbenchZComparisonStep(
                commit_hash=commit_hash,
                baseline_run_type=steps.BaselineRunCandidates.fork_point,
                z_score_threshold=500,
                conbench_client=conbench_client,
                step_name="z_500",
            ),
            steps.GitHubCheckStep(
                commit_hash=commit_hash,
                comparison_step_name="z_none",
                github_client=github_client,
                external_id="123",
            ),
            steps.GitHubPRCommentAboutCheckStep(
                pr_number=1, github_client=github_client
            ),
        ],
        error_handlers=[
            steps.GitHubCheckErrorHandler(
                commit_hash=commit_hash,
                github_client=github_client,
                build_url=build_url,
            ),
        ],
    )

    res = pipeline.run_pipeline()
    for step_name in [
        "z_none",
        "z_500",
        "GitHubCheckStep",
        "GitHubPRCommentAboutCheckStep",
    ]:
        assert res[step_name]

    # now force an error to test error handling
    pipeline.steps.append(
        steps.GitHubCheckStep(
            commit_hash=commit_hash,
            comparison_step_name="doesnt_exist",
            github_client=github_client,
        ),
    )
    with pytest.raises(KeyError):
        pipeline.run_pipeline()
