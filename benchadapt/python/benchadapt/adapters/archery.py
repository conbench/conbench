import json
import tempfile
import uuid
from pathlib import Path
from typing import Any, Dict, List

from ..result import BenchmarkResult
from .gbench import GoogleBenchmark, GoogleBenchmarkAdapter


class ArcheryAdapter(GoogleBenchmarkAdapter):
    """A class for running Apache Arrow's archery benchmarks and sending the results to conbench"""

    def __init__(
        self,
        result_fields_override: Dict[str, Any] = None,
        result_fields_append: Dict[str, Any] = None,
    ) -> None:
        result_file = Path(tempfile.mktemp())
        super().__init__(
            command=["archery", "benchmark", "run", "--output", result_file],
            result_file=result_file,
            result_fields_override=result_fields_override,
            result_fields_append=result_fields_append,
        )

    def _transform_results(self) -> List[BenchmarkResult]:
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
    ) -> List[BenchmarkResult]:
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
