from ...entities._comparator import (
    BenchmarkResultComparator,
    BenchmarkResultListComparator,
)


def test_compare_no_change():
    baseline = {
        "benchmark_name": "arrow-compute-scalar-cast-benchmark",
        "case_permutation": "CastUInt32ToInt32Safe/262144/1000",
        "language": "Python",
        "value": "1000",
        "error": None,
        "unit": "i/s",
        "id": "some-benchmark-id-1",
        "batch_id": "some-batch-id-1",
        "run_id": "some-run-id-1",
        "tags": {"tag_one": "one", "tag_two": "two"},
        "z_score": "0.0",
    }
    contender = {
        "benchmark_name": "arrow-compute-scalar-cast-benchmark",
        "case_permutation": "CastUInt32ToInt32Safe/262144/1000",
        "language": "Python",
        "value": "1000",
        "error": None,
        "unit": "i/s",
        "id": "some-benchmark-id-2",
        "batch_id": "some-batch-id-2",
        "run_id": "some-run-id-2",
        "tags": {"tag_one": "one", "tag_two": "two"},
        "z_score": "0.0",
    }

    result = BenchmarkResultComparator(baseline, contender).compare()

    assert result == {
        "unit": "i/s",
        "less_is_better": False,
        "baseline": {
            "benchmark_name": "arrow-compute-scalar-cast-benchmark",
            "case_permutation": "CastUInt32ToInt32Safe/262144/1000",
            "language": "Python",
            "value": 1000.0,
            "error": None,
            "benchmark_result_id": "some-benchmark-id-1",
            "batch_id": "some-batch-id-1",
            "run_id": "some-run-id-1",
            "tags": {"tag_one": "one", "tag_two": "two"},
        },
        "contender": {
            "benchmark_name": "arrow-compute-scalar-cast-benchmark",
            "case_permutation": "CastUInt32ToInt32Safe/262144/1000",
            "language": "Python",
            "value": 1000.0,
            "error": None,
            "benchmark_result_id": "some-benchmark-id-2",
            "batch_id": "some-batch-id-2",
            "run_id": "some-run-id-2",
            "tags": {"tag_one": "one", "tag_two": "two"},
        },
        "analysis": {
            "pairwise": {
                "percent_change": 0.0,
                "percent_threshold": 5.0,
                "regression_indicated": False,
                "improvement_indicated": False,
            },
            "lookback_z_score": {
                "z_threshold": 5.0,
                "z_score": 0.0,
                "regression_indicated": False,
                "improvement_indicated": False,
            },
        },
    }


def test_compare_regression():
    baseline = {
        "benchmark_name": "arrow-compute-scalar-cast-benchmark",
        "case_permutation": "CastUInt32ToInt32Safe/262144/1000",
        "language": "Python",
        "value": "1000",
        "error": None,
        "unit": "i/s",
        "id": "some-benchmark-id-1",
        "batch_id": "some-batch-id-1",
        "run_id": "some-run-id-1",
        "tags": {"tag_one": "one", "tag_two": "two"},
        "z_score": "-6.0",
    }
    contender = {
        "benchmark_name": "arrow-compute-scalar-cast-benchmark",
        "case_permutation": "CastUInt32ToInt32Safe/262144/1000",
        "language": "Python",
        "value": "940",
        "error": None,
        "unit": "i/s",
        "id": "some-benchmark-id-2",
        "batch_id": "some-batch-id-2",
        "run_id": "some-run-id-2",
        "tags": {"tag_one": "one", "tag_two": "two"},
        "z_score": "-6.0",
    }

    result = BenchmarkResultComparator(baseline, contender).compare()

    assert result == {
        "unit": "i/s",
        "less_is_better": False,
        "baseline": {
            "benchmark_name": "arrow-compute-scalar-cast-benchmark",
            "case_permutation": "CastUInt32ToInt32Safe/262144/1000",
            "language": "Python",
            "value": 1000.0,
            "error": None,
            "benchmark_result_id": "some-benchmark-id-1",
            "batch_id": "some-batch-id-1",
            "run_id": "some-run-id-1",
            "tags": {"tag_one": "one", "tag_two": "two"},
        },
        "contender": {
            "benchmark_name": "arrow-compute-scalar-cast-benchmark",
            "case_permutation": "CastUInt32ToInt32Safe/262144/1000",
            "language": "Python",
            "value": 940.0,
            "error": None,
            "benchmark_result_id": "some-benchmark-id-2",
            "batch_id": "some-batch-id-2",
            "run_id": "some-run-id-2",
            "tags": {"tag_one": "one", "tag_two": "two"},
        },
        "analysis": {
            "pairwise": {
                "percent_change": -6.0,
                "percent_threshold": 5.0,
                "regression_indicated": True,
                "improvement_indicated": False,
            },
            "lookback_z_score": {
                "z_threshold": 5.0,
                "z_score": -6.0,
                "regression_indicated": True,
                "improvement_indicated": False,
            },
        },
    }


