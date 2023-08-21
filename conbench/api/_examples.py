import copy


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
    info_id,
    context_id,
    batch_id,
    run_id,
    run_tags,
    run_reason,
    commit_id,
    parent_id,
    commit_type,  # "none", "known", "unknown"
    branch,
    hardware_id,
    hardware_name,
    hardware_type,
    name,
    stats=None,
    error=None,
    validation=None,
    optional_benchmark_info=None,
):
    if stats:
        stats = {
            "data": stats.get("data"),
            "times": stats.get("times"),
            "unit": "s",
            "time_unit": "s",
            "iqr": None,
            "iterations": 10,
            "max": None,
            "mean": None,
            "median": None,
            "min": None,
            "q1": None,
            "q3": None,
            "stdev": None,
        }
    elif error:
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
            "iqr": 0.030441500000000003,
            "iterations": 10,
            "max": 0.148896,
            "mean": 0.036369,
            "median": 0.008987499999999999,
            "min": 0.004733,
            "q1": 0.0065005,
            "q3": 0.036942,
            "stdev": 0.04919372267316679,
        }
    return {
        "id": benchmark_result_id,
        "run_id": run_id,
        "run_tags": run_tags,
        "run_reason": run_reason,
        "commit": None
        if commit_type == "none"
        else _api_commit_entity(
            commit_id,
            parent_id,
            branch,
            links=False,
            is_unknown_commit=commit_type == "unknown",
        ),
        "hardware": _api_hardware_entity(
            hardware_id, hardware_name, hardware_type, links=False
        ),
        "batch_id": batch_id,
        "timestamp": "2020-11-25T21:02:44Z",
        "stats": stats,
        "error": error,
        "validation": validation,
        "optional_benchmark_info": optional_benchmark_info,
        "change_annotations": {},
        "tags": {
            "compression": "snappy",
            "cpu_count": "2",
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


def _api_commit_entity(
    commit_id,
    parent_id,
    branch="some_user_or_org:some_branch",
    links=True,
    is_unknown_commit=False,
):
    if is_unknown_commit:
        return {
            "author_avatar": None,
            "author_login": None,
            "author_name": "",
            "branch": None,
            "fork_point_sha": None,
            "id": commit_id,
            "message": "",
            "parent_sha": None,
            "repository": "https://github.com/apache/arrow",
            "sha": "unknown commit",
            "timestamp": None,
            "url": "https://github.com/apache/arrow/commit/unknown commit",
        }

    result = {
        "author_avatar": "https://avatars.githubusercontent.com/u/878798?v=4",
        "author_login": "dianaclarke",
        "author_name": "Diana Clarke",
        "id": commit_id,
        "message": "ARROW-11771: [Developer][Archery] Move benchmark tests (so CI runs them)",
        "repository": "https://github.com/org/repo",
        "sha": "02addad336ba19a654f9c857ede546331be7b631",
        "url": "https://github.com/org/repo/commit/02addad336ba19a654f9c857ede546331be7b631",
        "parent_sha": "4beb514d071c9beec69b8917b5265e77ade22fb3",
        "timestamp": "2021-02-25T01:02:51",
        "links": {
            "list": "http://localhost/api/commits/",
            "self": "http://localhost/api/commits/%s/" % commit_id,
        },
        "branch": branch,
        "fork_point_sha": "02addad336ba19a654f9c857ede546331be7b631",
    }
    if parent_id:
        result["links"]["parent"] = "http://localhost/api/commits/%s/" % parent_id
    if not links:
        result.pop("links", None)
    return result


def _api_compare_entity(
    benchmark_result_ids, batch_ids, run_ids, benchmark_name, case_permutation, tags
):
    return {
        "unit": "s",
        "less_is_better": True,
        "baseline": {
            "benchmark_name": benchmark_name,
            "case_permutation": case_permutation,
            "language": "Python",
            "single_value_summary": 0.03637,
            "error": None,
            "benchmark_result_id": benchmark_result_ids[0],
            "batch_id": batch_ids[0],
            "run_id": run_ids[0],
            "tags": tags,
        },
        "contender": {
            "benchmark_name": benchmark_name,
            "case_permutation": case_permutation,
            "language": "Python",
            "single_value_summary": 0.03637,
            "error": None,
            "benchmark_result_id": benchmark_result_ids[1],
            "batch_id": batch_ids[1],
            "run_id": run_ids[1],
            "tags": tags,
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


def _api_compare_list(
    baseline_ids,
    contender_ids,
    batch_ids,
    run_ids,
    benchmark_names,
    case_permutations,
    tags,
):
    return [
        {
            "unit": "s",
            "less_is_better": True,
            "baseline": {
                "benchmark_name": benchmark_names[0],
                "case_permutation": case_permutations[0],
                "language": "Python",
                "single_value_summary": 0.03637,
                "error": None,
                "benchmark_result_id": baseline_ids[0],
                "batch_id": batch_ids[0],
                "run_id": run_ids[0],
                "tags": tags[0],
            },
            "contender": {
                "benchmark_name": benchmark_names[0],
                "case_permutation": case_permutations[0],
                "language": "Python",
                "single_value_summary": 0.03637,
                "error": None,
                "benchmark_result_id": contender_ids[0],
                "batch_id": batch_ids[1],
                "run_id": run_ids[1],
                "tags": tags[0],
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
                "benchmark_name": benchmark_names[1],
                "case_permutation": case_permutations[1],
                "language": "Python",
                "single_value_summary": 0.03637,
                "error": None,
                "benchmark_result_id": baseline_ids[1],
                "batch_id": batch_ids[0],
                "run_id": run_ids[0],
                "tags": tags[1],
            },
            "contender": {
                "benchmark_name": benchmark_names[1],
                "case_permutation": case_permutations[1],
                "language": "Python",
                "single_value_summary": 0.03637,
                "error": None,
                "benchmark_result_id": contender_ids[1],
                "batch_id": batch_ids[1],
                "run_id": run_ids[1],
                "tags": tags[1],
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
    ]


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


def _api_history_entity(benchmark_result_id, case_id, context_id, run_name):
    return [
        {
            "benchmark_result_id": benchmark_result_id,
            "case_id": case_id,
            "commit_hash": "02addad336ba19a654f9c857ede546331be7b631",
            "commit_msg": "ARROW-11771: [Developer][Archery] Move benchmark tests (so CI runs them)",
            "commit_timestamp": "2021-02-25T01:02:51",
            "context_id": context_id,
            "data": BENCHMARK_ENTITY["stats"]["data"],
            "hardware_hash": "diana-2-2-4-17179869184",
            "mean": 0.036369,
            "single_value_summary": 0.036369,
            "single_value_summary_type": "mean",
            "repository": "https://github.com/org/repo",
            "run_name": run_name,
            "times": BENCHMARK_ENTITY["stats"]["times"],
            "unit": "s",
            "zscorestats": {
                "begins_distribution_change": False,
                "residual": 0.0,
                "rolling_mean": 0.036369,
                "rolling_mean_excluding_this_commit": 0.036369,
                "rolling_stddev": 0.0,
                "segment_id": 0.0,
                "is_outlier": False,
            },
        }
    ]


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
    run_tags,
    run_reason,
    commit_id,
    parent_id,
    hardware_id,
    hardware_name,
    hardware_type,
    now,
):
    result = {
        "id": run_id,
        "tags": run_tags,
        "reason": run_reason,
        "timestamp": now,
        "commit": _api_commit_entity(commit_id, parent_id, links=False),
        "hardware": _api_hardware_entity(
            hardware_id, hardware_name, hardware_type, links=False
        ),
        "candidate_baseline_runs": {
            "fork_point": {
                "baseline_run_id": None,
                "commits_skipped": None,
                "error": "the contender run is already on the default branch",
            },
            "latest_default": {
                "baseline_run_id": None,
                "commits_skipped": None,
                "error": "the contender run is already on the default branch",
            },
            "parent": {
                "baseline_run_id": "598b44a1a3c94c63a4b17330c82c899e",
                "commits_skipped": ["7376b33c03298f273b9120ad83dd05da3d0c3bef"],
                "error": None,
            },
        },
    }
    return result


BENCHMARK_ENTITY = _api_benchmark_entity(
    "some-benchmark-uuid-1",
    "some-info-uuid-1",
    "some-context-uuid-1",
    "some-batch-uuid-1",
    "some-run-uuid-1",
    {"arbitrary": "tags"},
    "some run reason",
    "some-commit-uuid-1",
    "some-parent-commit-uuid-1",
    "known",
    "some_user_or_org:some_branch",
    "some-machine-uuid-1",
    "some-machine-name",
    "machine",
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
        "cpu_count": "2",
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
            "cpu_count": "2",
            "dataset": "nyctaxi_sample",
            "file_type": "parquet",
            "input_type": "arrow",
            "name": "file-read",
        },
        {
            "compression": "snappy",
            "cpu_count": "2",
            "dataset": "nyctaxi_sample",
            "file_type": "parquet",
            "input_type": "arrow",
            "name": "file-write",
        },
    ],
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
RUN_ENTITY_WITH_BASELINES = _api_run_entity(
    "some-run-uuid-1",
    {"arbitrary": "tags"},
    "some run reason",
    "some-commit-uuid-1",
    "some-parent-commit-uuid-1",
    "some-machine-uuid-1",
    "some-machine-name",
    "machine",
    "2021-02-04T17:22:05.225583",
)
RUN_ENTITY_WITHOUT_BASELINES = copy.deepcopy(RUN_ENTITY_WITH_BASELINES)
del RUN_ENTITY_WITHOUT_BASELINES["candidate_baseline_runs"]
RUN_LIST = [RUN_ENTITY_WITHOUT_BASELINES]

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
