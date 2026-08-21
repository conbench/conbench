from __future__ import annotations

from collections.abc import Mapping
from typing import TYPE_CHECKING, Any, Self, TypeVar, cast

from attrs import define as _attrs_define

if TYPE_CHECKING:
    from ..models.ci_report_baseline_error_type_0 import CIReportBaselineErrorType0
    from ..models.ci_report_comparison import CIReportComparison
    from ..models.ci_report_run_run_tags import CIReportRunRunTags
    from ..models.commit_type_0 import CommitType0


T = TypeVar("T", bound="CIReportRun")


@_attrs_define
class CIReportRun:
    """
    Attributes:
        baseline_commit (CommitType0 | None):
        baseline_error (CIReportBaselineErrorType0 | None):
        baseline_run_id (None | str):
        commit (CommitType0 | None):
        commits_skipped (list[str] | None):
        comparisons (list[CIReportComparison] | None):
        run_id (str):
        run_reason (None | str):
        run_tags (CIReportRunRunTags):
    """

    baseline_commit: CommitType0 | None
    baseline_error: CIReportBaselineErrorType0 | None
    baseline_run_id: None | str
    commit: CommitType0 | None
    commits_skipped: list[str] | None
    comparisons: list[CIReportComparison] | None
    run_id: str
    run_reason: None | str
    run_tags: CIReportRunRunTags

    def to_dict(self) -> dict[str, Any]:
        from ..models.ci_report_baseline_error_type_0 import CIReportBaselineErrorType0
        from ..models.commit_type_0 import CommitType0

        baseline_commit: dict[str, Any] | None
        if isinstance(self.baseline_commit, CommitType0):
            baseline_commit = self.baseline_commit.to_dict()
        else:
            baseline_commit = self.baseline_commit

        baseline_error: dict[str, Any] | None
        if isinstance(self.baseline_error, CIReportBaselineErrorType0):
            baseline_error = self.baseline_error.to_dict()
        else:
            baseline_error = self.baseline_error

        baseline_run_id: None | str
        baseline_run_id = self.baseline_run_id

        commit: dict[str, Any] | None
        if isinstance(self.commit, CommitType0):
            commit = self.commit.to_dict()
        else:
            commit = self.commit

        commits_skipped: list[str] | None
        if isinstance(self.commits_skipped, list):
            commits_skipped = self.commits_skipped

        else:
            commits_skipped = self.commits_skipped

        comparisons: list[dict[str, Any]] | None
        if isinstance(self.comparisons, list):
            comparisons = []
            for comparisons_type_0_item_data in self.comparisons:
                comparisons_type_0_item = comparisons_type_0_item_data.to_dict()
                comparisons.append(comparisons_type_0_item)

        else:
            comparisons = self.comparisons

        run_id = self.run_id

        run_reason: None | str
        run_reason = self.run_reason

        run_tags = self.run_tags.to_dict()

        field_dict: dict[str, Any] = {}

        field_dict.update(
            {
                "baseline_commit": baseline_commit,
                "baseline_error": baseline_error,
                "baseline_run_id": baseline_run_id,
                "commit": commit,
                "commits_skipped": commits_skipped,
                "comparisons": comparisons,
                "run_id": run_id,
                "run_reason": run_reason,
                "run_tags": run_tags,
            }
        )

        return field_dict

    @classmethod
    def from_dict(cls, src_dict: Mapping[str, Any]) -> Self:
        from ..models.ci_report_baseline_error_type_0 import CIReportBaselineErrorType0
        from ..models.ci_report_comparison import CIReportComparison
        from ..models.ci_report_run_run_tags import CIReportRunRunTags
        from ..models.commit_type_0 import CommitType0

        d = dict(src_dict)

        def _parse_baseline_commit(data: object) -> CommitType0 | None:
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

        baseline_commit = _parse_baseline_commit(d.pop("baseline_commit"))

        def _parse_baseline_error(data: object) -> CIReportBaselineErrorType0 | None:
            if data is None:
                return data
            try:
                if not isinstance(data, dict):
                    raise TypeError()
                componentsschemas_ci_report_baseline_error_type_0 = (
                    CIReportBaselineErrorType0.from_dict(data)
                )

                return componentsschemas_ci_report_baseline_error_type_0
            except (TypeError, ValueError, AttributeError, KeyError):
                pass
            return cast(CIReportBaselineErrorType0 | None, data)

        baseline_error = _parse_baseline_error(d.pop("baseline_error"))

        def _parse_baseline_run_id(data: object) -> None | str:
            if data is None:
                return data
            return cast(None | str, data)

        baseline_run_id = _parse_baseline_run_id(d.pop("baseline_run_id"))

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

        def _parse_commits_skipped(data: object) -> list[str] | None:
            if data is None:
                return data
            try:
                if not isinstance(data, list):
                    raise TypeError()
                commits_skipped_type_0 = cast(list[str], data)

                return commits_skipped_type_0
            except (TypeError, ValueError, AttributeError, KeyError):
                pass
            return cast(list[str] | None, data)

        commits_skipped = _parse_commits_skipped(d.pop("commits_skipped"))

        def _parse_comparisons(data: object) -> list[CIReportComparison] | None:
            if data is None:
                return data
            try:
                if not isinstance(data, list):
                    raise TypeError()
                comparisons_type_0 = []
                _comparisons_type_0 = data
                for comparisons_type_0_item_data in _comparisons_type_0:
                    comparisons_type_0_item = CIReportComparison.from_dict(
                        comparisons_type_0_item_data
                    )

                    comparisons_type_0.append(comparisons_type_0_item)

                return comparisons_type_0
            except (TypeError, ValueError, AttributeError, KeyError):
                pass
            return cast(list[CIReportComparison] | None, data)

        comparisons = _parse_comparisons(d.pop("comparisons"))

        run_id = d.pop("run_id")

        def _parse_run_reason(data: object) -> None | str:
            if data is None:
                return data
            return cast(None | str, data)

        run_reason = _parse_run_reason(d.pop("run_reason"))

        run_tags = CIReportRunRunTags.from_dict(d.pop("run_tags"))

        ci_report_run = cls(
            baseline_commit=baseline_commit,
            baseline_error=baseline_error,
            baseline_run_id=baseline_run_id,
            commit=commit,
            commits_skipped=commits_skipped,
            comparisons=comparisons,
            run_id=run_id,
            run_reason=run_reason,
            run_tags=run_tags,
        )

        return ci_report_run
