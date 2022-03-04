import datetime
import uuid

import requests

base_url = "http://127.0.0.1:5000/api"
session = requests.Session()


def generate_benchmarks_data(run_id, commit, benchmark_name, timestamp, mean=16.670462):
    return {
        "batch_id": uuid.uuid4().hex,
        "context": {
            "arrow_compiler_flags": "-fvisibility-inlines-hidden -std=c++17 -fmessage-length=0 -march=nocona -mtune=haswell -ftree-vectorize -fPIC -fstack-protector-strong -fno-plt -O2 -ffunction-sections -pipe -isystem /var/lib/buildkite-agent/miniconda3/envs/arrow-commit/include -fdiagnostics-color=always -O3 -DNDEBUG",
            "benchmark_language": "Python",
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
        "cluster_info": {
            "name": "cluster1",
            "info": {"workers": 2, "scheduler": 1},
            "optional_info": {},
        },
        "run_id": str(run_id),
        "run_name": f"commit: {commit}",
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
    }


def generate_benchmarks_data_with_error(run_id, commit, benchmark_name, timestamp):
    data = generate_benchmarks_data(run_id, commit, benchmark_name, timestamp)
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

    benchmark_names = ["csv-read", "csv-write"]

    for i in range(len(commits)):
        for benchmark_name in benchmark_names:
            run_id, commit, mean = i + 1, commits[i], means[i]
            timestamp = datetime.datetime.now() + datetime.timedelta(hours=i)
            if errors[i] and benchmark_name == "csv-read":
                benchmark_data = generate_benchmarks_data_with_error(
                    run_id, commit, benchmark_name, timestamp
                )
            else:
                benchmark_data = generate_benchmarks_data(
                    run_id, commit, benchmark_name, timestamp, mean
                )

            post_benchmarks(benchmark_data)


register()
login()
create_benchmarks_data()
