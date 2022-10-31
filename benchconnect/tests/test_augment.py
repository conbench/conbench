import json
import shutil
from typing import Callable

import pytest
from benchadapt.result import BenchmarkResult
from benchadapt.run import BenchmarkRun
from click.testing import CliRunner

from benchconnect._augment import augment_blob, result, run

minimal_result = {"stats": {"data": [1, 2], "unit": "s"}}
minimal_run = {}


@pytest.mark.parametrize(
    "params", [(minimal_result, BenchmarkResult), (minimal_run, BenchmarkRun)]
)
def test_augment_blob(params):
    raw_blob, cls = params
    augmented_blob = augment_blob(raw_blob, cls=cls)
    assert augmented_blob.keys() > raw_blob.keys()


class TestCliAugment:
    runner = CliRunner()

    @pytest.mark.parametrize("command", [result, run])
    def test_help(self, command: Callable) -> None:
        res = self.runner.invoke(command, args=["--help"])
        assert res.exit_code == 0
        assert res.output

    @pytest.mark.parametrize("params", [(result, minimal_result), (run, minimal_run)])
    def test_json(self, params: tuple):
        command, raw_blob = params

        res = self.runner.invoke(command, args=["--json", json.dumps(raw_blob)])
        assert res.exit_code == 0
        augmented_blob = json.loads(res.output)
        assert augmented_blob.keys() > raw_blob.keys()

    @pytest.mark.parametrize("params", [(result, minimal_result), (run, minimal_run)])
    def test_path(self, params: tuple, tmpdir):
        command, raw_blob = params

        tempjson1 = tmpdir / "file1.json"
        tempjson2 = tmpdir / "file2.json"

        for path in [tempjson1, tempjson2]:
            with open(path, "w") as f:
                json.dump(raw_blob, f)

        # file path
        res = self.runner.invoke(command, args=["--path", tempjson1])
        assert res.exit_code == 0
        augmented_blob = json.loads(res.output)
        assert augmented_blob.keys() > raw_blob.keys()

        # directory path
        res = self.runner.invoke(command, args=["--path", tmpdir])
        assert res.exit_code == 0

        for blob in res.output.splitlines():
            augmented_blob = json.loads(blob)
            assert augmented_blob.keys() > raw_blob.keys()

        shutil.rmtree(tmpdir, ignore_errors=True)
