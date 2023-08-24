from datetime import datetime
from typing import Callable, cast

import numpy as np
import pandas as pd
import pytest
import sigfig
import sqlalchemy as s

from conbench.types import TBenchmarkName

from ...db import _session as Session
from ...entities.commit import Commit
from ...entities.history import (
    _detect_shifts_with_trimmed_estimators,
    get_history_for_cchr,
    set_z_scores,
)
from ...tests.api import _fixtures


# Some different strategies for choosing a baseline commit to test set_z_scores()
def _get_closest_defaultbranch_ancestor(commit: Commit) -> Commit:
    """If on the default branch, use the parent as baseline. Else use the fork point."""
    fork_point_commit = commit.get_fork_point_commit()
    if commit == fork_point_commit:
        return commit.get_parent_commit()
    else:
        return fork_point_commit


def _get_parent(commit: Commit) -> Commit:
    """Always use the parent as baseline."""
    return commit.get_parent_commit()


def _get_head_of_default(commit: Commit) -> Commit:
    """Use the head of the default branch as baseline."""
    return Session.scalars(
        s.select(Commit)
        .filter(Commit.branch == "default", Commit.repository == commit.repository)
        .order_by(s.desc(Commit.timestamp))
        .limit(1)
    ).first()


def assert_equal_leeway(comparison, reference, figs=4):
    """
    Compare two Optional[float] values but allow for
    - a tiny absolute epsilon
    - a relatively dimensioned epsilon
    """
    if reference is None or comparison is None:
        assert comparison is reference
        return

    if abs(reference - comparison) < 10**-13:
        return

    # For tiny values close to zero the condition below can fail with for
    # example `assert -3.846e-15 == 0.0` -- in our context is I think this can
    # safely be considered numerical noise.
    assert sigfig.round(reference, sigfigs=figs) == sigfig.round(
        comparison, sigfigs=figs
    )


# These correspond to the benchmark_results of _fixtures.gen_fake_data() without modification
EXPECTED_Z_SCORES = {
    "closest_defaultbranch_ancestor": [
        None,
        None,
        28.48,
        0.7071,
        2.121,
        13.44,
        1.093,
        -2.186,
        -4.487,
        -4.947,
        None,
        None,
        None,
        None,
        None,
        -5.982,
    ],
    "parent": [
        None,
        None,
        28.48,
        0.7071,
        2.121,
        13.44,
        1.093,
        -2.825,
        -4.487,
        -4.947,
        None,
        None,
        None,
        None,
        None,
        -5.982,
    ],
    "head_of_default": [
        0.6625,
        0.6083,
        1.7269,
        0.6625,
        0.7167,
        1.150,
        1.150,
        0.1205,
        -0.6023,
        -0.7468,
        None,
        None,
        None,
        None,
        None,
        -1.072,
    ],
}


def test_get_history():
    _, benchmark_results = _fixtures.gen_fake_data()
    all_expected_benchmark_results_ixs = [
        [0, 1, 5, 8, 9, 15],
        [0, 1, 5, 8, 9, 15],
        [0, 1, 5, 8, 9, 15],
        [0, 1, 5, 8, 9, 15],
        [0, 1, 5, 8, 9, 15],
        [0, 1, 5, 8, 9, 15],
        [0, 1, 5, 8, 9, 15],
        [0, 1, 5, 8, 9, 15],
        [0, 1, 5, 8, 9, 15],
        [0, 1, 5, 8, 9, 15],
        [],  # only errors in the building
        [],  # no branch information
        [12],
        [13],
        [14],
        [0, 1, 5, 8, 9, 15],
    ]
    assert len(benchmark_results) == len(
        all_expected_benchmark_results_ixs
    ), "you should test all benchmark_results"

    # each input BenchmarkResult will give a subset of all BenchmarkResults as its history
    for benchmark_result, expected_benchmark_results_ixs in zip(
        benchmark_results, all_expected_benchmark_results_ixs
    ):
        expected_benchmark_result_ids = {
            benchmark_results[ix].id for ix in expected_benchmark_results_ixs
        }

        actual_history = get_history_for_cchr(
            cast(TBenchmarkName, str(benchmark_result.case.name)),
            benchmark_result.case_id,
            benchmark_result.context_id,
            benchmark_result.hardware.hash,
            benchmark_result.commit.repository,
        )
        actual_benchmark_result_ids = {
            row.benchmark_result_id for row in actual_history
        }

        assert expected_benchmark_result_ids == actual_benchmark_result_ids


