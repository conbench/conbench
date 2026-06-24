from __future__ import annotations

from collections.abc import Mapping
from typing import Any, TypeVar

from attrs import define as _attrs_define

T = TypeVar("T", bound="Hardware")


@_attrs_define
class Hardware:
    """
    Attributes:
        hash_ (str):
        id (str):
        name (str):
        type_ (str):
    """

    hash_: str
    id: str
    name: str
    type_: str

    def to_dict(self) -> dict[str, Any]:
        hash_ = self.hash_

        id = self.id

        name = self.name

        type_ = self.type_

        field_dict: dict[str, Any] = {}

        field_dict.update(
            {
                "hash": hash_,
                "id": id,
                "name": name,
                "type": type_,
            }
        )

        return field_dict

    @classmethod
    def from_dict(cls: type[T], src_dict: Mapping[str, Any]) -> T:
        d = dict(src_dict)
        hash_ = d.pop("hash")

        id = d.pop("id")

        name = d.pop("name")

        type_ = d.pop("type")

        hardware = cls(
            hash_=hash_,
            id=id,
            name=name,
            type_=type_,
        )

        return hardware
