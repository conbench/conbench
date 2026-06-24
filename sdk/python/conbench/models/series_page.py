from __future__ import annotations

from collections.abc import Mapping
from typing import TYPE_CHECKING, Any, TypeVar, cast

from attrs import define as _attrs_define

from ..types import UNSET, Unset

if TYPE_CHECKING:
    from ..models.series_list_item import SeriesListItem


T = TypeVar("T", bound="SeriesPage")


@_attrs_define
class SeriesPage:
    """
    Attributes:
        next_page_cursor (None | str):
        series (list[SeriesListItem] | None):
        schema (str | Unset): A URL to the JSON Schema for this object.
    """

    next_page_cursor: None | str
    series: list[SeriesListItem] | None
    schema: str | Unset = UNSET

    def to_dict(self) -> dict[str, Any]:
        next_page_cursor: None | str
        next_page_cursor = self.next_page_cursor

        series: list[dict[str, Any]] | None
        if isinstance(self.series, list):
            series = []
            for series_type_0_item_data in self.series:
                series_type_0_item = series_type_0_item_data.to_dict()
                series.append(series_type_0_item)

        else:
            series = self.series

        schema = self.schema

        field_dict: dict[str, Any] = {}

        field_dict.update(
            {
                "next_page_cursor": next_page_cursor,
                "series": series,
            }
        )
        if schema is not UNSET:
            field_dict["$schema"] = schema

        return field_dict

    @classmethod
    def from_dict(cls: type[T], src_dict: Mapping[str, Any]) -> T:
        from ..models.series_list_item import SeriesListItem

        d = dict(src_dict)

        def _parse_next_page_cursor(data: object) -> None | str:
            if data is None:
                return data
            return cast(None | str, data)

        next_page_cursor = _parse_next_page_cursor(d.pop("next_page_cursor"))

        def _parse_series(data: object) -> list[SeriesListItem] | None:
            if data is None:
                return data
            try:
                if not isinstance(data, list):
                    raise TypeError()
                series_type_0 = []
                _series_type_0 = data
                for series_type_0_item_data in _series_type_0:
                    series_type_0_item = SeriesListItem.from_dict(
                        series_type_0_item_data
                    )

                    series_type_0.append(series_type_0_item)

                return series_type_0
            except (TypeError, ValueError, AttributeError, KeyError):
                pass
            return cast(list[SeriesListItem] | None, data)

        series = _parse_series(d.pop("series"))

        schema = d.pop("$schema", UNSET)

        series_page = cls(
            next_page_cursor=next_page_cursor,
            series=series,
            schema=schema,
        )

        return series_page
