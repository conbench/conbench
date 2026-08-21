from __future__ import annotations

import datetime
from collections.abc import Mapping
from typing import Any, Self, TypeVar

from attrs import define as _attrs_define

from ..types import UNSET, Unset

T = TypeVar("T", bound="AlertEventView")


@_attrs_define
class AlertEventView:
    """
    Attributes:
        created_at (datetime.datetime):
        id (str):
        kind (str):
        report_url (str):
        repository (str):
        rule_id (str):
        status (str):
        status_reason (str):
        summary (Any):
        commit_sha (str | Unset):
        run_id (str | Unset):
    """

    created_at: datetime.datetime
    id: str
    kind: str
    report_url: str
    repository: str
    rule_id: str
    status: str
    status_reason: str
    summary: Any
    commit_sha: str | Unset = UNSET
    run_id: str | Unset = UNSET

    def to_dict(self) -> dict[str, Any]:
        created_at = self.created_at.isoformat()

        id = self.id

        kind = self.kind

        report_url = self.report_url

        repository = self.repository

        rule_id = self.rule_id

        status = self.status

        status_reason = self.status_reason

        summary = self.summary

        commit_sha = self.commit_sha

        run_id = self.run_id

        field_dict: dict[str, Any] = {}

        field_dict.update(
            {
                "created_at": created_at,
                "id": id,
                "kind": kind,
                "report_url": report_url,
                "repository": repository,
                "rule_id": rule_id,
                "status": status,
                "status_reason": status_reason,
                "summary": summary,
            }
        )
        if commit_sha is not UNSET:
            field_dict["commit_sha"] = commit_sha
        if run_id is not UNSET:
            field_dict["run_id"] = run_id

        return field_dict

    @classmethod
    def from_dict(cls, src_dict: Mapping[str, Any]) -> Self:
        d = dict(src_dict)
        created_at = datetime.datetime.fromisoformat(d.pop("created_at"))

        id = d.pop("id")

        kind = d.pop("kind")

        report_url = d.pop("report_url")

        repository = d.pop("repository")

        rule_id = d.pop("rule_id")

        status = d.pop("status")

        status_reason = d.pop("status_reason")

        summary = d.pop("summary")

        commit_sha = d.pop("commit_sha", UNSET)

        run_id = d.pop("run_id", UNSET)

        alert_event_view = cls(
            created_at=created_at,
            id=id,
            kind=kind,
            report_url=report_url,
            repository=repository,
            rule_id=rule_id,
            status=status,
            status_reason=status_reason,
            summary=summary,
            commit_sha=commit_sha,
            run_id=run_id,
        )

        return alert_event_view
