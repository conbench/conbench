import json
import tempfile
from pathlib import Path

import numpy as np
import pytest
from benchadapt.adapters import AsvBenchmarkAdapter
from benchadapt.result import BenchmarkResult

benchmarks_json = {
    "benchmarks.TimeSuite.time_insertion_sort": {
        "code": "class TimeSuite:\n    def time_insertion_sort(self):\n        rest_of_the_code",
        "min_run_count": 2,
        "name": "benchmarks.TimeSuite.time_insertion_sort",
        "number": 4,
        "param_names": [],
        "params": [],
        "repeat": 3,
        "rounds": 2,
        "sample_time": 0.01,
        "type": "time",
        "unit": "seconds",
        "version": "1198fba41755fd157a0c7f7bc588ee00d3c4b577d482adc3cf034d8476f03f50",
        "warmup_time": -1,
    },
    "strings.Repeat.time_repeat": {
        "code": "class Repeat:\n    def time_repeat(self, repeats):\n        rest_of_the_code",
        "min_run_count": 2,
        "name": "strings.Repeat.time_repeat",
        "number": 0,
        "param_names": ["repeats"],
        "params": [["'int'", "'array'"]],
        "repeat": 0,
        "rounds": 2,
        "sample_time": 0.01,
        "type": "time",
        "unit": "seconds",
        "version": "1020d0debc1446a71cfda9efe059407dc390e74d806d2783566fdba4e7d1de98",
        "warmup_time": -1,
    },
    "boolean.TimeLogicalOps.time_or_scalar": {
        "code": "class TimeLogicalOps:\n    def time_or_scalar(self):\n ",
        "min_run_count": 2,
        "name": "boolean.TimeLogicalOps.time_or_scalar",
        "number": 0,
        "param_names": [],
        "params": [],
        "repeat": 0,
        "rounds": 2,
        "sample_time": 0.01,
        "type": "time",
        "unit": "seconds",
        "version": "a9dcf90a110c0c703887ee44358e18a6930758987f7f1e9f921dd5ff4c84234e",
        "warmup_time": -1,
    },
    "array.ArrowStringArray.time_setitem_slice": {
        "code": "class ArrowStringArray:\n    def time_setitem_slice(self, chunks):\n        rest_of_the_code",
        "min_run_count": 2,
        "name": "array.ArrowStringArray.time_setitem_slice",
        "number": 0,
        "param_names": ["multiple_chunks"],
        "params": [["False", "True"]],
        "repeat": 0,
        "rounds": 2,
        "sample_time": 0.01,
        "type": "time",
        "unit": "seconds",
        "version": "6a0d09a5d23eb6dc7d6bb95140476cc1c1a896640e9d7bd005861c59072edc0d",
        "warmup_time": -1,
    },
    "algorithms.SortIntegerArray.time_argsort": {
        "code": "class SortIntegerArray:\n    def time_argsort(self, N):\n        rest_of_the_code",
        "min_run_count": 2,
        "name": "algorithms.SortIntegerArray.time_argsort",
        "number": 0,
        "param_names": ["param1"],
        "params": [["1000", "100000", "1"]],
        "repeat": 0,
        "rounds": 2,
        "sample_time": 0.01,
        "type": "time",
        "unit": "seconds",
        "version": "40aa122c3448a0c4db1b17a00f7b64ee18672679c258627dc894596ae752a9e0",
        "warmup_time": -1,
    },
    "series_methods.ToFrame.time_to_frame": {
        "code": "class ToFrame:\n    def time_to_frame(self, dtype, name):\n        rest_of_the_code",
        "min_run_count": 2,
        "name": "series_methods.ToFrame.time_to_frame",
        "number": 0,
        "param_names": ["dtype", "name"],
        "params": [
            [
                "'int64'",
            ],
            ["None", "'foo'"],
        ],
        "repeat": 0,
        "rounds": 2,
        "sample_time": 0.01,
        "type": "time",
        "unit": "seconds",
        "version": "9837bd38099b9a8813a9b22a59b46e9e9afd7614361947eb24b302192b97eb20",
        "warmup_time": -1,
    },
    "version": 2,
}

