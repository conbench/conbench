from __future__ import annotations

from collections.abc import Mapping
from typing import TYPE_CHECKING, Any, Self, TypeVar, cast

from attrs import define as _attrs_define

from ..types import UNSET, Unset

if TYPE_CHECKING:
    from ..models.error_detail import ErrorDetail


T = TypeVar("T", bound="ErrorModel")


@_attrs_define
class ErrorModel:
    """
    Attributes:
        schema (str | Unset): A URL to the JSON Schema for this object.
        detail (str | Unset): A human-readable explanation specific to this occurrence of the problem.
        errors (list[ErrorDetail] | None | Unset): Optional list of individual error details
        instance (str | Unset): A URI reference that identifies the specific occurrence of the problem.
        status (int | Unset): HTTP status code
        title (str | Unset): A short, human-readable summary of the problem type. This value should not change between
            occurrences of the error.
        type_ (str | Unset): A URI reference to human-readable documentation for the error. Default: 'about:blank'.
    """

    schema: str | Unset = UNSET
    detail: str | Unset = UNSET
    errors: list[ErrorDetail] | None | Unset = UNSET
    instance: str | Unset = UNSET
    status: int | Unset = UNSET
    title: str | Unset = UNSET
    type_: str | Unset = "about:blank"

    def to_dict(self) -> dict[str, Any]:
        schema = self.schema

        detail = self.detail

        errors: list[dict[str, Any]] | None | Unset
        if isinstance(self.errors, Unset):
            errors = UNSET
        elif isinstance(self.errors, list):
            errors = []
            for errors_type_0_item_data in self.errors:
                errors_type_0_item = errors_type_0_item_data.to_dict()
                errors.append(errors_type_0_item)

        else:
            errors = self.errors

        instance = self.instance

        status = self.status

        title = self.title

        type_ = self.type_

        field_dict: dict[str, Any] = {}

        field_dict.update({})
        if schema is not UNSET:
            field_dict["$schema"] = schema
        if detail is not UNSET:
            field_dict["detail"] = detail
        if errors is not UNSET:
            field_dict["errors"] = errors
        if instance is not UNSET:
            field_dict["instance"] = instance
        if status is not UNSET:
            field_dict["status"] = status
        if title is not UNSET:
            field_dict["title"] = title
        if type_ is not UNSET:
            field_dict["type"] = type_

        return field_dict

    @classmethod
    def from_dict(cls, src_dict: Mapping[str, Any]) -> Self:
        from ..models.error_detail import ErrorDetail

        d = dict(src_dict)
        schema = d.pop("$schema", UNSET)

        detail = d.pop("detail", UNSET)

        def _parse_errors(data: object) -> list[ErrorDetail] | None | Unset:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            try:
                if not isinstance(data, list):
                    raise TypeError()
                errors_type_0 = []
                _errors_type_0 = data
                for errors_type_0_item_data in _errors_type_0:
                    errors_type_0_item = ErrorDetail.from_dict(errors_type_0_item_data)

                    errors_type_0.append(errors_type_0_item)

                return errors_type_0
            except (TypeError, ValueError, AttributeError, KeyError):
                pass
            return cast(list[ErrorDetail] | None | Unset, data)

        errors = _parse_errors(d.pop("errors", UNSET))

        instance = d.pop("instance", UNSET)

        status = d.pop("status", UNSET)

        title = d.pop("title", UNSET)

        type_ = d.pop("type", UNSET)

        error_model = cls(
            schema=schema,
            detail=detail,
            errors=errors,
            instance=instance,
            status=status,
            title=title,
            type_=type_,
        )

        return error_model
