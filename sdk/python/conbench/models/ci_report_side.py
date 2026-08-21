from __future__ import annotations

import datetime
from collections.abc import Mapping
from typing import TYPE_CHECKING, Any, Self, TypeVar, cast

from attrs import define as _attrs_define

if TYPE_CHECKING:
    from ..models.ci_report_side_error_type_0 import CIReportSideErrorType0


T = TypeVar("T", bound="CIReportSide")


@_attrs_define
class CIReportSide:
    """
    Attributes:
        commit_sha (None | str):
        commit_timestamp (datetime.datetime | None):
        error (CIReportSideErrorType0 | None):
        result_id (str):
        result_timestamp (datetime.datetime):
        run_id (str):
        single_value_summary (float | None):
        single_value_summary_type (str):
    """

    commit_sha: None | str
    commit_timestamp: datetime.datetime | None
    error: CIReportSideErrorType0 | None
    result_id: str
    result_timestamp: datetime.datetime
    run_id: str
    single_value_summary: float | None
    single_value_summary_type: str

    def to_dict(self) -> dict[str, Any]:
        from ..models.ci_report_side_error_type_0 import CIReportSideErrorType0

        commit_sha: None | str
        commit_sha = self.commit_sha

        commit_timestamp: None | str
        if isinstance(self.commit_timestamp, datetime.datetime):
            commit_timestamp = self.commit_timestamp.isoformat()
        else:
            commit_timestamp = self.commit_timestamp

        error: dict[str, Any] | None
        if isinstance(self.error, CIReportSideErrorType0):
            error = self.error.to_dict()
        else:
            error = self.error

        result_id = self.result_id

        result_timestamp = self.result_timestamp.isoformat()

        run_id = self.run_id

        single_value_summary: float | None
        single_value_summary = self.single_value_summary

        single_value_summary_type = self.single_value_summary_type

        field_dict: dict[str, Any] = {}

        field_dict.update(
            {
                "commit_sha": commit_sha,
                "commit_timestamp": commit_timestamp,
                "error": error,
                "result_id": result_id,
                "result_timestamp": result_timestamp,
                "run_id": run_id,
                "single_value_summary": single_value_summary,
                "single_value_summary_type": single_value_summary_type,
            }
        )

        return field_dict

    @classmethod
    def from_dict(cls, src_dict: Mapping[str, Any]) -> Self:
        from ..models.ci_report_side_error_type_0 import CIReportSideErrorType0

        d = dict(src_dict)

        def _parse_commit_sha(data: object) -> None | str:
            if data is None:
                return data
            return cast(None | str, data)

        commit_sha = _parse_commit_sha(d.pop("commit_sha"))

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

        def _parse_error(data: object) -> CIReportSideErrorType0 | None:
            if data is None:
                return data
            try:
                if not isinstance(data, dict):
                    raise TypeError()
                error_type_0 = CIReportSideErrorType0.from_dict(data)

                return error_type_0
            except (TypeError, ValueError, AttributeError, KeyError):
                pass
            return cast(CIReportSideErrorType0 | None, data)

        error = _parse_error(d.pop("error"))

        result_id = d.pop("result_id")

        result_timestamp = datetime.datetime.fromisoformat(d.pop("result_timestamp"))

        run_id = d.pop("run_id")

        def _parse_single_value_summary(data: object) -> float | None:
            if data is None:
                return data
            return cast(float | None, data)

        single_value_summary = _parse_single_value_summary(
            d.pop("single_value_summary")
        )

        single_value_summary_type = d.pop("single_value_summary_type")

        ci_report_side = cls(
            commit_sha=commit_sha,
            commit_timestamp=commit_timestamp,
            error=error,
            result_id=result_id,
            result_timestamp=result_timestamp,
            run_id=run_id,
            single_value_summary=single_value_summary,
            single_value_summary_type=single_value_summary_type,
        )

        return ci_report_side
