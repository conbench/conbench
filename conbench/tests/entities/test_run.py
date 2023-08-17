import logging

from ..api import _fixtures
from ...entities.run import get_candidate_baseline_runs

log = logging.getLogger(__name__)


DEFAULT_BRANCH_PLACEHOLDER = {
    "error": "the contender run is already on the default branch",
    "baseline_run_id": None,
    "commits_skipped": None,
}


def test_get_candidate_baseline_runs():
    commits, benchmark_results = _fixtures.gen_fake_data()
    run_ids = [result.run_id for result in benchmark_results]
    # Corresponding to these fake runs:
    expected_baseline_run_dicts = [
        # run 0, commit 11111
        {
            "parent": {
                "error": "this baseline commit type does not exist for this run",
                "baseline_run_id": None,
                "commits_skipped": None,
            },
            "fork_point": DEFAULT_BRANCH_PLACEHOLDER,
            "latest_default": {
                "error": None,
                "baseline_run_id": run_ids[9],
                "commits_skipped": [],
            },
        },
        # run 1, commit 22222
        {
            "parent": {
                "error": None,
                "baseline_run_id": run_ids[0],
                "commits_skipped": [],
            },
            "fork_point": DEFAULT_BRANCH_PLACEHOLDER,
            "latest_default": {
                "error": None,
                "baseline_run_id": run_ids[9],
                "commits_skipped": [],
            },
        },
        # run 2, commit aaaaa
        {
            "parent": {
                "error": None,
                "baseline_run_id": run_ids[1],
                "commits_skipped": [],
            },
            "fork_point": {
                "error": None,
                "baseline_run_id": run_ids[1],
                "commits_skipped": [],
            },
            "latest_default": {
                "error": None,
                "baseline_run_id": run_ids[15],
                "commits_skipped": [],
            },
        },
        # run 3, commit bbbbb
        {
            "parent": {
                "error": None,
                "baseline_run_id": run_ids[2],
                "commits_skipped": [],
            },
            "fork_point": {
                "error": None,
                "baseline_run_id": run_ids[1],
                "commits_skipped": [],
            },
            "latest_default": {
                "error": None,
                "baseline_run_id": run_ids[15],
                "commits_skipped": [],
            },
        },
        # run 4, commit ddddd
        {
            "parent": {
                "error": None,
                "baseline_run_id": run_ids[1],
                "commits_skipped": ["ccccc", "33333"],
            },
            "fork_point": {
                "error": None,
                "baseline_run_id": run_ids[1],
                "commits_skipped": ["33333"],
            },
            "latest_default": {
                "error": None,
                "baseline_run_id": run_ids[15],
                "commits_skipped": [],
            },
        },
        # run 5, commit 44444
        {
            "parent": {
                "error": None,
                "baseline_run_id": run_ids[1],
                "commits_skipped": ["33333"],
            },
            "fork_point": DEFAULT_BRANCH_PLACEHOLDER,
            "latest_default": {
                "error": None,
                "baseline_run_id": run_ids[9],
                "commits_skipped": [],
            },
        },
        # run 6, commit fffff
        {
            "parent": {
                "error": None,
                "baseline_run_id": run_ids[5],
                "commits_skipped": ["eeeee"],
            },
            "fork_point": {
                "error": None,
                "baseline_run_id": run_ids[5],
                "commits_skipped": [],
            },
            "latest_default": {
                "error": None,
                "baseline_run_id": run_ids[15],
                "commits_skipped": [],
            },
        },
        # run 7, commit 00000
        {
            "parent": {
                "error": None,
                "baseline_run_id": run_ids[6],
                "commits_skipped": [],
            },
            "fork_point": {
                "error": None,
                "baseline_run_id": run_ids[5],
                "commits_skipped": [],
            },
            "latest_default": {
                "error": None,
                "baseline_run_id": run_ids[15],
                "commits_skipped": [],
            },
        },
        # run 8, commit 66666
        {
            "parent": {
                "error": None,
                "baseline_run_id": run_ids[5],
                "commits_skipped": ["55555"],
            },
            "fork_point": DEFAULT_BRANCH_PLACEHOLDER,
            "latest_default": {
                "error": None,
                "baseline_run_id": run_ids[9],
                "commits_skipped": [],
            },
        },
        # run 9, commit 66666
        {
            "parent": {
                "error": None,
                "baseline_run_id": run_ids[5],
                "commits_skipped": ["55555"],
            },
            "fork_point": DEFAULT_BRANCH_PLACEHOLDER,
            "latest_default": {
                "error": None,
                "baseline_run_id": run_ids[8],
                "commits_skipped": [],
            },
        },
        # run 10, commit abcde (different repo)
        {
            "parent": {
                "error": "this baseline commit type does not exist for this run",
                "baseline_run_id": None,
                "commits_skipped": None,
            },
            "fork_point": DEFAULT_BRANCH_PLACEHOLDER,
            "latest_default": {
                "error": "no matching baseline run was found",
                "baseline_run_id": None,
                "commits_skipped": None,
            },
        },
        # run 11, commit 'sha' (no detailed commit info)
        {
            "parent": {
                "error": "this baseline commit type does not exist for this run",
                "baseline_run_id": None,
                "commits_skipped": None,
            },
            "fork_point": {
                "error": "this baseline commit type does not exist for this run",
                "baseline_run_id": None,
                "commits_skipped": None,
            },
            "latest_default": {
                "error": "this baseline commit type does not exist for this run",
                "baseline_run_id": None,
                "commits_skipped": None,
            },
        },
        # run 12, commit 66666 (different case)
        {
            "parent": {
                "error": "no matching baseline run was found",
                "baseline_run_id": None,
                "commits_skipped": None,
            },
            "fork_point": DEFAULT_BRANCH_PLACEHOLDER,
            "latest_default": {
                "error": "no matching baseline run was found",
                "baseline_run_id": None,
                "commits_skipped": None,
            },
        },
        # run 13, commit 66666 (different context)
        {
            "parent": {
                "error": "no matching baseline run was found",
                "baseline_run_id": None,
                "commits_skipped": None,
            },
            "fork_point": DEFAULT_BRANCH_PLACEHOLDER,
            "latest_default": {
                "error": "no matching baseline run was found",
                "baseline_run_id": None,
                "commits_skipped": None,
            },
        },
        # run 14, commit 66666 (different hardware)
        {
            "parent": {
                "error": "no matching baseline run was found",
                "baseline_run_id": None,
                "commits_skipped": None,
            },
            "fork_point": DEFAULT_BRANCH_PLACEHOLDER,
            "latest_default": {
                "error": "no matching baseline run was found",
                "baseline_run_id": None,
                "commits_skipped": None,
            },
        },
        # run 15, commit 66666 (nightly reason)
        {
            "parent": {
                "error": None,
                "baseline_run_id": run_ids[5],
                "commits_skipped": ["55555"],
            },
            "fork_point": DEFAULT_BRANCH_PLACEHOLDER,
            "latest_default": {
                "error": None,
                "baseline_run_id": run_ids[9],
                "commits_skipped": [],
            },
        },
    ]
    assert len(run_ids) == len(expected_baseline_run_dicts), "you should test all runs"

    failures = []
    for ix, (result, expected_baseline_run_dict) in enumerate(
        zip(benchmark_results, expected_baseline_run_dicts)
    ):
        actual_baseline_run_dict = get_candidate_baseline_runs(result)
        if actual_baseline_run_dict != expected_baseline_run_dict:
            failures.append(ix)
            log.info(
                "run %d: expected:\n%s, but got \n%s",
                ix,
                expected_baseline_run_dict,
                actual_baseline_run_dict,
            )
    assert not failures

    # create one more nightly on 44444 and hope that we pick it up in the last test case
    # (which should also have a nightly reason)
    new_benchmark_result = _fixtures.benchmark_result(
        name=benchmark_results[-1].case.name,
        results=[1, 2, 3],
        reason="nightly",
        commit=commits["44444"],
    )
    actual_baseline_run_dict = get_candidate_baseline_runs(benchmark_results[-1])
    assert actual_baseline_run_dict == {
        "parent": {
            "error": None,
            "baseline_run_id": new_benchmark_result.run_id,
            "commits_skipped": ["55555"],
        },
        "fork_point": DEFAULT_BRANCH_PLACEHOLDER,
        "latest_default": {
            "error": None,
            "baseline_run_id": new_benchmark_result.run_id,
            "commits_skipped": ["66666", "55555"],
        },
    }

    # test a run with no commit that can still find a latest_default baseline
    benchmark_result_missing_commit = _fixtures.benchmark_result(
        name=benchmark_results[1].case.name,
        results=[1, 2, 3],
        no_github=True,
    )
    assert benchmark_result_missing_commit.commit is None
    actual_baseline_run_dict = get_candidate_baseline_runs(
        benchmark_result_missing_commit
    )
    assert actual_baseline_run_dict == {
        "parent": {
            "error": "the contender run is not connected to the git graph",
            "baseline_run_id": None,
            "commits_skipped": None,
        },
        "fork_point": {
            "error": "the contender run is not connected to the git graph",
            "baseline_run_id": None,
            "commits_skipped": None,
        },
        "latest_default": {
            "error": None,
            "baseline_run_id": run_ids[9],  # latest with same reason (commit)
            "commits_skipped": [],
        },
    }
