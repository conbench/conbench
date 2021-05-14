import os

from alembic import command
from alembic.config import Config

from ...db import Session
from ...entities.machine import Machine
from ...entities.summary import Summary


this_dir = os.path.abspath(os.path.dirname(__file__))
config_path = os.path.join(this_dir, "../../../alembic.ini")


VALID_PAYLOAD_1 = {
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
        "memory_bytes": "131590280000",
        "name": "diana",
        "os_name": "macOS",
        "os_version": "10.15.7",
    },
    "stats": {
        "batch_id": "7b2fdd9f929d47b9960152090d47f8e6",
        "run_id": "test_d91083587a7e_merge_machines_1",
        "run_name": "commit: 02addad336ba19a654f9c857ede546331be7b631",
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
        "timestamp": "2020-11-25T21:02:42.706806+00:00",
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

VALID_PAYLOAD_2 = {
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
        "memory_bytes": "131593068000",
        "name": "diana",
        "os_name": "macOS",
        "os_version": "10.15.7",
    },
    "stats": {
        "batch_id": "7b2fdd9f929d47b9960152090d47f8e6",
        "run_id": "test_d91083587a7e_merge_machines_2",
        "run_name": "commit: 02addad336ba19a654f9c857ede546331be7b631",
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
        "timestamp": "2020-11-25T21:02:42.706806+00:00",
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

VALID_PAYLOAD_3 = {
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
        "memory_bytes": "131593872000",
        "name": "diana",
        "os_name": "macOS",
        "os_version": "10.15.7",
    },
    "stats": {
        "batch_id": "7b2fdd9f929d47b9960152090d47f8e6",
        "run_id": "test_d91083587a7e_merge_machines_3",
        "run_name": "commit: 02addad336ba19a654f9c857ede546331be7b631",
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
        "timestamp": "2020-11-25T21:02:42.706806+00:00",
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


VALID_PAYLOAD_4 = {
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
        "memory_bytes": "131593872000",
        "name": "diana-x",
        "os_name": "macOS",
        "os_version": "10.15.7",
    },
    "stats": {
        "batch_id": "7b2fdd9f929d47b9960152090d47f8e6",
        "run_id": "test_d91083587a7e_merge_machines_4",
        "run_name": "commit: 02addad336ba19a654f9c857ede546331be7b631",
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
        "timestamp": "2020-11-25T21:02:42.706806+00:00",
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


VALID_PAYLOAD_5 = {
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
        "memory_bytes": "132070244352",
        "name": "diana-y",
        "os_name": "macOS",
        "os_version": "10.15.7",
    },
    "stats": {
        "batch_id": "7b2fdd9f929d47b9960152090d47f8e6",
        "run_id": "test_d91083587a7e_merge_machines_5",
        "run_name": "commit: 02addad336ba19a654f9c857ede546331be7b631",
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
        "timestamp": "2020-11-25T21:02:42.706806+00:00",
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
    summary_1 = Summary.create(VALID_PAYLOAD_1)
    summary_2 = Summary.create(VALID_PAYLOAD_2)
    summary_3 = Summary.create(VALID_PAYLOAD_3)
    summary_4 = Summary.create(VALID_PAYLOAD_4)
    summary_5 = Summary.create(VALID_PAYLOAD_5)

    before_machine_id_1 = summary_1.machine_id
    before_machine_id_2 = summary_2.machine_id
    before_machine_id_3 = summary_3.machine_id
    before_machine_id_4 = summary_4.machine_id
    before_machine_id_5 = summary_5.machine_id

    # assert before migration
    machines = set(
        [
            summary_1.machine_id,
            summary_2.machine_id,
            summary_3.machine_id,
            summary_4.machine_id,
            summary_5.machine_id,
        ]
    )
    assert len(machines) == 5

    assert summary_1.machine_id == summary_1.run.machine_id
    assert summary_2.machine_id == summary_2.run.machine_id
    assert summary_3.machine_id == summary_3.run.machine_id
    assert summary_4.machine_id == summary_4.run.machine_id
    assert summary_5.machine_id == summary_5.run.machine_id

    assert summary_1.machine_id != summary_2.machine_id
    assert summary_1.machine_id != summary_3.machine_id
    assert summary_1.machine_id != summary_4.machine_id
    assert summary_1.machine_id != summary_5.machine_id

    assert summary_1.machine.memory_bytes == 131590280000
    assert summary_2.machine.memory_bytes == 131593068000
    assert summary_3.machine.memory_bytes == 131593872000
    assert summary_4.machine.memory_bytes == 131593872000
    assert summary_5.machine.memory_bytes == 132070244352

    assert Machine.get(before_machine_id_1) is not None
    assert Machine.get(before_machine_id_2) is not None
    assert Machine.get(before_machine_id_3) is not None
    assert Machine.get(before_machine_id_4) is not None
    assert Machine.get(before_machine_id_5) is not None

    # do migration
    alembic_config = Config(config_path)
    command.stamp(alembic_config, "6da4b0d2ad27")
    command.upgrade(alembic_config, "d91083587a7e")

    Session.refresh(summary_1)
    Session.refresh(summary_2)
    Session.refresh(summary_3)
    Session.refresh(summary_4)
    Session.refresh(summary_5)

    # assert after migration
    machines = set(
        [
            summary_1.machine_id,
            summary_2.machine_id,
            summary_3.machine_id,
            summary_4.machine_id,
            summary_5.machine_id,
        ]
    )
    assert len(machines) == 3

    assert summary_1.machine_id == summary_1.run.machine_id
    assert summary_2.machine_id == summary_2.run.machine_id
    assert summary_3.machine_id == summary_3.run.machine_id
    assert summary_4.machine_id == summary_4.run.machine_id
    assert summary_5.machine_id == summary_5.run.machine_id

    assert summary_1.machine_id == summary_2.machine_id
    assert summary_1.machine_id == summary_3.machine_id
    assert summary_1.machine_id != summary_4.machine_id
    assert summary_1.machine_id != summary_5.machine_id

    assert summary_1.machine.memory_bytes == 132070244352
    assert summary_2.machine.memory_bytes == 132070244352
    assert summary_3.machine.memory_bytes == 132070244352
    assert summary_4.machine.memory_bytes == 132070244352
    assert summary_5.machine.memory_bytes == 132070244352

    assert Machine.get(before_machine_id_1) is not None
    assert Machine.get(before_machine_id_2) is None  # deleted
    assert Machine.get(before_machine_id_3) is None  # deleted
    assert Machine.get(before_machine_id_4) is not None
    assert Machine.get(before_machine_id_5) is not None
