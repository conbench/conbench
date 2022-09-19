import abc
import subprocess
from typing import Any, Dict, List

from ..client import ConbenchClient
from ..log import fatal_and_log
from ..result import BenchmarkResult


class BenchmarkAdapter(abc.ABC):
    """
    An abstract class to run benchmarks, transform results into conbench form,
    and send them to a conbench server

    Attributes
    ----------
    command : List[str]
        A list of args to be run on the command line, as would be passed
        to `subprocess.run()`.
    result_fields_override : Dict[str, Any]
        A dict of values to override on each instance of `BenchmarkResult`. Useful
        for specifying metadata only available at runtime, e.g. build info. Applied
        before ``results_field_append``.
    results_fields_append : Dict[str, Any]
        A dict of default values to be appended to `BenchmarkResult` values after
        instantiation. Useful for appending extra tags or other metadata in addition
        to that gathered elsewhere. Only applicable for dict attributes. For each
        element, will override any keys that already exist, i.e. it does not append
        recursively.
    results : List[BenchmarkResult]
        Once `run()` has been called, results from that run
    """

    command: List[str]
    result_fields_override: Dict[str, Any] = None
    result_fields_append: Dict[str, Any] = None
    results: List[BenchmarkResult] = None

    def __init__(
        self,
        command: List[str],
        result_fields_override: Dict[str, Any] = None,
        result_fields_append: Dict[str, Any] = None,
    ) -> None:
        self.command = command
        self.result_fields_override = result_fields_override or {}
        self.result_fields_append = result_fields_append or {}

    def __call__(self, **kwargs) -> list:
        """
        Run benchmarks and post results to conbench server

        Parameters
        ----------
        kwargs
            Passed through to `run()`
        """
        self.run(**kwargs)
        self.post_results()

    def run(self, params: List[str] = None) -> List[BenchmarkResult]:
        """
        Run benchmarks

        Parameters
        ----------
        params : List[str]
            Additional parameters to be appended to the command before running
        """
        command = self.command
        if params:
            command += params

        subprocess.run(args=command, check=True)
        self.results = self.transform_results()

        return self.results

    def transform_results(self) -> List[BenchmarkResult]:
        """
        Method to transform results from the command line call into a list of
        instances of `BenchmarkResult`. This method returns results updated
        with runtime metadata values specified on init.
        """
        results = self._transform_results()
        self.results = [self.update_benchmark_result(res) for res in results]
        return self.results

    @abc.abstractmethod
    def _transform_results(self) -> List[BenchmarkResult]:
        """
        Method to transform results from the command line call into a list of
        instances of `BenchmarkResult`. The results of this method will be
        updated to apply runtime metadata values specified on init.
        """

    def update_benchmark_result(self, result: BenchmarkResult) -> BenchmarkResult:
        """
        A method to update instances of `BenchmarkResult` with vallues specified on
        init in ``result_fields_override`` and/or ``result_fields_append``.

        Parameters
        ----------
        result
            An instance of `BenchmarkResult` to update
        """
        for param in self.result_fields_override:
            setattr(result, param, self.result_fields_override[param])

        for param in self.result_fields_append:
            setattr(
                result,
                param,
                {**getattr(result, param), **self.result_fields_append[param]},
            )

        return result

    def post_results(self) -> list:
        """
        Post results of run to conbench
        """
        client = ConbenchClient()

        if not self.results:
            fatal_and_log(
                "No results attribute to post! Was `run()` called on this instance?"
            )

        res_list = []
        for result in self.results:
            result_dict = result.to_publishable_dict()
            res = client.post(path="/benchmarks", json=result_dict)
            res_list.append(res)

        return res_list
