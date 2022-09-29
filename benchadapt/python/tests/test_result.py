import pytest

from benchadapt import BenchmarkResult

res_json = {
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
        "iterations": 3,
    },
    "tags": {
        "name": "very-real-benchmark",
        "suite": "dope-benchmarks",
        "source": "app-micro",
    },
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
    "context": {"benchmark_language": "A++"},
    "github": {
        "commit": "2z8c9c49a5dc4a179243268e4bb6daa5",
        "repository": "git@github.com:conchair/conchair",
    },
}


class TestBenchmarkResult:
    def test_roundtrip(self):
        res = BenchmarkResult(**res_json)
        assert res_json == res.to_publishable_dict()

    def test_warns_stats_error(self):
        with pytest.warns(UserWarning, match="Result not publishable!"):
            BenchmarkResult(stats={}, error={}).to_publishable_dict()

        with pytest.warns(UserWarning, match="Result not publishable!"):
            BenchmarkResult(stats=None, error=None).to_publishable_dict()

    def test_warns_machine_cluster(self):
        with pytest.warns(UserWarning, match="Result not publishable!"):
            BenchmarkResult(machine_info={}, cluster_info={}).to_publishable_dict()

        with pytest.warns(UserWarning, match="Result not publishable!"):
            BenchmarkResult(machine_info=None, cluster_info=None).to_publishable_dict()
