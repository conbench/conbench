import copy
import datetime

from ...entities.commit import Commit
from ...entities.history import get_history
from ...entities.summary import Summary
from ...runner import Conbench
from ...tests.api import _fixtures
from ...tests.helpers import _uuid


REPO = "arrow"
MACHINE = "diana-2-4-17179869184"


def create_benchmark_summary(results, commit, name=None):
    data = copy.deepcopy(_fixtures.VALID_PAYLOAD)
    data["run_id"], data["run_name"] = _uuid(), "commit: some commit"
    data["github"]["commit"] = commit.sha
    data["github"]["repository"] = commit.repository
    if name:
        data["tags"]["name"] = name
    data["stats"] = Conbench._stats(results, "s", [], "s")
    summary = Summary.create(data)
    return summary


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
    summary_1 = create_benchmark_summary(data, commit_1, name=name)

    data = [1.99, 2.0, 2.1]  # stayed the same
    summary_2 = create_benchmark_summary(data, commit_2, name=name)

    data = [1.1, 1.0, 0.99]  # got better
    summary_3 = create_benchmark_summary(data, commit_3, name=name)

    data = [1.2, 1.1, 1.0]  # stayed about the same
    summary_4 = create_benchmark_summary(data, commit_4, name=name)

    data = [3.1, 3.0, 2.99]  # measure commit 4 twice
    summary_5 = create_benchmark_summary(data, commit_4, name=name)

    data, case = [5.1, 5.2, 5.3], "different-case"  # n/a different case
    create_benchmark_summary(data, commit_1, name=case)

    assert summary_1.case_id == summary_2.case_id
    assert summary_1.case_id == summary_3.case_id
    assert summary_1.case_id == summary_4.case_id
    assert summary_1.case_id == summary_5.case_id

    assert summary_1.run.machine_id == summary_2.run.machine_id
    assert summary_1.run.machine_id == summary_3.run.machine_id
    assert summary_1.run.machine_id == summary_4.run.machine_id
    assert summary_1.run.machine_id == summary_5.run.machine_id

    case_id = summary_1.case_id
    context_id = summary_1.context_id
    machine_hash = summary_1.run.machine.hash

    # ----- get_commit_index

    expected = [
        (
            summary_1.id,
            case_id,
            context_id,
            summary_1.mean,
            "s",
            machine_hash,
            commit_1.sha,
            REPO,
            "message 11111",
            datetime.datetime(2021, 11, 1),
            "commit: some commit",
        ),
        (
            summary_2.id,
            case_id,
            context_id,
            summary_2.mean,
            "s",
            machine_hash,
            commit_2.sha,
            REPO,
            "message 22222",
            datetime.datetime(2021, 11, 2),
            "commit: some commit",
        ),
        (
            summary_3.id,
            case_id,
            context_id,
            summary_3.mean,
            "s",
            machine_hash,
            commit_3.sha,
            REPO,
            "message 33333",
            datetime.datetime(2021, 11, 3),
            "commit: some commit",
        ),
        (
            summary_4.id,
            case_id,
            context_id,
            summary_4.mean,
            "s",
            machine_hash,
            commit_4.sha,
            REPO,
            "message 44444",
            datetime.datetime(2021, 11, 4),
            "commit: some commit",
        ),
        (
            summary_5.id,
            case_id,
            context_id,
            summary_5.mean,
            "s",
            machine_hash,
            commit_4.sha,
            REPO,
            "message 44444",
            datetime.datetime(2021, 11, 4),
            "commit: some commit",
        ),
    ]
    assert set(get_history(case_id, context_id, machine_hash)) == set(expected)
