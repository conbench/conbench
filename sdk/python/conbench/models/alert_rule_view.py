from __future__ import annotations

import datetime
from collections.abc import Mapping
from typing import Any, Self, TypeVar

from attrs import define as _attrs_define

from ..types import UNSET, Unset

T = TypeVar("T", bound="AlertRuleView")


@_attrs_define
class AlertRuleView:
    """
    Attributes:
        baseline (str):
        created_at (datetime.datetime):
        enabled (bool):
        id (str):
        name (str):
        repository (str):
        state (str):
        threshold (float):
        threshold_z (float):
        updated_at (datetime.datetime):
        user_id (str):
        schema (str | Unset): A URL to the JSON Schema for this object.
        last_evaluated_at (datetime.datetime | Unset):
        run_reason (str | Unset):
    """

    baseline: str
    created_at: datetime.datetime
    enabled: bool
    id: str
    name: str
    repository: str
    state: str
    threshold: float
    threshold_z: float
    updated_at: datetime.datetime
    user_id: str
    schema: str | Unset = UNSET
    last_evaluated_at: datetime.datetime | Unset = UNSET
    run_reason: str | Unset = UNSET

    def to_dict(self) -> dict[str, Any]:
        baseline = self.baseline

        created_at = self.created_at.isoformat()

        enabled = self.enabled

        id = self.id

        name = self.name

        repository = self.repository

        state = self.state

        threshold = self.threshold

        threshold_z = self.threshold_z

        updated_at = self.updated_at.isoformat()

        user_id = self.user_id

        schema = self.schema

        last_evaluated_at: str | Unset = UNSET
        if not isinstance(self.last_evaluated_at, Unset):
            last_evaluated_at = self.last_evaluated_at.isoformat()

        run_reason = self.run_reason

        field_dict: dict[str, Any] = {}

        field_dict.update(
            {
                "baseline": baseline,
                "created_at": created_at,
                "enabled": enabled,
                "id": id,
                "name": name,
                "repository": repository,
                "state": state,
                "threshold": threshold,
                "threshold_z": threshold_z,
                "updated_at": updated_at,
                "user_id": user_id,
            }
        )
        if schema is not UNSET:
            field_dict["$schema"] = schema
        if last_evaluated_at is not UNSET:
            field_dict["last_evaluated_at"] = last_evaluated_at
        if run_reason is not UNSET:
            field_dict["run_reason"] = run_reason

        return field_dict

    @classmethod
    def from_dict(cls, src_dict: Mapping[str, Any]) -> Self:
        d = dict(src_dict)
        baseline = d.pop("baseline")

        created_at = datetime.datetime.fromisoformat(d.pop("created_at"))

        enabled = d.pop("enabled")

        id = d.pop("id")

        name = d.pop("name")

        repository = d.pop("repository")

        state = d.pop("state")

        threshold = d.pop("threshold")

        threshold_z = d.pop("threshold_z")

        updated_at = datetime.datetime.fromisoformat(d.pop("updated_at"))

        user_id = d.pop("user_id")

        schema = d.pop("$schema", UNSET)

        _last_evaluated_at = d.pop("last_evaluated_at", UNSET)
        last_evaluated_at: datetime.datetime | Unset
        if isinstance(_last_evaluated_at, Unset):
            last_evaluated_at = UNSET
        else:
            last_evaluated_at = datetime.datetime.fromisoformat(_last_evaluated_at)

        run_reason = d.pop("run_reason", UNSET)

        alert_rule_view = cls(
            baseline=baseline,
            created_at=created_at,
            enabled=enabled,
            id=id,
            name=name,
            repository=repository,
            state=state,
            threshold=threshold,
            threshold_z=threshold_z,
            updated_at=updated_at,
            user_id=user_id,
            schema=schema,
            last_evaluated_at=last_evaluated_at,
            run_reason=run_reason,
        )

        return alert_rule_view
