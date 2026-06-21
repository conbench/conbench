import tarfile
import tempfile
import unittest
import zipfile
from pathlib import Path

from scripts.python_sdk_artifact_hygiene import (
    ArtifactHygieneError,
    find_retired_payload_members,
    validate_python_sdk_artifact,
)


class PythonSDKArtifactHygieneTest(unittest.TestCase):
    def test_finds_retired_package_directory_members(self) -> None:
        leaked = find_retired_payload_members(
            [
                "conbench-0.1.0/conbench/__init__.py",
                "conbench-0.1.0/benchadapt/__init__.py",
            ]
        )

        self.assertEqual(leaked, ["conbench-0.1.0/benchadapt/__init__.py"])

    def test_finds_retired_package_directory_entries(self) -> None:
        leaked = find_retired_payload_members(
            [
                "conbench-0.1.0/conbench",
                "conbench-0.1.0/benchconnect",
            ]
        )

        self.assertEqual(leaked, ["conbench-0.1.0/benchconnect"])

    def test_finds_retired_single_file_modules(self) -> None:
        leaked = find_retired_payload_members(
            [
                "conbench-0.1.0/conbench/__init__.py",
                "conbench-0.1.0/conbench_client.py",
            ]
        )

        self.assertEqual(leaked, ["conbench-0.1.0/conbench_client.py"])

    def test_accepts_clean_wheel(self) -> None:
        with tempfile.TemporaryDirectory(prefix="conbench-sdk-artifact-") as tmp:
            wheel = Path(tmp) / "conbench-0.1.0-py3-none-any.whl"
            with zipfile.ZipFile(wheel, "w") as archive:
                archive.writestr("conbench/__init__.py", "")

            validate_python_sdk_artifact(wheel)

    def test_rejects_retired_module_in_sdist(self) -> None:
        with tempfile.TemporaryDirectory(prefix="conbench-sdk-artifact-") as tmp:
            sdist = Path(tmp) / "conbench-0.1.0.tar.gz"
            leaked = Path(tmp) / "conbench_client.py"
            leaked.write_text("", encoding="utf-8")
            with tarfile.open(sdist, "w:gz") as archive:
                archive.add(leaked, arcname="conbench-0.1.0/conbench_client.py")

            with self.assertRaisesRegex(
                ArtifactHygieneError,
                "retired legacy package payload leaked into .*conbench-0.1.0.tar.gz",
            ):
                validate_python_sdk_artifact(sdist)


if __name__ == "__main__":
    unittest.main()
