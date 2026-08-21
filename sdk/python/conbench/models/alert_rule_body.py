from __future__ import annotations

from collections.abc import Mapping
from typing import Any, Self, TypeVar

from attrs import define as _attrs_define

from ..types import UNSET, Unset

T = TypeVar("T", bound="AlertRuleBody")


@_attrs_define
class AlertRuleBody:
    """
    Attributes:
        name (str):
        repository (str):
        schema (str | Unset): A URL to the JSON Schema for this object.
        baseline (str | Unset):
        enabled (bool | Unset):
        run_reason (str | Unset):
        threshold (float | Unset):
        threshold_z (float | Unset):
    """

    name: str
    repository: str
    schema: str | Unset = UNSET
    baseline: str | Unset = UNSET
    enabled: bool | Unset = UNSET
    run_reason: str | Unset = UNSET
    threshold: float | Unset = UNSET
    threshold_z: float | Unset = UNSET

    def to_dict(self) -> dict[str, Any]:
        name = self.name

        repository = self.repository

        schema = self.schema

        baseline = self.baseline

        enabled = self.enabled

        run_reason = self.run_reason

        threshold = self.threshold

        threshold_z = self.threshold_z

        field_dict: dict[str, Any] = {}

        field_dict.update(
            {
                "name": name,
                "repository": repository,
            }
        )
        if schema is not UNSET:
            field_dict["$schema"] = schema
        if baseline is not UNSET:
            field_dict["baseline"] = baseline
        if enabled is not UNSET:
            field_dict["enabled"] = enabled
        if run_reason is not UNSET:
            field_dict["run_reason"] = run_reason
        if threshold is not UNSET:
            field_dict["threshold"] = threshold
        if threshold_z is not UNSET:
            field_dict["threshold_z"] = threshold_z

        return field_dict

    @classmethod
    def from_dict(cls, src_dict: Mapping[str, Any]) -> Self:
        d = dict(src_dict)
        name = d.pop("name")

        repository = d.pop("repository")

        schema = d.pop("$schema", UNSET)

        baseline = d.pop("baseline", UNSET)

        enabled = d.pop("enabled", UNSET)

        run_reason = d.pop("run_reason", UNSET)

        threshold = d.pop("threshold", UNSET)

        threshold_z = d.pop("threshold_z", UNSET)

        alert_rule_body = cls(
            name=name,
            repository=repository,
            schema=schema,
            baseline=baseline,
            enabled=enabled,
            run_reason=run_reason,
            threshold=threshold,
            threshold_z=threshold_z,
        )

        return alert_rule_body
