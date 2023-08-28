import json
import shutil

import pytest
from benchadapt.result import BenchmarkResult
from click.testing import CliRunner

from benchconnect._augment import augment_blob, result

minimal_result = {"stats": {"data": [1, 2], "unit": "s"}}


@pytest.fixture
def mock_github_env_vars(monkeypatch):
    monkeypatch.setenv("CONBENCH_PROJECT_REPOSITORY", "conchair/conchair")
    monkeypatch.setenv("CONBENCH_PROJECT_COMMIT", "fake-commit-hash")


def test_augment_blob(mock_github_env_vars):
    augmented_blob = augment_blob(minimal_result, cls=BenchmarkResult)
    assert augmented_blob.keys() > minimal_result.keys()


class TestCliAugment:
    runner = CliRunner()

    def test_help(self) -> None:
        res = self.runner.invoke(result, args=["--help"])
        assert res.exit_code == 0
        assert res.output

    def test_json(self, mock_github_env_vars):
        res = self.runner.invoke(result, args=["--json", json.dumps(minimal_result)])
        assert res.exit_code == 0
        augmented_blob = json.loads(res.output)
        assert augmented_blob.keys() > minimal_result.keys()

    def test_path(self, tmpdir, mock_github_env_vars):
        tempjson1 = tmpdir / "file1.json"
        tempjson2 = tmpdir / "file2.json"

        for path in [tempjson1, tempjson2]:
            with open(path, "w") as f:
                json.dump(minimal_result, f)

        # file path
        res = self.runner.invoke(result, args=["--path", tempjson1])
        assert res.exit_code == 0
        augmented_blob = json.loads(res.output)
        assert augmented_blob.keys() > minimal_result.keys()

        # directory path
        res = self.runner.invoke(result, args=["--path", tmpdir])
        assert res.exit_code == 0

        for blob in res.output.splitlines():
            augmented_blob = json.loads(blob)
            assert augmented_blob.keys() > minimal_result.keys()

        shutil.rmtree(tmpdir, ignore_errors=True)
