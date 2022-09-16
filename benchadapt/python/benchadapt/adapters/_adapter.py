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
    result_defaults_override : Dict[str, Any]
        A dict of default values to be passed to `BenchmarkResult`. Useful for
        specifying metadata only available at runtime, e.g. build info. Overrides
        `BenchmarkResult` defaults; is overridden by values passed in
        ``transform_results()``. Values of ``None`` do not unset defaults, just as
        when passed to ``BenchmarkResult`'s init method.
    results_defaults_append : Dict[str, Any]
        A dict of default values to be appended to `BenchmarkResult` values.
        Appended after instantiation. Useful for appending extra tags or other
        metadata in addition to that gathered elsewhere. Only applicable for dict
        attributes. For each element, will override any keys that already exist,
        i.e. it does not append recursively.
    results : List[BenchmarkResult]
        Once `run()` has been called, results from that run
    """

    command: List[str]
    result_defaults_override: Dict[str, Any] = None
    results: List[BenchmarkResult] = None

    def __init__(
        self,
        command: List[str],
        result_defaults_override: Dict[str, Any] = None,
        result_defaults_append: Dict[str, Any] = None,
    ) -> None:
        self.command = command

        if not result_defaults_override:
            result_defaults_override = {}
        self.result_defaults_override = result_defaults_override

        if not result_defaults_append:
            result_defaults_append = {}
        self.result_defaults_append = result_defaults_append

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

    @abc.abstractmethod
    def transform_results(self) -> List[BenchmarkResult]:
        """
        Method to transform results from the command line call into a list of
        instances of `BenchmarkResult`.
        """

    def curried_benchmark_result(self, **kwargs) -> BenchmarkResult:
        """
        A method to create instances of `BenchmarkResult` with defaults filled with
        any specified on init in ``result_defaults``.

        Parameters
        ----------
        kwargs
            Named arguments to parameters of `BenchmarkResult`. Takes priority over
            arguments from ``result_defaults`` and `BenchmarkResult`'s defaults.
        """
        res = BenchmarkResult(**{**self.result_defaults_override, **kwargs})

        for param in self.result_defaults_append:
            setattr(
                res,
                param,
                {**getattr(res, param), **self.result_defaults_append[param]},
            )

        return res

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
