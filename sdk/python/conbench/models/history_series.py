from __future__ import annotations

from collections.abc import Mapping
from typing import TYPE_CHECKING, Any, Self, TypeVar, cast

from attrs import define as _attrs_define

from ..types import UNSET, Unset

if TYPE_CHECKING:
    from ..models.history_sample import HistorySample


T = TypeVar("T", bound="HistorySeries")


@_attrs_define
class HistorySeries:
    """
    Attributes:
        history_fingerprint (str):
        samples (list[HistorySample] | None):
        schema (str | Unset): A URL to the JSON Schema for this object.
    """

    history_fingerprint: str
    samples: list[HistorySample] | None
    schema: str | Unset = UNSET

    def to_dict(self) -> dict[str, Any]:
        history_fingerprint = self.history_fingerprint

        samples: list[dict[str, Any]] | None
        if isinstance(self.samples, list):
            samples = []
            for samples_type_0_item_data in self.samples:
                samples_type_0_item = samples_type_0_item_data.to_dict()
                samples.append(samples_type_0_item)

        else:
            samples = self.samples

        schema = self.schema

        field_dict: dict[str, Any] = {}

        field_dict.update(
            {
                "history_fingerprint": history_fingerprint,
                "samples": samples,
            }
        )
        if schema is not UNSET:
            field_dict["$schema"] = schema

        return field_dict

    @classmethod
    def from_dict(cls, src_dict: Mapping[str, Any]) -> Self:
        from ..models.history_sample import HistorySample

        d = dict(src_dict)
        history_fingerprint = d.pop("history_fingerprint")

        def _parse_samples(data: object) -> list[HistorySample] | None:
            if data is None:
                return data
            try:
                if not isinstance(data, list):
                    raise TypeError()
                samples_type_0 = []
                _samples_type_0 = data
                for samples_type_0_item_data in _samples_type_0:
                    samples_type_0_item = HistorySample.from_dict(
                        samples_type_0_item_data
                    )

                    samples_type_0.append(samples_type_0_item)

                return samples_type_0
            except (TypeError, ValueError, AttributeError, KeyError):
                pass
            return cast(list[HistorySample] | None, data)

        samples = _parse_samples(d.pop("samples"))

        schema = d.pop("$schema", UNSET)

        history_series = cls(
            history_fingerprint=history_fingerprint,
            samples=samples,
            schema=schema,
        )

        return history_series
