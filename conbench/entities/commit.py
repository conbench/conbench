import functools
import json
import logging
import os
import time
from datetime import datetime, timedelta
from typing import Dict, List, Optional

import flask as f
import requests
import sqlalchemy as s
from sqlalchemy.orm import Query

from conbench import util

from ..config import Config
from ..db import Session
from ..entities._entity import (
    Base,
    EntityMixin,
    EntitySerializer,
    NotNull,
    Nullable,
    generate_uuid,
)

log = logging.getLogger(__name__)


class CantFindAncestorCommitsError(Exception):
    pass


class Commit(Base, EntityMixin):
    __tablename__ = "commit"
    id = NotNull(s.String(50), primary_key=True, default=generate_uuid)
    sha = NotNull(s.String(50))
    branch = Nullable(s.String(510))
    fork_point_sha = Nullable(s.String(50))
    parent = Nullable(s.String(50))
    repository = NotNull(s.String(100))
    message = NotNull(s.String(250))
    author_name = NotNull(s.String(100))
    author_login = Nullable(s.String(50))
    author_avatar = Nullable(s.String(100))
    timestamp = Nullable(s.DateTime(timezone=False))

    def get_parent_commit(self):
        return Commit.first(sha=self.parent, repository=self.repository)

    def get_fork_point_commit(self) -> Optional["Commit"]:
        if self.sha == self.fork_point_sha:
            return self
        else:
            return Commit.first(sha=self.fork_point_sha, repository=self.repository)

    @property
    def commit_ancestry_query(self) -> Query:
        """Return a query that returns the IDs and timestamps of all Commits in the
        direct ancestry of this commit, all the way back to the initial commit. Also
        returns whether the commit is on the default branch, and an ordering column.

        This is mostly used as an unordered subquery; e.g.
        ``subquery = commit.commit_ancestry_query.subquery()``. You may take advantage
        of this subquery's ``commit_order`` column to order by lineage. For example,
        to order from this commit backwards in lineage to the inital commit (like the
        default behavior of ``git log``), you may use
        ``.order_by(subquery.c.commit_order.desc())`` or
        ``.order_by(sqlalchemy.desc("commit_order"))``.

        For example, consider the following git graph, where more recent commits are
        near the top:

        G      (main)
        |  E2  (rebased branch)
        |  C2
        | /
        |/
        F
        |  E   (branch)
        D  |
        |  C
        | /
        |/
        B
        A

        Ordering by commit_order.desc(), the following commits would return the
        following ordered ancestors:

        A  :  A
        B  :  B, A
        C  :  C, B, A
        D  :  D, B, A
        E  :  E, C, B, A
        F  :  F, D, B, A
        C2 :  C2, F, D, B, A
        E2 :  E2, C2, F, D, B, A
        G  :  G, F, D, B, A

        Might raise CantFindAncestorCommitsError.
        """
        if not self.branch:
            raise CantFindAncestorCommitsError("commit branch is null")
        if not self.timestamp:
            raise CantFindAncestorCommitsError("commit timestamp is null")
        if not self.fork_point_sha:
            raise CantFindAncestorCommitsError("commit fork_point_sha is null")

        fork_point_commit = self.get_fork_point_commit()
        if not fork_point_commit:
            raise CantFindAncestorCommitsError("the fork point commit isn't in the db")
        if not fork_point_commit.timestamp:
            raise CantFindAncestorCommitsError("fork_point_commit timestamp is null")

        # Get default branch commits before/including the fork point
        query = Session.query(
            Commit.id.label("ancestor_id"),
            Commit.timestamp.label("ancestor_timestamp"),
            s.sql.expression.literal(True).label("on_default_branch"),
            s.func.concat("1_", Commit.timestamp).label("commit_order"),
        ).filter(
            Commit.repository == self.repository,
            Commit.sha == Commit.fork_point_sha,  # aka: on default branch
            Commit.timestamp <= fork_point_commit.timestamp,
        )

        # If this commit is on a non-default branch, add all commits since the fork point
        if self != fork_point_commit:
            branch_query = Session.query(
                Commit.id.label("ancestor_id"),
                Commit.timestamp.label("ancestor_timestamp"),
                s.sql.expression.literal(False).label("on_default_branch"),
                s.func.concat("2_", Commit.timestamp).label("commit_order"),
            ).filter(
                Commit.repository == self.repository,
                Commit.branch == self.branch,
                Commit.fork_point_sha == self.fork_point_sha,
                Commit.timestamp <= self.timestamp,
            )
            query = query.union(branch_query)

        return query

    @staticmethod
    def create_no_context():
        commit = Commit.first(sha="", repository="")
        if not commit:
            commit = Commit.create(
                {
                    "sha": "",
                    "repository": "",
                    "parent": None,
                    "timestamp": None,
                    "message": "",
                    "author_name": "",
                }
            )
        return commit

    @staticmethod
    def create_unknown_context(sha, repository):
        return Commit.create(
            {
                "sha": sha,
                "repository": repository,
                "parent": None,
                "timestamp": None,
                "message": "",
                "author_name": "",
            }
        )

    @staticmethod
    def create_github_context(sha, repository: str, github: dict):
        return Commit.create(
            {
                "sha": sha,
                "branch": github["branch"],
                "fork_point_sha": github["fork_point_sha"],
                "repository": repository,
                "parent": github["parent"],
                "timestamp": github["date"],
                "message": github["message"],
                "author_name": github["author_name"],
                "author_login": github["author_login"],
                "author_avatar": github["author_avatar"],
            }
        )


