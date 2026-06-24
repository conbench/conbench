from __future__ import annotations

import datetime
from collections.abc import Mapping
from typing import TYPE_CHECKING, Any, TypeVar, cast

from attrs import define as _attrs_define

if TYPE_CHECKING:
    from ..models.list_commit_type_0 import ListCommitType0
    from ..models.result_list_item_run_tags import ResultListItemRunTags


T = TypeVar("T", bound="ResultListItem")


@_attrs_define
class ResultListItem:
    """
    Attributes:
        batch_id (None | str):
        commit (ListCommitType0 | None):
        has_error (bool):
        history_fingerprint (str):
        id (str):
        run_id (str):
        run_reason (None | str):
        run_tags (ResultListItemRunTags):
        single_value_summary (float | None):
        single_value_summary_type (str):
        timestamp (datetime.datetime):
        unit (None | str):
    """

    batch_id: None | str
    commit: ListCommitType0 | None
    has_error: bool
    history_fingerprint: str
    id: str
    run_id: str
    run_reason: None | str
    run_tags: ResultListItemRunTags
    single_value_summary: float | None
    single_value_summary_type: str
    timestamp: datetime.datetime
    unit: None | str

    def to_dict(self) -> dict[str, Any]:
        from ..models.list_commit_type_0 import ListCommitType0

        batch_id: None | str
        batch_id = self.batch_id

        commit: dict[str, Any] | None
        if isinstance(self.commit, ListCommitType0):
            commit = self.commit.to_dict()
        else:
            commit = self.commit

        has_error = self.has_error

        history_fingerprint = self.history_fingerprint

        id = self.id

        run_id = self.run_id

        run_reason: None | str
        run_reason = self.run_reason

        run_tags = self.run_tags.to_dict()

        single_value_summary: float | None
        single_value_summary = self.single_value_summary

        single_value_summary_type = self.single_value_summary_type

        timestamp = self.timestamp.isoformat()

        unit: None | str
        unit = self.unit

        field_dict: dict[str, Any] = {}

        field_dict.update(
            {
                "batch_id": batch_id,
                "commit": commit,
                "has_error": has_error,
                "history_fingerprint": history_fingerprint,
                "id": id,
                "run_id": run_id,
                "run_reason": run_reason,
                "run_tags": run_tags,
                "single_value_summary": single_value_summary,
                "single_value_summary_type": single_value_summary_type,
                "timestamp": timestamp,
                "unit": unit,
            }
        )

        return field_dict

    @classmethod
    def from_dict(cls: type[T], src_dict: Mapping[str, Any]) -> T:
        from ..models.list_commit_type_0 import ListCommitType0
        from ..models.result_list_item_run_tags import ResultListItemRunTags

        d = dict(src_dict)

        def _parse_batch_id(data: object) -> None | str:
            if data is None:
                return data
            return cast(None | str, data)

        batch_id = _parse_batch_id(d.pop("batch_id"))

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

        has_error = d.pop("has_error")

        history_fingerprint = d.pop("history_fingerprint")

        id = d.pop("id")

        run_id = d.pop("run_id")

        def _parse_run_reason(data: object) -> None | str:
            if data is None:
                return data
            return cast(None | str, data)

        run_reason = _parse_run_reason(d.pop("run_reason"))

        run_tags = ResultListItemRunTags.from_dict(d.pop("run_tags"))

        def _parse_single_value_summary(data: object) -> float | None:
            if data is None:
                return data
            return cast(float | None, data)

        single_value_summary = _parse_single_value_summary(
            d.pop("single_value_summary")
        )

        single_value_summary_type = d.pop("single_value_summary_type")

        timestamp = datetime.datetime.fromisoformat(d.pop("timestamp"))

        def _parse_unit(data: object) -> None | str:
            if data is None:
                return data
            return cast(None | str, data)

        unit = _parse_unit(d.pop("unit"))

        result_list_item = cls(
            batch_id=batch_id,
            commit=commit,
            has_error=has_error,
            history_fingerprint=history_fingerprint,
            id=id,
            run_id=run_id,
            run_reason=run_reason,
            run_tags=run_tags,
            single_value_summary=single_value_summary,
            single_value_summary_type=single_value_summary_type,
            timestamp=timestamp,
            unit=unit,
        )

        return result_list_item
