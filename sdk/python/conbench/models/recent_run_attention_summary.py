from __future__ import annotations

from collections.abc import Mapping
from typing import Any, TypeVar

from attrs import define as _attrs_define

T = TypeVar("T", bound="RecentRunAttentionSummary")


@_attrs_define
class RecentRunAttentionSummary:
    """
    Attributes:
        benchmark_errors (int):
        compared (int):
        missing_baseline (int):
        not_comparable (int):
        regressions (int):
    """

    benchmark_errors: int
    compared: int
    missing_baseline: int
    not_comparable: int
    regressions: int

    def to_dict(self) -> dict[str, Any]:
        benchmark_errors = self.benchmark_errors

        compared = self.compared

        missing_baseline = self.missing_baseline

        not_comparable = self.not_comparable

        regressions = self.regressions

        field_dict: dict[str, Any] = {}

        field_dict.update(
            {
                "benchmark_errors": benchmark_errors,
                "compared": compared,
                "missing_baseline": missing_baseline,
                "not_comparable": not_comparable,
                "regressions": regressions,
            }
        )

        return field_dict

    @classmethod
    def from_dict(cls: type[T], src_dict: Mapping[str, Any]) -> T:
        d = dict(src_dict)
        benchmark_errors = d.pop("benchmark_errors")

        compared = d.pop("compared")

        missing_baseline = d.pop("missing_baseline")

        not_comparable = d.pop("not_comparable")

        regressions = d.pop("regressions")

        recent_run_attention_summary = cls(
            benchmark_errors=benchmark_errors,
            compared=compared,
            missing_baseline=missing_baseline,
            not_comparable=not_comparable,
            regressions=regressions,
        )

        return recent_run_attention_summary
