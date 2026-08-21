from __future__ import annotations

from collections.abc import Mapping
from typing import TYPE_CHECKING, Any, Self, TypeVar

from attrs import define as _attrs_define

from ..types import UNSET, Unset

if TYPE_CHECKING:
    from ..models.compare_analysis import CompareAnalysis
    from ..models.compare_side import CompareSide


T = TypeVar("T", bound="CompareResult")


@_attrs_define
class CompareResult:
    """
    Attributes:
        analysis (CompareAnalysis):
        baseline (CompareSide):
        contender (CompareSide):
        less_is_better (bool):
        unit (str):
        schema (str | Unset): A URL to the JSON Schema for this object.
    """

    analysis: CompareAnalysis
    baseline: CompareSide
    contender: CompareSide
    less_is_better: bool
    unit: str
    schema: str | Unset = UNSET

    def to_dict(self) -> dict[str, Any]:
        analysis = self.analysis.to_dict()

        baseline = self.baseline.to_dict()

        contender = self.contender.to_dict()

        less_is_better = self.less_is_better

        unit = self.unit

        schema = self.schema

        field_dict: dict[str, Any] = {}

        field_dict.update(
            {
                "analysis": analysis,
                "baseline": baseline,
                "contender": contender,
                "less_is_better": less_is_better,
                "unit": unit,
            }
        )
        if schema is not UNSET:
            field_dict["$schema"] = schema

        return field_dict

    @classmethod
    def from_dict(cls, src_dict: Mapping[str, Any]) -> Self:
        from ..models.compare_analysis import CompareAnalysis
        from ..models.compare_side import CompareSide

        d = dict(src_dict)
        analysis = CompareAnalysis.from_dict(d.pop("analysis"))

        baseline = CompareSide.from_dict(d.pop("baseline"))

        contender = CompareSide.from_dict(d.pop("contender"))

        less_is_better = d.pop("less_is_better")

        unit = d.pop("unit")

        schema = d.pop("$schema", UNSET)

        compare_result = cls(
            analysis=analysis,
            baseline=baseline,
            contender=contender,
            less_is_better=less_is_better,
            unit=unit,
            schema=schema,
        )

        return compare_result
