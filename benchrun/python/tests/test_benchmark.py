"""isort:skip_file"""
import multiprocessing as mp
from time import sleep

import pytest
from benchadapt.result import BenchmarkResult

from benchrun import Benchmark, CaseList, Iteration
from benchrun.cache import CacheManager


class FakeIteration(Iteration):
    name: str = "fake-benchmark"

    def setup(self, case: dict) -> None:
        self.env = {"setup": True}

    def before_each(self, case: dict) -> None:
        self.env["case"] = case
        self.env["before_each"] = True
        self.env["x"] = 1

    def run(self, case: dict) -> None:
        sleep(0.1)
        self.env["run"] = True
        self.env["x"] += 1

        if "error" in case:
            raise Exception(case["error"])

    def after_each(self, case: dict) -> None:
        self.env["after_each"] = True
        self.env["x"] += 1

    def teardown(self, case: dict) -> None:
        self.env = {}


class TestIteration:
    iteration = FakeIteration()

    def test_init(self) -> None:
        assert self.iteration.name == "fake-benchmark"
        assert isinstance(self.iteration.cache, CacheManager)

    def test_setup(self) -> None:
        self.iteration.setup(case={"param": "arg"})
        assert self.iteration.env == {"setup": True}

    def test_before_each(self) -> None:
        self.iteration.setup(case={"param": "arg"})
        self.iteration.before_each(case={"param": "arg"})
        assert self.iteration.env["setup"]
        assert self.iteration.env["before_each"]
        assert self.iteration.env["x"] == 1
        assert self.iteration.env["case"]["param"] == "arg"

    def test_run(self) -> None:
        self.iteration.setup(case={"param": "arg"})
        self.iteration.before_each(case={"param": "arg"})
        self.iteration.run(case={"param": "arg"})
        assert self.iteration.env["setup"]
        assert self.iteration.env["before_each"]
        assert self.iteration.env["run"]
        assert self.iteration.env["x"] == 2
        assert self.iteration.env["case"]["param"] == "arg"

    def test_after_each(self) -> None:
        self.iteration.setup(case={"param": "arg"})
        self.iteration.before_each(case={"param": "arg"})
        self.iteration.run(case={"param": "arg"})
        self.iteration.after_each(case={"param": "arg"})
        assert self.iteration.env["setup"]
        assert self.iteration.env["before_each"]
        assert self.iteration.env["run"]
        assert self.iteration.env["after_each"]
        assert self.iteration.env["x"] == 3
        assert self.iteration.env["case"]["param"] == "arg"

    def test_teardown(self) -> None:
        self.iteration.setup(case={"param": "arg"})
        self.iteration.before_each(case={"param": "arg"})
        self.iteration.run(case={"param": "arg"})
        self.iteration.after_each(case={"param": "arg"})
        self.iteration.teardown(case={"param": "arg"})
        assert self.iteration.env == {}

    def test_call(self) -> None:
        queue = mp.Queue()
        result_direct = self.iteration(
            case={"param": "arg"},
            iterations=2,
            settings={
                "drop_caches": False,
                "gc_collect": True,
                "gc_disable": True,
                "subprocess": True,
                "error_handling": "stop",
            },
            queue=queue,
        )

        result_queue = queue.get()

        for res in [result_direct, result_queue]:
            for time in res["stats"]["data"]:
                assert time > 0
            assert res["stats"]["iterations"] == 2
            assert res["error"] is None

        error_message = "You told me to fail!"
        with pytest.warns(UserWarning, match=error_message):
            result_direct_error = self.iteration(
                case={"param": "arg", "error": error_message},
                iterations=2,
                settings={
                    "drop_caches": False,
                    "gc_collect": True,
                    "gc_disable": True,
                    "subprocess": True,
                    "error_handling": "stop",
                },
                queue=queue,
            )

        result_queue_error = queue.get()

        for res in [result_direct_error, result_queue_error]:
            assert res["stats"] is None
            assert res["error"]["error"] == f"Exception('{error_message}')"
            assert "Traceback (most recent call last):" in res["error"]["stack_trace"]
            assert 'raise Exception(case["error"])' in res["error"]["stack_trace"]


class TestBenchmark:
    iteration = FakeIteration()
    case_list = CaseList(params={"foo": [1, 10, 100]})
    benchmark = Benchmark(iteration=iteration, case_list=case_list)
    benchmark_single_process = Benchmark(
        iteration=iteration, case_list=case_list, subprocess=False
    )
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
        assert self.benchmark.iteration == self.iteration
        assert self.benchmark.case_list == self.case_list
        assert self.benchmark.result_fields_append == {}
        assert self.benchmark.settings == {
            "drop_caches": False,
            "gc_collect": True,
            "gc_disable": True,
            "subprocess": True,
            "error_handling": "stop",
        }
        assert isinstance(self.benchmark.cache, CacheManager)

    @pytest.mark.parametrize("benchmark", [benchmark, benchmark_single_process])
    @pytest.mark.parametrize("case", case_list.case_list)
    def test_run_case(
        self, case: dict, benchmark: Benchmark, mock_github_env_vars
    ) -> None:
        result = benchmark.run_case(
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
        assert result.github["repository"] == self.github["repository"]
        assert result.github["commit"] == self.github["commit"]
        assert result.github["pr_number"] == self.github["pr_number"]
        assert result.stats["iterations"] == 2
        assert len(result.stats["data"]) == 2
        for time in result.stats["data"]:
            assert time > 0
        assert result.error is None
        assert result.tags == {"name": self.iteration.name, **case}
        assert result.info == {}
        assert result.context == {"benchmark_language": "Python"}

    @pytest.mark.parametrize("benchmark", [benchmark, benchmark_single_process])
    def test_run(self, benchmark: Benchmark, mock_github_env_vars) -> None:
        result_list = benchmark.run(
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
