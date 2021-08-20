import datetime
import json
import os

import dateutil
import pytest

from ...entities.commit import (
    GitHub,
    get_github_commit,
    repository_to_name,
    repository_to_url,
)
from ...tests.api import _fixtures

this_dir = os.path.abspath(os.path.dirname(__file__))


def test_repository_to_name():
    expected = "apache/arrow"
    assert repository_to_name(None) == ""
    assert repository_to_name("") == ""
    assert repository_to_name("blah blah") == "blah blah"
    assert repository_to_name("apache/arrow") == expected
    assert repository_to_name("https://github.com/apache/arrow") == expected
    assert repository_to_name("git@github.com:apache/arrow") == expected


def test_repository_to_url():
    expected = "https://github.com/apache/arrow"
    assert repository_to_url(None) == ""
    assert repository_to_url("") == ""
    assert repository_to_url("blah blah") == "https://github.com/blah blah"
    assert repository_to_url("apache/arrow") == expected
    assert repository_to_url("https://github.com/apache/arrow") == expected
    assert repository_to_url("git@github.com:apache/arrow") == expected


def test_get_github_commit_none():
    repo = "https://github.com/apache/arrow"
    sha = "3decc46119d583df56c7c66c77cf2803441c4458"

    assert get_github_commit(None, None) == {}
    assert get_github_commit("", "") == {}
    assert get_github_commit(repo, None) == {}
    assert get_github_commit(None, sha) == {}


@pytest.mark.slow
def test_get_github_commit():
    # NOTE: This integration test intentionally hits GitHub.
    # TODO: This test will fail once it's no longer one of the most recent 1000
    # commits to the apache/arrow repository.
    repo = "https://github.com/apache/arrow"
    sha = "3decc46119d583df56c7c66c77cf2803441c4458"
    tz = dateutil.tz.tzutc()
    expected = {
        "parent": "fcaa422c84796bcf7dbe328ee3612f434cd4d356",
        "date": datetime.datetime(2021, 3, 17, 16, 27, 37, tzinfo=tz),
        "message": "ARROW-11997: [Python] concat_tables crashes python interpreter",
        "author_name": "Diana Clarke",
        "author_login": "dianaclarke",
        "author_avatar": "https://avatars.githubusercontent.com/u/878798?v=4",
    }
    assert get_github_commit(repo, sha) == expected


@pytest.mark.slow
def test_get_github_commit_pull_request():
    # NOTE: This integration test intentionally hits GitHub.
    # TODO: This test will fail once it's no longer one of the most recent 1000
    # commits to the apache/arrow repository.
    repo = "https://github.com/apache/arrow"
    sha = "982023150ccbb06a6f581f6797c017492485b58c"
    tz = dateutil.tz.tzutc()
    expected = {
        "parent": "780e95c512d63bbea1e040af0eb44a0bf63c4d72",
        "date": datetime.datetime(2021, 7, 6, 21, 51, 48, tzinfo=tz),
        "message": "ARROW-13266: [JS] Improve benchmark names",
        "author_name": "Diana Clarke",
        "author_login": "dianaclarke",
        "author_avatar": "https://avatars.githubusercontent.com/u/878798?v=4",
    }
    assert get_github_commit(repo, sha) == expected


def test_parse_commits():
    path = os.path.join(this_dir, "github_commits.json")
    with open(path) as f:
        commits = json.load(f)
    expected = [
        "0219e9a198b201df852b4219816752b36f116825",
        "7eea2f53a1002552bbb87db5611e75c15b88b504",
        "e4dc71ac966997a5d8a0fbd2cf83ceb3e9a5db51",
        "21990c7d03f4910ade16be5469aaf19d3107e0b8",
        "18a41b412392c653e03cfe06887530ac3d8bf601",
        "cf6a7ff65f4e2920641d116a3ba1f578b2bd8a9e",
        "6c8d30ea82222fd2750b999840872d3f6cbdc8f8",
        "903977061194786699d1824c4e6cb977184351d1",
        "40008951dc7551581084b2359ee5e81ea6ee7f49",
        "a8a81f6e8a93a3e6a08e70ba4e278c97aff944ef",
        "fdd7d32bcbc4086242e6a3517ef49e4f4468bd56",
        "dfb0928e91c0d3bd89cb0497a3948ed8fea7fc78",
        "bc86814d6cd4865c1250319cbd0bf5431938ac80",
        "afea938e9db889ccc1565b0ad079b56e5192afd3",
        "3ce67ebe6750da22d04e73eab85e484fd29f8264",
        "f247e3ab7a4d2c33bfca6165570fabd62c2fb6ea",
        "780e95c512d63bbea1e040af0eb44a0bf63c4d72",
        "b69b3ed50424d0b39213d9a814044a94af2ab8e7",
        "27be94f39e988e6461d6900ca9b7ae28cfc65ea9",
        "0072c677fbbc85832fa7a90ab49daf7c1f99a373",
        "304f202f8be988fa96a4e85f005798f51602771b",
        "d9092ec7e11c2a626f9086fedead475846b52356",
        "41c4143992905cc85eb61a417cf9460c6db6b4df",
        "905809cbfb780dc1a1be17657334937ae59b446e",
        "835de65411caf95432736a4563d8cd4777bf9e27",
        "3a372d6e4af10298cf6219f9951e147ad45c3677",
        "0ebed2b9c9b739aa134507d3a26ad2015e535ff9",
        "9891d9b1eacfee0f356531ba381a916380fde9f1",
        "389587c566e0d0d59b635a76fcc8dbb89358d6ec",
        "32679ddf0495a50b2158146709e7ecfd27a467d9",
    ]
    assert GitHub._parse_commits(commits) == expected


def test_parse_commit():
    path = os.path.join(this_dir, "github_child.json")
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
    assert GitHub._parse_commit(commit) == expected


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
    assert GitHub._parse_commit(commit) == expected


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
    assert GitHub._parse_commit(commit) == expected
