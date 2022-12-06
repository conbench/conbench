import ast
import logging
import os

from openapi_spec_validator import validate_spec

from ...tests.api import _asserts

log = logging.getLogger(__name__)

this_dir = os.path.abspath(os.path.dirname(__file__))


class TestDocs(_asserts.ApiEndpointTest):
    def test_docs(self, client):
        response = client.get("/api/docs.json")

        path = os.path.join(this_dir, "_expected_docs.py")

        with open(path) as f:
            expected_docs = ast.literal_eval(f.read())

        try:
            # Note(JP): it seems that the hope here is that `assert_200_ok`
            # performs a deep object equality inspection, relying on the
            # `assert r.json == expected` equality check in the implementaion
            # of `assert_200_ok()`. But how deep is that, really? Typically,
            # the safest way to make sure that all details are after all equal
            # is to perform stable string serialization. What would we lose if
            # we were to compare JSON documents here?
            self.assert_200_ok(response, expected_docs)
        except AssertionError as exc:
            # Hoping that this shows a useful diff.
            log.info("caught assertion error: %s", exc)
            raise Exception(
                "/api/docs.json and _expected_docs.py are out of sync. "
                "Run `make rebuild-expected-api-docs` to regenerate "
                "_expected_docs.py and then review the diff manually."
            )

        # Maybe this is where we need a Python object structure, and not just
        # a JSON document.
        validate_spec(expected_docs)
