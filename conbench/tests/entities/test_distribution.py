import datetime
import decimal
import statistics

from ...entities.commit import Commit
from ...entities.distribution import (
    get_closest_parent,
    get_commits_up,
    get_distribution,
    set_z_scores,
)
from ...tests.api import _fixtures
from ...tests.helpers import _uuid

REPO = "https://github.com/org/something"
MACHINE = "diana-2-2-4-17179869184"

DISTRIBUTION = """SELECT text(:text_1) AS case_id, text(:text_2) AS context_id, text(:text_3) AS commit_id, machine.hash AS hash, max(summary.unit) AS unit, avg(summary.mean) AS mean_mean, stddev(summary.mean) AS mean_sd, avg(summary.min) AS min_mean, stddev(summary.min) AS min_sd, avg(summary.max) AS max_mean, stddev(summary.max) AS max_sd, avg(summary.median) AS median_mean, stddev(summary.median) AS median_sd, min(commits_up.timestamp) AS first_timestamp, max(commits_up.timestamp) AS last_timestamp, count(summary.mean) AS observations 
FROM summary JOIN run ON run.id = summary.run_id JOIN machine ON machine.id = run.machine_id JOIN (SELECT commit.id AS id, commit.timestamp AS timestamp 
FROM commit 
WHERE commit.repository = :repository_1 AND commit.timestamp IS NOT NULL AND commit.timestamp <= :timestamp_1 ORDER BY commit.timestamp DESC
 LIMIT :param_1) AS commits_up ON commits_up.id = run.commit_id 
WHERE run.name LIKE :name_1 AND summary.case_id = :case_id_1 AND summary.context_id = :context_id_1 AND machine.hash = :hash_1 GROUP BY summary.case_id, summary.context_id, machine.hash"""  # noqa


def test_z_score_calculations():
    """Manually sanity check the calculations used in the z-score tests."""

    # ----- RESULTS_UP

    summary_mean_0 = statistics.mean(_fixtures.RESULTS_UP[0])
    assert summary_mean_0 == 2.0
    summary_mean_1 = statistics.mean(_fixtures.RESULTS_UP[1])
    assert summary_mean_1 == 3.0
    summary_mean_2 = statistics.mean(_fixtures.RESULTS_UP[2])
    assert summary_mean_2 == 20.0

    distribution_mean_0 = statistics.mean([summary_mean_0])
    distribution_mean_1 = statistics.mean([summary_mean_0, summary_mean_1])
    assert distribution_mean_0 == 2.0
    assert distribution_mean_1 == 2.5

    distribution_stdev_1 = statistics.stdev([summary_mean_0, summary_mean_1])
    assert distribution_stdev_1 == 0.7071067811865476

    z_score = (summary_mean_2 - distribution_mean_1) / distribution_stdev_1
    assert z_score == _fixtures.Z_SCORE_UP

    # ----- RESULTS_DOWN

    summary_mean_0 = statistics.mean(_fixtures.RESULTS_DOWN[0])
    assert summary_mean_0 == 11.0
    summary_mean_1 = statistics.mean(_fixtures.RESULTS_DOWN[1])
    assert summary_mean_1 == 12.0
    summary_mean_2 = statistics.mean(_fixtures.RESULTS_DOWN[2])
    assert summary_mean_2 == 2.0

    distribution_mean_0 = statistics.mean([summary_mean_0])
    distribution_mean_1 = statistics.mean([summary_mean_0, summary_mean_1])
    assert distribution_mean_0 == 11.0
    assert distribution_mean_1 == 11.5

    distribution_stdev_1 = statistics.stdev([summary_mean_0, summary_mean_1])
    assert distribution_stdev_1 == 0.7071067811865476

    z_score = (summary_mean_2 - distribution_mean_1) / distribution_stdev_1
    assert z_score == _fixtures.Z_SCORE_DOWN


def test_distribution_query():
    summary = _fixtures.summary()
    query = str(get_distribution(summary, 3).statement.compile())
    assert query == DISTRIBUTION


