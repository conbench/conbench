from __future__ import annotations

import importlib.util
import os
from pathlib import Path
import sys
import types
import unittest
from unittest import mock


MODULE_PATH = Path(__file__).with_name("github.py")
SPEC = importlib.util.spec_from_file_location("migration_github", MODULE_PATH)
assert SPEC is not None
assert SPEC.loader is not None
github = importlib.util.module_from_spec(SPEC)
sys.modules.setdefault("requests", types.SimpleNamespace(get=None))
SPEC.loader.exec_module(github)


class GitHubHTTPAPIClientTest(unittest.TestCase):
    def test_auth_header_uses_first_valid_token_from_pool(self) -> None:
        with mock.patch.dict(os.environ, {"GITHUB_API_TOKEN": "bad, first-valid-token , second-valid-token"}):
            client = github.GitHubHTTPAPIClient()

        self.assertEqual(client.auth_header, {"Authorization": "Bearer first-valid-token"})


if __name__ == "__main__":
    unittest.main()
