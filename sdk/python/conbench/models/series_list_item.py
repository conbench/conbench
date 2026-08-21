from __future__ import annotations

import datetime
from collections.abc import Mapping
from typing import TYPE_CHECKING, Any, Self, TypeVar, cast

from attrs import define as _attrs_define

from ..models.series_list_item_status import SeriesListItemStatus

if TYPE_CHECKING:
    from ..models.hardware import Hardware
    from ..models.series_list_item_context import SeriesListItemContext
    from ..models.series_list_item_tags import SeriesListItemTags


T = TypeVar("T", bound="SeriesListItem")


@_attrs_define
class SeriesListItem:
    """
    Attributes:
        context (SeriesListItemContext):
        hardware (Hardware):
        history_fingerprint (str):
        latest_commit_sha (str):
        latest_commit_timestamp (datetime.datetime):
        latest_result_id (str):
        latest_result_timestamp (datetime.datetime):
        latest_single_value_summary (float | None):
        latest_single_value_summary_type (None | str):
        less_is_better (bool | None):
        name (str):
        point_count (int):
        repository (str):
        sparkline (list[float] | None):
        status (SeriesListItemStatus):
        tags (SeriesListItemTags):
        unit (None | str):
    """

    context: SeriesListItemContext
    hardware: Hardware
    history_fingerprint: str
    latest_commit_sha: str
    latest_commit_timestamp: datetime.datetime
    latest_result_id: str
    latest_result_timestamp: datetime.datetime
    latest_single_value_summary: float | None
    latest_single_value_summary_type: None | str
    less_is_better: bool | None
    name: str
    point_count: int
    repository: str
    sparkline: list[float] | None
    status: SeriesListItemStatus
    tags: SeriesListItemTags
    unit: None | str

    def to_dict(self) -> dict[str, Any]:
        context = self.context.to_dict()

        hardware = self.hardware.to_dict()

        history_fingerprint = self.history_fingerprint

        latest_commit_sha = self.latest_commit_sha

        latest_commit_timestamp = self.latest_commit_timestamp.isoformat()

        latest_result_id = self.latest_result_id

        latest_result_timestamp = self.latest_result_timestamp.isoformat()

        latest_single_value_summary: float | None
        latest_single_value_summary = self.latest_single_value_summary

        latest_single_value_summary_type: None | str
        latest_single_value_summary_type = self.latest_single_value_summary_type

        less_is_better: bool | None
        less_is_better = self.less_is_better

        name = self.name

        point_count = self.point_count

        repository = self.repository

        sparkline: list[float] | None
        if isinstance(self.sparkline, list):
            sparkline = self.sparkline

        else:
            sparkline = self.sparkline

        status = self.status.value

        tags = self.tags.to_dict()

        unit: None | str
        unit = self.unit

        field_dict: dict[str, Any] = {}

        field_dict.update(
            {
                "context": context,
                "hardware": hardware,
                "history_fingerprint": history_fingerprint,
                "latest_commit_sha": latest_commit_sha,
                "latest_commit_timestamp": latest_commit_timestamp,
                "latest_result_id": latest_result_id,
                "latest_result_timestamp": latest_result_timestamp,
                "latest_single_value_summary": latest_single_value_summary,
                "latest_single_value_summary_type": latest_single_value_summary_type,
                "less_is_better": less_is_better,
                "name": name,
                "point_count": point_count,
                "repository": repository,
                "sparkline": sparkline,
                "status": status,
                "tags": tags,
                "unit": unit,
            }
        )

        return field_dict

    @classmethod
    def from_dict(cls, src_dict: Mapping[str, Any]) -> Self:
        from ..models.hardware import Hardware
        from ..models.series_list_item_context import SeriesListItemContext
        from ..models.series_list_item_tags import SeriesListItemTags

        d = dict(src_dict)
        context = SeriesListItemContext.from_dict(d.pop("context"))

        hardware = Hardware.from_dict(d.pop("hardware"))

        history_fingerprint = d.pop("history_fingerprint")

        latest_commit_sha = d.pop("latest_commit_sha")

        latest_commit_timestamp = datetime.datetime.fromisoformat(
            d.pop("latest_commit_timestamp")
        )

        latest_result_id = d.pop("latest_result_id")

        latest_result_timestamp = datetime.datetime.fromisoformat(
            d.pop("latest_result_timestamp")
        )

        def _parse_latest_single_value_summary(data: object) -> float | None:
            if data is None:
                return data
            return cast(float | None, data)

        latest_single_value_summary = _parse_latest_single_value_summary(
            d.pop("latest_single_value_summary")
        )

        def _parse_latest_single_value_summary_type(data: object) -> None | str:
            if data is None:
                return data
            return cast(None | str, data)

        latest_single_value_summary_type = _parse_latest_single_value_summary_type(
            d.pop("latest_single_value_summary_type")
        )

        def _parse_less_is_better(data: object) -> bool | None:
            if data is None:
                return data
            return cast(bool | None, data)

        less_is_better = _parse_less_is_better(d.pop("less_is_better"))

        name = d.pop("name")

        point_count = d.pop("point_count")

        repository = d.pop("repository")

        def _parse_sparkline(data: object) -> list[float] | None:
            if data is None:
                return data
            try:
                if not isinstance(data, list):
                    raise TypeError()
                sparkline_type_0 = cast(list[float], data)

                return sparkline_type_0
            except (TypeError, ValueError, AttributeError, KeyError):
                pass
            return cast(list[float] | None, data)

        sparkline = _parse_sparkline(d.pop("sparkline"))

        status = SeriesListItemStatus(d.pop("status"))

        tags = SeriesListItemTags.from_dict(d.pop("tags"))

        def _parse_unit(data: object) -> None | str:
            if data is None:
                return data
            return cast(None | str, data)

        unit = _parse_unit(d.pop("unit"))

        series_list_item = cls(
            context=context,
            hardware=hardware,
            history_fingerprint=history_fingerprint,
            latest_commit_sha=latest_commit_sha,
            latest_commit_timestamp=latest_commit_timestamp,
            latest_result_id=latest_result_id,
            latest_result_timestamp=latest_result_timestamp,
            latest_single_value_summary=latest_single_value_summary,
            latest_single_value_summary_type=latest_single_value_summary_type,
            less_is_better=less_is_better,
            name=name,
            point_count=point_count,
            repository=repository,
            sparkline=sparkline,
            status=status,
            tags=tags,
            unit=unit,
        )

        return series_list_item
