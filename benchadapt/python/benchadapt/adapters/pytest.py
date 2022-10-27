import json
import tempfile
from pathlib import Path
from typing import Any, Dict, List

from ..log import log
from ..result import BenchmarkResult
from ._adapter import BenchmarkAdapter


class PytestAdapter(BenchmarkAdapter):
    """
    An adapter for sending results from
    [pytest-benchmark](https://github.com/ionelmc/pytest-benchmark) to conbench
    """

    result_file: Path

    def __init__(
        self,
        command: List[str],
        result_file: Path = None,
        result_fields_override: Dict[str, Any] = None,
        result_fields_append: Dict[str, Any] = None,
    ) -> None:
        """
        Parameters
        ----------
        command : List[str]
            A list of args to be run on the command line, as would be passed
            to `subprocess.run()`.
        result_file : Path
            The path to a file of benchmark results that will be generated when
            ``.run()`` is called. If ``None``, a tempfile will be used and
            ``["--benchmark-json='{tempfile}'"]`` will be appended to ``command``.
        """
        if not result_file:
            result_file = Path(tempfile.mktemp(suffix=".json"))
            file_flag = f"--benchmark-json='{result_file}'"
            command.append(file_flag)
            log.info(
                f"`result_file` not supplied; appending `{file_flag}` to `command`"
            )

        self.result_file = result_file
        super().__init__(command, result_fields_override, result_fields_append)

    def _transform_results(self) -> List[BenchmarkResult]:
        with open(self.result_file, "r") as f:
            raw_results = json.load(f)

        parsed_results = []
        for res in raw_results["benchmarks"]:
            tags = {"name": res["fullname"]}
            if res["param"]:
                tags["param"] = res["param"]
            if res["params"]:
                tags["params"] = res["params"]

            parsed_res = BenchmarkResult(
                batch_id=res["group"],
                stats={
                    "data": res["stats"]["data"],
                    "units": "s",
                    "iterations": len(res["stats"]["data"]),
                    "times": [],
                    "time_unit": "s",
                },
                tags=tags,
                context={"benchmark_language": "Python"},
                timestamp=f"{raw_results['datetime']}+00:00",
                # github={
                #     "commit": raw_results["commit_info"]["id"],
                #     # this is not quite what we want; it's just `conbench`
                #     # instead of `git@github.com:conbench/conbench`
                #     "repository": raw_results["commit_info"]["project"],
                # },
                # machine_info={
                #     "name": raw_results["machine_info"]["node"],
                #     "os_name": ,  # TODO
                #     "os_version": ,  # TODO
                #     "architecture_name": raw_results["machine_info"]["cpu"][
                #         "arch_string_raw"
                #     ],
                #     "kernel_name": raw_results["machine_info"]["release"],
                #     "memory_bytes": ,  # TODO
                #     "cpu_model_name": raw_results["machine_info"]["cpu"]["brand_raw"],
                #     "cpu_core_count": raw_results["machine_info"]["cpu"]["count"],
                #     "cpu_thread_count": ,  # TODO
                #     "cpu_l1d_cache_bytes": ,  # TODO
                #     "cpu_l1i_cache_bytes": ,  # TODO
                #     "cpu_l2_cache_bytes": ,  # TODO
                #     "cpu_l3_cache_bytes": ,  # TODO
                #     "cpu_frequency_max_hz": ,  # TODO
                #     "gpu_count": ,  # TODO
                #     "gpu_product_names": ,  # TODO
                # },
            )
            parsed_results.append(parsed_res)

        return parsed_results
