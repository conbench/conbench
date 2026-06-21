from __future__ import annotations

from collections.abc import Mapping
from typing import Any, TypeVar

from attrs import define as _attrs_define

from ..types import UNSET, Unset

T = TypeVar("T", bound="CreateTokenInputBody")


@_attrs_define
class CreateTokenInputBody:
    """
    Attributes:
        name (str):
        schema (str | Unset): A URL to the JSON Schema for this object.
    """

    name: str
    schema: str | Unset = UNSET

    def to_dict(self) -> dict[str, Any]:
        name = self.name

        schema = self.schema

        field_dict: dict[str, Any] = {}

        field_dict.update(
            {
                "name": name,
            }
        )
        if schema is not UNSET:
            field_dict["$schema"] = schema

        return field_dict

    @classmethod
    def from_dict(cls: type[T], src_dict: Mapping[str, Any]) -> T:
        d = dict(src_dict)
        name = d.pop("name")

        schema = d.pop("$schema", UNSET)

        create_token_input_body = cls(
            name=name,
            schema=schema,
        )

        return create_token_input_body
