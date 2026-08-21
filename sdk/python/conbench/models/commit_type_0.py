from __future__ import annotations

import datetime
from collections.abc import Mapping
from typing import Any, Self, TypeVar, cast

from attrs import define as _attrs_define

T = TypeVar("T", bound="CommitType0")


@_attrs_define
class CommitType0:
    """
    Attributes:
        id (str):
        message (str):
        repository (str):
        sha (str):
        timestamp (datetime.datetime | None):
    """

    id: str
    message: str
    repository: str
    sha: str
    timestamp: datetime.datetime | None

    def to_dict(self) -> dict[str, Any]:
        id = self.id

        message = self.message

        repository = self.repository

        sha = self.sha

        timestamp: None | str
        if isinstance(self.timestamp, datetime.datetime):
            timestamp = self.timestamp.isoformat()
        else:
            timestamp = self.timestamp

        field_dict: dict[str, Any] = {}

        field_dict.update(
            {
                "id": id,
                "message": message,
                "repository": repository,
                "sha": sha,
                "timestamp": timestamp,
            }
        )

        return field_dict

    @classmethod
    def from_dict(cls, src_dict: Mapping[str, Any]) -> Self:
        d = dict(src_dict)
        id = d.pop("id")

        message = d.pop("message")

        repository = d.pop("repository")

        sha = d.pop("sha")

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

        commit_type_0 = cls(
            id=id,
            message=message,
            repository=repository,
            sha=sha,
            timestamp=timestamp,
        )

        return commit_type_0
