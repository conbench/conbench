import copy
import datetime
import decimal
import uuid

from ...entities.commit import Commit
from ...entities.distribution import (
    get_commit_index,
    get_commits_up,
    get_distribution,
    get_sha_row_number,
)
from ...entities.summary import Summary
from ...tests.api.test_benchmarks import VALID_PAYLOAD


REPO = "arrow"

COMMIT_INDEX = """WITH ordered_commits AS 
(SELECT commit.id AS id, commit.sha AS sha, commit.parent AS parent, commit.timestamp AS timestamp 
FROM commit 
WHERE commit.repository = :repository_1 ORDER BY commit.timestamp DESC)
 SELECT ordered_commits.id, ordered_commits.sha, ordered_commits.parent, ordered_commits.timestamp, row_number() OVER () AS row_number 
FROM ordered_commits"""  # noqa


ROW_NUMBER = """WITH ordered_commits AS 
(SELECT commit.id AS id, commit.sha AS sha, commit.parent AS parent, commit.timestamp AS timestamp 
FROM commit 
WHERE commit.repository = :repository_1 ORDER BY commit.timestamp DESC)
 SELECT commit_index.row_number 
FROM (SELECT ordered_commits.id AS id, ordered_commits.sha AS sha, ordered_commits.parent AS parent, ordered_commits.timestamp AS timestamp, row_number() OVER () AS row_number 
FROM ordered_commits) AS commit_index 
WHERE commit_index.sha = :sha_1"""  # noqa


COMMITS_UP = """WITH ordered_commits AS 
(SELECT commit.id AS id, commit.sha AS sha, commit.parent AS parent, commit.timestamp AS timestamp 
FROM commit 
WHERE commit.repository = :repository_1 ORDER BY commit.timestamp DESC)
 SELECT commit_index.id, commit_index.sha, commit_index.parent, commit_index.timestamp, commit_index.row_number 
FROM (SELECT ordered_commits.id AS id, ordered_commits.sha AS sha, ordered_commits.parent AS parent, ordered_commits.timestamp AS timestamp, row_number() OVER () AS row_number 
FROM ordered_commits) AS commit_index 
WHERE commit_index.row_number >= (SELECT commit_index.row_number 
FROM (SELECT ordered_commits.id AS id, ordered_commits.sha AS sha, ordered_commits.parent AS parent, ordered_commits.timestamp AS timestamp, row_number() OVER () AS row_number 
FROM ordered_commits) AS commit_index 
WHERE commit_index.sha = :sha_1)
 LIMIT :param_1"""  # noqa


DISTRIBUTION = """WITH ordered_commits AS 
(SELECT commit.id AS id, commit.sha AS sha, commit.parent AS parent, commit.timestamp AS timestamp 
FROM commit 
WHERE commit.repository = :repository_1 ORDER BY commit.timestamp DESC)
 SELECT text(:text_1) AS latest_sha, summary.case_id, summary.context_id, summary.machine_id, max(summary.unit) AS unit, avg(summary.mean) AS mean_mean, stddev(summary.mean) AS mean_sd, avg(summary.min) AS min_mean, stddev(summary.min) AS min_sd, avg(summary.max) AS max_mean, stddev(summary.max) AS max_sd, avg(summary.median) AS median_mean, stddev(summary.median) AS median_sd, min(commits_up.timestamp) AS first_timestamp, max(commits_up.timestamp) AS last_timestamp, count(summary.mean) AS n_observations_used 
FROM summary JOIN run ON run.id = summary.run_id JOIN (SELECT commit_index.id AS id, commit_index.sha AS sha, commit_index.parent AS parent, commit_index.timestamp AS timestamp, commit_index.row_number AS row_number 
FROM (SELECT ordered_commits.id AS id, ordered_commits.sha AS sha, ordered_commits.parent AS parent, ordered_commits.timestamp AS timestamp, row_number() OVER () AS row_number 
FROM ordered_commits) AS commit_index 
WHERE commit_index.row_number >= (SELECT commit_index.row_number 
FROM (SELECT ordered_commits.id AS id, ordered_commits.sha AS sha, ordered_commits.parent AS parent, ordered_commits.timestamp AS timestamp, row_number() OVER () AS row_number 
FROM ordered_commits) AS commit_index 
WHERE commit_index.sha = :sha_1)
 LIMIT :param_1) AS commits_up ON commits_up.id = run.commit_id 
WHERE run.name LIKE :name_1 GROUP BY summary.case_id, summary.context_id, summary.machine_id"""  # noqa


def create_benchmark_summary():
    data = copy.deepcopy(VALID_PAYLOAD)
    data["stats"]["run_id"] = uuid.uuid4().hex
    data["stats"]["run_name"] = "commit: some commit"
    summary = Summary.create(data)
    return summary


