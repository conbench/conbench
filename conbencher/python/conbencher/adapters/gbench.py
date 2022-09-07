import datetime
import json
import uuid
from dataclasses import dataclass
from itertools import groupby
from tempfile import NamedTemporaryFile

from ..result import BenchmarkResult
from ._adapter import _BenchmarkAdapter


# adapted from https://github.com/apache/arrow/blob/master/dev/archery/archery/benchmark/google.py
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
    values: list[float]
    times: list[float]
    counters: list = None

    @classmethod
    def from_runs(cls, name: str, runs: list[GoogleBenchmarkObservation]):
        """
        Create a GoogleBenchmarkGroup instance from a list of observations

        Parameters
        ----------
        name: str
              Name of the benchmark
        runs: list(GoogleBenchmarkObservation)
              Repetitions of GoogleBenchmarkObservation run.
        """
        return cls(
            name=name,
            unit=runs[0].unit,
            time_unit=runs[0].time_unit,
            less_is_better=not runs[0].unit.endswith("per_second"),
            values=[b.value for b in runs],
            times=[b.real_time for b in runs],
        )


class GoogleBenchmarkAdapter(_BenchmarkAdapter):
    """A class for running Google Benchmarks and sending the results to conbench"""

    command = ["gbench", "benchmark", "run"]

    def __init__(self) -> None:
        self.result_file = NamedTemporaryFile().name
        self.command += ["--output", self.result_file]

        super().__init__()

    def transform_results(self) -> list[BenchmarkResult]:
        """Transform gbench results into a list of BenchmarkResult instances"""
        with open(self.result_file, "r") as f:
            raw_results = json.load(f)

        parsed_results = self._parse_results(results=raw_results, extra_tags={})

        return parsed_results

    def _parse_results(self, results: dict, extra_tags: dict) -> list[BenchmarkResult]:
        """Parse a blob of results from gbench into a list of `BenchmarkResult` instances"""
        # all results share a batch id
        batch_id = uuid.uuid4().hex
        gbench_context, benchmark_groups = self._parse_gbench_json(results)
        extra_tags["gbench_context"] = gbench_context

        parsed_results = []
        for benchmark in benchmark_groups:
            result_parsed = self._parse_benchmark(
                result=benchmark,
                batch_id=batch_id,
                extra_tags=extra_tags,
            )
            parsed_results.append(result_parsed)

        return parsed_results

    @staticmethod
    def _parse_gbench_json(raw_json: dict) -> tuple[dict, list]:
        """Parse gbench result json into a context dict and a list of grouped benchmarks"""
        gbench_context = raw_json.get("context")

        # Follow archery approach in ignoring aggregate results
        non_agg_benchmarks = [
            b for b in raw_json["benchmarks"] if b["run_type"] != "aggregate"
        ]

        benchmark_groups = groupby(
            sorted(non_agg_benchmarks, key=lambda x: x["name"]), lambda x: x["name"]
        )

        benchmarks = []
        for name, group in benchmark_groups:
            runs = [GoogleBenchmarkObservation(**obs) for obs in group]
            benchmarks.append(GoogleBenchmark.from_runs(name=name, runs=runs))

        return gbench_context, benchmarks

    def _parse_benchmark(
        self, result: GoogleBenchmark, batch_id: str, extra_tags: dict
    ) -> BenchmarkResult:
        """Parse a GoogleBenchmark instance into a `BenchmarkResult` instance"""
        name, tags = self._parse_benchmark_name(result.name)
        tags.update(extra_tags)

        res = BenchmarkResult(
            run_name=name,
            batch_id=batch_id,
            timestamp=datetime.datetime.now(datetime.timezone.utc).isoformat(),
            stats={
                "data": result.values,
                "unit": {
                    "bytes_per_second": "B/s",
                    "items_per_second": "i/s",
                }.get(result.unit, result.unit),
                "times": result.times,
                "time_unit": result.time_unit,
            },
            tags=tags,
            info={},
            context={"benchmark_language": "C++"},
        )

        return res

    @staticmethod
    def _parse_benchmark_name(full_name: str) -> tuple[str, dict[str, str]]:
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
