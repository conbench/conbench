import abc
import collections
import datetime
import gc
import statistics
import time
import uuid

import numpy as np

from .machine_info import language, machine_info
from .util import Connection


REGISTRY = []
LIST = []


def register_benchmark(cls):
    REGISTRY.append(cls)
    return cls


def register_list(cls):
    if not LIST:
        LIST.append(cls)
    return cls


def _now_formatted():
    now = datetime.datetime.now(datetime.timezone.utc)
    return now.isoformat()


class Benchmark(abc.ABC):
    @abc.abstractmethod
    def run(self, **kwargs):
        pass

    @property
    def cases(self):
        cases = getattr(self, "valid_cases", [])
        return cases[1:] if cases else []

    @property
    def fields(self):
        cases = getattr(self, "valid_cases", [])
        return cases[0] if cases else []

    @property
    def case_options(self):
        options = collections.defaultdict(set)
        fields, cases = self.fields, self.cases
        if not cases:
            return options
        for case in cases:
            for k, v in zip(fields, case):
                options[k].add(v)
        return options

    @property
    def case_ids(self):
        return [", ".join(case) for case in self.cases]

    def get_cases(self, case, options):
        run_all = options.get("all", False)
        return self.cases if run_all else [self._get_case(case, options)]

    def _get_case(self, case, options):
        if case is None:
            case = [options.get(c) for c in self.fields]
        case_tuples = [tuple(c) for c in self.cases]
        if tuple(case) not in case_tuples:
            invalid_case = dict(zip(self.fields, case))
            raise ValueError(f"Invalid case: {invalid_case}")
        return case


class BenchmarkList(abc.ABC):
    @abc.abstractmethod
    def list(self, classes):
        pass


class Conbench(Connection):
    def __init__(self):
        super().__init__()
        self.machine_info = machine_info(self.config.host_name)
        self.language = language()
        self.batch_id = uuid.uuid4().hex

    def benchmark(self, f, name, tags, context, run, options):
        iterations, gc_collect, gc_disable = self._get_options(options)
        if iterations < 1:
            raise ValueError(f"Invalid iterations: {iterations}")

        if gc_collect:
            gc.collect()
        if gc_disable:
            gc.disable()

        data, output = self._get_timing(f, iterations)

        gc.enable()

        context.update(self.language)
        tags["gc_collect"] = gc_collect
        tags["gc_disable"] = gc_disable

        # The benchmark measurement and execution time happen to be
        # the same in this case: both are execution time in seconds.
        # (since data == times, just record an empty list for times)
        result = {
            "data": data,
            "unit": "s",
            "times": [],
            "time_unit": "s",
        }

        benchmark, _ = self.record(
            result,
            name,
            tags,
            context,
            run,
            options,
        )

        return benchmark, output

    def record(self, result, name, tags, context, run, options, output=None):
        tags["name"] = name
        timestamp = _now_formatted()
        run_id = options.get("run_id")
        run_name = options.get("run_name")
        stats = self._stats(
            result["data"],
            result["unit"],
            result["times"],
            result["time_unit"],
            timestamp,
            run_id,
            run_name,
        )
        benchmark = {
            "stats": stats,
            "machine_info": self.machine_info,
            "context": context,
            "tags": tags,
            "run": run,
        }
        return benchmark, output

    def mark_new_batch(self):
        self.batch_id = uuid.uuid4().hex

    def _get_timing(self, f, iterations):
        times, output = [], None
        for _ in range(iterations):
            iteration_start = time.time()
            output = f()
            times.append(time.time() - iteration_start)
        return times, output

    def _get_options(self, options):
        gc_collect = options.get("gc_collect", True)
        gc_disable = options.get("gc_disable", True)
        iterations = options.get("iterations", 1)
        return iterations, gc_collect, gc_disable

    def _stats(self, data, unit, times, time_unit, timestamp, run_id, run_name):
        fmt = "{:.6f}"

        def _format(f, data, min_length=0):
            return fmt.format(f(data)) if len(data) > min_length else 0

        if not data:
            raise ValueError(f"Invalid data: {data}")

        q1, q3 = np.percentile(data, [25, 75])

        if not run_id:
            run_id = self.batch_id

        result = {
            "data": [fmt.format(x) for x in data],
            "times": [fmt.format(x) for x in times],
            "unit": unit,
            "time_unit": time_unit,
            "iterations": len(data),
            "timestamp": timestamp,
            "batch_id": self.batch_id,
            "run_id": run_id,
            "mean": _format(statistics.mean, data),
            "median": _format(statistics.median, data),
            "min": _format(min, data),
            "max": _format(max, data),
            "stdev": _format(statistics.stdev, data, min_length=2),
            "q1": fmt.format(q1),
            "q3": fmt.format(q3),
            "iqr": fmt.format(q3 - q1),
        }

        if run_name is not None:
            result["run_name"] = run_name

        return result
