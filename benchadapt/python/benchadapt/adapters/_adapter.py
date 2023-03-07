import abc
import datetime
import logging
import subprocess
import uuid
from typing import Any, Dict, List

import requests
from benchclients.conbench import ConbenchClient
from benchclients.logging import fatal_and_log

from ..result import BenchmarkResult

log = logging.getLogger("benchadapt.adapters")

# `basicConfig()` does nothing if the root logger already has handlers
# configured (that is, if this benchadapt library is imported in the context
# of a program that already has a root logger with handlers set up, then the
# following call is a noop.
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s.%(msecs)03d %(levelname)s: %(message)s",
    datefmt="%y%m%d-%H:%M:%S",
)


class BenchmarkAdapter(abc.ABC):
    """
    An abstract class to run benchmarks, transform results into conbench form,
    and send them to a conbench server.

    In general, one instance should correspond to one run (likely of many benchmarks).

    Attributes
    ----------
    command : List[str]
        A list of args to be run on the command line, as would be passed
        to `subprocess.run()`.
    result_fields_override : Dict[str, Any]
        A dict of values to override on each instance of `BenchmarkResult`. Useful
        for specifying metadata only available at runtime, e.g. ``run_reason`` and
        build info. Applied before ``results_field_append``. Useful for both dicts
        (will replace the full dict) and other types.
    results_fields_append : Dict[str, Any]
        A dict of values to be appended to `BenchmarkResult` values after
        instantiation. Useful for appending extra tags or other metadata in addition
        to that gathered elsewhere already in a dict field. Only applicable for dict
        attributes. For each element, will override any keys that already exist, i.e.
        it does not append recursively.
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
        log.info("Initializing adapter")
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

        log.info(
            f"Running benchmarks with command: `{' '.join([str(x) for x in command])}`"
        )
        subprocess.run(args=command, check=True)
        log.info("Benchmark run completed")
        self.results = self.transform_results()

        return self.results

    def transform_results(self) -> List[BenchmarkResult]:
        """
        Method to transform results from the command line call into a list of
        instances of `BenchmarkResult`. This method returns results updated
        with runtime metadata values specified on init.
        """
        log.info("Transforming results for conbench")
        results = self._transform_results()
        run_id = uuid.uuid4().hex
        self.results = [
            self.update_benchmark_result(res, run_id=run_id) for res in results
        ]
        log.info("Results transformation completed")
        return self.results

    @abc.abstractmethod
    def _transform_results(self) -> List[BenchmarkResult]:
        """
        Method to transform results from the command line call into a list of
        instances of `BenchmarkResult`. The results of this method will be
        updated to apply runtime metadata values specified on init.

        If a benchmark run produces multiple files, this method should handle
        all files in one run.

        It should generally not populate ``run_id`` (which the adapter will
        handle correctly if unspecified), ``run_name`` (which will get generated
        if the git commit is available), and ``run_reason`` (which should usually
        be specified in ``result_fields_override`` on initialization, as it will
        vary).
        """

    def update_benchmark_result(
        self, result: BenchmarkResult, run_id: str
    ) -> BenchmarkResult:
        """
        A method to update instances of `BenchmarkResult` with values specified on
        init in ``result_fields_override`` and/or ``result_fields_append``.

        Parameters
        ----------
        result : BenchmarkResult
            An instance of `BenchmarkResult` to update
        run_id : str
            Value to use for ``run_id`` if it is not already set directly in a
            ``_tranform_results()`` implementation or via ``result_fields_override``).
            Should match for all results for a run, so a hex UUID is generated in
            ``transform_results()`` in normal usage.
        """
        for param in self.result_fields_override:
            setattr(result, param, self.result_fields_override[param])

        for param in self.result_fields_append:
            setattr(
                result,
                param,
                {**getattr(result, param), **self.result_fields_append[param]},
            )

        if not result.run_id:
            result.run_id = run_id

        return result

    def post_results(self) -> list:
        """
        Post results of run to conbench
        """
        if not self.results:
            fatal_and_log(
                "No results attribute to post! Was `run()` called on this instance?"
            )

        log.info("Initializing conbench client")
        client = ConbenchClient()

        log.info("Posting results to conbench")
        res_list = []
        error = None
        for result in self.results:
            result_dict = result.to_publishable_dict()

            try:
                res = client.post(path="/benchmarks/", json=result_dict)
            except requests.exceptions.ReadTimeout as e:
                error_time = datetime.datetime.utcnow()
                log.info(f"{error_time} POST timed out: {repr(e)}. Retrying...")
                try:
                    res = client.post(path="/benchmarks/", json=result_dict)
                except requests.exceptions.ReadTimeout as ee:
                    error_time2 = datetime.datetime.utcnow()
                    log.warning(
                        (
                            f"{error_time2} POST timed out again: {repr(ee)}. "
                            "Skipping and continuing to other results."
                        )
                    )
                    error = ee

            res_list.append(res)

        if error:
            log.error(f"POST at {error_time} timed out twice:")
            raise error

        log.info("All results sent to conbench")
        return res_list
