import pytest

from benchadapt import BenchmarkResult

res_json = {
    "run_name": "very-real-benchmark",
    "run_id": "ezf69672dc3741259aac97650414a18c",
    "run_tags": {},
    "batch_id": "1z21bd2477d04ca8be0f4bad58c61757",
    "run_reason": "test",
    "timestamp": "2202-09-16T15:42:27.527948+00:00",
    "stats": {
        "data": [1.1, 2.2, 3.3],
        "unit": "ns",
        "times": [3.3, 2.2, 1.1],
        "time_unit": "ns",
        "iterations": 3,
    },
    "error": {"stack_trace": ["nothing", "really", "went", "wrong"]},
    "validation": {"worked_as_expected": True},
    "tags": {
        "name": "very-real-benchmark",
        "suite": "dope-benchmarks",
        "source": "app-micro",
    },
    "info": {},
    "optional_benchmark_info": {"foo": "bar"},
    "machine_info": {
        "name": "beepboop.local",
        "os_name": "macOS",
        "os_version": "12.6",
        "architecture_name": "arm64",
        "kernel_name": "21.6.0",
        "memory_bytes": "17179869184",
        "cpu_model_name": "Apple M3 Pro",
        "cpu_core_count": "100",
        "cpu_thread_count": "100",
        "cpu_l1d_cache_bytes": "655360",
        "cpu_l1i_cache_bytes": "1310720",
        "cpu_l2_cache_bytes": "41943040",
        "cpu_l3_cache_bytes": "0",
        "cpu_frequency_max_hz": "0",
        "gpu_count": "0",
        "gpu_product_names": [],
    },
    "context": {"benchmark_language": "A++"},
    "github": {
        "commit": "2z8c9c49a5dc4a179243268e4bb6daa5",
        "repository": "git@github.com:conchair/conchair",
        "pr_number": "47",
    },
}


class TestBenchmarkResult:
    def test_roundtrip(self):
        res = BenchmarkResult(**res_json)
        assert res_json == res.to_publishable_dict()

    def test_warns_stats_error(self):
        with pytest.warns(UserWarning, match="Result not publishable!"):
            BenchmarkResult(
                stats={}, error={}, github=res_json["github"]
            ).to_publishable_dict()

        with pytest.warns(UserWarning, match="Result not publishable!"):
            BenchmarkResult(
                stats=None, error=None, github=res_json["github"]
            ).to_publishable_dict()

    def test_warns_machine_cluster(self):
        with pytest.warns(UserWarning, match="Result not publishable!"):
            BenchmarkResult(
                machine_info={}, cluster_info={}, github=res_json["github"]
            ).to_publishable_dict()

        with pytest.warns(UserWarning, match="Result not publishable!"):
            BenchmarkResult(
                machine_info=None, cluster_info=None, github=res_json["github"]
            ).to_publishable_dict()

    def test_github_detection(self, monkeypatch):
        monkeypatch.setenv(
            "CONBENCH_PROJECT_REPOSITORY", res_json["github"]["repository"]
        )
        monkeypatch.setenv(
            "CONBENCH_PROJECT_PR_NUMBER", res_json["github"]["pr_number"]
        )
        monkeypatch.setenv("CONBENCH_PROJECT_COMMIT", res_json["github"]["commit"])
        assert BenchmarkResult().github == res_json["github"]

    def test_run_name_defaulting(self, monkeypatch):
        monkeypatch.setenv("CONBENCH_PROJECT_REPOSITORY", "http://localhost")
        monkeypatch.delenv("CONBENCH_PROJECT_PR_NUMBER", raising=False)
        monkeypatch.delenv("CONBENCH_PROJECT_COMMIT", raising=False)

        res = BenchmarkResult(run_reason=res_json["run_reason"])
        assert res.github == {"repository": "http://localhost"}

        assert res.run_name is None
        res.github = res_json["github"]
        assert (
            res.run_name == f"{res_json['run_reason']}: {res_json['github']['commit']}"
        )

    def test_commit_info_without_hash(self, monkeypatch):
        monkeypatch.setenv("CONBENCH_PROJECT_REPOSITORY", "http://localhost")
        monkeypatch.delenv("CONBENCH_PROJECT_PR_NUMBER", raising=False)
        monkeypatch.delenv("CONBENCH_PROJECT_COMMIT", raising=False)
        res = BenchmarkResult(stats={"data": [47.0]})
        d = res.to_publishable_dict()
        assert d["github"] == {"repository": "http://localhost"}

    def test_host_detection(self, monkeypatch):
        machine_info_name = "fake-computer-name"
        monkeypatch.setenv("CONBENCH_MACHINE_INFO_NAME", machine_info_name)

        result = BenchmarkResult(github=res_json["github"])
        assert result.machine_info["name"] == machine_info_name
        assert result.machine_info["name"] != res_json["machine_info"]["name"]
