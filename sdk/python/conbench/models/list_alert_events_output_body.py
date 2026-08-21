from __future__ import annotations

from collections.abc import Mapping
from typing import TYPE_CHECKING, Any, Self, TypeVar, cast

from attrs import define as _attrs_define

from ..types import UNSET, Unset

if TYPE_CHECKING:
    from ..models.alert_event_view import AlertEventView


T = TypeVar("T", bound="ListAlertEventsOutputBody")


@_attrs_define
class ListAlertEventsOutputBody:
    """
    Attributes:
        events (list[AlertEventView] | None):
        schema (str | Unset): A URL to the JSON Schema for this object.
    """

    events: list[AlertEventView] | None
    schema: str | Unset = UNSET

    def to_dict(self) -> dict[str, Any]:
        events: list[dict[str, Any]] | None
        if isinstance(self.events, list):
            events = []
            for events_type_0_item_data in self.events:
                events_type_0_item = events_type_0_item_data.to_dict()
                events.append(events_type_0_item)

        else:
            events = self.events

        schema = self.schema

        field_dict: dict[str, Any] = {}

        field_dict.update(
            {
                "events": events,
            }
        )
        if schema is not UNSET:
            field_dict["$schema"] = schema

        return field_dict

    @classmethod
    def from_dict(cls, src_dict: Mapping[str, Any]) -> Self:
        from ..models.alert_event_view import AlertEventView

        d = dict(src_dict)

        def _parse_events(data: object) -> list[AlertEventView] | None:
            if data is None:
                return data
            try:
                if not isinstance(data, list):
                    raise TypeError()
                events_type_0 = []
                _events_type_0 = data
                for events_type_0_item_data in _events_type_0:
                    events_type_0_item = AlertEventView.from_dict(
                        events_type_0_item_data
                    )

                    events_type_0.append(events_type_0_item)

                return events_type_0
            except (TypeError, ValueError, AttributeError, KeyError):
                pass
            return cast(list[AlertEventView] | None, data)

        events = _parse_events(d.pop("events"))

        schema = d.pop("$schema", UNSET)

        list_alert_events_output_body = cls(
            events=events,
            schema=schema,
        )

        return list_alert_events_output_body
