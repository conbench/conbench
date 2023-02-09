import json
import tempfile
from pathlib import Path

import pytest
from benchadapt.adapters import GoogleBenchmarkAdapter
from benchadapt.result import BenchmarkResult

gbench_json = {
    "context": {
        "date": "2022-09-02T16:11:56-05:00",
        "host_name": "snork.local",
        "executable": "/var/folders/0j/zz6p_mjx2_b727p6xdpm5chc0000gn/T/arrow-archery-pvr_us0l/WORKSPACE/build/release/arrow-tensor-conversion-benchmark",
        "num_cpus": 10,
        "mhz_per_cpu": 24,
        "cpu_scaling_enabled": False,
        "caches": [
            {"type": "Data", "level": 1, "size": 65536, "num_sharing": 1},
            {"type": "Instruction", "level": 1, "size": 131072, "num_sharing": 1},
            {"type": "Unified", "level": 2, "size": 4194304, "num_sharing": 2},
        ],
        "load_avg": [28.4897, 27.9819, 24.3301],
        "library_build_type": "release",
    },
    "benchmarks": [
        {
            "name": "Int8RowMajorTensorConversionFixture<Int32Type>/ConvertToSparseCOOTensorInt32",
            "family_index": 0,
            "per_family_instance_index": 0,
            "run_name": "Int8RowMajorTensorConversionFixture<Int32Type>/ConvertToSparseCOOTensorInt32",
            "run_type": "iteration",
            "repetitions": 3,
            "repetition_index": 0,
            "threads": 1,
            "iterations": 7150,
            "real_time": 88572.83803106814,
            "cpu_time": 88450.62937062935,
            "time_unit": "ns",
            "bytes_per_second": 488408056.6457208,
            "items_per_second": 488408056.6457208,
        },
        {
            "name": "Int8RowMajorTensorConversionFixture<Int32Type>/ConvertToSparseCOOTensorInt32",
            "family_index": 0,
            "per_family_instance_index": 0,
            "run_name": "Int8RowMajorTensorConversionFixture<Int32Type>/ConvertToSparseCOOTensorInt32",
            "run_type": "iteration",
            "repetitions": 3,
            "repetition_index": 1,
            "threads": 1,
            "iterations": 7150,
            "real_time": 87653.01273132746,
            "cpu_time": 87590.76923076922,
            "time_unit": "ns",
            "bytes_per_second": 493202655.70660776,
            "items_per_second": 493202655.70660776,
        },
        {
            "name": "Int8RowMajorTensorConversionFixture<Int32Type>/ConvertToSparseCOOTensorInt32",
            "family_index": 0,
            "per_family_instance_index": 0,
            "run_name": "Int8RowMajorTensorConversionFixture<Int32Type>/ConvertToSparseCOOTensorInt32",
            "run_type": "iteration",
            "repetitions": 3,
            "repetition_index": 2,
            "threads": 1,
            "iterations": 7150,
            "real_time": 89332.75062069818,
            "cpu_time": 89155.1048951049,
            "time_unit": "ns",
            "bytes_per_second": 484548810.1979892,
            "items_per_second": 484548810.1979892,
        },
        {
            "name": "Int8RowMajorTensorConversionFixture<Int32Type>/ConvertToSparseCOOTensorInt32_mean",
            "family_index": 0,
            "per_family_instance_index": 0,
            "run_name": "Int8RowMajorTensorConversionFixture<Int32Type>/ConvertToSparseCOOTensorInt32",
            "run_type": "aggregate",
            "repetitions": 3,
            "threads": 1,
            "aggregate_name": "mean",
            "aggregate_unit": "time",
            "iterations": 3,
            "real_time": 88519.53379436459,
            "cpu_time": 88398.83449883446,
            "time_unit": "ns",
            "bytes_per_second": 488719840.8501059,
            "items_per_second": 488719840.8501059,
        },
        {
            "name": "Int8RowMajorTensorConversionFixture<Int32Type>/ConvertToSparseCOOTensorInt32_median",
            "family_index": 0,
            "per_family_instance_index": 0,
            "run_name": "Int8RowMajorTensorConversionFixture<Int32Type>/ConvertToSparseCOOTensorInt32",
            "run_type": "aggregate",
            "repetitions": 3,
            "threads": 1,
            "aggregate_name": "median",
            "aggregate_unit": "time",
            "iterations": 3,
            "real_time": 88572.83803106814,
            "cpu_time": 88450.62937062937,
            "time_unit": "ns",
            "bytes_per_second": 488408056.6457208,
            "items_per_second": 488408056.6457208,
        },
        {
            "name": "Int8RowMajorTensorConversionFixture<Int32Type>/ConvertToSparseCOOTensorInt32_stddev",
            "family_index": 0,
            "per_family_instance_index": 0,
            "run_name": "Int8RowMajorTensorConversionFixture<Int32Type>/ConvertToSparseCOOTensorInt32",
            "run_type": "aggregate",
            "repetitions": 3,
            "threads": 1,
            "aggregate_name": "stddev",
            "aggregate_unit": "time",
            "iterations": 3,
            "real_time": 841.1366419830096,
            "cpu_time": 783.4529655553991,
            "time_unit": "ns",
            "bytes_per_second": 4335339.382834059,
            "items_per_second": 4335339.382834059,
        },
        {
            "name": "Int8RowMajorTensorConversionFixture<Int32Type>/ConvertToSparseCOOTensorInt32_cv",
            "family_index": 0,
            "per_family_instance_index": 0,
            "run_name": "Int8RowMajorTensorConversionFixture<Int32Type>/ConvertToSparseCOOTensorInt32",
            "run_type": "aggregate",
            "repetitions": 3,
            "threads": 1,
            "aggregate_name": "cv",
            "aggregate_unit": "percentage",
            "iterations": 3,
            "real_time": 0.009502271486619135,
            "cpu_time": 0.008862706957586966,
            "time_unit": "ns",
            "bytes_per_second": 0.00887080699505249,
            "items_per_second": 0.00887080699505249,
        },
        {
            "name": "Int8ColumnMajorTensorConversionFixture<Int32Type>/ConvertToSparseCOOTensorInt32",
            "family_index": 1,
            "per_family_instance_index": 0,
            "run_name": "Int8ColumnMajorTensorConversionFixture<Int32Type>/ConvertToSparseCOOTensorInt32",
            "run_type": "iteration",
            "repetitions": 3,
            "repetition_index": 0,
            "threads": 1,
            "iterations": 7635,
            "real_time": 90967.36529355316,
            "cpu_time": 90905.69744597246,
            "time_unit": "ns",
            "bytes_per_second": 475217738.97257483,
            "items_per_second": 475217738.97257483,
        },
        {
            "name": "Int8ColumnMajorTensorConversionFixture<Int32Type>/ConvertToSparseCOOTensorInt32",
            "family_index": 1,
            "per_family_instance_index": 0,
            "run_name": "Int8ColumnMajorTensorConversionFixture<Int32Type>/ConvertToSparseCOOTensorInt32",
            "run_type": "iteration",
            "repetitions": 3,
            "repetition_index": 1,
            "threads": 1,
            "iterations": 7635,
            "real_time": 90569.7118398229,
            "cpu_time": 90546.2999345121,
            "time_unit": "ns",
            "bytes_per_second": 477103979.19345725,
            "items_per_second": 477103979.19345725,
        },
        {
            "name": "Int8ColumnMajorTensorConversionFixture<Int32Type>/ConvertToSparseCOOTensorInt32",
            "family_index": 1,
            "per_family_instance_index": 0,
            "run_name": "Int8ColumnMajorTensorConversionFixture<Int32Type>/ConvertToSparseCOOTensorInt32",
            "run_type": "iteration",
            "repetitions": 3,
            "repetition_index": 2,
            "threads": 1,
            "iterations": 7635,
            "real_time": 91584.7740672192,
            "cpu_time": 91417.94368041903,
            "time_unit": "ns",
            "bytes_per_second": 472554930.2554821,
            "items_per_second": 472554930.2554821,
        },
    ],
}

