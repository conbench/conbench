from __future__ import annotations

from collections.abc import Mapping
from typing import TYPE_CHECKING, Any, Self, TypeVar, cast

from attrs import define as _attrs_define

from ..types import UNSET, Unset

if TYPE_CHECKING:
    from ..models.result_list_item import ResultListItem


T = TypeVar("T", bound="ResultPage")


@_attrs_define
class ResultPage:
    """
    Attributes:
        next_page_cursor (None | str):
        results (list[ResultListItem] | None):
        schema (str | Unset): A URL to the JSON Schema for this object.
    """

    next_page_cursor: None | str
    results: list[ResultListItem] | None
    schema: str | Unset = UNSET

    def to_dict(self) -> dict[str, Any]:
        next_page_cursor: None | str
        next_page_cursor = self.next_page_cursor

        results: list[dict[str, Any]] | None
        if isinstance(self.results, list):
            results = []
            for results_type_0_item_data in self.results:
                results_type_0_item = results_type_0_item_data.to_dict()
                results.append(results_type_0_item)

        else:
            results = self.results

        schema = self.schema

        field_dict: dict[str, Any] = {}

        field_dict.update(
            {
                "next_page_cursor": next_page_cursor,
                "results": results,
            }
        )
        if schema is not UNSET:
            field_dict["$schema"] = schema

        return field_dict

    @classmethod
    def from_dict(cls, src_dict: Mapping[str, Any]) -> Self:
        from ..models.result_list_item import ResultListItem

        d = dict(src_dict)

        def _parse_next_page_cursor(data: object) -> None | str:
            if data is None:
                return data
            return cast(None | str, data)

        next_page_cursor = _parse_next_page_cursor(d.pop("next_page_cursor"))

        def _parse_results(data: object) -> list[ResultListItem] | None:
            if data is None:
                return data
            try:
                if not isinstance(data, list):
                    raise TypeError()
                results_type_0 = []
                _results_type_0 = data
                for results_type_0_item_data in _results_type_0:
                    results_type_0_item = ResultListItem.from_dict(
                        results_type_0_item_data
                    )

                    results_type_0.append(results_type_0_item)

                return results_type_0
            except (TypeError, ValueError, AttributeError, KeyError):
                pass
            return cast(list[ResultListItem] | None, data)

        results = _parse_results(d.pop("results"))

        schema = d.pop("$schema", UNSET)

        result_page = cls(
            next_page_cursor=next_page_cursor,
            results=results,
            schema=schema,
        )

        return result_page
