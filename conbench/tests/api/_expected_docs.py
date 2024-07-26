{
    "components": {
        "responses": {
            "200": {"description": "OK"},
            "201": {"description": "Created"},
            "202": {"description": "No Content (accepted)"},
            "204": {"description": "No Content (success)"},
            "302": {"description": "Found"},
            "400": {
                "content": {
                    "application/json": {
                        "example": {
                            "code": 400,
                            "description": {
                                "_errors": ["Empty request body."],
                                "_schema": [
                                    "Invalid input type.",
                                    "Did you specify Content-type: application/json?",
                                ],
                            },
                            "name": "Bad Request",
                        },
                        "schema": {"$ref": "#/components/schemas/ErrorBadRequest"},
                    }
                },
                "description": "Bad Request",
            },
            "401": {
                "content": {
                    "application/json": {
                        "example": {"code": 401, "name": "Unauthorized"},
                        "schema": {"$ref": "#/components/schemas/Error"},
                    }
                },
                "description": "Unauthorized",
            },
            "404": {
                "content": {
                    "application/json": {
                        "example": {"code": 404, "name": "Not Found"},
                        "schema": {"$ref": "#/components/schemas/Error"},
                    }
                },
                "description": "Not Found",
            },
            "BenchmarkEntity": {
                "content": {
                    "application/json": {
                        "example": {
                            "batch_id": "some-batch-uuid-1",
                            "change_annotations": {},
                            "commit": {
                                "author_avatar": "https://avatars.githubusercontent.com/u/878798?v=4",
                                "author_login": "dianaclarke",
                                "author_name": "Diana Clarke",
                                "branch": "some_user_or_org:some_branch",
                                "fork_point_sha": "02addad336ba19a654f9c857ede546331be7b631",
                                "id": "some-commit-uuid-1",
                                "message": "ARROW-11771: [Developer][Archery] Move benchmark tests (so CI runs them)",
                                "parent_sha": "4beb514d071c9beec69b8917b5265e77ade22fb3",
                                "repository": "https://github.com/org/repo",
                                "sha": "02addad336ba19a654f9c857ede546331be7b631",
                                "timestamp": "2021-02-25T01:02:51",
                                "url": "https://github.com/org/repo/commit/02addad336ba19a654f9c857ede546331be7b631",
                            },
                            "commit_repo_url": "https://github.com/org/repo",
                            "error": None,
                            "hardware": {
                                "architecture_name": "x86_64",
                                "cpu_core_count": 2,
                                "cpu_frequency_max_hz": 3500000000,
                                "cpu_l1d_cache_bytes": 32768,
                                "cpu_l1i_cache_bytes": 32768,
                                "cpu_l2_cache_bytes": 262144,
                                "cpu_l3_cache_bytes": 4194304,
                                "cpu_model_name": "Intel(R) Core(TM) i7-7567U CPU @ 3.50GHz",
                                "cpu_thread_count": 4,
                                "gpu_count": 2,
                                "gpu_product_names": [
                                    "Tesla T4",
                                    "GeForce GTX 1060 3GB",
                                ],
                                "id": "some-machine-uuid-1",
                                "kernel_name": "19.6.0",
                                "memory_bytes": 17179869184,
                                "name": "some-machine-name",
                                "os_name": "macOS",
                                "os_version": "10.15.7",
                                "type": "machine",
                            },
                            "history_fingerprint": "some-hexdigest",
                            "id": "some-benchmark-uuid-1",
                            "links": {
                                "context": "http://localhost/api/contexts/some-context-uuid-1/",
                                "info": "http://localhost/api/info/some-info-uuid-1/",
                                "list": "http://localhost/api/benchmarks/",
                                "run": "http://localhost/api/runs/some-run-uuid-1/",
                                "self": "http://localhost/api/benchmarks/some-benchmark-uuid-1/",
                            },
                            "optional_benchmark_info": None,
                            "run_id": "some-run-uuid-1",
                            "run_reason": "some run reason",
                            "run_tags": {"arbitrary": "tags"},
                            "stats": {
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
                                "iqr": 0.030441500000000003,
                                "iterations": 10,
                                "max": 0.148896,
                                "mean": 0.036369,
                                "median": 0.008987499999999999,
                                "min": 0.004733,
                                "q1": 0.0065005,
                                "q3": 0.036942,
                                "stdev": 0.04919372267316679,
                                "time_unit": "s",
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
                            },
                            "tags": {
                                "compression": "snappy",
                                "cpu_count": "2",
                                "dataset": "nyctaxi_sample",
                                "file_type": "parquet",
                                "input_type": "arrow",
                                "name": "file-write",
                            },
                            "timestamp": "2020-11-25T21:02:44Z",
                            "validation": None,
                        }
                    }
                },
                "description": "OK",
            },
            "BenchmarkList": {
                "content": {
                    "application/json": {
                        "example": {
                            "data": [
                                {
                                    "batch_id": "some-batch-uuid-1",
                                    "change_annotations": {},
                                    "commit": {
                                        "author_avatar": "https://avatars.githubusercontent.com/u/878798?v=4",
                                        "author_login": "dianaclarke",
                                        "author_name": "Diana Clarke",
                                        "branch": "some_user_or_org:some_branch",
                                        "fork_point_sha": "02addad336ba19a654f9c857ede546331be7b631",
                                        "id": "some-commit-uuid-1",
                                        "message": "ARROW-11771: [Developer][Archery] Move benchmark tests (so CI runs them)",
                                        "parent_sha": "4beb514d071c9beec69b8917b5265e77ade22fb3",
                                        "repository": "https://github.com/org/repo",
                                        "sha": "02addad336ba19a654f9c857ede546331be7b631",
                                        "timestamp": "2021-02-25T01:02:51",
                                        "url": "https://github.com/org/repo/commit/02addad336ba19a654f9c857ede546331be7b631",
                                    },
                                    "commit_repo_url": "https://github.com/org/repo",
                                    "error": None,
                                    "hardware": {
                                        "architecture_name": "x86_64",
                                        "cpu_core_count": 2,
                                        "cpu_frequency_max_hz": 3500000000,
                                        "cpu_l1d_cache_bytes": 32768,
                                        "cpu_l1i_cache_bytes": 32768,
                                        "cpu_l2_cache_bytes": 262144,
                                        "cpu_l3_cache_bytes": 4194304,
                                        "cpu_model_name": "Intel(R) Core(TM) i7-7567U CPU @ 3.50GHz",
                                        "cpu_thread_count": 4,
                                        "gpu_count": 2,
                                        "gpu_product_names": [
                                            "Tesla T4",
                                            "GeForce GTX 1060 3GB",
                                        ],
                                        "id": "some-machine-uuid-1",
                                        "kernel_name": "19.6.0",
                                        "memory_bytes": 17179869184,
                                        "name": "some-machine-name",
                                        "os_name": "macOS",
                                        "os_version": "10.15.7",
                                        "type": "machine",
                                    },
                                    "history_fingerprint": "some-hexdigest",
                                    "id": "some-benchmark-uuid-1",
                                    "links": {
                                        "context": "http://localhost/api/contexts/some-context-uuid-1/",
                                        "info": "http://localhost/api/info/some-info-uuid-1/",
                                        "list": "http://localhost/api/benchmarks/",
                                        "run": "http://localhost/api/runs/some-run-uuid-1/",
                                        "self": "http://localhost/api/benchmarks/some-benchmark-uuid-1/",
                                    },
                                    "optional_benchmark_info": None,
                                    "run_id": "some-run-uuid-1",
                                    "run_reason": "some run reason",
                                    "run_tags": {"arbitrary": "tags"},
                                    "stats": {
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
                                        "iqr": 0.030441500000000003,
                                        "iterations": 10,
                                        "max": 0.148896,
                                        "mean": 0.036369,
                                        "median": 0.008987499999999999,
                                        "min": 0.004733,
                                        "q1": 0.0065005,
                                        "q3": 0.036942,
                                        "stdev": 0.04919372267316679,
                                        "time_unit": "s",
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
                                    },
                                    "tags": {
                                        "compression": "snappy",
                                        "cpu_count": "2",
                                        "dataset": "nyctaxi_sample",
                                        "file_type": "parquet",
                                        "input_type": "arrow",
                                        "name": "file-write",
                                    },
                                    "timestamp": "2020-11-25T21:02:44Z",
                                    "validation": None,
                                }
                            ],
                            "metadata": {"next_page_cursor": None},
                        }
                    }
                },
                "description": "OK",
            },
            "BenchmarkResultCreated": {
                "content": {
                    "application/json": {
                        "example": {
                            "batch_id": "some-batch-uuid-1",
                            "change_annotations": {},
                            "commit": {
                                "author_avatar": "https://avatars.githubusercontent.com/u/878798?v=4",
                                "author_login": "dianaclarke",
                                "author_name": "Diana Clarke",
                                "branch": "some_user_or_org:some_branch",
                                "fork_point_sha": "02addad336ba19a654f9c857ede546331be7b631",
                                "id": "some-commit-uuid-1",
                                "message": "ARROW-11771: [Developer][Archery] Move benchmark tests (so CI runs them)",
                                "parent_sha": "4beb514d071c9beec69b8917b5265e77ade22fb3",
                                "repository": "https://github.com/org/repo",
                                "sha": "02addad336ba19a654f9c857ede546331be7b631",
                                "timestamp": "2021-02-25T01:02:51",
                                "url": "https://github.com/org/repo/commit/02addad336ba19a654f9c857ede546331be7b631",
                            },
                            "commit_repo_url": "https://github.com/org/repo",
                            "error": None,
                            "hardware": {
                                "architecture_name": "x86_64",
                                "cpu_core_count": 2,
                                "cpu_frequency_max_hz": 3500000000,
                                "cpu_l1d_cache_bytes": 32768,
                                "cpu_l1i_cache_bytes": 32768,
                                "cpu_l2_cache_bytes": 262144,
                                "cpu_l3_cache_bytes": 4194304,
                                "cpu_model_name": "Intel(R) Core(TM) i7-7567U CPU @ 3.50GHz",
                                "cpu_thread_count": 4,
                                "gpu_count": 2,
                                "gpu_product_names": [
                                    "Tesla T4",
                                    "GeForce GTX 1060 3GB",
                                ],
                                "id": "some-machine-uuid-1",
                                "kernel_name": "19.6.0",
                                "memory_bytes": 17179869184,
                                "name": "some-machine-name",
                                "os_name": "macOS",
                                "os_version": "10.15.7",
                                "type": "machine",
                            },
                            "history_fingerprint": "some-hexdigest",
                            "id": "some-benchmark-uuid-1",
                            "links": {
                                "context": "http://localhost/api/contexts/some-context-uuid-1/",
                                "info": "http://localhost/api/info/some-info-uuid-1/",
                                "list": "http://localhost/api/benchmarks/",
                                "run": "http://localhost/api/runs/some-run-uuid-1/",
                                "self": "http://localhost/api/benchmarks/some-benchmark-uuid-1/",
                            },
                            "optional_benchmark_info": None,
                            "run_id": "some-run-uuid-1",
                            "run_reason": "some run reason",
                            "run_tags": {"arbitrary": "tags"},
                            "stats": {
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
                                "iqr": 0.030441500000000003,
                                "iterations": 10,
                                "max": 0.148896,
                                "mean": 0.036369,
                                "median": 0.008987499999999999,
                                "min": 0.004733,
                                "q1": 0.0065005,
                                "q3": 0.036942,
                                "stdev": 0.04919372267316679,
                                "time_unit": "s",
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
                            },
                            "tags": {
                                "compression": "snappy",
                                "cpu_count": "2",
                                "dataset": "nyctaxi_sample",
                                "file_type": "parquet",
                                "input_type": "arrow",
                                "name": "file-write",
                            },
                            "timestamp": "2020-11-25T21:02:44Z",
                            "validation": None,
                        }
                    }
                },
                "description": "Created \n\n The resulting entity URL is returned in the Location header.",
            },
            "CommitEntity": {
                "content": {
                    "application/json": {
                        "example": {
                            "author_avatar": "https://avatars.githubusercontent.com/u/878798?v=4",
                            "author_login": "dianaclarke",
                            "author_name": "Diana Clarke",
                            "branch": "some_user_or_org:some_branch",
                            "fork_point_sha": "02addad336ba19a654f9c857ede546331be7b631",
                            "id": "some-commit-uuid-1",
                            "links": {
                                "list": "http://localhost/api/commits/",
                                "parent": "http://localhost/api/commits/some-commit-parent-uuid-1/",
                                "self": "http://localhost/api/commits/some-commit-uuid-1/",
                            },
                            "message": "ARROW-11771: [Developer][Archery] Move benchmark tests (so CI runs them)",
                            "parent_sha": "4beb514d071c9beec69b8917b5265e77ade22fb3",
                            "repository": "https://github.com/org/repo",
                            "sha": "02addad336ba19a654f9c857ede546331be7b631",
                            "timestamp": "2021-02-25T01:02:51",
                            "url": "https://github.com/org/repo/commit/02addad336ba19a654f9c857ede546331be7b631",
                        }
                    }
                },
                "description": "OK",
            },
            "CommitList": {
                "content": {
                    "application/json": {
                        "example": [
                            {
                                "author_avatar": "https://avatars.githubusercontent.com/u/878798?v=4",
                                "author_login": "dianaclarke",
                                "author_name": "Diana Clarke",
                                "branch": "some_user_or_org:some_branch",
                                "fork_point_sha": "02addad336ba19a654f9c857ede546331be7b631",
                                "id": "some-commit-uuid-1",
                                "links": {
                                    "list": "http://localhost/api/commits/",
                                    "parent": "http://localhost/api/commits/some-commit-parent-uuid-1/",
                                    "self": "http://localhost/api/commits/some-commit-uuid-1/",
                                },
                                "message": "ARROW-11771: [Developer][Archery] Move benchmark tests (so CI runs them)",
                                "parent_sha": "4beb514d071c9beec69b8917b5265e77ade22fb3",
                                "repository": "https://github.com/org/repo",
                                "sha": "02addad336ba19a654f9c857ede546331be7b631",
                                "timestamp": "2021-02-25T01:02:51",
                                "url": "https://github.com/org/repo/commit/02addad336ba19a654f9c857ede546331be7b631",
                            }
                        ]
                    }
                },
                "description": "OK",
            },
            "CompareEntity": {
                "content": {
                    "application/json": {
                        "example": {
                            "analysis": {
                                "lookback_z_score": {
                                    "improvement_indicated": False,
                                    "regression_indicated": False,
                                    "z_score": 0.0,
                                    "z_threshold": 5.0,
                                },
                                "pairwise": {
                                    "improvement_indicated": False,
                                    "percent_change": 0.0,
                                    "percent_threshold": 5.0,
                                    "regression_indicated": False,
                                },
                            },
                            "baseline": {
                                "batch_id": "some-batch-uuid-1",
                                "benchmark_name": "file-read",
                                "benchmark_result_id": "some-benchmark-uuid-1",
                                "case_permutation": "snappy, nyctaxi_sample, parquet, arrow",
                                "error": None,
                                "language": "Python",
                                "result": {
                                    "batch_id": "some-batch-uuid-1",
                                    "change_annotations": {},
                                    "commit_repo_url": "https://github.com/org/repo",
                                    "error": None,
                                    "history_fingerprint": "some-hexdigest",
                                    "id": "some-benchmark-uuid-1",
                                    "optional_benchmark_info": None,
                                    "run_id": "some-run-uuid-1",
                                    "run_reason": "some run reason",
                                    "run_tags": {"arbitrary": "tags"},
                                    "stats": {
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
                                        "iqr": 0.030441500000000003,
                                        "iterations": 10,
                                        "max": 0.148896,
                                        "mean": 0.036369,
                                        "median": 0.008987499999999999,
                                        "min": 0.004733,
                                        "q1": 0.0065005,
                                        "q3": 0.036942,
                                        "stdev": 0.04919372267316679,
                                        "time_unit": "s",
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
                                    },
                                    "timestamp": "2020-11-25T21:02:44Z",
                                    "validation": None,
                                },
                                "run_id": "some-run-uuid-1",
                                "single_value_summary": 0.004733,
                                "tags": {
                                    "compression": "snappy",
                                    "cpu_count": "2",
                                    "dataset": "nyctaxi_sample",
                                    "file_type": "parquet",
                                    "input_type": "arrow",
                                    "name": "file-read",
                                },
                            },
                            "contender": {
                                "batch_id": "some-batch-uuid-2",
                                "benchmark_name": "file-read",
                                "benchmark_result_id": "some-benchmark-uuid-2",
                                "case_permutation": "snappy, nyctaxi_sample, parquet, arrow",
                                "error": None,
                                "language": "Python",
                                "result": {
                                    "batch_id": "some-batch-uuid-1",
                                    "change_annotations": {},
                                    "commit_repo_url": "https://github.com/org/repo",
                                    "error": None,
                                    "history_fingerprint": "some-hexdigest",
                                    "id": "some-benchmark-uuid-1",
                                    "optional_benchmark_info": None,
                                    "run_id": "some-run-uuid-1",
                                    "run_reason": "some run reason",
                                    "run_tags": {"arbitrary": "tags"},
                                    "stats": {
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
                                        "iqr": 0.030441500000000003,
                                        "iterations": 10,
                                        "max": 0.148896,
                                        "mean": 0.036369,
                                        "median": 0.008987499999999999,
                                        "min": 0.004733,
                                        "q1": 0.0065005,
                                        "q3": 0.036942,
                                        "stdev": 0.04919372267316679,
                                        "time_unit": "s",
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
                                    },
                                    "timestamp": "2020-11-25T21:02:44Z",
                                    "validation": None,
                                },
                                "run_id": "some-run-uuid-2",
                                "single_value_summary": 0.004733,
                                "tags": {
                                    "compression": "snappy",
                                    "cpu_count": "2",
                                    "dataset": "nyctaxi_sample",
                                    "file_type": "parquet",
                                    "input_type": "arrow",
                                    "name": "file-read",
                                },
                            },
                            "history_fingerprint": "history-fingerprint-1",
                            "less_is_better": True,
                            "unit": "s",
                        }
                    }
                },
                "description": "OK",
            },
            "CompareList": {
                "content": {
                    "application/json": {
                        "example": {
                            "data": [
                                {
                                    "analysis": {
                                        "lookback_z_score": {
                                            "improvement_indicated": False,
                                            "regression_indicated": False,
                                            "z_score": 0.0,
                                            "z_threshold": 5.0,
                                        },
                                        "pairwise": {
                                            "improvement_indicated": False,
                                            "percent_change": 0.0,
                                            "percent_threshold": 5.0,
                                            "regression_indicated": False,
                                        },
                                    },
                                    "baseline": {
                                        "batch_id": "some-batch-uuid-1",
                                        "benchmark_name": "file-read",
                                        "benchmark_result_id": "some-benchmark-uuid-1",
                                        "case_permutation": "snappy, nyctaxi_sample, parquet, arrow",
                                        "error": None,
                                        "language": "Python",
                                        "result": {
                                            "batch_id": "some-batch-uuid-1",
                                            "change_annotations": {},
                                            "commit_repo_url": "https://github.com/org/repo",
                                            "error": None,
                                            "history_fingerprint": "some-hexdigest",
                                            "id": "some-benchmark-uuid-1",
                                            "optional_benchmark_info": None,
                                            "run_id": "some-run-uuid-1",
                                            "run_reason": "some run reason",
                                            "run_tags": {"arbitrary": "tags"},
                                            "stats": {
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
                                                "iqr": 0.030441500000000003,
                                                "iterations": 10,
                                                "max": 0.148896,
                                                "mean": 0.036369,
                                                "median": 0.008987499999999999,
                                                "min": 0.004733,
                                                "q1": 0.0065005,
                                                "q3": 0.036942,
                                                "stdev": 0.04919372267316679,
                                                "time_unit": "s",
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
                                            },
                                            "timestamp": "2020-11-25T21:02:44Z",
                                            "validation": None,
                                        },
                                        "run_id": "some-run-uuid-1",
                                        "single_value_summary": 0.004733,
                                        "tags": {
                                            "compression": "snappy",
                                            "cpu_count": "2",
                                            "dataset": "nyctaxi_sample",
                                            "file_type": "parquet",
                                            "input_type": "arrow",
                                            "name": "file-read",
                                        },
                                    },
                                    "contender": {
                                        "batch_id": "some-batch-uuid-2",
                                        "benchmark_name": "file-read",
                                        "benchmark_result_id": "some-benchmark-uuid-3",
                                        "case_permutation": "snappy, nyctaxi_sample, parquet, arrow",
                                        "error": None,
                                        "language": "Python",
                                        "result": {
                                            "batch_id": "some-batch-uuid-1",
                                            "change_annotations": {},
                                            "commit_repo_url": "https://github.com/org/repo",
                                            "error": None,
                                            "history_fingerprint": "some-hexdigest",
                                            "id": "some-benchmark-uuid-1",
                                            "optional_benchmark_info": None,
                                            "run_id": "some-run-uuid-1",
                                            "run_reason": "some run reason",
                                            "run_tags": {"arbitrary": "tags"},
                                            "stats": {
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
                                                "iqr": 0.030441500000000003,
                                                "iterations": 10,
                                                "max": 0.148896,
                                                "mean": 0.036369,
                                                "median": 0.008987499999999999,
                                                "min": 0.004733,
                                                "q1": 0.0065005,
                                                "q3": 0.036942,
                                                "stdev": 0.04919372267316679,
                                                "time_unit": "s",
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
                                            },
                                            "timestamp": "2020-11-25T21:02:44Z",
                                            "validation": None,
                                        },
                                        "run_id": "some-run-uuid-2",
                                        "single_value_summary": 0.004733,
                                        "tags": {
                                            "compression": "snappy",
                                            "cpu_count": "2",
                                            "dataset": "nyctaxi_sample",
                                            "file_type": "parquet",
                                            "input_type": "arrow",
                                            "name": "file-read",
                                        },
                                    },
                                    "history_fingerprint": "history-fingerprint-1",
                                    "less_is_better": True,
                                    "unit": "s",
                                },
                                {
                                    "analysis": {
                                        "lookback_z_score": {
                                            "improvement_indicated": False,
                                            "regression_indicated": False,
                                            "z_score": 0.0,
                                            "z_threshold": 5.0,
                                        },
                                        "pairwise": {
                                            "improvement_indicated": False,
                                            "percent_change": 0.0,
                                            "percent_threshold": 5.0,
                                            "regression_indicated": False,
                                        },
                                    },
                                    "baseline": {
                                        "batch_id": "some-batch-uuid-1",
                                        "benchmark_name": "file-write",
                                        "benchmark_result_id": "some-benchmark-uuid-2",
                                        "case_permutation": "snappy, nyctaxi_sample, parquet, arrow",
                                        "error": None,
                                        "language": "Python",
                                        "result": {
                                            "batch_id": "some-batch-uuid-1",
                                            "change_annotations": {},
                                            "commit_repo_url": "https://github.com/org/repo",
                                            "error": None,
                                            "history_fingerprint": "some-hexdigest",
                                            "id": "some-benchmark-uuid-1",
                                            "optional_benchmark_info": None,
                                            "run_id": "some-run-uuid-1",
                                            "run_reason": "some run reason",
                                            "run_tags": {"arbitrary": "tags"},
                                            "stats": {
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
                                                "iqr": 0.030441500000000003,
                                                "iterations": 10,
                                                "max": 0.148896,
                                                "mean": 0.036369,
                                                "median": 0.008987499999999999,
                                                "min": 0.004733,
                                                "q1": 0.0065005,
                                                "q3": 0.036942,
                                                "stdev": 0.04919372267316679,
                                                "time_unit": "s",
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
                                            },
                                            "timestamp": "2020-11-25T21:02:44Z",
                                            "validation": None,
                                        },
                                        "run_id": "some-run-uuid-1",
                                        "single_value_summary": 0.004733,
                                        "tags": {
                                            "compression": "snappy",
                                            "cpu_count": "2",
                                            "dataset": "nyctaxi_sample",
                                            "file_type": "parquet",
                                            "input_type": "arrow",
                                            "name": "file-write",
                                        },
                                    },
                                    "contender": {
                                        "batch_id": "some-batch-uuid-2",
                                        "benchmark_name": "file-write",
                                        "benchmark_result_id": "some-benchmark-uuid-4",
                                        "case_permutation": "snappy, nyctaxi_sample, parquet, arrow",
                                        "error": None,
                                        "language": "Python",
                                        "result": {
                                            "batch_id": "some-batch-uuid-1",
                                            "change_annotations": {},
                                            "commit_repo_url": "https://github.com/org/repo",
                                            "error": None,
                                            "history_fingerprint": "some-hexdigest",
                                            "id": "some-benchmark-uuid-1",
                                            "optional_benchmark_info": None,
                                            "run_id": "some-run-uuid-1",
                                            "run_reason": "some run reason",
                                            "run_tags": {"arbitrary": "tags"},
                                            "stats": {
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
                                                "iqr": 0.030441500000000003,
                                                "iterations": 10,
                                                "max": 0.148896,
                                                "mean": 0.036369,
                                                "median": 0.008987499999999999,
                                                "min": 0.004733,
                                                "q1": 0.0065005,
                                                "q3": 0.036942,
                                                "stdev": 0.04919372267316679,
                                                "time_unit": "s",
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
                                            },
                                            "timestamp": "2020-11-25T21:02:44Z",
                                            "validation": None,
                                        },
                                        "run_id": "some-run-uuid-2",
                                        "single_value_summary": 0.004733,
                                        "tags": {
                                            "compression": "snappy",
                                            "cpu_count": "2",
                                            "dataset": "nyctaxi_sample",
                                            "file_type": "parquet",
                                            "input_type": "arrow",
                                            "name": "file-write",
                                        },
                                    },
                                    "history_fingerprint": "history-fingerprint-2",
                                    "less_is_better": True,
                                    "unit": "s",
                                },
                            ],
                            "metadata": {"next_page_cursor": None},
                        }
                    }
                },
                "description": "OK",
            },
            "ContextEntity": {
                "content": {
                    "application/json": {
                        "example": {
                            "arrow_compiler_flags": "-fPIC -arch x86_64 -arch x86_64 -std=c++11 -Qunused-arguments -fcolor-diagnostics -O3 -DNDEBUG",
                            "benchmark_language": "Python",
                            "id": "some-context-uuid-1",
                            "links": {
                                "list": "http://localhost/api/contexts/",
                                "self": "http://localhost/api/contexts/some-context-uuid-1/",
                            },
                        }
                    }
                },
                "description": "OK",
            },
            "ContextList": {
                "content": {
                    "application/json": {
                        "example": [
                            {
                                "arrow_compiler_flags": "-fPIC -arch x86_64 -arch x86_64 -std=c++11 -Qunused-arguments -fcolor-diagnostics -O3 -DNDEBUG",
                                "benchmark_language": "Python",
                                "id": "some-context-uuid-1",
                                "links": {
                                    "list": "http://localhost/api/contexts/",
                                    "self": "http://localhost/api/contexts/some-context-uuid-1/",
                                },
                            }
                        ]
                    }
                },
                "description": "OK",
            },
            "HardwareEntity": {
                "content": {
                    "application/json": {
                        "example": {
                            "architecture_name": "x86_64",
                            "cpu_core_count": 2,
                            "cpu_frequency_max_hz": 3500000000,
                            "cpu_l1d_cache_bytes": 32768,
                            "cpu_l1i_cache_bytes": 32768,
                            "cpu_l2_cache_bytes": 262144,
                            "cpu_l3_cache_bytes": 4194304,
                            "cpu_model_name": "Intel(R) Core(TM) i7-7567U CPU @ 3.50GHz",
                            "cpu_thread_count": 4,
                            "gpu_count": 2,
                            "gpu_product_names": ["Tesla T4", "GeForce GTX 1060 3GB"],
                            "id": "some-machine-uuid-1",
                            "kernel_name": "19.6.0",
                            "links": {
                                "list": "http://localhost/api/hardware/",
                                "self": "http://localhost/api/hardware/some-machine-uuid-1/",
                            },
                            "memory_bytes": 17179869184,
                            "name": "some-machine-name",
                            "os_name": "macOS",
                            "os_version": "10.15.7",
                            "type": "machine",
                        }
                    }
                },
                "description": "OK",
            },
            "HardwareList": {
                "content": {
                    "application/json": {
                        "example": [
                            {
                                "architecture_name": "x86_64",
                                "cpu_core_count": 2,
                                "cpu_frequency_max_hz": 3500000000,
                                "cpu_l1d_cache_bytes": 32768,
                                "cpu_l1i_cache_bytes": 32768,
                                "cpu_l2_cache_bytes": 262144,
                                "cpu_l3_cache_bytes": 4194304,
                                "cpu_model_name": "Intel(R) Core(TM) i7-7567U CPU @ 3.50GHz",
                                "cpu_thread_count": 4,
                                "gpu_count": 2,
                                "gpu_product_names": [
                                    "Tesla T4",
                                    "GeForce GTX 1060 3GB",
                                ],
                                "id": "some-machine-uuid-1",
                                "kernel_name": "19.6.0",
                                "links": {
                                    "list": "http://localhost/api/hardware/",
                                    "self": "http://localhost/api/hardware/some-machine-uuid-1/",
                                },
                                "memory_bytes": 17179869184,
                                "name": "some-machine-name",
                                "os_name": "macOS",
                                "os_version": "10.15.7",
                                "type": "machine",
                            }
                        ]
                    }
                },
                "description": "OK",
            },
            "HistoryList": {
                "content": {
                    "application/json": {
                        "example": {
                            "data": [
                                [
                                    {
                                        "benchmark_result_id": "some-benchmark-uuid-1",
                                        "case_id": "some-case-uuid-1",
                                        "commit_hash": "02addad336ba19a654f9c857ede546331be7b631",
                                        "commit_msg": "ARROW-11771: [Developer][Archery] Move benchmark tests (so CI runs them)",
                                        "commit_timestamp": "2021-02-25T01:02:51",
                                        "context_id": "some-context-uuid-1",
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
                                        "hardware_hash": "diana-2-2-4-17179869184",
                                        "history_fingerprint": "some-hexdigest",
                                        "mean": 0.036369,
                                        "repository": "https://github.com/org/repo",
                                        "result_timestamp": "2021-02-25T01:02:51",
                                        "run_name": "some run name",
                                        "run_tags": {
                                            "arbitrary": "tags",
                                            "name": "some run name",
                                        },
                                        "single_value_summary": 0.004733,
                                        "single_value_summary_type": "min",
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
                                        "zscorestats": {
                                            "begins_distribution_change": False,
                                            "is_outlier": False,
                                            "residual": 0.0,
                                            "rolling_mean": 0.004733,
                                            "rolling_mean_excluding_this_commit": 0.004733,
                                            "rolling_stddev": 0.0,
                                            "segment_id": 0.0,
                                        },
                                    }
                                ]
                            ],
                            "metadata": {"next_page_cursor": None},
                        }
                    }
                },
                "description": "OK",
            },
            "Index": {
                "content": {
                    "application/json": {
                        "example": {
                            "links": {
                                "benchmarks": "http://localhost/api/benchmarks/",
                                "commits": "http://localhost/api/commits/",
                                "contexts": "http://localhost/api/contexts/",
                                "docs": "http://localhost/api/docs.json",
                                "hardware": "http://localhost/api/hardware/",
                                "info": "http://localhost/api/info/",
                                "login": "http://localhost/api/login/",
                                "logout": "http://localhost/api/logout/",
                                "ping": "http://localhost/api/ping/",
                                "register": "http://localhost/api/register/",
                                "runs": "http://localhost/api/runs/",
                                "users": "http://localhost/api/users/",
                            }
                        }
                    }
                },
                "description": "OK",
            },
            "InfoEntity": {
                "content": {
                    "application/json": {
                        "example": {
                            "arrow_compiler_id": "AppleClang",
                            "arrow_compiler_version": "11.0.0.11000033",
                            "arrow_version": "2.0.0",
                            "benchmark_language_version": "Python 3.8.5",
                            "id": "some-info-uuid-1",
                            "links": {
                                "list": "http://localhost/api/info/",
                                "self": "http://localhost/api/info/some-info-uuid-1/",
                            },
                        }
                    }
                },
                "description": "OK",
            },
            "InfoList": {
                "content": {
                    "application/json": {
                        "example": [
                            {
                                "arrow_compiler_id": "AppleClang",
                                "arrow_compiler_version": "11.0.0.11000033",
                                "arrow_version": "2.0.0",
                                "benchmark_language_version": "Python 3.8.5",
                                "id": "some-info-uuid-1",
                                "links": {
                                    "list": "http://localhost/api/info/",
                                    "self": "http://localhost/api/info/some-info-uuid-1/",
                                },
                            }
                        ]
                    }
                },
                "description": "OK",
            },
            "Ping": {
                "content": {
                    "application/json": {
                        "example": {
                            "alembic_version": "0d4e564b1876",
                            "date": "Thu, 22 Oct 2020 15:53:55 UTC",
                        },
                        "schema": {"$ref": "#/components/schemas/Ping"},
                    }
                },
                "description": "OK",
            },
            "RunCreated": {
                "content": {"application/json": {"example": {}}},
                "description": "Created \n\n The resulting entity URL is returned in the Location header.",
            },
            "RunEntityWithBaselines": {
                "content": {
                    "application/json": {
                        "example": {
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
                                    "commits_skipped": [
                                        "7376b33c03298f273b9120ad83dd05da3d0c3bef"
                                    ],
                                    "error": None,
                                },
                            },
                            "commit": {
                                "author_avatar": "https://avatars.githubusercontent.com/u/878798?v=4",
                                "author_login": "dianaclarke",
                                "author_name": "Diana Clarke",
                                "branch": "some_user_or_org:some_branch",
                                "fork_point_sha": "02addad336ba19a654f9c857ede546331be7b631",
                                "id": "some-commit-uuid-1",
                                "message": "ARROW-11771: [Developer][Archery] Move benchmark tests (so CI runs them)",
                                "parent_sha": "4beb514d071c9beec69b8917b5265e77ade22fb3",
                                "repository": "https://github.com/org/repo",
                                "sha": "02addad336ba19a654f9c857ede546331be7b631",
                                "timestamp": "2021-02-25T01:02:51",
                                "url": "https://github.com/org/repo/commit/02addad336ba19a654f9c857ede546331be7b631",
                            },
                            "hardware": {
                                "architecture_name": "x86_64",
                                "cpu_core_count": 2,
                                "cpu_frequency_max_hz": 3500000000,
                                "cpu_l1d_cache_bytes": 32768,
                                "cpu_l1i_cache_bytes": 32768,
                                "cpu_l2_cache_bytes": 262144,
                                "cpu_l3_cache_bytes": 4194304,
                                "cpu_model_name": "Intel(R) Core(TM) i7-7567U CPU @ 3.50GHz",
                                "cpu_thread_count": 4,
                                "gpu_count": 2,
                                "gpu_product_names": [
                                    "Tesla T4",
                                    "GeForce GTX 1060 3GB",
                                ],
                                "id": "some-machine-uuid-1",
                                "kernel_name": "19.6.0",
                                "memory_bytes": 17179869184,
                                "name": "some-machine-name",
                                "os_name": "macOS",
                                "os_version": "10.15.7",
                                "type": "machine",
                            },
                            "id": "some-run-uuid-1",
                            "reason": "some run reason",
                            "tags": {"arbitrary": "tags"},
                            "timestamp": "2021-02-04T17:22:05.225583",
                        }
                    }
                },
                "description": "OK",
            },
            "RunEntityWithoutBaselines": {
                "content": {
                    "application/json": {
                        "example": {
                            "commit": {
                                "author_avatar": "https://avatars.githubusercontent.com/u/878798?v=4",
                                "author_login": "dianaclarke",
                                "author_name": "Diana Clarke",
                                "branch": "some_user_or_org:some_branch",
                                "fork_point_sha": "02addad336ba19a654f9c857ede546331be7b631",
                                "id": "some-commit-uuid-1",
                                "message": "ARROW-11771: [Developer][Archery] Move benchmark tests (so CI runs them)",
                                "parent_sha": "4beb514d071c9beec69b8917b5265e77ade22fb3",
                                "repository": "https://github.com/org/repo",
                                "sha": "02addad336ba19a654f9c857ede546331be7b631",
                                "timestamp": "2021-02-25T01:02:51",
                                "url": "https://github.com/org/repo/commit/02addad336ba19a654f9c857ede546331be7b631",
                            },
                            "hardware": {
                                "architecture_name": "x86_64",
                                "cpu_core_count": 2,
                                "cpu_frequency_max_hz": 3500000000,
                                "cpu_l1d_cache_bytes": 32768,
                                "cpu_l1i_cache_bytes": 32768,
                                "cpu_l2_cache_bytes": 262144,
                                "cpu_l3_cache_bytes": 4194304,
                                "cpu_model_name": "Intel(R) Core(TM) i7-7567U CPU @ 3.50GHz",
                                "cpu_thread_count": 4,
                                "gpu_count": 2,
                                "gpu_product_names": [
                                    "Tesla T4",
                                    "GeForce GTX 1060 3GB",
                                ],
                                "id": "some-machine-uuid-1",
                                "kernel_name": "19.6.0",
                                "memory_bytes": 17179869184,
                                "name": "some-machine-name",
                                "os_name": "macOS",
                                "os_version": "10.15.7",
                                "type": "machine",
                            },
                            "id": "some-run-uuid-1",
                            "reason": "some run reason",
                            "tags": {"arbitrary": "tags"},
                            "timestamp": "2021-02-04T17:22:05.225583",
                        }
                    }
                },
                "description": "OK",
            },
            "RunList": {
                "content": {
                    "application/json": {
                        "example": {
                            "data": [
                                {
                                    "commit": {
                                        "author_avatar": "https://avatars.githubusercontent.com/u/878798?v=4",
                                        "author_login": "dianaclarke",
                                        "author_name": "Diana Clarke",
                                        "branch": "some_user_or_org:some_branch",
                                        "fork_point_sha": "02addad336ba19a654f9c857ede546331be7b631",
                                        "id": "some-commit-uuid-1",
                                        "message": "ARROW-11771: [Developer][Archery] Move benchmark tests (so CI runs them)",
                                        "parent_sha": "4beb514d071c9beec69b8917b5265e77ade22fb3",
                                        "repository": "https://github.com/org/repo",
                                        "sha": "02addad336ba19a654f9c857ede546331be7b631",
                                        "timestamp": "2021-02-25T01:02:51",
                                        "url": "https://github.com/org/repo/commit/02addad336ba19a654f9c857ede546331be7b631",
                                    },
                                    "hardware": {
                                        "architecture_name": "x86_64",
                                        "cpu_core_count": 2,
                                        "cpu_frequency_max_hz": 3500000000,
                                        "cpu_l1d_cache_bytes": 32768,
                                        "cpu_l1i_cache_bytes": 32768,
                                        "cpu_l2_cache_bytes": 262144,
                                        "cpu_l3_cache_bytes": 4194304,
                                        "cpu_model_name": "Intel(R) Core(TM) i7-7567U CPU @ 3.50GHz",
                                        "cpu_thread_count": 4,
                                        "gpu_count": 2,
                                        "gpu_product_names": [
                                            "Tesla T4",
                                            "GeForce GTX 1060 3GB",
                                        ],
                                        "id": "some-machine-uuid-1",
                                        "kernel_name": "19.6.0",
                                        "memory_bytes": 17179869184,
                                        "name": "some-machine-name",
                                        "os_name": "macOS",
                                        "os_version": "10.15.7",
                                        "type": "machine",
                                    },
                                    "id": "some-run-uuid-1",
                                    "reason": "some run reason",
                                    "tags": {"arbitrary": "tags"},
                                    "timestamp": "2021-02-04T17:22:05.225583",
                                }
                            ],
                            "metadata": {"next_page_cursor": None},
                        }
                    }
                },
                "description": "OK",
            },
            "UserCreated": {
                "content": {
                    "application/json": {
                        "example": {
                            "email": "gwen@example.com",
                            "id": "some-user-uuid-1",
                            "links": {
                                "list": "http://localhost/api/users/",
                                "self": "http://localhost/api/users/some-user-uuid-1/",
                            },
                            "name": "Gwen Clarke",
                        }
                    }
                },
                "description": "Created \n\n The resulting entity URL is returned in the Location header.",
            },
            "UserEntity": {
                "content": {
                    "application/json": {
                        "example": {
                            "email": "gwen@example.com",
                            "id": "some-user-uuid-1",
                            "links": {
                                "list": "http://localhost/api/users/",
                                "self": "http://localhost/api/users/some-user-uuid-1/",
                            },
                            "name": "Gwen Clarke",
                        }
                    }
                },
                "description": "OK",
            },
            "UserList": {
                "content": {
                    "application/json": {
                        "example": [
                            {
                                "email": "gwen@example.com",
                                "id": "some-user-uuid-1",
                                "links": {
                                    "list": "http://localhost/api/users/",
                                    "self": "http://localhost/api/users/some-user-uuid-1/",
                                },
                                "name": "Gwen Clarke",
                            },
                            {
                                "email": "casey@example.com",
                                "id": "some-user-uuid-2",
                                "links": {
                                    "list": "http://localhost/api/users/",
                                    "self": "http://localhost/api/users/some-user-uuid-2/",
                                },
                                "name": "Casey Clarke",
                            },
                        ]
                    }
                },
                "description": "OK",
            },
        },
        "schemas": {
            "BenchmarkResultCreate": {
                "properties": {
                    "batch_id": {"type": "string"},
                    "change_annotations": {
                        "description": 'Post-analysis annotations about this BenchmarkResult that\ngive details about whether it represents a change, outlier, etc. in the overall\ndistribution of BenchmarkResults.\n\nCurrently-recognized keys that change Conbench behavior:\n\n- `begins_distribution_change` (bool) - Is this result the first result of a sufficiently\n"different" distribution than the result on the previous commit (for the same\nhardware/case/context)? That is, when evaluating whether future results are regressions\nor improvements, should we treat data from before this result as incomparable?\n',
                        "type": "object",
                    },
                    "cluster_info": {
                        "allOf": [{"$ref": "#/components/schemas/ClusterCreate"}],
                        "description": "Precisely one of `machine_info` and `cluster_info` must be provided.  The Conbench UI and API assume that all benchmark results with the same `run_id` share the same hardware. There is no technical enforcement of this on the server side, so some behavior may not work as intended if this assumption is broken by the client.",
                    },
                    "context": {
                        "description": "Required. Must be a JSON object (empty dictionary is allowed).  Relevant benchmark context (other than hardware/platform details and benchmark case parameters).  Conbench requires this object to remain constant when doing automated timeseries analysis (this breaks history).  Use this to store for example compiler flags or a runtime version that you expect to have significant impact on measurement results.",
                        "type": "object",
                    },
                    "error": {
                        "description": 'Details about an error that occurred while the benchmark was running (free-form JSON).  You may populate both this field and the "data" field of the "stats" object. In that case, the "data" field measures the metric\'s values before the error occurred. Those values will not be compared to non-errored values in analyses and comparisons.',
                        "type": "object",
                    },
                    "github": {
                        "allOf": [{"$ref": "#/components/schemas/SchemaGitHubCreate"}],
                        "description": "GitHub-flavored commit information. Required.  Use this object to tell Conbench with which specific state of benchmarked code (repository identifier, possible commit hash) the BenchmarkResult is associated.",
                    },
                    "info": {
                        "description": "Optional.  Arbitrary metadata associated with this benchmark result.  Ignored when assembling timeseries across results (differences do not break history).  Must be a JSON object if provided. A flat string-string mapping is recommended (not yet enforced).  This can be useful for example for storing URLs pointing to build artifacts. You can also use this to store environmental properties that you potentially would like to review later (a compiler version, or runtime version), and generally any kind of information that can later be useful for debugging unexpected measurements.",
                        "type": "object",
                    },
                    "machine_info": {
                        "allOf": [{"$ref": "#/components/schemas/MachineCreate"}],
                        "description": "Precisely one of `machine_info` and `cluster_info` must be provided.  The Conbench UI and API assume that all benchmark results with the same `run_id` share the same hardware. There is no technical enforcement of this on the server side, so some behavior may not work as intended if this assumption is broken by the client.",
                    },
                    "optional_benchmark_info": {
                        "description": "Deprecated. Use `info` instead.",
                        "type": "object",
                    },
                    "run_id": {
                        "description": 'Arbitrary identifier that you can use to group benchmark results. Typically used for a "run" of benchmarks (i.e. a single run of a CI pipeline) on a single commit and hardware. Required.  The API does not ensure uniqueness (and, correspondingly, does not detect collisions). If your use case relies on this grouping construct then use a client-side ID generation scheme with negligible likelihood for collisions (e.g., UUID type 4 or similar).  The Conbench UI and API assume that all benchmark results with the same `run_id` share the same `run_tags`, `run_reason`, hardware, and commit. There is no technical enforcement of this on the server side, so some behavior may not work as intended if this assumption is broken by the client.',
                        "type": "string",
                    },
                    "run_name": {
                        "description": "A legacy attribute. Use `run_tags` instead. Optional.",
                        "type": "string",
                    },
                    "run_reason": {
                        "description": 'Reason for the run (optional, does not need to be unique). A low-cardinality tag like `"commit"` or `"pull-request"`, used to group and filter runs, with special treatment in the UI and API.  The Conbench UI and API assume that all benchmark results with the same `run_id` share the same `run_reason`. There is no technical enforcement of this on the server side, so some behavior may not work as intended if this assumption is broken by the client.',
                        "type": "string",
                    },
                    "run_tags": {
                        "description": "An optional mapping of arbitrary keys and values that describe the CI run. These are used to group and filter runs in the UI and API. Do not include `run_reason` here; it should be provided below.  For legacy reasons, if `run_name` is given when POSTing a benchmark result, it will be added to `run_tags` automatically under the `name` key. This will be its new permanent home.  The Conbench UI and API assume that all benchmark results with the same `run_id` share the same `run_tags`. There is no technical enforcement of this on the server side, so some behavior may not work as intended if this assumption is broken by the client.",
                        "type": "object",
                    },
                    "stats": {"$ref": "#/components/schemas/BenchmarkResultStats"},
                    "tags": {
                        "description": 'The set of key/value pairs that represents a specific benchmark case permutation (a specific set of parameters).  Keys must be non-empty strings. Values should be non-empty strings.  The special key "name" must be provided with a string value: it indicates the name of the conceptual benchmark that was performed for obtaining the result at hand. All case permutations of a conceptual benchmark by definition have this name in common.  Example: a conceptual benchmark with name "foo-write-file" might have meaningful case permutations involving tag names such as `compression-method` (values: `gzip`, `lzma`, ...), `file-format` (values: `csv`, `hdf5`, ...), `dataset-name` (values: `foo`, `bar`, ...).  For each conceptual benchmark, it is valid to have one or many case permutations (if you supply only "name", then there is necessarily a single mutation with the special property that it has no other tags set).  We advise that each unique case (as defined by the complete set of key/value pairs) indeed corresponds to unique benchmarking behavior. That is, typically, all key/value pairs other than "name" directly correspond to input parameters to the same conceptual benchmark. Note however that Conbench benchmark result tags are not meant to store type information. Benchmark authors are advised to find a custom convention for mapping benchmark input parameters to tags.  Currently, primitive value types (int, float, boolean) are accepted, but stored as strings. Keys with empty string values or null values are ignored. In the future, Conbench might disallow all non-string values.',
                        "type": "object",
                    },
                    "timestamp": {
                        "description": "A datetime string indicating the time at which the benchmark was started. Expected to be in ISO 8601 notation. Timezone-aware notation recommended. Timezone-naive strings are interpreted in UTC. Fractions of seconds can be provided but are not returned by the API. Example value: 2022-11-25T22:02:42Z. This timestamp defines the default sorting order when viewing a list of benchmarks via the UI or when enumerating benchmarks via the /api/benchmarks/ HTTP endpoint.",
                        "format": "date-time",
                        "type": "string",
                    },
                    "validation": {
                        "description": "Benchmark results validation metadata (e.g., errors, validation types).",
                        "type": "object",
                    },
                },
                "required": [
                    "batch_id",
                    "context",
                    "github",
                    "run_id",
                    "tags",
                    "timestamp",
                ],
                "type": "object",
            },
            "BenchmarkResultStats": {
                "properties": {
                    "data": {
                        "description": 'A list of measurement results (e.g. duration, throughput).  Each value in this list is meant to correspond to one repetition of ideally the exact same measurement.  We recommend to repeat a measurement N times (3-6) for enabling systematic stability analysis.  Values are expected to be ordered in the order the repetitions were executed (the first element corresponds to the first repetition, the second element is the second repetition, etc.).  Values must be numeric or `null`: if one repetition failed but others did not you can mark the failed repetition as `null`.  Note that you may populate both this field and the "error" field in the top level of the benchmark result payload.  If any of the values in `data` is `null` or if the `error` field is set then Conbench will not include any of the reported data in automated analyses.',
                        "items": {"nullable": True, "type": "number"},
                        "type": "array",
                    },
                    "iqr": {
                        "description": "The inter-quartile range from `data`, will be calculated on the server if not present (the preferred method), but can be overridden if sent. Will be marked `null` if any iterations are missing.",
                        "type": "number",
                    },
                    "iterations": {
                        "description": "Here you can optionally store the number of microbenchmark iterations executed (per repetition). Treated as metadata. Do not store the number of repetitions here; this is reflected by the length of the `data` array.",
                        "type": "integer",
                    },
                    "max": {
                        "description": "The maximum from `data`, will be calculated on the server if not present (the preferred method), but can be overridden if sent. Will be marked `null` if any iterations are missing.",
                        "type": "number",
                    },
                    "mean": {
                        "description": "The mean from `data`, will be calculated on the server if not present (the preferred method), but can be overridden if sent. Will be marked `null` if any iterations are missing.",
                        "type": "number",
                    },
                    "median": {
                        "description": "The median from `data`, will be calculated on the server if not present (the preferred method), but can be overridden if sent. Will be marked `null` if any iterations are missing.",
                        "type": "number",
                    },
                    "min": {
                        "description": "The minimum from `data`, will be calculated on the server if not present (the preferred method), but can be overridden if sent. Will be marked `null` if any iterations are missing.",
                        "type": "number",
                    },
                    "q1": {
                        "description": "The first quartile from `data`, will be calculated on the server if not present (the preferred method), but can be overridden if sent. Will be marked `null` if any iterations are missing.",
                        "type": "number",
                    },
                    "q3": {
                        "description": "The third quartile from `data`, will be calculated on the server if not present (the preferred method), but can be overridden if sent. Will be marked `null` if any iterations are missing.",
                        "type": "number",
                    },
                    "stdev": {
                        "description": "The standard deviation from `data`, will be calculated on the server if not present (the preferred method), but can be overridden if sent. Will be marked `null` if any iterations are missing.",
                        "type": "number",
                    },
                    "time_unit": {
                        "description": "The unit of the times object (e.g. seconds, nanoseconds)",
                        "type": "string",
                    },
                    "times": {
                        "description": "Here, you can provide a list of benchmark durations. That can make sense if `data` is not a duration measure.  Optional. If provided, must be a list of numbers. `null` is allowed to represent a failed repetition.  The values should be ordered in the order the repetitions executed (the first element corresponds to the first repetition, the second element to the second repetition, etc).  The `time_unit` field (see below) should be provided, too.  Consider this as metadata. You can discover this field later via API and UI, however Conbench as of today does not do validation or analysis on the data.",
                        "items": {"nullable": True, "type": "number"},
                        "type": "array",
                    },
                    "unit": {
                        "description": "Unit of the numbers in `data`. Allowed values: B, B/s, s, ns, i/s",
                        "type": "string",
                    },
                },
                "required": ["data", "unit"],
                "type": "object",
            },
            "BenchmarkResultUpdate": {
                "properties": {
                    "change_annotations": {
                        "description": 'Post-analysis annotations about this BenchmarkResult that\ngive details about whether it represents a change, outlier, etc. in the overall\ndistribution of BenchmarkResults.\n\nCurrently-recognized keys that change Conbench behavior:\n\n- `begins_distribution_change` (bool) - Is this result the first result of a sufficiently\n"different" distribution than the result on the previous commit (for the same\nhardware/case/context)? That is, when evaluating whether future results are regressions\nor improvements, should we treat data from before this result as incomparable?\n\n\nThis endpoint will only update the user-specified keys, and leave the rest alone. To\ndelete an existing key, set the value to null.\n',
                        "type": "object",
                    }
                },
                "type": "object",
            },
            "ClusterCreate": {
                "properties": {
                    "info": {
                        "description": "Information related to cluster (e.g. `hosts`, `nodes` or `number of workers`) configured to run a set of benchmarks. Used to differentiate between similar benchmark runs performed on different sets of hardware",
                        "type": "object",
                    },
                    "name": {
                        "description": "Distinct name of the cluster, to be displayed on the web UI.",
                        "type": "string",
                    },
                    "optional_info": {
                        "description": "Additional optional information about the cluster, which is not likely to impact the benchmark performance (e.g. region, settings like logging type, etc). Despite the name, this field is required. An empty dictionary can be passed.",
                        "type": "object",
                    },
                },
                "required": ["info", "name", "optional_info"],
                "type": "object",
            },
            "Error": {
                "additionalProperties": True,
                "properties": {
                    "code": {"description": "HTTP error code", "type": "integer"},
                    "name": {"description": "HTTP error name", "type": "string"},
                },
                "required": ["code", "name"],
                "type": "object",
            },
            "ErrorBadRequest": {
                "additionalProperties": True,
                "properties": {
                    "code": {"description": "HTTP error code", "type": "integer"},
                    "description": {
                        "allOf": [{"$ref": "#/components/schemas/ErrorValidation"}],
                        "description": "Additional information about the bad request",
                    },
                    "name": {"description": "HTTP error name", "type": "string"},
                },
                "required": ["code", "name"],
                "type": "object",
            },
            "ErrorValidation": {
                "properties": {
                    "_errors": {
                        "description": "Validation error messages",
                        "items": {"type": "string"},
                        "type": "array",
                    },
                    "_schema": {
                        "description": "Schema error messages",
                        "items": {"type": "string"},
                        "type": "array",
                    },
                },
                "type": "object",
            },
            "Login": {
                "properties": {
                    "email": {"format": "email", "type": "string"},
                    "password": {"type": "string"},
                },
                "required": ["email", "password"],
                "type": "object",
            },
            "MachineCreate": {
                "properties": {
                    "architecture_name": {"type": "string"},
                    "cpu_core_count": {"type": "integer"},
                    "cpu_frequency_max_hz": {"type": "integer"},
                    "cpu_l1d_cache_bytes": {"type": "integer"},
                    "cpu_l1i_cache_bytes": {"type": "integer"},
                    "cpu_l2_cache_bytes": {"type": "integer"},
                    "cpu_l3_cache_bytes": {"type": "integer"},
                    "cpu_model_name": {"type": "string"},
                    "cpu_thread_count": {"type": "integer"},
                    "gpu_count": {"type": "integer"},
                    "gpu_product_names": {"items": {"type": "string"}, "type": "array"},
                    "kernel_name": {"type": "string"},
                    "memory_bytes": {"type": "integer"},
                    "name": {"type": "string"},
                    "os_name": {"type": "string"},
                    "os_version": {"type": "string"},
                },
                "required": [
                    "architecture_name",
                    "cpu_core_count",
                    "cpu_frequency_max_hz",
                    "cpu_l1d_cache_bytes",
                    "cpu_l1i_cache_bytes",
                    "cpu_l2_cache_bytes",
                    "cpu_l3_cache_bytes",
                    "cpu_model_name",
                    "cpu_thread_count",
                    "gpu_count",
                    "gpu_product_names",
                    "kernel_name",
                    "memory_bytes",
                    "name",
                    "os_name",
                    "os_version",
                ],
                "type": "object",
            },
            "Ping": {
                "properties": {
                    "date": {
                        "description": "Current date & time",
                        "format": "date-time",
                        "type": "string",
                    }
                },
                "required": ["date"],
                "type": "object",
            },
            "Register": {
                "properties": {
                    "email": {"format": "email", "type": "string"},
                    "name": {"type": "string"},
                    "password": {"type": "string"},
                    "secret": {"type": "string"},
                },
                "required": ["email", "name", "password", "secret"],
                "type": "object",
            },
            "SchemaGitHubCreate": {
                "properties": {
                    "branch": {
                        "description": "This is an alternative way to indicate that this benchmark result has been obtained for a commit that is not on the default branch. Do not use this for GitHub pull requests (use the `pr_number` argument for that, see above).  If set, this needs to be a string of the form `org:branch`.  Warning: currently, if `branch` and `pr_number` are both provided, there is no error and `branch` takes precedence. Only use this when you know what you are doing.",
                        "nullable": True,
                        "type": "string",
                    },
                    "commit": {
                        "description": "The commit hash of the benchmarked code.  Must not be an empty string.  Expected to be a known commit in the repository as specified by the `repository` URL property below.  This property is optional. If not provided, it means that this benchmark result is not associated with a reproducible commit in the given repository.  Not associating a benchmark result with a commit hash has special, limited purpose (pre-merge benchmarks, testing). It generally means that this benchmark result will not be considered for time series analysis along a commit tree.",
                        "type": "string",
                    },
                    "pr_number": {
                        "description": "If set, this needs to be an integer or a stringified integer.  This is the recommended way to indicate that this benchmark result has been obtained for a specific pull request branch. Conbench will use this pull request number to (try to) obtain branch information via the GitHub HTTP API.  Set this to `null` or leave this out to indicate that this benchmark result has been obtained for the default branch.",
                        "nullable": True,
                        "type": "integer",
                    },
                    "repository": {
                        "description": 'URL pointing to the benchmarked GitHub repository.  Must be provided in the format https://github.com/org/repo.  Trailing slashes are stripped off before database insertion.  As of the time of writing, only URLs starting with "https://github.com" are allowed. Conbench interacts with the GitHub HTTP API in order to fetch information about the benchmarked repository. The Conbench user/operator is expected to ensure that Conbench is configured with a GitHub HTTP API authentication token that is privileged to read commit information for the repository specified here.  Support for non-GitHub repositories (e.g. GitLab) or auxiliary repositories is interesting, but not yet well specified.',
                        "type": "string",
                    },
                },
                "required": ["repository"],
                "type": "object",
            },
            "UserCreate": {
                "properties": {
                    "email": {"format": "email", "type": "string"},
                    "name": {"type": "string"},
                    "password": {"type": "string"},
                },
                "required": ["email", "name", "password"],
                "type": "object",
            },
            "UserUpdate": {
                "properties": {
                    "email": {"format": "email", "type": "string"},
                    "name": {"type": "string"},
                    "password": {"type": "string"},
                },
                "type": "object",
            },
        },
    },
    "info": {"title": "local-dev-conbench", "version": "1.0.0"},
    "openapi": "3.0.2",
    "paths": {
        "/api/": {
            "get": {
                "description": "Get a list of API endpoints.",
                "responses": {
                    "200": {"$ref": "#/components/responses/Index"},
                    "401": {"$ref": "#/components/responses/401"},
                },
                "tags": ["Index"],
            }
        },
        "/api/benchmarks/": {
            "get": {
                "description": 'Return benchmark results.\n\nNote that this endpoint does not provide on-the-fly change detection\nanalysis (lookback z-score method) since the "baseline" is ill-defined.\n\nThis endpoint implements pagination; see the `cursor` and `page_size` query\nparameters for how it works.\n\nFor legacy reasons, this endpoint will not return results from before\n`2023-06-03 UTC`, unless the `run_id` query parameter is used to filter\nbenchmark results.\n',
                "parameters": [
                    {
                        "description": "Filter results to one specific `run_id`. Using this argument allows the\nresponse to return results from before `2023-06-03 UTC`.\n",
                        "in": "query",
                        "name": "run_id",
                        "schema": {"type": "string"},
                    },
                    {
                        "description": "Filter results to one specific `run_reason`.",
                        "in": "query",
                        "name": "run_reason",
                        "schema": {"type": "string"},
                    },
                    {
                        "description": "A cursor for pagination through matching results in reverse DB insertion\norder.\n\nTo get the first page of results, leave out this query parameter or\nsubmit `null`. The response's `metadata` key will contain a\n`next_page_cursor` key, which will contain the cursor to provide to this\nquery parameter in order to get the next page. (If there is expected to\nbe no data in the next page, the `next_page_cursor` will be `null`.)\n\nThe first page will contain the `page_size` most recent results matching\nthe given filter(s). Each subsequent page will have up to `page_size`\nresults, going backwards in time in DB insertion order, until there are\nno more matching results or the benchmark result timestamps reach\n`2023-06-03 UTC` (if the `run_id` filter isn't used; see above).\n\nImplementation detail: currently, the next page's cursor value is equal\nto the ID of the earliest result in the current page. A page of results\nis therefore defined as the `page_size` latest results with an ID\nlexicographically less than the cursor value.\n",
                        "in": "query",
                        "name": "cursor",
                        "schema": {"nullable": True, "type": "string"},
                    },
                    {
                        "description": "The size of pages for pagination (see `cursor`). Default 100. Max 1000.\n",
                        "in": "query",
                        "name": "page_size",
                        "schema": {"maximum": 1000, "minimum": 1, "type": "integer"},
                    },
                    {
                        "description": "The earliest (least recent) benchmark result timestamp to return. (Note\nthat this parameter does not affect the behavior of returning only\nresults after `2023-06-03 UTC` without a `run_id` provided.)\n\nThis parameter will also filter out results that were inserted into the\ndatabase before the given timestamp, independently of the user-given\nbenchmark result timestamp. This should not be a problem if you never\nupload data with a timestamp in the future, but if you do, you may get\nunexpected results around this boundary.\n",
                        "in": "query",
                        "name": "earliest_timestamp",
                        "schema": {"format": "date-time", "type": "string"},
                    },
                    {
                        "description": "The latest (most recent) benchmark result timestamp to return.",
                        "in": "query",
                        "name": "latest_timestamp",
                        "schema": {"format": "date-time", "type": "string"},
                    },
                ],
                "responses": {
                    "200": {"$ref": "#/components/responses/BenchmarkList"},
                    "401": {"$ref": "#/components/responses/401"},
                },
                "tags": ["Benchmarks"],
            },
            "post": {
                "description": "Submit a BenchmarkResult within a specific Run.\nIf the Run (as defined by its Run ID) is not known yet in the database it gets implicitly created, using details provided in this request. If the Run ID matches an existing run, then the rest of the fields describing the Run (such as name, hardware info, ...} are silently ignored.",
                "requestBody": {
                    "content": {
                        "application/json": {
                            "schema": {
                                "$ref": "#/components/schemas/BenchmarkResultCreate"
                            }
                        }
                    }
                },
                "responses": {
                    "201": {"$ref": "#/components/responses/BenchmarkResultCreated"},
                    "400": {"$ref": "#/components/responses/400"},
                    "401": {"$ref": "#/components/responses/401"},
                },
                "tags": ["Benchmarks"],
            },
        },
        "/api/benchmarks/{benchmark_result_id}/": {
            "delete": {
                "description": "Delete a benchmark result.",
                "parameters": [
                    {
                        "in": "path",
                        "name": "benchmark_result_id",
                        "required": True,
                        "schema": {"type": "string"},
                    }
                ],
                "responses": {
                    "204": {"$ref": "#/components/responses/204"},
                    "401": {"$ref": "#/components/responses/401"},
                    "404": {"$ref": "#/components/responses/404"},
                },
                "tags": ["Benchmarks"],
            },
            "get": {
                "description": "Get a specific benchmark result.\n",
                "parameters": [
                    {
                        "in": "path",
                        "name": "benchmark_result_id",
                        "required": True,
                        "schema": {"type": "string"},
                    }
                ],
                "responses": {
                    "200": {"$ref": "#/components/responses/BenchmarkEntity"},
                    "401": {"$ref": "#/components/responses/401"},
                    "404": {"$ref": "#/components/responses/404"},
                },
                "tags": ["Benchmarks"],
            },
            "put": {
                "description": "Edit a benchmark result.",
                "parameters": [
                    {
                        "in": "path",
                        "name": "benchmark_result_id",
                        "required": True,
                        "schema": {"type": "string"},
                    }
                ],
                "requestBody": {
                    "content": {
                        "application/json": {
                            "schema": {
                                "$ref": "#/components/schemas/BenchmarkResultUpdate"
                            }
                        }
                    }
                },
                "responses": {
                    "200": {"$ref": "#/components/responses/BenchmarkEntity"},
                    "401": {"$ref": "#/components/responses/401"},
                    "404": {"$ref": "#/components/responses/404"},
                },
                "tags": ["Benchmarks"],
            },
        },
        "/api/commits/": {
            "get": {
                "description": "Get a list of commits.",
                "responses": {
                    "200": {"$ref": "#/components/responses/CommitList"},
                    "401": {"$ref": "#/components/responses/401"},
                },
                "tags": ["Commits"],
            }
        },
        "/api/commits/{commit_id}/": {
            "get": {
                "description": "Get a commit.",
                "parameters": [
                    {
                        "in": "path",
                        "name": "commit_id",
                        "required": True,
                        "schema": {"type": "string"},
                    }
                ],
                "responses": {
                    "200": {"$ref": "#/components/responses/CommitEntity"},
                    "401": {"$ref": "#/components/responses/401"},
                    "404": {"$ref": "#/components/responses/404"},
                },
                "tags": ["Commits"],
            }
        },
        "/api/compare/benchmark-results/{compare_ids}/": {
            "get": {
                "description": "Compare a baseline and contender benchmark result.\n\nReturns basic information about the baseline and contender benchmark results\nas well as some analyses comparing the performance of the contender to the\nbaseline.\n\nThe `pairwise` analysis computes the percentage difference of the\ncontender's single-value summary (SVS) to the baseline's SVS. The reported\ndifference is signed such that a more negative value indicates more of a\nperformance regression. This difference is then thresholded such that values\nmore extreme than the threshold are marked as `regression_indicated` or\n`improvement_indicated`. The threshold is 5.0% by default, but can be\nchanged via the `threshold` query parameter, which should be a positive\npercent value.\n\nThe `pairwise` analysis may be `null` if either benchmark result does not\nhave a SVS, or if the baseline result's SVS is 0.\n\nThe `lookback_z_score` analysis compares the contender's SVS value to a\nbaseline distribution of benchmark result SVSs (from the git history of the\nbaseline result) via the so-called lookback z-score method. The reported\nz-score is also signed such that a more negative value indicates more of a\nperformance regression, and thresholded. The threshold z-score is 5.0 by\ndefault, but can be changed via the `threshold_z` query parameter, which\nshould be a positive number.\n\nThe `lookback_z_score` analysis object may be `null` if a z-score cannot be\ncomputed for the contender benchmark result, due to not finding a baseline\ndistribution that matches the contender benchmark result. More details about\nthis analysis can be found at\nhttps://conbench.github.io/conbench/pages/lookback_zscore.html.\n\nIf either benchmark result is not found, this endpoint will raise a 404. If\nthe benchmark results don't have the same unit, this endpoint will raise a\n400. Otherwise, you may compare any two benchmark results, no matter if\ntheir cases, contexts, hardwares, or even repositories don't match.\n",
                "parameters": [
                    {
                        "example": "<baseline_id>...<contender_id>",
                        "in": "path",
                        "name": "compare_ids",
                        "required": True,
                        "schema": {"type": "string"},
                    },
                    {"in": "query", "name": "threshold", "schema": {"type": "number"}},
                    {
                        "in": "query",
                        "name": "threshold_z",
                        "schema": {"type": "number"},
                    },
                ],
                "responses": {
                    "200": {"$ref": "#/components/responses/CompareEntity"},
                    "400": {"$ref": "#/components/responses/400"},
                    "401": {"$ref": "#/components/responses/401"},
                    "404": {"$ref": "#/components/responses/404"},
                },
                "tags": ["Comparisons"],
            }
        },
        "/api/compare/runs/{compare_ids}/": {
            "get": {
                "description": "Compare all benchmark results between two runs.\n\nThis endpoint will return a list of comparison objects, pairing benchmark\nresults from the given baseline and contender runs that have the same\nhistory fingerprint. The comparison object is the same as the `GET\n/api/compare/benchmark-results/` response; see that endpoint's documentation\nfor details.\n\nIf a benchmark result from one run does not have a matching result in the\nother run, a comparison object will still be returned for it, with the other\nresult's information replaced by `null` and each analysis also `null`.\n\nIf a benchmark result from one run has multiple matching results in the\nother run, a comparison object will be returned for each match. Filtering\nmust be done clientside.\n\nThis endpoint implements pagination; see the `cursor` and `page_size` query\nparameters for how it works.\n",
                "parameters": [
                    {
                        "description": "The baseline and contender run IDs, separated by `...`.",
                        "example": "<baseline_id>...<contender_id>",
                        "in": "path",
                        "name": "compare_ids",
                        "required": True,
                        "schema": {"type": "string"},
                    },
                    {
                        "description": "The threshold for the `pairwise` analysis, in percent. Defaults to 5.0.\n",
                        "in": "query",
                        "name": "threshold",
                        "schema": {"type": "number"},
                    },
                    {
                        "description": "The threshold for the `lookback_z_score` analysis, in z-score. Defaults\nto 5.0.\n",
                        "in": "query",
                        "name": "threshold_z",
                        "schema": {"type": "number"},
                    },
                    {
                        "description": "A cursor for pagination through comparisons in alphabetical order by\n`history_fingerprint`.\n\nTo get the first page of comparisons, leave out this query parameter or\nsubmit `null`. The response's `metadata` key will contain a\n`next_page_cursor` key, which will contain the cursor to provide to this\nquery parameter in order to get the next page. (If there is expected to\nbe no data in the next page, the `next_page_cursor` will be `null`.)\n\nThe first page will contain the comparisons that are first\nalphabetically by `history_fingerprint`. Each subsequent page will\ncorrespond to up to `page_size` unique fingerprints, continuing\nalphabetically, until there are no more comparisons.\n\nNote! In some cases there may be more than one comparison per\nfingerprint (if there were retries of a benchmark in the same run), so\nthe actual size of each page may vary slightly above the `page_size`.\n\nImplementation detail: currently, the next page's cursor value is equal\nto the latest `history_fingerprint` alphabetically in the current page.\nA page of comparisons is therefore defined as the comparisons with the\n`page_size` fingerprints alphabetically later than the given cursor\nvalue.\n\nNote that this means that if a new result belonging to one of the runs\nis created DURING a client's request loop with a fingerprint that is\nalphabetically earlier than the cursor value, it will not be included in\nthe next page. This is a known limitation of the current implementation,\nso ensure you use this endpoint after all results have been submitted.\n",
                        "in": "query",
                        "name": "cursor",
                        "schema": {"nullable": True, "type": "string"},
                    },
                    {
                        "description": "The max number of unique fingerprints to return per page for pagination\n(see `cursor`). Default 100. Max 1000.\n",
                        "in": "query",
                        "name": "page_size",
                        "schema": {"maximum": 1000, "minimum": 1, "type": "integer"},
                    },
                ],
                "responses": {
                    "200": {"$ref": "#/components/responses/CompareList"},
                    "401": {"$ref": "#/components/responses/401"},
                    "404": {"$ref": "#/components/responses/404"},
                },
                "tags": ["Comparisons"],
            }
        },
        "/api/contexts/": {
            "get": {
                "description": "Get a list of contexts.",
                "responses": {
                    "200": {"$ref": "#/components/responses/ContextList"},
                    "401": {"$ref": "#/components/responses/401"},
                },
                "tags": ["Contexts"],
            }
        },
        "/api/contexts/{context_id}/": {
            "get": {
                "description": "Get a context.",
                "parameters": [
                    {
                        "in": "path",
                        "name": "context_id",
                        "required": True,
                        "schema": {"type": "string"},
                    }
                ],
                "responses": {
                    "200": {"$ref": "#/components/responses/ContextEntity"},
                    "401": {"$ref": "#/components/responses/401"},
                    "404": {"$ref": "#/components/responses/404"},
                },
                "tags": ["Contexts"],
            }
        },
        "/api/docs.json": {},
        "/api/google/": {
            "get": {
                "description": "Google SSO.",
                "responses": {"302": {"$ref": "#/components/responses/302"}},
                "tags": ["Authentication"],
            }
        },
        "/api/google/callback": {
            "get": {
                "description": "Google SSO callback.",
                "responses": {
                    "302": {"$ref": "#/components/responses/302"},
                    "400": {"$ref": "#/components/responses/400"},
                },
                "tags": ["Authentication"],
            }
        },
        "/api/hardware/": {
            "get": {
                "description": "Get a list of hardware.",
                "responses": {
                    "200": {"$ref": "#/components/responses/HardwareList"},
                    "401": {"$ref": "#/components/responses/401"},
                },
                "tags": ["Hardware"],
            }
        },
        "/api/hardware/{hardware_id}/": {
            "get": {
                "description": "Get a hardware.",
                "parameters": [
                    {
                        "in": "path",
                        "name": "hardware_id",
                        "required": True,
                        "schema": {"type": "string"},
                    }
                ],
                "responses": {
                    "200": {"$ref": "#/components/responses/HardwareEntity"},
                    "401": {"$ref": "#/components/responses/401"},
                    "404": {"$ref": "#/components/responses/404"},
                },
                "tags": ["Hardware"],
            }
        },
        "/api/history/download/{benchmark_result_id}/": {
            "get": {
                "description": "Download time series",
                "parameters": [
                    {
                        "in": "path",
                        "name": "benchmark_result_id",
                        "required": True,
                        "schema": {"type": "string"},
                    }
                ],
                "responses": {
                    "200": {"$ref": "#/components/responses/HistoryList"},
                    "401": {"$ref": "#/components/responses/401"},
                    "404": {"$ref": "#/components/responses/404"},
                },
                "tags": ["History"],
            }
        },
        "/api/history/{benchmark_result_id}/": {
            "get": {
                "description": "Get details about all error-free benchmark results on the default branch\nthat match the given benchmark result's history fingerprint.\n\nThis endpoint also returns results of the lookback z-score analysis,\ncomparing each result to commits in its git history ending with its parent\ncommit. More details about this analysis can be found at\nhttps://conbench.github.io/conbench/pages/lookback_zscore.html.\n\nThough the response has pagination metadata, pagination is not currently\nimplemented. All matching results will be returned in one page.\n",
                "parameters": [
                    {
                        "in": "path",
                        "name": "benchmark_result_id",
                        "required": True,
                        "schema": {"type": "string"},
                    }
                ],
                "responses": {
                    "200": {"$ref": "#/components/responses/HistoryList"},
                    "401": {"$ref": "#/components/responses/401"},
                    "404": {"$ref": "#/components/responses/404"},
                },
                "tags": ["History"],
            }
        },
        "/api/info/": {
            "get": {
                "description": "Get a list of benchmark info.",
                "responses": {
                    "200": {"$ref": "#/components/responses/InfoList"},
                    "401": {"$ref": "#/components/responses/401"},
                },
                "tags": ["Info"],
            }
        },
        "/api/info/{info_id}/": {
            "get": {
                "description": "Get benchmark info.",
                "parameters": [
                    {
                        "in": "path",
                        "name": "info_id",
                        "required": True,
                        "schema": {"type": "string"},
                    }
                ],
                "responses": {
                    "200": {"$ref": "#/components/responses/InfoEntity"},
                    "401": {"$ref": "#/components/responses/401"},
                    "404": {"$ref": "#/components/responses/404"},
                },
                "tags": ["Info"],
            }
        },
        "/api/login/": {
            "post": {
                "description": "Login with email and password.",
                "requestBody": {
                    "content": {
                        "application/json": {
                            "schema": {"$ref": "#/components/schemas/Login"}
                        }
                    }
                },
                "responses": {
                    "204": {"$ref": "#/components/responses/204"},
                    "400": {"$ref": "#/components/responses/400"},
                },
                "tags": ["Authentication"],
            }
        },
        "/api/logout/": {
            "get": {
                "description": "Logout.",
                "responses": {"204": {"$ref": "#/components/responses/204"}},
                "tags": ["Authentication"],
            }
        },
        "/api/ping/": {
            "get": {
                "description": "Ping the API for status monitoring.",
                "responses": {"200": {"$ref": "#/components/responses/Ping"}},
                "tags": ["Ping"],
            }
        },
        "/api/redoc": {},
        "/api/register/": {
            "post": {
                "description": "Sign up for a user account.",
                "requestBody": {
                    "content": {
                        "application/json": {
                            "schema": {"$ref": "#/components/schemas/Register"}
                        }
                    }
                },
                "responses": {
                    "201": {"$ref": "#/components/responses/UserCreated"},
                    "400": {"$ref": "#/components/responses/400"},
                },
                "tags": ["Authentication"],
            }
        },
        "/api/runs/": {
            "get": {
                "description": "Get a list of runs associated with a commit hash or hashes.\n\nThis endpoint implements pagination; see the `cursor` and `page_size` query\nparameters for how it works.\n",
                "parameters": [
                    {
                        "description": "Required. A commit hash or a comma-separated list of commit hashes.\n",
                        "in": "query",
                        "name": "commit_hash",
                        "schema": {"type": "string"},
                    },
                    {
                        "description": "A cursor for pagination through matching runs in alphabetical order by\n`run_id`.\n\nTo get the first page of runs, leave out this query parameter or submit\n`null`. The response's `metadata` key will contain a `next_page_cursor`\nkey, which will contain the cursor to provide to this query parameter in\norder to get the next page. (If there is expected to be no data in the\nnext page, the `next_page_cursor` will be `null`.)\n\nThe first page will contain the `page_size` runs associated with the\ngiven commit hash(es) that are first alphabetically by `run_id`. Each\nsubsequent page will have up to `page_size` runs, continuing\nalphabetically, until there are no more matching runs.\n\nImplementation detail: currently, the next page's cursor value is equal\nto the latest `run_id` alphabetically in the current page. A page of\nruns is therefore defined as the `page_size` matching runs with an ID\nalphabetically later than the given cursor value.\n\nNote that this means that if a run is created DURING a client's request\nloop with an ID that is alphabetically earlier than the cursor value, it\nwill not be included in the next page. This is a known limitation of the\ncurrent implementation, and it is not expected to be a problem in\npractice. This is because the number of runs per commit hash is expected\nto be much less than the page size, and runs are added quite\ninfrequently.\n",
                        "in": "query",
                        "name": "cursor",
                        "schema": {"nullable": True, "type": "string"},
                    },
                    {
                        "description": "The size of pages for pagination (see `cursor`). Default 100. Max 1000.\n",
                        "in": "query",
                        "name": "page_size",
                        "schema": {"maximum": 1000, "minimum": 1, "type": "integer"},
                    },
                ],
                "responses": {
                    "200": {"$ref": "#/components/responses/RunList"},
                    "401": {"$ref": "#/components/responses/401"},
                },
                "tags": ["Runs"],
            }
        },
        "/api/runs/{run_id}/": {
            "get": {
                "description": 'Get a run and information about its candidate baseline runs.\n\nThe `"candidate_baseline_runs"` key in the response contains information\nabout up to three candidate baseline runs. Each baseline run corresponds to\na different candidate baseline commit, detailed below. If a baseline run is\nnot found for that commit, the response will detail why in the `"error"`\nkey. If a baseline run is found, its ID will be returned in the\n`"baseline_run_id"` key.\n\nThe three candidate baseline commits are:\n\n- the parent commit of the contender run\'s commit (`"parent"`)\n- if the contender run is on a PR branch, the default-branch commit that the\n  PR branch forked from (`"fork_point"`)\n- if the contender run is on a PR branch, the latest commit on the default\n  branch that has benchmark results (`"latest_default"`)\n\nWhen searching for a baseline run, each matching baseline run must:\n\n- be on the respective baseline commit, or in its git ancestry\n- match the contender run\'s hardware\n- have a benchmark result with the `case_id`/`context_id` of any of the\n  contender run\'s benchmark results\n\nIf there are multiple matches, prefer a baseline run with the same reason as\nthe contender run, and then use the baseline run with the most-recent\ncommit, finally tiebreaking by choosing the baseline run with the latest run\ntimestamp.\n\nIf any commits in the git ancestry were skipped to find a matching baseline\nrun, those commit hashes will be returned in the `"commits_skipped"` key.\n',
                "parameters": [
                    {
                        "in": "path",
                        "name": "run_id",
                        "required": True,
                        "schema": {"type": "string"},
                    }
                ],
                "responses": {
                    "200": {"$ref": "#/components/responses/RunEntityWithBaselines"},
                    "401": {"$ref": "#/components/responses/401"},
                    "404": {"$ref": "#/components/responses/404"},
                },
                "tags": ["Runs"],
            }
        },
        "/api/users/": {
            "get": {
                "description": "Get a list of users.",
                "responses": {
                    "200": {"$ref": "#/components/responses/UserList"},
                    "401": {"$ref": "#/components/responses/401"},
                },
                "tags": ["Users"],
            },
            "post": {
                "description": "Create a user.",
                "requestBody": {
                    "content": {
                        "application/json": {
                            "schema": {"$ref": "#/components/schemas/UserCreate"}
                        }
                    }
                },
                "responses": {
                    "201": {"$ref": "#/components/responses/UserCreated"},
                    "400": {"$ref": "#/components/responses/400"},
                    "401": {"$ref": "#/components/responses/401"},
                },
                "tags": ["Users"],
            },
        },
        "/api/users/{user_id}/": {
            "delete": {
                "description": "Delete a user.",
                "parameters": [
                    {
                        "in": "path",
                        "name": "user_id",
                        "required": True,
                        "schema": {"type": "string"},
                    }
                ],
                "responses": {
                    "204": {"$ref": "#/components/responses/204"},
                    "401": {"$ref": "#/components/responses/401"},
                    "404": {"$ref": "#/components/responses/404"},
                },
                "tags": ["Users"],
            },
            "get": {
                "description": "Get a user.",
                "parameters": [
                    {
                        "in": "path",
                        "name": "user_id",
                        "required": True,
                        "schema": {"type": "string"},
                    }
                ],
                "responses": {
                    "200": {"$ref": "#/components/responses/UserEntity"},
                    "401": {"$ref": "#/components/responses/401"},
                    "404": {"$ref": "#/components/responses/404"},
                },
                "tags": ["Users"],
            },
            "put": {
                "description": "Edit a user.",
                "parameters": [
                    {
                        "in": "path",
                        "name": "user_id",
                        "required": True,
                        "schema": {"type": "string"},
                    }
                ],
                "requestBody": {
                    "content": {
                        "application/json": {
                            "schema": {"$ref": "#/components/schemas/UserUpdate"}
                        }
                    }
                },
                "responses": {
                    "200": {"$ref": "#/components/responses/UserEntity"},
                    "401": {"$ref": "#/components/responses/401"},
                    "404": {"$ref": "#/components/responses/404"},
                },
                "tags": ["Users"],
            },
        },
    },
    "servers": [{"url": "http://127.0.0.1:5000/"}],
    "tags": [
        {"name": "Authentication"},
        {"description": "List of endpoints", "name": "Index"},
        {"description": "Manage users", "name": "Users"},
        {"description": "Record benchmarks", "name": "Benchmarks"},
        {"description": "Benchmarked commits", "name": "Commits"},
        {"description": "Benchmark comparisons", "name": "Comparisons"},
        {"description": "Extra benchmark information", "name": "Info"},
        {"description": "Benchmark contexts", "name": "Contexts"},
        {"description": "Benchmark history", "name": "History"},
        {"description": "Benchmark hardware", "name": "Hardware"},
        {"description": "Benchmark runs", "name": "Runs"},
        {"description": "Monitor status", "name": "Ping"},
        {
            "description": '## BenchmarkResultCreate\n<SchemaDefinition schemaRef="#/components/schemas/BenchmarkResultCreate" />\n\n## BenchmarkResultStats\n<SchemaDefinition schemaRef="#/components/schemas/BenchmarkResultStats" />\n\n## BenchmarkResultUpdate\n<SchemaDefinition schemaRef="#/components/schemas/BenchmarkResultUpdate" />\n\n## ClusterCreate\n<SchemaDefinition schemaRef="#/components/schemas/ClusterCreate" />\n\n## Error\n<SchemaDefinition schemaRef="#/components/schemas/Error" />\n\n## ErrorBadRequest\n<SchemaDefinition schemaRef="#/components/schemas/ErrorBadRequest" />\n\n## ErrorValidation\n<SchemaDefinition schemaRef="#/components/schemas/ErrorValidation" />\n\n## Login\n<SchemaDefinition schemaRef="#/components/schemas/Login" />\n\n## MachineCreate\n<SchemaDefinition schemaRef="#/components/schemas/MachineCreate" />\n\n## Ping\n<SchemaDefinition schemaRef="#/components/schemas/Ping" />\n\n## Register\n<SchemaDefinition schemaRef="#/components/schemas/Register" />\n\n## SchemaGitHubCreate\n<SchemaDefinition schemaRef="#/components/schemas/SchemaGitHubCreate" />\n\n## UserCreate\n<SchemaDefinition schemaRef="#/components/schemas/UserCreate" />\n\n## UserUpdate\n<SchemaDefinition schemaRef="#/components/schemas/UserUpdate" />\n',
            "name": "Models",
            "x-displayName": "Object models",
        },
    ],
}
