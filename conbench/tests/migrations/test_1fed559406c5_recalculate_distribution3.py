import decimal
import os
import uuid

from alembic import command
from alembic.config import Config

from ...entities.distribution import Distribution
from ...entities.summary import Summary

this_dir = os.path.abspath(os.path.dirname(__file__))
config_path = os.path.join(this_dir, "../../../alembic.ini")


VALID_PAYLOAD_1 = {
    "batch_id": "7b2fdd9f929d47b9960152090d47f8e6",
    "run_id": "2a5709d179f349cba69ed242be3e6321",
    "timestamp": "2020-11-25T21:02:42.706806+00:00",
    "run_name": "commit: 02addad336ba19a654f9c857ede546331be7b631",
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
        "name": uuid.uuid4().hex,
    },
}

VALID_PAYLOAD_2 = {
    "batch_id": "7b2fdd9f929d47b9960152090d47f8e6",
    "run_id": "2a5709d179f349cba69ed242be3e6321",
    "run_name": "commit: 02addad336ba19a654f9c857ede546331be7b631",
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
        "name": uuid.uuid4().hex,
    },
}


def test_upgrade():
    summary_1 = Summary.create(VALID_PAYLOAD_1)
    summary_2 = Summary.create(VALID_PAYLOAD_2)

    # assert before migration
    distributions = Distribution.search(
        filters=[Distribution.case_id == summary_1.case_id]
    )
    assert len(distributions) == 1
    assert distributions[0].unit == "s"
    assert distributions[0].observations == 1
    assert distributions[0].mean_mean == decimal.Decimal("0.03636900000000000000")
    assert distributions[0].mean_sd is None
    assert distributions[0].min_mean == decimal.Decimal("0.00473300000000000000")
    assert distributions[0].min_sd is None
    assert distributions[0].max_mean == decimal.Decimal("0.14889600000000000000")
    assert distributions[0].max_sd is None
    assert distributions[0].median_mean == decimal.Decimal("0.00898800000000000000")
    assert distributions[0].median_sd is None

    distributions = Distribution.search(
        filters=[Distribution.case_id == summary_2.case_id]
    )
    assert len(distributions) == 1
    assert distributions[0].unit == "s"
    assert distributions[0].observations == 1
    assert distributions[0].mean_mean == decimal.Decimal("0.03636900000000000000")
    assert distributions[0].mean_sd is None
    assert distributions[0].min_mean == decimal.Decimal("0.00473300000000000000")
    assert distributions[0].min_sd is None
    assert distributions[0].max_mean == decimal.Decimal("0.14889600000000000000")
    assert distributions[0].max_sd is None
    assert distributions[0].median_mean == decimal.Decimal("0.00898800000000000000")
    assert distributions[0].median_sd is None

    # do migration
    alembic_config = Config(config_path)
    command.stamp(alembic_config, "0fed559406c5")
    command.upgrade(alembic_config, "1fed559406c5")

    # assert after migration
    distributions = Distribution.search(
        filters=[Distribution.case_id == summary_1.case_id]
    )
    assert len(distributions) == 1
    assert distributions[0].unit == "s"
    assert distributions[0].observations == 1
    assert distributions[0].mean_mean == decimal.Decimal("0.03636900000000000000")
    assert distributions[0].mean_sd is None
    assert distributions[0].min_mean == decimal.Decimal("0.00473300000000000000")
    assert distributions[0].min_sd is None
    assert distributions[0].max_mean == decimal.Decimal("0.14889600000000000000")
    assert distributions[0].max_sd is None
    assert distributions[0].median_mean == decimal.Decimal("0.00898800000000000000")
    assert distributions[0].median_sd is None

    distributions = Distribution.search(
        filters=[Distribution.case_id == summary_2.case_id]
    )
    assert len(distributions) == 1
    assert distributions[0].unit == "s"
    assert distributions[0].observations == 1
    assert distributions[0].mean_mean == decimal.Decimal("0.03636900000000000000")
    assert distributions[0].mean_sd is None
    assert distributions[0].min_mean == decimal.Decimal("0.00473300000000000000")
    assert distributions[0].min_sd is None
    assert distributions[0].max_mean == decimal.Decimal("0.14889600000000000000")
    assert distributions[0].max_sd is None
    assert distributions[0].median_mean == decimal.Decimal("0.00898800000000000000")
    assert distributions[0].median_sd is None
