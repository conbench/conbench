import uuid
from typing import Any, Generator, List

from benchadapt import BenchmarkResult

from ._benchmark import Benchmark


class CallableBenchmarkList:
    """
    A list of benchmarks in a Callable class suitable for adapting with benchadapt's
    generic ``CallableAdapter``

    Attributes
    ----------
    benchmarks : List[Benchmark]
        A list of instances of `Benchmark` to run together
    """

    benchmarks: List[Benchmark] = None

    def __init__(self, benchmarks: List[Benchmark]) -> None:
        self.benchmarks = benchmarks

    def __call__(self, **kwargs: Any) -> List[BenchmarkResult]:
        """
        Run all valid cases for each benchmark.

        Parameters
        ----------
        kwargs : Any
            Passed through to the ``.run()`` method of each benchmark. ``run_reason``
            should usually be specified here. ``run_name`` and ``run_id`` can be, but
            will be correctly handled by default.
        """
        kwargs["run_id"] = kwargs.get("run_id") or uuid.uuid4().hex
        results = []

        for benchmark in self.benchmarks:
            results += benchmark.run(**kwargs)

        return results


class GeneratorBenchmarkList(CallableBenchmarkList):
    """
    A list of benchmarks in a Callable class suitable for adapting with benchadapt's
    generic ``GeneratorAdapter``

    Attributes
    ----------
    benchmarks : List[Benchmark]
        A list of instances of `Benchmark` to run together
    """

    def __call__(
        self,
        run_name: str = None,
        batch_id: str = None,
        iterations: int = 1,
        **kwargs: Any
    ) -> Generator[BenchmarkResult, None, None]:
        """
        A generator that will yeild one case at a time

        Parameters
        ----------
        run_name:
            Name for the run. Current convention is ``f"{run_reason}: {github['commit']}"``.
            If missing and ``github["commmit"]`` exists, ``run_name`` will be populated
            according to that pattern (even if ``run_reason`` is ``None``); otherwise it will
            remain ``None``. Users should not set this manually unless they want to identify
            runs in some other fashion. Benchmark name should be specified in ``tags["name"]``.
        batch_id : str
            ID string for the batch
        iterations : int
            How many times to run each case
        kwargs : Any
            Passed through to the ``.run_case()`` method of each benchmark. ``run_reason``
            should usually be specified here. ``run_id`` can be, but will be correctly
            handled by default.
        """
        kwargs["run_id"] = kwargs.get("run_id") or uuid.uuid4().hex

        for benchmark in self.benchmarks:
            for case in benchmark.case_list.case_list:
                yield benchmark.run_case(
                    case=case,
                    run_name=run_name,
                    batch_id=batch_id,
                    iterations=iterations,
                    **kwargs
                )
