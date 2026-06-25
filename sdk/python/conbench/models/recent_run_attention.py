from __future__ import annotations

from collections.abc import Mapping
from typing import TYPE_CHECKING, Any, TypeVar

from attrs import define as _attrs_define

from ..models.recent_run_attention_status import RecentRunAttentionStatus

if TYPE_CHECKING:
    from ..models.recent_run_attention_summary import RecentRunAttentionSummary


T = TypeVar("T", bound="RecentRunAttention")


@_attrs_define
class RecentRunAttention:
    """
    Attributes:
        report_url (str):
        status (RecentRunAttentionStatus):
        status_reason (str):
        summary (RecentRunAttentionSummary):
    """

    report_url: str
    status: RecentRunAttentionStatus
    status_reason: str
    summary: RecentRunAttentionSummary

    def to_dict(self) -> dict[str, Any]:
        report_url = self.report_url

        status = self.status.value

        status_reason = self.status_reason

        summary = self.summary.to_dict()

        field_dict: dict[str, Any] = {}

        field_dict.update(
            {
                "report_url": report_url,
                "status": status,
                "status_reason": status_reason,
                "summary": summary,
            }
        )

        return field_dict

    @classmethod
    def from_dict(cls: type[T], src_dict: Mapping[str, Any]) -> T:
        from ..models.recent_run_attention_summary import RecentRunAttentionSummary

        d = dict(src_dict)
        report_url = d.pop("report_url")

        status = RecentRunAttentionStatus(d.pop("status"))

        status_reason = d.pop("status_reason")

        summary = RecentRunAttentionSummary.from_dict(d.pop("summary"))

        recent_run_attention = cls(
            report_url=report_url,
            status=status,
            status_reason=status_reason,
            summary=summary,
        )

        return recent_run_attention
