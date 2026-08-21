from __future__ import annotations

from collections.abc import Mapping
from typing import Any, Self, TypeVar, cast

from attrs import define as _attrs_define

from ..types import UNSET, Unset

T = TypeVar("T", bound="StatsInput")


@_attrs_define
class StatsInput:
    """
    Attributes:
        data (list[float | None] | None):
        iqr (float | Unset):
        iterations (int | Unset):
        max_ (float | Unset):
        mean (float | Unset):
        median (float | Unset):
        min_ (float | Unset):
        q1 (float | Unset):
        q3 (float | Unset):
        stdev (float | Unset):
        time_unit (str | Unset):
        times (list[float | None] | None | Unset):
        unit (str | Unset):
    """

    data: list[float | None] | None
    iqr: float | Unset = UNSET
    iterations: int | Unset = UNSET
    max_: float | Unset = UNSET
    mean: float | Unset = UNSET
    median: float | Unset = UNSET
    min_: float | Unset = UNSET
    q1: float | Unset = UNSET
    q3: float | Unset = UNSET
    stdev: float | Unset = UNSET
    time_unit: str | Unset = UNSET
    times: list[float | None] | None | Unset = UNSET
    unit: str | Unset = UNSET

    def to_dict(self) -> dict[str, Any]:
        data: list[float | None] | None
        if isinstance(self.data, list):
            data = []
            for data_type_0_item_data in self.data:
                data_type_0_item: float | None
                data_type_0_item = data_type_0_item_data
                data.append(data_type_0_item)

        else:
            data = self.data

        iqr = self.iqr

        iterations = self.iterations

        max_ = self.max_

        mean = self.mean

        median = self.median

        min_ = self.min_

        q1 = self.q1

        q3 = self.q3

        stdev = self.stdev

        time_unit = self.time_unit

        times: list[float | None] | None | Unset
        if isinstance(self.times, Unset):
            times = UNSET
        elif isinstance(self.times, list):
            times = []
            for times_type_0_item_data in self.times:
                times_type_0_item: float | None
                times_type_0_item = times_type_0_item_data
                times.append(times_type_0_item)

        else:
            times = self.times

        unit = self.unit

        field_dict: dict[str, Any] = {}

        field_dict.update(
            {
                "data": data,
            }
        )
        if iqr is not UNSET:
            field_dict["iqr"] = iqr
        if iterations is not UNSET:
            field_dict["iterations"] = iterations
        if max_ is not UNSET:
            field_dict["max"] = max_
        if mean is not UNSET:
            field_dict["mean"] = mean
        if median is not UNSET:
            field_dict["median"] = median
        if min_ is not UNSET:
            field_dict["min"] = min_
        if q1 is not UNSET:
            field_dict["q1"] = q1
        if q3 is not UNSET:
            field_dict["q3"] = q3
        if stdev is not UNSET:
            field_dict["stdev"] = stdev
        if time_unit is not UNSET:
            field_dict["time_unit"] = time_unit
        if times is not UNSET:
            field_dict["times"] = times
        if unit is not UNSET:
            field_dict["unit"] = unit

        return field_dict

    @classmethod
    def from_dict(cls, src_dict: Mapping[str, Any]) -> Self:
        d = dict(src_dict)

        def _parse_data(data: object) -> list[float | None] | None:
            if data is None:
                return data
            try:
                if not isinstance(data, list):
                    raise TypeError()
                data_type_0 = []
                _data_type_0 = data
                for data_type_0_item_data in _data_type_0:

                    def _parse_data_type_0_item(data: object) -> float | None:
                        if data is None:
                            return data
                        return cast(float | None, data)

                    data_type_0_item = _parse_data_type_0_item(data_type_0_item_data)

                    data_type_0.append(data_type_0_item)

                return data_type_0
            except (TypeError, ValueError, AttributeError, KeyError):
                pass
            return cast(list[float | None] | None, data)

        data = _parse_data(d.pop("data"))

        iqr = d.pop("iqr", UNSET)

        iterations = d.pop("iterations", UNSET)

        max_ = d.pop("max", UNSET)

        mean = d.pop("mean", UNSET)

        median = d.pop("median", UNSET)

        min_ = d.pop("min", UNSET)

        q1 = d.pop("q1", UNSET)

        q3 = d.pop("q3", UNSET)

        stdev = d.pop("stdev", UNSET)

        time_unit = d.pop("time_unit", UNSET)

        def _parse_times(data: object) -> list[float | None] | None | Unset:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            try:
                if not isinstance(data, list):
                    raise TypeError()
                times_type_0 = []
                _times_type_0 = data
                for times_type_0_item_data in _times_type_0:

                    def _parse_times_type_0_item(data: object) -> float | None:
                        if data is None:
                            return data
                        return cast(float | None, data)

                    times_type_0_item = _parse_times_type_0_item(times_type_0_item_data)

                    times_type_0.append(times_type_0_item)

                return times_type_0
            except (TypeError, ValueError, AttributeError, KeyError):
                pass
            return cast(list[float | None] | None | Unset, data)

        times = _parse_times(d.pop("times", UNSET))

        unit = d.pop("unit", UNSET)

        stats_input = cls(
            data=data,
            iqr=iqr,
            iterations=iterations,
            max_=max_,
            mean=mean,
            median=median,
            min_=min_,
            q1=q1,
            q3=q3,
            stdev=stdev,
            time_unit=time_unit,
            times=times,
            unit=unit,
        )

        return stats_input