def test_distribution():
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

    # note that commit_6 & commit_7 are intentionally missing

    commit_8 = Commit.create(
        {
            "sha": "88888",
            "repository": REPO,
            "parent": "77777",
            "timestamp": datetime.datetime(2021, 11, 7),
            "message": "message 88888",
            "author_name": "author_name",
            "author_login": "author_login",
            "author_avatar": "author_avatar",
        }
    )

    name = _uuid()
    data = [2.1, 2.0, 1.99]  # first commit
    summary_1 = _fixtures.summary(results=data, commit=commit_1, name=name)

    data = [1.99, 2.0, 2.1]  # stayed the same
    summary_2 = _fixtures.summary(results=data, commit=commit_2, name=name)

    data = [1.1, 1.0, 0.99]  # got better
    summary_3 = _fixtures.summary(results=data, commit=commit_3, name=name)

    data = [1.2, 1.1, 1.0]  # stayed about the same
    summary_4 = _fixtures.summary(results=data, commit=commit_4, name=name)

    data = [3.1, 3.0, 2.99]  # got worse
    summary_5 = _fixtures.summary(results=data, commit=commit_5, name=name)

    # note that summary_6 & summary_7 are intentionally missing

    data = [4.1, 4.0, 4.99]  # got even worse
    summary_8 = _fixtures.summary(results=data, commit=commit_8, name=name)

    data = [5.1, 5.2, 5.3]  # n/a different repo
    summary_b = _fixtures.summary(results=data, commit=commit_b, name=name)

    data, case = [5.1, 5.2, 5.3], "different-case"  # n/a different case
    summary_x = _fixtures.summary(results=data, commit=commit_1, name=case)

    data = [8.1, 8.2, 8.3]  # pull request, exclude from distribution
    _fixtures.summary(results=data, commit=commit_1, pull_request=True)

    assert summary_1.case_id == summary_2.case_id
    assert summary_1.case_id == summary_3.case_id
    assert summary_1.case_id == summary_4.case_id
    assert summary_1.case_id == summary_5.case_id
    assert summary_1.case_id == summary_8.case_id

    assert summary_1.run.hardware_id == summary_2.run.hardware_id
    assert summary_1.run.hardware_id == summary_3.run.hardware_id
    assert summary_1.run.hardware_id == summary_4.run.hardware_id
    assert summary_1.run.hardware_id == summary_5.run.hardware_id
    assert summary_1.run.hardware_id == summary_8.run.hardware_id

    # ----- get_commits_up

    expected = [
        (commit_8.id, commit_8.timestamp),
        (commit_5.id, commit_5.timestamp),
        (commit_4.id, commit_4.timestamp),
    ]
    assert get_commits_up(commit_8, 3).all() == expected
    expected = [
        (commit_5.id, commit_5.timestamp),
        (commit_4.id, commit_4.timestamp),
        (commit_3.id, commit_3.timestamp),
    ]
    assert get_commits_up(commit_5, 3).all() == expected
    expected = [
        (commit_4.id, commit_4.timestamp),
        (commit_3.id, commit_3.timestamp),
        (commit_2.id, commit_2.timestamp),
    ]
    assert get_commits_up(commit_4, 3).all() == expected
    expected = [
        (commit_3.id, commit_3.timestamp),
        (commit_2.id, commit_2.timestamp),
        (commit_1.id, commit_1.timestamp),
    ]
    assert get_commits_up(commit_3, 3).all() == expected
    expected = [
        (commit_2.id, commit_2.timestamp),
        (commit_1.id, commit_1.timestamp),
    ]
    assert get_commits_up(commit_2, 3).all() == expected
    expected = [
        (commit_1.id, commit_1.timestamp),
    ]
    assert get_commits_up(commit_1, 3).all() == expected

    # ----- get_closest_parent

    assert get_closest_parent(summary_8.run).id == commit_5.id
    assert get_closest_parent(summary_5.run).id == commit_4.id
    assert get_closest_parent(summary_4.run).id == commit_3.id
    assert get_closest_parent(summary_3.run).id == commit_2.id
    assert get_closest_parent(summary_2.run).id == commit_1.id
    assert get_closest_parent(summary_1.run) is None

    # ----- get_distribution

    assert get_distribution(summary_8, 10).all() == [
        (
            summary_8.case_id,
            summary_8.context_id,
            commit_8.id,
            MACHINE,
            "s",
            decimal.Decimal("2.2638888333333333"),
            decimal.Decimal("1.2634175058737182"),
            decimal.Decimal("2.1600000000000000"),
            decimal.Decimal("1.1701965646847541"),
            decimal.Decimal("2.4316666666666667"),
            decimal.Decimal("1.4492814311467137"),
            decimal.Decimal("2.2000000000000000"),
            decimal.Decimal("1.1815244390193544"),
            datetime.datetime(2021, 11, 1, 0, 0),
            datetime.datetime(2021, 11, 7, 0, 0),
            6,
        )
    ]
    assert get_distribution(summary_5, 10).all() == [
        (
            summary_5.case_id,
            summary_5.context_id,
            commit_5.id,
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
    assert get_distribution(summary_4, 10).all() == [
        (
            summary_4.case_id,
            summary_4.context_id,
            commit_4.id,
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
    assert get_distribution(summary_3, 10).all() == [
        (
            summary_3.case_id,
            summary_3.context_id,
            commit_3.id,
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
    assert get_distribution(summary_2, 10).all() == [
        (
            summary_2.case_id,
            summary_2.context_id,
            commit_2.id,
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
    assert get_distribution(summary_1, 10).all() == [
        (
            summary_1.case_id,
            summary_1.context_id,
            commit_1.id,
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

    # ----- set_z_scores

    # first commit, no distribution history
    set_z_scores([summary_1])
    assert summary_1.z_score is None

    # second commit, no change
    set_z_scores([summary_2])
    assert summary_2.z_score is None

    # third commit, got better, but distribution stdev was 0
    set_z_scores([summary_3])
    assert summary_3.z_score is None

    # forth commit, stayed about the same (but still better)
    set_z_scores([summary_4])
    assert summary_4.z_score == decimal.Decimal("1.033456981849430176204879553")

    # fifth commit, got worse
    set_z_scores([summary_5])
    assert summary_5.z_score == decimal.Decimal("-2.657403264808751253340839750")

    # note that summary_6 & summary_7 are intentionally missing

    # eighth commit, got even worse
    set_z_scores([summary_8])
    assert summary_8.z_score == decimal.Decimal("-3.071033093952584018991452191")

    # n/a different repo, no distribution history
    set_z_scores([summary_b])
    assert summary_b.z_score is None

    # n/a different case, no distribution history
    set_z_scores([summary_x])
    assert summary_x.z_score is None


def test_distribution_multiple_runs_same_commit():
    commit_1 = Commit.create(
        {
            "sha": "xxxxx",
            "repository": REPO,
            "parent": "wwwww",
            "timestamp": datetime.datetime(2021, 11, 1),
            "message": "message xxxxx",
            "author_name": "author_name",
            "author_login": "author_login",
            "author_avatar": "author_avatar",
        }
    )
    commit_2 = Commit.create(
        {
            "sha": "yyyyy",
            "repository": REPO,
            "parent": "xxxxx",
            "timestamp": datetime.datetime(2021, 11, 2),
            "message": "message yyyyy",
            "author_name": "author_name",
            "author_login": "author_login",
            "author_avatar": "author_avatar",
        }
    )
    commit_3 = Commit.create(
        {
            "sha": "zzzzz",
            "repository": REPO,
            "parent": "yyyyy",
            "timestamp": datetime.datetime(2021, 11, 3),
            "message": "message zzzzz",
            "author_name": "author_name",
            "author_login": "author_login",
            "author_avatar": "author_avatar",
        }
    )

    name = _uuid()
    summary_1 = _fixtures.summary(
        results=_fixtures.RESULTS_UP[0], commit=commit_1, name=name
    )
    summary_2 = _fixtures.summary(
        results=_fixtures.RESULTS_UP[1], commit=commit_2, name=name
    )
    summary_3 = _fixtures.summary(
        results=_fixtures.RESULTS_UP[2], commit=commit_3, name=name
    )

    case_id = summary_1.case_id
    context_id = summary_1.context_id

    assert get_distribution(summary_1, 10).all() == [
        (
            case_id,
            context_id,
            commit_1.id,
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

    assert get_distribution(summary_2, 10).all() == [
        (
            case_id,
            context_id,
            commit_2.id,
            MACHINE,
            "s",
            decimal.Decimal("2.5000000000000000"),
            decimal.Decimal("0.70710678118654752440"),
            decimal.Decimal("1.5000000000000000"),
            decimal.Decimal("0.70710678118654752440"),
            decimal.Decimal("3.5000000000000000"),
            decimal.Decimal("0.70710678118654752440"),
            decimal.Decimal("2.5000000000000000"),
            decimal.Decimal("0.70710678118654752440"),
            datetime.datetime(2021, 11, 1, 0, 0),
            datetime.datetime(2021, 11, 2, 0, 0),
            2,
        )
    ]

    # before
    set_z_scores([summary_1])
    assert summary_1.z_score is None
    set_z_scores([summary_2])
    assert summary_2.z_score is None
    set_z_scores([summary_3])
    Z_SCORE_UP_DECIMAL = decimal.Decimal(_fixtures.Z_SCORE_UP)
    assert round(summary_3.z_score, 10) == -1 * round(Z_SCORE_UP_DECIMAL, 10)

    # re-run commit 2
    summary_4 = _fixtures.summary(results=[0, 1, 2], commit=commit_2, name=name)
    set_z_scores([summary_4])
    assert summary_4.z_score is None

    # after, summary_3 z-score changes with more info
    set_z_scores([summary_1])
    assert summary_1.z_score is None
    set_z_scores([summary_2])
    assert summary_2.z_score is None
    set_z_scores([summary_3])
    Z_SCORE_UP_DECIMAL = decimal.Decimal("18.0000000000")
    assert round(summary_3.z_score, 10) == -1 * round(Z_SCORE_UP_DECIMAL, 10)