def test_compare_regression_less_is_better():
    baseline = {
        "benchmark_name": "arrow-compute-scalar-cast-benchmark",
        "case_permutation": "CastUInt32ToInt32Safe/262144/1000",
        "language": "Python",
        "value": "1000",
        "error": None,
        "unit": "s",
        "id": "some-benchmark-id-1",
        "batch_id": "some-batch-id-1",
        "run_id": "some-run-id-1",
        "tags": {"tag_one": "one", "tag_two": "two"},
        "z_score": "-6.0",
    }
    contender = {
        "benchmark_name": "arrow-compute-scalar-cast-benchmark",
        "case_permutation": "CastUInt32ToInt32Safe/262144/1000",
        "language": "Python",
        "value": "1060",
        "error": None,
        "unit": "s",
        "id": "some-benchmark-id-2",
        "batch_id": "some-batch-id-2",
        "run_id": "some-run-id-2",
        "tags": {"tag_one": "one", "tag_two": "two"},
        "z_score": "-6.0",
    }

    result = BenchmarkResultComparator(baseline, contender).compare()

    assert result == {
        "unit": "s",
        "less_is_better": True,
        "baseline": {
            "benchmark_name": "arrow-compute-scalar-cast-benchmark",
            "case_permutation": "CastUInt32ToInt32Safe/262144/1000",
            "language": "Python",
            "value": 1000.0,
            "error": None,
            "benchmark_result_id": "some-benchmark-id-1",
            "batch_id": "some-batch-id-1",
            "run_id": "some-run-id-1",
            "tags": {"tag_one": "one", "tag_two": "two"},
        },
        "contender": {
            "benchmark_name": "arrow-compute-scalar-cast-benchmark",
            "case_permutation": "CastUInt32ToInt32Safe/262144/1000",
            "language": "Python",
            "value": 1060.0,
            "error": None,
            "benchmark_result_id": "some-benchmark-id-2",
            "batch_id": "some-batch-id-2",
            "run_id": "some-run-id-2",
            "tags": {"tag_one": "one", "tag_two": "two"},
        },
        "analysis": {
            "pairwise": {
                "percent_change": -6.0,
                "percent_threshold": 5.0,
                "regression_indicated": True,
                "improvement_indicated": False,
            },
            "lookback_z_score": {
                "z_threshold": 5.0,
                "z_score": -6.0,
                "regression_indicated": True,
                "improvement_indicated": False,
            },
        },
    }


def test_compare_regression_but_under_threshold():
    baseline = {
        "benchmark_name": "arrow-compute-scalar-cast-benchmark",
        "case_permutation": "CastUInt32ToInt32Safe/262144/1000",
        "language": "Python",
        "value": "1000",
        "error": None,
        "unit": "i/s",
        "id": "some-benchmark-id-1",
        "batch_id": "some-batch-id-1",
        "run_id": "some-run-id-1",
        "tags": {"tag_one": "one", "tag_two": "two"},
        "z_score": "-5.0",
    }
    contender = {
        "benchmark_name": "arrow-compute-scalar-cast-benchmark",
        "case_permutation": "CastUInt32ToInt32Safe/262144/1000",
        "language": "Python",
        "value": "950",
        "error": None,
        "unit": "i/s",
        "id": "some-benchmark-id-2",
        "batch_id": "some-batch-id-2",
        "run_id": "some-run-id-2",
        "tags": {"tag_one": "one", "tag_two": "two"},
        "z_score": "-5.0",
    }

    result = BenchmarkResultComparator(baseline, contender).compare()

    assert result == {
        "unit": "i/s",
        "less_is_better": False,
        "baseline": {
            "benchmark_name": "arrow-compute-scalar-cast-benchmark",
            "case_permutation": "CastUInt32ToInt32Safe/262144/1000",
            "language": "Python",
            "value": 1000.0,
            "error": None,
            "benchmark_result_id": "some-benchmark-id-1",
            "batch_id": "some-batch-id-1",
            "run_id": "some-run-id-1",
            "tags": {"tag_one": "one", "tag_two": "two"},
        },
        "contender": {
            "benchmark_name": "arrow-compute-scalar-cast-benchmark",
            "case_permutation": "CastUInt32ToInt32Safe/262144/1000",
            "language": "Python",
            "value": 950.0,
            "error": None,
            "benchmark_result_id": "some-benchmark-id-2",
            "batch_id": "some-batch-id-2",
            "run_id": "some-run-id-2",
            "tags": {"tag_one": "one", "tag_two": "two"},
        },
        "analysis": {
            "pairwise": {
                "percent_change": -5.0,
                "percent_threshold": 5.0,
                "regression_indicated": False,
                "improvement_indicated": False,
            },
            "lookback_z_score": {
                "z_threshold": 5.0,
                "z_score": -5.0,
                "regression_indicated": False,
                "improvement_indicated": False,
            },
        },
    }


