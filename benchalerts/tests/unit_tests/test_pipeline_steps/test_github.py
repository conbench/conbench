from traceback import format_exc
from typing import Optional

import pytest

from benchalerts import Alerter
from benchalerts.conbench_dataclasses import FullComparisonInfo
from benchalerts.integrations.github import GitHubRepoClient
from benchalerts.pipeline_steps.github import (
    GitHubCheckErrorHandler,
    GitHubCheckStep,
    GitHubPRCommentAboutCheckStep,
)

from ..mocks import (
    MockAdapter,
    MockResponse,
    check_posted_comment,
    check_posted_markdown,
    response_dir,
)


class MockAlerter(Alerter):
    def github_check_summary(
        self, full_comparison: FullComparisonInfo, build_url: Optional[str]
    ) -> str:
        base_message = super().github_check_summary(full_comparison, build_url)
        return base_message + "\n\nThis message was generated from pytest."

    def github_pr_comment(
        self, full_comparison: FullComparisonInfo, check_link: str
    ) -> str:
        base_message = super().github_pr_comment(full_comparison, check_link)
        return base_message + "\n\nThis message was generated from pytest."


@pytest.mark.parametrize(
    ["mock_comparison_info", "expected_check_summary", "expected_check_details"],
    [
        ("errors_baselines", "summary_errors_baselines", "details_regressions"),
        ("errors_nobaselines", "summary_errors_nobaselines", None),
        ("noerrors_nobaselines", "summary_noerrors_nobaselines", None),
        ("regressions", "summary_regressions", "details_regressions"),
        ("noregressions", "summary_noregressions", "details_noregressions"),
        ("nocommit", "summary_nocommit", "details_nocommit"),
        ("noruns", "summary_noruns", "details_noruns"),
        ("noresults", "summary_noresults", None),
    ],
    indirect=["mock_comparison_info"],
)
@pytest.mark.parametrize("github_auth", ["pat", "app"], indirect=True)
def test_GitHubCheckStep(
    mock_comparison_info: FullComparisonInfo,
    expected_check_summary: str,
    expected_check_details: str,
    caplog: pytest.LogCaptureFixture,
    github_auth: str,
):
    if github_auth == "pat":
        with pytest.raises(ValueError, match="GitHub App"):
            GitHubCheckStep(
                commit_hash="abc",
                github_client=GitHubRepoClient(repo="some/repo", adapter=MockAdapter()),
                comparison_step_name="comparison_step",
                external_id="123",
                build_url="https://austin.something",
                alerter=MockAlerter(),
            )
        return

    step = GitHubCheckStep(
        commit_hash="abc",
        github_client=GitHubRepoClient(repo="some/repo", adapter=MockAdapter()),
        comparison_step_name="comparison_step",
        external_id="123",
        build_url="https://austin.something",
        alerter=MockAlerter(),
    )
    gh_res, full_comparison = step.run_step({"comparison_step": mock_comparison_info})
    assert gh_res
    assert full_comparison == mock_comparison_info
    check_posted_markdown(caplog, [(expected_check_summary, expected_check_details)])


@pytest.mark.parametrize(
    ["mock_comparison_info", "expected_comment"],
    [
        ("errors_baselines", "comment_errors_baselines"),
        ("errors_nobaselines", "comment_errors_nobaselines"),
        ("noerrors_nobaselines", "comment_noerrors_nobaselines"),
        ("regressions", "comment_regressions"),
        ("noregressions", "comment_noregressions"),
        ("nocommit", "comment_nocommit"),
        ("noruns", "comment_noruns"),
        ("noresults", "comment_noresults"),
    ],
    indirect=["mock_comparison_info"],
)
@pytest.mark.parametrize("github_auth", ["pat", "app"], indirect=True)
def test_GitHubPRCommentAboutCheckStep(
    mock_comparison_info: FullComparisonInfo,
    expected_comment: str,
    caplog: pytest.LogCaptureFixture,
    github_auth: str,
):
    mock_check_response = MockResponse.from_file(
        response_dir / "POST_github_check-runs.json"
    ).json()

    step = GitHubPRCommentAboutCheckStep(
        pr_number=1,
        github_client=GitHubRepoClient(repo="some/repo", adapter=MockAdapter()),
        check_step_name="check_step",
        alerter=MockAlerter(),
    )
    res = step.run_step(
        previous_outputs={"check_step": (mock_check_response, mock_comparison_info)}
    )
    assert res
    check_posted_comment(caplog, [expected_comment])


@pytest.mark.parametrize("mock_comparison_info", ["regressions"], indirect=True)
@pytest.mark.parametrize("github_auth", ["pat", "app"], indirect=True)
def test_GitHubPRCommentAboutCheckStep_no_comment(
    mock_comparison_info: FullComparisonInfo,
    caplog: pytest.LogCaptureFixture,
    github_auth: str,
):
    class NoneAlerter(Alerter):
        def github_pr_comment(
            self, full_comparison: FullComparisonInfo, check_link: str
        ) -> str:
            return ""

    mock_check_response = MockResponse.from_file(
        response_dir / "POST_github_check-runs.json"
    ).json()

    step = GitHubPRCommentAboutCheckStep(
        pr_number=1,
        github_client=GitHubRepoClient(repo="some/repo", adapter=MockAdapter()),
        check_step_name="check_step",
        alerter=NoneAlerter(),
    )
    res = step.run_step(
        previous_outputs={"check_step": (mock_check_response, mock_comparison_info)}
    )
    assert res is None
    check_posted_comment(caplog, [])


@pytest.mark.parametrize("github_auth", ["pat", "app"], indirect=True)
def test_GitHubCheckErrorHandler(caplog: pytest.LogCaptureFixture, github_auth: str):
    try:
        1 / 0
    except Exception as e:
        exc = e
        traceback = format_exc()

    if github_auth == "pat":
        with pytest.raises(ValueError, match="GitHub App"):
            GitHubCheckErrorHandler(
                commit_hash="abc",
                github_client=GitHubRepoClient(repo="some/repo", adapter=MockAdapter()),
                build_url="https://google.com",
            )
        return

    handler = GitHubCheckErrorHandler(
        commit_hash="abc",
        github_client=GitHubRepoClient(repo="some/repo", adapter=MockAdapter()),
        build_url="https://google.com",
    )
    handler.handle_error(exc=exc, traceback=traceback)
    check_posted_markdown(caplog, [("summary_builderror", "details_builderror")])
