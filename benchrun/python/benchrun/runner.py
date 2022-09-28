import abc
import copy
import gc
import multiprocessing as mp
import time
import warnings

from benchadapt import BenchmarkResult

from .cache import CacheManager


class Iteration(abc.ABC):
    """
    Abstract class defining how to run one iteration of a benchmark.
    """

    cache = None

    def __init__(self) -> None:
        self.cache = CacheManager()

    def setup(self, params: dict) -> dict:
        """
        Code to run in each iteration before timing. Results are passed to the
        ``setup_results`` param of ``iteration_run()``.
        """
        return {}

    @abc.abstractmethod
    def run(self, params: dict, setup_results: dict) -> dict:
        """Code to time. Results are passed to ``iteration_teardown()``"""

    def teardown(self, params: dict, run_results: dict) -> None:
        """Code to run in each iteration after timing"""
        pass

    def __call__(self, params: dict, settings: dict, queue: mp.Queue) -> float:
        if settings["drop_caches"]:
            self.cache.sync_and_drop()
        if settings["gc_collect"]:
            gc.collect()
        if settings["gc_disable"]:
            gc.disable()

        elapsed_time = None
        error = None
        try:
            setup_results = self.setup(params=params)
            start_time = time.time()
            run_results = self.run(params=params, setup_results=setup_results)
            end_time = time.time()
            self.teardown(params=params, run_results=run_results)
            elapsed_time = end_time - start_time
        except Exception as e:
            error = repr(e)
            warnings.warn(error)

        gc.enable()

        queue.put({"time": elapsed_time, "error": error})
        return elapsed_time


class Benchmark:
    """
    A class that takes an `Iteration` instance and runs it correctly for each case

    Parameters
    ----------
    iteration : Iteration
        An instance of `Iteration` defining code to benchmark
    drop_caches : bool
        Try to drop disk caches?
    gc_collect : bool
        Run garbage collection before timing code?
    gc_disable : bool
        Disable garbage collection during timing?
    error_handling : str
        What should happen if a benchmark errors out? Options: ``"stop"`` (skip future iterations
        and report only error), ``"break"`` (skip future iterations and report everything so far),
        ``"continue"`` (run all iterations even if they fail and report everything). As we currently
        can't report both metrics and errors for the same benchmark, ``"stop"`` and ``"break"`` are
        currently identical, and ``"continue"`` may run longer, but will report the same thing.
    """

    iteration = None
    settings = None
    cache = None

    def __init__(
        self,
        iteration: Iteration,
        drop_caches: bool = False,
        gc_collect: bool = True,
        gc_disable: bool = True,
        error_handling: str = "stop",
    ) -> None:
        assert error_handling in ["stop", "break", "continue"]

        self.iteration = iteration
        self.settings = {
            "drop_caches": drop_caches,
            "gc_collect": gc_collect,
            "gc_disable": gc_disable,
            "error_handling": error_handling,
        }

        self.cache = CacheManager()

    def run_iteration(self, params: dict) -> dict:
        iteration = copy.deepcopy(self.iteration)
        queue = mp.Queue()
        proc = mp.Process(target=iteration, args=(params, self.settings, queue))
        proc.start()
        res = queue.get()
        proc.join()
        return res

    def run_case(self, params: dict, iterations: int = 1) -> BenchmarkResult:

        times = []
        error = None
        for _ in range(iterations):
            res = self.run_iteration(params=params)
            if res["error"]:
                error = res["error"]

                if self.settings["error_handling"] in ["stop", "break"]:
                    break
            else:
                times.append(res["time"])

        if len(times) > 0:
            stats = {"data": times, "units": "s"}
        else:
            stats = None

        res = BenchmarkResult(
            stats=stats,
            error=error,
            context={"benchmark_language": "Python"},
        )

        return res
