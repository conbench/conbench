# Copyright (c) 2022, Voltron Data.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import os

import pytest

from benchalerts.clients import GitHubRepoClient


@pytest.mark.parametrize("github_auth", ["pat", "app"], indirect=True)
def test_create_pull_request_comment(github_auth: str):
    if os.getenv("CI"):
        pytest.skip("Don't post a PR comment from CI")

    gh = GitHubRepoClient("conbench/benchalerts")
    res = gh.create_pull_request_comment(
        "posted from an integration test", commit_sha="adc9b73"
    )
    if github_auth == "pat":
        assert res["user"]["type"] == "User"
    elif github_auth == "app":
        assert res["user"]["type"] == "Bot"