def test_compare_regression_custom_threshold_and_threshold_z():
    baseline = {
        "benchmark_name": "arrow-compute-scalar-cast-benchmark",
        "case_permutation": "CastUInt32ToInt32Safe/262144/1000",
        "language": "Python",
        "value": "1000",
        "error": None,
        "unit": "i/s",
        "id": "some-benchmark-id-1",
        "batch_id": "some-batch-id-1",
        "run_id": "some-run-id-1",
        "tags": {"tag_one": "one", "tag_two": "two"},
        "z_score": "-5.0",
    }
    contender = {
        "benchmark_name": "arrow-compute-scalar-cast-benchmark",
        "case_permutation": "CastUInt32ToInt32Safe/262144/1000",
        "language": "Python",
        "value": "950",
        "error": None,
        "unit": "i/s",
        "id": "some-benchmark-id-2",
        "batch_id": "some-batch-id-2",
        "run_id": "some-run-id-2",
        "tags": {"tag_one": "one", "tag_two": "two"},
        "z_score": "-5.0",
    }

    threshold, threshold_z = 4, 1
    result = BenchmarkResultComparator(
        baseline, contender, threshold, threshold_z
    ).compare()

    assert result == {
        "unit": "i/s",
        "less_is_better": False,
        "baseline": {
            "benchmark_name": "arrow-compute-scalar-cast-benchmark",
            "case_permutation": "CastUInt32ToInt32Safe/262144/1000",
            "language": "Python",
            "value": 1000.0,
            "error": None,
            "benchmark_result_id": "some-benchmark-id-1",
            "batch_id": "some-batch-id-1",
            "run_id": "some-run-id-1",
            "tags": {"tag_one": "one", "tag_two": "two"},
        },
        "contender": {
            "benchmark_name": "arrow-compute-scalar-cast-benchmark",
            "case_permutation": "CastUInt32ToInt32Safe/262144/1000",
            "language": "Python",
            "value": 950.0,
            "error": None,
            "benchmark_result_id": "some-benchmark-id-2",
            "batch_id": "some-batch-id-2",
            "run_id": "some-run-id-2",
            "tags": {"tag_one": "one", "tag_two": "two"},
        },
        "analysis": {
            "pairwise": {
                "percent_change": -5.0,
                "percent_threshold": 4.0,
                "regression_indicated": True,
                "improvement_indicated": False,
            },
            "lookback_z_score": {
                "z_threshold": 1.0,
                "z_score": -5.0,
                "regression_indicated": True,
                "improvement_indicated": False,
            },
        },
    }


def test_compare_improvement():
    baseline = {
        "benchmark_name": "arrow-compute-scalar-cast-benchmark",
        "case_permutation": "CastUInt32ToInt32Safe/262144/1000",
        "language": "Python",
        "value": "1000",
        "error": None,
        "unit": "i/s",
        "id": "some-benchmark-id-1",
        "batch_id": "some-batch-id-1",
        "run_id": "some-run-id-1",
        "tags": {"tag_one": "one", "tag_two": "two"},
        "z_score": "6.0",
    }
    contender = {
        "benchmark_name": "arrow-compute-scalar-cast-benchmark",
        "case_permutation": "CastUInt32ToInt32Safe/262144/1000",
        "language": "Python",
        "value": "1060",
        "error": None,
        "unit": "i/s",
        "id": "some-benchmark-id-2",
        "batch_id": "some-batch-id-2",
        "run_id": "some-run-id-2",
        "tags": {"tag_one": "one", "tag_two": "two"},
        "z_score": "6.0",
    }

    result = BenchmarkResultComparator(baseline, contender).compare()

    assert result == {
        "unit": "i/s",
        "less_is_better": False,
        "baseline": {
            "benchmark_name": "arrow-compute-scalar-cast-benchmark",
            "case_permutation": "CastUInt32ToInt32Safe/262144/1000",
            "language": "Python",
            "value": 1000.0,
            "error": None,
            "benchmark_result_id": "some-benchmark-id-1",
            "batch_id": "some-batch-id-1",
            "run_id": "some-run-id-1",
            "tags": {"tag_one": "one", "tag_two": "two"},
        },
        "contender": {
            "benchmark_name": "arrow-compute-scalar-cast-benchmark",
            "case_permutation": "CastUInt32ToInt32Safe/262144/1000",
            "language": "Python",
            "value": 1060.0,
            "error": None,
            "benchmark_result_id": "some-benchmark-id-2",
            "batch_id": "some-batch-id-2",
            "run_id": "some-run-id-2",
            "tags": {"tag_one": "one", "tag_two": "two"},
        },
        "analysis": {
            "pairwise": {
                "percent_change": 6.0,
                "percent_threshold": 5.0,
                "regression_indicated": False,
                "improvement_indicated": True,
            },
            "lookback_z_score": {
                "z_threshold": 5.0,
                "z_score": 6.0,
                "regression_indicated": False,
                "improvement_indicated": True,
            },
        },
    }


