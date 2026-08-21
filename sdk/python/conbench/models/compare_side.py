from __future__ import annotations

from collections.abc import Mapping
from typing import Any, Self, TypeVar

from attrs import define as _attrs_define

T = TypeVar("T", bound="CompareSide")


@_attrs_define
class CompareSide:
    """
    Attributes:
        benchmark_result_id (str):
        run_id (str):
        single_value_summary (float):
    """

    benchmark_result_id: str
    run_id: str
    single_value_summary: float

    def to_dict(self) -> dict[str, Any]:
        benchmark_result_id = self.benchmark_result_id

        run_id = self.run_id

        single_value_summary = self.single_value_summary

        field_dict: dict[str, Any] = {}

        field_dict.update(
            {
                "benchmark_result_id": benchmark_result_id,
                "run_id": run_id,
                "single_value_summary": single_value_summary,
            }
        )

        return field_dict

    @classmethod
    def from_dict(cls, src_dict: Mapping[str, Any]) -> Self:
        d = dict(src_dict)
        benchmark_result_id = d.pop("benchmark_result_id")

        run_id = d.pop("run_id")

        single_value_summary = d.pop("single_value_summary")

        compare_side = cls(
            benchmark_result_id=benchmark_result_id,
            run_id=run_id,
            single_value_summary=single_value_summary,
        )

        return compare_side
