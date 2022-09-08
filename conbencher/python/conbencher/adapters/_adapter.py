import abc
import subprocess
from typing import List

from ..client import ConbenchClient
from ..log import fatal_and_log
from ..result import BenchmarkResult


class _BenchmarkAdapter(abc.ABC):
    """
    An abstract class to run benchmarks, transform results into conbench form,
    and send them to a conbench server

    Attributes
    ----------
    command : List[str]
        A list of args to be run on the command line, as would be passed
        to `subprocess.run()`.
    results : List[BenchmarkResult]
        Once `run()` has been called, results from that run
    """

    command: List[str]
    results: List[BenchmarkResult] = None

    def __init__(self, command: List[str]) -> None:
        self.command = command

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

        res = subprocess.run(args=command)
        res.check_returncode()

        self.results = self.transform_results()

        return self.results

    @abc.abstractmethod
    def transform_results(self) -> List[BenchmarkResult]:
        """
        Method to transform results from the command line call into a list of
        instances of `BenchmarkResult`.
        """
        raise NotImplementedError

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
