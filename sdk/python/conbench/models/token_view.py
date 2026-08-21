from __future__ import annotations

import datetime
from collections.abc import Mapping
from typing import Any, Self, TypeVar

from attrs import define as _attrs_define

from ..types import UNSET, Unset

T = TypeVar("T", bound="TokenView")


@_attrs_define
class TokenView:
    """
    Attributes:
        created_at (datetime.datetime):
        id (str):
        name (str):
        prefix (str):
        last_used_at (datetime.datetime | Unset):
        revoked_at (datetime.datetime | Unset):
    """

    created_at: datetime.datetime
    id: str
    name: str
    prefix: str
    last_used_at: datetime.datetime | Unset = UNSET
    revoked_at: datetime.datetime | Unset = UNSET

    def to_dict(self) -> dict[str, Any]:
        created_at = self.created_at.isoformat()

        id = self.id

        name = self.name

        prefix = self.prefix

        last_used_at: str | Unset = UNSET
        if not isinstance(self.last_used_at, Unset):
            last_used_at = self.last_used_at.isoformat()

        revoked_at: str | Unset = UNSET
        if not isinstance(self.revoked_at, Unset):
            revoked_at = self.revoked_at.isoformat()

        field_dict: dict[str, Any] = {}

        field_dict.update(
            {
                "created_at": created_at,
                "id": id,
                "name": name,
                "prefix": prefix,
            }
        )
        if last_used_at is not UNSET:
            field_dict["last_used_at"] = last_used_at
        if revoked_at is not UNSET:
            field_dict["revoked_at"] = revoked_at

        return field_dict

    @classmethod
    def from_dict(cls, src_dict: Mapping[str, Any]) -> Self:
        d = dict(src_dict)
        created_at = datetime.datetime.fromisoformat(d.pop("created_at"))

        id = d.pop("id")

        name = d.pop("name")

        prefix = d.pop("prefix")

        _last_used_at = d.pop("last_used_at", UNSET)
        last_used_at: datetime.datetime | Unset
        if isinstance(_last_used_at, Unset):
            last_used_at = UNSET
        else:
            last_used_at = datetime.datetime.fromisoformat(_last_used_at)

        _revoked_at = d.pop("revoked_at", UNSET)
        revoked_at: datetime.datetime | Unset
        if isinstance(_revoked_at, Unset):
            revoked_at = UNSET
        else:
            revoked_at = datetime.datetime.fromisoformat(_revoked_at)

        token_view = cls(
            created_at=created_at,
            id=id,
            name=name,
            prefix=prefix,
            last_used_at=last_used_at,
            revoked_at=revoked_at,
        )

        return token_view
