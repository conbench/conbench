import copy

from ...entities.summary import Summary
from ...runner import Conbench
from ...tests.helpers import _uuid

CHILD = "02addad336ba19a654f9c857ede546331be7b631"
PARENT = "4beb514d071c9beec69b8917b5265e77ade22fb3"
GRANDPARENT = "6d703c4c7b15be630af48d5e9ef61628751674b2"
ELDER = "81e9417eb68171e03a304097ae86e1fd83307130"


RESULTS_UP = [[1, 2, 3], [2, 3, 4], [10, 20, 30]]
RESULTS_DOWN = [[10, 11, 12], [11, 12, 13], [1, 2, 3]]
Z_SCORE_UP = 24.74873734152916
Z_SCORE_DOWN = -13.435028842544401


VALID_PAYLOAD = {
    "run_id": "2a5709d179f349cba69ed242be3e6321",
    "run_name": "commit: 02addad336ba19a654f9c857ede546331be7b631",
    "batch_id": "7b2fdd9f929d47b9960152090d47f8e6",
    "timestamp": "2020-11-25T21:02:42.706806+00:00",
    "context": {
        "arrow_compiler_flags": "-fPIC -arch x86_64 -arch x86_64 -std=c++11 -Qunused-arguments -fcolor-diagnostics -O3 -DNDEBUG",
        "arrow_compiler_id": "AppleClang",
        "arrow_compiler_version": "11.0.0.11000033",
        "arrow_version": "2.0.0",
        "benchmark_language_version": "Python 3.8.5",
        "benchmark_language": "Python",
    },
    "github": {
        "commit": "02addad336ba19a654f9c857ede546331be7b631",
        "repository": "https://github.com/apache/arrow",
    },
    "machine_info": {
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
    },
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
        "max": "0.148896",
        "mean": "0.036369",
        "median": "0.008988",
        "min": "0.004733",
        "q1": "0.006500",
        "q3": "0.036942",
        "stdev": "0.049194",
    },
    "tags": {
        "compression": "snappy",
        "cpu_count": 2,
        "dataset": "nyctaxi_sample",
        "file_type": "parquet",
        "input_type": "arrow",
        "name": "file-write",
    },
}


def summary(
    name=None,
    batch_id=None,
    run_id=None,
    results=None,
    unit=None,
    language=None,
    machine=None,
    sha=None,
    commit=None,
    pull_request=False,
):
    data = copy.deepcopy(VALID_PAYLOAD)
    data["run_name"] = f"commit: {_uuid()}"
    data["run_id"] = run_id if run_id else _uuid()
    data["batch_id"] = batch_id if batch_id else _uuid()
    data["tags"]["name"] = name if name else _uuid()

    if language:
        data["context"]["benchmark_language"] = language
    if machine:
        data["machine_info"]["name"] = machine
    if pull_request:
        data["run_name"] = "pull request: some commit"
    if sha:
        data["github"]["commit"] = sha
    if commit:
        data["github"]["commit"] = commit.sha
        data["github"]["repository"] = commit.repository

    if results is not None:
        unit = unit if unit else "s"
        data["stats"] = Conbench._stats(results, unit, [], "s")

    return Summary.create(data)
