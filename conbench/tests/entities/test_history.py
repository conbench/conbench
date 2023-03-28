from datetime import datetime

import numpy as np
import pandas as pd

from ...entities.commit import Commit
from ...entities.history import (
    _detect_shifts_with_trimmed_estimators,
    _to_float,
    get_history_for_cchr,
    set_z_scores,
)
from ...tests.api import _fixtures

# These correspond to the benchmark_results of _fixtures.gen_fake_data() without modification
EXPECTED_Z_SCORES = [
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
]


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
    for benchmark_result, expected_benchmark_results_ixs, expected_z_score in zip(
        benchmark_results, all_expected_benchmark_results_ixs, EXPECTED_Z_SCORES
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

        if benchmark_result.id in actual_benchmark_result_ids:
            # we're on the default branch so the distribution stats should be available
            dist_mean, dist_stddev = [
                (
                    _to_float(row.zscorestats.rolling_mean),
                    _to_float(row.zscorestats.rolling_stddev),
                )
                for row in actual_history
                if row.benchmark_result_id == benchmark_result.id
            ][0]
            if dist_stddev:
                assert (
                    dist_mean - _to_float(benchmark_result.mean)
                ) / dist_stddev == expected_z_score
            else:
                assert expected_z_score is None


def test_append_z_scores():
    _, benchmark_results = _fixtures.gen_fake_data()
    assert len(benchmark_results) == len(
        EXPECTED_Z_SCORES
    ), "you should test all benchmark_results"

    set_z_scores(benchmark_results)
    for benchmark_result, expected_z_score in zip(benchmark_results, EXPECTED_Z_SCORES):
        assert benchmark_result.z_score == expected_z_score

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
    expected_z_scores = EXPECTED_Z_SCORES + [-52.99938107760085]

    set_z_scores(benchmark_results)
    for benchmark_result, expected_z_score in zip(benchmark_results, expected_z_scores):
        assert benchmark_result.z_score == expected_z_score


def test_append_z_scores_with_distribution_change():
    expected_z_scores = EXPECTED_Z_SCORES.copy()
    expected_z_scores[6] = 0.0
    expected_z_scores[7] = -32.90896534380864
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

    set_z_scores(benchmark_results)
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