def test_compare_improvement_less_is_better():
    baseline = {
        "benchmark_name": "arrow-compute-scalar-cast-benchmark",
        "case_permutation": "CastUInt32ToInt32Safe/262144/1000",
        "language": "Python",
        "value": "1000",
        "error": None,
        "unit": "s",
        "id": "some-benchmark-id-1",
        "batch_id": "some-batch-id-1",
        "run_id": "some-run-id-1",
        "tags": {"tag_one": "one", "tag_two": "two"},
        "z_score": "6.0",
    }
    contender = {
        "benchmark_name": "arrow-compute-scalar-cast-benchmark",
        "case_permutation": "CastUInt32ToInt32Safe/262144/1000",
        "language": "Python",
        "value": "940",
        "error": None,
        "unit": "s",
        "id": "some-benchmark-id-2",
        "batch_id": "some-batch-id-2",
        "run_id": "some-run-id-2",
        "tags": {"tag_one": "one", "tag_two": "two"},
        "z_score": "6.0",
    }

    result = BenchmarkResultComparator(baseline, contender).compare()

    assert result == {
        "unit": "s",
        "less_is_better": True,
        "baseline": {
            "benchmark_name": "arrow-compute-scalar-cast-benchmark",
            "case_permutation": "CastUInt32ToInt32Safe/262144/1000",
            "language": "Python",
            "value": 1000.0,
            "error": None,
            "benchmark_result_id": "some-benchmark-id-1",
            "batch_id": "some-batch-id-1",
            "run_id": "some-run-id-1",
            "tags": {"tag_one": "one", "tag_two": "two"},
        },
        "contender": {
            "benchmark_name": "arrow-compute-scalar-cast-benchmark",
            "case_permutation": "CastUInt32ToInt32Safe/262144/1000",
            "language": "Python",
            "value": 940.0,
            "error": None,
            "benchmark_result_id": "some-benchmark-id-2",
            "batch_id": "some-batch-id-2",
            "run_id": "some-run-id-2",
            "tags": {"tag_one": "one", "tag_two": "two"},
        },
        "analysis": {
            "pairwise": {
                "percent_change": 6.0,
                "percent_threshold": 5.0,
                "regression_indicated": False,
                "improvement_indicated": True,
            },
            "lookback_z_score": {
                "z_threshold": 5.0,
                "z_score": 6.0,
                "regression_indicated": False,
                "improvement_indicated": True,
            },
        },
    }


def test_compare_improvement_but_under_threshold():
    baseline = {
        "benchmark_name": "arrow-compute-scalar-cast-benchmark",
        "case_permutation": "CastUInt32ToInt32Safe/262144/1000",
        "language": "Python",
        "value": "1000",
        "error": None,
        "unit": "i/s",
        "id": "some-benchmark-id-1",
        "batch_id": "some-batch-id-1",
        "run_id": "some-run-id-1",
        "tags": {"tag_one": "one", "tag_two": "two"},
        "z_score": "5.0",
    }
    contender = {
        "benchmark_name": "arrow-compute-scalar-cast-benchmark",
        "case_permutation": "CastUInt32ToInt32Safe/262144/1000",
        "language": "Python",
        "value": "1050",
        "error": None,
        "unit": "i/s",
        "id": "some-benchmark-id-2",
        "batch_id": "some-batch-id-2",
        "run_id": "some-run-id-2",
        "tags": {"tag_one": "one", "tag_two": "two"},
        "z_score": "5.0",
    }

    threshold, threshold_z = 4, 1
    result = BenchmarkResultComparator(
        baseline, contender, threshold, threshold_z
    ).compare()

    assert result == {
        "unit": "i/s",
        "less_is_better": False,
        "baseline": {
            "benchmark_name": "arrow-compute-scalar-cast-benchmark",
            "case_permutation": "CastUInt32ToInt32Safe/262144/1000",
            "language": "Python",
            "value": 1000.0,
            "error": None,
            "benchmark_result_id": "some-benchmark-id-1",
            "batch_id": "some-batch-id-1",
            "run_id": "some-run-id-1",
            "tags": {"tag_one": "one", "tag_two": "two"},
        },
        "contender": {
            "benchmark_name": "arrow-compute-scalar-cast-benchmark",
            "case_permutation": "CastUInt32ToInt32Safe/262144/1000",
            "language": "Python",
            "value": 1050.0,
            "error": None,
            "benchmark_result_id": "some-benchmark-id-2",
            "batch_id": "some-batch-id-2",
            "run_id": "some-run-id-2",
            "tags": {"tag_one": "one", "tag_two": "two"},
        },
        "analysis": {
            "pairwise": {
                "percent_change": 5.0,
                "percent_threshold": 4.0,
                "regression_indicated": False,
                "improvement_indicated": True,
            },
            "lookback_z_score": {
                "z_threshold": 1.0,
                "z_score": 5.0,
                "regression_indicated": False,
                "improvement_indicated": True,
            },
        },
    }


