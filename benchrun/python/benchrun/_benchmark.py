import abc
import copy
import gc
import multiprocessing as mp
import time
import uuid
import warnings
from typing import Any, Dict, List

from benchadapt import BenchmarkResult

from .cache import CacheManager
from .case import CaseList


class Iteration(abc.ABC):
    """
    Abstract class defining how to run one iteration of a benchmark.

    Attributes
    ----------

    name : str
        A name for the benchmark. Should be specified when inheriting.
    cache : CacheManager
        An CacheManager instance for clearing the disk cache when specified.
        Do not mess with this.
    """

    name: str
    cache = None

    def __init__(self) -> None:
        self.cache = CacheManager()

    def setup(self, case: dict) -> dict:
        """
        Code to run in each iteration before timing.

        Parameters
        ----------
        case : dict
            A dict where keys are parameters and values are scalar arguments for a benchmark

        Returns
        -------
        A dict passed to the ``setup_results`` param of ``run()`` when the class is called.
        """
        return {}

    @abc.abstractmethod
    def run(self, case: dict, setup_results: dict) -> dict:
        """
        Code to time.

        Parameters
        ----------
        case : dict
            A dict where keys are parameters and values are scalar arguments for a benchmark
        setup_results : dict
            The results of calling ``setup()``. Use for passing data between stages.

        Returns
        -------
        A dict passed to the ``run_results`` param of ``teardown()`` when the class is called.
        """

    def teardown(self, case: dict, run_results: dict) -> None:
        """
        Code to run in each iteration after timing.

        Parameters
        ----------
        case : dict
            A dict where keys are parameters and values are scalar arguments for a benchmark
        run_results : dict
            The results of calling ``run()``. Use for passing data between stages.
        """
        pass

    def __call__(self, case: dict, settings: dict, queue: mp.Queue) -> float:
        """
        Run all stages and return a time.

        Parameters
        ----------
        case : dict
            A dict where keys are parameters and values are scalar arguments for a benchmark
        settings : dict
            A dict containing keys ``drop_caches``, ``gc_collect``, and ``gc_disable`` with bool values.
        queue : multiprocessing.Queue
            An instance of `multiprocessing.Queue` used for sending data back to a parent process.
        """

        if settings["drop_caches"]:
            self.cache.sync_and_drop()
        if settings["gc_collect"]:
            gc.collect()
        if settings["gc_disable"]:
            gc.disable()

        elapsed_time = None
        error = None
        try:
            setup_results = self.setup(case=case)
            start_time = time.time()
            run_results = self.run(case=case, setup_results=setup_results)
            end_time = time.time()
            self.teardown(case=case, run_results=run_results)
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
    case_list : CaseList
        An instance of `CaseList` defining a list of valid cases for which to run this benchmark.
    results_fields_append : Dict[str, Any]
        A dict of values to be appended to `BenchmarkResult` values after
        instantiation. Useful for appending extra tags or other metadata in addition
        to that gathered elsewhere. Only applicable for dict attributes. For each
        element, will override any keys that already exist, i.e. it does not append
        recursively.

        In most cases, should be set on the adapter, not here, but can be set here to
        specify benchmark-dependent values like appending a tag for ``suite``.
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

    iteration: Iteration = None
    case_list: CaseList = None
    result_fields_append: Dict[str, Any] = None
    settings = None
    cache = None

    def __init__(
        self,
        iteration: Iteration,
        case_list: CaseList,
        result_fields_append: Dict[str, Any] = {},
        drop_caches: bool = False,
        gc_collect: bool = True,
        gc_disable: bool = True,
        error_handling: str = "stop",
    ) -> None:
        assert error_handling in ["stop", "break", "continue"]

        self.iteration = iteration
        self.case_list = case_list
        self.result_fields_append = result_fields_append or {}
        self.settings = {
            "drop_caches": drop_caches,
            "gc_collect": gc_collect,
            "gc_disable": gc_disable,
            "error_handling": error_handling,
        }
        self.cache = CacheManager()

    def run_iteration(self, case: dict) -> dict:
        iteration = copy.deepcopy(self.iteration)
        queue = mp.Queue()
        proc = mp.Process(target=iteration, args=(case, self.settings, queue))
        proc.start()
        res = queue.get()
        proc.join()
        return res

    def run_case(
        self,
        case: dict,
        iterations: int,
        run_reason: str,
        run_name: str,
        run_id: str,
        batch_id: str,
    ) -> BenchmarkResult:

        times = []
        error = None
        for _ in range(iterations):
            res = self.run_iteration(case=case)
            if res["error"]:
                error = res["error"]

                if self.settings["error_handling"] in ["stop", "break"]:
                    break
            else:
                times.append(res["time"])

        if len(times) > 0:
            stats = {"data": times, "units": "s", "iterations": iterations}
        else:
            stats = None

        res = BenchmarkResult(
            run_name=run_name,
            run_id=run_id,
            batch_id=batch_id,
            run_reason=run_reason,
            stats=stats,
            error=error,
            tags={"name": self.iteration.name, **case},
            # info={},  # TODO: is there common detectable metadata worth putting here?
            context={"benchmark_language": "Python"},
        )

        for param in self.result_fields_append:
            setattr(
                res,
                param,
                {**getattr(res, param), **self.result_fields_append[param]},
            )

        return res

    def run(
        self,
        run_reason: str,
        run_id: str,
        run_name: str = None,
        batch_id: str = None,
        iterations: int = 1,
    ) -> List[BenchmarkResult]:
        batch_id = batch_id or uuid.uuid4().hex

        result_list = [
            self.run_case(
                case=case,
                iterations=iterations,
                run_reason=run_reason,
                run_name=run_name,
                run_id=run_id,
                batch_id=batch_id,
            )
            for case in self.case_list.case_list
        ]

        return result_list
