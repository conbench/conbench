from __future__ import annotations

from collections.abc import Mapping
from typing import TYPE_CHECKING, Any, Self, TypeVar, cast

from attrs import define as _attrs_define

from ..types import UNSET, Unset

if TYPE_CHECKING:
    from ..models.update_result_input_body_change_annotations_type_0 import (
        UpdateResultInputBodyChangeAnnotationsType0,
    )


T = TypeVar("T", bound="UpdateResultInputBody")


@_attrs_define
class UpdateResultInputBody:
    """
    Attributes:
        schema (str | Unset): A URL to the JSON Schema for this object.
        change_annotations (None | Unset | UpdateResultInputBodyChangeAnnotationsType0):
    """

    schema: str | Unset = UNSET
    change_annotations: None | Unset | UpdateResultInputBodyChangeAnnotationsType0 = (
        UNSET
    )

    def to_dict(self) -> dict[str, Any]:
        from ..models.update_result_input_body_change_annotations_type_0 import (
            UpdateResultInputBodyChangeAnnotationsType0,
        )

        schema = self.schema

        change_annotations: dict[str, Any] | None | Unset
        if isinstance(self.change_annotations, Unset):
            change_annotations = UNSET
        elif isinstance(
            self.change_annotations, UpdateResultInputBodyChangeAnnotationsType0
        ):
            change_annotations = self.change_annotations.to_dict()
        else:
            change_annotations = self.change_annotations

        field_dict: dict[str, Any] = {}

        field_dict.update({})
        if schema is not UNSET:
            field_dict["$schema"] = schema
        if change_annotations is not UNSET:
            field_dict["change_annotations"] = change_annotations

        return field_dict

    @classmethod
    def from_dict(cls, src_dict: Mapping[str, Any]) -> Self:
        from ..models.update_result_input_body_change_annotations_type_0 import (
            UpdateResultInputBodyChangeAnnotationsType0,
        )

        d = dict(src_dict)
        schema = d.pop("$schema", UNSET)

        def _parse_change_annotations(
            data: object,
        ) -> None | Unset | UpdateResultInputBodyChangeAnnotationsType0:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            try:
                if not isinstance(data, dict):
                    raise TypeError()
                change_annotations_type_0 = (
                    UpdateResultInputBodyChangeAnnotationsType0.from_dict(data)
                )

                return change_annotations_type_0
            except (TypeError, ValueError, AttributeError, KeyError):
                pass
            return cast(
                None | Unset | UpdateResultInputBodyChangeAnnotationsType0, data
            )

        change_annotations = _parse_change_annotations(
            d.pop("change_annotations", UNSET)
        )

        update_result_input_body = cls(
            schema=schema,
            change_annotations=change_annotations,
        )

        return update_result_input_body
