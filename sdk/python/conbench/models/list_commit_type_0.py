from __future__ import annotations

import datetime
from collections.abc import Mapping
from typing import Any, TypeVar, cast

from attrs import define as _attrs_define

T = TypeVar("T", bound="ListCommitType0")


@_attrs_define
class ListCommitType0:
    """
    Attributes:
        hash_ (str):
        repository (str):
        timestamp (datetime.datetime | None):
    """

    hash_: str
    repository: str
    timestamp: datetime.datetime | None

    def to_dict(self) -> dict[str, Any]:
        hash_ = self.hash_

        repository = self.repository

        timestamp: None | str
        if isinstance(self.timestamp, datetime.datetime):
            timestamp = self.timestamp.isoformat()
        else:
            timestamp = self.timestamp

        field_dict: dict[str, Any] = {}

        field_dict.update(
            {
                "hash": hash_,
                "repository": repository,
                "timestamp": timestamp,
            }
        )

        return field_dict

    @classmethod
    def from_dict(cls: type[T], src_dict: Mapping[str, Any]) -> T:
        d = dict(src_dict)
        hash_ = d.pop("hash")

        repository = d.pop("repository")

        def _parse_timestamp(data: object) -> datetime.datetime | None:
            if data is None:
                return data
            try:
                if not isinstance(data, str):
                    raise TypeError()
                timestamp_type_0 = datetime.datetime.fromisoformat(data)

                return timestamp_type_0
            except (TypeError, ValueError, AttributeError, KeyError):
                pass
            return cast(datetime.datetime | None, data)

        timestamp = _parse_timestamp(d.pop("timestamp"))

        list_commit_type_0 = cls(
            hash_=hash_,
            repository=repository,
            timestamp=timestamp,
        )

        return list_commit_type_0
