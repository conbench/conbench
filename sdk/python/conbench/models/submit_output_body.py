from __future__ import annotations

from collections.abc import Mapping
from typing import Any, Self, TypeVar

from attrs import define as _attrs_define

from ..types import UNSET, Unset

T = TypeVar("T", bound="SubmitOutputBody")


@_attrs_define
class SubmitOutputBody:
    """
    Attributes:
        history_fingerprint (str):
        id (str):
        run_id (str):
        schema (str | Unset): A URL to the JSON Schema for this object.
    """

    history_fingerprint: str
    id: str
    run_id: str
    schema: str | Unset = UNSET

    def to_dict(self) -> dict[str, Any]:
        history_fingerprint = self.history_fingerprint

        id = self.id

        run_id = self.run_id

        schema = self.schema

        field_dict: dict[str, Any] = {}

        field_dict.update(
            {
                "history_fingerprint": history_fingerprint,
                "id": id,
                "run_id": run_id,
            }
        )
        if schema is not UNSET:
            field_dict["$schema"] = schema

        return field_dict

    @classmethod
    def from_dict(cls, src_dict: Mapping[str, Any]) -> Self:
        d = dict(src_dict)
        history_fingerprint = d.pop("history_fingerprint")

        id = d.pop("id")

        run_id = d.pop("run_id")

        schema = d.pop("$schema", UNSET)

        submit_output_body = cls(
            history_fingerprint=history_fingerprint,
            id=id,
            run_id=run_id,
            schema=schema,
        )

        return submit_output_body
