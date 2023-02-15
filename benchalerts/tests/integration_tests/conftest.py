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
from _pytest.fixtures import SubRequest


@pytest.fixture
def github_auth(request: SubRequest, monkeypatch: pytest.MonkeyPatch) -> str:
    """Sets the correct env vars based on the requested GitHub auth type.

    You can do @pytest.mark.parametrize("github_auth", ["pat", "app"], indirect=True)
    to paramatrize this fixture.
    """
    auth_type = request.param

    if auth_type == "pat":
        if not os.getenv("GITHUB_API_TOKEN"):
            pytest.skip("GITHUB_API_TOKEN not found")
        monkeypatch.delenv("GITHUB_APP_ID", raising=False)
        monkeypatch.delenv("GITHUB_APP_PRIVATE_KEY", raising=False)

    elif auth_type == "app":
        if not os.getenv("GITHUB_APP_ID") or not os.getenv("GITHUB_APP_PRIVATE_KEY"):
            pytest.skip("GITHUB_APP_ID or GITHUB_APP_PRIVATE_KEY not found")
        monkeypatch.delenv("GITHUB_API_TOKEN", raising=False)

    return auth_type
