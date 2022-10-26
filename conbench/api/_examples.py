class FakeUser1:
    id = "some-user-uuid-1"
    name = "Gwen Clarke"
    email = "gwen@example.com"


class FakeUser2:
    id = "some-user-uuid-2"
    name = "Casey Clarke"
    email = "casey@example.com"


def _api_user_entity(user):
    return {
        "email": user.email,
        "id": user.id,
        "links": {
            "list": "http://localhost/api/users/",
            "self": "http://localhost/api/users/%s/" % user.id,
        },
        "name": user.name,
    }


def _api_benchmark_entity(
    benchmark_result_id,
    case_id,
    info_id,
    context_id,
    batch_id,
    run_id,
    name,
    error=None,
    validation=None,
    optional_benchmark_info=None,
):
    if error:
        stats = {
            "data": [],
            "times": [],
            "unit": None,
            "time_unit": None,
            "iqr": None,
            "iterations": None,
            "max": None,
            "mean": None,
            "median": None,
            "min": None,
            "q1": None,
            "q3": None,
            "stdev": None,
            "z_score": None,
            "z_regression": False,
            "z_improvement": False,
        }
    else:
        stats = {
            "data": [
                0.099094,
                0.037129,
                0.036381,
                0.148896,
                0.008104,
                0.005496,
                0.009871,
                0.006008,
                0.007978,
                0.004733,
            ],
            "times": [
                0.099094,
                0.037129,
                0.036381,
                0.148896,
                0.008104,
                0.005496,
                0.009871,
                0.006008,
                0.007978,
                0.004733,
            ],
            "unit": "s",
            "time_unit": "s",
            "iqr": 0.030442,
            "iterations": 10,
            "max": 0.148896,
            "mean": 0.036369,
            "median": 0.008988,
            "min": 0.004733,
            "q1": 0.006500,
            "q3": 0.036942,
            "stdev": 0.049194,
            "z_score": None,
            "z_regression": False,
            "z_improvement": False,
        }
    return {
        "id": benchmark_result_id,
        "run_id": run_id,
        "batch_id": batch_id,
        "timestamp": "2020-11-25T21:02:42.706806",
        "stats": stats,
        "error": error,
        "validation": validation,
        "optional_benchmark_info": optional_benchmark_info,
        "tags": {
            "id": case_id,
            "compression": "snappy",
            "cpu_count": 2,
            "dataset": "nyctaxi_sample",
            "file_type": "parquet",
            "input_type": "arrow",
            "name": name,
        },
        "links": {
            "list": "http://localhost/api/benchmarks/",
            "self": "http://localhost/api/benchmarks/%s/" % benchmark_result_id,
            "context": "http://localhost/api/contexts/%s/" % context_id,
            "info": "http://localhost/api/info/%s/" % info_id,
            "run": "http://localhost/api/runs/%s/" % run_id,
        },
    }


def _api_commit_entity(commit_id, parent_id, links=True):
    result = {
        "author_avatar": "https://avatars.githubusercontent.com/u/878798?v=4",
        "author_login": "dianaclarke",
        "author_name": "Diana Clarke",
        "id": commit_id,
        "message": "ARROW-11771: [Developer][Archery] Move benchmark tests (so CI runs them)",
        "repository": "https://github.com/apache/arrow",
        "sha": "02addad336ba19a654f9c857ede546331be7b631",
        "url": "https://github.com/apache/arrow/commit/02addad336ba19a654f9c857ede546331be7b631",
        "parent_sha": "4beb514d071c9beec69b8917b5265e77ade22fb3",
        "timestamp": "2021-02-25T01:02:51",
        "links": {
            "list": "http://localhost/api/commits/",
            "self": "http://localhost/api/commits/%s/" % commit_id,
        },
    }
    if parent_id:
        result["links"]["parent"] = "http://localhost/api/commits/%s/" % parent_id
    if not links:
        result.pop("links", None)
    return result


def _api_compare_entity(benchmark_ids, batch_ids, run_ids, batch, benchmark, tags):
    return {
        "baseline": "0.036 s",
        "baseline_error": None,
        "baseline_id": benchmark_ids[0],
        "baseline_batch_id": batch_ids[0],
        "baseline_run_id": run_ids[0],
        "batch": batch,
        "benchmark": benchmark,
        "language": "Python",
        "change": "0.000%",
        "threshold": "5.000%",
        "regression": False,
        "improvement": False,
        "threshold_z": 5.0,
        "baseline_z_score": None,
        "contender_z_score": None,
        "baseline_z_regression": False,
        "baseline_z_improvement": False,
        "contender_z_regression": False,
        "contender_z_improvement": False,
        "contender": "0.036 s",
        "contender_error": None,
        "contender_id": benchmark_ids[1],
        "contender_batch_id": batch_ids[1],
        "contender_run_id": run_ids[1],
        "less_is_better": True,
        "unit": "s",
        "tags": tags,
    }


