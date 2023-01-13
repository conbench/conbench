import pytest

from benchadapt import BenchmarkRun

run_json = {
    "name": "very-real-benchmark",
    "id": "ezf69672dc3741259aac97650414a18c",
    "reason": "test",
    "finished_timestamp": "2202-09-16T15:42:27.527948+00:00",
    "error_info": {"stack_trace": ["nothing", "really", "went", "wrong"]},
    "error_type": "none really",
    "info": {},
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
    "github": {
        "commit": "2z8c9c49a5dc4a179243268e4bb6daa5",
        "repository": "git@github.com:conchair/conchair",
        "pr_number": "47",
    },
}


class TestBenchmarkRun:
    def test_roundtrip(self):
        run = BenchmarkRun(**run_json)
        assert run_json == run.to_publishable_dict()

    def test_warns_machine_cluster(self):
        with pytest.warns(UserWarning, match="Run not publishable!"):
            BenchmarkRun(
                machine_info={}, cluster_info={}, github=run_json["github"]
            ).to_publishable_dict()

        with pytest.warns(UserWarning, match="Run not publishable!"):
            BenchmarkRun(
                machine_info=None, cluster_info=None, github=run_json["github"]
            ).to_publishable_dict()

    def test_github_detection(self, monkeypatch):
        monkeypatch.setenv(
            "CONBENCH_PROJECT_REPOSITORY", run_json["github"]["repository"]
        )
        monkeypatch.setenv(
            "CONBENCH_PROJECT_PR_NUMBER", run_json["github"]["pr_number"]
        )
        monkeypatch.setenv("CONBENCH_PROJECT_COMMIT", run_json["github"]["commit"])
        assert BenchmarkRun().github == run_json["github"]

        monkeypatch.delenv("CONBENCH_PROJECT_REPOSITORY")
        monkeypatch.delenv("CONBENCH_PROJECT_PR_NUMBER")
        monkeypatch.delenv("CONBENCH_PROJECT_COMMIT")

        with pytest.warns(
            UserWarning,
            match="Both CONBENCH_PROJECT_REPOSITORY and CONBENCH_PROJECT_COMMIT must be set if `github` is not specified",
        ):
            BenchmarkRun()

            with pytest.raises(
                ValueError,
                match="Run not publishable! `github.repository` and `github.commit` must be populated",
            ):
                BenchmarkRun().to_publishable_dict()

    def test_host_detection(self, monkeypatch):
        machine_info_name = "fake-computer-name"
        monkeypatch.setenv("CONBENCH_MACHINE_INFO_NAME", machine_info_name)

        run = BenchmarkRun(github=run_json["github"])

        assert run.machine_info["name"] == machine_info_name
        assert run.machine_info["name"] != run_json["machine_info"]["name"]