def test_compare_improvement_custom_threshold_and_threshold_z():
    baseline = {
        "benchmark_name": "arrow-compute-scalar-cast-benchmark",
        "case_permutation": "CastUInt32ToInt32Safe/262144/1000",
        "language": "Python",
        "value": "1000",
        "error": None,
        "unit": "i/s",
        "id": "some-benchmark-id-1",
        "batch_id": "some-batch-id-1",
        "run_id": "some-run-id-1",
        "tags": {"tag_one": "one", "tag_two": "two"},
        "z_score": "5.0",
    }
    contender = {
        "benchmark_name": "arrow-compute-scalar-cast-benchmark",
        "case_permutation": "CastUInt32ToInt32Safe/262144/1000",
        "language": "Python",
        "value": "1050",
        "error": None,
        "unit": "i/s",
        "id": "some-benchmark-id-2",
        "batch_id": "some-batch-id-2",
        "run_id": "some-run-id-2",
        "tags": {"tag_one": "one", "tag_two": "two"},
        "z_score": "5.0",
    }

    result = BenchmarkResultComparator(baseline, contender).compare()

    assert result == {
        "unit": "i/s",
        "less_is_better": False,
        "baseline": {
            "benchmark_name": "arrow-compute-scalar-cast-benchmark",
            "case_permutation": "CastUInt32ToInt32Safe/262144/1000",
            "language": "Python",
            "value": 1000.0,
            "error": None,
            "benchmark_result_id": "some-benchmark-id-1",
            "batch_id": "some-batch-id-1",
            "run_id": "some-run-id-1",
            "tags": {"tag_one": "one", "tag_two": "two"},
        },
        "contender": {
            "benchmark_name": "arrow-compute-scalar-cast-benchmark",
            "case_permutation": "CastUInt32ToInt32Safe/262144/1000",
            "language": "Python",
            "value": 1050.0,
            "error": None,
            "benchmark_result_id": "some-benchmark-id-2",
            "batch_id": "some-batch-id-2",
            "run_id": "some-run-id-2",
            "tags": {"tag_one": "one", "tag_two": "two"},
        },
        "analysis": {
            "pairwise": {
                "percent_change": 5.0,
                "percent_threshold": 5.0,
                "regression_indicated": False,
                "improvement_indicated": False,
            },
            "lookback_z_score": {
                "z_threshold": 5.0,
                "z_score": 5.0,
                "regression_indicated": False,
                "improvement_indicated": False,
            },
        },
    }


def test_compare_list():
    pairs = {
        "some-case-id-1": {
            "baseline": {
                "benchmark_name": "math",
                "case_permutation": "addition",
                "language": "Python",
                "unit": "s",
                "value": "0.036369",
                "error": None,
                "id": "some-benchmark-id-1",
                "batch_id": "some-batch-id-1",
                "run_id": "some-run-id-1",
                "tags": {"tag_one": "one", "tag_two": "two"},
                "z_score": "0.0",
            },
            "contender": {
                "benchmark_name": "math",
                "case_permutation": "addition",
                "language": "Python",
                "unit": "s",
                "value": "0.036369",
                "error": None,
                "id": "some-benchmark-id-2",
                "batch_id": "some-batch-id-2",
                "run_id": "some-run-id-2",
                "tags": {"tag_one": "one", "tag_two": "two"},
                "z_score": "0.0",
            },
        },
        "some-case-id-2": {
            "baseline": {
                "benchmark_name": "math",
                "case_permutation": "subtraction",
                "language": "Python",
                "unit": "s",
                "value": "1.036369",
                "error": None,
                "id": "some-benchmark-id-3",
                "batch_id": "some-batch-id-1",
                "run_id": "some-run-id-1",
                "tags": {"tag_one": "1", "tag_two": "2"},
                "z_score": "-6.0",
            },
            "contender": {
                "benchmark_name": "math",
                "case_permutation": "subtraction",
                "language": "Python",
                "unit": "s",
                "value": "0.036369",
                "error": None,
                "id": "some-benchmark-id-4",
                "batch_id": "some-batch-id-2",
                "run_id": "some-run-id-2",
                "tags": {"tag_one": "1", "tag_two": "2"},
                "z_score": "6.0",
            },
        },
    }

    result = BenchmarkResultListComparator(pairs).compare()

    assert list(result) == [
        {
            "unit": "s",
            "less_is_better": True,
            "baseline": {
                "benchmark_name": "math",
                "case_permutation": "addition",
                "language": "Python",
                "value": 0.03637,
                "error": None,
                "benchmark_result_id": "some-benchmark-id-1",
                "batch_id": "some-batch-id-1",
                "run_id": "some-run-id-1",
                "tags": {"tag_one": "one", "tag_two": "two"},
            },
            "contender": {
                "benchmark_name": "math",
                "case_permutation": "addition",
                "language": "Python",
                "value": 0.03637,
                "error": None,
                "benchmark_result_id": "some-benchmark-id-2",
                "batch_id": "some-batch-id-2",
                "run_id": "some-run-id-2",
                "tags": {"tag_one": "one", "tag_two": "two"},
            },
            "analysis": {
                "pairwise": {
                    "percent_change": 0.0,
                    "percent_threshold": 5.0,
                    "regression_indicated": False,
                    "improvement_indicated": False,
                },
                "lookback_z_score": {
                    "z_threshold": 5.0,
                    "z_score": 0.0,
                    "regression_indicated": False,
                    "improvement_indicated": False,
                },
            },
        },
        {
            "unit": "s",
            "less_is_better": True,
            "baseline": {
                "benchmark_name": "math",
                "case_permutation": "subtraction",
                "language": "Python",
                "value": 1.036,
                "error": None,
                "benchmark_result_id": "some-benchmark-id-3",
                "batch_id": "some-batch-id-1",
                "run_id": "some-run-id-1",
                "tags": {"tag_one": "1", "tag_two": "2"},
            },
            "contender": {
                "benchmark_name": "math",
                "case_permutation": "subtraction",
                "language": "Python",
                "value": 0.03637,
                "error": None,
                "benchmark_result_id": "some-benchmark-id-4",
                "batch_id": "some-batch-id-2",
                "run_id": "some-run-id-2",
                "tags": {"tag_one": "1", "tag_two": "2"},
            },
            "analysis": {
                "pairwise": {
                    "percent_change": 96.49,
                    "percent_threshold": 5.0,
                    "regression_indicated": False,
                    "improvement_indicated": True,
                },
                "lookback_z_score": {
                    "z_threshold": 5.0,
                    "z_score": 6.0,
                    "regression_indicated": False,
                    "improvement_indicated": True,
                },
            },
        },
    ]


