from __future__ import annotations

from collections.abc import Mapping
from typing import Any, TypeVar, cast

from attrs import define as _attrs_define

T = TypeVar("T", bound="ZScoreStatsType0")


@_attrs_define
class ZScoreStatsType0:
    """
    Attributes:
        begins_distribution_change (bool):
        is_outlier (bool):
        is_step (bool):
        residual (float | None):
        rolling_mean (float | None):
        rolling_mean_excluding_this_commit (float | None):
        rolling_stddev (float | None):
        segment_id (int):
    """

    begins_distribution_change: bool
    is_outlier: bool
    is_step: bool
    residual: float | None
    rolling_mean: float | None
    rolling_mean_excluding_this_commit: float | None
    rolling_stddev: float | None
    segment_id: int

    def to_dict(self) -> dict[str, Any]:
        begins_distribution_change = self.begins_distribution_change

        is_outlier = self.is_outlier

        is_step = self.is_step

        residual: float | None
        residual = self.residual

        rolling_mean: float | None
        rolling_mean = self.rolling_mean

        rolling_mean_excluding_this_commit: float | None
        rolling_mean_excluding_this_commit = self.rolling_mean_excluding_this_commit

        rolling_stddev: float | None
        rolling_stddev = self.rolling_stddev

        segment_id = self.segment_id

        field_dict: dict[str, Any] = {}

        field_dict.update(
            {
                "begins_distribution_change": begins_distribution_change,
                "is_outlier": is_outlier,
                "is_step": is_step,
                "residual": residual,
                "rolling_mean": rolling_mean,
                "rolling_mean_excluding_this_commit": rolling_mean_excluding_this_commit,
                "rolling_stddev": rolling_stddev,
                "segment_id": segment_id,
            }
        )

        return field_dict

    @classmethod
    def from_dict(cls: type[T], src_dict: Mapping[str, Any]) -> T:
        d = dict(src_dict)
        begins_distribution_change = d.pop("begins_distribution_change")

        is_outlier = d.pop("is_outlier")

        is_step = d.pop("is_step")

        def _parse_residual(data: object) -> float | None:
            if data is None:
                return data
            return cast(float | None, data)

        residual = _parse_residual(d.pop("residual"))

        def _parse_rolling_mean(data: object) -> float | None:
            if data is None:
                return data
            return cast(float | None, data)

        rolling_mean = _parse_rolling_mean(d.pop("rolling_mean"))

        def _parse_rolling_mean_excluding_this_commit(data: object) -> float | None:
            if data is None:
                return data
            return cast(float | None, data)

        rolling_mean_excluding_this_commit = _parse_rolling_mean_excluding_this_commit(
            d.pop("rolling_mean_excluding_this_commit")
        )

        def _parse_rolling_stddev(data: object) -> float | None:
            if data is None:
                return data
            return cast(float | None, data)

        rolling_stddev = _parse_rolling_stddev(d.pop("rolling_stddev"))

        segment_id = d.pop("segment_id")

        z_score_stats_type_0 = cls(
            begins_distribution_change=begins_distribution_change,
            is_outlier=is_outlier,
            is_step=is_step,
            residual=residual,
            rolling_mean=rolling_mean,
            rolling_mean_excluding_this_commit=rolling_mean_excluding_this_commit,
            rolling_stddev=rolling_stddev,
            segment_id=segment_id,
        )

        return z_score_stats_type_0
