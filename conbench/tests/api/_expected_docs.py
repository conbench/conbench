{
    "components": {
        "responses": {
            "200": {"description": "OK"},
            "201": {"description": "Created"},
            "202": {"description": "No Content (accepted)"},
            "204": {"description": "No Content (success)"},
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
            "BenchmarkCreated": {
                "content": {
                    "application/json": {
                        "example": {
                            "id": "some-benchmark-uuid-1",
                            "links": {
                                "context": "http://localhost/api/contexts/some-context-uuid-1/",
                                "list": "http://localhost/api/benchmarks/",
                                "machine": "http://localhost/api/machines/some-machine-uuid-1/",
                                "run": "http://localhost/api/runs/some-run-uuid-1/",
                                "self": "http://localhost/api/benchmarks/some-benchmark-uuid-1/",
                            },
                            "stats": {
                                "batch_id": "some-batch-uuid-1",
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
                                "iqr": "0.030442",
                                "iterations": 10,
                                "max": "0.148896",
                                "mean": "0.036369",
                                "median": "0.008988",
                                "min": "0.004733",
                                "q1": "0.006500",
                                "q3": "0.036942",
                                "run_id": "some-run-uuid-1",
                                "stdev": "0.049194",
                                "time_unit": "s",
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
                                "timestamp": "2020-11-25T21:02:42.706806",
                                "unit": "s",
                            },
                            "tags": {
                                "compression": "snappy",
                                "cpu_count": 2,
                                "dataset": "nyctaxi_sample",
                                "dataset_columns": 18,
                                "dataset_rows": 998,
                                "file_type": "parquet",
                                "gc_collect": True,
                                "gc_disable": True,
                                "id": "some-case-uuid-1",
                                "input_type": "arrow",
                                "name": "file-write",
                            },
                        }
                    }
                },
                "description": "Created \n\n The resulting entity URL is returned in the Location header.",
            },
            "BenchmarkEntity": {
                "content": {
                    "application/json": {
                        "example": {
                            "id": "some-benchmark-uuid-1",
                            "links": {
                                "context": "http://localhost/api/contexts/some-context-uuid-1/",
                                "list": "http://localhost/api/benchmarks/",
                                "machine": "http://localhost/api/machines/some-machine-uuid-1/",
                                "run": "http://localhost/api/runs/some-run-uuid-1/",
                                "self": "http://localhost/api/benchmarks/some-benchmark-uuid-1/",
                            },
                            "stats": {
                                "batch_id": "some-batch-uuid-1",
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
                                "iqr": "0.030442",
                                "iterations": 10,
                                "max": "0.148896",
                                "mean": "0.036369",
                                "median": "0.008988",
                                "min": "0.004733",
                                "q1": "0.006500",
                                "q3": "0.036942",
                                "run_id": "some-run-uuid-1",
                                "stdev": "0.049194",
                                "time_unit": "s",
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
                                "timestamp": "2020-11-25T21:02:42.706806",
                                "unit": "s",
                            },
                            "tags": {
                                "compression": "snappy",
                                "cpu_count": 2,
                                "dataset": "nyctaxi_sample",
                                "dataset_columns": 18,
                                "dataset_rows": 998,
                                "file_type": "parquet",
                                "gc_collect": True,
                                "gc_disable": True,
                                "id": "some-case-uuid-1",
                                "input_type": "arrow",
                                "name": "file-write",
                            },
                        }
                    }
                },
                "description": "OK",
            },
            "BenchmarkList": {
                "content": {
                    "application/json": {
                        "example": [
                            {
                                "id": "some-benchmark-uuid-1",
                                "links": {
                                    "context": "http://localhost/api/contexts/some-context-uuid-1/",
                                    "list": "http://localhost/api/benchmarks/",
                                    "machine": "http://localhost/api/machines/some-machine-uuid-1/",
                                    "run": "http://localhost/api/runs/some-run-uuid-1/",
                                    "self": "http://localhost/api/benchmarks/some-benchmark-uuid-1/",
                                },
                                "stats": {
                                    "batch_id": "some-batch-uuid-1",
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
                                    "iqr": "0.030442",
                                    "iterations": 10,
                                    "max": "0.148896",
                                    "mean": "0.036369",
                                    "median": "0.008988",
                                    "min": "0.004733",
                                    "q1": "0.006500",
                                    "q3": "0.036942",
                                    "run_id": "some-run-uuid-1",
                                    "stdev": "0.049194",
                                    "time_unit": "s",
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
                                    "timestamp": "2020-11-25T21:02:42.706806",
                                    "unit": "s",
                                },
                                "tags": {
                                    "compression": "snappy",
                                    "cpu_count": 2,
                                    "dataset": "nyctaxi_sample",
                                    "dataset_columns": 18,
                                    "dataset_rows": 998,
                                    "file_type": "parquet",
                                    "gc_collect": True,
                                    "gc_disable": True,
                                    "id": "some-case-uuid-1",
                                    "input_type": "arrow",
                                    "name": "file-write",
                                },
                            },
                            {
                                "id": "some-benchmark-uuid-2",
                                "links": {
                                    "context": "http://localhost/api/contexts/some-context-uuid-1/",
                                    "list": "http://localhost/api/benchmarks/",
                                    "machine": "http://localhost/api/machines/some-machine-uuid-1/",
                                    "run": "http://localhost/api/runs/some-run-uuid-1/",
                                    "self": "http://localhost/api/benchmarks/some-benchmark-uuid-2/",
                                },
                                "stats": {
                                    "batch_id": "some-batch-uuid-1",
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
                                    "iqr": "0.030442",
                                    "iterations": 10,
                                    "max": "0.148896",
                                    "mean": "0.036369",
                                    "median": "0.008988",
                                    "min": "0.004733",
                                    "q1": "0.006500",
                                    "q3": "0.036942",
                                    "run_id": "some-run-uuid-1",
                                    "stdev": "0.049194",
                                    "time_unit": "s",
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
                                    "timestamp": "2020-11-25T21:02:42.706806",
                                    "unit": "s",
                                },
                                "tags": {
                                    "compression": "snappy",
                                    "cpu_count": 2,
                                    "dataset": "nyctaxi_sample",
                                    "dataset_columns": 18,
                                    "dataset_rows": 998,
                                    "file_type": "parquet",
                                    "gc_collect": True,
                                    "gc_disable": True,
                                    "id": "some-case-uuid-1",
                                    "input_type": "arrow",
                                    "name": "file-write",
                                },
                            },
                        ]
                    }
                },
                "description": "OK",
            },
            "CompareEntity": {
                "content": {
                    "application/json": {
                        "example": {
                            "baseline": "0.036 s",
                            "baseline_batch_id": "some-batch-uuid-1",
                            "baseline_id": "some-benchmark-uuid-1",
                            "baseline_run_id": "some-run-uuid-1",
                            "batch": "file-read",
                            "benchmark": "snappy, nyctaxi_sample, parquet, arrow",
                            "change": "0.000%",
                            "contender": "0.036 s",
                            "contender_batch_id": "some-batch-uuid-2",
                            "contender_id": "some-benchmark-uuid-2",
                            "contender_run_id": "some-run-uuid-2",
                            "improvement": False,
                            "less_is_better": True,
                            "regression": False,
                            "unit": "s",
                        }
                    }
                },
                "description": "OK",
            },
            "CompareList": {
                "content": {
                    "application/json": {
                        "example": [
                            {
                                "baseline": "0.036 s",
                                "baseline_batch_id": "some-batch-uuid-1",
                                "baseline_id": "some-benchmark-uuid-1",
                                "baseline_run_id": "some-run-uuid-1",
                                "batch": "file-read",
                                "benchmark": "snappy, nyctaxi_sample, parquet, arrow",
                                "change": "0.000%",
                                "contender": "0.036 s",
                                "contender_batch_id": "some-batch-uuid-2",
                                "contender_id": "some-benchmark-uuid-3",
                                "contender_run_id": "some-run-uuid-2",
                                "improvement": False,
                                "less_is_better": True,
                                "regression": False,
                                "unit": "s",
                            },
                            {
                                "baseline": "0.036 s",
                                "baseline_batch_id": "some-batch-uuid-1",
                                "baseline_id": "some-benchmark-uuid-2",
                                "baseline_run_id": "some-run-uuid-1",
                                "batch": "file-write",
                                "benchmark": "snappy, nyctaxi_sample, parquet, arrow",
                                "change": "0.000%",
                                "contender": "0.036 s",
                                "contender_batch_id": "some-batch-uuid-2",
                                "contender_id": "some-benchmark-uuid-4",
                                "contender_run_id": "some-run-uuid-2",
                                "improvement": False,
                                "less_is_better": True,
                                "regression": False,
                                "unit": "s",
                            },
                        ]
                    }
                },
                "description": "OK",
            },
            "ContextEntity": {
                "content": {
                    "application/json": {
                        "example": {
                            "arrow_compiler_flags": "-fPIC -arch x86_64 -arch x86_64 -std=c++11 -Qunused-arguments -fcolor-diagnostics -O3 -DNDEBUG",
                            "arrow_compiler_id": "AppleClang",
                            "arrow_compiler_version": "11.0.0.11000033",
                            "arrow_git_revision": "02addad336ba19a654f9c857ede546331be7b631",
                            "arrow_version": "2.0.0",
                            "benchmark_language": "Python",
                            "benchmark_language_version": "Python 3.8.5",
                            "id": "some-context-uuid-1",
                            "links": {
                                "self": "http://localhost/api/contexts/some-context-uuid-1/"
                            },
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
                                "docs": "http://localhost/api/docs.json",
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
            "MachineEntity": {
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
                            "id": "some-machine-uuid-1",
                            "kernel_name": "19.6.0",
                            "links": {
                                "self": "http://localhost/api/machines/some-machine-uuid-1/"
                            },
                            "memory_bytes": 17179869184,
                            "name": "diana",
                            "os_name": "macOS",
                            "os_version": "10.15.7",
                        }
                    }
                },
                "description": "OK",
            },
            "Ping": {
                "content": {
                    "application/json": {
                        "example": {"date": "Thu, 22 Oct 2020 15:53:55 UTC"},
                        "schema": {"$ref": "#/components/schemas/Ping"},
                    }
                },
                "description": "OK",
            },
            "RunEntity": {
                "content": {
                    "application/json": {
                        "example": {
                            "commit": {
                                "author_avatar": "https://avatars.githubusercontent.com/u/878798?v=4",
                                "author_login": "dianaclarke",
                                "author_name": "Diana Clarke",
                                "id": "some-commit-uuid-1",
                                "message": "ARROW-11771: [Developer][Archery] Move benchmark tests (so CI runs them)",
                                "repository": "https://github.com/apache/arrow",
                                "sha": "02addad336ba19a654f9c857ede546331be7b631",
                                "timestamp": "2021-02-25T01:02:51",
                                "url": "https://github.com/apache/arrow/commit/02addad336ba19a654f9c857ede546331be7b631",
                            },
                            "id": "some-run-uuid-1",
                            "links": {
                                "machine": "http://localhost/api/machines/some-machine-uuid-1/",
                                "self": "http://localhost/api/runs/some-run-uuid-1/",
                            },
                            "machine": {
                                "architecture_name": "x86_64",
                                "cpu_core_count": 2,
                                "cpu_frequency_max_hz": 3500000000,
                                "cpu_l1d_cache_bytes": 32768,
                                "cpu_l1i_cache_bytes": 32768,
                                "cpu_l2_cache_bytes": 262144,
                                "cpu_l3_cache_bytes": 4194304,
                                "cpu_model_name": "Intel(R) Core(TM) i7-7567U CPU @ 3.50GHz",
                                "cpu_thread_count": 4,
                                "id": "some-machine-uuid-1",
                                "kernel_name": "19.6.0",
                                "memory_bytes": 17179869184,
                                "name": "diana",
                                "os_name": "macOS",
                                "os_version": "10.15.7",
                            },
                            "name": "pull request: 9564",
                            "timestamp": "2021-02-04T17:22:05.225583",
                        }
                    }
                },
                "description": "OK",
            },
            "RunList": {
                "content": {
                    "application/json": {
                        "example": [
                            {
                                "commit": {
                                    "author_avatar": "https://avatars.githubusercontent.com/u/878798?v=4",
                                    "author_login": "dianaclarke",
                                    "author_name": "Diana Clarke",
                                    "id": "some-commit-uuid-1",
                                    "message": "ARROW-11771: [Developer][Archery] Move benchmark tests (so CI runs them)",
                                    "repository": "https://github.com/apache/arrow",
                                    "sha": "02addad336ba19a654f9c857ede546331be7b631",
                                    "timestamp": "2021-02-25T01:02:51",
                                    "url": "https://github.com/apache/arrow/commit/02addad336ba19a654f9c857ede546331be7b631",
                                },
                                "id": "some-run-uuid-1",
                                "links": {
                                    "machine": "http://localhost/api/machines/some-machine-uuid-1/",
                                    "self": "http://localhost/api/runs/some-run-uuid-1/",
                                },
                                "machine": {
                                    "architecture_name": "x86_64",
                                    "cpu_core_count": 2,
                                    "cpu_frequency_max_hz": 3500000000,
                                    "cpu_l1d_cache_bytes": 32768,
                                    "cpu_l1i_cache_bytes": 32768,
                                    "cpu_l2_cache_bytes": 262144,
                                    "cpu_l3_cache_bytes": 4194304,
                                    "cpu_model_name": "Intel(R) Core(TM) i7-7567U CPU @ 3.50GHz",
                                    "cpu_thread_count": 4,
                                    "id": "some-machine-uuid-1",
                                    "kernel_name": "19.6.0",
                                    "memory_bytes": 17179869184,
                                    "name": "diana",
                                    "os_name": "macOS",
                                    "os_version": "10.15.7",
                                },
                                "name": "pull request: 9564",
                                "timestamp": "2021-02-04T17:22:05.225583",
                            },
                            {
                                "commit": {
                                    "author_avatar": "https://avatars.githubusercontent.com/u/878798?v=4",
                                    "author_login": "dianaclarke",
                                    "author_name": "Diana Clarke",
                                    "id": "some-commit-uuid-1",
                                    "message": "ARROW-11771: [Developer][Archery] Move benchmark tests (so CI runs them)",
                                    "repository": "https://github.com/apache/arrow",
                                    "sha": "02addad336ba19a654f9c857ede546331be7b631",
                                    "timestamp": "2021-02-25T01:02:51",
                                    "url": "https://github.com/apache/arrow/commit/02addad336ba19a654f9c857ede546331be7b631",
                                },
                                "id": "some-run-uuid-2",
                                "links": {
                                    "machine": "http://localhost/api/machines/some-machine-uuid-1/",
                                    "self": "http://localhost/api/runs/some-run-uuid-2/",
                                },
                                "machine": {
                                    "architecture_name": "x86_64",
                                    "cpu_core_count": 2,
                                    "cpu_frequency_max_hz": 3500000000,
                                    "cpu_l1d_cache_bytes": 32768,
                                    "cpu_l1i_cache_bytes": 32768,
                                    "cpu_l2_cache_bytes": 262144,
                                    "cpu_l3_cache_bytes": 4194304,
                                    "cpu_model_name": "Intel(R) Core(TM) i7-7567U CPU @ 3.50GHz",
                                    "cpu_thread_count": 4,
                                    "id": "some-machine-uuid-1",
                                    "kernel_name": "19.6.0",
                                    "memory_bytes": 17179869184,
                                    "name": "diana",
                                    "os_name": "macOS",
                                    "os_version": "10.15.7",
                                },
                                "name": "pull request: 9564",
                                "timestamp": "2021-03-04T17:18:05.715583",
                            },
                        ]
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
            "BenchmarkCreate": {
                "properties": {
                    "context": {"type": "object"},
                    "machine_info": {"$ref": "#/components/schemas/MachineCreate"},
                    "run": {"type": "object"},
                    "stats": {"$ref": "#/components/schemas/SummaryCreate"},
                    "tags": {"type": "object"},
                },
                "required": ["context", "machine_info", "run", "stats", "tags"],
                "type": "object",
            },
            "Error": {
                "properties": {
                    "code": {"description": "HTTP error code", "type": "integer"},
                    "name": {"description": "HTTP error name", "type": "string"},
                },
                "required": ["code", "name"],
                "type": "object",
            },
            "ErrorBadRequest": {
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
                    "remember_me": {"type": "boolean"},
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
            "SummaryCreate": {
                "properties": {
                    "batch_id": {"type": "string"},
                    "data": {"items": {"type": "number"}, "type": "array"},
                    "iqr": {"type": "number"},
                    "iterations": {"type": "integer"},
                    "max": {"type": "number"},
                    "mean": {"type": "number"},
                    "median": {"type": "number"},
                    "min": {"type": "number"},
                    "q1": {"type": "number"},
                    "q3": {"type": "number"},
                    "run_id": {"type": "string"},
                    "run_name": {"type": "string"},
                    "stdev": {"type": "number"},
                    "time_unit": {"type": "string"},
                    "times": {"items": {"type": "number"}, "type": "array"},
                    "timestamp": {"format": "date-time", "type": "string"},
                    "unit": {"type": "string"},
                },
                "required": [
                    "batch_id",
                    "data",
                    "iterations",
                    "run_id",
                    "time_unit",
                    "times",
                    "timestamp",
                    "unit",
                ],
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
    "info": {"title": "Conbench", "version": "1.0.0"},
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
                "description": "Get a list of benchmarks.",
                "parameters": [
                    {"in": "query", "name": "name", "schema": {"type": "string"}},
                    {"in": "query", "name": "batch_id", "schema": {"type": "string"}},
                    {"in": "query", "name": "run_id", "schema": {"type": "string"}},
                ],
                "responses": {
                    "200": {"$ref": "#/components/responses/BenchmarkList"},
                    "401": {"$ref": "#/components/responses/401"},
                },
                "tags": ["Benchmarks"],
            },
            "post": {
                "description": "Create a benchmark.",
                "requestBody": {
                    "content": {
                        "application/json": {
                            "schema": {"$ref": "#/components/schemas/BenchmarkCreate"}
                        }
                    }
                },
                "responses": {
                    "201": {"$ref": "#/components/responses/BenchmarkCreated"},
                    "400": {"$ref": "#/components/responses/400"},
                    "401": {"$ref": "#/components/responses/401"},
                },
                "tags": ["Benchmarks"],
            },
        },
        "/api/benchmarks/{benchmark_id}/": {
            "delete": {
                "description": "Delete a benchmark.",
                "parameters": [
                    {
                        "in": "path",
                        "name": "benchmark_id",
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
                "description": "Get a benchmark.",
                "parameters": [
                    {
                        "in": "path",
                        "name": "benchmark_id",
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
        },
        "/api/compare/batches/{compare_ids}/": {
            "get": {
                "description": "Compare benchmark results.",
                "parameters": [
                    {
                        "example": "<baseline_id>...<contender_id>",
                        "in": "path",
                        "name": "compare_ids",
                        "required": True,
                        "schema": {"type": "string"},
                    },
                    {"in": "query", "name": "raw", "schema": {"type": "boolean"}},
                    {"in": "query", "name": "threshold", "schema": {"type": "integer"}},
                ],
                "responses": {
                    "200": {"$ref": "#/components/responses/CompareList"},
                    "401": {"$ref": "#/components/responses/401"},
                    "404": {"$ref": "#/components/responses/404"},
                },
                "tags": ["Compare"],
            }
        },
        "/api/compare/benchmarks/{compare_ids}/": {
            "get": {
                "description": "Compare benchmark results.",
                "parameters": [
                    {
                        "example": "<baseline_id>...<contender_id>",
                        "in": "path",
                        "name": "compare_ids",
                        "required": True,
                        "schema": {"type": "string"},
                    },
                    {"in": "query", "name": "raw", "schema": {"type": "boolean"}},
                    {"in": "query", "name": "threshold", "schema": {"type": "integer"}},
                ],
                "responses": {
                    "200": {"$ref": "#/components/responses/CompareEntity"},
                    "401": {"$ref": "#/components/responses/401"},
                    "404": {"$ref": "#/components/responses/404"},
                },
                "tags": ["Compare"],
            }
        },
        "/api/compare/runs/{compare_ids}/": {
            "get": {
                "description": "Compare benchmark results.",
                "parameters": [
                    {
                        "example": "<baseline_id>...<contender_id>",
                        "in": "path",
                        "name": "compare_ids",
                        "required": True,
                        "schema": {"type": "string"},
                    },
                    {"in": "query", "name": "raw", "schema": {"type": "boolean"}},
                    {"in": "query", "name": "threshold", "schema": {"type": "integer"}},
                ],
                "responses": {
                    "200": {"$ref": "#/components/responses/CompareList"},
                    "401": {"$ref": "#/components/responses/401"},
                    "404": {"$ref": "#/components/responses/404"},
                },
                "tags": ["Compare"],
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
        "/api/machines/{machine_id}/": {
            "get": {
                "description": "Get a machine.",
                "parameters": [
                    {
                        "in": "path",
                        "name": "machine_id",
                        "required": True,
                        "schema": {"type": "string"},
                    }
                ],
                "responses": {
                    "200": {"$ref": "#/components/responses/MachineEntity"},
                    "401": {"$ref": "#/components/responses/401"},
                    "404": {"$ref": "#/components/responses/404"},
                },
                "tags": ["Machines"],
            }
        },
        "/api/ping/": {
            "get": {
                "description": "Ping the API for status monitoring.",
                "responses": {"200": {"$ref": "#/components/responses/Ping"}},
                "tags": ["Ping"],
            }
        },
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
                "description": "Get a list of runs.",
                "responses": {
                    "200": {"$ref": "#/components/responses/RunList"},
                    "401": {"$ref": "#/components/responses/401"},
                },
                "tags": ["Runs"],
            }
        },
        "/api/runs/{run_id}/": {
            "get": {
                "description": "Get a run.",
                "parameters": [
                    {
                        "in": "path",
                        "name": "run_id",
                        "required": True,
                        "schema": {"type": "string"},
                    }
                ],
                "responses": {
                    "200": {"$ref": "#/components/responses/RunEntity"},
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
    "servers": [{"url": "http://localhost:5000/"}],
    "tags": [
        {"name": "Authentication"},
        {"description": "List of endpoints", "name": "Index"},
        {"description": "Manage users", "name": "Users"},
        {"description": "Record benchmarks", "name": "Benchmarks"},
        {"description": "Compare benchmarks", "name": "Compare"},
        {"description": "Benchmark contexts", "name": "Contexts"},
        {"description": "Benchmark machines", "name": "Machines"},
        {"description": "Benchmark runs", "name": "Runs"},
        {"description": "Monitor status", "name": "Ping"},
    ],
}
