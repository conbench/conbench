import json
import uuid
from dataclasses import dataclass
from itertools import groupby
from pathlib import Path
from typing import Any, Dict, List, Tuple

from ..result import BenchmarkResult
from ._adapter import BenchmarkAdapter


# adapted from https://github.com/apache/arrow/blob/main/dev/archery/archery/benchmark/google.py
class GoogleBenchmarkObservation:
    """Represents one run of a single (google c++) benchmark.
    Aggregates are reported by Google Benchmark executables alongside
    other observations whenever repetitions are specified (with
    `--benchmark_repetitions` on the bare benchmark, or with the
    archery option `--repetitions`). Aggregate observations are not
    included in `GoogleBenchmark.runs`.
    RegressionSumKernel/32768/0                 1 us          1 us  25.8077GB/s
    RegressionSumKernel/32768/0                 1 us          1 us  25.7066GB/s
    RegressionSumKernel/32768/0                 1 us          1 us  25.1481GB/s
    RegressionSumKernel/32768/0                 1 us          1 us  25.846GB/s
    RegressionSumKernel/32768/0                 1 us          1 us  25.6453GB/s
    RegressionSumKernel/32768/0_mean            1 us          1 us  25.6307GB/s
    RegressionSumKernel/32768/0_median          1 us          1 us  25.7066GB/s
    RegressionSumKernel/32768/0_stddev          0 us          0 us  288.046MB/s
    """

    def __init__(
        self,
        name: str,
        real_time: float,
        cpu_time: float,
        time_unit: str,
        run_type: str,
        size=None,
        bytes_per_second: float = None,
        items_per_second: float = None,
        **counters: dict,
    ):
        self._name = name
        self.real_time = real_time
        self.cpu_time = cpu_time
        self.time_unit = time_unit
        self.run_type = run_type
        self.size = size
        self.bytes_per_second = bytes_per_second
        self.items_per_second = items_per_second
        self.counters = counters

    @property
    def is_aggregate(self):
        """Indicate if the observation is a run or an aggregate."""
        return self.run_type == "aggregate"

    @property
    def is_realtime(self):
        """Indicate if the preferred value is realtime instead of cputime."""
        return self.name.find("/real_time") != -1

    @property
    def name(self):
        name = self._name
        return name.rsplit("_", maxsplit=1)[0] if self.is_aggregate else name

    @property
    def time(self):
        return self.real_time if self.is_realtime else self.cpu_time

    @property
    def value(self):
        """Return the benchmark value."""
        return self.bytes_per_second or self.items_per_second or self.time

    @property
    def unit(self):
        if self.bytes_per_second:
            return "bytes_per_second"
        elif self.items_per_second:
            return "items_per_second"
        else:
            return self.time_unit


@dataclass
class GoogleBenchmark:
    """A set of GoogleBenchmarkObservations."""

    name: str
    unit: str
    time_unit: str
    less_is_better: bool
    values: List[float]
    times: List[float]
    counters: List = None

    @classmethod
    def from_runs(cls, runs: List[GoogleBenchmarkObservation]):
        """
        Create a GoogleBenchmarkGroup instance from a list of observations

        Parameters
        ----------
        runs: List(GoogleBenchmarkObservation)
              Repetitions of GoogleBenchmarkObservation run.
        """
        return cls(
            name=runs[0].name,
            unit=runs[0].unit,
            time_unit=runs[0].time_unit,
            less_is_better=not runs[0].unit.endswith("per_second"),
            values=[b.value for b in runs],
            times=[b.real_time for b in runs],
        )


