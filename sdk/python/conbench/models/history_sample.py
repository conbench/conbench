from __future__ import annotations

import datetime
from collections.abc import Mapping
from typing import TYPE_CHECKING, Any, Self, TypeVar, cast

from attrs import define as _attrs_define

if TYPE_CHECKING:
    from ..models.history_sample_change_annotations import (
        HistorySampleChangeAnnotations,
    )
    from ..models.history_sample_info import HistorySampleInfo
    from ..models.history_sample_run_tags import HistorySampleRunTags
    from ..models.z_score_stats_type_0 import ZScoreStatsType0


T = TypeVar("T", bound="HistorySample")


@_attrs_define
class HistorySample:
    """
    Attributes:
        benchmark_result_id (str):
        change_annotations (HistorySampleChangeAnnotations):
        commit_hash (str):
        commit_message (str):
        commit_repository (str):
        commit_timestamp (datetime.datetime | None):
        data (list[float] | None):
        hardware_hash (str):
        info (HistorySampleInfo):
        mean (float | None):
        result_timestamp (datetime.datetime):
        run_tags (HistorySampleRunTags):
        single_value_summary (float):
        single_value_summary_type (str):
        unit (None | str):
        zscorestats (None | ZScoreStatsType0):
    """

    benchmark_result_id: str
    change_annotations: HistorySampleChangeAnnotations
    commit_hash: str
    commit_message: str
    commit_repository: str
    commit_timestamp: datetime.datetime | None
    data: list[float] | None
    hardware_hash: str
    info: HistorySampleInfo
    mean: float | None
    result_timestamp: datetime.datetime
    run_tags: HistorySampleRunTags
    single_value_summary: float
    single_value_summary_type: str
    unit: None | str
    zscorestats: None | ZScoreStatsType0

    def to_dict(self) -> dict[str, Any]:
        from ..models.z_score_stats_type_0 import ZScoreStatsType0

        benchmark_result_id = self.benchmark_result_id

        change_annotations = self.change_annotations.to_dict()

        commit_hash = self.commit_hash

        commit_message = self.commit_message

        commit_repository = self.commit_repository

        commit_timestamp: None | str
        if isinstance(self.commit_timestamp, datetime.datetime):
            commit_timestamp = self.commit_timestamp.isoformat()
        else:
            commit_timestamp = self.commit_timestamp

        data: list[float] | None
        if isinstance(self.data, list):
            data = self.data

        else:
            data = self.data

        hardware_hash = self.hardware_hash

        info = self.info.to_dict()

        mean: float | None
        mean = self.mean

        result_timestamp = self.result_timestamp.isoformat()

        run_tags = self.run_tags.to_dict()

        single_value_summary = self.single_value_summary

        single_value_summary_type = self.single_value_summary_type

        unit: None | str
        unit = self.unit

        zscorestats: dict[str, Any] | None
        if isinstance(self.zscorestats, ZScoreStatsType0):
            zscorestats = self.zscorestats.to_dict()
        else:
            zscorestats = self.zscorestats

        field_dict: dict[str, Any] = {}

        field_dict.update(
            {
                "benchmark_result_id": benchmark_result_id,
                "change_annotations": change_annotations,
                "commit_hash": commit_hash,
                "commit_message": commit_message,
                "commit_repository": commit_repository,
                "commit_timestamp": commit_timestamp,
                "data": data,
                "hardware_hash": hardware_hash,
                "info": info,
                "mean": mean,
                "result_timestamp": result_timestamp,
                "run_tags": run_tags,
                "single_value_summary": single_value_summary,
                "single_value_summary_type": single_value_summary_type,
                "unit": unit,
                "zscorestats": zscorestats,
            }
        )

        return field_dict

    @classmethod
    def from_dict(cls, src_dict: Mapping[str, Any]) -> Self:
        from ..models.history_sample_change_annotations import (
            HistorySampleChangeAnnotations,
        )
        from ..models.history_sample_info import HistorySampleInfo
        from ..models.history_sample_run_tags import HistorySampleRunTags
        from ..models.z_score_stats_type_0 import ZScoreStatsType0

        d = dict(src_dict)
        benchmark_result_id = d.pop("benchmark_result_id")

        change_annotations = HistorySampleChangeAnnotations.from_dict(
            d.pop("change_annotations")
        )

        commit_hash = d.pop("commit_hash")

        commit_message = d.pop("commit_message")

        commit_repository = d.pop("commit_repository")

        def _parse_commit_timestamp(data: object) -> datetime.datetime | None:
            if data is None:
                return data
            try:
                if not isinstance(data, str):
                    raise TypeError()
                commit_timestamp_type_0 = datetime.datetime.fromisoformat(data)

                return commit_timestamp_type_0
            except (TypeError, ValueError, AttributeError, KeyError):
                pass
            return cast(datetime.datetime | None, data)

        commit_timestamp = _parse_commit_timestamp(d.pop("commit_timestamp"))

        def _parse_data(data: object) -> list[float] | None:
            if data is None:
                return data
            try:
                if not isinstance(data, list):
                    raise TypeError()
                data_type_0 = cast(list[float], data)

                return data_type_0
            except (TypeError, ValueError, AttributeError, KeyError):
                pass
            return cast(list[float] | None, data)

        data = _parse_data(d.pop("data"))

        hardware_hash = d.pop("hardware_hash")

        info = HistorySampleInfo.from_dict(d.pop("info"))

        def _parse_mean(data: object) -> float | None:
            if data is None:
                return data
            return cast(float | None, data)

        mean = _parse_mean(d.pop("mean"))

        result_timestamp = datetime.datetime.fromisoformat(d.pop("result_timestamp"))

        run_tags = HistorySampleRunTags.from_dict(d.pop("run_tags"))

        single_value_summary = d.pop("single_value_summary")

        single_value_summary_type = d.pop("single_value_summary_type")

        def _parse_unit(data: object) -> None | str:
            if data is None:
                return data
            return cast(None | str, data)

        unit = _parse_unit(d.pop("unit"))

        def _parse_zscorestats(data: object) -> None | ZScoreStatsType0:
            if data is None:
                return data
            try:
                if not isinstance(data, dict):
                    raise TypeError()
                componentsschemas_z_score_stats_type_0 = ZScoreStatsType0.from_dict(
                    data
                )

                return componentsschemas_z_score_stats_type_0
            except (TypeError, ValueError, AttributeError, KeyError):
                pass
            return cast(None | ZScoreStatsType0, data)

        zscorestats = _parse_zscorestats(d.pop("zscorestats"))

        history_sample = cls(
            benchmark_result_id=benchmark_result_id,
            change_annotations=change_annotations,
            commit_hash=commit_hash,
            commit_message=commit_message,
            commit_repository=commit_repository,
            commit_timestamp=commit_timestamp,
            data=data,
            hardware_hash=hardware_hash,
            info=info,
            mean=mean,
            result_timestamp=result_timestamp,
            run_tags=run_tags,
            single_value_summary=single_value_summary,
            single_value_summary_type=single_value_summary_type,
            unit=unit,
            zscorestats=zscorestats,
        )

        return history_sample
