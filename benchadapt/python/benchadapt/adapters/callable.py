from typing import Any, Callable, Dict, List

from benchclients import log

from ..result import BenchmarkResult
from ._adapter import BenchmarkAdapter


class CallableAdapter(BenchmarkAdapter):
    """
    A generic adapter for adapting benchmarks defined in a Callable, i.e. a
    function or class with a ``__call__()`` method that directly returns a
    list of `BenchmarkResult` instances. Does not shell out.

    Attributes
    ----------

    callable : Callable
        A Callable (a function or a class with a ``__call__()`` method) that
        returns a list of `BenchmarkResult` instances
    """

    callable: Callable = None

    def __init__(
        self,
        callable: Callable,
        result_fields_override: Dict[str, Any] = None,
        result_fields_append: Dict[str, Any] = None,
    ) -> None:
        self.callable = callable

        super().__init__(
            command=[],
            result_fields_override=result_fields_override,
            result_fields_append=result_fields_append,
        )

    def run(self, params: List[str] = None) -> List[BenchmarkResult]:
        """
        Run benchmarks

        Parameters
        ----------
        params : List[str]
            Additional kwargs to be passed though to the callable
        """
        params = params or {}

        log.info(f"Running callable with params {params}")
        self.results = self.callable(**params)
        log.info("Benchmark run completed")
        self.results = self.transform_results()

        return self.results

    def _transform_results(self) -> List[BenchmarkResult]:
        return self.results
