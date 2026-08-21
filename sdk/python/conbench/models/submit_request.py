from __future__ import annotations

import datetime
from collections.abc import Mapping
from typing import TYPE_CHECKING, Any, Self, TypeVar, cast

from attrs import define as _attrs_define

from ..types import UNSET, Unset

if TYPE_CHECKING:
    from ..models.cluster_info import ClusterInfo
    from ..models.git_hub_info import GitHubInfo
    from ..models.machine_info import MachineInfo
    from ..models.stats_input import StatsInput
    from ..models.submit_request_change_annotations_type_0 import (
        SubmitRequestChangeAnnotationsType0,
    )
    from ..models.submit_request_context import SubmitRequestContext
    from ..models.submit_request_error import SubmitRequestError
    from ..models.submit_request_info import SubmitRequestInfo
    from ..models.submit_request_optional_benchmark_info_type_0 import (
        SubmitRequestOptionalBenchmarkInfoType0,
    )
    from ..models.submit_request_run_tags import SubmitRequestRunTags
    from ..models.submit_request_tags import SubmitRequestTags
    from ..models.submit_request_validation_type_0 import SubmitRequestValidationType0


T = TypeVar("T", bound="SubmitRequest")


@_attrs_define
class SubmitRequest:
    """
    Attributes:
        context (SubmitRequestContext):
        github (GitHubInfo):
        run_id (str):
        tags (SubmitRequestTags):
        timestamp (datetime.datetime):
        schema (str | Unset): A URL to the JSON Schema for this object.
        batch_id (str | Unset):
        change_annotations (None | SubmitRequestChangeAnnotationsType0 | Unset):
        cluster_info (ClusterInfo | Unset):
        error (SubmitRequestError | Unset):
        info (SubmitRequestInfo | Unset):
        machine_info (MachineInfo | Unset):
        optional_benchmark_info (None | SubmitRequestOptionalBenchmarkInfoType0 | Unset):
        run_name (str | Unset):
        run_reason (str | Unset):
        run_tags (SubmitRequestRunTags | Unset):
        stats (StatsInput | Unset):
        submission_key (str | Unset):
        submission_payload_sha256 (str | Unset):
        validation (None | SubmitRequestValidationType0 | Unset):
    """

    context: SubmitRequestContext
    github: GitHubInfo
    run_id: str
    tags: SubmitRequestTags
    timestamp: datetime.datetime
    schema: str | Unset = UNSET
    batch_id: str | Unset = UNSET
    change_annotations: None | SubmitRequestChangeAnnotationsType0 | Unset = UNSET
    cluster_info: ClusterInfo | Unset = UNSET
    error: SubmitRequestError | Unset = UNSET
    info: SubmitRequestInfo | Unset = UNSET
    machine_info: MachineInfo | Unset = UNSET
    optional_benchmark_info: None | SubmitRequestOptionalBenchmarkInfoType0 | Unset = (
        UNSET
    )
    run_name: str | Unset = UNSET
    run_reason: str | Unset = UNSET
    run_tags: SubmitRequestRunTags | Unset = UNSET
    stats: StatsInput | Unset = UNSET
    submission_key: str | Unset = UNSET
    submission_payload_sha256: str | Unset = UNSET
    validation: None | SubmitRequestValidationType0 | Unset = UNSET

    def to_dict(self) -> dict[str, Any]:
        from ..models.submit_request_change_annotations_type_0 import (
            SubmitRequestChangeAnnotationsType0,
        )
        from ..models.submit_request_optional_benchmark_info_type_0 import (
            SubmitRequestOptionalBenchmarkInfoType0,
        )
        from ..models.submit_request_validation_type_0 import (
            SubmitRequestValidationType0,
        )

        context = self.context.to_dict()

        github = self.github.to_dict()

        run_id = self.run_id

        tags = self.tags.to_dict()

        timestamp = self.timestamp.isoformat()

        schema = self.schema

        batch_id = self.batch_id

        change_annotations: dict[str, Any] | None | Unset
        if isinstance(self.change_annotations, Unset):
            change_annotations = UNSET
        elif isinstance(self.change_annotations, SubmitRequestChangeAnnotationsType0):
            change_annotations = self.change_annotations.to_dict()
        else:
            change_annotations = self.change_annotations

        cluster_info: dict[str, Any] | Unset = UNSET
        if not isinstance(self.cluster_info, Unset):
            cluster_info = self.cluster_info.to_dict()

        error: dict[str, Any] | Unset = UNSET
        if not isinstance(self.error, Unset):
            error = self.error.to_dict()

        info: dict[str, Any] | Unset = UNSET
        if not isinstance(self.info, Unset):
            info = self.info.to_dict()

        machine_info: dict[str, Any] | Unset = UNSET
        if not isinstance(self.machine_info, Unset):
            machine_info = self.machine_info.to_dict()

        optional_benchmark_info: dict[str, Any] | None | Unset
        if isinstance(self.optional_benchmark_info, Unset):
            optional_benchmark_info = UNSET
        elif isinstance(
            self.optional_benchmark_info, SubmitRequestOptionalBenchmarkInfoType0
        ):
            optional_benchmark_info = self.optional_benchmark_info.to_dict()
        else:
            optional_benchmark_info = self.optional_benchmark_info

        run_name = self.run_name

        run_reason = self.run_reason

        run_tags: dict[str, Any] | Unset = UNSET
        if not isinstance(self.run_tags, Unset):
            run_tags = self.run_tags.to_dict()

        stats: dict[str, Any] | Unset = UNSET
        if not isinstance(self.stats, Unset):
            stats = self.stats.to_dict()

        submission_key = self.submission_key

        submission_payload_sha256 = self.submission_payload_sha256

        validation: dict[str, Any] | None | Unset
        if isinstance(self.validation, Unset):
            validation = UNSET
        elif isinstance(self.validation, SubmitRequestValidationType0):
            validation = self.validation.to_dict()
        else:
            validation = self.validation

        field_dict: dict[str, Any] = {}

        field_dict.update(
            {
                "context": context,
                "github": github,
                "run_id": run_id,
                "tags": tags,
                "timestamp": timestamp,
            }
        )
        if schema is not UNSET:
            field_dict["$schema"] = schema
        if batch_id is not UNSET:
            field_dict["batch_id"] = batch_id
        if change_annotations is not UNSET:
            field_dict["change_annotations"] = change_annotations
        if cluster_info is not UNSET:
            field_dict["cluster_info"] = cluster_info
        if error is not UNSET:
            field_dict["error"] = error
        if info is not UNSET:
            field_dict["info"] = info
        if machine_info is not UNSET:
            field_dict["machine_info"] = machine_info
        if optional_benchmark_info is not UNSET:
            field_dict["optional_benchmark_info"] = optional_benchmark_info
        if run_name is not UNSET:
            field_dict["run_name"] = run_name
        if run_reason is not UNSET:
            field_dict["run_reason"] = run_reason
        if run_tags is not UNSET:
            field_dict["run_tags"] = run_tags
        if stats is not UNSET:
            field_dict["stats"] = stats
        if submission_key is not UNSET:
            field_dict["submission_key"] = submission_key
        if submission_payload_sha256 is not UNSET:
            field_dict["submission_payload_sha256"] = submission_payload_sha256
        if validation is not UNSET:
            field_dict["validation"] = validation

        return field_dict

    @classmethod
    def from_dict(cls, src_dict: Mapping[str, Any]) -> Self:
        from ..models.cluster_info import ClusterInfo
        from ..models.git_hub_info import GitHubInfo
        from ..models.machine_info import MachineInfo
        from ..models.stats_input import StatsInput
        from ..models.submit_request_change_annotations_type_0 import (
            SubmitRequestChangeAnnotationsType0,
        )
        from ..models.submit_request_context import SubmitRequestContext
        from ..models.submit_request_error import SubmitRequestError
        from ..models.submit_request_info import SubmitRequestInfo
        from ..models.submit_request_optional_benchmark_info_type_0 import (
            SubmitRequestOptionalBenchmarkInfoType0,
        )
        from ..models.submit_request_run_tags import SubmitRequestRunTags
        from ..models.submit_request_tags import SubmitRequestTags
        from ..models.submit_request_validation_type_0 import (
            SubmitRequestValidationType0,
        )

        d = dict(src_dict)
        context = SubmitRequestContext.from_dict(d.pop("context"))

        github = GitHubInfo.from_dict(d.pop("github"))

        run_id = d.pop("run_id")

        tags = SubmitRequestTags.from_dict(d.pop("tags"))

        timestamp = datetime.datetime.fromisoformat(d.pop("timestamp"))

        schema = d.pop("$schema", UNSET)

        batch_id = d.pop("batch_id", UNSET)

        def _parse_change_annotations(
            data: object,
        ) -> None | SubmitRequestChangeAnnotationsType0 | Unset:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            try:
                if not isinstance(data, dict):
                    raise TypeError()
                change_annotations_type_0 = (
                    SubmitRequestChangeAnnotationsType0.from_dict(data)
                )

                return change_annotations_type_0
            except (TypeError, ValueError, AttributeError, KeyError):
                pass
            return cast(None | SubmitRequestChangeAnnotationsType0 | Unset, data)

        change_annotations = _parse_change_annotations(
            d.pop("change_annotations", UNSET)
        )

        _cluster_info = d.pop("cluster_info", UNSET)
        cluster_info: ClusterInfo | Unset
        if isinstance(_cluster_info, Unset):
            cluster_info = UNSET
        else:
            cluster_info = ClusterInfo.from_dict(_cluster_info)

        _error = d.pop("error", UNSET)
        error: SubmitRequestError | Unset
        if isinstance(_error, Unset):
            error = UNSET
        else:
            error = SubmitRequestError.from_dict(_error)

        _info = d.pop("info", UNSET)
        info: SubmitRequestInfo | Unset
        if isinstance(_info, Unset):
            info = UNSET
        else:
            info = SubmitRequestInfo.from_dict(_info)

        _machine_info = d.pop("machine_info", UNSET)
        machine_info: MachineInfo | Unset
        if isinstance(_machine_info, Unset):
            machine_info = UNSET
        else:
            machine_info = MachineInfo.from_dict(_machine_info)

        def _parse_optional_benchmark_info(
            data: object,
        ) -> None | SubmitRequestOptionalBenchmarkInfoType0 | Unset:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            try:
                if not isinstance(data, dict):
                    raise TypeError()
                optional_benchmark_info_type_0 = (
                    SubmitRequestOptionalBenchmarkInfoType0.from_dict(data)
                )

                return optional_benchmark_info_type_0
            except (TypeError, ValueError, AttributeError, KeyError):
                pass
            return cast(None | SubmitRequestOptionalBenchmarkInfoType0 | Unset, data)

        optional_benchmark_info = _parse_optional_benchmark_info(
            d.pop("optional_benchmark_info", UNSET)
        )

        run_name = d.pop("run_name", UNSET)

        run_reason = d.pop("run_reason", UNSET)

        _run_tags = d.pop("run_tags", UNSET)
        run_tags: SubmitRequestRunTags | Unset
        if isinstance(_run_tags, Unset):
            run_tags = UNSET
        else:
            run_tags = SubmitRequestRunTags.from_dict(_run_tags)

        _stats = d.pop("stats", UNSET)
        stats: StatsInput | Unset
        if isinstance(_stats, Unset):
            stats = UNSET
        else:
            stats = StatsInput.from_dict(_stats)

        submission_key = d.pop("submission_key", UNSET)

        submission_payload_sha256 = d.pop("submission_payload_sha256", UNSET)

        def _parse_validation(
            data: object,
        ) -> None | SubmitRequestValidationType0 | Unset:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            try:
                if not isinstance(data, dict):
                    raise TypeError()
                validation_type_0 = SubmitRequestValidationType0.from_dict(data)

                return validation_type_0
            except (TypeError, ValueError, AttributeError, KeyError):
                pass
            return cast(None | SubmitRequestValidationType0 | Unset, data)

        validation = _parse_validation(d.pop("validation", UNSET))

        submit_request = cls(
            context=context,
            github=github,
            run_id=run_id,
            tags=tags,
            timestamp=timestamp,
            schema=schema,
            batch_id=batch_id,
            change_annotations=change_annotations,
            cluster_info=cluster_info,
            error=error,
            info=info,
            machine_info=machine_info,
            optional_benchmark_info=optional_benchmark_info,
            run_name=run_name,
            run_reason=run_reason,
            run_tags=run_tags,
            stats=stats,
            submission_key=submission_key,
            submission_payload_sha256=submission_payload_sha256,
            validation=validation,
        )

        return submit_request
