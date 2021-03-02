from ...compare import BenchmarkComparator, BenchmarkListComparator


def test_compare_no_change():
    baseline = {
        "batch": "arrow-compute-scalar-cast-benchmark",
        "benchmark": "CastUInt32ToInt32Safe/262144/1000",
        "value": "1000",
        "unit": "i/s",
        "id": "some-benchmark-id-1",
        "batch_id": "some-batch-id-1",
        "run_id": "some-run-id-1",
    }
    contender = {
        "batch": "arrow-compute-scalar-cast-benchmark",
        "benchmark": "CastUInt32ToInt32Safe/262144/1000",
        "value": "1000",
        "unit": "i/s",
        "id": "some-benchmark-id-2",
        "batch_id": "some-batch-id-2",
        "run_id": "some-run-id-2",
    }

    result = BenchmarkComparator(baseline, contender).compare()
    formatted = BenchmarkComparator(baseline, contender).formatted()

    assert result == {
        "batch": "arrow-compute-scalar-cast-benchmark",
        "benchmark": "CastUInt32ToInt32Safe/262144/1000",
        "change": "0.000",
        "regression": False,
        "improvement": False,
        "baseline": "1000.000",
        "contender": "1000.000",
        "baseline_id": "some-benchmark-id-1",
        "contender_id": "some-benchmark-id-2",
        "baseline_batch_id": "some-batch-id-1",
        "contender_batch_id": "some-batch-id-2",
        "baseline_run_id": "some-run-id-1",
        "contender_run_id": "some-run-id-2",
        "unit": "i/s",
        "less_is_better": False,
    }
    assert formatted == {
        "batch": "arrow-compute-scalar-cast-benchmark",
        "benchmark": "CastUInt32ToInt32Safe/262144/1000",
        "change": "0.000%",
        "regression": False,
        "improvement": False,
        "baseline": "1.000K i/s",
        "contender": "1.000K i/s",
        "baseline_id": "some-benchmark-id-1",
        "contender_id": "some-benchmark-id-2",
        "baseline_batch_id": "some-batch-id-1",
        "contender_batch_id": "some-batch-id-2",
        "baseline_run_id": "some-run-id-1",
        "contender_run_id": "some-run-id-2",
        "unit": "i/s",
        "less_is_better": False,
    }


def test_compare_regression():
    baseline = {
        "batch": "arrow-compute-scalar-cast-benchmark",
        "benchmark": "CastUInt32ToInt32Safe/262144/1000",
        "value": "1000",
        "unit": "i/s",
        "id": "some-benchmark-id-1",
        "batch_id": "some-batch-id-1",
        "run_id": "some-run-id-1",
    }
    contender = {
        "batch": "arrow-compute-scalar-cast-benchmark",
        "benchmark": "CastUInt32ToInt32Safe/262144/1000",
        "value": "940",
        "unit": "i/s",
        "id": "some-benchmark-id-2",
        "batch_id": "some-batch-id-2",
        "run_id": "some-run-id-2",
    }

    result = BenchmarkComparator(baseline, contender).compare()
    formatted = BenchmarkComparator(baseline, contender).formatted()

    assert result == {
        "batch": "arrow-compute-scalar-cast-benchmark",
        "benchmark": "CastUInt32ToInt32Safe/262144/1000",
        "change": "-6.000",
        "regression": True,
        "improvement": False,
        "baseline": "1000.000",
        "contender": "940.000",
        "baseline_id": "some-benchmark-id-1",
        "contender_id": "some-benchmark-id-2",
        "baseline_batch_id": "some-batch-id-1",
        "contender_batch_id": "some-batch-id-2",
        "baseline_run_id": "some-run-id-1",
        "contender_run_id": "some-run-id-2",
        "unit": "i/s",
        "less_is_better": False,
    }
    assert formatted == {
        "batch": "arrow-compute-scalar-cast-benchmark",
        "benchmark": "CastUInt32ToInt32Safe/262144/1000",
        "change": "-6.000%",
        "regression": True,
        "improvement": False,
        "baseline": "1.000K i/s",
        "contender": "940 i/s",
        "baseline_id": "some-benchmark-id-1",
        "contender_id": "some-benchmark-id-2",
        "baseline_batch_id": "some-batch-id-1",
        "contender_batch_id": "some-batch-id-2",
        "baseline_run_id": "some-run-id-1",
        "contender_run_id": "some-run-id-2",
        "unit": "i/s",
        "less_is_better": False,
    }


