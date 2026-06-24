from __future__ import annotations

from collections.abc import Mapping
from typing import TYPE_CHECKING, Any, TypeVar

from attrs import define as _attrs_define

from ..types import UNSET, Unset

if TYPE_CHECKING:
    from ..models.cluster_info_info import ClusterInfoInfo
    from ..models.cluster_info_optional_info import ClusterInfoOptionalInfo


T = TypeVar("T", bound="ClusterInfo")


@_attrs_define
class ClusterInfo:
    """
    Attributes:
        info (ClusterInfoInfo):
        name (str):
        optional_info (ClusterInfoOptionalInfo | Unset):
    """

    info: ClusterInfoInfo
    name: str
    optional_info: ClusterInfoOptionalInfo | Unset = UNSET

    def to_dict(self) -> dict[str, Any]:
        info = self.info.to_dict()

        name = self.name

        optional_info: dict[str, Any] | Unset = UNSET
        if not isinstance(self.optional_info, Unset):
            optional_info = self.optional_info.to_dict()

        field_dict: dict[str, Any] = {}

        field_dict.update(
            {
                "info": info,
                "name": name,
            }
        )
        if optional_info is not UNSET:
            field_dict["optional_info"] = optional_info

        return field_dict

    @classmethod
    def from_dict(cls: type[T], src_dict: Mapping[str, Any]) -> T:
        from ..models.cluster_info_info import ClusterInfoInfo
        from ..models.cluster_info_optional_info import ClusterInfoOptionalInfo

        d = dict(src_dict)
        info = ClusterInfoInfo.from_dict(d.pop("info"))

        name = d.pop("name")

        _optional_info = d.pop("optional_info", UNSET)
        optional_info: ClusterInfoOptionalInfo | Unset
        if isinstance(_optional_info, Unset):
            optional_info = UNSET
        else:
            optional_info = ClusterInfoOptionalInfo.from_dict(_optional_info)

        cluster_info = cls(
            info=info,
            name=name,
            optional_info=optional_info,
        )

        return cluster_info
