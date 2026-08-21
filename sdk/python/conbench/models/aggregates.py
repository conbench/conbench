from __future__ import annotations

from collections.abc import Mapping
from typing import Any, Self, TypeVar, cast

from attrs import define as _attrs_define

T = TypeVar("T", bound="Aggregates")


@_attrs_define
class Aggregates:
    """
    Attributes:
        iqr (float | None):
        max_ (float | None):
        mean (float | None):
        median (float | None):
        min_ (float | None):
        q1 (float | None):
        q3 (float | None):
        stdev (float | None):
    """

    iqr: float | None
    max_: float | None
    mean: float | None
    median: float | None
    min_: float | None
    q1: float | None
    q3: float | None
    stdev: float | None

    def to_dict(self) -> dict[str, Any]:
        iqr: float | None
        iqr = self.iqr

        max_: float | None
        max_ = self.max_

        mean: float | None
        mean = self.mean

        median: float | None
        median = self.median

        min_: float | None
        min_ = self.min_

        q1: float | None
        q1 = self.q1

        q3: float | None
        q3 = self.q3

        stdev: float | None
        stdev = self.stdev

        field_dict: dict[str, Any] = {}

        field_dict.update(
            {
                "iqr": iqr,
                "max": max_,
                "mean": mean,
                "median": median,
                "min": min_,
                "q1": q1,
                "q3": q3,
                "stdev": stdev,
            }
        )

        return field_dict

    @classmethod
    def from_dict(cls, src_dict: Mapping[str, Any]) -> Self:
        d = dict(src_dict)

        def _parse_iqr(data: object) -> float | None:
            if data is None:
                return data
            return cast(float | None, data)

        iqr = _parse_iqr(d.pop("iqr"))

        def _parse_max_(data: object) -> float | None:
            if data is None:
                return data
            return cast(float | None, data)

        max_ = _parse_max_(d.pop("max"))

        def _parse_mean(data: object) -> float | None:
            if data is None:
                return data
            return cast(float | None, data)

        mean = _parse_mean(d.pop("mean"))

        def _parse_median(data: object) -> float | None:
            if data is None:
                return data
            return cast(float | None, data)

        median = _parse_median(d.pop("median"))

        def _parse_min_(data: object) -> float | None:
            if data is None:
                return data
            return cast(float | None, data)

        min_ = _parse_min_(d.pop("min"))

        def _parse_q1(data: object) -> float | None:
            if data is None:
                return data
            return cast(float | None, data)

        q1 = _parse_q1(d.pop("q1"))

        def _parse_q3(data: object) -> float | None:
            if data is None:
                return data
            return cast(float | None, data)

        q3 = _parse_q3(d.pop("q3"))

        def _parse_stdev(data: object) -> float | None:
            if data is None:
                return data
            return cast(float | None, data)

        stdev = _parse_stdev(d.pop("stdev"))

        aggregates = cls(
            iqr=iqr,
            max_=max_,
            mean=mean,
            median=median,
            min_=min_,
            q1=q1,
            q3=q3,
            stdev=stdev,
        )

        return aggregates
