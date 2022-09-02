import json

from ..result import BenchmarkResult
from .gbench import GbenchRunner


class ArcheryRunner(GbenchRunner):
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
