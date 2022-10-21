from typing import Generator

from benchadapt.adapters import GeneratorAdapter

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


def fake_generator(**kwargs) -> Generator[BenchmarkResult, None, None]:
    for _ in range(2):
        yield BenchmarkResult(**res_json)


class TestGeneratorAdapter:
    def test_init(self) -> None:
        adapter = GeneratorAdapter(generator=fake_generator)
        assert adapter.generator == fake_generator
        assert adapter.result_fields_append == {}
        assert adapter.result_fields_override == {}
        assert adapter.command == []

    def test_transform_results(self) -> None:
        adapter = GeneratorAdapter(generator=fake_generator)
        assert adapter.results is None
        adapter.results = [next(fake_generator())]
        assert adapter.transform_results(run_id=res_json["run_id"]) == [
            next(fake_generator())
        ]

    def test_run(self) -> None:
        adapter = GeneratorAdapter(generator=fake_generator)
        for run, original in zip(adapter.run(), fake_generator()):
            assert run == [original]

    def test_result_fields(self) -> None:
        adapter = GeneratorAdapter(
            generator=fake_generator,
            result_fields_append={"tags": {"price": "$14.99"}},
            result_fields_override={"run_name": "fun run"},
        )
        for res_list in adapter.run():
            assert res_list[0].tags["price"] == "$14.99"
            assert res_list[0].run_name == "fun run"
