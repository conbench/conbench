import abc
import copy
import gc
import multiprocessing as mp
import time
import traceback
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
        A CacheManager instance for clearing the disk cache when specified.
        Do not mess with this.
    env : dict
        A dict stages can use to pass data between them.
    """

    name: str
    cache = None
    env: dict = None

    def __init__(self) -> None:
        assert self.name
        self.cache = CacheManager()
        self.env = {}

    def setup(self, case: dict) -> None:
        """
        Global setup that runs once before any iteration.
        """
        pass

    def before_each(self, case: dict) -> None:
        """
        Code to run in each iteration before timing.

        Parameters
        ----------
        case : dict
            A dict where keys are parameters and values are scalar arguments for a benchmark
        """
        pass

    @abc.abstractmethod
    def run(self, case: dict) -> None:
        """
        Code to time.

        Parameters
        ----------
        case : dict
            A dict where keys are parameters and values are scalar arguments for a benchmark
        """

    def after_each(self, case: dict) -> None:
        """
        Code to run in each iteration after timing.

        Parameters
        ----------
        case : dict
            A dict where keys are parameters and values are scalar arguments for a benchmark
        """
        pass

    def teardown(self, case: dict) -> None:
        """Global teardown that runs once after all iterations"""
        pass

    def __call__(
        self, case: dict, iterations: int, settings: dict, queue: mp.Queue
    ) -> dict:
        """
        Run iterations and return list of times.

        Parameters
        ----------
        case : dict
            A dict where keys are parameters and values are scalar arguments for a benchmark
        iterations : int
            Integer of repetitions to run
        settings : dict
            A dict containing keys ``drop_caches``, ``gc_collect``, and ``gc_disable`` with bool values.
        queue : multiprocessing.Queue
            An instance of `multiprocessing.Queue` used for sending data back to a parent process.

        Returns
        -------
        A dict with ``stats`` and ``error`` keys with values suitable for the respective
        ``BenchmarkResult`` fields.
        """
        self.setup(case=case)

        times = []
        error = None
        for _ in range(iterations):
            res = self.run_iteration(case=case, settings=settings)
            if res["error"]:
                error = res["error"]

                if settings["error_handling"] in ["stop", "break"]:
                    break
            else:
                times.append(res["time"])

        if len(times) > 0:
            stats = {"data": times, "units": "s", "iterations": iterations}
        else:
            stats = None

        result = {"stats": stats, "error": error}
        queue.put(result)
        self.teardown(case=case)
        return result

    def run_iteration(self, case: dict, settings: dict) -> dict:
        """Run a single iteration, without setup or teardown"""
        if settings["drop_caches"]:
            self.cache.sync_and_drop()
        if settings["gc_collect"]:
            gc.collect()
        if settings["gc_disable"]:
            gc.disable()

        elapsed_time = None
        error = None
        try:
            self.before_each(case=case)
            start_time = time.monotonic()
            self.run(case=case)
            end_time = time.monotonic()
            self.after_each(case=case)
            elapsed_time = end_time - start_time
        except Exception as e:
            error = {"error": repr(e), "stack_trace": traceback.format_exc()}
            warnings.warn(error["error"])

        gc.enable()
        return {"time": elapsed_time, "error": error}


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
    subprocess : bool
        Run all benchmarks in a subprocess?
    error_handling : str
        What should happen if an iteration errors out? Options: ``"stop"`` (skip future iterations
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
        result_fields_append: Dict[str, Any] = None,
        drop_caches: bool = False,
        gc_collect: bool = True,
        gc_disable: bool = True,
        subprocess: bool = True,
        error_handling: str = "stop",
    ) -> None:
        assert error_handling in ["stop", "break", "continue"]

        self.iteration = iteration
        self.case_list = case_list
        self.result_fields_append = result_fields_append or {}
        self.settings = {
            # TODO: Figure out if we should change `drop_caches` default to True
            "drop_caches": drop_caches,
            "gc_collect": gc_collect,
            "gc_disable": gc_disable,
            "subprocess": subprocess,
            "error_handling": error_handling,
        }
        self.cache = CacheManager()

    def run_case(
        self,
        case: dict,
        iterations: int,
        run_reason: str,
        run_name: str,
        run_id: str,
        batch_id: str,
    ) -> BenchmarkResult:
        iteration = copy.deepcopy(self.iteration)
        queue = mp.Queue()
        if self.settings["subprocess"]:
            proc = mp.Process(
                target=iteration, args=(case, iterations, self.settings, queue)
            )
            proc.start()
            res = queue.get()
            proc.join()
        else:
            iteration(
                case=case, iterations=iterations, settings=self.settings, queue=queue
            )
            res = queue.get()

        result = BenchmarkResult(
            run_name=run_name,
            run_id=run_id,
            batch_id=batch_id,
            run_reason=run_reason,
            stats=res["stats"],
            error=res["error"],
            tags={"name": self.iteration.name, **case},
            # info={},  # TODO: is there common detectable metadata worth putting here?
            context={"benchmark_language": "Python"},
        )

        for param in self.result_fields_append:
            setattr(
                result,
                param,
                {**getattr(result, param), **self.result_fields_append[param]},
            )

        return result

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
