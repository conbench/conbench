import abc
import subprocess

from .client import ConbenchClient
from .log import fatal_and_log
from .result import BenchmarkResult


class BenchmarkRunner(abc.ABC):
    """
    An abstract class to run benchmarks, transform results into conbench form,
    and send them to a conbench server

    Parameters
    ----------
    command : list[str]
        A list of args to be run on the command line, as would be passed
        to `subprocess.run()`
    """

    results: list[BenchmarkResult] = None

    def __init__(self, command: list[str]) -> None:
        self.command = command
        self.client = ConbenchClient()

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

    def run(self, params: list[str] = None, **kwargs) -> list[BenchmarkResult]:
        """
        Run benchmarks

        Parameters
        ----------
        params : list[str]
            Additional parameters to be appended to the command before running
        kwargs : dict[str, Any]
            Named arguments passed through to `subprocess.run()`
        """
        command = self.command
        if params:
            command += params

        res = subprocess.run(args=command, **kwargs)
        res.check_returncode()

        self.results = self.transform_results()

        return self.results

    @abc.abstractmethod
    def transform_results(self) -> list[BenchmarkResult]:
        """
        Method to transform results from the command line call into a list of
        instances of `BenchmarkResult`.
        """
        raise NotImplementedError

    def post_results(self) -> list:
        """
        Post results of run to conbench
        """
        if not self.results:
            fatal_and_log(
                "No results attribute to post! Was `run()` called on this instance?"
            )

        res_list = []
        for result in self.results:
            result_dict = result.to_publishable_dict()
            res = self.client.post(path="/benchmarks", json=result_dict)
            res_list.append(res)

        return res_list
