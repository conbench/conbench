import os
import uuid

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy.orm.exc import ObjectDeletedError

from ...db import Session

this_dir = os.path.abspath(os.path.dirname(__file__))
config_path = os.path.join(this_dir, "../../../alembic.ini")


# new school
VALID_PAYLOAD_1 = {
    "run_id": "2a5709d179f349cba69ed242be3e6321",
    "run_name": "commit: 02addad336ba19a654f9c857ede546331be7b631",
    "batch_id": "7b2fdd9f929d47b9960152090d47f8e6",
    "timestamp": "2020-11-25T21:02:42.706806+00:00",
    "context": {
        "arrow_compiler_flags": "-fPIC -arch x86_64 -arch x86_64 -std=c++11 -Qunused-arguments -fcolor-diagnostics -O3 -DNDEBUG",
        "benchmark_language": "Python",
    },
    "info": {
        "arrow_version": "2.0.0",
        "benchmark_language_version": "Python 3.8.5",
        "arrow_compiler_version": "11.0.0.11000033",
        "arrow_compiler_id": "AppleClang",
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
        "name": uuid.uuid4().hex,
    },
}

# old school
VALID_PAYLOAD_2 = {
    "run_id": "2a5709d179f349cba69ed242be3e6321",
    "run_name": "commit: 02addad336ba19a654f9c857ede546331be7b631",
    "batch_id": "7b2fdd9f929d47b9960152090d47f8e6",
    "timestamp": "2020-11-25T21:02:42.706806+00:00",
    "context": {
        "arrow_compiler_flags": "-fPIC -arch x86_64 -arch x86_64 -std=c++11 -Qunused-arguments -fcolor-diagnostics -O3 -DNDEBUG",
        "benchmark_language": "Python",
        "arrow_version": "2.0.0",
        "benchmark_language_version": "Python 3.8.5",
        "arrow_compiler_version": "11.0.0.11000033",
        "arrow_compiler_id": "AppleClang",
    },
    "info": {},
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
        "name": uuid.uuid4().hex,
    },
}

# old school - correct info & context doesn't exist yet
VALID_PAYLOAD_3 = {
    "run_id": "2a5709d179f349cba69ed242be3e6321",
    "run_name": "commit: 02addad336ba19a654f9c857ede546331be7b631",
    "batch_id": "7b2fdd9f929d47b9960152090d47f8e6",
    "timestamp": "2020-11-25T21:02:42.706806+00:00",
    "context": {
        "arrow_compiler_flags": "-fPIC -arch x86_64 -arch x86_64 -std=c++11 -Qunused-arguments -fcolor-diagnostics -O3 -DNDEBUG",
        "benchmark_language": "R",
        "arrow_version": "7.0.0-SNAPSHOT",
        "benchmark_language_version": "R version 4.1.1 (2021-08-10)",
        "arrow_compiler_version": "9.4.0",
        "arrow_compiler_id": "GNU",
        "arrow_version_r": "6.0.0.9000",
    },
    "info": {},
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
        "name": uuid.uuid4().hex,
    },
}

# non-arrow, description
VALID_PAYLOAD_4 = {
    "run_id": "2a5709d179f349cba69ed242be3e6321",
    "run_name": "commit: 02addad336ba19a654f9c857ede546331be7b631",
    "batch_id": "7b2fdd9f929d47b9960152090d47f8e6",
    "timestamp": "2020-11-25T21:02:42.706806+00:00",
    "context": {
        "benchmark_language": "R",
        "description": "some long description",
        "foo_version": "0.3.0",
        "benchmark_language_version": "R version 4.1.1 (2021-08-10)",
        "LOGGING_LEVEL": "trace",
        "data_path": "/mnt/workspace/foo/100",
    },
    "info": {},
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
        "name": uuid.uuid4().hex,
    },
}