# NB: this assumes only one branch will be associated with a SHA when posting to
# Conbench. Subsequent posts with the same SHA on a new branch will fail.
# That should be impossible with a "normal" CI setup, and only possible if people post
# manually outside of CI.
#
# We impose this limitation here to make history queries easier to manage.
s.Index(
    "commit_index",
    Commit.sha,
    Commit.repository,
    unique=True,
)


class _Serializer(EntitySerializer):
    def _dump(self, commit):
        url = None
        if commit.repository and commit.sha:
            url = f"{commit.repository}/commit/{commit.sha}"
        timestamp = commit.timestamp.isoformat() if commit.timestamp else None
        result = {
            "id": commit.id,
            "sha": commit.sha,
            "branch": commit.branch,
            "fork_point_sha": commit.fork_point_sha,
            "url": url,
            "parent_sha": commit.parent,
            "repository": commit.repository,
            "message": commit.message,
            "author_name": commit.author_name,
            "author_login": commit.author_login,
            "author_avatar": commit.author_avatar,
            "timestamp": timestamp,
            "links": {
                "list": f.url_for("api.commits", _external=True),
                "self": f.url_for("api.commit", commit_id=commit.id, _external=True),
            },
        }
        if not self.many:
            parent, parent_url = commit.get_parent_commit(), None
            if parent:
                parent_url = f.url_for(
                    "api.commit", commit_id=parent.id, _external=True
                )
            result["links"]["parent"] = parent_url
        return result


class CommitSerializer:
    one = _Serializer()
    many = _Serializer(many=True)


GITHUB = "https://api.github.com"
this_dir = os.path.abspath(os.path.dirname(__file__))


def repository_to_name(repository):
    if not repository:
        return ""
    name = repository
    if "github.com/" in repository:
        name = repository.split("github.com/")[1]
    elif "git@github.com:" in repository:
        name = repository.split("git@github.com:")[1]
    return name


def repository_to_url(repository):
    name = repository_to_name(repository)
    return f"https://github.com/{name.lower()}" if name else ""


def get_github_commit(repository: str, pr_number: str, branch: str, sha: str) -> dict:
    """
    This function interacts with the GitHub HTTP API. Exceptions related to API
    interaction errors are not handled here (and should be expected and handled
    in the caller). Expected error sources are among the following :

    - transient issues on DNS or TCP level
    - transient HTTP errors such as 5xx
    - transient but permanent-ish HTTP errors such as rate limiting
    - HTTP authentication/authorization errors
    - permanent error responses

    If this is free of bugs then all expected exceptions should derive from
    requests.exceptions.RequestException.

    """
    if not repository or not sha:
        return {}

    github = GitHub()
    name = repository_to_name(repository)

    # `github.get_commit()` below may raise an exception if the GitHub
    # GitHub HTTP API failed, e.g. with a 4xx rate limiting response.
    commit = github.get_commit(name, sha)

    if branch:
        commit["branch"] = branch
    elif pr_number:
        commit["branch"] = github.get_branch_from_pr_number(
            name=name, pr_number=pr_number
        )
    else:
        commit["branch"] = github.get_default_branch(name=name)

    commit["fork_point_sha"] = github.get_fork_point_sha(name=name, sha=sha)

    return commit


