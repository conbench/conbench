from traceback import format_exc

import pytest

from benchalerts.conbench_dataclasses import FullComparisonInfo
from benchalerts.integrations.github import GitHubRepoClient
from benchalerts.pipeline_steps.github import (
    GitHubCheckErrorHandler,
    GitHubCheckStep,
    GitHubPRCommentAboutCheckStep,
    GitHubStatusErrorHandler,
    GitHubStatusStep,
)

from ..mocks import MockAdapter, MockResponse, check_posted_markdown, response_dir


@pytest.mark.parametrize(
    ["mock_comparison_info", "expected_check_summary", "expected_check_details"],
    [
        ("errors_baselines", "summary_errors_baselines", "details_regressions"),
        ("errors_nobaselines", "summary_errors_nobaselines", None),
        ("noerrors_nobaselines", "summary_noerrors_nobaselines", None),
        ("regressions", "summary_regressions", "details_regressions"),
        ("noregressions", "summary_noregressions", "details_noregressions"),
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
                github_client=GitHubRepoClient(repo="some/repo", adapter=MockAdapter()),
                comparison_step_name="comparison_step",
                warn_if_baseline_isnt_parent=True,
            )
        return

    step = GitHubCheckStep(
        github_client=GitHubRepoClient(repo="some/repo", adapter=MockAdapter()),
        comparison_step_name="comparison_step",
        warn_if_baseline_isnt_parent=True,
    )
    res = step.run_step({"comparison_step": mock_comparison_info})
    assert res
    check_posted_markdown(caplog, [(expected_check_summary, expected_check_details)])


@pytest.mark.parametrize(
    "mock_comparison_info",
    [
        "errors_baselines",
        "errors_nobaselines",
        "noerrors_nobaselines",
        "regressions",
        "noregressions",
    ],
    indirect=["mock_comparison_info"],
)
@pytest.mark.parametrize("github_auth", ["pat", "app"], indirect=True)
def test_GitHubStatusStep(mock_comparison_info: FullComparisonInfo, github_auth: str):
    step = GitHubStatusStep(
        github_client=GitHubRepoClient(repo="some/repo", adapter=MockAdapter()),
        comparison_step_name="comparison_step",
    )
    res = step.run_step({"comparison_step": mock_comparison_info})
    assert res


@pytest.mark.parametrize("github_auth", ["pat", "app"], indirect=True)
def test_GitHubPRCommentAboutCheckStep(github_auth: str):
    mock_check_response = MockResponse.from_file(
        response_dir / "POST_github_check-runs.json"
    ).json()

    step = GitHubPRCommentAboutCheckStep(
        pr_number=1,
        github_client=GitHubRepoClient(repo="some/repo", adapter=MockAdapter()),
        check_step_name="check_step",
    )
    res = step.run_step(previous_outputs={"check_step": mock_check_response})
    assert res


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


@pytest.mark.parametrize("github_auth", ["pat", "app"], indirect=True)
def test_GitHubStatusErrorHandler(github_auth: str):
    try:
        1 / 0
    except Exception as e:
        exc = e
        traceback = format_exc()

    handler = GitHubStatusErrorHandler(
        commit_hash="abc",
        github_client=GitHubRepoClient(repo="some/repo", adapter=MockAdapter()),
        build_url="https://google.com",
    )
    handler.handle_error(exc=exc, traceback=traceback)
