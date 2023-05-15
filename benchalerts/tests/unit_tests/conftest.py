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

from benchalerts.conbench_dataclasses import FullComparisonInfo, RunComparisonInfo

from .mocks import MockResponse, response_dir


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
def mock_comparison_info(request: SubRequest) -> FullComparisonInfo:
    """Mock a FullComparisonInfo, like something that might be output from a
    GetConbenchZComparisonStep.

    Use this like
    @pytest.mark.parametrize(
        "mock_comparison_info",
        [
            "errors_baselines",
            "errors_nobaselines",
            "noerrors_nobaselines",
            "regressions",
            "noregressions",
            "nocommit",
            "noruns",
            "noresults",
        ],
        indirect=["mock_comparison_info"],
    )
    """
    how: str = request.param

    def _response(basename: str):
        """Get a mocked response."""
        filename = basename + ".json"
        return MockResponse.from_file(response_dir / filename).json()

    def _run(has_errors: bool, has_baseline: bool, has_commit: bool):
        """Get a mocked run response."""
        if not has_commit:
            run_id = "no_commit"
        elif has_baseline:
            run_id = "some_contender"
        else:
            run_id = "contender_wo_base"
        res = _response(f"GET_conbench_runs_{run_id}")
        res["has_errors"] = has_errors
        if res["commit"]:
            res["commit"]["sha"] = "abc"
        return res

    def _compare(has_errors: bool, has_regressions: bool):
        """Get a mocked compare response."""
        suffix = "" if has_regressions else "_threshold_z_500"
        res = _response(
            f"GET_conbench_compare_runs_some_baseline_some_contender{suffix}"
        )
        if not has_errors:
            for result in res:
                result["contender"]["error"] = None
        return res

    def _results(has_errors: bool):
        """Get a mocked benchmark results response."""
        res = _response("GET_conbench_benchmark-results_run_id_contender_wo_base")
        if not has_errors:
            for result in res:
                result["error"] = None
        return res

    if how == "errors_baselines":
        return FullComparisonInfo(
            [
                RunComparisonInfo(
                    contender_info=_run(
                        has_errors=True, has_baseline=True, has_commit=True
                    ),
                    baseline_run_type="parent",
                    compare_results=_compare(has_errors=True, has_regressions=True),
                    benchmark_results=None,
                )
            ]
            * 3
        )
    if how == "errors_nobaselines":
        return FullComparisonInfo(
            [
                RunComparisonInfo(
                    contender_info=_run(
                        has_errors=True, has_baseline=False, has_commit=True
                    ),
                    baseline_run_type="parent",
                    compare_results=None,
                    benchmark_results=_results(has_errors=True),
                )
            ]
            * 2
        )
    if how == "noerrors_nobaselines":
        return FullComparisonInfo(
            [
                RunComparisonInfo(
                    contender_info=_run(
                        has_errors=False, has_baseline=False, has_commit=True
                    ),
                    baseline_run_type="parent",
                    compare_results=None,
                    benchmark_results=_results(has_errors=False),
                )
            ]
            * 2
        )
    if how == "regressions":
        return FullComparisonInfo(
            [
                RunComparisonInfo(
                    contender_info=_run(
                        has_errors=False, has_baseline=False, has_commit=True
                    ),
                    baseline_run_type="parent",
                    compare_results=None,
                    benchmark_results=_results(has_errors=False),
                ),
                RunComparisonInfo(
                    contender_info=_run(
                        has_errors=False, has_baseline=True, has_commit=True
                    ),
                    baseline_run_type="parent",
                    compare_results=_compare(has_errors=False, has_regressions=True),
                    benchmark_results=None,
                ),
                RunComparisonInfo(
                    contender_info=_run(
                        has_errors=False, has_baseline=True, has_commit=True
                    ),
                    baseline_run_type="parent",
                    compare_results=_compare(has_errors=False, has_regressions=True),
                    benchmark_results=None,
                ),
            ]
        )
    if how == "noregressions":
        return FullComparisonInfo(
            [
                RunComparisonInfo(
                    contender_info=_run(
                        has_errors=False, has_baseline=True, has_commit=True
                    ),
                    baseline_run_type="parent",
                    compare_results=_compare(has_errors=False, has_regressions=False),
                    benchmark_results=None,
                )
            ]
            * 2
        )
    if how == "nocommit":
        return FullComparisonInfo(
            [
                RunComparisonInfo(
                    contender_info=_run(
                        has_errors=False, has_baseline=False, has_commit=False
                    ),
                    baseline_run_type="latest_default",
                    compare_results=_compare(has_errors=False, has_regressions=False),
                    benchmark_results=None,
                )
            ]
            * 2
        )
    if how == "noruns":
        return FullComparisonInfo([])
    if how == "noresults":
        return FullComparisonInfo(
            [
                RunComparisonInfo(
                    contender_info=_run(
                        has_errors=False, has_baseline=False, has_commit=True
                    ),
                    baseline_run_type="parent",
                    compare_results=None,
                    benchmark_results=[],
                )
            ]
        )