@pytest.mark.parametrize(
    ["strategy_name", "get_baseline_func"],
    [
        ("closest_defaultbranch_ancestor", _get_closest_defaultbranch_ancestor),
        ("parent", _get_parent),
        ("head_of_default", _get_head_of_default),
    ],
)
def test_set_z_scores(
    strategy_name: str, get_baseline_func: Callable[[Commit], Commit]
):
    _, benchmark_results = _fixtures.gen_fake_data()
    assert len(benchmark_results) == len(
        EXPECTED_Z_SCORES[strategy_name]
    ), "you should test all benchmark_results"

    for benchmark_result in benchmark_results:
        baseline_commit = get_baseline_func(benchmark_result.commit)
        if baseline_commit:
            set_z_scores(
                contender_benchmark_results=[benchmark_result],
                baseline_commit=baseline_commit,
            )
        else:
            benchmark_result.z_score = None

    for benchmark_result, expected_z_score in zip(
        benchmark_results, EXPECTED_Z_SCORES[strategy_name]
    ):
        assert_equal_leeway(benchmark_result.z_score, expected_z_score)

    if strategy_name == "head_of_default":
        return

    # Post another result and ensure the previous z-scores didn't change
    new_commit = Commit.create(
        {
            "sha": "77777",
            "branch": "default",
            "fork_point_sha": "77777",
            "parent": "66666",
            "repository": _fixtures.REPO,
            "message": "message",
            "author_name": "author_name",
            "timestamp": datetime(2022, 1, 7),
        }
    )
    benchmark_results.append(
        _fixtures.benchmark_result(
            results=[100, 101, 102],
            commit=new_commit,
            name=benchmark_results[0].case.name,
        )
    )
    expected_z_scores = EXPECTED_Z_SCORES[strategy_name] + [-52.9993797469743]

    for benchmark_result in benchmark_results:
        baseline_commit = get_baseline_func(benchmark_result.commit)
        if baseline_commit:
            set_z_scores(
                contender_benchmark_results=[benchmark_result],
                baseline_commit=baseline_commit,
            )
        else:
            benchmark_result.z_score = None

    for benchmark_result, expected_z_score in zip(benchmark_results, expected_z_scores):
        assert_equal_leeway(benchmark_result.z_score, expected_z_score)


@pytest.mark.parametrize(
    ["strategy_name", "get_baseline_func"],
    [
        ("closest_defaultbranch_ancestor", _get_closest_defaultbranch_ancestor),
        ("parent", _get_parent),
    ],
)
def test_set_z_scores_with_distribution_change(
    strategy_name: str, get_baseline_func: Callable[[Commit], Commit]
):
    expected_z_scores = EXPECTED_Z_SCORES[strategy_name].copy()
    expected_z_scores[6] = 0.0
    if strategy_name == "closest_defaultbranch_ancestor":
        expected_z_scores[7] = -32.90896534380864
    else:
        expected_z_scores[7] = -3.846766028925861
    expected_z_scores[8] = -56.00239876112446
    expected_z_scores[9] = -60.62177826491064
    expected_z_scores[15] = -71.0140831103239

    _, benchmark_results = _fixtures.gen_fake_data()

    # Mark the BenchmarkResult on commit 44444 as a distribution change
    for benchmark_result in benchmark_results:
        if benchmark_result.commit.sha == "44444":
            benchmark_result.update(
                {"change_annotations": {"begins_distribution_change": True}}
            )

    assert len(benchmark_results) == len(
        expected_z_scores
    ), "you should test all benchmark_results"

    for benchmark_result in benchmark_results:
        baseline_commit = get_baseline_func(benchmark_result.commit)
        if baseline_commit:
            set_z_scores(
                contender_benchmark_results=[benchmark_result],
                baseline_commit=baseline_commit,
            )
        else:
            benchmark_result.z_score = None

    for benchmark_result, expected_z_score in zip(benchmark_results, expected_z_scores):
        assert_equal_leeway(benchmark_result.z_score, expected_z_score)


def test_detect_shifts_with_trimmed_estimators():
    np.random.seed(47)
    mean_vals = pd.Series(np.random.randn(100))

    # shift
    mean_vals[50:] += 20
    # outliers
    outlier_indices = [5, 95]
    mean_vals[outlier_indices] = 10

    df = pd.DataFrame(
        {
            "case_id": ["fake-case"] * 100,
            "context_id": ["fake-context"] * 100,
            "hash": ["fake-hash"] * 100,
            "repository": ["fake-repo"] * 100,
            "timestamp": np.arange(100),
            "result_timestamp": np.arange(100),
            "mean": mean_vals,
            # Introduce concept of single value summary (SVS), currently
            # equivalent with mean, the single value representing the outcome
            # of the benchmark result.
            "svs": mean_vals,
        }
    )

    result_df = _detect_shifts_with_trimmed_estimators(df)

    assert list(result_df.columns) == list(df.columns) + ["is_step", "is_outlier"]
    for i, is_outlier in enumerate(result_df.is_outlier):
        if i in outlier_indices:
            assert is_outlier
        else:
            assert not is_outlier

    assert not np.any(result_df.is_step[:50])
    assert result_df.is_step[50]
    assert not np.any(result_df.is_step[51:])
