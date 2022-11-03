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
