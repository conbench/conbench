import pytest

from ..mocks import MockSlackClient


class TestSlackClient:
    @property
    def slack(self):
        return MockSlackClient()

    def test_post_message(self, slack_env):
        resp = self.slack.post_message(channel_id="123", message="hello")
        assert resp["ok"]

    def test_post_message_fails(self, slack_env):
        with pytest.raises(ValueError, match="Failed to send message"):
            self.slack.post_message(channel_id="fail", message="hello")

    def test_missing_token(self, slack_env_missing):
        with pytest.raises(ValueError, match="SLACK_TOKEN"):
            self.slack
