from __future__ import annotations

import datetime
from collections.abc import Mapping
from typing import TYPE_CHECKING, Any, TypeVar, cast

from attrs import define as _attrs_define

from ..types import UNSET, Unset

if TYPE_CHECKING:
    from ..models.aggregates import Aggregates
    from ..models.commit_type_0 import CommitType0
    from ..models.hardware import Hardware
    from ..models.result_detail_change_annotations import ResultDetailChangeAnnotations
    from ..models.result_detail_context import ResultDetailContext
    from ..models.result_detail_error_type_0 import ResultDetailErrorType0
    from ..models.result_detail_info import ResultDetailInfo
    from ..models.result_detail_optional_benchmark_info_type_0 import (
        ResultDetailOptionalBenchmarkInfoType0,
    )
    from ..models.result_detail_run_tags import ResultDetailRunTags
    from ..models.result_detail_tags import ResultDetailTags
    from ..models.result_detail_validation_type_0 import ResultDetailValidationType0


T = TypeVar("T", bound="ResultDetail")


@_attrs_define
class ResultDetail:
    """
    Attributes:
        batch_id (None | str):
        change_annotations (ResultDetailChangeAnnotations):
        commit (CommitType0 | None):
        commit_repo_url (str):
        context (ResultDetailContext):
        data (list[float | None] | None):
        error (None | ResultDetailErrorType0):
        hardware (Hardware):
        history_fingerprint (str):
        id (str):
        info (ResultDetailInfo):
        iterations (int | None):
        less_is_better (bool | None):
        optional_benchmark_info (None | ResultDetailOptionalBenchmarkInfoType0):
        run_id (str):
        run_reason (None | str):
        run_tags (ResultDetailRunTags):
        single_value_summary (float | None):
        single_value_summary_type (str):
        stats (Aggregates):
        tags (ResultDetailTags):
        time_unit (None | str):
        times (list[float | None] | None):
        timestamp (datetime.datetime):
        unit (None | str):
        validation (None | ResultDetailValidationType0):
        schema (str | Unset): A URL to the JSON Schema for this object.
    """

    batch_id: None | str
    change_annotations: ResultDetailChangeAnnotations
    commit: CommitType0 | None
    commit_repo_url: str
    context: ResultDetailContext
    data: list[float | None] | None
    error: None | ResultDetailErrorType0
    hardware: Hardware
    history_fingerprint: str
    id: str
    info: ResultDetailInfo
    iterations: int | None
    less_is_better: bool | None
    optional_benchmark_info: None | ResultDetailOptionalBenchmarkInfoType0
    run_id: str
    run_reason: None | str
    run_tags: ResultDetailRunTags
    single_value_summary: float | None
    single_value_summary_type: str
    stats: Aggregates
    tags: ResultDetailTags
    time_unit: None | str
    times: list[float | None] | None
    timestamp: datetime.datetime
    unit: None | str
    validation: None | ResultDetailValidationType0
    schema: str | Unset = UNSET

    def to_dict(self) -> dict[str, Any]:
        from ..models.commit_type_0 import CommitType0
        from ..models.result_detail_error_type_0 import ResultDetailErrorType0
        from ..models.result_detail_optional_benchmark_info_type_0 import (
            ResultDetailOptionalBenchmarkInfoType0,
        )
        from ..models.result_detail_validation_type_0 import ResultDetailValidationType0

        batch_id: None | str
        batch_id = self.batch_id

        change_annotations = self.change_annotations.to_dict()

        commit: dict[str, Any] | None
        if isinstance(self.commit, CommitType0):
            commit = self.commit.to_dict()
        else:
            commit = self.commit

        commit_repo_url = self.commit_repo_url

        context = self.context.to_dict()

        data: list[float | None] | None
        if isinstance(self.data, list):
            data = []
            for data_type_0_item_data in self.data:
                data_type_0_item: float | None
                data_type_0_item = data_type_0_item_data
                data.append(data_type_0_item)

        else:
            data = self.data

        error: dict[str, Any] | None
        if isinstance(self.error, ResultDetailErrorType0):
            error = self.error.to_dict()
        else:
            error = self.error

        hardware = self.hardware.to_dict()

        history_fingerprint = self.history_fingerprint

        id = self.id

        info = self.info.to_dict()

        iterations: int | None
        iterations = self.iterations

        less_is_better: bool | None
        less_is_better = self.less_is_better

        optional_benchmark_info: dict[str, Any] | None
        if isinstance(
            self.optional_benchmark_info, ResultDetailOptionalBenchmarkInfoType0
        ):
            optional_benchmark_info = self.optional_benchmark_info.to_dict()
        else:
            optional_benchmark_info = self.optional_benchmark_info

        run_id = self.run_id

        run_reason: None | str
        run_reason = self.run_reason

        run_tags = self.run_tags.to_dict()

        single_value_summary: float | None
        single_value_summary = self.single_value_summary

        single_value_summary_type = self.single_value_summary_type

        stats = self.stats.to_dict()

        tags = self.tags.to_dict()

        time_unit: None | str
        time_unit = self.time_unit

        times: list[float | None] | None
        if isinstance(self.times, list):
            times = []
            for times_type_0_item_data in self.times:
                times_type_0_item: float | None
                times_type_0_item = times_type_0_item_data
                times.append(times_type_0_item)

        else:
            times = self.times

        timestamp = self.timestamp.isoformat()

        unit: None | str
        unit = self.unit

        validation: dict[str, Any] | None
        if isinstance(self.validation, ResultDetailValidationType0):
            validation = self.validation.to_dict()
        else:
            validation = self.validation

        schema = self.schema

        field_dict: dict[str, Any] = {}

        field_dict.update(
            {
                "batch_id": batch_id,
                "change_annotations": change_annotations,
                "commit": commit,
                "commit_repo_url": commit_repo_url,
                "context": context,
                "data": data,
                "error": error,
                "hardware": hardware,
                "history_fingerprint": history_fingerprint,
                "id": id,
                "info": info,
                "iterations": iterations,
                "less_is_better": less_is_better,
                "optional_benchmark_info": optional_benchmark_info,
                "run_id": run_id,
                "run_reason": run_reason,
                "run_tags": run_tags,
                "single_value_summary": single_value_summary,
                "single_value_summary_type": single_value_summary_type,
                "stats": stats,
                "tags": tags,
                "time_unit": time_unit,
                "times": times,
                "timestamp": timestamp,
                "unit": unit,
                "validation": validation,
            }
        )
        if schema is not UNSET:
            field_dict["$schema"] = schema

        return field_dict

    @classmethod
    def from_dict(cls: type[T], src_dict: Mapping[str, Any]) -> T:
        from ..models.aggregates import Aggregates
        from ..models.commit_type_0 import CommitType0
        from ..models.hardware import Hardware
        from ..models.result_detail_change_annotations import (
            ResultDetailChangeAnnotations,
        )
        from ..models.result_detail_context import ResultDetailContext
        from ..models.result_detail_error_type_0 import ResultDetailErrorType0
        from ..models.result_detail_info import ResultDetailInfo
        from ..models.result_detail_optional_benchmark_info_type_0 import (
            ResultDetailOptionalBenchmarkInfoType0,
        )
        from ..models.result_detail_run_tags import ResultDetailRunTags
        from ..models.result_detail_tags import ResultDetailTags
        from ..models.result_detail_validation_type_0 import ResultDetailValidationType0

        d = dict(src_dict)

        def _parse_batch_id(data: object) -> None | str:
            if data is None:
                return data
            return cast(None | str, data)

        batch_id = _parse_batch_id(d.pop("batch_id"))

        change_annotations = ResultDetailChangeAnnotations.from_dict(
            d.pop("change_annotations")
        )

        def _parse_commit(data: object) -> CommitType0 | None:
            if data is None:
                return data
            try:
                if not isinstance(data, dict):
                    raise TypeError()
                componentsschemas_commit_type_0 = CommitType0.from_dict(data)

                return componentsschemas_commit_type_0
            except (TypeError, ValueError, AttributeError, KeyError):
                pass
            return cast(CommitType0 | None, data)

        commit = _parse_commit(d.pop("commit"))

        commit_repo_url = d.pop("commit_repo_url")

        context = ResultDetailContext.from_dict(d.pop("context"))

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

        def _parse_error(data: object) -> None | ResultDetailErrorType0:
            if data is None:
                return data
            try:
                if not isinstance(data, dict):
                    raise TypeError()
                error_type_0 = ResultDetailErrorType0.from_dict(data)

                return error_type_0
            except (TypeError, ValueError, AttributeError, KeyError):
                pass
            return cast(None | ResultDetailErrorType0, data)

        error = _parse_error(d.pop("error"))

        hardware = Hardware.from_dict(d.pop("hardware"))

        history_fingerprint = d.pop("history_fingerprint")

        id = d.pop("id")

        info = ResultDetailInfo.from_dict(d.pop("info"))

        def _parse_iterations(data: object) -> int | None:
            if data is None:
                return data
            return cast(int | None, data)

        iterations = _parse_iterations(d.pop("iterations"))

        def _parse_less_is_better(data: object) -> bool | None:
            if data is None:
                return data
            return cast(bool | None, data)

        less_is_better = _parse_less_is_better(d.pop("less_is_better"))

        def _parse_optional_benchmark_info(
            data: object,
        ) -> None | ResultDetailOptionalBenchmarkInfoType0:
            if data is None:
                return data
            try:
                if not isinstance(data, dict):
                    raise TypeError()
                optional_benchmark_info_type_0 = (
                    ResultDetailOptionalBenchmarkInfoType0.from_dict(data)
                )

                return optional_benchmark_info_type_0
            except (TypeError, ValueError, AttributeError, KeyError):
                pass
            return cast(None | ResultDetailOptionalBenchmarkInfoType0, data)

        optional_benchmark_info = _parse_optional_benchmark_info(
            d.pop("optional_benchmark_info")
        )

        run_id = d.pop("run_id")

        def _parse_run_reason(data: object) -> None | str:
            if data is None:
                return data
            return cast(None | str, data)

        run_reason = _parse_run_reason(d.pop("run_reason"))

        run_tags = ResultDetailRunTags.from_dict(d.pop("run_tags"))

        def _parse_single_value_summary(data: object) -> float | None:
            if data is None:
                return data
            return cast(float | None, data)

        single_value_summary = _parse_single_value_summary(
            d.pop("single_value_summary")
        )

        single_value_summary_type = d.pop("single_value_summary_type")

        stats = Aggregates.from_dict(d.pop("stats"))

        tags = ResultDetailTags.from_dict(d.pop("tags"))

        def _parse_time_unit(data: object) -> None | str:
            if data is None:
                return data
            return cast(None | str, data)

        time_unit = _parse_time_unit(d.pop("time_unit"))

        def _parse_times(data: object) -> list[float | None] | None:
            if data is None:
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
            return cast(list[float | None] | None, data)

        times = _parse_times(d.pop("times"))

        timestamp = datetime.datetime.fromisoformat(d.pop("timestamp"))

        def _parse_unit(data: object) -> None | str:
            if data is None:
                return data
            return cast(None | str, data)

        unit = _parse_unit(d.pop("unit"))

        def _parse_validation(data: object) -> None | ResultDetailValidationType0:
            if data is None:
                return data
            try:
                if not isinstance(data, dict):
                    raise TypeError()
                validation_type_0 = ResultDetailValidationType0.from_dict(data)

                return validation_type_0
            except (TypeError, ValueError, AttributeError, KeyError):
                pass
            return cast(None | ResultDetailValidationType0, data)

        validation = _parse_validation(d.pop("validation"))

        schema = d.pop("$schema", UNSET)

        result_detail = cls(
            batch_id=batch_id,
            change_annotations=change_annotations,
            commit=commit,
            commit_repo_url=commit_repo_url,
            context=context,
            data=data,
            error=error,
            hardware=hardware,
            history_fingerprint=history_fingerprint,
            id=id,
            info=info,
            iterations=iterations,
            less_is_better=less_is_better,
            optional_benchmark_info=optional_benchmark_info,
            run_id=run_id,
            run_reason=run_reason,
            run_tags=run_tags,
            single_value_summary=single_value_summary,
            single_value_summary_type=single_value_summary_type,
            stats=stats,
            tags=tags,
            time_unit=time_unit,
            times=times,
            timestamp=timestamp,
            unit=unit,
            validation=validation,
            schema=schema,
        )

        return result_detail
