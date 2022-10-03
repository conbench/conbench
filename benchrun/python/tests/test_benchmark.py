import multiprocessing as mp

import pytest
from benchadapt.result import BenchmarkResult

from benchrun import Benchmark, CaseList, Iteration
from benchrun.cache import CacheManager


class FakeIteration(Iteration):
    name: str = "fake-benchmark"

    def setup(self, case: dict) -> dict:
        return {"case": case, "setup": True, "x": 1}

    def run(self, case: dict, setup_results: dict) -> dict:
        setup_results["run"] = True
        setup_results["x"] += 1
        return setup_results

    def teardown(self, case: dict, run_results: dict) -> dict:
        run_results["teardown"] = True
        run_results["x"] += 1
        return run_results


class TestIteration:
    iteration = FakeIteration()
    setup_results: dict = None
    run_results: dict = None

    def setup(self) -> None:
        self.setup_results = self.iteration.setup(case={"param": "arg"})

    def run(self) -> None:
        self.run_results = self.iteration.run(
            case={"param": "arg"}, setup_results=self.setup_results
        )

    def test_init(self) -> None:
        assert self.iteration.name == "fake-benchmark"
        assert isinstance(self.iteration.cache, CacheManager)

    def test_setup(self) -> None:
        self.setup()
        assert self.setup_results["setup"]
        assert self.setup_results["x"] == 1
        assert self.setup_results["case"]["param"] == "arg"

    def test_run(self) -> None:
        self.run()
        assert self.run_results["setup"]
        assert self.run_results["run"]
        assert self.run_results["x"] == 2
        assert self.run_results["case"]["param"] == "arg"

    def test_teardown(self) -> None:
        self.setup()
        self.run()
        teardown_results = self.iteration.teardown(
            case={"param": "arg"}, run_results=self.run_results
        )
        assert teardown_results["setup"]
        assert teardown_results["run"]
        assert teardown_results["teardown"]
        assert teardown_results["x"] == 3
        assert teardown_results["case"]["param"] == "arg"

    def test_call(self) -> None:
        queue = mp.Queue()
        time = self.iteration(
            case={"param": "arg"},
            settings={
                "drop_caches": False,
                "gc_collect": True,
                "gc_disable": True,
                "error_handling": "stop",
            },
            queue=queue,
        )
        assert time > 0

        result = queue.get()
        assert time == result["time"]
        assert result["error"] is None


class TestBenchmark:
    iteration = FakeIteration()
    case_list = CaseList(params={"foo": [1, 10, 100]})
    benchmark = Benchmark(iteration=iteration, case_list=case_list)

    def test_init(self) -> None:
        assert self.benchmark.iteration == self.iteration
        assert self.benchmark.case_list == self.case_list
        assert self.benchmark.result_fields_append == {}
        assert self.benchmark.settings == {
            "drop_caches": False,
            "gc_collect": True,
            "gc_disable": True,
            "error_handling": "stop",
        }
        assert isinstance(self.benchmark.cache, CacheManager)

    def test_run_iteration(self) -> None:
        result = self.benchmark.run_iteration(case=self.case_list.case_list[0])
        assert result["time"] > 0
        assert result["error"] is None

    @pytest.mark.parametrize("case", case_list.case_list)
    def test_run_case(self, case: dict) -> None:
        result = self.benchmark.run_case(
            case=case,
            iterations=2,
            run_reason="test",
            run_name="test-run-case-name",
            run_id="test-run-case-run-id",
            batch_id="test-run-case-batch-id",
        )
        assert isinstance(result, BenchmarkResult)
        assert result.run_reason == "test"
        assert result.run_name == "test-run-case-name"
        assert result.run_id == "test-run-case-run-id"
        assert result.batch_id == "test-run-case-batch-id"
        assert result.stats["iterations"] == 2
        assert len(result.stats["data"]) == 2
        for time in result.stats["data"]:
            assert time > 0
        assert result.error is None
        assert result.tags == {"name": self.iteration.name, **case}
        assert result.info == {}
        assert result.context == {"benchmark_language": "Python"}

    def test_run(self) -> None:
        result_list = self.benchmark.run(
            run_reason="test",
            run_name="test-run-name",
            run_id="test-run-run-id",
            batch_id="test-run-batch-id",
            iterations=2,
        )
        assert len(result_list) == len(self.case_list.case_list)
        for result in result_list:
            assert isinstance(result, BenchmarkResult)
            assert result.run_reason == "test"
            assert result.run_name == "test-run-name"
            assert result.run_id == "test-run-run-id"
            assert result.batch_id == "test-run-batch-id"
            assert result.stats["iterations"] == 2
            assert len(result.stats["data"]) == 2
            for time in result.stats["data"]:
                assert time > 0
            assert result.error is None
            assert result.tags["name"] == self.iteration.name
            assert result.tags["foo"] in self.case_list.params["foo"]
            assert result.info == {}
            assert result.context == {"benchmark_language": "Python"}
