from __future__ import annotations

from collections.abc import Mapping
from typing import Any, TypeVar

from attrs import define as _attrs_define

T = TypeVar("T", bound="CIReportSummary")


@_attrs_define
class CIReportSummary:
    """
    Attributes:
        analyzed (int):
        benchmark_errors (int):
        compared (int):
        contender_results (int):
        improvements (int):
        missing_baseline (int):
        missing_runs (int):
        not_comparable (int):
        regressions (int):
        runs (int):
    """

    analyzed: int
    benchmark_errors: int
    compared: int
    contender_results: int
    improvements: int
    missing_baseline: int
    missing_runs: int
    not_comparable: int
    regressions: int
    runs: int

    def to_dict(self) -> dict[str, Any]:
        analyzed = self.analyzed

        benchmark_errors = self.benchmark_errors

        compared = self.compared

        contender_results = self.contender_results

        improvements = self.improvements

        missing_baseline = self.missing_baseline

        missing_runs = self.missing_runs

        not_comparable = self.not_comparable

        regressions = self.regressions

        runs = self.runs

        field_dict: dict[str, Any] = {}

        field_dict.update(
            {
                "analyzed": analyzed,
                "benchmark_errors": benchmark_errors,
                "compared": compared,
                "contender_results": contender_results,
                "improvements": improvements,
                "missing_baseline": missing_baseline,
                "missing_runs": missing_runs,
                "not_comparable": not_comparable,
                "regressions": regressions,
                "runs": runs,
            }
        )

        return field_dict

    @classmethod
    def from_dict(cls: type[T], src_dict: Mapping[str, Any]) -> T:
        d = dict(src_dict)
        analyzed = d.pop("analyzed")

        benchmark_errors = d.pop("benchmark_errors")

        compared = d.pop("compared")

        contender_results = d.pop("contender_results")

        improvements = d.pop("improvements")

        missing_baseline = d.pop("missing_baseline")

        missing_runs = d.pop("missing_runs")

        not_comparable = d.pop("not_comparable")

        regressions = d.pop("regressions")

        runs = d.pop("runs")

        ci_report_summary = cls(
            analyzed=analyzed,
            benchmark_errors=benchmark_errors,
            compared=compared,
            contender_results=contender_results,
            improvements=improvements,
            missing_baseline=missing_baseline,
            missing_runs=missing_runs,
            not_comparable=not_comparable,
            regressions=regressions,
            runs=runs,
        )

        return ci_report_summary
