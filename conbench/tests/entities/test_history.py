from datetime import datetime
from typing import Callable

import numpy as np
import pandas as pd
import pytest
import sqlalchemy as s

from ...db import Session
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


# These correspond to the benchmark_results of _fixtures.gen_fake_data() without modification
EXPECTED_Z_SCORES = {
    "closest_defaultbranch_ancestor": [
        None,
        None,
        28.477042698148946,
        0.7071067811865444,
        2.1213203435596393,
        13.435028842544385,
        1.0928748862317967,
        -2.1857497724635935,
        -4.486538431438488,
        -4.946696853470237,
        None,
        None,
        None,
        None,
        None,
        None,
        -5.98205200884773,
    ],
    "parent": [
        None,
        None,
        28.477042698148946,
        0.7071067811865444,
        2.1213203435596393,
        13.435028842544385,
        1.0928748862317967,
        -2.8246140882627757,
        -4.486538431438488,
        -4.946696853470237,
        None,
        None,
        None,
        None,
        None,
        None,
        -5.98205200884773,
    ],
    "head_of_default": [
        0.6624922329803099,
        0.6082883205453794,
        1.7268570607654594,
        0.6624922329803099,
        0.7166961454152404,
        1.150327444894684,
        1.150327444894684,
        0.12045310863100521,
        -0.602265543155026,
        -0.7468094903278821,
        None,
        None,
        None,
        None,
        None,
        None,
        -1.0720329649374651,
    ],
}


def test_get_history():
    _, benchmark_results = _fixtures.gen_fake_data()
    all_expected_benchmark_results_ixs = [
        [0, 1, 5, 8, 9, 16],
        [0, 1, 5, 8, 9, 16],
        [0, 1, 5, 8, 9, 16],
        [0, 1, 5, 8, 9, 16],
        [0, 1, 5, 8, 9, 16],
        [0, 1, 5, 8, 9, 16],
        [0, 1, 5, 8, 9, 16],
        [0, 1, 5, 8, 9, 16],
        [0, 1, 5, 8, 9, 16],
        [0, 1, 5, 8, 9, 16],
        [],  # only errors in the building
        [],  # no branch information
        [],  # no branch information
        [13],
        [14],
        [15],
        [0, 1, 5, 8, 9, 16],
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
            benchmark_result.case_id,
            benchmark_result.context_id,
            benchmark_result.run.hardware.hash,
            benchmark_result.run.commit.repository,
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
        baseline_commit = get_baseline_func(benchmark_result.run.commit)
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
        assert benchmark_result.z_score == expected_z_score

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
    expected_z_scores = EXPECTED_Z_SCORES[strategy_name] + [-52.99938107760085]

    for benchmark_result in benchmark_results:
        baseline_commit = get_baseline_func(benchmark_result.run.commit)
        if baseline_commit:
            set_z_scores(
                contender_benchmark_results=[benchmark_result],
                baseline_commit=baseline_commit,
            )
        else:
            benchmark_result.z_score = None

    for benchmark_result, expected_z_score in zip(benchmark_results, expected_z_scores):
        assert benchmark_result.z_score == expected_z_score


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
    expected_z_scores[8] = -56.00297033789095
    expected_z_scores[9] = -60.62177826491064
    expected_z_scores[16] = -71.0140831103239

    _, benchmark_results = _fixtures.gen_fake_data()

    # Mark the BenchmarkResult on commit 44444 as a distribution change
    for benchmark_result in benchmark_results:
        if benchmark_result.run.commit.sha == "44444":
            benchmark_result.update(
                {"change_annotations": {"begins_distribution_change": True}}
            )

    assert len(benchmark_results) == len(
        expected_z_scores
    ), "you should test all benchmark_results"

    for benchmark_result in benchmark_results:
        baseline_commit = get_baseline_func(benchmark_result.run.commit)
        if baseline_commit:
            set_z_scores(
                contender_benchmark_results=[benchmark_result],
                baseline_commit=baseline_commit,
            )
        else:
            benchmark_result.z_score = None

    for benchmark_result, expected_z_score in zip(benchmark_results, expected_z_scores):
        assert benchmark_result.z_score == expected_z_score


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
