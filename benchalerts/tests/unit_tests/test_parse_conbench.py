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

import pathlib
from copy import deepcopy

import pytest
from _pytest.fixtures import SubRequest

from benchalerts.clients import CheckStatus
from benchalerts.parse_conbench import (
    benchmarks_with_errors,
    benchmarks_with_z_regressions,
    regression_check_status,
    regression_details,
    regression_summary,
)
from benchalerts.talk_to_conbench import RunComparison

from .mocks import MockResponse, response_dir


@pytest.fixture
def mock_comparisons(request: SubRequest):
    how: str = request.param

    def _response(basename: str):
        """Get a mocked response."""
        filename = basename + ".json"
        return MockResponse.from_file(response_dir / filename).json()

    def _dup_info(basename: str):
        """Get a mocked response and duplicate it with a different ID."""
        info = _response(basename)
        info_2 = deepcopy(info)
        info_2["id"] += "_2"
        return info, info_2

    contender_info, contender_info_2 = _dup_info("GET_conbench_runs_some_contender")
    baseline_info, baseline_info_2 = _dup_info("GET_conbench_runs_some_baseline")
    no_baseline_info = _response("GET_conbench_runs_contender_wo_base")
    compare_results_noregressions = _response(
        "GET_conbench_compare_runs_some_baseline_some_contender_threshold_z_500"
    )
    compare_results_regressions = _response(
        "GET_conbench_compare_runs_some_baseline_some_contender"
    )
    benchmark_results = _response("GET_conbench_benchmarks_run_id_contender_wo_base")

    if how == "noregressions":
        return [
            RunComparison(
                contender_info=contender_info,
                baseline_info=baseline_info,
                compare_results=compare_results_noregressions,
            ),
            RunComparison(
                contender_info=contender_info_2,
                baseline_info=baseline_info_2,
                compare_results=compare_results_noregressions,
            ),
        ]
    elif how == "regressions":
        return [
            RunComparison(
                contender_info=contender_info,
                baseline_info=baseline_info,
                compare_results=compare_results_regressions,
            ),
            RunComparison(
                contender_info=contender_info_2,
                baseline_info=baseline_info_2,
                compare_results=compare_results_regressions,
            ),
        ]
    elif how == "no_baseline_without_errors":
        no_baseline_info["has_errors"] = False
        benchmark_results[1]["error"] = None
        return [
            RunComparison(
                contender_info=no_baseline_info, benchmark_results=benchmark_results
            ),
        ]
    elif how == "no_baseline":
        return [
            RunComparison(
                contender_info=no_baseline_info, benchmark_results=benchmark_results
            ),
        ]


def get_expected_markdown(filename: str) -> str:
    if not filename:
        return None
    file = pathlib.Path(__file__).parent / "expected_md" / (filename + ".md")
    with open(file, "r") as f:
        return f.read()


@pytest.mark.parametrize(
    ["mock_comparisons", "expected_len"],
    [
        ("noregressions", 2),
        ("regressions", 2),
        ("no_baseline", 1),
        ("no_baseline_without_errors", 0),
    ],
    indirect=["mock_comparisons"],
)
def test_benchmarks_with_errors(mock_comparisons, expected_len):
    actual = benchmarks_with_errors(mock_comparisons)
    assert len(actual) == expected_len


@pytest.mark.parametrize(
    ["mock_comparisons", "expected_len"],
    [
        ("noregressions", 0),
        ("regressions", 2),
        ("no_baseline", 0),
        ("no_baseline_without_errors", 0),
    ],
    indirect=["mock_comparisons"],
)
def test_benchmarks_with_z_regressions(mock_comparisons, expected_len):
    actual = benchmarks_with_z_regressions(mock_comparisons)
    assert len(actual) == expected_len


@pytest.mark.parametrize(
    ["mock_comparisons", "expected_md"],
    [
        ("noregressions", "summary_noregressions"),
        ("regressions", "summary_regressions"),
        ("no_baseline", "summary_nobaseline"),
    ],
    indirect=["mock_comparisons"],
)
def test_regression_summary(mock_comparisons, expected_md):
    actual = regression_summary(mock_comparisons, warn_if_baseline_isnt_parent=True)
    expected = get_expected_markdown(expected_md)
    assert (
        actual.strip() == expected.strip()
    ), f"see tests/unit_tests/expected_md/{expected_md}.md"


@pytest.mark.parametrize(
    ["mock_comparisons", "expected_md"],
    [
        ("noregressions", "details_noregressions"),
        ("regressions", "details_regressions"),
        ("no_baseline", None),
        ("no_baseline_without_errors", None),
    ],
    indirect=["mock_comparisons"],
)
def test_regression_details(mock_comparisons, expected_md):
    actual = regression_details(mock_comparisons)
    expected = get_expected_markdown(expected_md)
    if expected:
        assert (
            actual.strip() == expected.strip()
        ), f"see tests/unit_tests/expected_md/{expected_md}.md"
    else:
        assert actual is expected


@pytest.mark.parametrize(
    ["mock_comparisons", "expected_status"],
    [
        ("noregressions", CheckStatus.SUCCESS),
        ("regressions", CheckStatus.FAILURE),
        ("no_baseline", CheckStatus.ACTION_REQUIRED),
        ("no_baseline_without_errors", CheckStatus.SKIPPED),
    ],
    indirect=["mock_comparisons"],
)
def test_regression_check_status(mock_comparisons, expected_status):
    assert regression_check_status(mock_comparisons) == expected_status
