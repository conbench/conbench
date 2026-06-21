from __future__ import annotations

import datetime
from collections.abc import Mapping
from typing import Any, TypeVar

from attrs import define as _attrs_define

from ..types import UNSET, Unset

T = TypeVar("T", bound="CliExchangeOutputBody")


@_attrs_define
class CliExchangeOutputBody:
    """
    Attributes:
        created_at (datetime.datetime):
        id (str):
        name (str):
        prefix (str):
        token (str): The plaintext secret. Shown once.
        schema (str | Unset): A URL to the JSON Schema for this object.
    """

    created_at: datetime.datetime
    id: str
    name: str
    prefix: str
    token: str
    schema: str | Unset = UNSET

    def to_dict(self) -> dict[str, Any]:
        created_at = self.created_at.isoformat()

        id = self.id

        name = self.name

        prefix = self.prefix

        token = self.token

        schema = self.schema

        field_dict: dict[str, Any] = {}

        field_dict.update(
            {
                "created_at": created_at,
                "id": id,
                "name": name,
                "prefix": prefix,
                "token": token,
            }
        )
        if schema is not UNSET:
            field_dict["$schema"] = schema

        return field_dict

    @classmethod
    def from_dict(cls: type[T], src_dict: Mapping[str, Any]) -> T:
        d = dict(src_dict)
        created_at = datetime.datetime.fromisoformat(d.pop("created_at"))

        id = d.pop("id")

        name = d.pop("name")

        prefix = d.pop("prefix")

        token = d.pop("token")

        schema = d.pop("$schema", UNSET)

        cli_exchange_output_body = cls(
            created_at=created_at,
            id=id,
            name=name,
            prefix=prefix,
            token=token,
            schema=schema,
        )

        return cli_exchange_output_body