def backfill_default_branch_commits(repourl: str, new_commit: Commit) -> None:
    """Catches up the default-branch commits in the database.

    Will search GitHub for any untracked commits, between the given new_commit back in
    time to the last tracked commit, and backfill all of them.

    Won't backfill any commits before the last tracked commit. But if there are no
    commits in the database, will backfill them all.

    This may raise exceptions as of HTTP request/response cycle errors during
    GitHub HTTP API interaction.
    """

    github = GitHub()

    # `repourl` is expected to be a URL pointing to a GitHub repositopry. It
    # must be of the shape "https://github.com/org/repo". `repospec` then is
    # unambiguously specifying the same GitHub repository using the canonical
    # "org/repo" notation.
    repospec = repository_to_name(repourl)

    # This triggers one HTTP request.
    default_branch = github.get_default_branch(repospec)

    last_tracked_commit = Commit.all(
        filter_args=[Commit.sha != new_commit.sha, Commit.timestamp.isnot(None)],
        branch=default_branch,
        repository=repourl,
        order_by=Commit.timestamp.desc(),
        limit=1,
    )

    if last_tracked_commit:
        since = last_tracked_commit[0].timestamp

    elif Config.TESTING and "apache/arrow" in repourl:
        # Also see https://github.com/conbench/conbench/issues/637.
        log.info(
            "backfill_default_branch_commits(): apache/arrow and "
            "Config.TESTING. Backfill commits only from the last 60 days "
            "in order to reduce duration & API quota usage."
        )
        since = datetime.today() - timedelta(days=60)

    else:
        # Fetch commits since beginning of time
        since = datetime(1970, 1, 1)

    # This triggers potentially many HTTP requests to the GitHub HTTP API.
    # May raise exceptions as of HTTP request/response cycle errors.
    commits = github.get_commits_to_branch(
        name=repospec,
        branch=default_branch,
        since=since,
        until=new_commit.timestamp,
    )
    commits_to_try = commits[1:-1]  # since/until are inclusive; we want exclusive

    log.info(f"Backfilling {len(commits_to_try)} commit(s)")
    if commits_to_try:
        Commit.upsert_do_nothing(
            [
                {
                    "sha": commit_info["sha"],
                    "branch": default_branch,
                    "fork_point_sha": commit_info["sha"],
                    "repository": commit_info["repository"],
                    "parent": commit_info["github"]["parent"],
                    "timestamp": commit_info["github"]["date"],
                    "message": commit_info["github"]["message"],
                    "author_name": commit_info["github"]["author_name"],
                    "author_login": commit_info["github"]["author_login"],
                    "author_avatar": commit_info["github"]["author_avatar"],
                }
                for commit_info in commits_to_try
            ]
        )