def test_compare_regression_but_under_threshold():
    baseline = {
        "batch": "arrow-compute-scalar-cast-benchmark",
        "benchmark": "CastUInt32ToInt32Safe/262144/1000",
        "value": "1000",
        "unit": "i/s",
        "id": "some-benchmark-id-1",
        "batch_id": "some-batch-id-1",
        "run_id": "some-run-id-1",
    }
    contender = {
        "batch": "arrow-compute-scalar-cast-benchmark",
        "benchmark": "CastUInt32ToInt32Safe/262144/1000",
        "value": "950",
        "unit": "i/s",
        "id": "some-benchmark-id-2",
        "batch_id": "some-batch-id-2",
        "run_id": "some-run-id-2",
    }

    result = BenchmarkComparator(baseline, contender).compare()
    formatted = BenchmarkComparator(baseline, contender).formatted()

    assert result == {
        "batch": "arrow-compute-scalar-cast-benchmark",
        "benchmark": "CastUInt32ToInt32Safe/262144/1000",
        "change": "-5.000",
        "regression": False,
        "improvement": False,
        "baseline": "1000.000",
        "contender": "950.000",
        "baseline_id": "some-benchmark-id-1",
        "contender_id": "some-benchmark-id-2",
        "baseline_batch_id": "some-batch-id-1",
        "contender_batch_id": "some-batch-id-2",
        "baseline_run_id": "some-run-id-1",
        "contender_run_id": "some-run-id-2",
        "unit": "i/s",
        "less_is_better": False,
    }
    assert formatted == {
        "batch": "arrow-compute-scalar-cast-benchmark",
        "benchmark": "CastUInt32ToInt32Safe/262144/1000",
        "change": "-5.000%",
        "regression": False,
        "improvement": False,
        "baseline": "1.000K i/s",
        "contender": "950 i/s",
        "baseline_id": "some-benchmark-id-1",
        "contender_id": "some-benchmark-id-2",
        "baseline_batch_id": "some-batch-id-1",
        "contender_batch_id": "some-batch-id-2",
        "baseline_run_id": "some-run-id-1",
        "contender_run_id": "some-run-id-2",
        "unit": "i/s",
        "less_is_better": False,
    }


def test_compare_improvement():
    baseline = {
        "batch": "arrow-compute-scalar-cast-benchmark",
        "benchmark": "CastUInt32ToInt32Safe/262144/1000",
        "value": "1000",
        "unit": "i/s",
        "id": "some-benchmark-id-1",
        "batch_id": "some-batch-id-1",
        "run_id": "some-run-id-1",
    }
    contender = {
        "batch": "arrow-compute-scalar-cast-benchmark",
        "benchmark": "CastUInt32ToInt32Safe/262144/1000",
        "value": "1060",
        "unit": "i/s",
        "id": "some-benchmark-id-2",
        "batch_id": "some-batch-id-2",
        "run_id": "some-run-id-2",
    }

    result = BenchmarkComparator(baseline, contender).compare()
    formatted = BenchmarkComparator(baseline, contender).formatted()

    assert result == {
        "batch": "arrow-compute-scalar-cast-benchmark",
        "benchmark": "CastUInt32ToInt32Safe/262144/1000",
        "change": "6.000",
        "regression": False,
        "improvement": True,
        "baseline": "1000.000",
        "contender": "1060.000",
        "baseline_id": "some-benchmark-id-1",
        "contender_id": "some-benchmark-id-2",
        "baseline_batch_id": "some-batch-id-1",
        "contender_batch_id": "some-batch-id-2",
        "baseline_run_id": "some-run-id-1",
        "contender_run_id": "some-run-id-2",
        "unit": "i/s",
        "less_is_better": False,
    }
    assert formatted == {
        "batch": "arrow-compute-scalar-cast-benchmark",
        "benchmark": "CastUInt32ToInt32Safe/262144/1000",
        "change": "6.000%",
        "regression": False,
        "improvement": True,
        "baseline": "1.000K i/s",
        "contender": "1.060K i/s",
        "baseline_id": "some-benchmark-id-1",
        "contender_id": "some-benchmark-id-2",
        "baseline_batch_id": "some-batch-id-1",
        "contender_batch_id": "some-batch-id-2",
        "baseline_run_id": "some-run-id-1",
        "contender_run_id": "some-run-id-2",
        "unit": "i/s",
        "less_is_better": False,
    }


