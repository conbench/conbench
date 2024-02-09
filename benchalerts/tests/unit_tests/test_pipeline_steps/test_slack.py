from traceback import format_exc
from typing import Optional

import pytest

from benchalerts import Alerter
from benchalerts.conbench_dataclasses import FullComparisonInfo
from benchalerts.pipeline_steps.slack import (
    SlackErrorHandler,
    SlackMessageAboutBadCheckStep,
)

from ..mocks import (
    MockResponse,
    MockSlackClient,
    check_posted_slack_message,
    response_dir,
)


class MockAlerter(Alerter):
    def slack_message(self, **kwargs) -> str:
        base_message = super().slack_message(**kwargs)
        return base_message + "\n\nThis message was generated from pytest."


CHECK_LINK = "<https://github.com/github/hello-world/runs/4|check link>"
COMMENT_LINK = (
    ", <https://github.com/octocat/Hello-World/issues/1347#issuecomment-1|comment link>"
)
MESSAGE_TEMPLATE = """
Check run posted with status `{status}`: {check_link}{comment_link}

This message was generated from pytest.
"""


@pytest.mark.parametrize(
    ["mock_comparison_info", "expected_status"],
    [
        ("errors_baselines", "action_required"),
        ("errors_nobaselines", "action_required"),
        ("noerrors_nobaselines", "skipped"),
        ("regressions", "failure"),
        ("noregressions", None),
        ("nocommit", None),
        ("noruns", "action_required"),
        ("noresults", "action_required"),
    ],
    indirect=["mock_comparison_info"],
)
@pytest.mark.parametrize("pr_comment_step_name", [None, "pr_comment_step"])
def test_SlackMessageAboutBadCheckStep(
    mock_comparison_info: FullComparisonInfo,
    expected_status: Optional[str],
    pr_comment_step_name: Optional[str],
    caplog: pytest.LogCaptureFixture,
    slack_env,
):
    """Test that SlackMessageAboutBadCheckStep posts the right message to Slack."""
    mock_check_response = MockResponse.from_file(
        response_dir / "POST_github_check-runs.json"
    ).json()
    mock_comment_response = MockResponse.from_file(
        response_dir / "POST_github_issues_1_comments.json"
    ).json()

    step = SlackMessageAboutBadCheckStep(
        channel_id="123",
        slack_client=MockSlackClient(),
        check_step_name="check_step",
        pr_comment_step_name=pr_comment_step_name,
        alerter=MockAlerter(),
    )
    res = step.run_step(
        {
            "check_step": (mock_check_response, mock_comparison_info),
            "pr_comment_step": mock_comment_response,
        }
    )
    if expected_status:
        assert res
        if pr_comment_step_name:
            expected_message = MESSAGE_TEMPLATE.format(
                status=expected_status, check_link=CHECK_LINK, comment_link=COMMENT_LINK
            )
        else:
            expected_message = MESSAGE_TEMPLATE.format(
                status=expected_status, check_link=CHECK_LINK, comment_link=""
            )
    else:
        assert not res
        expected_message = None
    check_posted_slack_message(caplog, expected_message)


@pytest.mark.parametrize("mock_comparison_info", ["regressions"], indirect=True)
def test_SlackMessageAboutBadCheckStep_no_comment(
    mock_comparison_info: FullComparisonInfo,
    caplog: pytest.LogCaptureFixture,
    slack_env,
):
    """Test that SlackMessageAboutBadCheckStep posts the right message to Slack."""
    mock_check_response = MockResponse.from_file(
        response_dir / "POST_github_check-runs.json"
    ).json()
    mock_comment_response = MockResponse.from_file(
        response_dir / "POST_github_issues_1_comments.json"
    ).json()

    class NoneAlerter(Alerter):
        def slack_message(self, **kwargs) -> str:
            return ""

    step = SlackMessageAboutBadCheckStep(
        channel_id="123",
        slack_client=MockSlackClient(),
        check_step_name="check_step",
        pr_comment_step_name="pr_comment_step",
        alerter=NoneAlerter(),
    )
    res = step.run_step(
        {
            "check_step": (mock_check_response, mock_comparison_info),
            "pr_comment_step": mock_comment_response,
        }
    )
    assert not res
    expected_message = None
    check_posted_slack_message(caplog, expected_message)


def test_SlackErrorHandler(caplog: pytest.LogCaptureFixture, slack_env):
    """Test that SlackErrorHandler posts the right message to Slack."""
    try:
        1 / 0
    except Exception as e:
        exc = e
        traceback = format_exc()

    handler = SlackErrorHandler(
        channel_id="123", slack_client=MockSlackClient(), build_url="https://google.com"
    )
    handler.handle_error(exc=exc, traceback=traceback)
    check_posted_slack_message(
        caplog, "Error in benchalerts pipeline. self.build_url='https://google.com'"
    )