asv_json = {
    "commit_hash": "0d24f201cc2506de45a2ed688d9f72f7123d58f7",
    "env_name": "conda-py3.10",
    "date": 1703062645000,
    "params": {
        "arch": "arm64",
        "cpu": "Apple M2",
        "machine": "MyMachine",
        "num_cpu": "8",
        "os": "macOS 13.5.1 (22G90)",
        "ram": "16GB",
        "python": "3.10",
    },
    "python": "3.10",
    "requirements": {},
    "env_vars": {},
    "result_columns": [
        "result",
        "params",
        "version",
        "started_at",
        "duration",
        "stats_ci_99_a",
        "stats_ci_99_b",
        "stats_q_25",
        "stats_q_75",
        "stats_number",
        "stats_repeat",
        "samples",
        "profile",
    ],
    "results": {
        "benchmarks.TimeSuite.time_insertion_sort": [
            [1.2035623905003376],
            [],
            "1198fba41755fd157a0c7f7bc588ee00d3c4b577d482adc3cf034d8476f03f50",
            1703063099923,
            38.656,
            [1.2016],
            [1.2053],
            [1.2025],
            [1.2045],
            [4],
            [6],
        ]
    },
    "durations": {},
    "version": 2,
}

asv_json_param_and_samples = {
    "commit_hash": "89b286a699b2d023b7a1ebc468abf230d84ad547",
    "env_name": "conda-py3.10-Cython3.0-jinja2-matplotlib ...",
    "date": 1709607034000,
    "params": {
        "arch": "arm64",
        "cpu": "Apple M2",
        "machine": "MyMachine",
        "num_cpu": "8",
        "os": "macOS 13.5.1 (22G90)",
        "ram": "16GB",
        "python": "3.10",
        "Cython": "3.0",
        "matplotlib": "",
        "sqlalchemy": "",
        "scipy": "",
        "numba": "",
        "numexpr": "",
        "pytables": "",
        "pyarrow": "",
        "openpyxl": "",
        "xlsxwriter": "",
        "xlrd": "",
        "odfpy": "",
        "jinja2": "",
        "meson": "",
        "meson-python": "",
        "python-build": "",
    },
    "python": "3.10",
    "requirements": {
        "Cython": "3.0",
        "matplotlib": "",
        "sqlalchemy": "",
        "scipy": "",
        "numba": "",
        "numexpr": "",
        "pytables": "",
        "pyarrow": "",
        "openpyxl": "",
        "xlsxwriter": "",
        "xlrd": "",
        "odfpy": "",
        "jinja2": "",
        "meson": "",
        "meson-python": "",
        "python-build": "",
    },
    "env_vars": {},
    "result_columns": [
        "result",
        "params",
        "version",
        "started_at",
        "duration",
        "stats_ci_99_a",
        "stats_ci_99_b",
        "stats_q_25",
        "stats_q_75",
        "stats_number",
        "stats_repeat",
        "samples",
        "profile",
    ],
    "results": {
        "strings.Repeat.time_repeat": [
            [0.03481033350544749, 0.03935433350125095],
            [["'int'", "'array'"]],
            "1020d0debc1446a71cfda9efe059407dc390e74d806d2783566fdba4e7d1de98",
            1709658661060,
            2.571,
            [0.0344, 0.039027],
            [0.035398, 0.039706],
            [0.034686, 0.039297],
            [0.035208, 0.039587],
            [1, 1],
            [10, 10],
        ],
        "boolean.TimeLogicalOps.time_or_scalar": [
            [0.00001634304932968048],
            [],
            "a9dcf90a110c0c703887ee44358e18a6930758987f7f1e9f921dd5ff4c84234e",
            1709659847382,
            0.91048,
            [0.000016278],
            [0.000016475],
            [0.000016302],
            [0.000016374],
            [669],
            [10],
            [
                [
                    0.000016370204791373757,
                    0.0000164747757895297,
                    0.000016352142014517064,
                    0.000016375186853806846,
                    0.000016442887910143355,
                    0.00001633370702185561,
                    0.000016333956644843892,
                    0.000016291790719454486,
                    0.000016286434983849937,
                    0.000016278026913333076,
                ]
            ],
        ],
        "array.ArrowStringArray.time_setitem_slice": [
            [0.00006179990675063583, 0.0001277931890998422],
            [["False", "True"]],
            "6a0d09a5d23eb6dc7d6bb95140476cc1c1a896640e9d7bd005861c59072edc0d",
            1709800865468,
            1.875,
            [0.000061653, 0.00012664],
            [0.00006225, 0.000136],
            [0.00006173, 0.00012706],
            [0.000061992, 0.00012931],
            [177, 82],
            [10, 10],
            [
                [
                    0.00006182156493334826,
                    0.00006185522589748356,
                    0.00006203789830912894,
                    0.00006174882492418848,
                    0.0000617782485679234,
                    0.00006172410722185284,
                    0.00006224953116964823,
                    0.00006212170615971173,
                    0.0000616723163800556,
                    0.00006165348587289326,
                ],
                [
                    0.00012692784153708688,
                    0.00012744156105682345,
                    0.00012687448782721397,
                    0.00013600406094976678,
                    0.00012771798781880246,
                    0.00012936482948489579,
                    0.00013176371945386253,
                    0.00012914939050948839,
                    0.0001266422804314416,
                    0.00012786839038088192,
                ],
            ],
        ],
        "algorithms.SortIntegerArray.time_argsort": [
            [9.382720887127119e-06, 0.0008135993461669737, np.NaN],
            [["1000", "100000", "1"]],
            "40aa122c3448a0c4db1b17a00f7b64ee18672679c258627dc894596ae752a9e0",
            1709835572798,
            2.3563,
            [9.2976e-06, 0.00079774, np.NaN],
            [9.5915e-06, 0.00083937, np.NaN],
            [9.3473e-06, 0.00080488, np.NaN],
            [9.4343e-06, 0.00082726, np.NaN],
            [1082, 13, np.NaN],
            [10, 10, np.NaN],
        ],
        "series_methods.ToFrame.time_to_frame": [
            [1.4953170287206877e-05, 1.495111301503055e-05],
            [["'int64'"], ["None", "'foo'"]],
            "9837bd38099b9a8813a9b22a59b46e9e9afd7614361947eb24b302192b97eb20",
        ],
    },
    "durations": {},
    "version": 2,
}


