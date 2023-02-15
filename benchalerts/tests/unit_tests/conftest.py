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
        monkeypatch.setenv("GITHUB_API_TOKEN", "token")
        monkeypatch.delenv("GITHUB_APP_ID", raising=False)
        monkeypatch.delenv("GITHUB_APP_PRIVATE_KEY", raising=False)

    elif auth_type == "app":
        monkeypatch.delenv("GITHUB_API_TOKEN", raising=False)
        monkeypatch.setenv("GITHUB_APP_ID", "123456")
        # this is fake but conforms to standards
        monkeypatch.setenv(
            "GITHUB_APP_PRIVATE_KEY",
            """-----BEGIN RSA PRIVATE KEY-----
MIIBOgIBAAJBAKj34GkxFhD90vcNLYLInFEX6Ppy1tPf9Cnzj4p4WGeKLs1Pt8Qu
KUpRKfFLfRYC9AIKjbJTWit+CqvjWYzvQwECAwEAAQJAIJLixBy2qpFoS4DSmoEm
o3qGy0t6z09AIJtH+5OeRV1be+N4cDYJKffGzDa88vQENZiRm0GRq6a+HPGQMd2k
TQIhAKMSvzIBnni7ot/OSie2TmJLY4SwTQAevXysE2RbFDYdAiEBCUEaRQnMnbp7
9mxDXDf6AU0cN/RPBjb9qSHDcWZHGzUCIG2Es59z8ugGrDY+pxLQnwfotadxd+Uy
v/Ow5T0q5gIJAiEAyS4RaI9YG8EWx/2w0T67ZUVAw8eOMB6BIUg0Xcu+3okCIBOs
/5OiPgoTdSy7bcF9IGpSE8ZgGKzgYQVZeN97YE00
-----END RSA PRIVATE KEY-----""",
        )

    elif auth_type == "none":
        monkeypatch.delenv("GITHUB_API_TOKEN", raising=False)
        monkeypatch.delenv("GITHUB_APP_ID", raising=False)
        monkeypatch.delenv("GITHUB_APP_PRIVATE_KEY", raising=False)

    return auth_type


@pytest.fixture
def conbench_env(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("CONBENCH_URL", "https://conbench.biz")
    monkeypatch.setenv("CONBENCH_EMAIL", "email")
    monkeypatch.setenv("CONBENCH_PASSWORD", "password")


@pytest.fixture
def missing_conbench_env(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.delenv("CONBENCH_URL", raising=False)
    monkeypatch.delenv("CONBENCH_EMAIL", raising=False)
    monkeypatch.delenv("CONBENCH_PASSWORD", raising=False)
