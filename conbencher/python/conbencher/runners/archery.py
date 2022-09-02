import datetime
import json
import uuid

from ..result import BenchmarkResult
from .gbench import _parse_benchmark_name
from ._runner import _BenchmarkRunner


class ArcheryRunner(_BenchmarkRunner):
    result_file = "archery-results.json"
    command = ["archery", "benchmark", "run", "--output", result_file]

    def transform_results(self) -> list[BenchmarkResult]:
        """Transform archery results into a list of BenchmarkResult instances"""
        with open(self.result_file, "r") as f:
            raw_results = json.load(f)

        parsed_results = []
        for suite in raw_results["suites"]:
            parsed_results += self._parse_results(
                results=suite,
                extra_tags={"suite": suite["name"], "source": "cpp-micro"},
            )

        return parsed_results

    def _parse_results(
        self, results: dict, extra_tags: dict = None
    ) -> list[BenchmarkResult]:
        """Parse a blob of results from archery into a list of `BenchmarkResult` instances"""
        # all results share a batch id
        batch_id = uuid.uuid4().hex

        parsed_results = []
        for result in results["benchmarks"]:
            result_parsed = self._parse_benchmark(
                result=result,
                batch_id=batch_id,
                extra_tags=extra_tags,
            )
            parsed_results.append(result_parsed)

        return parsed_results

    def _parse_benchmark(
        self, result: dict, batch_id: str, extra_tags: dict
    ) -> BenchmarkResult:
        """Parse an archery json benchmark result into a `BenchmarkResult` instance"""
        name, tags = _parse_benchmark_name(result["name"])
        if extra_tags:
            tags.update(extra_tags)

        res = BenchmarkResult(
            run_name=name,
            batch_id=batch_id,
            timestamp=datetime.datetime.now(datetime.timezone.utc).isoformat(),
            stats={
                "data": result["values"],
                "unit": {
                    "bytes_per_second": "B/s",
                    "items_per_second": "i/s",
                }.get(result["unit"], result["unit"]),
                "times": result["times"],
                "time_unit": result.get("time_unit", "s"),
            },
            tags=tags,
            info={},
            context={"benchmark_language": "C++"},
        )

        return res
