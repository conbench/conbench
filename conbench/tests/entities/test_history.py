import decimal
from datetime import datetime

from ...entities.commit import Commit
from ...entities.history import get_history, set_z_scores
from ...tests.api import _fixtures

# These correspond to the benchmark_results of _fixtures.gen_fake_data() without modification
EXPECTED_Z_SCORES = [
    None,
    None,
    decimal.Decimal("28.47704269814897756213593267"),
    decimal.Decimal("0.7071067811865475244008443621"),
    decimal.Decimal("2.121320343559642573202533086"),
    decimal.Decimal("13.43502884254440296361604288"),
    decimal.Decimal("1.092874886231796430755831194"),
    decimal.Decimal("-2.185749772463593034070854952"),
    decimal.Decimal("-4.486538431438487624231781225"),
    decimal.Decimal("-4.946696853470236793924906443"),
    None,
    None,
    None,
    None,
    None,
    None,
    decimal.Decimal("-5.982052008847728203870175752"),
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

        actual_history = get_history(
            benchmark_result.case_id,
            benchmark_result.context_id,
            benchmark_result.run.hardware.hash,
            benchmark_result.run.commit.repository,
        )
        actual_benchmark_result_ids = {row.id for row in actual_history}

        assert expected_benchmark_result_ids == actual_benchmark_result_ids

        if benchmark_result.id in actual_benchmark_result_ids:
            # we're on the default branch so the distribution stats should be available
            dist_mean, dist_stddev = [
                (row.rolling_mean, row.rolling_stddev)
                for row in actual_history
                if row.id == benchmark_result.id
            ][0]
            if dist_stddev:
                assert (
                    dist_mean - benchmark_result.mean
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
    expected_z_scores = EXPECTED_Z_SCORES + [
        decimal.Decimal("-52.99938107760084621169252236")
    ]

    set_z_scores(benchmark_results)
    for benchmark_result, expected_z_score in zip(benchmark_results, expected_z_scores):
        assert benchmark_result.z_score == expected_z_score


def test_append_z_scores_with_distribution_change():
    expected_z_scores = EXPECTED_Z_SCORES.copy()
    expected_z_scores[6] = decimal.Decimal("0")
    expected_z_scores[7] = decimal.Decimal("-32.90896534380866857702148049")
    expected_z_scores[8] = decimal.Decimal("-56.00297033789100726112978662")
    expected_z_scores[9] = decimal.Decimal("-60.62177826491070527346062195")
    expected_z_scores[16] = decimal.Decimal("-71.01408311032396903462530000")

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
