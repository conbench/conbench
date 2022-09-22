from pathlib import Path
from typing import List

from benchadapt.adapters import BenchmarkAdapter

from benchadapt import BenchmarkResult

RESULTS_DICT = {
    "run_name": "very-real-benchmark",
    "run_id": "ezf69672dc3741259aac97650414a18c",
    "batch_id": "1z21bd2477d04ca8be0f4bad58c61757",
    "run_reason": None,
    "timestamp": "2202-09-16T15:42:27.527948+00:00",
    "stats": {
        "data": [1.1, 2.2, 3.3],
        "unit": "ns",
        "times": [3.3, 2.2, 1.1],
        "time_unit": "ns",
    },
    "tags": {
        "name": "very-real-benchmark",
        "suite": "dope-benchmarks",
        "source": "app-micro",
    },
    "info": {},
    "context": {"benchmark_language": "A++"},
    "github": {
        "commit": "2z8c9c49a5dc4a179243268e4bb6daa5",
        "repository": "git@github.com:conchair/conchair",
    },
}


class FakeAdapter(BenchmarkAdapter):
    def _transform_results(self) -> List[BenchmarkResult]:
        return [BenchmarkResult(**RESULTS_DICT)]


class TestBenchmarkAdapter:
    def test_transform_results(self) -> None:
        fake_adapter = FakeAdapter(command=["echo", "hello"])

        res_list = fake_adapter.transform_results()
        assert res_list[0] == BenchmarkResult(**RESULTS_DICT)

    def test_run(self) -> None:
        fake_adapter = FakeAdapter(command=["echo", Path(".").resolve()])

        res_list = fake_adapter.run()
        assert res_list[0] == BenchmarkResult(**RESULTS_DICT)

    def test_override_results(self) -> None:
        result_fields_override = {"cluster_info": {"size": "v big"}}

        fake_adapter = FakeAdapter(
            command=["echo", "hello"],
            result_fields_override=result_fields_override,
        )

        res_list = fake_adapter.transform_results()
        assert res_list[0].cluster_info == result_fields_override["cluster_info"]
        # `machine_info` normally autopopulated, but should be depopulated when
        # `cluster_info` is specified
        assert res_list[0].machine_info is None

    def test_append_results(self) -> None:
        results_fields_append = {"tags": {"price": "$15.99"}}

        fake_adapter = FakeAdapter(
            command=["echo", "hello"],
            result_fields_append=results_fields_append,
        )

        res_list = fake_adapter.transform_results()
        assert res_list[0].tags == {
            **RESULTS_DICT["tags"],
            **results_fields_append["tags"],
        }
