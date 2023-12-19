"""Pipeline steps to talk to Slack."""

from typing import Any, Dict, Optional

from benchclients.logging import log

from ..alert_pipeline import AlertPipelineErrorHandler, AlertPipelineStep
from ..integrations.github import CheckStatus
from ..integrations.slack import SlackClient
from ..message_formatting import Alerter


class SlackMessageAboutBadCheckStep(AlertPipelineStep):
    """An ``AlertPipeline`` step to post to Slack about a failing GitHub Check that was
    created by a previously-run ``GitHubCheckStep``. This is useful if you're running
    benchmarks on a merge-commit, and no one is necessarily monitoring the Checks on the
    default branch.

    Parameters
    ----------
    channel_id
        The ID of the Slack channel to post to.
    slack_client
        A SlackClient instance. If not provided, will default to ``SlackClient()``.
    check_step_name
        The name of the ``GitHubCheckStep`` that ran earlier in the pipeline. Defaults
        to "GitHubCheckStep" (which was the default if no name was given to that step).
    pr_comment_step_name
        [Optional] The name of the ``GitHubPRCommentStep`` that ran earlier in the
        pipeline. If provided, will include a link to the comment in the Slack message.
    step_name
        The name for this step. If not given, will default to this class's name.
    alerter
        Advanced usage; should not be necessary in most cases. An optional Alerter
        instance to use to format the message. If not provided, will default to
        ``Alerter()``.

    Returns
    -------
    dict
        The response body from the Slack HTTP API as a dict, or None if no message was
        posted (e.g. if the check was successful).

    Notes
    -----
    Environment variables
    ~~~~~~~~~~~~~~~~~~~~~
    ``SLACK_TOKEN``
        A Slack token; see https://api.slack.com/authentication/token-types. Tokens look
        like ``xoxb-...`` if they're bot tokens. Only required if ``slack_client`` is
        not provided.
    """

    def __init__(
        self,
        channel_id: str,
        slack_client: Optional[SlackClient] = None,
        check_step_name: str = "GitHubCheckStep",
        pr_comment_step_name: Optional[str] = None,
        step_name: Optional[str] = None,
        alerter: Optional[Alerter] = None,
    ) -> None:
        super().__init__(step_name=step_name)
        self.channel_id = channel_id
        self.slack_client = slack_client or SlackClient()
        self.check_step_name = check_step_name
        self.pr_comment_step_name = pr_comment_step_name
        self.alerter = alerter or Alerter()

    def run_step(self, previous_outputs: Dict[str, Any]) -> Optional[dict]:
        check_details, full_comparison = previous_outputs[self.check_step_name]
        if self.pr_comment_step_name:
            comment_details = previous_outputs[self.pr_comment_step_name]
        else:
            comment_details = None

        if self.alerter.github_check_status(full_comparison) == CheckStatus.SUCCESS:
            log.info("GitHub Check was successful; not posting to Slack.")
            return None

        res = self.slack_client.post_message(
            message=self.alerter.slack_message(
                full_comparison=full_comparison,
                check_details=check_details,
                comment_details=comment_details,
            ),
            channel_id=self.channel_id,
        )
        return res


class SlackErrorHandler(AlertPipelineErrorHandler):
    """Handle errors in a pipeline by posting a Slack message.

    Parameters
    ----------
    channel_id
        The ID of the Slack channel to post to.
    slack_client
        A SlackClient instance. If not provided, will default to ``SlackClient()``.
    build_url
        An optional build URL to include in the message.

    Notes
    -----
    Environment variables
    ~~~~~~~~~~~~~~~~~~~~~
    ``SLACK_TOKEN``
        A Slack token; see https://api.slack.com/authentication/token-types. Tokens look
        like ``xoxb-...`` if they're bot tokens. Only required if ``slack_client`` is
        not provided.
    """

    def __init__(
        self,
        channel_id: str,
        slack_client: Optional[SlackClient] = None,
        build_url: Optional[str] = None,
    ) -> None:
        self.channel_id = channel_id
        self.slack_client = slack_client or SlackClient()
        self.build_url = build_url

    def handle_error(self, exc: BaseException, traceback: str) -> None:
        res = self.slack_client.post_message(
            channel_id=self.channel_id,
            message=f"Error in benchalerts pipeline. {self.build_url=}",
        )
        log.debug(res)