def _api_compare_list(
    baseline_ids,
    contender_ids,
    batch_ids,
    run_ids,
    batches,
    benchmarks,
    tags,
):
    return [
        {
            "baseline": "0.036 s",
            "baseline_error": None,
            "baseline_id": baseline_ids[0],
            "baseline_batch_id": batch_ids[0],
            "baseline_run_id": run_ids[0],
            "batch": batches[0],
            "benchmark": benchmarks[0],
            "language": "Python",
            "change": "0.000%",
            "threshold": "5.000%",
            "regression": False,
            "improvement": False,
            "threshold_z": 5.0,
            "baseline_z_score": None,
            "contender_z_score": None,
            "baseline_z_regression": False,
            "baseline_z_improvement": False,
            "contender_z_regression": False,
            "contender_z_improvement": False,
            "contender": "0.036 s",
            "contender_error": None,
            "contender_id": contender_ids[0],
            "contender_batch_id": batch_ids[1],
            "contender_run_id": run_ids[1],
            "less_is_better": True,
            "unit": "s",
            "tags": tags[0],
        },
        {
            "baseline": "0.036 s",
            "baseline_error": None,
            "baseline_id": baseline_ids[1],
            "baseline_batch_id": batch_ids[0],
            "baseline_run_id": run_ids[0],
            "batch": batches[1],
            "benchmark": benchmarks[1],
            "language": "Python",
            "change": "0.000%",
            "threshold": "5.000%",
            "regression": False,
            "improvement": False,
            "threshold_z": 5.0,
            "baseline_z_score": None,
            "contender_z_score": None,
            "baseline_z_regression": False,
            "baseline_z_improvement": False,
            "contender_z_regression": False,
            "contender_z_improvement": False,
            "contender": "0.036 s",
            "contender_error": None,
            "contender_id": contender_ids[1],
            "contender_batch_id": batch_ids[1],
            "contender_run_id": run_ids[1],
            "less_is_better": True,
            "unit": "s",
            "tags": tags[1],
        },
    ]


def _api_compare_benchmark_result(
    baseline_commit_id,
    contender_commit_id,
    baseline_id,
    baseline_name,
    baseline_timestamp,
    contender_id,
    contender_name,
    contender_timestamp,
):
    return {
        "commits": {
            "baseline": {
                "author_avatar": "https://avatars.githubusercontent.com/u/1299904?v=4",
                "author_login": "bkietz",
                "author_name": "Benjamin Kietzman",
                "id": baseline_commit_id,
                "message": "ARROW-11767: [C++] Scalar::Hash may segfault",
                "parent_sha": "6d703c4c7b15be630af48d5e9ef61628751674b2",
                "repository": "https://github.com/apache/arrow",
                "sha": "4beb514d071c9beec69b8917b5265e77ade22fb3",
                "timestamp": "2021-02-24T22:12:11",
                "url": "https://github.com/apache/arrow/commit/4beb514d071c9beec69b8917b5265e77ade22fb3",
            },
            "contender": {
                "author_avatar": "https://avatars.githubusercontent.com/u/878798?v=4",
                "author_login": "dianaclarke",
                "author_name": "Diana Clarke",
                "id": contender_commit_id,
                "message": "ARROW-11771: [Developer][Archery] Move benchmark tests (so CI runs them)",
                "parent_sha": "4beb514d071c9beec69b8917b5265e77ade22fb3",
                "repository": "https://github.com/apache/arrow",
                "sha": "02addad336ba19a654f9c857ede546331be7b631",
                "timestamp": "2021-02-25T01:02:51",
                "url": "https://github.com/apache/arrow/commit/02addad336ba19a654f9c857ede546331be7b631",
            },
        },
        "links": {
            "self": "http://localhost/api/compare/commits/4beb514d071c9beec69b8917b5265e77ade22fb3...02addad336ba19a654f9c857ede546331be7b631/"
        },
        "runs": [
            {
                "baseline": {
                    "hardware_name": "diana",
                    "run": f"http://localhost/api/runs/{baseline_id}/",
                    "run_id": baseline_id,
                    "run_name": baseline_name,
                    "run_timestamp": baseline_timestamp,
                },
                "compare": f"http://localhost/api/compare/runs/{baseline_id}...{contender_id}/",
                "contender": {
                    "hardware_name": "diana",
                    "run": f"http://localhost/api/runs/{contender_id}/",
                    "run_id": contender_id,
                    "run_name": contender_name,
                    "run_timestamp": contender_timestamp,
                },
            },
        ],
    }


