from __future__ import annotations

from collections.abc import Mapping
from typing import Any, Self, TypeVar

from attrs import define as _attrs_define

from ..types import UNSET, Unset

T = TypeVar("T", bound="CapabilitiesOutputBody")


@_attrs_define
class CapabilitiesOutputBody:
    """
    Attributes:
        auth_disabled (bool):
        can_write_results (bool):
        signed_in (bool):
        schema (str | Unset): A URL to the JSON Schema for this object.
    """

    auth_disabled: bool
    can_write_results: bool
    signed_in: bool
    schema: str | Unset = UNSET

    def to_dict(self) -> dict[str, Any]:
        auth_disabled = self.auth_disabled

        can_write_results = self.can_write_results

        signed_in = self.signed_in

        schema = self.schema

        field_dict: dict[str, Any] = {}

        field_dict.update(
            {
                "auth_disabled": auth_disabled,
                "can_write_results": can_write_results,
                "signed_in": signed_in,
            }
        )
        if schema is not UNSET:
            field_dict["$schema"] = schema

        return field_dict

    @classmethod
    def from_dict(cls, src_dict: Mapping[str, Any]) -> Self:
        d = dict(src_dict)
        auth_disabled = d.pop("auth_disabled")

        can_write_results = d.pop("can_write_results")

        signed_in = d.pop("signed_in")

        schema = d.pop("$schema", UNSET)

        capabilities_output_body = cls(
            auth_disabled=auth_disabled,
            can_write_results=can_write_results,
            signed_in=signed_in,
            schema=schema,
        )

        return capabilities_output_body
