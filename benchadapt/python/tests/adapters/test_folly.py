import json
import tempfile
from pathlib import Path

import pytest

from benchadapt.adapters import FollyAdapter
from benchadapt.result import BenchmarkResult

folly_jsons = {
    "velox_benchmark_basic_selectivity_vector.json": [
        [
            "/Users/jkeane/repos/velox/velox/benchmarks/basic/SelectivityVector.cpp",
            "sumBaselineAll",
            0,
        ],
        [
            "/Users/jkeane/repos/velox/velox/benchmarks/basic/SelectivityVector.cpp",
            "sumSelectivityAll",
            0,
        ],
        [
            "/Users/jkeane/repos/velox/velox/benchmarks/basic/SelectivityVector.cpp",
            "sumSelectivity99PerCent",
            0,
        ],
        [
            "/Users/jkeane/repos/velox/velox/benchmarks/basic/SelectivityVector.cpp",
            "sumSelectivity50PerCent",
            0,
        ],
        [
            "/Users/jkeane/repos/velox/velox/benchmarks/basic/SelectivityVector.cpp",
            "sumSelectivity10PerCent",
            0,
        ],
        [
            "/Users/jkeane/repos/velox/velox/benchmarks/basic/SelectivityVector.cpp",
            "sumSelectivity1PerCent",
            0,
        ],
    ],
    "velox_benchmark_feature_normalization.json": [
        [
            "/Users/jkeane/repos/velox/velox/benchmarks/basic/FeatureNormalization.cpp",
            "normalize",
            17.781428779296874,
        ],
        [
            "/Users/jkeane/repos/velox/velox/benchmarks/basic/FeatureNormalization.cpp",
            "normalizeConstant",
            15.583608779296874,
        ],
    ],
}


class TestFollyAdapter:
    folly_bms = [
        *folly_jsons["velox_benchmark_feature_normalization.json"],
        *folly_jsons["velox_benchmark_basic_selectivity_vector.json"],
    ]

    @pytest.fixture(scope="class")
    def folly_adapter(self):
        tempdir = Path(tempfile.mkdtemp())

        folly_adapter = FollyAdapter(
            command=["echo", "'Hello, world!'"],
            result_dir=tempdir,
        )

        for file in folly_jsons:
            with open(folly_adapter.result_dir / file, "w") as f:
                json.dump(folly_jsons[file], f)

        return folly_adapter

    def test_transform_results(self, folly_adapter) -> None:
        results = folly_adapter.transform_results()

        assert len(results) == len(self.folly_bms)
        for result, original in zip(results, self.folly_bms):
            assert isinstance(result, BenchmarkResult)
            assert result.run_name in [
                "velox_benchmark_basic_selectivity_vector",
                "velox_benchmark_feature_normalization",
            ]
            assert result.context == {"benchmark_language": "C++"}
            assert result.machine_info is not None
            assert result.stats["data"][0] == original[2]
            assert result.stats["times"][0] == original[2]

    def test_run(self, folly_adapter) -> None:
        results = folly_adapter.run()
        assert len(results) == len(self.folly_bms)
