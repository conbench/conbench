import json
import uuid
from pathlib import Path
from typing import Any, Dict, List

from ..result import BenchmarkResult
from ._adapter import BenchmarkAdapter


class FollyAdapter(BenchmarkAdapter):
    """Run folly benchmarks and send the results to conbench"""

    result_dir: Path

    def __init__(
        self,
        command: List[str],
        result_dir: Path,
        result_defaults_override: Dict[str, Any] = None,
        result_defaults_append: Dict[str, Any] = None,
    ) -> None:
        """
        Parameters
        ----------
        command : List[str]
            A list of strings defining a shell command to run folly benchmarks
        result_dir : Path
            Path to directory where folly results will be populated
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
        """
        self.result_dir = Path(result_dir)
        super().__init__(
            command=command,
            result_defaults_override=result_defaults_override,
            result_defaults_append=result_defaults_append,
        )

    def transform_results(self) -> List[BenchmarkResult]:
        """Transform folly results into conbench form"""

        parsed_benchmarks = []
        for path in self.result_dir.resolve().glob("**/*.json"):
            batch_id = uuid.uuid4().hex
            suite = path.stem

            with open(path, "r") as f:
                raw_json = json.load(f)

            for result in raw_json:
                # Folly benchmark exports line separators by mistake as
                # an entry in the json file.
                if result[1] == "-":
                    continue

                bm_name = result[1].lstrip("%")

                parsed_benchmark = self.curried_benchmark_result(
                    run_name=suite,
                    batch_id=batch_id,
                    stats={
                        # Folly always returns in ns, so use that. All benchmarks are times,
                        # none are throughput so both data and times have the same unit
                        "data": [result[2]],
                        "unit": "ns",
                        "times": [result[2]],
                        "time_unit": "ns",
                    },
                    tags={"name": bm_name, "suite": suite, "source": "cpp-micro"},
                    info={},
                    context={"benchmark_language": "C++"},
                )

                parsed_benchmarks.append(parsed_benchmark)

        return parsed_benchmarks
