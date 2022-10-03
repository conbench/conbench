from benchrun import Benchmark, BenchmarkList, CaseList, Iteration


class FakeIteration(Iteration):
    name: str = "fake-benchmark"

    def run(self, case: dict, setup_results: dict) -> dict:
        return {"x": 1, "case": case, "setup_results": setup_results}


class TestBenchmarkList:
    iteration = FakeIteration()
    case_list = CaseList(params={"foo": [1, 10, 100]})
    benchmark = Benchmark(iteration=iteration, case_list=case_list)
    benchmark_list = BenchmarkList([benchmark, benchmark])

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
