from __future__ import annotations

from collections.abc import Mapping
from typing import Any, Self, TypeVar

from attrs import define as _attrs_define

T = TypeVar("T", bound="LookbackAnalysisType0")


@_attrs_define
class LookbackAnalysisType0:
    """
    Attributes:
        improvement_indicated (bool):
        regression_indicated (bool):
        z_score (float):
        z_threshold (float):
    """

    improvement_indicated: bool
    regression_indicated: bool
    z_score: float
    z_threshold: float

    def to_dict(self) -> dict[str, Any]:
        improvement_indicated = self.improvement_indicated

        regression_indicated = self.regression_indicated

        z_score = self.z_score

        z_threshold = self.z_threshold

        field_dict: dict[str, Any] = {}

        field_dict.update(
            {
                "improvement_indicated": improvement_indicated,
                "regression_indicated": regression_indicated,
                "z_score": z_score,
                "z_threshold": z_threshold,
            }
        )

        return field_dict

    @classmethod
    def from_dict(cls, src_dict: Mapping[str, Any]) -> Self:
        d = dict(src_dict)
        improvement_indicated = d.pop("improvement_indicated")

        regression_indicated = d.pop("regression_indicated")

        z_score = d.pop("z_score")

        z_threshold = d.pop("z_threshold")

        lookback_analysis_type_0 = cls(
            improvement_indicated=improvement_indicated,
            regression_indicated=regression_indicated,
            z_score=z_score,
            z_threshold=z_threshold,
        )

        return lookback_analysis_type_0
