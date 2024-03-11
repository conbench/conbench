import json
from pathlib import Path
from typing import Any, Dict, List
import itertools
import numpy as np
import os
from datetime import datetime

from ..result import BenchmarkResult
from ._adapter import BenchmarkAdapter


class AsvBenchmarkAdapter(BenchmarkAdapter):

    def __init__(
        self,
        command: List[str],
        result_file: Path,
        benchmarks_file_path: Path,
        result_fields_override: Dict[str, Any] = None,
    ) -> None:
        """
        Parameters
        ----------
        command : List[str]
            A list of strings defining a shell command to run benchmarks
        result_file : Path
            Name of file with its path, generated by asv by commit. It holds
            the benchmarks results.
        benchmarks_file_pat : Path
            Path to the benchmarks.json file. Generated by asv to hold information
            about the benchmarks.
        result_fields_override : Dict[str, Any]
            A dict of values to override on each instance of `BenchmarkResult`. Useful
            for specifying metadata only available at runtime, e.g. build info. Applied
            before ``results_field_append``.
        """
        self.result_file = result_file
        self.benchmarks_file_path = benchmarks_file_path
        super().__init__(
            command=command,
            result_fields_override=result_fields_override,
        )

    def _transform_results(self) -> List[BenchmarkResult]:
        """Transform asv results into a list of BenchmarkResults instances"""

        with open(self.result_file, "r") as f:
            benchmarks_results = json.load(f)

        benchmarks_file = self.benchmarks_file_path / "benchmarks.json"
        with open(benchmarks_file) as f:
            benchmarks_info = json.load(f)

        parsed_benchmarks = self._parse_results(benchmarks_results, benchmarks_info)

        return parsed_benchmarks

    def _parse_results(
        self, benchmarks_results: str, benchmarks_info: str
    ) -> List[BenchmarkResult]:
        """
        From asv documention "result_columns" is a list of column names for the results dictionary.
        ["result", "params", "version", "started_at", "duration", "stats_ci_99_a", "stats_ci_99_b",
        "stats_q_25", "stats_q_75", "stats_number", "stats_repeat", "samples", "profile"]
        In this first version of the adapter we are using only the "result" column.
        """
        try:
            result_columns = benchmarks_results["result_columns"]
        except:
            raise Exception("Incorrect file format")
        parsed_benchmarks = []

        for benchmark_name in benchmarks_results["results"]:
            try:
                # benchmarks_results["results"][name] bellow has either a list
                # with items corresponding to each result of a parameters combination,
                # or just one value if the benchmark has no parameters.
                # "name" is the name of the benchmark
                result_dict = dict(
                    zip(result_columns, benchmarks_results["results"][benchmark_name])
                )
                if "samples" in result_dict:
                    data_key = "samples"
                else:
                    data_key = "result"
                for param_values, data in zip(
                    itertools.product(*result_dict["params"]), result_dict[data_key]
                ):
                    if np.any(np.isnan(data)):
                        # Nan is generated in the results by pandas benchmarks
                        # when a combination of parameters is not allowed.
                        # In this case, the result is not sent to  the conbench webapp
                        continue
                    param_dic = dict(
                        zip(
                            benchmarks_info[benchmark_name]["param_names"], param_values
                        )
                    )
                    tags = {}
                    tags["name"] = benchmark_name

                    # For conbench, "name" is a key reserved for tags. But if there is a
                    # parameter or case called "name", it overrides tags["name"]. So
                    # the benchmark_name gets lost. Hence this check:
                    if "name" in param_dic:
                        param_dic["name_"] = param_dic["name"]
                        del param_dic["name"]
                    tags.update(param_dic)

                    # asv units are seconds or bytes, conbench uses "s" or "B"
                    units = {"seconds": "s", "bytes": "B"}
                    params = benchmarks_results["params"]

                    # Asv returns one value wich is the average of the samples
                    # (called iterations in conbench). But this can be changed.
                    # Using asv run flag --append-samples or --record-samples,
                    # it returns the value of each iteration. In this case
                    # "data" will be a list.
                    # Also, iterations should be 1 if asv provides the average, but
                    # if we run asv to return each iteration,
                    # variable "iterations" should match the number of values.
                    if data_key == "result":
                        data = [data]
                        iterations = 1
                    else:
                        iterations = len(data)

                    parsed_benchmark = BenchmarkResult(
                        stats={
                            "data": data,
                            "unit": units[benchmarks_info[benchmark_name]["unit"]],
                            "iterations": iterations,
                        },
                        tags=tags,
                        context={
                            "benchmark_language": "Python",
                            "env_name": benchmarks_results["env_name"],
                            "python": benchmarks_results["python"],
                            "requirements": benchmarks_results["requirements"],
                        },
                        github={
                            "repository": os.environ["REPOSITORY"],
                            "commit": benchmarks_results["commit_hash"],
                        },
                        info={
                            "date": str(
                                datetime.fromtimestamp(benchmarks_results["date"] / 1e3)
                            ),
                        },
                        machine_info={
                            "name": params["machine"],
                            "os_name": params["os"],
                            "os_version": params["os"],
                            "architecture_name": params["arch"],
                            "kernel_name": "x",
                            "memory_bytes": 0,
                            "cpu_model_name": params["cpu"],
                            "cpu_core_count": params["num_cpu"],
                            "cpu_thread_count": 0,
                            "cpu_l1d_cache_bytes": 0,
                            "cpu_l1i_cache_bytes": 0,
                            "cpu_l2_cache_bytes": 0,
                            "cpu_l3_cache_bytes": 0,
                            "cpu_frequency_max_hz": 0,
                            "gpu_count": 0,
                            "gpu_product_names": [],
                        },
                    )
                    parsed_benchmarks.append(parsed_benchmark)
            except:
                # This happens if the name of the benchmark is
                # not found in benchmarks.json. This file should
                # be updated after benchmarks are changed (by the
                # asv user).
                continue

        return parsed_benchmarks
