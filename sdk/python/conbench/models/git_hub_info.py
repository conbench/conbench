from __future__ import annotations

from collections.abc import Mapping
from typing import Any, Self, TypeVar, cast

from attrs import define as _attrs_define

from ..types import UNSET, Unset

T = TypeVar("T", bound="GitHubInfo")


@_attrs_define
class GitHubInfo:
    """
    Attributes:
        repository (str):
        branch (None | str | Unset): Branch in org:branch form; only for non-default-branch runs outside PRs.
        commit (str | Unset):
        pr_number (int | None | Unset): Pull request number; used to resolve the branch via the GitHub API.
    """

    repository: str
    branch: None | str | Unset = UNSET
    commit: str | Unset = UNSET
    pr_number: int | None | Unset = UNSET

    def to_dict(self) -> dict[str, Any]:
        repository = self.repository

        branch: None | str | Unset
        if isinstance(self.branch, Unset):
            branch = UNSET
        else:
            branch = self.branch

        commit = self.commit

        pr_number: int | None | Unset
        if isinstance(self.pr_number, Unset):
            pr_number = UNSET
        else:
            pr_number = self.pr_number

        field_dict: dict[str, Any] = {}

        field_dict.update(
            {
                "repository": repository,
            }
        )
        if branch is not UNSET:
            field_dict["branch"] = branch
        if commit is not UNSET:
            field_dict["commit"] = commit
        if pr_number is not UNSET:
            field_dict["pr_number"] = pr_number

        return field_dict

    @classmethod
    def from_dict(cls, src_dict: Mapping[str, Any]) -> Self:
        d = dict(src_dict)
        repository = d.pop("repository")

        def _parse_branch(data: object) -> None | str | Unset:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            return cast(None | str | Unset, data)

        branch = _parse_branch(d.pop("branch", UNSET))

        commit = d.pop("commit", UNSET)

        def _parse_pr_number(data: object) -> int | None | Unset:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            return cast(int | None | Unset, data)

        pr_number = _parse_pr_number(d.pop("pr_number", UNSET))

        git_hub_info = cls(
            repository=repository,
            branch=branch,
            commit=commit,
            pr_number=pr_number,
        )

        return git_hub_info
