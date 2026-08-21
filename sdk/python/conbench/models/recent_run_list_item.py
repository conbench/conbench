from __future__ import annotations

import datetime
from collections.abc import Mapping
from typing import TYPE_CHECKING, Any, Self, TypeVar, cast

from attrs import define as _attrs_define

from ..types import UNSET, Unset

if TYPE_CHECKING:
    from ..models.list_commit_type_0 import ListCommitType0
    from ..models.recent_run_attention import RecentRunAttention
    from ..models.recent_run_list_item_run_tags import RecentRunListItemRunTags


T = TypeVar("T", bound="RecentRunListItem")


@_attrs_define
class RecentRunListItem:
    """
    Attributes:
        batch_count (int):
        commit (ListCommitType0 | None):
        commit_sha (None | str):
        error_count (int):
        first_result_at (datetime.datetime):
        last_result_at (datetime.datetime):
        latest_batch_id (None | str):
        latest_result_id (str):
        repository (str):
        result_count (int):
        run_id (str):
        run_reason (None | str):
        run_tags (RecentRunListItemRunTags):
        series_count (int):
        attention (RecentRunAttention | Unset):
    """

    batch_count: int
    commit: ListCommitType0 | None
    commit_sha: None | str
    error_count: int
    first_result_at: datetime.datetime
    last_result_at: datetime.datetime
    latest_batch_id: None | str
    latest_result_id: str
    repository: str
    result_count: int
    run_id: str
    run_reason: None | str
    run_tags: RecentRunListItemRunTags
    series_count: int
    attention: RecentRunAttention | Unset = UNSET

    def to_dict(self) -> dict[str, Any]:
        from ..models.list_commit_type_0 import ListCommitType0

        batch_count = self.batch_count

        commit: dict[str, Any] | None
        if isinstance(self.commit, ListCommitType0):
            commit = self.commit.to_dict()
        else:
            commit = self.commit

        commit_sha: None | str
        commit_sha = self.commit_sha

        error_count = self.error_count

        first_result_at = self.first_result_at.isoformat()

        last_result_at = self.last_result_at.isoformat()

        latest_batch_id: None | str
        latest_batch_id = self.latest_batch_id

        latest_result_id = self.latest_result_id

        repository = self.repository

        result_count = self.result_count

        run_id = self.run_id

        run_reason: None | str
        run_reason = self.run_reason

        run_tags = self.run_tags.to_dict()

        series_count = self.series_count

        attention: dict[str, Any] | Unset = UNSET
        if not isinstance(self.attention, Unset):
            attention = self.attention.to_dict()

        field_dict: dict[str, Any] = {}

        field_dict.update(
            {
                "batch_count": batch_count,
                "commit": commit,
                "commit_sha": commit_sha,
                "error_count": error_count,
                "first_result_at": first_result_at,
                "last_result_at": last_result_at,
                "latest_batch_id": latest_batch_id,
                "latest_result_id": latest_result_id,
                "repository": repository,
                "result_count": result_count,
                "run_id": run_id,
                "run_reason": run_reason,
                "run_tags": run_tags,
                "series_count": series_count,
            }
        )
        if attention is not UNSET:
            field_dict["attention"] = attention

        return field_dict

    @classmethod
    def from_dict(cls, src_dict: Mapping[str, Any]) -> Self:
        from ..models.list_commit_type_0 import ListCommitType0
        from ..models.recent_run_attention import RecentRunAttention
        from ..models.recent_run_list_item_run_tags import RecentRunListItemRunTags

        d = dict(src_dict)
        batch_count = d.pop("batch_count")

        def _parse_commit(data: object) -> ListCommitType0 | None:
            if data is None:
                return data
            try:
                if not isinstance(data, dict):
                    raise TypeError()
                componentsschemas_list_commit_type_0 = ListCommitType0.from_dict(data)

                return componentsschemas_list_commit_type_0
            except (TypeError, ValueError, AttributeError, KeyError):
                pass
            return cast(ListCommitType0 | None, data)

        commit = _parse_commit(d.pop("commit"))

        def _parse_commit_sha(data: object) -> None | str:
            if data is None:
                return data
            return cast(None | str, data)

        commit_sha = _parse_commit_sha(d.pop("commit_sha"))

        error_count = d.pop("error_count")

        first_result_at = datetime.datetime.fromisoformat(d.pop("first_result_at"))

        last_result_at = datetime.datetime.fromisoformat(d.pop("last_result_at"))

        def _parse_latest_batch_id(data: object) -> None | str:
            if data is None:
                return data
            return cast(None | str, data)

        latest_batch_id = _parse_latest_batch_id(d.pop("latest_batch_id"))

        latest_result_id = d.pop("latest_result_id")

        repository = d.pop("repository")

        result_count = d.pop("result_count")

        run_id = d.pop("run_id")

        def _parse_run_reason(data: object) -> None | str:
            if data is None:
                return data
            return cast(None | str, data)

        run_reason = _parse_run_reason(d.pop("run_reason"))

        run_tags = RecentRunListItemRunTags.from_dict(d.pop("run_tags"))

        series_count = d.pop("series_count")

        _attention = d.pop("attention", UNSET)
        attention: RecentRunAttention | Unset
        if isinstance(_attention, Unset):
            attention = UNSET
        else:
            attention = RecentRunAttention.from_dict(_attention)

        recent_run_list_item = cls(
            batch_count=batch_count,
            commit=commit,
            commit_sha=commit_sha,
            error_count=error_count,
            first_result_at=first_result_at,
            last_result_at=last_result_at,
            latest_batch_id=latest_batch_id,
            latest_result_id=latest_result_id,
            repository=repository,
            result_count=result_count,
            run_id=run_id,
            run_reason=run_reason,
            run_tags=run_tags,
            series_count=series_count,
            attention=attention,
        )

        return recent_run_list_item