def _api_context_entity(context_id, links=True):
    result = {
        "id": context_id,
        "arrow_compiler_flags": "-fPIC -arch x86_64 -arch x86_64 -std=c++11 -Qunused-arguments -fcolor-diagnostics -O3 -DNDEBUG",
        "benchmark_language": "Python",
        "links": {
            "list": "http://localhost/api/contexts/",
            "self": "http://localhost/api/contexts/%s/" % context_id,
        },
    }
    if not links:
        result.pop("links", None)
    return result


def _api_history_entity(benchmark_id, case_id, context_id, run_name):
    return {
        "benchmark_id": benchmark_id,
        "case_id": case_id,
        "context_id": context_id,
        "hardware_hash": "diana-2-2-4-17179869184",
        "unit": "s",
        "mean": 0.036369,
        "distribution_mean": 0.036369,
        "distribution_stdev": 0.000000,
        "repository": "https://github.com/apache/arrow",
        "sha": "02addad336ba19a654f9c857ede546331be7b631",
        "timestamp": "2021-02-25T01:02:51",
        "message": "ARROW-11771: [Developer][Archery] Move benchmark tests (so CI runs them)",
        "run_name": run_name,
    }


def _api_info_entity(info_id, links=True):
    result = {
        "id": info_id,
        "arrow_compiler_id": "AppleClang",
        "arrow_compiler_version": "11.0.0.11000033",
        "arrow_version": "2.0.0",
        "benchmark_language_version": "Python 3.8.5",
        "links": {
            "list": "http://localhost/api/info/",
            "self": "http://localhost/api/info/%s/" % info_id,
        },
    }
    if not links:
        result.pop("links", None)
    return result


def _api_hardware_entity(
    hardware_id, hardware_name, hardware_type="machine", links=True
):
    if hardware_type == "machine":
        result = {
            "id": hardware_id,
            "type": "machine",
            "architecture_name": "x86_64",
            "cpu_l1d_cache_bytes": 32768,
            "cpu_l1i_cache_bytes": 32768,
            "cpu_l2_cache_bytes": 262144,
            "cpu_l3_cache_bytes": 4194304,
            "cpu_core_count": 2,
            "cpu_frequency_max_hz": 3500000000,
            "cpu_model_name": "Intel(R) Core(TM) i7-7567U CPU @ 3.50GHz",
            "cpu_thread_count": 4,
            "kernel_name": "19.6.0",
            "memory_bytes": 17179869184,
            "name": hardware_name,
            "os_name": "macOS",
            "os_version": "10.15.7",
            "gpu_count": 2,
            "gpu_product_names": ["Tesla T4", "GeForce GTX 1060 3GB"],
            "links": {
                "list": "http://localhost/api/hardware/",
                "self": "http://localhost/api/hardware/%s/" % hardware_id,
            },
        }
    else:
        result = {
            "id": hardware_id,
            "type": "cluster",
            "info": {"gpu": 1},
            "optional_info": {"workers": 1},
            "name": hardware_name,
            "links": {
                "list": "http://localhost/api/hardware/",
                "self": "http://localhost/api/hardware/%s/" % hardware_id,
            },
        }
    if not links:
        result.pop("links", None)
    return result


def _api_run_entity(
    run_id,
    run_name,
    run_reason,
    commit_id,
    parent_id,
    hardware_id,
    hardware_name,
    hardware_type,
    now,
    baseline_id,
    include_baseline=True,
    has_errors=False,
    finished_timestamp=None,
    info=None,
    error_info=None,
    error_type=None,
):
    result = {
        "id": run_id,
        "name": run_name,
        "reason": run_reason,
        "timestamp": now,
        "finished_timestamp": finished_timestamp,
        "info": info,
        "error_info": error_info,
        "error_type": error_type,
        "commit": _api_commit_entity(commit_id, parent_id, links=False),
        "hardware": _api_hardware_entity(
            hardware_id, hardware_name, hardware_type, links=False
        ),
        "has_errors": has_errors,
        "links": {
            "list": "http://localhost/api/runs/",
            "self": "http://localhost/api/runs/%s/" % run_id,
            "commit": "http://localhost/api/commits/%s/" % commit_id,
            "hardware": "http://localhost/api/hardware/%s/" % hardware_id,
        },
    }
    baseline_url = None
    if baseline_id:
        baseline_url = "http://localhost/api/runs/%s/" % baseline_id
    if include_baseline:
        result["links"]["baseline"] = baseline_url
    return result