class TestAsvAdapter:
    @pytest.fixture
    def asv_adapter(self, monkeypatch):
        monkeypatch.setenv("REPOSITORY", "git@github.com:conchair/conchair")
        result_file = tempfile.mktemp(suffix=".json")
        tempdir = Path(tempfile.mkdtemp())

        asv_adapter = AsvBenchmarkAdapter(
            command=["echo", "'Hello, world!'"],
            result_file=Path(result_file),
            benchmarks_file_path=tempdir,
        )

        with open(asv_adapter.result_file, "w") as f:
            json.dump(asv_json, f)

        name = tempdir / "benchmarks.json"
        with open(name, "w") as f:
            json.dump(benchmarks_json, f)

        return asv_adapter

    def test_transform_results(self, asv_adapter) -> None:
        """This tests basic case: no params, no samples, only one benchmark."""
        results = asv_adapter.transform_results()

        assert len(results) == 1
        assert len(set(res.tags["name"] for res in results)) == 1
        assert len(set(res.batch_id for res in results)) == 1
        for result in results:
            assert isinstance(result, BenchmarkResult)
            assert isinstance(result.run_name, str)
            assert result.tags["name"].endswith("time_insertion_sort")
            assert result.context == {
                "benchmark_language": "Python",
                "env_name": "conda-py3.10",
                "python": "3.10",
                "requirements": {},
            }
            assert result.machine_info is not None
            assert result.stats == {
                "data": [1.2035623905003376],
                "unit": "s",
                "iterations": 1,
            }
            assert result.github["commit"] == "0d24f201cc2506de45a2ed688d9f72f7123d58f7"

    def test_run(self, asv_adapter) -> None:
        results = asv_adapter.run()
        assert len(results) == 1


