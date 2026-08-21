from __future__ import annotations

from collections.abc import Mapping
from typing import Any, Self, TypeVar

from attrs import define as _attrs_define

from ..types import UNSET, Unset

T = TypeVar("T", bound="CIReportRowLinks")


@_attrs_define
class CIReportRowLinks:
    """
    Attributes:
        result (str):
        series (str):
        compare (str | Unset):
    """

    result: str
    series: str
    compare: str | Unset = UNSET

    def to_dict(self) -> dict[str, Any]:
        result = self.result

        series = self.series

        compare = self.compare

        field_dict: dict[str, Any] = {}

        field_dict.update(
            {
                "result": result,
                "series": series,
            }
        )
        if compare is not UNSET:
            field_dict["compare"] = compare

        return field_dict

    @classmethod
    def from_dict(cls, src_dict: Mapping[str, Any]) -> Self:
        d = dict(src_dict)
        result = d.pop("result")

        series = d.pop("series")

        compare = d.pop("compare", UNSET)

        ci_report_row_links = cls(
            result=result,
            series=series,
            compare=compare,
        )

        return ci_report_row_links
