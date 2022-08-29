import json
import uuid

from ..result import BenchmarkResult
from ._runner import _BenchmarkRunner


class GbenchRunner(_BenchmarkRunner):
    result_file = "gbench-results.json"
    command = ["gbench", "benchmark", "run", "--output", result_file]

    def transform_results(self) -> list[BenchmarkResult]:
        with open(self.result_file, "r") as f:
            raw_results = json.load(f)

        parsed_results = []
        for suite in raw_results["suite"]:
            batch_id = uuid.uuid4().hex
            for result in suite["benchmarks"]:
                name, tags = self._parse_benchmark_name(result["name"])
                tags["suite"] = suite["name"]
                tags["source"] = "cpp-micro"

                res = BenchmarkResult(
                    name=name,
                    batch_id=batch_id,
                    stats={},  # TODO
                    params={},  # TODO
                    tags=tags,
                    info={},
                    machine_info={},  # TODO
                    context={"benchmark_language": "C++"},
                    github={},  # TODO
                    options={},  # TODO
                    output="",  # TODO
                )
                parsed_results.append(res)

        return parsed_results

    def _parse_benchmark_name(full_name):
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
