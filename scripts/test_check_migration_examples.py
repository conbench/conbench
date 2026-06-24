import unittest
from pathlib import Path


class CheckMigrationExamplesTest(unittest.TestCase):
    def test_script_adds_repo_root_and_sdk_to_pythonpath(self) -> None:
        script = Path("scripts/check_migration_examples.sh").read_text(encoding="utf-8")

        self.assertIn('export PYTHONPATH="$root:$root/sdk/python"', script)


if __name__ == "__main__":
    unittest.main()
