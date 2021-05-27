import copy
import datetime
import decimal
import uuid

from ...entities.commit import Commit
from ...entities.distribution import (
    Distribution,
    get_commit_index,
    get_commits_up,
    get_distribution,
    get_sha_row_number,
    set_z_scores,
)
from ...entities.summary import Summary
from ...runner import Conbench
from ...tests.api.test_benchmarks import VALID_PAYLOAD


REPO = "arrow"
MACHINE = "diana-2-4-17179869184"

COMMIT_INDEX = """WITH ordered_commits AS 
(SELECT commit.id AS id, commit.sha AS sha, commit.timestamp AS timestamp 
FROM commit 
WHERE commit.repository = :repository_1 ORDER BY commit.timestamp DESC)
 SELECT ordered_commits.id, ordered_commits.sha, ordered_commits.timestamp, row_number() OVER () AS row_number 
FROM ordered_commits"""  # noqa


ROW_NUMBER = """WITH ordered_commits AS 
(SELECT commit.id AS id, commit.sha AS sha, commit.timestamp AS timestamp 
FROM commit 
WHERE commit.repository = :repository_1 ORDER BY commit.timestamp DESC)
 SELECT commit_index.row_number 
FROM (SELECT ordered_commits.id AS id, ordered_commits.sha AS sha, ordered_commits.timestamp AS timestamp, row_number() OVER () AS row_number 
FROM ordered_commits) AS commit_index 
WHERE commit_index.sha = :sha_1"""  # noqa


COMMITS_UP = """WITH ordered_commits AS 
(SELECT commit.id AS id, commit.sha AS sha, commit.timestamp AS timestamp 
FROM commit 
WHERE commit.repository = :repository_1 ORDER BY commit.timestamp DESC)
 SELECT commit_index.id, commit_index.sha, commit_index.timestamp, commit_index.row_number 
FROM (SELECT ordered_commits.id AS id, ordered_commits.sha AS sha, ordered_commits.timestamp AS timestamp, row_number() OVER () AS row_number 
FROM ordered_commits) AS commit_index 
WHERE commit_index.row_number >= (SELECT commit_index.row_number 
FROM (SELECT ordered_commits.id AS id, ordered_commits.sha AS sha, ordered_commits.timestamp AS timestamp, row_number() OVER () AS row_number 
FROM ordered_commits) AS commit_index 
WHERE commit_index.sha = :sha_1)
 LIMIT :param_1"""  # noqa


DISTRIBUTION = """WITH ordered_commits AS 
(SELECT commit.id AS id, commit.sha AS sha, commit.timestamp AS timestamp 
FROM commit 
WHERE commit.repository = :repository_1 ORDER BY commit.timestamp DESC)
 SELECT text(:text_1) AS repository, text(:text_2) AS sha, summary.case_id, summary.context_id, concat(machine.name, :concat_1, machine.cpu_core_count, :concat_2, machine.cpu_thread_count, :concat_3, machine.memory_bytes) AS hash, max(summary.unit) AS unit, avg(summary.mean) AS mean_mean, stddev(summary.mean) AS mean_sd, avg(summary.min) AS min_mean, stddev(summary.min) AS min_sd, avg(summary.max) AS max_mean, stddev(summary.max) AS max_sd, avg(summary.median) AS median_mean, stddev(summary.median) AS median_sd, min(commits_up.timestamp) AS first_timestamp, max(commits_up.timestamp) AS last_timestamp, count(summary.mean) AS observations 
FROM summary JOIN run ON run.id = summary.run_id JOIN machine ON machine.id = summary.machine_id JOIN (SELECT commit_index.id AS id, commit_index.sha AS sha, commit_index.timestamp AS timestamp, commit_index.row_number AS row_number 
FROM (SELECT ordered_commits.id AS id, ordered_commits.sha AS sha, ordered_commits.timestamp AS timestamp, row_number() OVER () AS row_number 
FROM ordered_commits) AS commit_index 
WHERE commit_index.row_number >= (SELECT commit_index.row_number 
FROM (SELECT ordered_commits.id AS id, ordered_commits.sha AS sha, ordered_commits.timestamp AS timestamp, row_number() OVER () AS row_number 
FROM ordered_commits) AS commit_index 
WHERE commit_index.sha = :sha_1)
 LIMIT :param_1) AS commits_up ON commits_up.id = run.commit_id 
WHERE run.name LIKE :name_1 AND summary.case_id = :case_id_1 AND summary.context_id = :context_id_1 AND concat(machine.name, :concat_4, machine.cpu_core_count, :concat_5, machine.cpu_thread_count, :concat_6, machine.memory_bytes) = :param_2 GROUP BY summary.case_id, summary.context_id, machine.name, machine.cpu_core_count, machine.cpu_thread_count, machine.memory_bytes"""  # noqa


