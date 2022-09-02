import datetime
import json
import uuid

from ..result import BenchmarkResult
from ._runner import _BenchmarkRunner


class GbenchRunner(_BenchmarkRunner):
    result_file = "gbench-results.json"
    command = ["gbench", "benchmark", "run", "--output", result_file]

    def transform_results(self) -> list[BenchmarkResult]:
        """Transform gbench results into a list of BenchmarkResult instances"""
        with open(self.result_file, "r") as f:
            raw_results = json.load(f)

        parsed_results = self._parse_results(raw_results)

        return parsed_results

    def _parse_results(
        self, results: dict, extra_tags: dict = None
    ) -> list[BenchmarkResult]:
        """Parse a blob of results from gbench into a list of `BenchmarkResult` instances"""
        batch_id = uuid.uuid4().hex
        gbench_context = results.get("context")
        parsed_results = []
        for result in results["benchmarks"]:
            result_parsed = self._parse_benchmark(
                result=result,
                gbench_context=gbench_context,
                batch_id=batch_id,
                extra_tags=extra_tags,
            )
            parsed_results.append(result_parsed)

        return parsed_results

    def _parse_benchmark(
        self, result: dict, gbench_context: dict, batch_id: str, extra_tags: dict
    ) -> BenchmarkResult:
        """Parse a gbench json benchmark result into a `BenchmarkResult` instance"""
        name, tags = self._parse_benchmark_name(result["name"])
        if extra_tags:
            tags.update(extra_tags)
        if gbench_context:
            tags["gbench_contex"] = gbench_context

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

    def _parse_benchmark_name(self, full_name: str) -> tuple[str, dict[str, str]]:
        """Split gbench name into benchmark name and tags"""
        parts = full_name.split("/", 1)
        name, params = parts[0], ""
        if len(parts) == 2:
            params = parts[1]

        parts = name.split("<", 1)
        if len(parts) == 2:
            if params:
                name, params = parts[0], f"<{parts[1]}/{params}"
            else:
                name, params = parts[0], f"<{parts[1]}"

        tags = {}
        if params:
            tags["params"] = params

        return name, tags
