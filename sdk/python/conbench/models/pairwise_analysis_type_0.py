from __future__ import annotations

from collections.abc import Mapping
from typing import Any, Self, TypeVar

from attrs import define as _attrs_define

T = TypeVar("T", bound="PairwiseAnalysisType0")


@_attrs_define
class PairwiseAnalysisType0:
    """
    Attributes:
        improvement_indicated (bool):
        percent_change (float):
        percent_threshold (float):
        regression_indicated (bool):
    """

    improvement_indicated: bool
    percent_change: float
    percent_threshold: float
    regression_indicated: bool

    def to_dict(self) -> dict[str, Any]:
        improvement_indicated = self.improvement_indicated

        percent_change = self.percent_change

        percent_threshold = self.percent_threshold

        regression_indicated = self.regression_indicated

        field_dict: dict[str, Any] = {}

        field_dict.update(
            {
                "improvement_indicated": improvement_indicated,
                "percent_change": percent_change,
                "percent_threshold": percent_threshold,
                "regression_indicated": regression_indicated,
            }
        )

        return field_dict

    @classmethod
    def from_dict(cls, src_dict: Mapping[str, Any]) -> Self:
        d = dict(src_dict)
        improvement_indicated = d.pop("improvement_indicated")

        percent_change = d.pop("percent_change")

        percent_threshold = d.pop("percent_threshold")

        regression_indicated = d.pop("regression_indicated")

        pairwise_analysis_type_0 = cls(
            improvement_indicated=improvement_indicated,
            percent_change=percent_change,
            percent_threshold=percent_threshold,
            regression_indicated=regression_indicated,
        )

        return pairwise_analysis_type_0
