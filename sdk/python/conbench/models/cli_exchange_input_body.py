from __future__ import annotations

from collections.abc import Mapping
from typing import Any, TypeVar

from attrs import define as _attrs_define

from ..types import UNSET, Unset

T = TypeVar("T", bound="CliExchangeInputBody")


@_attrs_define
class CliExchangeInputBody:
    """
    Attributes:
        code (str):
        name (str):
        schema (str | Unset): A URL to the JSON Schema for this object.
    """

    code: str
    name: str
    schema: str | Unset = UNSET

    def to_dict(self) -> dict[str, Any]:
        code = self.code

        name = self.name

        schema = self.schema

        field_dict: dict[str, Any] = {}

        field_dict.update(
            {
                "code": code,
                "name": name,
            }
        )
        if schema is not UNSET:
            field_dict["$schema"] = schema

        return field_dict

    @classmethod
    def from_dict(cls: type[T], src_dict: Mapping[str, Any]) -> T:
        d = dict(src_dict)
        code = d.pop("code")

        name = d.pop("name")

        schema = d.pop("$schema", UNSET)

        cli_exchange_input_body = cls(
            code=code,
            name=name,
            schema=schema,
        )

        return cli_exchange_input_body
