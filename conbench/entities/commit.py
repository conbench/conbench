import itertools
import json
import logging
import os
import threading
import time
from datetime import datetime, timedelta
from typing import Dict, List, Optional

import flask as f
import requests
import sqlalchemy as s
from sqlalchemy.orm import Mapped, Query

from conbench import metrics, util

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


# Used for keeping track of the per-request count of GitHub HTTP API
# authentication token rotations. Must be mutated from / locked to precisely
# one HTTP request handler. That's guaranteed as long as we use gunicorn's
# process worker. If we were to transition to thread workers, this should be a
# threadlocal. Prepare for that (there is no downside attached).
_tloc = threading.local()


class Commit(Base, EntityMixin):
    __tablename__ = "commit"
    id: Mapped[str] = NotNull(s.String(50), primary_key=True, default=generate_uuid)
    sha: Mapped[str] = NotNull(s.String(50))
    branch: Mapped[Optional[str]] = Nullable(s.String(510))
    fork_point_sha: Mapped[Optional[str]] = Nullable(s.String(50))

    # Note(JP): this is supposed to be the commit hash of the parent commit.
    # Need to make the naming nicer, and I also believe we want to manage
    # that parent/child relationship better?
    parent: Mapped[Optional[str]] = Nullable(s.String(50))

    # This is meant to be the URL to the repository without trailing slash.
    # Should be renamed to repo_url
    repository: Mapped[str] = NotNull(s.String(300))
    message: Mapped[str] = NotNull(s.String(250))
    author_name: Mapped[str] = NotNull(s.String(100))
    author_login: Mapped[Optional[str]] = Nullable(s.String(50))

    # I think this is guaranteed to be a URL. Is it?
    author_avatar: Mapped[Optional[str]] = Nullable(s.String(100))
    # Note(JP): tz-naive datetime, git commit author date, in UTC.
    # Edit: adding the type Optional[datetime] is not sufficient because
    # further down we use `.label()` which seems to be sqlalchemy-specific
    timestamp: Mapped[Optional[datetime]] = Nullable(s.DateTime(timezone=False))

    def get_parent_commit(self):
        # Hm -- should this not be done with a foreign key relationship?
        return Commit.first(sha=self.parent, repository=self.repository)

    def get_fork_point_commit(self) -> Optional["Commit"]:
        if self.sha == self.fork_point_sha:
            return self
        else:
            return Commit.first(sha=self.fork_point_sha, repository=self.repository)

    @property
    def repo_url(self) -> Optional[str]:
        """
        Return a URL string or None. The returned string is guaranteed to start
        with 'http' and is guanrateed to not have a trailing slash.

        The `None` case is here because I think the database may contain emtpy
        strings.
        """
        u = self.repository
        if u.startswith("http"):
            # Remove trailing slash(es), if applicable.
            return u.rstrip("/")

        return None

    @property
    def commit_url(self) -> Optional[str]:
        """
        Return a URL string pointing to the commit, or None. The returned
        string is guaranteed to start with 'http' and is guanrateed to not have
        a trailing slash.

        The `None` case is here because I think the database may contain emtpy
        strings.

        The URL path construction via /commit/{hash} is as of today
        GitHub-specific. Therefore, there may be cases where the URL is
        invalid (when the base URL does not point got GitHub)
        """
        u = self.repository
        if u.startswith("http"):
            # Remove trailing slash(es) from base URL, if applicable. Ideally
            # this kind of normalization happens before DB insertion.
            return u.rstrip("/") + f"/commit/{self.hash}"

        return None

    @property
    def hash(self) -> str:
        """
        The full-length commit hash.

        This is here for naming and documentation purposes.
        """
        return self.sha

    @property
    def author_avatar_url(self) -> Optional[str]:
        """
        Return a URL string or None.

        The returned string is guaranteed to start with 'http' and is
        guanrateed to not have a trailing slash.
        """
        u = self.author_avatar
        if u and u.startswith("http"):
            # Remove trailing slash(es), if applicable.
            return u.rstrip("/")

        return None

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
            s.sql.expression.literal(True, s.Boolean).label("on_default_branch"),
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
                s.sql.expression.literal(False, s.Boolean).label("on_default_branch"),
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
        # Special commit row, a singleton that call results can relate to (in
        # DB, via forgeign key) that have _no_ commit information set. But: is
        # that needed? Why have that relation at all then?
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
    def create_unknown_context(hash: str, repo_url: str) -> "Commit":
        # Note(JP): I think this means "could not verify, could not get further
        # info from remote API" -- but we _do_ have a commit hash, and a
        # repository URL specifier -- insert that into the database. Also see
        # https://github.com/conbench/conbench/issues/817
        assert hash is not None
        assert len(hash)
        assert repo_url.startswith("http")

        return Commit.create(
            {
                "sha": hash,
                "repository": repo_url,
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


def repository_to_name(repository: str) -> str:
    """
    Normalize user-given repository information into an org/repo notation.

    (I try to document this in hindsight)

    Expected input variants:

    Guaranteed to return a string.

    If the input string is a URL that is independent of github then the return
    value is still a URL.
    """
    if not repository:
        return ""

    name = repository
    if "github.com/" in repository:
        name = repository.split("github.com/")[1]
    elif "git@github.com:" in repository:
        name = repository.split("git@github.com:")[1]
    return name


def repository_to_url(repository: str) -> str:
    """
    Warning: this may return an emtpy string, output is not guaranteed to be
    a URL.
    """
    name = repository_to_name(repository)

    if not name:
        # What is this needed for? With this, Commit.repository can be set to
        # be an empty string, I think.
        return ""

    # Note(JP): `name` may still be a URL. In that case, return this.
    if name.startswith("http"):
        return name

    # Now that we're seemingly generating a github.com-specific URL, we should
    # make sure that `name` appears to be in org/repo notation, i.e. contains
    # a slash.
    if "/" not in name:
        log.warning(
            "repository_to_url() about to create invalid URL, name is: %s", name
        )

    # Note(JP): the `lower()` appears to be dangerous. URLs are case-sensitive.
    # We should trust user-given input in that regard, or at least think this
    # through a little further. Also see
    # https://github.com/conbench/conbench/issues/818
    return f"https://github.com/{name.lower()}"


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

    name = repository_to_name(repository)

    # `github.get_commit()` below may raise an exception if the GitHub
    # GitHub HTTP API failed, e.g. with a 4xx rate limiting response.
    commit = _github.get_commit(name, sha)

    if branch:
        commit["branch"] = branch
    elif pr_number:
        commit["branch"] = _github.get_branch_from_pr_number(
            name=name, pr_number=pr_number
        )
    else:
        commit["branch"] = _github.get_default_branch(name=name)

    commit["fork_point_sha"] = _github.get_fork_point_sha(name=name, sha=sha)

    return commit


def backfill_default_branch_commits(repo_url: str, new_commit: Commit) -> None:
    """Catches up the default-branch commits in the database.

    Will search GitHub for any untracked commits, between the given new_commit back in
    time to the last tracked commit, and backfill all of them.

    Won't backfill any commits before the last tracked commit. But if there are no
    commits in the database, will backfill them all.

    This may raise exceptions as of HTTP request/response cycle errors during
    GitHub HTTP API interaction.
    """
    if new_commit.timestamp is None:
        # This would be a no-op
        return

    # Note(JP): the way I read the code I think that `repo_url` is expected to
    # be a URL pointing to a GitHub repositopry. It must be of the shape
    # "https://github.com/org/repo". `repospec` then is unambiguously
    # specifying the same GitHub repository using the canonical "org/repo"
    # notation.
    repospec = repository_to_name(repo_url)

    # This triggers one HTTP request.
    default_branch = _github.get_default_branch(repospec)

    last_tracked_commit = Commit.all(
        filter_args=[Commit.sha != new_commit.sha, Commit.timestamp.isnot(None)],
        branch=default_branch,
        repository=repo_url,
        order_by=Commit.timestamp.desc(),
        limit=1,
    )

    if last_tracked_commit:
        since = last_tracked_commit[0].timestamp
        if since is None:
            # This would be a no-op
            return

    elif Config.TESTING and "apache/arrow" in repo_url:
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
    commits = _github.get_commits_to_branch(
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


class GitHubHTTPApiClient:
    """
    An instance of this class is meant to be used in a per-process
    singleton-fashion for doing GitHub HTTP API client interaction.
    """

    def __init__(self) -> None:
        self._read_auth_tokens_from_env()

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

    def _read_auth_tokens_from_env(self) -> None:
        """
        This reads GITHUB_API_TOKEN, initializes a cycling iterator (if more
        than one token was provided), and always populates

        self._token_pool (None, or pool of size greater 1)
        self._token_pool_size (int size)
        self._current_auth_token (empty string, or with a token).

        When reading GitHub API token(s) from environment: support two formats:
        one token, or more than one token (comma-separated)
        """

        data = os.getenv("GITHUB_API_TOKEN")
        self._token_pool: Optional[itertools.cycle[str]] = None
        self._token_pool_size: int = 0

        # Convention: empty string means: not set
        self._current_auth_token: str = ""

        if data is None:
            log.info("GITHUB_API_TOKEN env not set")
            return

        log.info("GITHUB_API_TOKEN env is set, length of data: %s", len(data))

        token_candidates = data.split(",")

        tokens_to_use: List[str] = []
        for tc in token_candidates:
            # Remove leading and trailing whitespace.
            t = tc.strip()
            # Sanity-check the length. The fine-grained personal tokens
            # seemingly have a length smaller 100, but don't try to be precise
            # here.
            if len(t) < 5 or len(t) > 130:
                log.info("unexpected token length, ignore: %s", len(t))
            else:
                tokens_to_use.append(t)

        if len(tokens_to_use) == 0:
            #
            return

        if len(tokens_to_use) == 1:
            self._current_auth_token = tokens_to_use[0]
            log.info("configured a single GitHub HTTP API auth token")
            return

        # This is the only place where self._token_pool is set to a non-None
        # value.
        self._token_pool = itertools.cycle(tokens_to_use)
        self._token_pool_size = len(tokens_to_use)
        log.info(
            "configured GitHub HTTP API authentication token pool: %s",
            ", ".join(f"{ttu[:6]}..." for ttu in tokens_to_use),
        )
        self._rotate_auth_token()

    def _rotate_auth_token(self):
        """
        Return True if token was rotated, False otherwise.
        """
        if self._token_pool is None:
            # convention: pool size greater than 1, rotation takes effect.
            log.debug("tried rotating auth token, but no pool is configured")
            return False

        self._current_auth_token = next(self._token_pool)
        # Fine-grained personal access tokens are prefixed with `github_pat_``
        # Personal access tokens (classic) have the prefix `ghp_`
        tpfx = self._current_auth_token[:6]
        if self._current_auth_token.startswith("github_pat_"):
            tpfx = self._current_auth_token[:14]

        log.info(
            "current auth token has length %s and starts with: %s",
            len(self._current_auth_token),
            tpfx,
        )
        return True

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
            # Note(JP): `commit_author["date"]` represents the time when the
            # commit was authored (when it was originally made on the developer
            # machine). This time never changes. git also knows the concept of
            # the commit date which is updated every time the commit is
            # modified; for example when rebasing or cherry-picking. We don't
            # consider this here. `commit_author["date"]` is expected to be an
            # ISO 8601 timestring as returned by the GitHub HTTP API and that
            # is tz-aware (Zulu time, UTC).
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

        # (re)set this to be zero before starting into the retry loop. This
        # thread-local variable is mutated from within
        # `_get_response_retry_guts()`. Cannot trivially set type to int, see
        # https://github.com/python/mypy/issues/2388
        _tloc.auth_token_rotations = 0

        while time.monotonic() < deadline:
            attempt += 1

            result = self._get_response_retry_guts(url)

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

        # Give up after retrying.
        metrics.COUNTER_GITHUB_HTTP_API_REQUEST_FAILURES.inc()
        raise Exception(
            f"_get_response(): deadline exceeded, giving up after {time.monotonic()-t0:.3f} s"
        )

    def _get_response_retry_guts(self, url) -> Optional[dict]:
        """
        Return deserialized JSON-structure or raise an exception or return
        `None` which indicates a retryable error.
        """

        # This counter is meant to count _attempts_. Errors (failed attempts)
        # are counted separately
        metrics.COUNTER_GITHUB_HTTP_API_REQUESTS.inc()
        try:
            # This next line can raise exceptions corresponding to transient
            # issues related to DNS, TCP, HTTP during sending request, while
            # waiting for response, or while receiving the response. `requests`
            # has a little bit of retrying built-in by default for some of
            # these errors, but it's not trying too hard. Add more retrying
            # on top of that.
            if self._current_auth_token:
                resp = requests.get(
                    url,
                    headers={"Authorization": f"Bearer { self._current_auth_token}"},
                )
            else:
                resp = requests.get(url)

        except requests.exceptions.RequestException as exc:
            metrics.COUNTER_GITHUB_HTTP_API_RETRYABLE_ERRORS.inc()
            log.info(
                "error during HTTP request/response cycle: %s --  "
                "assume that it's retryable, retry soon.",
                exc,
            )
            return None

        reqquota: Optional[int] = None
        if "x-ratelimit-remaining" in resp.headers:
            # Expect the value to always be int-convertible.
            reqquota = int(resp.headers["x-ratelimit-remaining"])
            metrics.GAUGE_GITHUB_HTTP_API_QUOTA_REMAINING.set(reqquota)
            # Temporary workaround, see metrics._periodically_set_q_rem()
            metrics.gauge_gh_api_rem_set["set"] = False

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
            metrics.COUNTER_GITHUB_HTTP_API_403RESPONSES.inc()

            log.info(
                "403 response, x-ratelimit headers: %s",
                ", ".join(
                    f"{k}: {v}"
                    for k, v in resp.headers.items()
                    if "x-ratelimit" in k.lower()
                ),
            )

            if reqquota == 0:
                if self._rotate_auth_token():
                    _tloc.auth_token_rotations += 1
                    # Example: rotations performed: 1, pool size: 2
                    #  -> proceed (this request/token pair was not tried)
                    # Example: rotations performed: 2, pool size: 2
                    #  -> proceed (this request/token pair was tried once before,
                    #     try this one again, but after that give up)
                    # Example: rotations performed: 3, pool size: 2
                    #  -> give up
                    if _tloc.auth_token_rotations <= self._token_pool_size:
                        log.info("reqquota 0, rotated auth token, retry request")
                        return None

                    log.info("reqquota 0, cycled through auth token pool, give up")

                metrics.COUNTER_GITHUB_HTTP_API_REQUEST_FAILURES.inc()
                raise Exception("Hourly GitHub HTTP API quota exhausted")

            metrics.COUNTER_GITHUB_HTTP_API_RETRYABLE_ERRORS.inc()
            log.info("quota not exhausted, try to retry soon")
            # Add additional wait time, because this seems to be a legit
            # HTTP request rate limiting error -- we have to seriously back
            # off if we want to have success. The wait time in the
            # _get_response() loop is too short.
            time.sleep(2)
            return None

        # For the rare occasion where the GitHub HTTP API returns a 5xx
        # response we certainly want to retry.
        if str(resp.status_code).startswith("5"):
            metrics.COUNTER_GITHUB_HTTP_API_RETRYABLE_ERRORS.inc()
            return None

        # Non-retryable error.
        metrics.COUNTER_GITHUB_HTTP_API_REQUEST_FAILURES.inc()
        raise Exception(
            f"Unexpected GitHub HTTP API response: {resp}",
        )


# Initialize long-lived, cross-request GitHub HTTP API client object. This
# object internally maintains state that is meant to be long-lived.
_github = GitHubHTTPApiClient()
