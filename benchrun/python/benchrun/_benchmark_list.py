import uuid
from typing import Any, List

from benchadapt import BenchmarkResult

from ._benchmark import Benchmark


class BenchmarkList:
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
