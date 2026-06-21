import datetime
import logging
import os
from typing import Dict, List, Optional

import requests


GITHUB = "https://api.github.com"
log = logging.getLogger(__name__)


def repository_to_name(repository: str) -> str:
    if not repository:
        return ""
    if "github.com/" in repository:
        return repository.split("github.com/")[1]
    if "git@github.com:" in repository:
        return repository.split("git@github.com:")[1]
    return repository


def repository_to_url(repository: str) -> str:
    name = repository_to_name(repository)
    if not name:
        return ""
    if name.startswith("http"):
        return name
    return f"https://github.com/{name}"


def parse_github_datetime(value: str) -> datetime.datetime:
    parsed = datetime.datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=datetime.timezone.utc)
    return parsed.astimezone(datetime.timezone.utc)


class GitHubHTTPAPIClient:
    def __init__(self) -> None:
        self.auth_header: Optional[Dict[str, str]] = None
        for token in os.environ.get("GITHUB_API_TOKEN", "").split(","):
            token = token.strip()
            if 5 <= len(token) <= 130:
                self.auth_header = {"Authorization": f"Bearer {token}"}
                break

    def get_default_branch(self, name: str) -> Optional[str]:
        if name == "org/repo":
            return "org:default_branch"

        response = self._get_response(f"{GITHUB}/repos/{name}")
        if not response:
            return None

        if response["fork"]:
            org = response["source"]["owner"]["login"]
            branch = response["source"]["default_branch"]
        else:
            org = response["owner"]["login"]
            branch = response["default_branch"]
        return f"{org}:{branch}"

    def get_commit(self, name: str, sha: str) -> Optional[dict]:
        if not name or not sha:
            return None
        return self._parse_commit(
            self._get_response(f"{GITHUB}/repos/{name}/commits/{sha}")
        )

    def get_commits_to_branch(
        self,
        name: str,
        branch: str,
        since: datetime.datetime,
        until: datetime.datetime,
    ) -> List[dict]:
        if name == "org/repo":
            return []
        if ":" in branch:
            branch = branch.split(":", 1)[1]

        since_iso = since.replace(tzinfo=None).isoformat() + "Z"
        until_iso = until.replace(tzinfo=None).isoformat() + "Z"
        url = (
            f"{GITHUB}/repos/{name}/commits?per_page=100&sha={branch}"
            f"&since={since_iso}&until={until_iso}"
        )

        commits: List[dict] = []
        page = 1
        while True:
            this_page = self._get_response(url + f"&page={page}")
            if not this_page:
                break
            commits.extend(this_page)
            if len(this_page) < 100:
                break
            page += 1

        return [
            {
                "sha": commit["sha"],
                "repository": repository_to_url(name),
                "github": self._parse_commit(commit),
            }
            for commit in commits
        ]

    def get_fork_point_sha(self, name: str, sha: str) -> Optional[str]:
        if not name or not sha:
            return None
        base = self.get_default_branch(name)
        if not base:
            return None
        response = self._get_response(f"{GITHUB}/repos/{name}/compare/{base}...{sha}")
        if not response:
            return None
        return response["merge_base_commit"]["sha"]

    def _get_response(self, url: str) -> dict:
        log.info("fetching GitHub metadata from %s", url)
        response = requests.get(url, headers=self.auth_header, timeout=20)
        if response.status_code != 200:
            raise RuntimeError(
                "Unexpected GitHub HTTP API response for URL "
                f"{url}: {response}. Leading bytes of body: "
                f"'{response.text[:150]} ...'"
            )
        return response.json()

    @staticmethod
    def _parse_commit(commit: dict) -> dict:
        author = commit.get("author")
        commit_author = commit["commit"]["author"]
        return {
            "parent": commit["parents"][0]["sha"] if commit["parents"] else None,
            "date": parse_github_datetime(commit_author["date"]),
            "message": commit["commit"]["message"].split("\n")[0][:240],
            "author_name": commit_author["name"],
            "author_login": author["login"] if author else None,
            "author_avatar": author["avatar_url"] if author else None,
        }
