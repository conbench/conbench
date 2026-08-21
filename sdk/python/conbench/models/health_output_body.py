from __future__ import annotations

from collections.abc import Mapping
from typing import Any, Self, TypeVar

from attrs import define as _attrs_define

from ..types import UNSET, Unset

T = TypeVar("T", bound="HealthOutputBody")


@_attrs_define
class HealthOutputBody:
    """
    Attributes:
        status (str):
        schema (str | Unset): A URL to the JSON Schema for this object.
    """

    status: str
    schema: str | Unset = UNSET

    def to_dict(self) -> dict[str, Any]:
        status = self.status

        schema = self.schema

        field_dict: dict[str, Any] = {}

        field_dict.update(
            {
                "status": status,
            }
        )
        if schema is not UNSET:
            field_dict["$schema"] = schema

        return field_dict

    @classmethod
    def from_dict(cls, src_dict: Mapping[str, Any]) -> Self:
        d = dict(src_dict)
        status = d.pop("status")

        schema = d.pop("$schema", UNSET)

        health_output_body = cls(
            status=status,
            schema=schema,
        )

        return health_output_body
