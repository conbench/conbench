import datetime
import json
import uuid
from itertools import groupby

from ..result import BenchmarkResult
from ._runner import _BenchmarkRunner


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


class GoogleBenchmarkGroup:
    """A set of GoogleBenchmarkObservations."""

    def __init__(self, name, runs):
        """Initialize a GoogleBenchmarkGroup.
        Parameters
        ----------
        name: str
              Name of the benchmark
        runs: list(GoogleBenchmarkObservation)
              Repetitions of GoogleBenchmarkObservation run.
        """
        self.name = name
        self.runs = runs
        self.unit = self.runs[0].unit
        self.time_unit = self.runs[0].time_unit
        self.less_is_better = not self.unit.endswith("per_second")
        self.values = [b.value for b in self.runs]
        self.times = [b.real_time for b in self.runs]
        # Slight kludge to extract the UserCounters for each benchmark
        self.counters = self.runs[0].counters


class GoogleBenchmarkRunner(_BenchmarkRunner):
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
        # all results share a batch id
        batch_id = uuid.uuid4().hex
        gbench_context, benchmark_groups = self.parse_gbench_json(results)

        parsed_results = []
        for benchmark in benchmark_groups:
            result_parsed = self._parse_benchmark(
                result=benchmark,
                gbench_context=gbench_context,
                batch_id=batch_id,
                extra_tags=extra_tags,
            )
            parsed_results.append(result_parsed)

        return parsed_results

    def _parse_benchmark(
        self, result: list, gbench_context: dict, batch_id: str, extra_tags: dict
    ) -> BenchmarkResult:
        """Parse a group of gbench json benchmark results into a `BenchmarkResult` instance"""
        name, tags = _parse_benchmark_name(result.name)
        if extra_tags:
            tags.update(extra_tags)
        if gbench_context:
            tags["gbench_context"] = gbench_context

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
    def parse_gbench_json(raw_json: dict) -> tuple[dict, list]:
        """Parse gbench result json into a context dict and a list of grouped benchmarks"""
        gbench_context = raw_json.get("context")

        non_agg_benchmarks = [
            b for b in raw_json["benchmarks"] if b["run_type"] != "aggregate"
        ]

        benchmark_groups = groupby(
            sorted(non_agg_benchmarks, key=lambda x: x["name"]), lambda x: x["name"]
        )

        benchmarks = []
        for name, group in benchmark_groups:
            runs = [GoogleBenchmarkObservation(**obs) for obs in group]
            benchmarks.append(GoogleBenchmarkGroup(name=name, runs=runs))

        return gbench_context, benchmarks
