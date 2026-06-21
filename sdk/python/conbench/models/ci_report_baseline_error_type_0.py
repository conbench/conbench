from __future__ import annotations

from collections.abc import Mapping
from typing import Any, TypeVar, cast

from attrs import define as _attrs_define

from ..types import UNSET, Unset

T = TypeVar("T", bound="CIReportBaselineErrorType0")


@_attrs_define
class CIReportBaselineErrorType0:
    """
    Attributes:
        baseline (str):
        code (str):
        commit_sha (None | str):
        message (str):
        run_id (str):
        searched_ancestor_limit (int | Unset):
        searched_commit_shas (list[str] | None | Unset):
    """

    baseline: str
    code: str
    commit_sha: None | str
    message: str
    run_id: str
    searched_ancestor_limit: int | Unset = UNSET
    searched_commit_shas: list[str] | None | Unset = UNSET

    def to_dict(self) -> dict[str, Any]:
        baseline = self.baseline

        code = self.code

        commit_sha: None | str
        commit_sha = self.commit_sha

        message = self.message

        run_id = self.run_id

        searched_ancestor_limit = self.searched_ancestor_limit

        searched_commit_shas: list[str] | None | Unset
        if isinstance(self.searched_commit_shas, Unset):
            searched_commit_shas = UNSET
        elif isinstance(self.searched_commit_shas, list):
            searched_commit_shas = self.searched_commit_shas

        else:
            searched_commit_shas = self.searched_commit_shas

        field_dict: dict[str, Any] = {}

        field_dict.update(
            {
                "baseline": baseline,
                "code": code,
                "commit_sha": commit_sha,
                "message": message,
                "run_id": run_id,
            }
        )
        if searched_ancestor_limit is not UNSET:
            field_dict["searched_ancestor_limit"] = searched_ancestor_limit
        if searched_commit_shas is not UNSET:
            field_dict["searched_commit_shas"] = searched_commit_shas

        return field_dict

    @classmethod
    def from_dict(cls: type[T], src_dict: Mapping[str, Any]) -> T:
        d = dict(src_dict)
        baseline = d.pop("baseline")

        code = d.pop("code")

        def _parse_commit_sha(data: object) -> None | str:
            if data is None:
                return data
            return cast(None | str, data)

        commit_sha = _parse_commit_sha(d.pop("commit_sha"))

        message = d.pop("message")

        run_id = d.pop("run_id")

        searched_ancestor_limit = d.pop("searched_ancestor_limit", UNSET)

        def _parse_searched_commit_shas(data: object) -> list[str] | None | Unset:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            try:
                if not isinstance(data, list):
                    raise TypeError()
                searched_commit_shas_type_0 = cast(list[str], data)

                return searched_commit_shas_type_0
            except (TypeError, ValueError, AttributeError, KeyError):
                pass
            return cast(list[str] | None | Unset, data)

        searched_commit_shas = _parse_searched_commit_shas(
            d.pop("searched_commit_shas", UNSET)
        )

        ci_report_baseline_error_type_0 = cls(
            baseline=baseline,
            code=code,
            commit_sha=commit_sha,
            message=message,
            run_id=run_id,
            searched_ancestor_limit=searched_ancestor_limit,
            searched_commit_shas=searched_commit_shas,
        )

        return ci_report_baseline_error_type_0
