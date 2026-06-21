from __future__ import annotations

from collections.abc import Mapping
from typing import Any, TypeVar

from attrs import define as _attrs_define

from ..types import UNSET, Unset

T = TypeVar("T", bound="MeOutputBody")


@_attrs_define
class MeOutputBody:
    """
    Attributes:
        email (str):
        id (str):
        name (str):
        schema (str | Unset): A URL to the JSON Schema for this object.
    """

    email: str
    id: str
    name: str
    schema: str | Unset = UNSET

    def to_dict(self) -> dict[str, Any]:
        email = self.email

        id = self.id

        name = self.name

        schema = self.schema

        field_dict: dict[str, Any] = {}

        field_dict.update(
            {
                "email": email,
                "id": id,
                "name": name,
            }
        )
        if schema is not UNSET:
            field_dict["$schema"] = schema

        return field_dict

    @classmethod
    def from_dict(cls: type[T], src_dict: Mapping[str, Any]) -> T:
        d = dict(src_dict)
        email = d.pop("email")

        id = d.pop("id")

        name = d.pop("name")

        schema = d.pop("$schema", UNSET)

        me_output_body = cls(
            email=email,
            id=id,
            name=name,
            schema=schema,
        )

        return me_output_body