class GoogleBenchmarkAdapter(BenchmarkAdapter):
    """A class for running Google Benchmarks and sending the results to conbench"""

    def __init__(
        self,
        command: List[str],
        result_file: Path,
        result_fields_override: Dict[str, Any] = None,
        result_fields_append: Dict[str, Any] = None,
    ) -> None:
        """
        Parameters
        ----------
        command : List[str]
            A list of strings defining a shell command to run the benchmarks
        result_file : Path
            The path to a file of benchmark results that will be generated when ``.run()`` is called
        result_fields_override : Dict[str, Any]
            A dict of values to override on each instance of `BenchmarkResult`. Useful
            for specifying metadata only available at runtime, e.g. build info. Applied
            before ``results_field_append``.
        results_fields_append : Dict[str, Any]
            A dict of default values to be appended to `BenchmarkResult` values after
            instantiation. Useful for appending extra tags or other metadata in addition
            to that gathered elsewhere. Only applicable for dict attributes. For each
            element, will override any keys that already exist, i.e. it does not append
            recursively.
        """
        self.result_file = Path(result_file)
        super().__init__(
            command=command,
            result_fields_override=result_fields_override,
            result_fields_append=result_fields_append,
        )

    def _transform_results(self) -> List[BenchmarkResult]:
        """Transform gbench results into a list of BenchmarkResult instances"""
        with open(self.result_file, "r") as f:
            raw_results = json.load(f)

        parsed_results = self._parse_results(results=raw_results, extra_tags={})

        return parsed_results

    def _parse_results(self, results: dict, extra_tags: dict) -> List[BenchmarkResult]:
        """Parse a blob of results from gbench into a list of `BenchmarkResult` instances"""
        gbench_context, benchmark_groups = self._parse_gbench_json(results)

        parsed_results = []
        for name, benchmark in benchmark_groups.items():
            for case in benchmark["cases"]:
                result_parsed = self._parse_benchmark(
                    result=case,
                    batch_id=benchmark["batch_id"],
                    extra_tags=extra_tags,
                )
                result_parsed.optional_benchmark_info = {
                    "gbench_context": gbench_context
                }
                parsed_results.append(result_parsed)

        return parsed_results

    def _parse_gbench_json(self, raw_json: dict) -> Tuple[dict, dict]:
        """
        Parse gbench result json into a context dict and a list of grouped benchmarks

        See https://github.com/google/benchmark/blob/main/docs/user_guide.md#output-formats
        for a (very minimal!) example of gbench output json. This method splits out
        the `context` attribute, which "contains information about the run in general,
        including information about the CPU and the date" from the `benchmarks` one, which
        contains a dict for all benchmarks in the run.

        Aggregate benchmarks are excluded, as they are duplicative of the raw benchmarks.

        Structure of returns:

        `gbench_context`: The `context` dict of gbench context, unedited.
        `benchmarks`: {
            <benchmark name>: {
                "batch_id": <uuid>,
                "cases": List[GoogleBenchmark]
            },
            ...
        }
        """
        gbench_context = raw_json.get("context")

        # Follow archery approach in ignoring aggregate results
        non_agg_benchmarks = [
            b for b in raw_json["benchmarks"] if b["run_type"] != "aggregate"
        ]

        benchmarks = {}
        benchmark_groups = groupby(
            sorted(non_agg_benchmarks, key=lambda x: x["name"]),
            lambda x: self._parse_benchmark_name(full_name=x["name"])[0],
        )
        # set one `batch_id` for all cases that share a benchmark name
        for bm_name, group in benchmark_groups:
            benchmarks[bm_name] = {"batch_id": uuid.uuid4().hex, "cases": []}
            benchmark_cases = groupby(
                sorted(group, key=lambda x: x["name"]), lambda x: x["name"]
            )
            # collapse all iterations for a benchmark case
            for _, case in benchmark_cases:
                iterations = [GoogleBenchmarkObservation(**obs) for obs in case]
                benchmarks[bm_name]["cases"].append(
                    GoogleBenchmark.from_runs(runs=iterations)
                )

        return gbench_context, benchmarks

    def _parse_benchmark(
        self, result: GoogleBenchmark, batch_id: str, extra_tags: dict
    ) -> BenchmarkResult:
        """Parse a GoogleBenchmark instance into a `BenchmarkResult` instance"""
        name, tags = self._parse_benchmark_name(result.name)
        tags["name"] = name
        tags.update(extra_tags)

        res = BenchmarkResult(
            batch_id=batch_id,
            stats={
                "data": result.values,
                "unit": {
                    "bytes_per_second": "B/s",
                    "items_per_second": "i/s",
                }.get(result.unit, result.unit),
                "times": result.times,
                "time_unit": result.time_unit,
                "iterations": len(result.values),
            },
            tags=tags,
            info={},
            context={"benchmark_language": "C++"},
        )

        return res

    @staticmethod
    def _parse_benchmark_name(full_name: str) -> Tuple[str, Dict[str, str]]:
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
