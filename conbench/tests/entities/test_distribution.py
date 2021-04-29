import datetime

from ...entities.commit import Commit
from ...entities.distribution import (
    get_commit_index,
    get_commits_up,
    get_sha_row_number,
)


REPO = "arrow"

COMMIT_INDEX = """WITH ordered_commits AS 
(SELECT commit.id AS id, commit.sha AS sha, commit.parent AS parent, commit.timestamp AS timestamp 
FROM commit 
WHERE commit.repository = :repository_1 ORDER BY commit.timestamp DESC)
 SELECT ordered_commits.id, ordered_commits.sha, ordered_commits.parent, ordered_commits.timestamp, row_number() OVER () AS row_number 
FROM ordered_commits"""


ROW_NUMBER = """WITH ordered_commits AS 
(SELECT commit.id AS id, commit.sha AS sha, commit.parent AS parent, commit.timestamp AS timestamp 
FROM commit 
WHERE commit.repository = :repository_1 ORDER BY commit.timestamp DESC)
 SELECT commit_index.row_number 
FROM (SELECT ordered_commits.id AS id, ordered_commits.sha AS sha, ordered_commits.parent AS parent, ordered_commits.timestamp AS timestamp, row_number() OVER () AS row_number 
FROM ordered_commits) AS commit_index 
WHERE commit_index.sha = :sha_1"""


COMMITS_UP = """WITH ordered_commits AS 
(SELECT commit.id AS id, commit.sha AS sha, commit.parent AS parent, commit.timestamp AS timestamp 
FROM commit 
WHERE commit.repository = :repository_1 ORDER BY commit.timestamp DESC)
 SELECT commit_index.id, commit_index.sha, commit_index.parent, commit_index.timestamp, commit_index.row_number 
FROM (SELECT ordered_commits.id AS id, ordered_commits.sha AS sha, ordered_commits.parent AS parent, ordered_commits.timestamp AS timestamp, row_number() OVER () AS row_number 
FROM ordered_commits) AS commit_index 
WHERE commit_index.row_number >= :row_number_1
 LIMIT :param_1"""


def test_distibution_queries():
    assert str(get_commit_index(REPO).statement.compile()) == COMMIT_INDEX
    assert str(get_sha_row_number(REPO, "SOME SHA").statement.compile()) == ROW_NUMBER
    assert str(get_commits_up(REPO, "SOME SHA", 3).statement.compile()) == COMMITS_UP


def test_distibution():
    commit_1 = Commit.create(
        {
            "sha": "11111",
            "repository": REPO,
            "parent": "00000",
            "timestamp": datetime.datetime(2021, 11, 1),
            "message": "message 11111",
            "author_name": "author_name",
            "author_login": "author_login",
            "author_avatar": "author_avatar",
        }
    )
    commit_2 = Commit.create(
        {
            "sha": "22222",
            "repository": REPO,
            "parent": "11111",
            "timestamp": datetime.datetime(2021, 11, 2),
            "message": "message 22222",
            "author_name": "author_name",
            "author_login": "author_login",
            "author_avatar": "author_avatar",
        }
    )
    commit_3 = Commit.create(
        {
            "sha": "33333",
            "repository": REPO,
            "parent": "22222",
            "timestamp": datetime.datetime(2021, 11, 3),
            "message": "message 33333",
            "author_name": "author_name",
            "author_login": "author_login",
            "author_avatar": "author_avatar",
        }
    )
    Commit.create(
        {
            "sha": "bbbbb",
            "repository": "not arrow",
            "parent": "aaaaa",
            "timestamp": datetime.datetime(2021, 11, 3),
            "message": "NOT an arrow commit",
            "author_name": "author_name",
            "author_login": "author_login",
            "author_avatar": "author_avatar",
        }
    )
    commit_4 = Commit.create(
        {
            "sha": "44444",
            "repository": REPO,
            "parent": "33333",
            "timestamp": datetime.datetime(2021, 11, 4),
            "message": "message 44444",
            "author_name": "author_name",
            "author_login": "author_login",
            "author_avatar": "author_avatar",
        }
    )
    commit_5 = Commit.create(
        {
            "sha": "55555",
            "repository": REPO,
            "parent": "44444",
            "timestamp": datetime.datetime(2021, 11, 5),
            "message": "message 55555",
            "author_name": "author_name",
            "author_login": "author_login",
            "author_avatar": "author_avatar",
        }
    )
    expected = [
        (commit_5.id, commit_5.sha, commit_5.parent, commit_5.timestamp, 1),
        (commit_4.id, commit_4.sha, commit_4.parent, commit_4.timestamp, 2),
        (commit_3.id, commit_3.sha, commit_3.parent, commit_3.timestamp, 3),
        (commit_2.id, commit_2.sha, commit_2.parent, commit_2.timestamp, 4),
        (commit_1.id, commit_1.sha, commit_1.parent, commit_1.timestamp, 5),
    ]
    assert get_commit_index(REPO).all() == expected

    assert get_sha_row_number(REPO, "55555").all() == [(1,)]
    assert get_sha_row_number(REPO, "44444").all() == [(2,)]
    assert get_sha_row_number(REPO, "33333").all() == [(3,)]
    assert get_sha_row_number(REPO, "22222").all() == [(4,)]
    assert get_sha_row_number(REPO, "11111").all() == [(5,)]
    assert get_sha_row_number(REPO, "00000").all() == []

    expected = [
        (commit_5.id, commit_5.sha, commit_5.parent, commit_5.timestamp, 1),
        (commit_4.id, commit_4.sha, commit_4.parent, commit_4.timestamp, 2),
        (commit_3.id, commit_3.sha, commit_3.parent, commit_3.timestamp, 3),
    ]
    assert get_commits_up(REPO, "55555", 3).all() == expected
    expected = [
        (commit_4.id, commit_4.sha, commit_4.parent, commit_4.timestamp, 2),
        (commit_3.id, commit_3.sha, commit_3.parent, commit_3.timestamp, 3),
        (commit_2.id, commit_2.sha, commit_2.parent, commit_2.timestamp, 4),
    ]
    assert get_commits_up(REPO, "44444", 3).all() == expected
    expected = [
        (commit_3.id, commit_3.sha, commit_3.parent, commit_3.timestamp, 3),
        (commit_2.id, commit_2.sha, commit_2.parent, commit_2.timestamp, 4),
        (commit_1.id, commit_1.sha, commit_1.parent, commit_1.timestamp, 5),
    ]
    assert get_commits_up(REPO, "33333", 3).all() == expected
    expected = [
        (commit_2.id, commit_2.sha, commit_2.parent, commit_2.timestamp, 4),
        (commit_1.id, commit_1.sha, commit_1.parent, commit_1.timestamp, 5),
    ]
    assert get_commits_up(REPO, "22222", 3).all() == expected
    expected = [
        (commit_1.id, commit_1.sha, commit_1.parent, commit_1.timestamp, 5),
    ]
    assert get_commits_up(REPO, "11111", 3).all() == expected
    assert get_commits_up(REPO, "00000", 3).all() == []
