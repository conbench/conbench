import json
import uuid

from ..result import BenchmarkResult
from .gbench import GoogleBenchmark, GoogleBenchmarkRunner


class ArcheryRunner(GoogleBenchmarkRunner):
    """A class for running Apache Arrow's archery benchmarks and sending the results to conbench"""

    command = ["archery", "benchmark", "run"]

    def transform_results(self) -> list[BenchmarkResult]:
        """Transform archery results into a list of BenchmarkResult instances"""
        with open(self.result_file, "r") as f:
            raw_results = json.load(f)

        parsed_results = []
        for suite in raw_results["suites"]:
            parsed_results += self._parse_suite(
                results=suite,
                extra_tags={"suite": suite["name"], "source": "cpp-micro"},
            )

        return parsed_results

    def _parse_suite(
        self, results: dict, extra_tags: dict = None
    ) -> list[BenchmarkResult]:
        """Parse a blob of results from archery into a list of `BenchmarkResult` instances"""
        # all results share a batch id
        batch_id = uuid.uuid4().hex

        parsed_results = []
        for result in results["benchmarks"]:
            result_parsed = self._parse_benchmark(
                result=GoogleBenchmark(**result),
                batch_id=batch_id,
                extra_tags=extra_tags,
            )
            parsed_results.append(result_parsed)

        return parsed_results