class GitHub:
    def __init__(self):
        self.test_shas = {
            "02addad336ba19a654f9c857ede546331be7b631": "github_child.json",
            "4beb514d071c9beec69b8917b5265e77ade22fb3": "github_parent.json",
            "6d703c4c7b15be630af48d5e9ef61628751674b2": "github_grandparent.json",
            "81e9417eb68171e03a304097ae86e1fd83307130": "github_elder.json",
        }
        self.test_commits = [
            "02addad336ba19a654f9c857ede546331be7b631",
            "4beb514d071c9beec69b8917b5265e77ade22fb3",
            "6d703c4c7b15be630af48d5e9ef61628751674b2",
            "81e9417eb68171e03a304097ae86e1fd83307130",
            "4de992c60ba433ad9b15ca1c41e6ec40bc542c2a",
            "unknown commit",
            "testing repository with just org/repo",
            "testing repository with git@g",
        ]

    def get_default_branch(self, name):
        if name == "org/repo":
            # test case
            return "org:default_branch"

        url = f"{GITHUB}/repos/{name}"
        response = self._get_response(url)
        if not response:
            return None

        if response["fork"]:
            org = response["source"]["owner"]["login"]
            branch = response["source"]["default_branch"]
        else:
            org = response["owner"]["login"]
            branch = response["default_branch"]

        return f"{org}:{branch}"

    def get_commit(self, name, sha):
        # Pragmatic method for testing.
        if sha in self.test_commits:
            return self._parse_commit(self._mocked_get_response(sha))

        url = f"{GITHUB}/repos/{name}/commits/{sha}"

        # _get_response() may raise an exception, for example if the GH
        # HTTP API returned a non-2xx HTTP response (e.g. in case of rate
        # limiting).
        return self._parse_commit(self._get_response(url))

    def get_commits_to_branch(
        self, name: str, branch: str, since: datetime, until: datetime
    ) -> List[dict]:
        """Get information about each commit on a given branch.

        since and until are inclusive.

        `name` is the GitHub repository specifier in org/repo notation.

        Expect tz-naive datetime objects, or expect tz-aware objects with UTC
        timezone.
        """
        assert "/" in name

        if name == "org/repo":
            # test case
            return []

        if ":" in branch:
            branch = branch.split(":")[1]

        since_iso_for_url = since.replace(tzinfo=None).isoformat() + "Z"
        until_iso_for_url = until.replace(tzinfo=None).isoformat() + "Z"
        del since, until

        log.info(
            f"Finding all commits to the {branch} branch of {name} between "
            f" {since_iso_for_url} and {until_iso_for_url}"
        )
        url = (
            f"{GITHUB}/repos/{name}/commits?per_page=100&sha={branch}"
            f"&since={since_iso_for_url}&until={until_iso_for_url}"
        )
        commits: List[Dict] = []
        page = 1

        # This may raise exceptions as of HTTP request/response cycle errors.
        this_page = self._get_response(url + f"&page={page}")

        if len(this_page) == 0:
            log.info("API returned no commits")
            return []

        commits += this_page

        while len(this_page) == 100:
            page += 1
            this_page = self._get_response(url + f"&page={page}")
            commits += this_page

        return [
            {
                "sha": commit["sha"],
                "repository": repository_to_url(name),
                "github": self._parse_commit(commit),
            }
            for commit in commits
        ]

    def get_fork_point_sha(self, name: str, sha: str) -> Optional[str]:
        """
        Get the most common ancestor commit between an arbitrary SHA and the default
        branch.

        Returns ``None`` if sha is not supplied or if GitHub can't find it, otherwise
        returns the fork point sha, called the "merge base" in git-speak.
        """
        if sha in self.test_commits:
            # they're on the default branch, so sha==fork_point_sha
            return sha

        if not name or not sha:
            return None

        base = self.get_default_branch(name=name)
        url = f"{GITHUB}/repos/{name}/compare/{base}...{sha}"
        response = self._get_response(url=url)
        if not response:
            return None

        fork_point_sha = response["merge_base_commit"]["sha"]
        return fork_point_sha

    def get_branch_from_pr_number(self, name: str, pr_number: str) -> Optional[str]:
        if pr_number == 12345678:
            # test case
            return "some_user_or_org:some_branch"

        if not name or not pr_number:
            return None

        url = f"{GITHUB}/repos/{name}/pulls/{pr_number}"
        response = self._get_response(url=url)
        if not response:
            return None

        branch = response["head"]["label"]
        return branch

    @functools.cached_property
    def session(self):
        token, session = os.getenv("GITHUB_API_TOKEN"), None
        if token:
            session = requests.Session()
            session.headers = {"Authorization": f"Bearer {token}"}
        return session

    def _mocked_get_response(self, sha) -> dict:
        """
        Note(JP): this function performed magic before and I am trying to write
        a docstring now. Maybe: load commit information from disk, if
        available. Otherwise, if the commit hash `sha` contains the magic words
        'unknown' or 'testing' then pretend as if fetching these from the
        GitHub HTTP API failed, and raise an exception simimar to _get_response
        would do.
        """

        if "unknown" in sha or "testing" in sha:
            raise Exception("_mocked_get_response(): simulate _get_response() error")

        path = os.path.join(this_dir, f"../tests/entities/{self.test_shas[sha]}")
        with open(path) as f:
            return json.load(f)

    @staticmethod
    def _parse_commits(commits):
        return [commit["sha"] for commit in commits]

    @staticmethod
    def _parse_commit(commit):
        author = commit.get("author")
        commit_author = commit["commit"]["author"]

        return {
            "parent": commit["parents"][0]["sha"] if commit["parents"] else None,
            # Note: `commit_author["date"]` here is expected to be an ISO 8601
            # timestring as returned by the GitHub HTTP API and that is
            # tz-aware (Zulu time, UTC).
            "date": util.tznaive_iso8601_to_tzaware_dt(commit_author["date"]),
            # Note(JP): don't we want to indicate if the msg was truncated,
            # with e.g. an ellipsis?
            "message": commit["commit"]["message"].split("\n")[0][:240],
            "author_name": commit_author["name"],
            "author_login": author["login"] if author else None,
            "author_avatar": author["avatar_url"] if author else None,
        }

    def _get_response(self, url) -> dict:
        """Attempt to get HTTP response with retrying behavior towards a
        best-effort approach in view of typical retryable errors.

        Do not try for too long because there is an HTTP client waiting for
        _us_ to generate an HTTP response in a more or less timely fashion.
        Gunicorn has a worker timeout behavior (as of the time of writing: 120
        seconds) and the retrying method below must come to a conclusion before
        that.

        Return deserialized JSON-structure or raise an exception.
        """
        timeout_seconds = 20

        t0 = time.monotonic()
        deadline = t0 + timeout_seconds
        attempt: int = 0

        while time.monotonic() < deadline:
            attempt += 1

            result = self._get_response_retrycore(url)

            if result is not None:
                return result

            # The first retry attempt comes quick, then there is slow exp
            # growth, and a max: 0.66, 1.33, 2.66, 5.33, 5.5, 5.5, ...
            wait_seconds = min((2**attempt) / 3.0, 5.5)
            log.info(f"attempt {attempt} failed, wait for {wait_seconds:.3f} s")

            # Would the next wait exceed the deadline? This is an optimization.
            if (time.monotonic() + wait_seconds) > deadline:
                break

            # Note that this blocks the current executor (gunicorn process, at
            # the time of writing) from processing other incoming HTTP
            # requests.
            time.sleep(wait_seconds)

        raise Exception(
            f"_get_response(): deadline exceeded, giving up after {time.monotonic()-t0:.3f} s"
        )

    def _get_response_retrycore(self, url) -> Optional[dict]:
        """
        Return deserialized JSON-structure or raise an exception or return
        `None` which indicates a retryable error.
        """

        try:
            # This next line can raise exceptions corresponding to transient
            # issues related to DNS, TCP, HTTP during sending request, while
            # waiting for response, or while receiving the response. `requests`
            # has a little bit of retrying built-in by default for some of
            # these errors, but it's not trying too hard. Add more retrying
            # on top of that.
            resp = self.session.get(url) if self.session else requests.get(url)
        except requests.exceptions.RequestException as exc:
            log.info(
                "error during HTTP request/response cycle: %s --  "
                "assume that it's retryable, retry soon.",
                exc,
            )
            return None

        # In the code block below `resp` reflects an actual HTTP response.
        if resp.status_code == 200:
            # This may raise an exception if JSON-deserialization fails. If
            # JSON deser succeeds then this is known to be a dict at the outest
            # level.
            return resp.json()

        # Log code and body prefix: important for debuggability.
        log.info(
            "got unexpected HTTP response with code %s: %s",
            resp.status_code,
            resp.text[:1000],
        )

        if resp.status_code == 403:
            log.info(
                "x-ratelimit headers: %s",
                ", ".join(
                    f"{k}: {v}"
                    for k, v in resp.headers.items()
                    if "x-ratelimit" in k.lower()
                ),
            )

            if int(resp.headers.get("x-ratelimit-remaining", 0)) > 100:
                log.info("quota not exhausted, try to retry soon")
                # Add additional wait time, because this seems to be a legit
                # HTTP request rate limiting error -- we have to seriously back
                # off if we want to have success. The wait time in the
                # _get_response() loop is too short.
                time.sleep(2)
                return None

            raise Exception("Hourly GitHub HTTP API quota exhausted")

        # For the rare occasion where the GitHub HTTP API returns a 5xx
        # response we certainly want to retry immediately.
        if str(resp.status_code).startswith("5"):
            return None

        raise Exception(
            f"Unexpected GitHub HTTP API response: {resp}",
        )