def test_compare_improvement_but_under_threshold():
    baseline = {
        "batch": "arrow-compute-scalar-cast-benchmark",
        "benchmark": "CastUInt32ToInt32Safe/262144/1000",
        "value": "1000",
        "unit": "i/s",
        "id": "some-benchmark-id-1",
        "batch_id": "some-batch-id-1",
        "run_id": "some-run-id-1",
    }
    contender = {
        "batch": "arrow-compute-scalar-cast-benchmark",
        "benchmark": "CastUInt32ToInt32Safe/262144/1000",
        "value": "1050",
        "unit": "i/s",
        "id": "some-benchmark-id-2",
        "batch_id": "some-batch-id-2",
        "run_id": "some-run-id-2",
    }

    result = BenchmarkComparator(baseline, contender).compare()
    formatted = BenchmarkComparator(baseline, contender).formatted()

    assert result == {
        "batch": "arrow-compute-scalar-cast-benchmark",
        "benchmark": "CastUInt32ToInt32Safe/262144/1000",
        "change": "5.000",
        "regression": False,
        "improvement": False,
        "baseline": "1000.000",
        "contender": "1050.000",
        "baseline_id": "some-benchmark-id-1",
        "contender_id": "some-benchmark-id-2",
        "baseline_batch_id": "some-batch-id-1",
        "contender_batch_id": "some-batch-id-2",
        "baseline_run_id": "some-run-id-1",
        "contender_run_id": "some-run-id-2",
        "unit": "i/s",
        "less_is_better": False,
    }
    assert formatted == {
        "batch": "arrow-compute-scalar-cast-benchmark",
        "benchmark": "CastUInt32ToInt32Safe/262144/1000",
        "change": "5.000%",
        "regression": False,
        "improvement": False,
        "baseline": "1.000K i/s",
        "contender": "1.050K i/s",
        "baseline_id": "some-benchmark-id-1",
        "contender_id": "some-benchmark-id-2",
        "baseline_batch_id": "some-batch-id-1",
        "contender_batch_id": "some-batch-id-2",
        "baseline_run_id": "some-run-id-1",
        "contender_run_id": "some-run-id-2",
        "unit": "i/s",
        "less_is_better": False,
    }


