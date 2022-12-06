from ...entities.history import get_history
from ...tests.api import _fixtures


def test_history():
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

        actual_history = get_history(
            benchmark_result.case_id,
            benchmark_result.context_id,
            benchmark_result.run.hardware.hash,
            benchmark_result.run.commit.repository,
        )
        actual_benchmark_result_ids = {row[0] for row in actual_history}

        assert expected_benchmark_result_ids == actual_benchmark_result_ids