def test_distibution_queries():
    query = str(get_commit_index(REPO).statement.compile())
    assert query == COMMIT_INDEX
    query = str(get_sha_row_number(REPO, "SOME SHA").statement.compile())
    assert query == ROW_NUMBER
    query = str(get_commits_up(REPO, "SOME SHA", 3).statement.compile())
    assert query == COMMITS_UP
    query = str(get_distribution(REPO, "SOME SHA", 3).statement.compile())
    assert query == DISTRIBUTION


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
    commit_b = Commit.create(
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
    summary_1 = create_benchmark_summary()
    summary_1.run.commit_id = commit_1.id
    summary_1.save()

    summary_2 = create_benchmark_summary()
    summary_2.run.commit_id = commit_2.id
    summary_2.save()

    summary_3 = create_benchmark_summary()
    summary_3.run.commit_id = commit_3.id
    summary_3.save()

    summary_4 = create_benchmark_summary()
    summary_4.run.commit_id = commit_4.id
    summary_4.save()

    summary_5 = create_benchmark_summary()
    summary_5.run.commit_id = commit_5.id
    summary_5.save()

    summary_b = create_benchmark_summary()
    summary_b.run.commit_id = commit_b.id
    summary_b.save()

    # ----- get_commit_index

    expected = [
        (commit_5.id, commit_5.sha, commit_5.parent, commit_5.timestamp, 1),
        (commit_4.id, commit_4.sha, commit_4.parent, commit_4.timestamp, 2),
        (commit_3.id, commit_3.sha, commit_3.parent, commit_3.timestamp, 3),
        (commit_2.id, commit_2.sha, commit_2.parent, commit_2.timestamp, 4),
        (commit_1.id, commit_1.sha, commit_1.parent, commit_1.timestamp, 5),
    ]
    assert get_commit_index(REPO).all() == expected

    # ----- get_sha_row_number

    assert get_sha_row_number(REPO, "55555").all() == [(1,)]
    assert get_sha_row_number(REPO, "44444").all() == [(2,)]
    assert get_sha_row_number(REPO, "33333").all() == [(3,)]
    assert get_sha_row_number(REPO, "22222").all() == [(4,)]
    assert get_sha_row_number(REPO, "11111").all() == [(5,)]

    # ----- get_commits_up

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

    # ----- get_distribution

    assert set(get_distribution(REPO, "55555", 3).all()) == set(
        [
            (
                "55555",
                summary_5.case_id,
                summary_5.context_id,
                summary_5.machine_id,
                "s",
                decimal.Decimal("0.03636900000000000000"),
                decimal.Decimal("0"),
                decimal.Decimal("0.00473300000000000000"),
                decimal.Decimal("0"),
                decimal.Decimal("0.14889600000000000000"),
                decimal.Decimal("0"),
                decimal.Decimal("0.00898800000000000000"),
                decimal.Decimal("0"),
                datetime.datetime(2021, 11, 3, 0, 0),
                datetime.datetime(2021, 11, 5, 0, 0),
                3,
            ),
            (
                "55555",
                summary_4.case_id,
                summary_4.context_id,
                summary_4.machine_id,
                "s",
                decimal.Decimal("0.03636900000000000000"),
                decimal.Decimal("0"),
                decimal.Decimal("0.00473300000000000000"),
                decimal.Decimal("0"),
                decimal.Decimal("0.14889600000000000000"),
                decimal.Decimal("0"),
                decimal.Decimal("0.00898800000000000000"),
                decimal.Decimal("0"),
                datetime.datetime(2021, 11, 3, 0, 0),
                datetime.datetime(2021, 11, 5, 0, 0),
                3,
            ),
            (
                "55555",
                summary_3.case_id,
                summary_3.context_id,
                summary_3.machine_id,
                "s",
                decimal.Decimal("0.03636900000000000000"),
                decimal.Decimal("0"),
                decimal.Decimal("0.00473300000000000000"),
                decimal.Decimal("0"),
                decimal.Decimal("0.14889600000000000000"),
                decimal.Decimal("0"),
                decimal.Decimal("0.00898800000000000000"),
                decimal.Decimal("0"),
                datetime.datetime(2021, 11, 3, 0, 0),
                datetime.datetime(2021, 11, 5, 0, 0),
                3,
            ),
        ]
    )
    assert set(get_distribution(REPO, "44444", 3).all()) == set(
        [
            (
                "44444",
                summary_4.case_id,
                summary_4.context_id,
                summary_4.machine_id,
                "s",
                decimal.Decimal("0.03636900000000000000"),
                decimal.Decimal("0"),
                decimal.Decimal("0.00473300000000000000"),
                decimal.Decimal("0"),
                decimal.Decimal("0.14889600000000000000"),
                decimal.Decimal("0"),
                decimal.Decimal("0.00898800000000000000"),
                decimal.Decimal("0"),
                datetime.datetime(2021, 11, 2, 0, 0),
                datetime.datetime(2021, 11, 4, 0, 0),
                3,
            ),
            (
                "44444",
                summary_3.case_id,
                summary_3.context_id,
                summary_3.machine_id,
                "s",
                decimal.Decimal("0.03636900000000000000"),
                decimal.Decimal("0"),
                decimal.Decimal("0.00473300000000000000"),
                decimal.Decimal("0"),
                decimal.Decimal("0.14889600000000000000"),
                decimal.Decimal("0"),
                decimal.Decimal("0.00898800000000000000"),
                decimal.Decimal("0"),
                datetime.datetime(2021, 11, 2, 0, 0),
                datetime.datetime(2021, 11, 4, 0, 0),
                3,
            ),
            (
                "44444",
                summary_2.case_id,
                summary_2.context_id,
                summary_2.machine_id,
                "s",
                decimal.Decimal("0.03636900000000000000"),
                decimal.Decimal("0"),
                decimal.Decimal("0.00473300000000000000"),
                decimal.Decimal("0"),
                decimal.Decimal("0.14889600000000000000"),
                decimal.Decimal("0"),
                decimal.Decimal("0.00898800000000000000"),
                decimal.Decimal("0"),
                datetime.datetime(2021, 11, 2, 0, 0),
                datetime.datetime(2021, 11, 4, 0, 0),
                3,
            ),
        ]
    )
    assert set(get_distribution(REPO, "33333", 3).all()) == set(
        [
            (
                "33333",
                summary_3.case_id,
                summary_3.context_id,
                summary_3.machine_id,
                "s",
                decimal.Decimal("0.03636900000000000000"),
                decimal.Decimal("0"),
                decimal.Decimal("0.00473300000000000000"),
                decimal.Decimal("0"),
                decimal.Decimal("0.14889600000000000000"),
                decimal.Decimal("0"),
                decimal.Decimal("0.00898800000000000000"),
                decimal.Decimal("0"),
                datetime.datetime(2021, 11, 1, 0, 0),
                datetime.datetime(2021, 11, 3, 0, 0),
                3,
            ),
            (
                "33333",
                summary_2.case_id,
                summary_2.context_id,
                summary_2.machine_id,
                "s",
                decimal.Decimal("0.03636900000000000000"),
                decimal.Decimal("0"),
                decimal.Decimal("0.00473300000000000000"),
                decimal.Decimal("0"),
                decimal.Decimal("0.14889600000000000000"),
                decimal.Decimal("0"),
                decimal.Decimal("0.00898800000000000000"),
                decimal.Decimal("0"),
                datetime.datetime(2021, 11, 1, 0, 0),
                datetime.datetime(2021, 11, 3, 0, 0),
                3,
            ),
            (
                "33333",
                summary_1.case_id,
                summary_1.context_id,
                summary_1.machine_id,
                "s",
                decimal.Decimal("0.03636900000000000000"),
                decimal.Decimal("0"),
                decimal.Decimal("0.00473300000000000000"),
                decimal.Decimal("0"),
                decimal.Decimal("0.14889600000000000000"),
                decimal.Decimal("0"),
                decimal.Decimal("0.00898800000000000000"),
                decimal.Decimal("0"),
                datetime.datetime(2021, 11, 1, 0, 0),
                datetime.datetime(2021, 11, 3, 0, 0),
                3,
            ),
        ]
    )
    assert set(get_distribution(REPO, "22222", 3).all()) == set(
        [
            (
                "22222",
                summary_2.case_id,
                summary_2.context_id,
                summary_2.machine_id,
                "s",
                decimal.Decimal("0.03636900000000000000"),
                decimal.Decimal("0"),
                decimal.Decimal("0.00473300000000000000"),
                decimal.Decimal("0"),
                decimal.Decimal("0.14889600000000000000"),
                decimal.Decimal("0"),
                decimal.Decimal("0.00898800000000000000"),
                decimal.Decimal("0"),
                datetime.datetime(2021, 11, 1, 0, 0),
                datetime.datetime(2021, 11, 2, 0, 0),
                2,
            ),
            (
                "22222",
                summary_1.case_id,
                summary_1.context_id,
                summary_1.machine_id,
                "s",
                decimal.Decimal("0.03636900000000000000"),
                decimal.Decimal("0"),
                decimal.Decimal("0.00473300000000000000"),
                decimal.Decimal("0"),
                decimal.Decimal("0.14889600000000000000"),
                decimal.Decimal("0"),
                decimal.Decimal("0.00898800000000000000"),
                decimal.Decimal("0"),
                datetime.datetime(2021, 11, 1, 0, 0),
                datetime.datetime(2021, 11, 2, 0, 0),
                2,
            ),
        ]
    )
    assert set(get_distribution(REPO, "11111", 3).all()) == set(
        [
            (
                "11111",
                summary_1.case_id,
                summary_1.context_id,
                summary_1.machine_id,
                "s",
                decimal.Decimal("0.03636900000000000000"),
                None,
                decimal.Decimal("0.00473300000000000000"),
                None,
                decimal.Decimal("0.14889600000000000000"),
                None,
                decimal.Decimal("0.00898800000000000000"),
                None,
                datetime.datetime(2021, 11, 1, 0, 0),
                datetime.datetime(2021, 11, 1, 0, 0),
                1,
            ),
        ]
    )
