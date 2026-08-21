from __future__ import annotations

import datetime
from collections.abc import Mapping
from typing import Any, Self, TypeVar, cast

from attrs import define as _attrs_define

T = TypeVar("T", bound="ListCommitType0")


@_attrs_define
class ListCommitType0:
    """
    Attributes:
        author_avatar (None | str):
        author_login (None | str):
        author_name (str):
        hash_ (str):
        message (str):
        repository (str):
        timestamp (datetime.datetime | None):
    """

    author_avatar: None | str
    author_login: None | str
    author_name: str
    hash_: str
    message: str
    repository: str
    timestamp: datetime.datetime | None

    def to_dict(self) -> dict[str, Any]:
        author_avatar: None | str
        author_avatar = self.author_avatar

        author_login: None | str
        author_login = self.author_login

        author_name = self.author_name

        hash_ = self.hash_

        message = self.message

        repository = self.repository

        timestamp: None | str
        if isinstance(self.timestamp, datetime.datetime):
            timestamp = self.timestamp.isoformat()
        else:
            timestamp = self.timestamp

        field_dict: dict[str, Any] = {}

        field_dict.update(
            {
                "author_avatar": author_avatar,
                "author_login": author_login,
                "author_name": author_name,
                "hash": hash_,
                "message": message,
                "repository": repository,
                "timestamp": timestamp,
            }
        )

        return field_dict

    @classmethod
    def from_dict(cls, src_dict: Mapping[str, Any]) -> Self:
        d = dict(src_dict)

        def _parse_author_avatar(data: object) -> None | str:
            if data is None:
                return data
            return cast(None | str, data)

        author_avatar = _parse_author_avatar(d.pop("author_avatar"))

        def _parse_author_login(data: object) -> None | str:
            if data is None:
                return data
            return cast(None | str, data)

        author_login = _parse_author_login(d.pop("author_login"))

        author_name = d.pop("author_name")

        hash_ = d.pop("hash")

        message = d.pop("message")

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
            author_avatar=author_avatar,
            author_login=author_login,
            author_name=author_name,
            hash_=hash_,
            message=message,
            repository=repository,
            timestamp=timestamp,
        )

        return list_commit_type_0