def test_compare_list():
    pairs = {
        "some-case-id-1": {
            "baseline": {
                "batch": "math",
                "benchmark": "addition",
                "unit": "s",
                "value": "0.036369",
                "id": "some-benchmark-id-1",
                "batch_id": "some-batch-id-1",
                "run_id": "some-run-id-1",
            },
            "contender": {
                "batch": "math",
                "benchmark": "addition",
                "unit": "s",
                "value": "0.036369",
                "id": "some-benchmark-id-2",
                "batch_id": "some-batch-id-2",
                "run_id": "some-run-id-2",
            },
        },
        "some-case-id-2": {
            "baseline": {
                "batch": "math",
                "benchmark": "subtraction",
                "unit": "s",
                "value": "1.036369",
                "id": "some-benchmark-id-3",
                "batch_id": "some-batch-id-1",
                "run_id": "some-run-id-1",
            },
            "contender": {
                "batch": "math",
                "benchmark": "subtraction",
                "unit": "s",
                "value": "0.036369",
                "id": "some-benchmark-id-4",
                "batch_id": "some-batch-id-2",
                "run_id": "some-run-id-2",
            },
        },
    }

    result = BenchmarkListComparator(pairs).compare()
    formatted = BenchmarkListComparator(pairs).formatted()

    assert list(result) == [
        {
            "batch": "math",
            "benchmark": "addition",
            "change": "0.000",
            "regression": False,
            "improvement": False,
            "baseline": "0.036",
            "contender": "0.036",
            "baseline_id": "some-benchmark-id-1",
            "contender_id": "some-benchmark-id-2",
            "baseline_batch_id": "some-batch-id-1",
            "contender_batch_id": "some-batch-id-2",
            "baseline_run_id": "some-run-id-1",
            "contender_run_id": "some-run-id-2",
            "unit": "s",
            "less_is_better": True,
        },
        {
            "batch": "math",
            "benchmark": "subtraction",
            "change": "-96.491",
            "regression": False,
            "improvement": True,
            "baseline": "1.036",
            "contender": "0.036",
            "baseline_id": "some-benchmark-id-3",
            "contender_id": "some-benchmark-id-4",
            "baseline_batch_id": "some-batch-id-1",
            "contender_batch_id": "some-batch-id-2",
            "baseline_run_id": "some-run-id-1",
            "contender_run_id": "some-run-id-2",
            "unit": "s",
            "less_is_better": True,
        },
    ]
    assert list(formatted) == [
        {
            "batch": "math",
            "benchmark": "addition",
            "change": "0.000%",
            "regression": False,
            "improvement": False,
            "baseline": "0.036 s",
            "contender": "0.036 s",
            "baseline_id": "some-benchmark-id-1",
            "contender_id": "some-benchmark-id-2",
            "baseline_batch_id": "some-batch-id-1",
            "contender_batch_id": "some-batch-id-2",
            "baseline_run_id": "some-run-id-1",
            "contender_run_id": "some-run-id-2",
            "unit": "s",
            "less_is_better": True,
        },
        {
            "batch": "math",
            "benchmark": "subtraction",
            "change": "-96.491%",
            "regression": False,
            "improvement": True,
            "baseline": "1.036 s",
            "contender": "0.036 s",
            "baseline_id": "some-benchmark-id-3",
            "contender_id": "some-benchmark-id-4",
            "baseline_batch_id": "some-batch-id-1",
            "contender_batch_id": "some-batch-id-2",
            "baseline_run_id": "some-run-id-1",
            "contender_run_id": "some-run-id-2",
            "unit": "s",
            "less_is_better": True,
        },
    ]


def test_compare_list_missing_contender():
    pairs = {
        "some-case-id-1": {
            "baseline": {
                "batch": "math",
                "benchmark": "addition",
                "unit": "s",
                "value": "0.036369",
                "id": "some-benchmark-id-1",
                "batch_id": "some-batch-id-1",
                "run_id": "some-run-id-1",
            },
        },
        "some-case-id-2": {
            "baseline": {
                "batch": "math",
                "benchmark": "subtraction",
                "unit": "s",
                "value": "1.036369",
                "id": "some-benchmark-id-3",
                "batch_id": "some-batch-id-1",
                "run_id": "some-run-id-1",
            },
            "contender": {
                "batch": "math",
                "benchmark": "subtraction",
                "unit": "s",
                "value": "0.036369",
                "id": "some-benchmark-id-4",
                "batch_id": "some-batch-id-2",
                "run_id": "some-run-id-2",
            },
        },
    }

    result = BenchmarkListComparator(pairs).compare()
    formatted = BenchmarkListComparator(pairs).formatted()

    assert list(result) == [
        {
            "batch": "math",
            "benchmark": "addition",
            "change": "0.000",
            "regression": False,
            "improvement": False,
            "baseline": "0.036",
            "contender": None,
            "baseline_id": "some-benchmark-id-1",
            "contender_id": None,
            "baseline_batch_id": "some-batch-id-1",
            "contender_batch_id": None,
            "baseline_run_id": "some-run-id-1",
            "contender_run_id": None,
            "unit": "s",
            "less_is_better": True,
        },
        {
            "batch": "math",
            "benchmark": "subtraction",
            "change": "-96.491",
            "regression": False,
            "improvement": True,
            "baseline": "1.036",
            "contender": "0.036",
            "baseline_id": "some-benchmark-id-3",
            "contender_id": "some-benchmark-id-4",
            "baseline_batch_id": "some-batch-id-1",
            "contender_batch_id": "some-batch-id-2",
            "baseline_run_id": "some-run-id-1",
            "contender_run_id": "some-run-id-2",
            "unit": "s",
            "less_is_better": True,
        },
    ]
    assert list(formatted) == [
        {
            "batch": "math",
            "benchmark": "addition",
            "change": "0.000%",
            "regression": False,
            "improvement": False,
            "baseline": "0.036 s",
            "contender": None,
            "baseline_id": "some-benchmark-id-1",
            "contender_id": None,
            "baseline_batch_id": "some-batch-id-1",
            "contender_batch_id": None,
            "baseline_run_id": "some-run-id-1",
            "contender_run_id": None,
            "unit": "s",
            "less_is_better": True,
        },
        {
            "batch": "math",
            "benchmark": "subtraction",
            "change": "-96.491%",
            "regression": False,
            "improvement": True,
            "baseline": "1.036 s",
            "contender": "0.036 s",
            "baseline_id": "some-benchmark-id-3",
            "contender_id": "some-benchmark-id-4",
            "baseline_batch_id": "some-batch-id-1",
            "contender_batch_id": "some-batch-id-2",
            "baseline_run_id": "some-run-id-1",
            "contender_run_id": "some-run-id-2",
            "unit": "s",
            "less_is_better": True,
        },
    ]


