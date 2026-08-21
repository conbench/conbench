from __future__ import annotations

from collections.abc import Mapping
from typing import TYPE_CHECKING, Any, Self, TypeVar, cast

from attrs import define as _attrs_define

from ..models.ci_report_comparison_status import CIReportComparisonStatus
from ..types import UNSET, Unset

if TYPE_CHECKING:
    from ..models.ci_report_analysis_type_0 import CIReportAnalysisType0
    from ..models.ci_report_baseline_side_type_0 import CIReportBaselineSideType0
    from ..models.ci_report_comparison_context import CIReportComparisonContext
    from ..models.ci_report_comparison_error_type_0 import CIReportComparisonErrorType0
    from ..models.ci_report_comparison_info import CIReportComparisonInfo
    from ..models.ci_report_comparison_tags import CIReportComparisonTags
    from ..models.ci_report_row_links import CIReportRowLinks
    from ..models.ci_report_side import CIReportSide
    from ..models.hardware import Hardware


T = TypeVar("T", bound="CIReportComparison")


@_attrs_define
class CIReportComparison:
    """
    Attributes:
        analysis (CIReportAnalysisType0 | None):
        baseline (CIReportBaselineSideType0 | None):
        contender (CIReportSide):
        context (CIReportComparisonContext):
        error (CIReportComparisonErrorType0 | None):
        hardware (Hardware):
        history_fingerprint (str):
        info (CIReportComparisonInfo):
        less_is_better (bool | None):
        links (CIReportRowLinks):
        name (str):
        status (CIReportComparisonStatus):
        tags (CIReportComparisonTags):
        unit (None | str):
        reason (str | Unset):
    """

    analysis: CIReportAnalysisType0 | None
    baseline: CIReportBaselineSideType0 | None
    contender: CIReportSide
    context: CIReportComparisonContext
    error: CIReportComparisonErrorType0 | None
    hardware: Hardware
    history_fingerprint: str
    info: CIReportComparisonInfo
    less_is_better: bool | None
    links: CIReportRowLinks
    name: str
    status: CIReportComparisonStatus
    tags: CIReportComparisonTags
    unit: None | str
    reason: str | Unset = UNSET

    def to_dict(self) -> dict[str, Any]:
        from ..models.ci_report_analysis_type_0 import CIReportAnalysisType0
        from ..models.ci_report_baseline_side_type_0 import CIReportBaselineSideType0
        from ..models.ci_report_comparison_error_type_0 import (
            CIReportComparisonErrorType0,
        )

        analysis: dict[str, Any] | None
        if isinstance(self.analysis, CIReportAnalysisType0):
            analysis = self.analysis.to_dict()
        else:
            analysis = self.analysis

        baseline: dict[str, Any] | None
        if isinstance(self.baseline, CIReportBaselineSideType0):
            baseline = self.baseline.to_dict()
        else:
            baseline = self.baseline

        contender = self.contender.to_dict()

        context = self.context.to_dict()

        error: dict[str, Any] | None
        if isinstance(self.error, CIReportComparisonErrorType0):
            error = self.error.to_dict()
        else:
            error = self.error

        hardware = self.hardware.to_dict()

        history_fingerprint = self.history_fingerprint

        info = self.info.to_dict()

        less_is_better: bool | None
        less_is_better = self.less_is_better

        links = self.links.to_dict()

        name = self.name

        status = self.status.value

        tags = self.tags.to_dict()

        unit: None | str
        unit = self.unit

        reason = self.reason

        field_dict: dict[str, Any] = {}

        field_dict.update(
            {
                "analysis": analysis,
                "baseline": baseline,
                "contender": contender,
                "context": context,
                "error": error,
                "hardware": hardware,
                "history_fingerprint": history_fingerprint,
                "info": info,
                "less_is_better": less_is_better,
                "links": links,
                "name": name,
                "status": status,
                "tags": tags,
                "unit": unit,
            }
        )
        if reason is not UNSET:
            field_dict["reason"] = reason

        return field_dict

    @classmethod
    def from_dict(cls, src_dict: Mapping[str, Any]) -> Self:
        from ..models.ci_report_analysis_type_0 import CIReportAnalysisType0
        from ..models.ci_report_baseline_side_type_0 import CIReportBaselineSideType0
        from ..models.ci_report_comparison_context import CIReportComparisonContext
        from ..models.ci_report_comparison_error_type_0 import (
            CIReportComparisonErrorType0,
        )
        from ..models.ci_report_comparison_info import CIReportComparisonInfo
        from ..models.ci_report_comparison_tags import CIReportComparisonTags
        from ..models.ci_report_row_links import CIReportRowLinks
        from ..models.ci_report_side import CIReportSide
        from ..models.hardware import Hardware

        d = dict(src_dict)

        def _parse_analysis(data: object) -> CIReportAnalysisType0 | None:
            if data is None:
                return data
            try:
                if not isinstance(data, dict):
                    raise TypeError()
                componentsschemas_ci_report_analysis_type_0 = (
                    CIReportAnalysisType0.from_dict(data)
                )

                return componentsschemas_ci_report_analysis_type_0
            except (TypeError, ValueError, AttributeError, KeyError):
                pass
            return cast(CIReportAnalysisType0 | None, data)

        analysis = _parse_analysis(d.pop("analysis"))

        def _parse_baseline(data: object) -> CIReportBaselineSideType0 | None:
            if data is None:
                return data
            try:
                if not isinstance(data, dict):
                    raise TypeError()
                componentsschemas_ci_report_baseline_side_type_0 = (
                    CIReportBaselineSideType0.from_dict(data)
                )

                return componentsschemas_ci_report_baseline_side_type_0
            except (TypeError, ValueError, AttributeError, KeyError):
                pass
            return cast(CIReportBaselineSideType0 | None, data)

        baseline = _parse_baseline(d.pop("baseline"))

        contender = CIReportSide.from_dict(d.pop("contender"))

        context = CIReportComparisonContext.from_dict(d.pop("context"))

        def _parse_error(data: object) -> CIReportComparisonErrorType0 | None:
            if data is None:
                return data
            try:
                if not isinstance(data, dict):
                    raise TypeError()
                error_type_0 = CIReportComparisonErrorType0.from_dict(data)

                return error_type_0
            except (TypeError, ValueError, AttributeError, KeyError):
                pass
            return cast(CIReportComparisonErrorType0 | None, data)

        error = _parse_error(d.pop("error"))

        hardware = Hardware.from_dict(d.pop("hardware"))

        history_fingerprint = d.pop("history_fingerprint")

        info = CIReportComparisonInfo.from_dict(d.pop("info"))

        def _parse_less_is_better(data: object) -> bool | None:
            if data is None:
                return data
            return cast(bool | None, data)

        less_is_better = _parse_less_is_better(d.pop("less_is_better"))

        links = CIReportRowLinks.from_dict(d.pop("links"))

        name = d.pop("name")

        status = CIReportComparisonStatus(d.pop("status"))

        tags = CIReportComparisonTags.from_dict(d.pop("tags"))

        def _parse_unit(data: object) -> None | str:
            if data is None:
                return data
            return cast(None | str, data)

        unit = _parse_unit(d.pop("unit"))

        reason = d.pop("reason", UNSET)

        ci_report_comparison = cls(
            analysis=analysis,
            baseline=baseline,
            contender=contender,
            context=context,
            error=error,
            hardware=hardware,
            history_fingerprint=history_fingerprint,
            info=info,
            less_is_better=less_is_better,
            links=links,
            name=name,
            status=status,
            tags=tags,
            unit=unit,
            reason=reason,
        )

        return ci_report_comparison
