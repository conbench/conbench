import uuid
from typing import Any, Dict, Generator, List

from ..log import log
from ..result import BenchmarkResult
from ._adapter import BenchmarkAdapter


class GeneratorAdapter(BenchmarkAdapter):
    """
    A generic adapter for adapting benchmarks defined in a generator (i.e. a
    generator or class with an ``__call__()`` method) that yields one
    `BenchmarkResult` instance at a time. Does not shell out.

    Attributes
    ----------

    generator : Generator[BenchmarkResult, None, None]
        A callable that yields one `BenchmarkResult` instance at a time
    """

    generator: Generator[BenchmarkResult, None, None] = None

    def __init__(
        self,
        generator: Generator[BenchmarkResult, None, None],
        result_fields_override: Dict[str, Any] = None,
        result_fields_append: Dict[str, Any] = None,
    ) -> None:
        self.generator = generator

        super().__init__(
            command=[],
            result_fields_override=result_fields_override,
            result_fields_append=result_fields_append,
        )

    def __call__(self, **kwargs) -> None:
        """
        Run each benchmark and post the result to conbench server

        Parameters
        ----------
        kwargs
            Passed through to `run()`
        """
        for _ in self.run(**kwargs):
            self.post_results()

    def run(
        self, params: Dict[str, Any] = None
    ) -> Generator[List[BenchmarkResult], None, None]:
        """
        Run benchmarks. Unlike other adapters, this method is here a generator.

        Parameters
        ----------
        params : Dict[str, Any]
            Additional kwargs to be passed though to the iterable
        """
        params = params or {}
        run_id = uuid.uuid4().hex

        log.info(f"Running iterable with params {params}")

        # self.results will hold one at a time, so this will accumulate everything
        # so the state is the same as running all at once at the end
        all_results = []
        for result in self.generator(**params):
            all_results.append(result)
            self.results = [result]
            self.transform_results(run_id=run_id)
            yield self.results

        log.info("Benchmark run completed")
        self.results = all_results

    def transform_results(self, run_id: str) -> List[BenchmarkResult]:
        """
        Method to transform results from the command line call into a list of
        instances of `BenchmarkResult`. This method returns results updated
        with runtime metadata values specified on init.

        Identical to the parent method, except takes `run_id` as a parameter
        instead of generating it in each call.
        """
        log.info("Transforming one result for conbench")
        results = self._transform_results()
        self.results = [
            self.update_benchmark_result(res, run_id=run_id) for res in results
        ]
        log.info("Result transformation completed")
        return self.results

    def _transform_results(self) -> List[BenchmarkResult]:
        return self.results
