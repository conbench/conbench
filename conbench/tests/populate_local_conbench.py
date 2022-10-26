import datetime
import uuid

import requests

base_url = "http://127.0.0.1:5000/api"
session = requests.Session()


def generate_benchmarks_data(
    run_id,
    commit,
    benchmark_name,
    benchmark_language,
    timestamp,
    hardware_type,
    reason,
    mean=16.670462,
):
    run_name = f"{reason}: {commit}" if reason else commit
    data = {
        "batch_id": uuid.uuid4().hex,
        "context": {
            "arrow_compiler_flags": "-fvisibility-inlines-hidden -std=c++17 -fmessage-length=0 -march=nocona -mtune=haswell -ftree-vectorize -fPIC -fstack-protector-strong -fno-plt -O2 -ffunction-sections -pipe -isystem /var/lib/buildkite-agent/miniconda3/envs/arrow-commit/include -fdiagnostics-color=always -O3 -DNDEBUG",
            "benchmark_language": benchmark_language,
        },
        "github": {
            "commit": commit,
            "repository": "https://github.com/apache/arrow",
        },
        "info": {
            "arrow_compiler_id": "GNU",
            "arrow_compiler_version": "9.4.0",
            "arrow_version": "8.0.0-SNAPSHOT",
            "benchmark_language_version": "Python 3.8.12",
        },
        "run_id": str(run_id),
        "run_name": run_name,
        "stats": {
            "data": ["14.928533", "14.551965", "14.530887"],
            "iqr": "0.198823",
            "iterations": 3,
            "max": "14.928533",
            "mean": mean,
            "median": "16.551965",
            "min": "14.530887",
            "q1": "14.541426",
            "q3": "14.740249",
            "stdev": "0.223744",
            "time_unit": "s",
            "times": [],
            "unit": "s",
        },
        "tags": {
            "compression": "uncompressed1",
            "cpu_count": None,
            "dataset": "fanniemae_2016Q4",
            "name": benchmark_name,
            "streaming": "streaming",
        },
        "timestamp": str(timestamp),
        "validation": {"type": "pandas.testing", "success": True},
    }

    if reason:
        data["run_reason"] = reason

    data["optional_benchmark_info"] = {
        "log uri": "s3://some/log",
        "trace uri": "s3://some/trace",
    }

    for key in ["info", "tags", "context"]:
        fields_set = {
            f"{benchmark_language}_specific_{key}_field_1": "value-1",
            f"{benchmark_language}_specific_{key}_field_2": f"{benchmark_language}-{key}-value-2",
            f"{key}_field_3": f"{benchmark_language}-{key}-value-2",
            f"{key}_field_4": None if benchmark_language == "Python" else "value-4",
        }
        data[key].update(fields_set)
        if benchmark_language == "Python":
            for i in range(5, 7):
                data[key][f"field_{i}"] = f"value-{i}"

    if hardware_type == "cluster":
        data["cluster_info"] = {
            "name": "cluster1",
            "info": {"workers": 2, "scheduler": 1},
            "optional_info": {},
        }
    else:
        data["machine_info"] = {
            "name": "machine1",
            "architecture_name": "aarch64",
            "cpu_core_count": "16",
            "cpu_frequency_max_hz": "0",
            "cpu_l1d_cache_bytes": "65536",
            "cpu_l1i_cache_bytes": "65536",
            "cpu_l2_cache_bytes": "1048576",
            "cpu_l3_cache_bytes": "33554432",
            "cpu_model_name": "",
            "cpu_thread_count": "16",
            "gpu_count": "0",
            "gpu_product_names": [],
            "kernel_name": "4.14.248-189.473.amzn2.aarch64",
            "memory_bytes": "64424509440",
            "os_name": "Linux",
            "os_version": "4.14.248-189.473.amzn2.aarch64-aarch64-with-glibc2.17",
        }

    return data


def generate_benchmarks_data_with_error(
    run_id,
    commit,
    benchmark_name,
    benchmark_language,
    timestamp,
    hardware_type,
    reason,
):
    data = generate_benchmarks_data(
        run_id,
        commit,
        benchmark_name,
        benchmark_language,
        timestamp,
        hardware_type,
        reason,
    )
    data.pop("stats")
    data["error"] = {"command": "some command", "stack trace": "stack trace ..."}
    return data


def register():
    url = f"{base_url}/register/"
    data = {"email": "e@e.com", "password": "test", "name": "e", "secret": "conbench"}
    print(session.post(url, json=data))


def login():
    url = f"{base_url}/login/"
    data = {"email": "e@e.com", "password": "test", "remember_me": True}
    print(session.post(url, json=data))


def post_benchmarks(data):
    url = f"{base_url}/benchmarks/"
    print(session.post(url, json=data))


def update_run(run_id, data):
    url = f"{base_url}/runs/{run_id}/"
    print(session.put(url, json=data))


def update_run_with_info(run_id, timestamp):
    data = {
        "finished_timestamp": str(timestamp + datetime.timedelta(hours=1)),
        "info": {"setup": "passed"},
        "error_info": {"error": "error", "stack_trace": "stack_trace", "fatal": True},
        "error_type": "fatal",
    }
    update_run(run_id, data)


def create_benchmarks_data():
    commits = [
        "e314d8d0d611c7f9ca7f2fbee174fcea3d0c66f2",
        "ce46c1adf10654248b02c349210bb63ecc6828ad",
        "9719eae66dcf38c966ae769215d27020a6dd5550",
        "650f111b524fb1c5bfbfa6f533d15929c90ddc40",
        "e26a88fd9fecca876073c5a18cf571c0daca6b3b",
        "2462492389a8f2ca286c481852c84ba1f0d0eff9",
    ]

    means = [16.670462, 16.4, 16.5, 16.67, 16.7, 16.7]

    errors = [False, False, True, False, True, True]

    reasons = ["commit", None, "pull request", "nightly", "manual", "an accident"]

    benchmark_names = ["csv-read", "csv-write"]

    benchmark_languages = ["Python", "R", "JavaScript"]

    hardware_types = ["machine", "cluster"]

    runs = []

    for i in range(len(commits)):
        for hardware_type in hardware_types:
            for benchmark_language in benchmark_languages:
                for benchmark_name in benchmark_names:
                    run_id = f"{hardware_type}{i+1}"
                    commit, mean, reason = commits[i], means[i], reasons[i]
                    timestamp = datetime.datetime.now() + datetime.timedelta(hours=i)
                    if errors[i] and benchmark_name == "csv-read":
                        benchmark_data = generate_benchmarks_data_with_error(
                            run_id,
                            commit,
                            benchmark_name,
                            benchmark_language,
                            timestamp,
                            hardware_type,
                            reason,
                        )
                    else:
                        benchmark_data = generate_benchmarks_data(
                            run_id,
                            commit,
                            benchmark_name,
                            benchmark_language,
                            timestamp,
                            hardware_type,
                            reason,
                            mean,
                        )

                    post_benchmarks(benchmark_data)
                    runs.append((run_id, timestamp))

    run_id, timestamp = runs[-1]
    update_run_with_info(run_id, timestamp)


register()
login()
create_benchmarks_data()