def test_compare_list_missing_contender():
    pairs = {
        "some-case-id-1": {
            "baseline": {
                "benchmark_name": "math",
                "case_permutation": "addition",
                "language": "Python",
                "unit": "s",
                "value": "0.036369",
                "error": None,
                "id": "some-benchmark-id-1",
                "batch_id": "some-batch-id-1",
                "run_id": "some-run-id-1",
                "tags": {"tag_one": "one", "tag_two": "two"},
                "z_score": "0.0",
            },
        },
        "some-case-id-2": {
            "baseline": {
                "benchmark_name": "math",
                "case_permutation": "subtraction",
                "language": "Python",
                "unit": "s",
                "value": "1.036369",
                "error": None,
                "id": "some-benchmark-id-3",
                "batch_id": "some-batch-id-1",
                "run_id": "some-run-id-1",
                "tags": {"tag_one": "1", "tag_two": "2"},
                "z_score": "0.0",
            },
            "contender": {
                "benchmark_name": "math",
                "case_permutation": "subtraction",
                "language": "Python",
                "unit": "s",
                "value": "0.036369",
                "error": None,
                "id": "some-benchmark-id-4",
                "batch_id": "some-batch-id-2",
                "run_id": "some-run-id-2",
                "tags": {"tag_one": "1", "tag_two": "2"},
                "z_score": "0.0",
            },
        },
    }

    result = BenchmarkResultListComparator(pairs).compare()

    assert list(result) == [
        {
            "unit": "s",
            "less_is_better": True,
            "baseline": {
                "benchmark_name": "math",
                "case_permutation": "addition",
                "language": "Python",
                "value": 0.03637,
                "error": None,
                "benchmark_result_id": "some-benchmark-id-1",
                "batch_id": "some-batch-id-1",
                "run_id": "some-run-id-1",
                "tags": {"tag_one": "one", "tag_two": "two"},
            },
            "contender": None,
            "analysis": {
                "pairwise": {
                    "percent_change": 0.0,
                    "percent_threshold": 5.0,
                    "regression_indicated": False,
                    "improvement_indicated": False,
                },
                "lookback_z_score": {
                    "z_threshold": 5.0,
                    "z_score": None,
                    "regression_indicated": False,
                    "improvement_indicated": False,
                },
            },
        },
        {
            "unit": "s",
            "less_is_better": True,
            "baseline": {
                "benchmark_name": "math",
                "case_permutation": "subtraction",
                "language": "Python",
                "value": 1.036,
                "error": None,
                "benchmark_result_id": "some-benchmark-id-3",
                "batch_id": "some-batch-id-1",
                "run_id": "some-run-id-1",
                "tags": {"tag_one": "1", "tag_two": "2"},
            },
            "contender": {
                "benchmark_name": "math",
                "case_permutation": "subtraction",
                "language": "Python",
                "value": 0.03637,
                "error": None,
                "benchmark_result_id": "some-benchmark-id-4",
                "batch_id": "some-batch-id-2",
                "run_id": "some-run-id-2",
                "tags": {"tag_one": "1", "tag_two": "2"},
            },
            "analysis": {
                "pairwise": {
                    "percent_change": 96.49,
                    "percent_threshold": 5.0,
                    "regression_indicated": False,
                    "improvement_indicated": True,
                },
                "lookback_z_score": {
                    "z_threshold": 5.0,
                    "z_score": 0.0,
                    "regression_indicated": False,
                    "improvement_indicated": False,
                },
            },
        },
    ]


