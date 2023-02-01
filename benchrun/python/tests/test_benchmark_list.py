import pytest

from benchrun import Benchmark, BenchmarkList, CaseList, Iteration


class FakeIteration(Iteration):
    name: str = "fake-benchmark"

    def run(self, case: dict) -> None:
        self.env = {"x": 1, "case": case}


class TestBenchmarkList:
    iteration = FakeIteration()
    case_list = CaseList(params={"foo": [1, 10, 100]})
    benchmark = Benchmark(iteration=iteration, case_list=case_list)
    benchmark_list = BenchmarkList([benchmark, benchmark])
    github = {
        "commit": "2z8c9c49a5dc4a179243268e4bb6daa5",
        "repository": "git@github.com:conchair/conchair",
        "pr_number": "47",
    }

    @pytest.fixture
    def mock_github_env_vars(self, monkeypatch):
        monkeypatch.setenv("CONBENCH_PROJECT_REPOSITORY", self.github["repository"])
        monkeypatch.setenv("CONBENCH_PROJECT_PR_NUMBER", self.github["pr_number"])
        monkeypatch.setenv("CONBENCH_PROJECT_COMMIT", self.github["commit"])

    def test_init(self) -> None:
        assert len(self.benchmark_list.benchmarks) == 2
        assert self.benchmark_list.benchmarks[0] == self.benchmark

    def test_call(self, mock_github_env_vars) -> None:
        result_list = self.benchmark_list(run_reason="test")
        assert len(result_list) == (
            len(self.benchmark_list.benchmarks) * len(self.case_list.case_list)
        )
        run_id = result_list[0].run_id
        for result in result_list:
            # all results should have the same run_id
            assert result.run_id == run_id
            assert result.run_reason == "test"
