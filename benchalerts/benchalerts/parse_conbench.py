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

import textwrap
from dataclasses import dataclass
from typing import List

from .clients import CheckStatus
from .talk_to_conbench import RunComparison


def _clean(text: str) -> str:
    """Clean text so it displays nicely as GitHub Markdown."""
    return textwrap.fill(textwrap.dedent(text), 10000).replace("  ", "\n\n").strip()


@dataclass
class _CaseInfo:
    run_id: str
    run_reason: str
    run_time: str
    run_link: str
    case_name: str
    case_link: str

    @property
    def Run_Reason(self):
        return self.run_reason.title()


def _list_cases(case_infos: List[_CaseInfo]) -> str:
    """Create a Markdown list of case information."""
    out = ""
    previous_run_id = ""

    for case in case_infos:
        if case.run_id != previous_run_id:
            out += f"\n\n- {case.Run_Reason} Run at [{case.run_time}]({case.run_link})"
            previous_run_id = case.run_id
        out += f"\n  - [{case.case_name}]({case.case_link})"

    if out:
        out += "\n\n"

    return out


def benchmarks_with_errors(comparisons: List[RunComparison]) -> List[_CaseInfo]:
    """Find information about benchmark cases that had errors."""
    out = []

    for comparison in comparisons:
        if comparison.compare_results:
            out += [
                _CaseInfo(
                    run_id=comparison.contender_id,
                    run_reason=comparison.contender_reason,
                    run_time=comparison.contender_datetime,
                    run_link=comparison.compare_link,
                    case_name=case["benchmark"],
                    case_link=comparison.case_link(case["contender_id"]),
                )
                for case in comparison.compare_results
                if case["contender_error"]
            ]
        elif comparison.benchmark_results:
            out += [
                _CaseInfo(
                    run_id=comparison.contender_id,
                    run_reason=comparison.contender_reason,
                    run_time=comparison.contender_datetime,
                    run_link=comparison.contender_link,
                    case_name=case["tags"].get("name", str(case["tags"])),
                    case_link=comparison.case_link(case["id"]),
                )
                for case in comparison.benchmark_results
                if case["error"]
            ]

    return out


def benchmarks_with_z_regressions(comparisons: List[RunComparison]) -> List[_CaseInfo]:
    """Find information about benchmark cases whose z-scores were extreme enough to
    constitute a regression.
    """
    out = []

    for comparison in comparisons:
        if comparison.compare_results:
            out += [
                _CaseInfo(
                    run_id=comparison.contender_id,
                    run_reason=comparison.contender_reason,
                    run_time=comparison.contender_datetime,
                    run_link=comparison.compare_link,
                    case_name=case["benchmark"],
                    case_link=comparison.case_link(case["contender_id"]),
                )
                for case in comparison.compare_results
                if case["contender_z_regression"]
            ]

    return out


def regression_summary(
    comparisons: List[RunComparison], warn_if_baseline_isnt_parent: bool
) -> str:
    """Generate a Markdown summary of what happened regarding errors and regressions."""
    sha = comparisons[0].contender_info["commit"]["sha"][:8]
    errors = benchmarks_with_errors(comparisons)
    regressions = benchmarks_with_z_regressions(comparisons)
    summary = ""

    if errors:
        summary += _clean(
            """
            ## Benchmarks with errors

            These are errors that were caught while running the benchmarks. You can
            click the link next to each case to go to the Conbench entry for that
            benchmark, which might have more information about what the error was.
            """
        )
        summary += _list_cases(errors)

    summary += "## Benchmarks with performance regressions\n\n"

    if not any(comparison.baseline_info for comparison in comparisons):
        summary += _clean(
            f"""
            Conbench could not find a baseline run for contender commit `{sha}`. A
            baseline run needs to be on the default branch in the same repository, with
            the same hardware and context, and have at least one of the same benchmark
            cases.
            """
        )
        return summary

    summary += _clean(
        f"""
        Contender commit `{sha}` had {len(regressions)} performance regression(s)
        compared to its baseline commit.
        """
    )
    summary += "\n\n"

    if regressions:
        summary += "### Benchmarks with regressions:"
        summary += _list_cases(regressions)

    if (
        any(not comparison.baseline_is_parent for comparison in comparisons)
        and warn_if_baseline_isnt_parent
    ):
        summary += _clean(
            """
            ### Note

            The baseline commit was not the immediate parent of the contender commit.
            See the link below for details.
            """
        )

    return summary


def regression_details(comparisons: List[RunComparison]) -> str:
    """Generate Markdown details of what happened regarding regressions."""
    if not any(comparison.baseline_info for comparison in comparisons):
        return None

    z_score_threshold = comparisons[0].compare_results[0]["threshold_z"]
    details = _clean(
        f"""
        Conbench has details about {len(comparisons)} total run(s) on this commit.

        This report was generated using a z-score threshold of {z_score_threshold}. A
        regression is defined as a benchmark exhibiting a z-score higher than the
        threshold in the "bad" direction (e.g. down for iterations per second; up for
        total time taken).
        """
    )
    return details


def regression_check_status(
    comparisons: List[RunComparison],
) -> CheckStatus:
    """Return a different status based on errors and regressions."""
    regressions = benchmarks_with_z_regressions(comparisons)

    if any(comparison.has_errors for comparison in comparisons):
        # has errors
        return CheckStatus.ACTION_REQUIRED
    if not any(comparison.baseline_info for comparison in comparisons):
        # no baseline runs found
        return CheckStatus.SKIPPED
    elif regressions:
        # at least one regression
        return CheckStatus.FAILURE
    else:
        # no regressions
        return CheckStatus.SUCCESS
