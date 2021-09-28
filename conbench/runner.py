import abc
import collections
import datetime
import functools
import gc
import statistics
import subprocess
import time
import uuid

import numpy as np

from .machine_info import github_info, machine_info, python_info, r_info
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
    def __init__(self):
        self.conbench = Conbench()

    @abc.abstractmethod
    def run(self, **kwargs):
        """
        Parameters
        ----------
        all : boolean, optional
            Run all benchmark cases.
        case : sequence, optional
            Benchmark options sequence (rather than individual params):
            [<option1>, <option2>, ..., <option3>]
        iterations : int, default 1
            Number of times to run the benchmark.
        drop_caches : boolean, default False
            Whether to drop caches before each benchmark run.
        gc_collect : boolean, default True
            Whether to do garbage collection before each benchmark run.
        gc_disable : boolean, default True
            Whether to do disable collection during each benchmark run.
        run_id : str, optional
            Group executions together with a run id.
        run_name : str, optional
            Name of run (commit, pull request, etc).
        Returns
        -------
        (result, output) : sequence
            result : The benchmark result.
            output : The output from the benchmarked function.
        """
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
        return [", ".join([str(c) for c in case]) for case in self.cases]

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
        self.batch_id = uuid.uuid4().hex
        self._drop_caches_failed = False
        self._purge_failed = False

    @functools.cached_property
    def python_info(self):
        return python_info()

    @functools.cached_property
    def r_info(self):
        return r_info()

    @functools.cached_property
    def github_info(self):
        return github_info()

    @functools.cached_property
    def machine_info(self):
        return machine_info(self.config.host_name)

    def benchmark(self, f, name, publish=True, **kwargs):
        """Benchmark a function and publish the result."""
        tags, context, github, options, _ = self._init(kwargs)

        timing_options = self._get_timing_options(options)
        iterations = timing_options.pop("iterations")
        if iterations < 1:
            raise ValueError(f"Invalid iterations: {iterations}")

        data, output = self._get_timing(f, iterations, timing_options)
        context.update(self.python_info)
        benchmark, _ = self.record(
            {"data": data, "unit": "s"},
            name,
            tags=tags,
            context=context,
            github=github,
            options=options,
            publish=False,
        )
        if publish:
            self.publish(benchmark)
        return benchmark, output

    def record(self, result, name, publish=True, **kwargs):
        """Record and publish an external benchmark result."""
        tags, context, github, options, output = self._init(kwargs)

        tags["name"] = name
        stats = self._stats(
            result["data"],
            result["unit"],
            result.get("times", []),
            result.get("time_unit", "s"),
        )

        batch_id = options.get("batch_id")
        if batch_id:
            self.batch_id = batch_id

        run_id = options.get("run_id")
        if run_id is None:
            run_id = self.batch_id

        benchmark = {
            "run_id": run_id,
            "batch_id": self.batch_id,
            "timestamp": _now_formatted(),
            "stats": stats,
            "machine_info": self.machine_info,
            "context": context,
            "tags": tags,
            "github": github,
        }

        run_name = options.get("run_name")
        if run_name is not None:
            benchmark["run_name"] = run_name

        if publish:
            self.publish(benchmark)
        return benchmark, output

    def mark_new_batch(self):
        self.batch_id = uuid.uuid4().hex

    def sync_and_drop_caches(self):
        if not self._drop_caches_failed:
            command = "sync; echo 3 | sudo tee /proc/sys/vm/drop_caches"
            try:
                subprocess.check_output(command, shell=True)
                return True
            except subprocess.CalledProcessError:
                self._drop_caches_failed = True

        if not self._purge_failed:
            command = "sync; sudo purge"
            try:
                subprocess.check_output(command, shell=True)
                return True
            except subprocess.CalledProcessError:
                self._purge_failed = True

        return False

    def _init(self, kwargs):
        tags = kwargs.get("tags", {})
        context = kwargs.get("context", {})
        github = kwargs.get("github", {})
        options = kwargs.get("options", {})
        github = github if github else self.github_info
        return tags, context, github, options, kwargs.get("output")

    def _get_timing(self, f, iterations, options):
        times, output = [], None

        for _ in range(iterations):
            if options["drop_caches"]:
                self.sync_and_drop_caches()
            if options["gc_collect"]:
                gc.collect()
            if options["gc_disable"]:
                gc.disable()

            if output is not None:
                # We only need output from the final run.
                # For other runs delete before we run the next
                # iteration to avoid doubling memory
                del output

            iteration_start = time.time()
            output = f()
            times.append(time.time() - iteration_start)

            gc.enable()

        return times, output

    def _get_timing_options(self, options):
        return {
            "gc_collect": options.get("gc_collect", True),
            "gc_disable": options.get("gc_disable", True),
            "drop_caches": options.get("drop_caches", False),
            "iterations": options.get("iterations", 1),
        }

    @staticmethod
    def _stats(data, unit, times, time_unit):
        fmt = "{:.6f}"

        def _format(f, data, min_length=0):
            return fmt.format(f(data)) if len(data) > min_length else 0

        if not data:
            raise ValueError(f"Invalid data: {data}")

        q1, q3 = np.percentile(data, [25, 75])

        result = {
            "data": [fmt.format(x) for x in data],
            "times": [fmt.format(x) for x in times],
            "unit": unit,
            "time_unit": time_unit,
            "iterations": len(data),
            "mean": _format(statistics.mean, data),
            "median": _format(statistics.median, data),
            "min": _format(min, data),
            "max": _format(max, data),
            "stdev": _format(statistics.stdev, data, min_length=2),
            "q1": fmt.format(q1),
            "q3": fmt.format(q3),
            "iqr": fmt.format(q3 - q1),
        }

        return result

    def execute_r_command(self, r_command, quiet=True):
        if quiet:
            command = ["R", "-s", "-q", "-e", r_command]
        else:
            command = ["R", "-e", r_command]
        result = subprocess.run(command, capture_output=True)
        output = result.stdout.decode("utf-8").strip()
        error = result.stderr.decode("utf-8").strip()
        if result.returncode != 0:
            raise Exception(error)
        return output, error
