from __future__ import annotations

from collections.abc import Mapping
from typing import Any, TypeVar

from attrs import define as _attrs_define

from ..types import UNSET, Unset

T = TypeVar("T", bound="ErrorDetail")


@_attrs_define
class ErrorDetail:
    """
    Attributes:
        location (str | Unset): Where the error occurred, e.g. 'body.items[3].tags' or 'path.thing-id'
        message (str | Unset): Error message text
        value (Any | Unset): The value at the given location
    """

    location: str | Unset = UNSET
    message: str | Unset = UNSET
    value: Any | Unset = UNSET

    def to_dict(self) -> dict[str, Any]:
        location = self.location

        message = self.message

        value = self.value

        field_dict: dict[str, Any] = {}

        field_dict.update({})
        if location is not UNSET:
            field_dict["location"] = location
        if message is not UNSET:
            field_dict["message"] = message
        if value is not UNSET:
            field_dict["value"] = value

        return field_dict

    @classmethod
    def from_dict(cls: type[T], src_dict: Mapping[str, Any]) -> T:
        d = dict(src_dict)
        location = d.pop("location", UNSET)

        message = d.pop("message", UNSET)

        value = d.pop("value", UNSET)

        error_detail = cls(
            location=location,
            message=message,
            value=value,
        )

        return error_detail
