import datetime
import decimal

from ...entities.commit import Commit
from ...entities.history import get_history
from ...tests.api import _fixtures
from ...tests.helpers import _uuid

REPO = "https://github.com/org/something"


def test_history():
    commit_1 = Commit.create(
        {
            "sha": "x11111",
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
            "sha": "x22222",
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
            "sha": "x33333",
            "repository": REPO,
            "parent": "22222",
            "timestamp": datetime.datetime(2021, 11, 3),
            "message": "message 33333",
            "author_name": "author_name",
            "author_login": "author_login",
            "author_avatar": "author_avatar",
        }
    )
    commit_4 = Commit.create(
        {
            "sha": "x44444",
            "repository": REPO,
            "parent": "33333",
            "timestamp": datetime.datetime(2021, 11, 4),
            "message": "message 44444",
            "author_name": "author_name",
            "author_login": "author_login",
            "author_avatar": "author_avatar",
        }
    )

    name = _uuid()
    data = [2.1, 2.0, 1.99]  # first commit
    benchmark_result_1 = _fixtures.benchmark_result(
        results=data, commit=commit_1, name=name
    )

    data = [1.99, 2.0, 2.1]  # stayed the same
    benchmark_result_2 = _fixtures.benchmark_result(
        results=data, commit=commit_2, name=name
    )

    # failed
    _fixtures.benchmark_result(commit=commit_3, name=name, error={"stack_trace": "..."})

    data = [1.1, 1.0, 0.99]  # got better
    benchmark_result_3 = _fixtures.benchmark_result(
        results=data, commit=commit_3, name=name
    )

    data = [1.2, 1.1, 1.0]  # stayed about the same
    benchmark_result_4 = _fixtures.benchmark_result(
        results=data, commit=commit_4, name=name
    )

    data = [3.1, 3.0, 2.99]  # measure commit 4 twice
    benchmark_result_5 = _fixtures.benchmark_result(
        results=data, commit=commit_4, name=name
    )

    data, name = [5.1, 5.2, 5.3], "different-case"
    _fixtures.benchmark_result(results=data, commit=commit_1, name=name)

    data, language = [6.1, 6.2, 6.3], "different-context"
    _fixtures.benchmark_result(
        results=data, commit=commit_1, name=name, language=language
    )

    data, machine = [7.1, 7.2, 7.3], "different-machine"
    _fixtures.benchmark_result(
        results=data, commit=commit_1, name=name, hardware_name=machine
    )

    data = [8.1, 8.2, 8.3]  # pull request, exclude from history
    _fixtures.benchmark_result(
        results=data, commit=commit_1, name=name, pull_request=True
    )

    assert benchmark_result_1.case_id == benchmark_result_2.case_id
    assert benchmark_result_1.case_id == benchmark_result_3.case_id
    assert benchmark_result_1.case_id == benchmark_result_4.case_id
    assert benchmark_result_1.case_id == benchmark_result_5.case_id

    assert benchmark_result_1.run.hardware_id == benchmark_result_2.run.hardware_id
    assert benchmark_result_1.run.hardware_id == benchmark_result_3.run.hardware_id
    assert benchmark_result_1.run.hardware_id == benchmark_result_4.run.hardware_id
    assert benchmark_result_1.run.hardware_id == benchmark_result_5.run.hardware_id

    case_id = benchmark_result_1.case_id
    context_id = benchmark_result_1.context_id
    hardware_hash = benchmark_result_1.run.hardware.hash

    # ----- get_commit_index

    expected = [
        (
            benchmark_result_1.id,
            case_id,
            context_id,
            benchmark_result_1.mean,
            "s",
            hardware_hash,
            commit_1.sha,
            REPO,
            "message 11111",
            datetime.datetime(2021, 11, 1),
            decimal.Decimal("2.0300000000000000"),
            None,
            benchmark_result_1.run.name,
        ),
        (
            benchmark_result_2.id,
            case_id,
            context_id,
            benchmark_result_2.mean,
            "s",
            hardware_hash,
            commit_2.sha,
            REPO,
            "message 22222",
            datetime.datetime(2021, 11, 2),
            decimal.Decimal("2.0300000000000000"),
            decimal.Decimal("0"),
            benchmark_result_2.run.name,
        ),
        (
            benchmark_result_3.id,
            case_id,
            context_id,
            benchmark_result_3.mean,
            "s",
            hardware_hash,
            commit_3.sha,
            REPO,
            "message 33333",
            datetime.datetime(2021, 11, 3),
            decimal.Decimal("1.6966666666666667"),
            decimal.Decimal("0.57735026918962576451"),
            benchmark_result_3.run.name,
        ),
        (
            benchmark_result_4.id,
            case_id,
            context_id,
            benchmark_result_4.mean,
            "s",
            hardware_hash,
            commit_4.sha,
            REPO,
            "message 44444",
            datetime.datetime(2021, 11, 4),
            decimal.Decimal("1.8440000000000000"),
            decimal.Decimal("0.82035358230460601799"),
            benchmark_result_4.run.name,
        ),
        (
            benchmark_result_5.id,
            case_id,
            context_id,
            benchmark_result_5.mean,
            "s",
            hardware_hash,
            commit_4.sha,
            REPO,
            "message 44444",
            datetime.datetime(2021, 11, 4),
            decimal.Decimal("1.8440000000000000"),
            decimal.Decimal("0.82035358230460601799"),
            benchmark_result_5.run.name,
        ),
    ]
    actual = get_history(case_id, context_id, hardware_hash)
    assert len(actual) == len(expected)
    assert set(actual) == set(expected)
