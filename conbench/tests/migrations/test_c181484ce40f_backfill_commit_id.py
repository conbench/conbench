import os
import uuid

from alembic import command
from alembic.config import Config

from ...db import Session
from ...entities.distribution import Distribution
from ...entities.summary import Summary


this_dir = os.path.abspath(os.path.dirname(__file__))
config_path = os.path.join(this_dir, "../../../alembic.ini")


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


def test_upgrade():
    VALID_PAYLOAD["tags"]["name"] = uuid.uuid4().hex
    summary = Summary.create(VALID_PAYLOAD)

    # make commit_id null
    distribution = Distribution.one(case_id=summary.case_id)
    commit_id_before = distribution.commit_id
    repository_before = distribution.repository
    sha_before = distribution.sha
    distribution.commit_id = None
    distribution.save()

    # assert before migration
    Session.refresh(distribution)
    assert distribution.commit_id is None
    assert distribution.repository == repository_before
    assert distribution.sha == sha_before

    # do migration
    alembic_config = Config(config_path)
    command.stamp(alembic_config, "dc0ed346df63")
    command.upgrade(alembic_config, "c181484ce40f")

    # assert after migration
    Session.refresh(distribution)
    assert distribution.commit_id == commit_id_before
    assert distribution.repository == repository_before
    assert distribution.sha == sha_before