big_gbench_json = {
    "context": {
        "date": "2023-02-07T16:16:18+01:00",
        "host_name": "aLaptop",
        "executable": "../../cpp/build/gbenchmarks/do_fun_things_benchmark",
        "num_cpus": 16,
        "mhz_per_cpu": 4600,
        "cpu_scaling_enabled": True,
        "caches": [
            {"type": "Data", "level": 1, "size": 49152, "num_sharing": 2},
            {"type": "Instruction", "level": 1, "size": 32768, "num_sharing": 2},
            {"type": "Unified", "level": 2, "size": 1310720, "num_sharing": 2},
            {"type": "Unified", "level": 3, "size": 25165824, "num_sharing": 16},
        ],
        "load_avg": [2.76, 2.33, 1.56],
        "library_build_type": "release",
    },
    "benchmarks": [
        *[
            {
                "name": "DoThingAndThenUndoIt/param_1:0/param_2:1024/param_3:1600/real_time/threads:1",
                "family_index": 0,
                "per_family_instance_index": 0,
                "run_name": "DoThingAndThenUndoIt/param_1:0/param_2:1024/param_3:1600/real_time/threads:1",
                "run_type": "iteration",
                "repetitions": 1,
                "repetition_index": 0,
                "threads": 1,
                "iterations": 1396,
                "real_time": 4.7759552005683666e05,
                "cpu_time": 4.7759015257879649e05,
                "time_unit": "ns",
            }
        ]
        * 3,
        *[
            {
                "name": "DoThingAndThenUndoIt/param_1:0/param_2:1024/param_3:1600/real_time/threads:2",
                "family_index": 0,
                "per_family_instance_index": 1,
                "run_name": "DoThingAndThenUndoIt/param_1:0/param_2:1024/param_3:1600/real_time/threads:2",
                "run_type": "iteration",
                "repetitions": 1,
                "repetition_index": 0,
                "threads": 2,
                "iterations": 424,
                "real_time": 1.3930781780654453e06,
                "cpu_time": 2.2883681108490578e06,
                "time_unit": "ns",
            }
        ]
        * 3,
        *[
            {
                "name": "DoThingAndThenUndoItDifferently/param_1:0/param_2:1024/real_time/threads:1",
                "family_index": 1,
                "per_family_instance_index": 0,
                "run_name": "DoThingAndThenUndoItDifferently/param_1:0/param_2:1024/real_time/threads:1",
                "run_type": "iteration",
                "repetitions": 1,
                "repetition_index": 0,
                "threads": 1,
                "iterations": 5374,
                "real_time": 1.2566177409746450e05,
                "cpu_time": 1.2565883178265738e05,
                "time_unit": "ns",
            }
        ]
        * 3,
        *[
            {
                "name": "DoThingAndThenUndoItDifferently/param_1:0/param_2:1024/real_time/threads:2",
                "family_index": 1,
                "per_family_instance_index": 1,
                "run_name": "DoThingAndThenUndoItDifferently/param_1:0/param_2:1024/real_time/threads:2",
                "run_type": "iteration",
                "repetitions": 1,
                "repetition_index": 0,
                "threads": 2,
                "iterations": 2596,
                "real_time": 2.5244852041621989e05,
                "cpu_time": 4.2161582781201869e05,
                "time_unit": "ns",
            }
        ]
        * 3,
    ],
}


