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
    def slack_message(
        self, full_comparison: FullComparisonInfo, check_details: dict
    ) -> str:
        base_message = super().slack_message(full_comparison, check_details)
        return base_message + "\n\nThis message was generated from pytest."


MESSAGE_TEMPLATE = """
Check run posted with status `{status}`: <https://github.com/github/hello-world/runs/4|link>

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
def test_SlackMessageAboutBadCheckStep(
    mock_comparison_info: FullComparisonInfo,
    expected_status: Optional[str],
    caplog: pytest.LogCaptureFixture,
    slack_env,
):
    """Test that SlackMessageAboutBadCheckStep posts the right message to Slack."""
    mock_check_response = MockResponse.from_file(
        response_dir / "POST_github_check-runs.json"
    ).json()

    step = SlackMessageAboutBadCheckStep(
        channel_id="123",
        slack_client=MockSlackClient(),
        check_step_name="check_step",
        alerter=MockAlerter(),
    )
    res = step.run_step({"check_step": (mock_check_response, mock_comparison_info)})
    if expected_status:
        assert res
        expected_message = MESSAGE_TEMPLATE.format(status=expected_status)
    else:
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
