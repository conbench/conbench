import datetime
import dateutil
import json
import os

from ...entities.commit import parse_commit
from ...tests.api import _fixtures


this_dir = os.path.abspath(os.path.dirname(__file__))


def test_parse_commit():
    path = os.path.join(this_dir, "github_commit.json")
    with open(path) as f:
        commit = json.load(f)
    tz = dateutil.tz.tzutc()
    message = "Move benchmark tests (so CI runs them)"
    expected = {
        "parent": _fixtures.PARENT,
        "message": f"ARROW-11771: [Developer][Archery] {message}",
        "date": datetime.datetime(2021, 2, 25, 1, 2, 51, tzinfo=tz),
        "author_name": "Diana Clarke",
        "author_login": "dianaclarke",
        "author_avatar": "https://avatars.githubusercontent.com/u/878798?v=4",
    }
    assert parse_commit(commit) == expected


def test_parse_commit_no_author():
    path = os.path.join(this_dir, "github_commit_no_author.json")
    with open(path) as f:
        commit = json.load(f)
    tz = dateutil.tz.tzutc()
    message = "Move benchmark tests (so CI runs them)"
    expected = {
        "parent": _fixtures.PARENT,
        "message": f"ARROW-11771: [Developer][Archery] {message}",
        "date": datetime.datetime(2021, 2, 25, 1, 2, 51, tzinfo=tz),
        "author_name": "Diana Clarke",
        "author_login": None,
        "author_avatar": None,
    }
    assert parse_commit(commit) == expected


def test_parse_pull_request_commit():
    path = os.path.join(this_dir, "github_pull_request_commit.json")
    with open(path) as f:
        commit = json.load(f)
    tz = dateutil.tz.tzutc()
    message = "Move benchmark tests (so CI runs them)"
    expected = {
        "parent": "81e9417eb68171e03a304097ae86e1fd83307130",
        "message": f"ARROW-11771: [Developer][Archery] {message}",
        "date": datetime.datetime(2021, 2, 24, 20, 59, 4, tzinfo=tz),
        "author_name": "Diana Clarke",
        "author_login": "dianaclarke",
        "author_avatar": "https://avatars.githubusercontent.com/u/878798?v=4",
    }
    assert parse_commit(commit) == expected
