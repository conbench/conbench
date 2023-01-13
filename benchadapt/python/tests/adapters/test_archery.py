import json

import pytest
from benchadapt.adapters import ArcheryAdapter
from benchadapt.result import BenchmarkResult

archery_json = {
    "suites": [
        {
            "name": "arrow-tensor-conversion-benchmark",
            "benchmarks": [
                {
                    "name": "DoubleColumnMajorTensorConversionFixture<Int32Type>/ConvertToSparseCOOTensorInt32",
                    "unit": "bytes_per_second",
                    "less_is_better": False,
                    "values": [
                        3843659358.727243,
                        3846368103.9123325,
                        3852355319.7965193,
                    ],
                    "time_unit": "ns",
                    "times": [89813.27749444859, 89951.00325321, 90086.37264234325],
                    "counters": {
                        "family_index": 13,
                        "per_family_instance_index": 0,
                        "run_name": "DoubleColumnMajorTensorConversionFixture<Int32Type>/ConvertToSparseCOOTensorInt32",
                        "repetitions": 3,
                        "repetition_index": 2,
                        "threads": 1,
                        "iterations": 7691,
                    },
                },
                {
                    "name": "DoubleColumnMajorTensorConversionFixture<Int32Type>/ConvertToSparseCSFTensorInt32",
                    "unit": "bytes_per_second",
                    "less_is_better": False,
                    "values": [906194205.7378266, 921971663.0376312, 922406541.4456899],
                    "time_unit": "ns",
                    "times": [
                        374886.0342104987,
                        375056.96038956096,
                        381894.73465721105,
                    ],
                    "counters": {
                        "family_index": 31,
                        "per_family_instance_index": 0,
                        "run_name": "DoubleColumnMajorTensorConversionFixture<Int32Type>/ConvertToSparseCSFTensorInt32",
                        "repetitions": 3,
                        "repetition_index": 1,
                        "threads": 1,
                        "iterations": 1839,
                    },
                },
            ],
        }
    ]
}


class TestArcheryAdapter:
    @pytest.fixture
    def archery_adapter(self, monkeypatch):
        monkeypatch.setenv(
            "CONBENCH_PROJECT_REPOSITORY", "git@github.com:conchair/conchair"
        )
        monkeypatch.setenv("CONBENCH_PROJECT_PR_NUMBER", "47")
        monkeypatch.setenv(
            "CONBENCH_PROJECT_COMMIT", "2z8c9c49a5dc4a179243268e4bb6daa5"
        )

        archery_adapter = ArcheryAdapter()
        archery_adapter.command = ["echo", "'Hello, world!'"]

        with open(archery_adapter.result_file, "w") as f:
            json.dump(archery_json, f)

        return archery_adapter

    def test_transform_results(self, archery_adapter) -> None:
        results = archery_adapter.transform_results()

        assert len(results) == len(archery_json["suites"][0]["benchmarks"])
        for result in results:
            original = [
                blob
                for blob in archery_json["suites"][0]["benchmarks"]
                if result.tags["params"] in blob["name"]
            ][0]
            assert isinstance(result, BenchmarkResult)
            assert result.tags["name"] == "DoubleColumnMajorTensorConversionFixture"
            assert result.context == {"benchmark_language": "C++"}
            assert "params" in result.tags
            assert result.machine_info is not None
            assert result.stats["data"] == original["values"]
            assert result.stats["times"] == original["times"]
            assert result.stats["iterations"] == len(original["values"])

    def test_run(self, archery_adapter) -> None:
        results = archery_adapter.run()
        assert len(results) == len(archery_json["suites"][0]["benchmarks"])
