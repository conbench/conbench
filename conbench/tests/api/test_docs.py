import ast
import os
import subprocess

from openapi_spec_validator import validate_spec

from ...tests.api import _asserts

this_dir = os.path.abspath(os.path.dirname(__file__))


class TestDocs(_asserts.ApiEndpointTest):
    def test_docs(self, client):
        response = client.get("/api/docs.json")
        path = os.path.join(this_dir, "_expected_docs.py")

        with open(path) as f:
            expected_docs = ast.literal_eval(f.read())

        try:
            self.assert_200_ok(response, expected_docs)
        except AssertionError:
            if os.getenv("CI"):
                raise RuntimeError(
                    "The 'CI' env var was set so we're assuming this test was run in "
                    f"CI. However, {path} was not updated with the latest docs "
                    "changes. Run `pytest conbench/tests/api/test_docs.py` locally to "
                    "fix the file automatically."
                )
            # update expected docs on API changes
            # (onus is on devs to review diff)
            with open(path, "w") as f:
                f.write(str(response.json))
            subprocess.run(["black", path])

        with open(path) as f:
            expected_docs = ast.literal_eval(f.read())
        validate_spec(expected_docs)