def create_benchmark_summary(results, commit, benchmark_name=None):
    data = copy.deepcopy(VALID_PAYLOAD)
    now = datetime.datetime.now(datetime.timezone.utc)
    run_id, run_name = uuid.uuid4().hex, "commit: some commit"
    data["github"]["commit"] = commit.sha
    data["github"]["repository"] = commit.repository
    if benchmark_name:
        data["tags"]["name"] = benchmark_name
    batch_id = data["stats"]["batch_id"]
    data["stats"] = Conbench._stats(
        results, "s", [], "s", now.isoformat(), run_id, batch_id, run_name
    )
    summary = Summary.create(data)
    return summary


def test_distibution_queries():
    query = str(get_commit_index(REPO).statement.compile())
    assert query == COMMIT_INDEX
    query = str(get_sha_row_number(REPO, "SHA").statement.compile())
    assert query == ROW_NUMBER
    query = str(get_commits_up(REPO, "SHA", 3).statement.compile())
    assert query == COMMITS_UP
    query = str(get_distribution(REPO, "SHA", "ID", "ID", "ID", 3).statement.compile())
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

    data = [2.1, 2.0, 1.99]  # first commit
    summary_1 = create_benchmark_summary(data, commit_1)

    data = [1.99, 2.0, 2.1]  # stayed the same
    summary_2 = create_benchmark_summary(data, commit_2)

    data = [1.1, 1.0, 0.99]  # got better
    summary_3 = create_benchmark_summary(data, commit_3)

    data = [1.2, 1.1, 1.0]  # stayed about the same
    summary_4 = create_benchmark_summary(data, commit_4)

    data = [3.1, 3.0, 2.99]  # got worse
    summary_5 = create_benchmark_summary(data, commit_5)

    data = [5.1, 5.2, 5.3]  # n/a different repo
    summary_b = create_benchmark_summary(data, commit_b)

    data, case = [5.1, 5.2, 5.3], "different-case"  # n/a different case
    summary_x = create_benchmark_summary(data, commit_1, case)

    assert summary_1.case_id == summary_2.case_id
    assert summary_1.case_id == summary_3.case_id
    assert summary_1.case_id == summary_4.case_id
    assert summary_1.case_id == summary_5.case_id

    assert summary_1.machine_id == summary_2.machine_id
    assert summary_1.machine_id == summary_3.machine_id
    assert summary_1.machine_id == summary_4.machine_id
    assert summary_1.machine_id == summary_5.machine_id

    case_id = summary_1.case_id
    context_id = summary_1.context_id
    machine_hash = summary_1.machine.hash

    assert Distribution.count() >= 7

    # ----- get_commit_index

    expected = [
        (commit_5.id, commit_5.sha, commit_5.timestamp, 1),
        (commit_4.id, commit_4.sha, commit_4.timestamp, 2),
        (commit_3.id, commit_3.sha, commit_3.timestamp, 3),
        (commit_2.id, commit_2.sha, commit_2.timestamp, 4),
        (commit_1.id, commit_1.sha, commit_1.timestamp, 5),
    ]
    assert get_commit_index(REPO).all() == expected

    # ----- get_sha_row_number

    assert get_sha_row_number(REPO, "55555").all() == [(1,)]
    assert get_sha_row_number(REPO, "44444").all() == [(2,)]
    assert get_sha_row_number(REPO, "33333").all() == [(3,)]
    assert get_sha_row_number(REPO, "22222").all() == [(4,)]
    assert get_sha_row_number(REPO, "11111").all() == [(5,)]
    assert get_sha_row_number(REPO, "00000").all() == []

    # ----- get_commits_up

    expected = [
        (commit_5.id, commit_5.sha, commit_5.timestamp, 1),
        (commit_4.id, commit_4.sha, commit_4.timestamp, 2),
        (commit_3.id, commit_3.sha, commit_3.timestamp, 3),
    ]
    assert get_commits_up(REPO, "55555", 3).all() == expected
    expected = [
        (commit_4.id, commit_4.sha, commit_4.timestamp, 2),
        (commit_3.id, commit_3.sha, commit_3.timestamp, 3),
        (commit_2.id, commit_2.sha, commit_2.timestamp, 4),
    ]
    assert get_commits_up(REPO, "44444", 3).all() == expected
    expected = [
        (commit_3.id, commit_3.sha, commit_3.timestamp, 3),
        (commit_2.id, commit_2.sha, commit_2.timestamp, 4),
        (commit_1.id, commit_1.sha, commit_1.timestamp, 5),
    ]
    assert get_commits_up(REPO, "33333", 3).all() == expected
    expected = [
        (commit_2.id, commit_2.sha, commit_2.timestamp, 4),
        (commit_1.id, commit_1.sha, commit_1.timestamp, 5),
    ]
    assert get_commits_up(REPO, "22222", 3).all() == expected
    expected = [
        (commit_1.id, commit_1.sha, commit_1.timestamp, 5),
    ]
    assert get_commits_up(REPO, "11111", 3).all() == expected
    assert get_commits_up(REPO, "00000", 3).all() == []

    # ----- get_distribution

    assert get_distribution(
        REPO, "55555", case_id, context_id, machine_hash, 10
    ).all() == [
        (
            REPO,
            "55555",
            summary_5.case_id,
            summary_5.context_id,
            MACHINE,
            "s",
            decimal.Decimal("1.8440000000000000"),
            decimal.Decimal("0.82035358230460601799"),
            decimal.Decimal("1.7920000000000000"),
            decimal.Decimal("0.83427813108099627329"),
            decimal.Decimal("1.9200000000000000"),
            decimal.Decimal("0.81363382427231969152"),
            decimal.Decimal("1.8200000000000000"),
            decimal.Decimal("0.81363382427231969152"),
            datetime.datetime(2021, 11, 1, 0, 0),
            datetime.datetime(2021, 11, 5, 0, 0),
            5,
        )
    ]
    assert get_distribution(
        REPO, "44444", case_id, context_id, machine_hash, 10
    ).all() == [
        (
            REPO,
            "44444",
            summary_4.case_id,
            summary_4.context_id,
            MACHINE,
            "s",
            decimal.Decimal("1.5475000000000000"),
            decimal.Decimal("0.55787543412485909532"),
            decimal.Decimal("1.4925000000000000"),
            decimal.Decimal("0.57447802394869727514"),
            decimal.Decimal("1.6250000000000000"),
            decimal.Decimal("0.55000000000000000000"),
            decimal.Decimal("1.5250000000000000"),
            decimal.Decimal("0.55000000000000000000"),
            datetime.datetime(2021, 11, 1, 0, 0),
            datetime.datetime(2021, 11, 4, 0, 0),
            4,
        )
    ]
    assert get_distribution(
        REPO, "33333", case_id, context_id, machine_hash, 10
    ).all() == [
        (
            REPO,
            "33333",
            summary_3.case_id,
            summary_3.context_id,
            MACHINE,
            "s",
            decimal.Decimal("1.6966666666666667"),
            decimal.Decimal("0.57735026918962576451"),
            decimal.Decimal("1.6566666666666667"),
            decimal.Decimal("0.57735026918962576451"),
            decimal.Decimal("1.7666666666666667"),
            decimal.Decimal("0.57735026918962576451"),
            decimal.Decimal("1.6666666666666667"),
            decimal.Decimal("0.57735026918962576451"),
            datetime.datetime(2021, 11, 1, 0, 0),
            datetime.datetime(2021, 11, 3, 0, 0),
            3,
        )
    ]
    assert get_distribution(
        REPO, "22222", case_id, context_id, machine_hash, 10
    ).all() == [
        (
            REPO,
            "22222",
            summary_2.case_id,
            summary_2.context_id,
            MACHINE,
            "s",
            decimal.Decimal("2.0300000000000000"),
            decimal.Decimal("0"),
            decimal.Decimal("1.9900000000000000"),
            decimal.Decimal("0"),
            decimal.Decimal("2.1000000000000000"),
            decimal.Decimal("0"),
            decimal.Decimal("2.0000000000000000"),
            decimal.Decimal("0"),
            datetime.datetime(2021, 11, 1, 0, 0),
            datetime.datetime(2021, 11, 2, 0, 0),
            2,
        )
    ]
    assert get_distribution(
        REPO, "11111", case_id, context_id, machine_hash, 10
    ).all() == [
        (
            REPO,
            "11111",
            summary_1.case_id,
            summary_1.context_id,
            MACHINE,
            "s",
            decimal.Decimal("2.0300000000000000"),
            None,
            decimal.Decimal("1.99000000000000000000"),
            None,
            decimal.Decimal("2.1000000000000000"),
            None,
            decimal.Decimal("2.0000000000000000"),
            None,
            datetime.datetime(2021, 11, 1, 0, 0),
            datetime.datetime(2021, 11, 1, 0, 0),
            1,
        )
    ]
    assert (
        get_distribution(REPO, "00000", case_id, context_id, machine_hash, 10).all()
        == []
    )

    # ----- set_z_scores

    # first commit, no distribution history
    set_z_scores([summary_1])
    assert summary_1.z_score == 0

    # second commit, no change
    set_z_scores([summary_2])
    assert summary_2.z_score == 0

    # third commit, got better
    set_z_scores([summary_3])
    assert summary_3.z_score == decimal.Decimal("-1.154700538379251586751622041")

    # forth commit, stayed about the same
    set_z_scores([summary_4])
    assert summary_4.z_score == decimal.Decimal("-0.8021503952795387425767458943")

    # fifth commit, got worse
    set_z_scores([summary_5])
    assert summary_5.z_score == decimal.Decimal("1.445718072770755055613474796")

    # n/a different repo, no distribution history
    set_z_scores([summary_b])
    assert summary_b.z_score == 0

    # n/a different case, no distribution history
    set_z_scores([summary_x])
    assert summary_x.z_score == 0