# non-arrow, empty description
VALID_PAYLOAD_5 = {
    "run_id": "2a5709d179f349cba69ed242be3e6321",
    "run_name": "commit: 02addad336ba19a654f9c857ede546331be7b631",
    "batch_id": "7b2fdd9f929d47b9960152090d47f8e6",
    "timestamp": "2020-11-25T21:02:42.706806+00:00",
    "context": {
        "benchmark_language": "R",
        "description": "",
        "foo_version": "0.3.0",
        "benchmark_language_version": "R version 4.1.1 (2021-08-10)",
        "LOGGING_LEVEL": "trace",
        "data_path": "/mnt/workspace/foo/100",
    },
    "info": {},
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
        "name": uuid.uuid4().hex,
    },
}


def test_upgrade():
    from ...entities.context import Context
    from ...entities.info import Info
    from ...entities.summary import Summary

    # fishy -- why isn't create_db in conftest.py dropping all?
    Summary.delete_all()
    Context.delete_all()
    Info.delete_all()

    summary_1 = Summary.create(VALID_PAYLOAD_1)
    summary_2 = Summary.create(VALID_PAYLOAD_2)
    summary_3 = Summary.create(VALID_PAYLOAD_3)
    summary_4 = Summary.create(VALID_PAYLOAD_4)
    summary_5 = Summary.create(VALID_PAYLOAD_5)

    info_1 = summary_1.info
    context_1 = summary_1.context

    info_2 = summary_2.info
    context_2 = summary_2.context

    info_3 = summary_3.info
    context_3 = summary_3.context

    info_4 = summary_4.info
    context_4 = summary_4.context

    info_5 = summary_5.info
    context_5 = summary_5.context

    # before migration
    assert summary_1.info.tags == {
        "arrow_version": "2.0.0",
        "arrow_compiler_id": "AppleClang",
        "arrow_compiler_version": "11.0.0.11000033",
        "benchmark_language_version": "Python 3.8.5",
    }
    assert summary_1.context.tags == {
        "benchmark_language": "Python",
        "arrow_compiler_flags": "-fPIC -arch x86_64 -arch x86_64 -std=c++11 -Qunused-arguments -fcolor-diagnostics -O3 -DNDEBUG",
    }

    assert summary_2.info.tags == {}
    assert summary_2.context.tags == {
        "arrow_version": "2.0.0",
        "arrow_compiler_id": "AppleClang",
        "benchmark_language": "Python",
        "arrow_compiler_flags": "-fPIC -arch x86_64 -arch x86_64 -std=c++11 -Qunused-arguments -fcolor-diagnostics -O3 -DNDEBUG",
        "arrow_compiler_version": "11.0.0.11000033",
        "benchmark_language_version": "Python 3.8.5",
    }

    assert summary_3.info.tags == {}
    assert summary_3.context.tags == {
        "arrow_version": "7.0.0-SNAPSHOT",
        "arrow_version_r": "6.0.0.9000",
        "arrow_compiler_id": "GNU",
        "benchmark_language": "R",
        "arrow_compiler_flags": "-fPIC -arch x86_64 -arch x86_64 -std=c++11 -Qunused-arguments -fcolor-diagnostics -O3 -DNDEBUG",
        "arrow_compiler_version": "9.4.0",
        "benchmark_language_version": "R version 4.1.1 (2021-08-10)",
    }

    assert summary_4.info.tags == {}
    assert summary_4.context.tags == {
        "description": "some long description",
        "LOGGING_LEVEL": "trace",
        "foo_version": "0.3.0",
        "benchmark_language": "R",
        "benchmark_language_version": "R version 4.1.1 (2021-08-10)",
        "data_path": "/mnt/workspace/foo/100",
    }

    assert summary_5.info.tags == {}
    assert summary_5.context.tags == {
        "description": "",
        "LOGGING_LEVEL": "trace",
        "foo_version": "0.3.0",
        "benchmark_language": "R",
        "benchmark_language_version": "R version 4.1.1 (2021-08-10)",
        "data_path": "/mnt/workspace/foo/100",
    }

    assert summary_1.info_id != summary_2.info_id
    assert summary_1.context_id != summary_2.context_id

    assert summary_1.info_id != summary_3.info_id
    assert summary_1.context_id != summary_3.context_id

    # do migration
    alembic_config = Config(config_path)
    command.stamp(alembic_config, "3ddd66ca34f2")
    command.upgrade(alembic_config, "f542b3646629")

    # fishy -- how do you sync the alembic session with this one?
    Session.commit()

    # assert after migration
    assert summary_1.info.tags == {
        "arrow_version": "2.0.0",
        "arrow_compiler_id": "AppleClang",
        "arrow_compiler_version": "11.0.0.11000033",
        "benchmark_language_version": "Python 3.8.5",
    }
    assert summary_1.context.tags == {
        "benchmark_language": "Python",
        "arrow_compiler_flags": "-fPIC -arch x86_64 -arch x86_64 -std=c++11 -Qunused-arguments -fcolor-diagnostics -O3 -DNDEBUG",
    }

    assert summary_2.info.tags == {
        "arrow_version": "2.0.0",
        "arrow_compiler_id": "AppleClang",
        "arrow_compiler_version": "11.0.0.11000033",
        "benchmark_language_version": "Python 3.8.5",
    }
    assert summary_2.context.tags == {
        "benchmark_language": "Python",
        "arrow_compiler_flags": "-fPIC -arch x86_64 -arch x86_64 -std=c++11 -Qunused-arguments -fcolor-diagnostics -O3 -DNDEBUG",
    }

    assert summary_3.info.tags == {
        "arrow_version": "7.0.0-SNAPSHOT",
        "arrow_compiler_id": "GNU",
        "arrow_compiler_version": "9.4.0",
        "arrow_version_r": "6.0.0.9000",
        "benchmark_language_version": "R version 4.1.1 (2021-08-10)",
    }
    assert summary_3.context.tags == {
        "benchmark_language": "R",
        "arrow_compiler_flags": "-fPIC -arch x86_64 -arch x86_64 -std=c++11 -Qunused-arguments -fcolor-diagnostics -O3 -DNDEBUG",
    }

    assert summary_4.info.tags == {
        "foo_version": "0.3.0",
        "description": "some long description",
        "benchmark_language_version": "R version 4.1.1 (2021-08-10)",
        "data_path": "/mnt/workspace/foo/100",
    }
    assert summary_4.context.tags == {
        "benchmark_language": "R",
        "LOGGING_LEVEL": "trace",
    }

    assert summary_5.info.tags == {
        "foo_version": "0.3.0",
        "benchmark_language_version": "R version 4.1.1 (2021-08-10)",
        "data_path": "/mnt/workspace/foo/100",
    }
    assert summary_5.context.tags == {
        "benchmark_language": "R",
        "LOGGING_LEVEL": "trace",
    }

    assert summary_1.info_id == summary_2.info_id
    assert summary_1.context_id == summary_2.context_id

    assert summary_1.info_id != summary_3.info_id
    assert summary_1.context_id != summary_3.context_id

    Info.get(info_1.id)
    with pytest.raises(ObjectDeletedError):
        Info.get(info_2.id)
    with pytest.raises(ObjectDeletedError):
        Info.get(info_3.id)
    with pytest.raises(ObjectDeletedError):
        Info.get(info_4.id)
    with pytest.raises(ObjectDeletedError):
        Info.get(info_5.id)

    Context.get(context_1.id)
    with pytest.raises(ObjectDeletedError):
        Context.get(context_2.id)
    with pytest.raises(ObjectDeletedError):
        Context.get(context_3.id)
    with pytest.raises(ObjectDeletedError):
        Context.get(context_4.id)
    with pytest.raises(ObjectDeletedError):
        Context.get(context_5.id)
