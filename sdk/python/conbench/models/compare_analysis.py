from __future__ import annotations

from collections.abc import Mapping
from typing import TYPE_CHECKING, Any, Self, TypeVar, cast

from attrs import define as _attrs_define

if TYPE_CHECKING:
    from ..models.lookback_analysis_type_0 import LookbackAnalysisType0
    from ..models.pairwise_analysis_type_0 import PairwiseAnalysisType0


T = TypeVar("T", bound="CompareAnalysis")


@_attrs_define
class CompareAnalysis:
    """
    Attributes:
        lookback_z_score (LookbackAnalysisType0 | None):
        pairwise (None | PairwiseAnalysisType0):
    """

    lookback_z_score: LookbackAnalysisType0 | None
    pairwise: None | PairwiseAnalysisType0

    def to_dict(self) -> dict[str, Any]:
        from ..models.lookback_analysis_type_0 import LookbackAnalysisType0
        from ..models.pairwise_analysis_type_0 import PairwiseAnalysisType0

        lookback_z_score: dict[str, Any] | None
        if isinstance(self.lookback_z_score, LookbackAnalysisType0):
            lookback_z_score = self.lookback_z_score.to_dict()
        else:
            lookback_z_score = self.lookback_z_score

        pairwise: dict[str, Any] | None
        if isinstance(self.pairwise, PairwiseAnalysisType0):
            pairwise = self.pairwise.to_dict()
        else:
            pairwise = self.pairwise

        field_dict: dict[str, Any] = {}

        field_dict.update(
            {
                "lookback_z_score": lookback_z_score,
                "pairwise": pairwise,
            }
        )

        return field_dict

    @classmethod
    def from_dict(cls, src_dict: Mapping[str, Any]) -> Self:
        from ..models.lookback_analysis_type_0 import LookbackAnalysisType0
        from ..models.pairwise_analysis_type_0 import PairwiseAnalysisType0

        d = dict(src_dict)

        def _parse_lookback_z_score(data: object) -> LookbackAnalysisType0 | None:
            if data is None:
                return data
            try:
                if not isinstance(data, dict):
                    raise TypeError()
                componentsschemas_lookback_analysis_type_0 = (
                    LookbackAnalysisType0.from_dict(data)
                )

                return componentsschemas_lookback_analysis_type_0
            except (TypeError, ValueError, AttributeError, KeyError):
                pass
            return cast(LookbackAnalysisType0 | None, data)

        lookback_z_score = _parse_lookback_z_score(d.pop("lookback_z_score"))

        def _parse_pairwise(data: object) -> None | PairwiseAnalysisType0:
            if data is None:
                return data
            try:
                if not isinstance(data, dict):
                    raise TypeError()
                componentsschemas_pairwise_analysis_type_0 = (
                    PairwiseAnalysisType0.from_dict(data)
                )

                return componentsschemas_pairwise_analysis_type_0
            except (TypeError, ValueError, AttributeError, KeyError):
                pass
            return cast(None | PairwiseAnalysisType0, data)

        pairwise = _parse_pairwise(d.pop("pairwise"))

        compare_analysis = cls(
            lookback_z_score=lookback_z_score,
            pairwise=pairwise,
        )

        return compare_analysis