class TestAsvAdapter_with_param_andsamples:
    @pytest.fixture
    def asv_adapter(self, monkeypatch):
        monkeypatch.setenv("REPOSITORY", "git@github.com:conchair/conchair")

        result_file = tempfile.mktemp(suffix=".json")
        tempdir = Path(tempfile.mkdtemp())

        asv_adapter = AsvBenchmarkAdapter(
            command=["echo", "'Hello, world!'"],
            result_file=Path(result_file),
            benchmarks_file_path=tempdir,
        )

        with open(asv_adapter.result_file, "w") as f:
            json.dump(asv_json_param_and_samples, f)

        name = tempdir.joinpath("benchmarks.json")
        with open(name, "w") as f:
            json.dump(benchmarks_json, f)

        return asv_adapter

    def test_transform_results(self, asv_adapter) -> None:
        # The structure of asv benchmarks change depending on the use
        # of samples (called "iterations" in conbenchand) and/or parameters
        # (called "cases" for conbench). So here testing for different combinations.
        results = asv_adapter.transform_results()
        assert len(results) == 9
        assert len([res.tags["name"] for res in results]) == 9

        for res in results:

            match res.tags:
                # Benchmark strings.Repeat.time_repeat uses two parameters or cases
                # ('int' and 'array') but no samples. It must return two results.
                case {"name": "strings.Repeat.time_repeat", "repeats": "'int'"}:
                    assert res.stats == {
                        "data": [0.03481033350544749],
                        "unit": "s",
                        "iterations": 1,
                    }
                case {"name": "strings.Repeat.time_repeat", "repeats": "'array'"}:
                    assert res.stats == {
                        "data": [0.03935433350125095],
                        "unit": "s",
                        "iterations": 1,
                    }

                # Benchmark 'boolean.TimeLogicalOps.time_or_scalar' uses samples
                # (iterations) but no parameters. It must return a list with these values.
                case {"name": "boolean.TimeLogicalOps.time_or_scalar"}:
                    assert res.stats == {
                        "data": [
                            1.6370204791373757e-05,
                            1.64747757895297e-05,
                            1.6352142014517064e-05,
                            1.6375186853806846e-05,
                            1.6442887910143355e-05,
                            1.633370702185561e-05,
                            1.6333956644843892e-05,
                            1.6291790719454486e-05,
                            1.6286434983849937e-05,
                            1.6278026913333076e-05,
                        ],
                        "unit": "s",
                        "iterations": 10,
                    }
                # Benchmark array.ArrowStringArray.time_setitem_slice uses samples
                # and parameters
                case {
                    "name": "array.ArrowStringArray.time_setitem_slice",
                    "multiple_chunks": "False",
                }:
                    assert len(res.stats["data"]) == 10
                case {
                    "name": "array.ArrowStringArray.time_setitem_slice",
                    "multiple_chunks": "True",
                }:
                    assert len(res.stats["data"]) == 10

                # Benchmark algorithms.SortIntegerArray.time_argsort tests that
                # NaN results still generate the rest for the data and the adapter
                # doesn't break. (A very common case).
                case {
                    "name": "algorithms.SortIntegerArray.time_argsort",
                    "param1": "1000",
                }:
                    assert res.stats["data"] == [9.382720887127119e-06]
                case {
                    "name": "algorithms.SortIntegerArray.time_argsort",
                    "param1": "100000",
                }:
                    assert res.stats["data"] == [0.0008135993461669737]

                # Benchmark series_methods.ToFrame.time_to_frame tests that
                # a parameter or case is not called "name". (This was generating a bug).
                case {
                    "name": "series_methods.ToFrame.time_to_frame",
                    "dtype": "'int64'",
                    "name_": "'foo'",
                }:
                    assert res.stats["data"] == [1.495111301503055e-05]
                case {
                    "name": "series_methods.ToFrame.time_to_frame",
                    "dtype": "'int64'",
                    "name_": "None",
                }:
                    assert res.stats["data"] == [1.4953170287206877e-05]
                # A result may pass the test of len above (the number of results)
                # but here checking that the names of benchmarks are still correct.
                case _:
                    assert False

    def test_run(self, asv_adapter) -> None:
        results = asv_adapter.run()
        assert len(results) == 9