def test_compare_list_empty_contender():
    pairs = {
        "some-case-id-1": {
            "baseline": {
                "batch": "math",
                "benchmark": "addition",
                "unit": "s",
                "value": "0.036369",
                "id": "some-benchmark-id-1",
                "batch_id": "some-batch-id-1",
                "run_id": "some-run-id-1",
            },
            "contender": {},
        },
        "some-case-id-2": {
            "baseline": {
                "batch": "math",
                "benchmark": "subtraction",
                "unit": "s",
                "value": "1.036369",
                "id": "some-benchmark-id-3",
                "batch_id": "some-batch-id-1",
                "run_id": "some-run-id-1",
            },
            "contender": {
                "batch": "math",
                "benchmark": "subtraction",
                "unit": "s",
                "value": "0.036369",
                "id": "some-benchmark-id-4",
                "batch_id": "some-batch-id-2",
                "run_id": "some-run-id-2",
            },
        },
    }

    result = BenchmarkListComparator(pairs).compare()
    formatted = BenchmarkListComparator(pairs).formatted()

    assert list(result) == [
        {
            "batch": "math",
            "benchmark": "addition",
            "change": "0.000",
            "regression": False,
            "improvement": False,
            "baseline": "0.036",
            "contender": None,
            "baseline_id": "some-benchmark-id-1",
            "contender_id": None,
            "baseline_batch_id": "some-batch-id-1",
            "contender_batch_id": None,
            "baseline_run_id": "some-run-id-1",
            "contender_run_id": None,
            "unit": "s",
            "less_is_better": True,
        },
        {
            "batch": "math",
            "benchmark": "subtraction",
            "change": "-96.491",
            "regression": False,
            "improvement": True,
            "baseline": "1.036",
            "contender": "0.036",
            "baseline_id": "some-benchmark-id-3",
            "contender_id": "some-benchmark-id-4",
            "baseline_batch_id": "some-batch-id-1",
            "contender_batch_id": "some-batch-id-2",
            "baseline_run_id": "some-run-id-1",
            "contender_run_id": "some-run-id-2",
            "unit": "s",
            "less_is_better": True,
        },
    ]
    assert list(formatted) == [
        {
            "batch": "math",
            "benchmark": "addition",
            "change": "0.000%",
            "regression": False,
            "improvement": False,
            "baseline": "0.036 s",
            "contender": None,
            "baseline_id": "some-benchmark-id-1",
            "contender_id": None,
            "baseline_batch_id": "some-batch-id-1",
            "contender_batch_id": None,
            "baseline_run_id": "some-run-id-1",
            "contender_run_id": None,
            "unit": "s",
            "less_is_better": True,
        },
        {
            "batch": "math",
            "benchmark": "subtraction",
            "change": "-96.491%",
            "improvement": True,
            "regression": False,
            "baseline": "1.036 s",
            "contender": "0.036 s",
            "baseline_id": "some-benchmark-id-3",
            "contender_id": "some-benchmark-id-4",
            "baseline_batch_id": "some-batch-id-1",
            "contender_batch_id": "some-batch-id-2",
            "baseline_run_id": "some-run-id-1",
            "contender_run_id": "some-run-id-2",
            "unit": "s",
            "less_is_better": True,
        },
    ]


