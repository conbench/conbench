import json
import uuid
from pathlib import Path
from typing import List

from ..result import BenchmarkResult
from ._adapter import BenchmarkAdapter


class FollyAdapter(BenchmarkAdapter):
    """Run folly benchmarks and send the results to conbench"""

    result_dir: Path

    def __init__(self, command: List[str], result_dir: Path) -> None:
        """
        Parameters
        ----------
        command : List[str]
            A list of strings defining a shell command to run folly benchmarks
        result_dir : Path
            Path to directory where folly results will be populated
        """
        self.result_dir = Path(result_dir)
        super().__init__(command=command)

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

                parsed_benchmark = BenchmarkResult(
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