class TestGbenchAdapter:
    @pytest.fixture
    def gbench_adapter(self, monkeypatch):
        monkeypatch.setenv(
            "CONBENCH_PROJECT_REPOSITORY", "git@github.com:conchair/conchair"
        )
        monkeypatch.setenv("CONBENCH_PROJECT_PR_NUMBER", "47")
        monkeypatch.setenv(
            "CONBENCH_PROJECT_COMMIT", "2z8c9c49a5dc4a179243268e4bb6daa5"
        )

        result_file = tempfile.mktemp(suffix=".json")
        gbench_adapter = GoogleBenchmarkAdapter(
            command=["echo", "'Hello, world!'"], result_file=Path(result_file)
        )

        with open(gbench_adapter.result_file, "w") as f:
            json.dump(gbench_json, f)

        return gbench_adapter

    def test_transform_results(self, gbench_adapter) -> None:
        results = gbench_adapter.transform_results()

        assert len(results) == 2
        # each benchmark name should have a different batch_id regardless of the number of results
        assert len(set(res.tags["name"] for res in results)) == 2
        assert len(set(res.batch_id for res in results)) == 2
        for result in results:
            assert isinstance(result, BenchmarkResult)
            assert isinstance(result.run_name, str)
            assert result.tags["name"].endswith("MajorTensorConversionFixture")
            assert result.context == {"benchmark_language": "C++"}
            assert "params" in result.tags
            assert result.machine_info is not None
            assert result.stats["iterations"] == 3
            assert "gbench_context" in result.optional_benchmark_info

    def test_run(self, gbench_adapter) -> None:
        results = gbench_adapter.run()
        assert len(results) == 2


class TestBigGbenchAdapter:
    @pytest.fixture
    def gbench_adapter(self, monkeypatch):
        monkeypatch.setenv(
            "CONBENCH_PROJECT_REPOSITORY", "git@github.com:conchair/conchair"
        )
        monkeypatch.setenv("CONBENCH_PROJECT_PR_NUMBER", "47")
        monkeypatch.setenv(
            "CONBENCH_PROJECT_COMMIT", "2z8c9c49a5dc4a179243268e4bb6daa5"
        )

        result_file = tempfile.mktemp(suffix=".json")
        gbench_adapter = GoogleBenchmarkAdapter(
            command=["echo", "'Hello, world!'"], result_file=Path(result_file)
        )

        with open(gbench_adapter.result_file, "w") as f:
            json.dump(big_gbench_json, f)

        return gbench_adapter

    def test_transform_results(self, gbench_adapter) -> None:
        results = gbench_adapter.transform_results()

        assert len(results) == 4
        # each benchmark name should have a different batch_id regardless of the number of results
        assert len(set(res.tags["name"] for res in results)) == 2
        assert len(set(res.batch_id for res in results)) == 2
        for result in results:
            assert isinstance(result, BenchmarkResult)
            assert isinstance(result.run_name, str)
            assert result.tags["name"].startswith("DoThingAndThenUndoIt")
            assert result.context == {"benchmark_language": "C++"}
            assert "params" in result.tags
            assert result.machine_info is not None
            assert result.stats["iterations"] == 3
            assert "gbench_context" in result.optional_benchmark_info

    def test_run(self, gbench_adapter) -> None:
        results = gbench_adapter.run()
        assert len(results) == 4
