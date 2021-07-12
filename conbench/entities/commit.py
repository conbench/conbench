import functools
import json
import os

import dateutil.parser
import requests
import sqlalchemy as s

from ..entities._entity import (
    Base,
    EntityMixin,
    EntitySerializer,
    generate_uuid,
    NotNull,
    Nullable,
)


class Commit(Base, EntityMixin):
    __tablename__ = "commit"
    id = NotNull(s.String(50), primary_key=True, default=generate_uuid)
    sha = NotNull(s.String(50))
    parent = NotNull(s.String(50))
    repository = NotNull(s.String(100))
    message = NotNull(s.String(250))
    author_name = NotNull(s.String(100))
    author_login = Nullable(s.String(50))
    author_avatar = Nullable(s.String(100))
    timestamp = NotNull(s.DateTime(timezone=False))


s.Index(
    "commit_index",
    Commit.sha,
    unique=True,
)


class _Serializer(EntitySerializer):
    def _dump(self, commit):
        return {
            "id": commit.id,
            "sha": commit.sha,
            "url": f"{commit.repository}/commit/{commit.sha}",
            "parent_sha": commit.parent,
            "parent_url": f"{commit.repository}/commit/{commit.parent}",
            "repository": commit.repository,
            "message": commit.message,
            "author_name": commit.author_name,
            "author_login": commit.author_login,
            "author_avatar": commit.author_avatar,
            "timestamp": commit.timestamp.isoformat(),
        }


class CommitSerializer:
    one = _Serializer()
    many = _Serializer(many=True)


GITHUB = "https://api.github.com"
this_dir = os.path.abspath(os.path.dirname(__file__))


def get_github_commit(repository, sha):
    github = GitHub()
    name = repository.split("github.com/")[1]
    commit = github.get_commit(name, sha)
    commits = github.get_commits(name, sha)
    if commit["parent"] in commits:
        return commit
    else:
        # this is a pull request, find the parent of the first commit
        parent = commit["parent"]
        while True:
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
        for branch in ["master", "main"]:
            url = f"{GITHUB}/repos/{name}/commits?sha={branch}&per_page=100"
            response = self._get_response(url)
            if response:
                commits = self._parse_commits(response)
                for page in range(2, 11):
                    url = f"{GITHUB}/repos/{name}/commits?sha={branch}&per_page=100&page={page}"
                    response = self._get_response(url)
                    if response:
                        commits.extend(self._parse_commits(response))
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
        return {
            "parent": commit["parents"][0]["sha"],
            "date": dateutil.parser.isoparse(commit["commit"]["author"]["date"]),
            "message": commit["commit"]["message"].split("\n")[0],
            "author_name": commit["commit"]["author"]["name"],
            "author_login": commit["author"]["login"] if commit["author"] else None,
            "author_avatar": commit["author"]["avatar_url"]
            if commit["author"]
            else None,
        }

    def _get_response(self, url):
        response = self.session.get(url) if self.session else requests.get(url)
        if response.status_code != 200:
            print(response.json())
            return None
        return response.json()