def test_compare_list_missing_baseline():
    pairs = {
        "some-case-id-1": {
            "contender": {
                "batch": "math",
                "benchmark": "addition",
                "unit": "s",
                "value": "0.036369",
                "id": "some-benchmark-id-2",
                "batch_id": "some-batch-id-2",
                "run_id": "some-run-id-2",
            },
        },
        "some-case-id-2": {
            "baseline": {
                "batch": "math",
                "benchmark": "subtraction",
                "unit": "s",
                "value": "1.036369",
                "id": "some-benchmark-id-3",
                "batch_id": "some-batch-id-1",
                "run_id": "some-run-id-1",
            },
            "contender": {
                "batch": "math",
                "benchmark": "subtraction",
                "unit": "s",
                "value": "0.036369",
                "id": "some-benchmark-id-4",
                "batch_id": "some-batch-id-2",
                "run_id": "some-run-id-2",
            },
        },
    }

    result = BenchmarkListComparator(pairs).compare()
    formatted = BenchmarkListComparator(pairs).formatted()

    assert list(result) == [
        {
            "batch": "math",
            "benchmark": "addition",
            "change": "0.000",
            "regression": False,
            "improvement": False,
            "baseline": None,
            "contender": "0.036",
            "baseline_id": None,
            "contender_id": "some-benchmark-id-2",
            "baseline_batch_id": None,
            "contender_batch_id": "some-batch-id-2",
            "baseline_run_id": None,
            "contender_run_id": "some-run-id-2",
            "unit": "s",
            "less_is_better": True,
        },
        {
            "batch": "math",
            "benchmark": "subtraction",
            "change": "-96.491",
            "regression": False,
            "improvement": True,
            "baseline": "1.036",
            "contender": "0.036",
            "baseline_id": "some-benchmark-id-3",
            "contender_id": "some-benchmark-id-4",
            "baseline_batch_id": "some-batch-id-1",
            "contender_batch_id": "some-batch-id-2",
            "baseline_run_id": "some-run-id-1",
            "contender_run_id": "some-run-id-2",
            "unit": "s",
            "less_is_better": True,
        },
    ]
    assert list(formatted) == [
        {
            "batch": "math",
            "benchmark": "addition",
            "change": "0.000%",
            "regression": False,
            "improvement": False,
            "baseline": None,
            "contender": "0.036 s",
            "baseline_id": None,
            "contender_id": "some-benchmark-id-2",
            "baseline_batch_id": None,
            "contender_batch_id": "some-batch-id-2",
            "baseline_run_id": None,
            "contender_run_id": "some-run-id-2",
            "unit": "s",
            "less_is_better": True,
        },
        {
            "batch": "math",
            "benchmark": "subtraction",
            "change": "-96.491%",
            "regression": False,
            "improvement": True,
            "baseline": "1.036 s",
            "contender": "0.036 s",
            "baseline_id": "some-benchmark-id-3",
            "contender_id": "some-benchmark-id-4",
            "baseline_batch_id": "some-batch-id-1",
            "contender_batch_id": "some-batch-id-2",
            "baseline_run_id": "some-run-id-1",
            "contender_run_id": "some-run-id-2",
            "unit": "s",
            "less_is_better": True,
        },
    ]


