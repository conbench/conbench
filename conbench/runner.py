import abc
import collections
import datetime
import functools
import gc
import statistics
import subprocess
import time
import traceback
import uuid

import numpy as np

from .machine_info import github_info, machine_info, python_info, r_info
from .util import Connection

REGISTRY = []
LIST = []


LANG = "benchmark_language"
LANG_VERSION = "benchmark_language_version"


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
            Free-text name of run (commit ABC, pull request 123, etc).
        run_reason : str, optional
            Reason for run (commit, pull request, manual, etc). Probably will be used
            to group runs, so try to keep the cardinality low.
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
            case = []
            for i, c in enumerate(self.fields):
                pick = self.cases[0][i]
                if isinstance(pick, bool):
                    case.append(options.get(c).lower() in ["True", "true"])
                else:
                    t = type(self.cases[0][i])
                    case.append(t(options.get(c)))
        case_tuples = [tuple(c) for c in self.cases]
        if tuple(case) not in case_tuples:
            invalid_case = dict(zip(self.fields, case))
            raise ValueError(f"Invalid case: {invalid_case}")
        return case


class BenchmarkList(abc.ABC):
    @abc.abstractmethod
    def list(self, classes):
        pass


class MixinPython:
    @functools.cached_property
    def python_info(self):
        return python_info()

    def set_python_info_and_context(self, info, context):
        lang = self.python_info
        info.update({LANG_VERSION: lang[LANG_VERSION]})
        context.update({LANG: lang[LANG]})

    def benchmark(self, f, name, publish=True, **kwargs):
        """Benchmark a function and publish the result."""
        (
            tags,
            optional_benchmark_info,
            context,
            info,
            github,
            options,
            cluster_info,
            _,
        ) = self._init(kwargs)
        self.set_python_info_and_context(info, context)

        timing_options = self._get_timing_options(options)
        iterations = timing_options.pop("iterations")
        if iterations < 1:
            raise ValueError(f"Invalid iterations: {iterations}")

        try:
            data, output = self._get_timing(f, iterations, timing_options)
            benchmark, _ = self.record(
                {"data": data, "unit": "s"},
                name,
                tags=tags,
                optional_benchmark_info=optional_benchmark_info,
                context=context,
                info=info,
                github=github,
                options=options,
                cluster_info=cluster_info,
                publish=False,
            )
        except Exception as e:
            error = {"stack_trace": traceback.format_exc()}
            benchmark, _ = self.record(
                None,
                name,
                tags=tags,
                optional_benchmark_info=optional_benchmark_info,
                context=context,
                info=info,
                github=github,
                options=options,
                cluster_info=cluster_info,
                error=error,
                publish=False,
            )
            raise e
        finally:
            if publish:
                self.publish(benchmark)

        return benchmark, output


class MixinR:
    @functools.cached_property
    def r_info(self):
        return r_info()

    def get_r_info_and_context(self):
        lang = self.r_info
        info = {LANG_VERSION: lang[LANG_VERSION]}
        context = {LANG: lang[LANG]}
        return info, context

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


class Conbench(Connection, MixinPython, MixinR):
    def __init__(self):
        super().__init__()
        self._run_id = uuid.uuid4().hex
        self._batch_id = uuid.uuid4().hex
        self._drop_caches_failed = False
        self._purge_failed = False

    @functools.cached_property
    def github_info(self):
        return github_info()

    @functools.cached_property
    def machine_info(self):
        return machine_info(self.config.host_name)

    def record(self, result, name, error=None, publish=True, **kwargs):
        """Record and publish an external benchmark result."""
        (
            tags,
            optional_benchmark_info,
            context,
            info,
            github,
            options,
            cluster_info,
            output,
        ) = self._init(kwargs)

        tags["name"] = name

        batch_id = options.get("batch_id")
        if not batch_id:
            batch_id = self._batch_id

        run_id = options.get("run_id")
        if not run_id:
            run_id = self._run_id

        benchmark = {
            "run_id": run_id,
            "batch_id": batch_id,
            "timestamp": _now_formatted(),
            "context": context,
            "info": info,
            "tags": tags,
            "optional_benchmark_info": optional_benchmark_info,
            "github": github,
        }
        if error:
            benchmark["error"] = error
        else:
            benchmark["stats"] = self._stats(
                result["data"],
                result["unit"],
                result.get("times", []),
                result.get("time_unit", "s"),
            )

        if cluster_info:
            benchmark["cluster_info"] = cluster_info
        else:
            benchmark["machine_info"] = self.machine_info

        run_name = options.get("run_name")
        if run_name is not None:
            benchmark["run_name"] = run_name

        run_reason = options.get("run_reason")
        if run_reason is not None:
            benchmark["run_reason"] = run_reason

        if publish:
            self.publish(benchmark)
        return benchmark, output

    def get_run_id(self, options):
        run_id = options.get("run_id")
        return run_id if run_id else self._run_id

    def mark_new_batch(self):
        self._batch_id = uuid.uuid4().hex

    def manually_batch(self, batch_id):
        self._batch_id = batch_id

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
        optional_benchmark_info = kwargs.get("optional_benchmark_info", {})
        context = kwargs.get("context", {})
        info = kwargs.get("info", {})
        github = kwargs.get("github", {})
        options = kwargs.get("options", {})
        cluster_info = kwargs.get("cluster_info", {})
        github = github if github else self.github_info
        return (
            tags,
            optional_benchmark_info,
            context,
            info,
            github,
            options,
            cluster_info,
            kwargs.get("output"),
        )

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
