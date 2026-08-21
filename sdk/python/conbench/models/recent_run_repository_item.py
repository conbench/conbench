from __future__ import annotations

from collections.abc import Mapping
from typing import Any, Self, TypeVar

from attrs import define as _attrs_define

T = TypeVar("T", bound="RecentRunRepositoryItem")


@_attrs_define
class RecentRunRepositoryItem:
    """
    Attributes:
        repository (str):
    """

    repository: str

    def to_dict(self) -> dict[str, Any]:
        repository = self.repository

        field_dict: dict[str, Any] = {}

        field_dict.update(
            {
                "repository": repository,
            }
        )

        return field_dict

    @classmethod
    def from_dict(cls, src_dict: Mapping[str, Any]) -> Self:
        d = dict(src_dict)
        repository = d.pop("repository")

        recent_run_repository_item = cls(
            repository=repository,
        )

        return recent_run_repository_item