def test_distibution_multiple_runs_same_commit():
    commit_1 = Commit.create(
        {
            "sha": "YYYYY",
            "repository": REPO,
            "parent": "XXXXX",
            "timestamp": datetime.datetime(2021, 11, 1),
            "message": "message 11111",
            "author_name": "author_name",
            "author_login": "author_login",
            "author_avatar": "author_avatar",
        }
    )

    data = [1, 2, 3]
    summary_1 = create_benchmark_summary(data, commit_1)

    case_id = summary_1.case_id
    context_id = summary_1.context_id
    machine_hash = summary_1.machine.hash

    assert get_distribution(
        REPO, "YYYYY", case_id, context_id, machine_hash, 10
    ).all() == [
        (
            REPO,
            "YYYYY",
            summary_1.case_id,
            summary_1.context_id,
            MACHINE,
            "s",
            decimal.Decimal("2.0000000000000000"),
            None,
            decimal.Decimal("1.00000000000000000000"),
            None,
            decimal.Decimal("3.0000000000000000"),
            None,
            decimal.Decimal("2.0000000000000000"),
            None,
            datetime.datetime(2021, 11, 1, 0, 0),
            datetime.datetime(2021, 11, 1, 0, 0),
            1,
        )
    ]

    set_z_scores([summary_1])
    assert summary_1.z_score == 0

    data = [4, 5, 6]
    summary_2 = create_benchmark_summary(data, commit_1)

    assert summary_1.case_id == summary_2.case_id
    assert summary_1.context_id == summary_2.context_id
    assert summary_1.run.commit_id == summary_2.run.commit_id
    assert summary_1.machine_id == summary_2.machine_id

    assert get_distribution(
        REPO, "YYYYY", case_id, context_id, machine_hash, 10
    ).all() == [
        (
            REPO,
            "YYYYY",
            summary_1.case_id,
            summary_1.context_id,
            MACHINE,
            "s",
            decimal.Decimal("3.5000000000000000"),
            decimal.Decimal("2.1213203435596426"),
            decimal.Decimal("2.5000000000000000"),
            decimal.Decimal("2.1213203435596426"),
            decimal.Decimal("4.5000000000000000"),
            decimal.Decimal("2.1213203435596426"),
            decimal.Decimal("3.5000000000000000"),
            decimal.Decimal("2.1213203435596426"),
            datetime.datetime(2021, 11, 1, 0, 0),
            datetime.datetime(2021, 11, 1, 0, 0),
            2,
        )
    ]

    set_z_scores([summary_1])
    assert summary_1.z_score == decimal.Decimal("-0.7071067811865475154683553909")

    set_z_scores([summary_2])
    assert summary_2.z_score == decimal.Decimal("0.7071067811865475154683553909")