def test_compare_list_empty_contender():
    pairs = {
        "some-case-id-1": {
            "baseline": {
                "benchmark_name": "math",
                "case_permutation": "addition",
                "language": "Python",
                "unit": "s",
                "value": "0.036369",
                "error": None,
                "id": "some-benchmark-id-1",
                "batch_id": "some-batch-id-1",
                "run_id": "some-run-id-1",
                "tags": {"tag_one": "one", "tag_two": "two"},
                "z_score": "0.0",
            },
            "contender": {},
        },
        "some-case-id-2": {
            "baseline": {
                "benchmark_name": "math",
                "case_permutation": "subtraction",
                "language": "Python",
                "unit": "s",
                "value": "1.036369",
                "error": None,
                "id": "some-benchmark-id-3",
                "batch_id": "some-batch-id-1",
                "run_id": "some-run-id-1",
                "tags": {"tag_one": "1", "tag_two": "2"},
                "z_score": "0.0",
            },
            "contender": {
                "benchmark_name": "math",
                "case_permutation": "subtraction",
                "language": "Python",
                "unit": "s",
                "value": "0.036369",
                "error": None,
                "id": "some-benchmark-id-4",
                "batch_id": "some-batch-id-2",
                "run_id": "some-run-id-2",
                "tags": {"tag_one": "1", "tag_two": "2"},
                "z_score": "0.0",
            },
        },
    }

    result = BenchmarkResultListComparator(pairs).compare()

    assert list(result) == [
        {
            "unit": "s",
            "less_is_better": True,
            "baseline": {
                "benchmark_name": "math",
                "case_permutation": "addition",
                "language": "Python",
                "value": 0.03637,
                "error": None,
                "benchmark_result_id": "some-benchmark-id-1",
                "batch_id": "some-batch-id-1",
                "run_id": "some-run-id-1",
                "tags": {"tag_one": "one", "tag_two": "two"},
            },
            "contender": None,
            "analysis": {
                "pairwise": {
                    "percent_change": 0.0,
                    "percent_threshold": 5.0,
                    "regression_indicated": False,
                    "improvement_indicated": False,
                },
                "lookback_z_score": {
                    "z_threshold": 5.0,
                    "z_score": None,
                    "regression_indicated": False,
                    "improvement_indicated": False,
                },
            },
        },
        {
            "unit": "s",
            "less_is_better": True,
            "baseline": {
                "benchmark_name": "math",
                "case_permutation": "subtraction",
                "language": "Python",
                "value": 1.036,
                "error": None,
                "benchmark_result_id": "some-benchmark-id-3",
                "batch_id": "some-batch-id-1",
                "run_id": "some-run-id-1",
                "tags": {"tag_one": "1", "tag_two": "2"},
            },
            "contender": {
                "benchmark_name": "math",
                "case_permutation": "subtraction",
                "language": "Python",
                "value": 0.03637,
                "error": None,
                "benchmark_result_id": "some-benchmark-id-4",
                "batch_id": "some-batch-id-2",
                "run_id": "some-run-id-2",
                "tags": {"tag_one": "1", "tag_two": "2"},
            },
            "analysis": {
                "pairwise": {
                    "percent_change": 96.49,
                    "percent_threshold": 5.0,
                    "regression_indicated": False,
                    "improvement_indicated": True,
                },
                "lookback_z_score": {
                    "z_threshold": 5.0,
                    "z_score": 0.0,
                    "regression_indicated": False,
                    "improvement_indicated": False,
                },
            },
        },
    ]


def test_compare_list_missing_baseline():
    pairs = {
        "some-case-id-1": {
            "contender": {
                "benchmark_name": "math",
                "case_permutation": "addition",
                "language": "Python",
                "unit": "s",
                "value": "0.036369",
                "error": None,
                "id": "some-benchmark-id-2",
                "batch_id": "some-batch-id-2",
                "run_id": "some-run-id-2",
                "tags": {"tag_one": "one", "tag_two": "two"},
                "z_score": "0.0",
            },
        },
        "some-case-id-2": {
            "baseline": {
                "benchmark_name": "math",
                "case_permutation": "subtraction",
                "language": "Python",
                "unit": "s",
                "value": "1.036369",
                "error": None,
                "id": "some-benchmark-id-3",
                "batch_id": "some-batch-id-1",
                "run_id": "some-run-id-1",
                "tags": {"tag_one": "1", "tag_two": "2"},
                "z_score": "0.0",
            },
            "contender": {
                "benchmark_name": "math",
                "case_permutation": "subtraction",
                "language": "Python",
                "unit": "s",
                "value": "0.036369",
                "error": None,
                "id": "some-benchmark-id-4",
                "batch_id": "some-batch-id-2",
                "run_id": "some-run-id-2",
                "tags": {"tag_one": "1", "tag_two": "2"},
                "z_score": "0.0",
            },
        },
    }

    result = BenchmarkResultListComparator(pairs).compare()

    assert list(result) == [
        {
            "unit": "s",
            "less_is_better": True,
            "baseline": None,
            "contender": {
                "benchmark_name": "math",
                "case_permutation": "addition",
                "language": "Python",
                "value": 0.03637,
                "error": None,
                "benchmark_result_id": "some-benchmark-id-2",
                "batch_id": "some-batch-id-2",
                "run_id": "some-run-id-2",
                "tags": {"tag_one": "one", "tag_two": "two"},
            },
            "analysis": {
                "pairwise": {
                    "percent_change": 0.0,
                    "percent_threshold": 5.0,
                    "regression_indicated": False,
                    "improvement_indicated": False,
                },
                "lookback_z_score": {
                    "z_threshold": 5.0,
                    "z_score": 0.0,
                    "regression_indicated": False,
                    "improvement_indicated": False,
                },
            },
        },
        {
            "unit": "s",
            "less_is_better": True,
            "baseline": {
                "benchmark_name": "math",
                "case_permutation": "subtraction",
                "language": "Python",
                "value": 1.036,
                "error": None,
                "benchmark_result_id": "some-benchmark-id-3",
                "batch_id": "some-batch-id-1",
                "run_id": "some-run-id-1",
                "tags": {"tag_one": "1", "tag_two": "2"},
            },
            "contender": {
                "benchmark_name": "math",
                "case_permutation": "subtraction",
                "language": "Python",
                "value": 0.03637,
                "error": None,
                "benchmark_result_id": "some-benchmark-id-4",
                "batch_id": "some-batch-id-2",
                "run_id": "some-run-id-2",
                "tags": {"tag_one": "1", "tag_two": "2"},
            },
            "analysis": {
                "pairwise": {
                    "percent_change": 96.49,
                    "percent_threshold": 5.0,
                    "regression_indicated": False,
                    "improvement_indicated": True,
                },
                "lookback_z_score": {
                    "z_threshold": 5.0,
                    "z_score": 0.0,
                    "regression_indicated": False,
                    "improvement_indicated": False,
                },
            },
        },
    ]


