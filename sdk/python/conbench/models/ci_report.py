from __future__ import annotations

from collections.abc import Mapping
from typing import TYPE_CHECKING, Any, TypeVar, cast

from attrs import define as _attrs_define

from ..models.ci_report_status import CIReportStatus
from ..types import UNSET, Unset

if TYPE_CHECKING:
    from ..models.ci_report_run import CIReportRun
    from ..models.ci_report_summary import CIReportSummary


T = TypeVar("T", bound="CIReport")


@_attrs_define
class CIReport:
    """
    Attributes:
        baseline (str):
        commit_sha (None | str):
        missing_run_ids (list[str] | None):
        report_url (str):
        repository (str):
        runs (list[CIReportRun] | None):
        selected_run_ids (list[str] | None):
        status (CIReportStatus):
        status_reason (str):
        summary (CIReportSummary):
        threshold (float):
        threshold_z (float):
        schema (str | Unset): A URL to the JSON Schema for this object.
    """

    baseline: str
    commit_sha: None | str
    missing_run_ids: list[str] | None
    report_url: str
    repository: str
    runs: list[CIReportRun] | None
    selected_run_ids: list[str] | None
    status: CIReportStatus
    status_reason: str
    summary: CIReportSummary
    threshold: float
    threshold_z: float
    schema: str | Unset = UNSET

    def to_dict(self) -> dict[str, Any]:
        baseline = self.baseline

        commit_sha: None | str
        commit_sha = self.commit_sha

        missing_run_ids: list[str] | None
        if isinstance(self.missing_run_ids, list):
            missing_run_ids = self.missing_run_ids

        else:
            missing_run_ids = self.missing_run_ids

        report_url = self.report_url

        repository = self.repository

        runs: list[dict[str, Any]] | None
        if isinstance(self.runs, list):
            runs = []
            for runs_type_0_item_data in self.runs:
                runs_type_0_item = runs_type_0_item_data.to_dict()
                runs.append(runs_type_0_item)

        else:
            runs = self.runs

        selected_run_ids: list[str] | None
        if isinstance(self.selected_run_ids, list):
            selected_run_ids = self.selected_run_ids

        else:
            selected_run_ids = self.selected_run_ids

        status = self.status.value

        status_reason = self.status_reason

        summary = self.summary.to_dict()

        threshold = self.threshold

        threshold_z = self.threshold_z

        schema = self.schema

        field_dict: dict[str, Any] = {}

        field_dict.update(
            {
                "baseline": baseline,
                "commit_sha": commit_sha,
                "missing_run_ids": missing_run_ids,
                "report_url": report_url,
                "repository": repository,
                "runs": runs,
                "selected_run_ids": selected_run_ids,
                "status": status,
                "status_reason": status_reason,
                "summary": summary,
                "threshold": threshold,
                "threshold_z": threshold_z,
            }
        )
        if schema is not UNSET:
            field_dict["$schema"] = schema

        return field_dict

    @classmethod
    def from_dict(cls: type[T], src_dict: Mapping[str, Any]) -> T:
        from ..models.ci_report_run import CIReportRun
        from ..models.ci_report_summary import CIReportSummary

        d = dict(src_dict)
        baseline = d.pop("baseline")

        def _parse_commit_sha(data: object) -> None | str:
            if data is None:
                return data
            return cast(None | str, data)

        commit_sha = _parse_commit_sha(d.pop("commit_sha"))

        def _parse_missing_run_ids(data: object) -> list[str] | None:
            if data is None:
                return data
            try:
                if not isinstance(data, list):
                    raise TypeError()
                missing_run_ids_type_0 = cast(list[str], data)

                return missing_run_ids_type_0
            except (TypeError, ValueError, AttributeError, KeyError):
                pass
            return cast(list[str] | None, data)

        missing_run_ids = _parse_missing_run_ids(d.pop("missing_run_ids"))

        report_url = d.pop("report_url")

        repository = d.pop("repository")

        def _parse_runs(data: object) -> list[CIReportRun] | None:
            if data is None:
                return data
            try:
                if not isinstance(data, list):
                    raise TypeError()
                runs_type_0 = []
                _runs_type_0 = data
                for runs_type_0_item_data in _runs_type_0:
                    runs_type_0_item = CIReportRun.from_dict(runs_type_0_item_data)

                    runs_type_0.append(runs_type_0_item)

                return runs_type_0
            except (TypeError, ValueError, AttributeError, KeyError):
                pass
            return cast(list[CIReportRun] | None, data)

        runs = _parse_runs(d.pop("runs"))

        def _parse_selected_run_ids(data: object) -> list[str] | None:
            if data is None:
                return data
            try:
                if not isinstance(data, list):
                    raise TypeError()
                selected_run_ids_type_0 = cast(list[str], data)

                return selected_run_ids_type_0
            except (TypeError, ValueError, AttributeError, KeyError):
                pass
            return cast(list[str] | None, data)

        selected_run_ids = _parse_selected_run_ids(d.pop("selected_run_ids"))

        status = CIReportStatus(d.pop("status"))

        status_reason = d.pop("status_reason")

        summary = CIReportSummary.from_dict(d.pop("summary"))

        threshold = d.pop("threshold")

        threshold_z = d.pop("threshold_z")

        schema = d.pop("$schema", UNSET)

        ci_report = cls(
            baseline=baseline,
            commit_sha=commit_sha,
            missing_run_ids=missing_run_ids,
            report_url=report_url,
            repository=repository,
            runs=runs,
            selected_run_ids=selected_run_ids,
            status=status,
            status_reason=status_reason,
            summary=summary,
            threshold=threshold,
            threshold_z=threshold_z,
            schema=schema,
        )

        return ci_report
