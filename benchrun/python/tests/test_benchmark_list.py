import pytest

from benchrun import (
    Benchmark,
    CallableBenchmarkList,
    CaseList,
    GeneratorBenchmarkList,
    Iteration,
)


class FakeIteration(Iteration):
    name: str = "fake-benchmark"

    def run(self, case: dict) -> None:
        self.env = {"x": 1, "case": case}


class TestCallableBenchmarkList:
    iteration = FakeIteration()
    case_list = CaseList(params={"foo": [1, 10, 100]})
    benchmark = Benchmark(iteration=iteration, case_list=case_list)
    benchmark_list = CallableBenchmarkList([benchmark, benchmark])

    def test_init(self) -> None:
        assert len(self.benchmark_list.benchmarks) == 2
        assert self.benchmark_list.benchmarks[0] == self.benchmark

    def test_call(self) -> None:
        result_list = self.benchmark_list(run_reason="test")
        assert len(result_list) == (
            len(self.benchmark_list.benchmarks) * len(self.case_list.case_list)
        )
        run_id = result_list[0].run_id
        for result in result_list:
            # all results should have the same run_id
            assert result.run_id == run_id
            assert result.run_reason == "test"


class TestGeneratorBenchmarkList:
    iteration = FakeIteration()
    case_list = CaseList(params={"foo": [1, 10, 100]})
    benchmark = Benchmark(iteration=iteration, case_list=case_list)
    benchmark_list = GeneratorBenchmarkList([benchmark, benchmark])

    def test_init(self) -> None:
        assert len(self.benchmark_list.benchmarks) == 2
        assert self.benchmark_list.benchmarks[0] == self.benchmark

    def test_call(self) -> None:
        run_id = None
        for result, case in zip(
            self.benchmark_list(run_reason="test"), self.case_list.case_list * 2
        ):
            if not run_id:
                run_id = result.run_id

            assert result.run_id == run_id
            assert result.run_reason == "test"
            assert result.tags["foo"] == case["foo"]

    def test_iter(self) -> None:
        generator = self.benchmark_list(run_reason="test")

        for case in self.case_list.case_list * 2:
            result = next(generator)
            assert result.run_reason == "test"
            assert result.tags["foo"] == case["foo"]

        # generator should be exhausted now
        with pytest.raises(StopIteration):
            next(generator)
