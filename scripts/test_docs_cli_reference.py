import tempfile
import unittest
from pathlib import Path

from scripts.docs_cli_reference import (
    CLIReferenceError,
    REQUIRED_CLI_REFERENCE_PHRASES,
    validate_cli_reference,
)


class DocsCLIReferenceTest(unittest.TestCase):
    def make_reference(self, omitted: set[str] | None = None) -> Path:
        tmp_handle = tempfile.TemporaryDirectory(prefix="conbench-docs-cli-reference-")
        self.addCleanup(tmp_handle.cleanup)
        path = Path(tmp_handle.name) / "cli-reference.md"
        omitted = omitted or set()
        text = "# CLI Reference\n\n" + "\n".join(
            phrase for phrase in REQUIRED_CLI_REFERENCE_PHRASES if phrase not in omitted
        )
        path.write_text(text, encoding="utf-8")
        return path

    def test_accepts_reference_with_required_cli_phrases(self) -> None:
        validate_cli_reference(self.make_reference())

    def test_reports_missing_result_get_command(self) -> None:
        missing = "conbench results get <id> --server URL"

        with self.assertRaisesRegex(CLIReferenceError, "missing CLI reference evidence: " + missing):
            validate_cli_reference(self.make_reference({missing}))

    def test_reports_missing_token_resolution_safety_note(self) -> None:
        missing = "prefer `CONBENCH_TOKEN` over `--token`"

        with self.assertRaisesRegex(CLIReferenceError, "missing CLI reference evidence: " + missing):
            validate_cli_reference(self.make_reference({missing}))

    def test_required_phrases_pin_cobra_command_framework(self) -> None:
        self.assertIn("The CLI uses Cobra", REQUIRED_CLI_REFERENCE_PHRASES)


if __name__ == "__main__":
    unittest.main()
