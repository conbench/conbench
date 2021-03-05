import datetime
import dateutil
import json
import os

from ...entities.commit import parse_commit


this_dir = os.path.abspath(os.path.dirname(__file__))


def test_parse_commit():
    path = os.path.join(this_dir, "github_commit.json")
    with open(path) as f:
        commit = json.load(f)
    tz = dateutil.tz.tzutc()
    message = "Move benchmark tests (so CI runs them)"
    sha = "02addad336ba19a654f9c857ede546331be7b631"
    expected = {
        "url": f"https://github.com/apache/arrow/commit/{sha}",
        "message": f"ARROW-11771: [Developer][Archery] {message}",
        "date": datetime.datetime(2021, 2, 25, 1, 2, 51, tzinfo=tz),
        "author_name": "Diana Clarke",
        "author_login": "dianaclarke",
        "author_avatar": "https://avatars.githubusercontent.com/u/878798?v=4",
    }
    assert parse_commit(commit) == expected


def test_parse_pull_request_commit():
    path = os.path.join(this_dir, "github_pull_request_commit.json")
    with open(path) as f:
        commit = json.load(f)
    tz = dateutil.tz.tzutc()
    message = "Move benchmark tests (so CI runs them)"
    sha = "bfe37ca73e7b387001ca009a262ad37df3457bd5"
    expected = {
        "url": f"https://github.com/apache/arrow/commit/{sha}",
        "message": f"ARROW-11771: [Developer][Archery] {message}",
        "date": datetime.datetime(2021, 2, 24, 20, 59, 4, tzinfo=tz),
        "author_name": "Diana Clarke",
        "author_login": "dianaclarke",
        "author_avatar": "https://avatars.githubusercontent.com/u/878798?v=4",
    }
    assert parse_commit(commit) == expected
