from __future__ import annotations

from collections.abc import Mapping
from typing import TYPE_CHECKING, Any, TypeVar, cast

from attrs import define as _attrs_define

from ..types import UNSET, Unset

if TYPE_CHECKING:
    from ..models.recent_run_list_item import RecentRunListItem


T = TypeVar("T", bound="RecentRunsPage")


@_attrs_define
class RecentRunsPage:
    """
    Attributes:
        runs (list[RecentRunListItem] | None):
        schema (str | Unset): A URL to the JSON Schema for this object.
    """

    runs: list[RecentRunListItem] | None
    schema: str | Unset = UNSET

    def to_dict(self) -> dict[str, Any]:
        runs: list[dict[str, Any]] | None
        if isinstance(self.runs, list):
            runs = []
            for runs_type_0_item_data in self.runs:
                runs_type_0_item = runs_type_0_item_data.to_dict()
                runs.append(runs_type_0_item)

        else:
            runs = self.runs

        schema = self.schema

        field_dict: dict[str, Any] = {}

        field_dict.update(
            {
                "runs": runs,
            }
        )
        if schema is not UNSET:
            field_dict["$schema"] = schema

        return field_dict

    @classmethod
    def from_dict(cls: type[T], src_dict: Mapping[str, Any]) -> T:
        from ..models.recent_run_list_item import RecentRunListItem

        d = dict(src_dict)

        def _parse_runs(data: object) -> list[RecentRunListItem] | None:
            if data is None:
                return data
            try:
                if not isinstance(data, list):
                    raise TypeError()
                runs_type_0 = []
                _runs_type_0 = data
                for runs_type_0_item_data in _runs_type_0:
                    runs_type_0_item = RecentRunListItem.from_dict(
                        runs_type_0_item_data
                    )

                    runs_type_0.append(runs_type_0_item)

                return runs_type_0
            except (TypeError, ValueError, AttributeError, KeyError):
                pass
            return cast(list[RecentRunListItem] | None, data)

        runs = _parse_runs(d.pop("runs"))

        schema = d.pop("$schema", UNSET)

        recent_runs_page = cls(
            runs=runs,
            schema=schema,
        )

        return recent_runs_page