BENCHMARK_ENTITY = _api_benchmark_entity(
    "some-benchmark-uuid-1",
    "some-case-uuid-1",
    "some-info-uuid-1",
    "some-context-uuid-1",
    "some-batch-uuid-1",
    "some-run-uuid-1",
    "file-write",
)
COMMIT_ENTITY = _api_commit_entity(
    "some-commit-uuid-1",
    "some-commit-parent-uuid-1",
)
COMPARE_ENTITY = _api_compare_entity(
    ["some-benchmark-uuid-1", "some-benchmark-uuid-2"],
    ["some-batch-uuid-1", "some-batch-uuid-2"],
    ["some-run-uuid-1", "some-run-uuid-2"],
    "file-read",
    "snappy, nyctaxi_sample, parquet, arrow",
    {
        "compression": "snappy",
        "cpu_count": 2,
        "dataset": "nyctaxi_sample",
        "file_type": "parquet",
        "input_type": "arrow",
        "name": "file-read",
    },
)
COMPARE_LIST = _api_compare_list(
    ["some-benchmark-uuid-1", "some-benchmark-uuid-2"],
    ["some-benchmark-uuid-3", "some-benchmark-uuid-4"],
    ["some-batch-uuid-1", "some-batch-uuid-2"],
    ["some-run-uuid-1", "some-run-uuid-2"],
    ["file-read", "file-write"],
    [
        "snappy, nyctaxi_sample, parquet, arrow",
        "snappy, nyctaxi_sample, parquet, arrow",
    ],
    [
        {
            "compression": "snappy",
            "cpu_count": 2,
            "dataset": "nyctaxi_sample",
            "file_type": "parquet",
            "input_type": "arrow",
            "name": "file-read",
        },
        {
            "compression": "snappy",
            "cpu_count": 2,
            "dataset": "nyctaxi_sample",
            "file_type": "parquet",
            "input_type": "arrow",
            "name": "file-write",
        },
    ],
)
COMPARE_BENCHMARK_RESULT = _api_compare_benchmark_result(
    "some-baseline-commit-id",
    "some-contender-commit-id",
    "some-baseline-run-id",
    "commit: 4beb514d071c9beec69b8917b5265e77ade22fb3",
    "2021-02-24T23:12:11",
    "some-contender-run-id",
    "commit: 02addad336ba19a654f9c857ede546331be7b631",
    "2021-02-25T06:02:51",
)
CONTEXT_ENTITY = _api_context_entity("some-context-uuid-1")
HISTORY_ENTITY = _api_history_entity(
    "some-benchmark-uuid-1",
    "some-case-uuid-1",
    "some-context-uuid-1",
    "some run name",
)
INFO_ENTITY = _api_info_entity("some-info-uuid-1")
HARDWARE_ENTITY = _api_hardware_entity("some-machine-uuid-1", "some-machine-name")
RUN_ENTITY = _api_run_entity(
    "some-run-uuid-1",
    "some run name",
    "some run reason",
    "some-commit-uuid-1",
    "some-parent-commit-uuid-1",
    "some-machine-uuid-1",
    "some-machine-name",
    "machine",
    "2021-02-04T17:22:05.225583",
    "some-run-uuid-0",
)
RUN_LIST = [
    _api_run_entity(
        "some-run-uuid-1",
        "some run name",
        "some run reason",
        "some-commit-uuid-1",
        "some-parent-commit-uuid-1",
        "some-machine-uuid-1",
        "some-machine-name",
        "machine",
        "2021-02-04T17:22:05.225583",
        None,
        include_baseline=False,
    ),
]
USER_ENTITY = _api_user_entity(FakeUser1())
USER_LIST = [
    _api_user_entity(FakeUser1()),
    _api_user_entity(FakeUser2()),
]


API_401 = {"code": 401, "name": "Unauthorized"}
API_404 = {"code": 404, "name": "Not Found"}
API_400 = {
    "code": 400,
    "name": "Bad Request",
    "description": {
        "_errors": ["Empty request body."],
        "_schema": [
            "Invalid input type.",
            "Did you specify Content-type: application/json?",
        ],
    },
}

API_PING = {
    "alembic_version": "0d4e564b1876",
    "date": "Thu, 22 Oct 2020 15:53:55 UTC",
}
API_INDEX = {
    "links": {
        "benchmarks": "http://localhost/api/benchmarks/",
        "commits": "http://localhost/api/commits/",
        "contexts": "http://localhost/api/contexts/",
        "docs": "http://localhost/api/docs.json",
        "login": "http://localhost/api/login/",
        "logout": "http://localhost/api/logout/",
        "info": "http://localhost/api/info/",
        "hardware": "http://localhost/api/hardware/",
        "register": "http://localhost/api/register/",
        "runs": "http://localhost/api/runs/",
        "ping": "http://localhost/api/ping/",
        "users": "http://localhost/api/users/",
    }
}
