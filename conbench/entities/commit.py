import functools
import json
import os

import dateutil.parser
import flask as f
import requests
import sqlalchemy as s

from ..entities._entity import (
    Base,
    EntityMixin,
    EntitySerializer,
    NotNull,
    Nullable,
    generate_uuid,
)


class Commit(Base, EntityMixin):
    __tablename__ = "commit"
    id = NotNull(s.String(50), primary_key=True, default=generate_uuid)
    sha = NotNull(s.String(50))
    parent = Nullable(s.String(50))
    repository = NotNull(s.String(100))
    message = NotNull(s.String(250))
    author_name = NotNull(s.String(100))
    author_login = Nullable(s.String(50))
    author_avatar = Nullable(s.String(100))
    timestamp = Nullable(s.DateTime(timezone=False))

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
    def create_github_context(sha, repository, github):
        return Commit.create(
            {
                "sha": sha,
                "repository": repository,
                "parent": github["parent"],
                "timestamp": github["date"],
                "message": github["message"],
                "author_name": github["author_name"],
                "author_login": github["author_login"],
                "author_avatar": github["author_avatar"],
            }
        )


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
        return {
            "id": commit.id,
            "sha": commit.sha,
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
    return f"https://github.com/{name}" if name else ""


def get_github_commit(repository, sha):
    if not repository or not sha:
        return {}

    github = GitHub()
    name = repository_to_name(repository)
    commit = github.get_commit(name, sha)
    if commit is None:
        return {}

    parent = commit["parent"]
    commits = github.get_commits(name, parent)
    if parent in commits:
        return commit
    else:
        # This is a pull request, find the parent of the first commit.
        # TODO: This will fail if the pull request has more than 50 commits.
        # It will also give up if it can't find the parent after 50 tries
        # (which could happen for a really old pull request).
        parent = commit["parent"]
        for _ in range(50):
            other = github.get_commit(name, parent)
            if other["parent"] in commits:
                commit["parent"] = other["parent"]
                return commit
            else:
                parent = other["parent"]

    return {}


class GitHub:
    def __init__(self):
        self.test_shas = {
            "02addad336ba19a654f9c857ede546331be7b631": "github_child.json",
            "4beb514d071c9beec69b8917b5265e77ade22fb3": "github_parent.json",
            "6d703c4c7b15be630af48d5e9ef61628751674b2": "github_grandparent.json",
        }
        self.test_commits = [
            "02addad336ba19a654f9c857ede546331be7b631",
            "4beb514d071c9beec69b8917b5265e77ade22fb3",
            "6d703c4c7b15be630af48d5e9ef61628751674b2",
            "81e9417eb68171e03a304097ae86e1fd83307130",
        ]

    def get_commits(self, name, sha):
        if sha in self.test_commits:
            return self.test_commits

        commits = []

        # Grabs the last 1000 commits to the main branch. TODO: If the pull
        # request is old, the parent may not be in the last 1000 commits.
        for branch in ["master", "main"]:
            url = f"{GITHUB}/repos/{name}/commits?sha={branch}&per_page=100"
            response = self._get_response(url)
            if response:
                commits = self._parse_commits(response)
                if sha in commits:
                    return commits
                for page in range(2, 11):
                    url = f"{GITHUB}/repos/{name}/commits?sha={branch}&per_page=100&page={page}"
                    response = self._get_response(url)
                    if response:
                        commits.extend(self._parse_commits(response))
                        if sha in commits:
                            return commits
            if commits:
                break

        return commits

    def get_commit(self, name, sha):
        if sha in self.test_commits:
            response = self.test_commit(sha)
        else:
            url = f"{GITHUB}/repos/{name}/commits/{sha}"
            response = self._get_response(url)
        return self._parse_commit(response) if response else None

    @functools.cached_property
    def session(self):
        token, session = os.getenv("GITHUB_API_TOKEN"), None
        if token:
            session = requests.Session()
            session.headers = {"Authorization": f"Bearer {token}"}
        return session

    def test_commit(self, sha):
        fixture = f"../tests/entities/{self.test_shas[sha]}"
        path = os.path.join(this_dir, fixture)
        with open(path) as fixture:
            return json.load(fixture)

    @staticmethod
    def _parse_commits(commits):
        return [commit["sha"] for commit in commits]

    @staticmethod
    def _parse_commit(commit):
        author = commit.get("author")
        commit_author = commit["commit"]["author"]
        return {
            "parent": commit["parents"][0]["sha"],
            "date": dateutil.parser.isoparse(commit_author["date"]),
            "message": commit["commit"]["message"].split("\n")[0],
            "author_name": commit_author["name"],
            "author_login": author["login"] if author else None,
            "author_avatar": author["avatar_url"] if author else None,
        }

    def _get_response(self, url):
        response = self.session.get(url) if self.session else requests.get(url)
        if response.status_code != 200:
            print(response.json())
            return None
        return response.json()