def test_compare_list_empty_baseline():
    pairs = {
        "some-case-id-1": {
            "baseline": {},
            "contender": {
                "batch": "math",
                "benchmark": "addition",
                "unit": "s",
                "value": "0.036369",
                "id": "some-benchmark-id-2",
                "batch_id": "some-batch-id-2",
                "run_id": "some-run-id-2",
            },
        },
        "some-case-id-2": {
            "baseline": {
                "batch": "math",
                "benchmark": "subtraction",
                "unit": "s",
                "value": "1.036369",
                "id": "some-benchmark-id-3",
                "batch_id": "some-batch-id-1",
                "run_id": "some-run-id-1",
            },
            "contender": {
                "batch": "math",
                "benchmark": "subtraction",
                "unit": "s",
                "value": "0.036369",
                "id": "some-benchmark-id-4",
                "batch_id": "some-batch-id-2",
                "run_id": "some-run-id-2",
            },
        },
    }

    result = BenchmarkListComparator(pairs).compare()
    formatted = BenchmarkListComparator(pairs).formatted()

    assert list(result) == [
        {
            "batch": "math",
            "benchmark": "addition",
            "change": "0.000",
            "regression": False,
            "improvement": False,
            "baseline": None,
            "contender": "0.036",
            "baseline_id": None,
            "contender_id": "some-benchmark-id-2",
            "baseline_batch_id": None,
            "contender_batch_id": "some-batch-id-2",
            "baseline_run_id": None,
            "contender_run_id": "some-run-id-2",
            "unit": "s",
            "less_is_better": True,
        },
        {
            "batch": "math",
            "benchmark": "subtraction",
            "change": "-96.491",
            "regression": False,
            "improvement": True,
            "baseline": "1.036",
            "contender": "0.036",
            "baseline_id": "some-benchmark-id-3",
            "contender_id": "some-benchmark-id-4",
            "baseline_batch_id": "some-batch-id-1",
            "contender_batch_id": "some-batch-id-2",
            "baseline_run_id": "some-run-id-1",
            "contender_run_id": "some-run-id-2",
            "unit": "s",
            "less_is_better": True,
        },
    ]
    assert list(formatted) == [
        {
            "batch": "math",
            "benchmark": "addition",
            "change": "0.000%",
            "regression": False,
            "improvement": False,
            "baseline": None,
            "contender": "0.036 s",
            "baseline_id": None,
            "contender_id": "some-benchmark-id-2",
            "baseline_batch_id": None,
            "contender_batch_id": "some-batch-id-2",
            "baseline_run_id": None,
            "contender_run_id": "some-run-id-2",
            "unit": "s",
            "less_is_better": True,
        },
        {
            "batch": "math",
            "benchmark": "subtraction",
            "change": "-96.491%",
            "regression": False,
            "improvement": True,
            "baseline": "1.036 s",
            "contender": "0.036 s",
            "baseline_id": "some-benchmark-id-3",
            "contender_id": "some-benchmark-id-4",
            "baseline_batch_id": "some-batch-id-1",
            "contender_batch_id": "some-batch-id-2",
            "baseline_run_id": "some-run-id-1",
            "contender_run_id": "some-run-id-2",
            "unit": "s",
            "less_is_better": True,
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

    result = BenchmarkListComparator(pairs).compare()
    formatted = BenchmarkListComparator(pairs).formatted()

    assert list(result) == [
        {
            "batch": "unknown",
            "benchmark": "unknown",
            "change": "0.000",
            "regression": False,
            "improvement": False,
            "baseline": None,
            "contender": None,
            "baseline_id": None,
            "contender_id": None,
            "baseline_batch_id": None,
            "contender_batch_id": None,
            "baseline_run_id": None,
            "contender_run_id": None,
            "unit": "unknown",
            "less_is_better": True,
        },
        {
            "batch": "unknown",
            "benchmark": "unknown",
            "change": "0.000",
            "regression": False,
            "improvement": False,
            "baseline": None,
            "contender": None,
            "baseline_id": None,
            "contender_id": None,
            "baseline_batch_id": None,
            "contender_batch_id": None,
            "baseline_run_id": None,
            "contender_run_id": None,
            "unit": "unknown",
            "less_is_better": True,
        },
    ]
    assert list(formatted) == [
        {
            "batch": "unknown",
            "benchmark": "unknown",
            "change": "0.000%",
            "regression": False,
            "improvement": False,
            "baseline": None,
            "contender": None,
            "baseline_id": None,
            "contender_id": None,
            "baseline_batch_id": None,
            "contender_batch_id": None,
            "baseline_run_id": None,
            "contender_run_id": None,
            "unit": "unknown",
            "less_is_better": True,
        },
        {
            "batch": "unknown",
            "benchmark": "unknown",
            "change": "0.000%",
            "regression": False,
            "improvement": False,
            "baseline": None,
            "contender": None,
            "baseline_id": None,
            "contender_id": None,
            "baseline_batch_id": None,
            "contender_batch_id": None,
            "baseline_run_id": None,
            "contender_run_id": None,
            "unit": "unknown",
            "less_is_better": True,
        },
    ]
