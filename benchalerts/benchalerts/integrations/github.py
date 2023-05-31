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

import datetime
import enum
import os
from typing import TYPE_CHECKING, Any, Dict, Optional

import jwt
from benchclients.base import BaseClient
from benchclients.logging import fatal_and_log, log

if TYPE_CHECKING:
    from requests.adapters import HTTPAdapter


class GitHubAppClient(BaseClient):
    """A client to interact with a GitHub App.

    Parameters
    ----------
    adapter
        A requests adapter to mount to the requests session. If not given, one will be
        created with a backoff retry strategy.

    Notes
    -----
    Environment variables
    ~~~~~~~~~~~~~~~~~~~~~
    GITHUB_APP_ID
        The numeric GitHub App ID you can get from its settings page.
    GITHUB_APP_PRIVATE_KEY
        The full contents of the private key file downloaded from the App's settings
        page.
    """

    def __init__(self, adapter: Optional["HTTPAdapter"] = None):
        app_id = os.getenv("GITHUB_APP_ID", "")
        if not app_id:
            fatal_and_log("Environment variable GITHUB_APP_ID not found")

        private_key = os.getenv("GITHUB_APP_PRIVATE_KEY", "")
        if not private_key:
            fatal_and_log("Environment variable GITHUB_APP_PRIVATE_KEY not found")

        super().__init__(adapter=adapter)
        encoded_jwt = self._encode_jwt(app_id=app_id, private_key=private_key)
        self.session.headers = {"Authorization": f"Bearer {encoded_jwt}"}
        self.base_url = "https://api.github.com/app"

    @staticmethod
    def _encode_jwt(app_id: str, private_key: str) -> str:
        """Create, sign, and encode a JSON web token to use for GitHub App endpoints."""
        payload = {
            "iss": app_id,
            "iat": datetime.datetime.utcnow() - datetime.timedelta(minutes=1),
            # https://docs.github.com/en/apps/creating-github-apps/authenticating-with-a-github-app/generating-a-json-web-token-jwt-for-a-github-app#about-json-web-tokens-jwts
            # According to the authenticator (GitHub) the JWT lifetime must be no more
            # than 10 minutes, but using exactly 10 minutes may be flaky due to system
            # clock disagreement (see https://github.com/conbench/conbench/issues/1101).
            # We only need this token briefly anyway.
            "exp": datetime.datetime.utcnow() + datetime.timedelta(minutes=3),
        }
        log.debug("Payload to encode for JWT: %s", str(payload))
        encoded_jwt = jwt.encode(payload=payload, key=private_key, algorithm="RS256")
        return encoded_jwt

    def get_app_access_token(self) -> str:
        """Authenticate as the GitHub App and generate an app installation access token.

        The token lasts for 1 hour, which should be plenty of time to do anything this
        package needs to do.

        Returns
        -------
        str
            A temporary API token to use for the GitHub API endpoints that the app has
            permission to access.
        """
        # We tell developers to create a new app for each organization, so they can
        # control the private key. So there should be exactly 1 installation here.
        # (Note: 1 installation could have multiple repos in the same organization.)
        installations = self.get("/installations")
        install_id = installations[0]["id"]

        token_info = self.post(f"/installations/{install_id}/access_tokens")
        return token_info["token"]


# used as inputs to some GitHubRepoClient methods
class CheckStatus(str, enum.Enum):
    # statuses
    QUEUED = "queued"
    IN_PROGRESS = "in_progress"
    # conclusions
    ACTION_REQUIRED = "action_required"
    CANCELLED = "cancelled"
    FAILURE = "failure"
    NEUTRAL = "neutral"
    SUCCESS = "success"
    SKIPPED = "skipped"
    TIMED_OUT = "timed_out"


