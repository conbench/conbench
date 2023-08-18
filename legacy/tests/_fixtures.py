from .helpers import _uuid

CHILD = "02addad336ba19a654f9c857ede546331be7b631"
PARENT = "4beb514d071c9beec69b8917b5265e77ade22fb3"
GRANDPARENT = "6d703c4c7b15be630af48d5e9ef61628751674b2"
ELDER = "81e9417eb68171e03a304097ae86e1fd83307130"

REPO = "https://github.com/org/something"

RESULTS_UP = [[1, 2, 3], [2, 3, 4], [10, 20, 30]]
RESULTS_DOWN = [[10, 11, 12], [11, 12, 13], [1, 2, 3]]
Z_SCORE_UP = 24.74873734152916  # Computed using statistics.stdev()
Z_SCORE_DOWN = -13.435028842544401  # Computed using statistics.stdev()

CLUSTER_INFO = {
    "name": f"cluster-{_uuid()}",
    "info": {"gpu": 1},
    "optional_info": {"workers": 1},
}

MACHINE_INFO = {
    "architecture_name": "x86_64",
    "cpu_l1d_cache_bytes": "32768",
    "cpu_l1i_cache_bytes": "32768",
    "cpu_l2_cache_bytes": "262144",
    "cpu_l3_cache_bytes": "4194304",
    "cpu_core_count": "2",
    "cpu_frequency_max_hz": "3500000000",
    "cpu_model_name": "Intel(R) Core(TM) i7-7567U CPU @ 3.50GHz",
    "cpu_thread_count": "4",
    "kernel_name": "19.6.0",
    "memory_bytes": "17179869184",
    "name": "diana",
    "os_name": "macOS",
    "os_version": "10.15.7",
    "gpu_count": "2",
    "gpu_product_names": ["Tesla T4", "GeForce GTX 1060 3GB"],
}

VALID_RESULT_PAYLOAD = {
    "run_id": "2a5709d179f349cba69ed242be3e6321",
    "run_name": "commit: 02addad336ba19a654f9c857ede546331be7b631",
    "run_reason": "commit",
    "batch_id": "7b2fdd9f929d47b9960152090d47f8e6",
    "timestamp": "2020-11-25T21:02:44Z",
    "context": {
        "arrow_compiler_flags": "-fPIC -arch x86_64 -arch x86_64 -std=c++11 -Qunused-arguments -fcolor-diagnostics -O3 -DNDEBUG",
        "benchmark_language": "Python",
    },
    "info": {
        "arrow_version": "2.0.0",
        "benchmark_language_version": "Python 3.8.5",
        "arrow_compiler_version": "11.0.0.11000033",
        "arrow_compiler_id": "AppleClang",
    },
    "optional_benchmark_info": {"trace_id": "some trace id", "logs": "some log uri"},
    "validation": {"type": "pandas.testing", "success": True},
    "github": {
        "commit": "02addad336ba19a654f9c857ede546331be7b631",
        "repository": "https://github.com/org/repo",
        "branch": None,
        "pr_number": 12345678,
    },
    "machine_info": MACHINE_INFO,
    "stats": {
        "data": [
            "0.099094",
            "0.037129",
            "0.036381",
            "0.148896",
            "0.008104",
            "0.005496",
            "0.009871",
            "0.006008",
            "0.007978",
            "0.004733",
        ],
        "times": [
            "0.099094",
            "0.037129",
            "0.036381",
            "0.148896",
            "0.008104",
            "0.005496",
            "0.009871",
            "0.006008",
            "0.007978",
            "0.004733",
        ],
        "unit": "s",
        "time_unit": "s",
        "iqr": "0.030442",
        "iterations": 10,
        "max": "0.1489",
        "mean": "0.036369",
        "median": "0.0089875",
        "min": "0.004733",
        "q1": "0.0065005",
        "q3": "0.036942",
        "stdev": "0.049194",
    },
    "tags": {
        "compression": "snappy",
        "cpu_count": "2",
        "dataset": "nyctaxi_sample",
        "file_type": "parquet",
        "input_type": "arrow",
        "name": "file-write",
    },
}

VALID_RESULT_PAYLOAD_WITH_ERROR = dict(
    run_id="ya5709d179f349cba69ed242be3e6323",
    error={"stack_trace": "some trace", "command": "ls"},
    **{
        key: value
        for key, value in VALID_RESULT_PAYLOAD.items()
        if key not in ("stats", "run_id")
    },
)

VALID_RESULT_PAYLOAD_WITH_ITERATION_ERROR = dict(
    run_id="ya5709d179f349cba69ed242be3e6323",
    # It's interesting that this has both, the `error` property set and
    # missing iteration data. Either is sufficient for marking a result as
    # "errored".
    error={"stack_trace": "some trace", "command": "ls"},
    **{
        key: value
        for key, value in VALID_RESULT_PAYLOAD.items()
        if key not in ("stats", "run_id")
    },
    stats={
        "data": [
            "0.099094",
            None,
            "0.036381",
            "0.148896",
            "0.008104",
            "0.005496",
            "0.009871",
            "0.006008",
            "0.007978",
            "0.004733",
        ],
        "times": [
            "0.099094",
            None,
            "0.036381",
            "0.148896",
            "0.008104",
            "0.005496",
            "0.009871",
            "0.006008",
            "0.007978",
            "0.004733",
        ],
        "unit": "s",
        "time_unit": "s",
        "iterations": 10,
    },
)

VALID_RESULT_PAYLOAD_FOR_CLUSTER = dict(
    run_id="3a5709d179f349cba69ed242be3e6323",
    cluster_info=CLUSTER_INFO,
    **{
        key: value
        for key, value in VALID_RESULT_PAYLOAD.items()
        if key not in ("machine_info", "run_id")
    },
)

VALID_RUN_PAYLOAD = {
    "id": _uuid(),
    "name": "commit: 02addad336ba19a654f9c857ede546331be7b631",
    "reason": "commit",
    "finished_timestamp": "2020-11-25T21:02:42Z",
    "info": {
        "setup": "passed",
    },
    "github": {
        "commit": "02addad336ba19a654f9c857ede546331be7b631",
        "repository": "https://github.com/org/repo",
        "branch": None,
        "pr_number": 12345678,
    },
    "machine_info": MACHINE_INFO,
}

VALID_RUN_PAYLOAD_FOR_CLUSTER = dict(
    id=_uuid(),
    cluster_info=CLUSTER_INFO,
    **{
        key: value
        for key, value in VALID_RUN_PAYLOAD.items()
        if key not in ("machine_info", "id")
    },
)

VALID_RUN_PAYLOAD_WITH_ERROR = dict(
    id=_uuid(),
    error_info={"error": "error", "stack_trace": "stack_trace", "fatal": True},
    error_type="fatal",
    **{key: value for key, value in VALID_RUN_PAYLOAD.items() if key not in ("id")},
)
