import os

from benchclients.http import RetryingHTTPClient
from benchclients.logging import fatal_and_log


class SlackClient(RetryingHTTPClient):
    """A client to interact with Slack.

    This uses the token-based authentication method, not the Incoming Webhooks method.

    Notes
    -----
    Environment variables
    ~~~~~~~~~~~~~~~~~~~~~
    ``SLACK_TOKEN``
        A Slack token; see https://api.slack.com/authentication/token-types. Tokens look
        like ``xoxb-...`` if they're bot tokens.
    """

    default_retry_for_seconds = 60
    timeout_long_running_requests = (3.5, 10)

    def __init__(self) -> None:
        token = os.getenv("SLACK_TOKEN", "")
        if not token:
            fatal_and_log("Environment variable SLACK_TOKEN not found.")

        super().__init__()
        self.session.headers.update({"Authorization": f"Bearer {token}"})

    @property
    def _base_url(self) -> str:
        return "https://slack.com/api"

    def _login_or_raise(self) -> None:
        pass

    def post_message(self, channel_id: str, message: str) -> dict:
        """Post a message to a Slack channel.

        Parameters
        ----------
        channel_id
            The ID of the channel to post to.
        message
            The message text.

        Returns
        -------
        dict
            The response body from the Slack HTTP API as a dict.
        """
        resp_dict = self._make_request(
            "POST",
            self._abs_url_from_path("/chat.postMessage"),
            200,
            json={"channel": channel_id, "text": message},
        ).json()

        if not resp_dict.get("ok"):
            fatal_and_log(
                f"Failed to send message to Slack. Deserialized response body: {resp_dict}",
            )

        return resp_dict