def test_compare_list_empty_baseline():
    pairs = {
        "some-case-id-1": {
            "baseline": {},
            "contender": {
                "benchmark_name": "math",
                "case_permutation": "addition",
                "language": "Python",
                "unit": "s",
                "value": 0.036369,
                "error": None,
                "id": "some-benchmark-id-2",
                "batch_id": "some-batch-id-2",
                "run_id": "some-run-id-2",
                "tags": {"tag_one": "one", "tag_two": "two"},
                "z_score": "0.0",
            },
        },
        "some-case-id-2": {
            "baseline": {
                "benchmark_name": "math",
                "case_permutation": "subtraction",
                "language": "Python",
                "unit": "s",
                "value": 1.036369,
                "error": None,
                "id": "some-benchmark-id-3",
                "batch_id": "some-batch-id-1",
                "run_id": "some-run-id-1",
                "tags": {"tag_one": "1", "tag_two": "2"},
                "z_score": "0.0",
            },
            "contender": {
                "benchmark_name": "math",
                "case_permutation": "subtraction",
                "language": "Python",
                "unit": "s",
                "value": 0.036369,
                "error": None,
                "id": "some-benchmark-id-4",
                "batch_id": "some-batch-id-2",
                "run_id": "some-run-id-2",
                "tags": {"tag_one": "1", "tag_two": "2"},
                "z_score": "0.0",
            },
        },
    }

    result = BenchmarkResultListComparator(pairs).compare()

    assert list(result) == [
        {
            "unit": "s",
            "less_is_better": True,
            "baseline": None,
            "contender": {
                "benchmark_name": "math",
                "case_permutation": "addition",
                "language": "Python",
                "value": 0.03637,
                "error": None,
                "benchmark_result_id": "some-benchmark-id-2",
                "batch_id": "some-batch-id-2",
                "run_id": "some-run-id-2",
                "tags": {"tag_one": "one", "tag_two": "two"},
            },
            "analysis": {
                "pairwise": {
                    "percent_change": 0.0,
                    "percent_threshold": 5.0,
                    "regression_indicated": False,
                    "improvement_indicated": False,
                },
                "lookback_z_score": {
                    "z_threshold": 5.0,
                    "z_score": 0.0,
                    "regression_indicated": False,
                    "improvement_indicated": False,
                },
            },
        },
        {
            "unit": "s",
            "less_is_better": True,
            "baseline": {
                "benchmark_name": "math",
                "case_permutation": "subtraction",
                "language": "Python",
                "value": 1.036,
                "error": None,
                "benchmark_result_id": "some-benchmark-id-3",
                "batch_id": "some-batch-id-1",
                "run_id": "some-run-id-1",
                "tags": {"tag_one": "1", "tag_two": "2"},
            },
            "contender": {
                "benchmark_name": "math",
                "case_permutation": "subtraction",
                "language": "Python",
                "value": 0.03637,
                "error": None,
                "benchmark_result_id": "some-benchmark-id-4",
                "batch_id": "some-batch-id-2",
                "run_id": "some-run-id-2",
                "tags": {"tag_one": "1", "tag_two": "2"},
            },
            "analysis": {
                "pairwise": {
                    "percent_change": 96.49,
                    "percent_threshold": 5.0,
                    "regression_indicated": False,
                    "improvement_indicated": True,
                },
                "lookback_z_score": {
                    "z_threshold": 5.0,
                    "z_score": 0.0,
                    "regression_indicated": False,
                    "improvement_indicated": False,
                },
            },
        },
    ]


def test_compare_list_empty_pair():
    pairs = {
        "some-case-id-1": {
            "baseline": {},
            "contender": {},
        },
        "some-case-id-2": {
            "baseline": {},
            "contender": {},
        },
    }

    result = BenchmarkResultListComparator(pairs).compare()

    assert list(result) == [
        {
            "unit": "unknown",
            "less_is_better": True,
            "baseline": None,
            "contender": None,
            "analysis": {
                "pairwise": {
                    "percent_change": 0.0,
                    "percent_threshold": 5.0,
                    "regression_indicated": False,
                    "improvement_indicated": False,
                },
                "lookback_z_score": {
                    "z_threshold": 5.0,
                    "z_score": None,
                    "regression_indicated": False,
                    "improvement_indicated": False,
                },
            },
        },
        {
            "unit": "unknown",
            "less_is_better": True,
            "baseline": None,
            "contender": None,
            "analysis": {
                "pairwise": {
                    "percent_change": 0.0,
                    "percent_threshold": 5.0,
                    "regression_indicated": False,
                    "improvement_indicated": False,
                },
                "lookback_z_score": {
                    "z_threshold": 5.0,
                    "z_score": None,
                    "regression_indicated": False,
                    "improvement_indicated": False,
                },
            },
        },
    ]