class GitHubRepoClient(BaseClient):
    """A client to interact with a GitHub repo.

    You may authenticate with the GitHub API using a GitHub Personal Access Token or a
    GitHub App. The correct environment variables must be set depending on which method
    of authentication you're using. If all are set, the App method will be used.

    Parameters
    ----------
    repo
        The repo name, in the form 'owner/repo'.
    adapter
        A requests adapter to mount to the requests session. If not given, one will be
        created with a backoff retry strategy.

    Notes
    -----
    Environment variables
    ~~~~~~~~~~~~~~~~~~~~~
    GITHUB_APP_ID
        The numeric GitHub App ID you can get from its settings page. Only used for
        GitHub App authentication.
    GITHUB_APP_PRIVATE_KEY
        The full contents of the private key file downloaded from the App's settings
        page. Only used for GitHub App authentication.
    GITHUB_API_TOKEN
        A GitHub API token with ``repo`` access. Only used for Personal Access Token
        authentication.
    """

    def __init__(self, repo: str, adapter: Optional["HTTPAdapter"] = None):
        if os.getenv("GITHUB_APP_ID") or os.getenv("GITHUB_APP_PRIVATE_KEY"):
            log.info("Attempting to authenticate as a GitHub App.")
            app_client = GitHubAppClient(adapter=adapter)
            token = app_client.get_app_access_token()
            self._is_github_app_token = True
        else:
            token = os.getenv("GITHUB_API_TOKEN", "")
            if not token:
                fatal_and_log("Environment variable GITHUB_API_TOKEN not found.")
            self._is_github_app_token = False

        super().__init__(adapter=adapter)
        self.session.headers = {"Authorization": f"Bearer {token}"}
        self.base_url = f"https://api.github.com/repos/{repo}"

    def create_pull_request_comment(
        self,
        comment: str,
        *,
        pull_number: Optional[int] = None,
        commit_hash: Optional[str] = None,
    ):
        """Create a comment on a pull request, specified either by pull request number
        or commit hash.

        Parameters
        ----------
        comment
            The comment text.
        pull_number
            The number of the pull request. Specify either this or ``commit_hash``.
        commit_hash
            The hash of a commit associated with the pull request. Specify either this
            or ``pull_number``.
        """
        if not pull_number and not commit_hash:
            fatal_and_log("pull_number and commit_hash are both missing")

        if commit_hash:
            pull_numbers = [
                pull["number"] for pull in self.get(f"/commits/{commit_hash}/pulls")
            ]
            if len(pull_numbers) != 1:
                fatal_and_log(
                    "Need exactly 1 pull request associated with commit "
                    f"'{commit_hash}'. Found {pull_numbers}."
                )
            pull_number = pull_numbers[0]

        log.info(
            f"Posting the following message to pull request #{pull_number}:\n\n"
            + comment
        )
        return self.post(f"/issues/{pull_number}/comments", json={"body": comment})

    def update_check(
        self,
        name: str,
        commit_hash: str,
        status: CheckStatus,
        title: Optional[str] = None,
        summary: Optional[str] = None,
        details: Optional[str] = None,
        details_url: Optional[str] = None,
        external_id: Optional[str] = None,
    ):
        """Adds a new (or updates an existing) GitHub Check on a commit.

        A GitHub Check is a more fully-featured commit status, but you must be
        authenticated as a GitHub App to update checks. Subsequent uses of this method
        with the same ``name`` will overwrite the previous check.

        Parameters
        ----------
        name
            The name of the check. Subsequent updates with the same name will overwrite
            the previous check.
        commit_hash
            The 40-character hash of the commit to update.
        status
            The overall check status. Must be one of the CheckStatus enum values. If
            it's QUEUED or IN_PROGRESS, the "started_at" field will be sent in the
            payload with the current time in UTC. If it's another value, the
            "completed_at" field will be sent instead.
        title
            The short title of the check results. Default None. If supplied, summary
            must be supplied.
        summary
            A longer summary of the check results. Supports Markdown. Default None. If
            supplied, title must be supplied.
        details
            Details about the check results. Supports Markdown. Default None.
        details_url
            A URL to be linked to when clicking on check Details. Default None.
        external_id
            An optional reference to another system. Default None.

        Returns
        -------
        dict
            GitHub's details about the new status.
        """
        json: Dict[str, Any] = {"name": name, "head_sha": commit_hash}

        if status in [CheckStatus.QUEUED, CheckStatus.IN_PROGRESS]:
            json["status"] = status.value
            json["started_at"] = datetime.datetime.utcnow().isoformat() + "Z"
        elif isinstance(status, CheckStatus):
            json["conclusion"] = status.value
            json["completed_at"] = datetime.datetime.utcnow().isoformat() + "Z"
        else:
            fatal_and_log("status must be a CheckStatus", etype=TypeError)

        if title:
            json["output"] = {"title": title, "summary": summary}
            if details:
                json["output"]["text"] = details

        if details_url:
            json["details_url"] = details_url

        if external_id:
            json["external_id"] = external_id

        return self.post("/check-runs", json=json)
