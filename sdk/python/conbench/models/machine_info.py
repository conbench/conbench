from __future__ import annotations

from collections.abc import Mapping
from typing import Any, TypeVar, cast

from attrs import define as _attrs_define

from ..types import UNSET, Unset

T = TypeVar("T", bound="MachineInfo")


@_attrs_define
class MachineInfo:
    """
    Attributes:
        name (str):
        architecture_name (str | Unset):
        cpu_core_count (int | Unset):
        cpu_frequency_max_hz (int | Unset):
        cpu_l1d_cache_bytes (int | Unset):
        cpu_l1i_cache_bytes (int | Unset):
        cpu_l2_cache_bytes (int | Unset):
        cpu_l3_cache_bytes (int | Unset):
        cpu_model_name (str | Unset):
        cpu_thread_count (int | Unset):
        gpu_count (int | Unset):
        gpu_product_names (list[str] | None | Unset):
        kernel_name (str | Unset):
        memory_bytes (int | Unset):
        os_name (str | Unset):
        os_version (str | Unset):
    """

    name: str
    architecture_name: str | Unset = UNSET
    cpu_core_count: int | Unset = UNSET
    cpu_frequency_max_hz: int | Unset = UNSET
    cpu_l1d_cache_bytes: int | Unset = UNSET
    cpu_l1i_cache_bytes: int | Unset = UNSET
    cpu_l2_cache_bytes: int | Unset = UNSET
    cpu_l3_cache_bytes: int | Unset = UNSET
    cpu_model_name: str | Unset = UNSET
    cpu_thread_count: int | Unset = UNSET
    gpu_count: int | Unset = UNSET
    gpu_product_names: list[str] | None | Unset = UNSET
    kernel_name: str | Unset = UNSET
    memory_bytes: int | Unset = UNSET
    os_name: str | Unset = UNSET
    os_version: str | Unset = UNSET

    def to_dict(self) -> dict[str, Any]:
        name = self.name

        architecture_name = self.architecture_name

        cpu_core_count = self.cpu_core_count

        cpu_frequency_max_hz = self.cpu_frequency_max_hz

        cpu_l1d_cache_bytes = self.cpu_l1d_cache_bytes

        cpu_l1i_cache_bytes = self.cpu_l1i_cache_bytes

        cpu_l2_cache_bytes = self.cpu_l2_cache_bytes

        cpu_l3_cache_bytes = self.cpu_l3_cache_bytes

        cpu_model_name = self.cpu_model_name

        cpu_thread_count = self.cpu_thread_count

        gpu_count = self.gpu_count

        gpu_product_names: list[str] | None | Unset
        if isinstance(self.gpu_product_names, Unset):
            gpu_product_names = UNSET
        elif isinstance(self.gpu_product_names, list):
            gpu_product_names = self.gpu_product_names

        else:
            gpu_product_names = self.gpu_product_names

        kernel_name = self.kernel_name

        memory_bytes = self.memory_bytes

        os_name = self.os_name

        os_version = self.os_version

        field_dict: dict[str, Any] = {}

        field_dict.update(
            {
                "name": name,
            }
        )
        if architecture_name is not UNSET:
            field_dict["architecture_name"] = architecture_name
        if cpu_core_count is not UNSET:
            field_dict["cpu_core_count"] = cpu_core_count
        if cpu_frequency_max_hz is not UNSET:
            field_dict["cpu_frequency_max_hz"] = cpu_frequency_max_hz
        if cpu_l1d_cache_bytes is not UNSET:
            field_dict["cpu_l1d_cache_bytes"] = cpu_l1d_cache_bytes
        if cpu_l1i_cache_bytes is not UNSET:
            field_dict["cpu_l1i_cache_bytes"] = cpu_l1i_cache_bytes
        if cpu_l2_cache_bytes is not UNSET:
            field_dict["cpu_l2_cache_bytes"] = cpu_l2_cache_bytes
        if cpu_l3_cache_bytes is not UNSET:
            field_dict["cpu_l3_cache_bytes"] = cpu_l3_cache_bytes
        if cpu_model_name is not UNSET:
            field_dict["cpu_model_name"] = cpu_model_name
        if cpu_thread_count is not UNSET:
            field_dict["cpu_thread_count"] = cpu_thread_count
        if gpu_count is not UNSET:
            field_dict["gpu_count"] = gpu_count
        if gpu_product_names is not UNSET:
            field_dict["gpu_product_names"] = gpu_product_names
        if kernel_name is not UNSET:
            field_dict["kernel_name"] = kernel_name
        if memory_bytes is not UNSET:
            field_dict["memory_bytes"] = memory_bytes
        if os_name is not UNSET:
            field_dict["os_name"] = os_name
        if os_version is not UNSET:
            field_dict["os_version"] = os_version

        return field_dict

    @classmethod
    def from_dict(cls: type[T], src_dict: Mapping[str, Any]) -> T:
        d = dict(src_dict)
        name = d.pop("name")

        architecture_name = d.pop("architecture_name", UNSET)

        cpu_core_count = d.pop("cpu_core_count", UNSET)

        cpu_frequency_max_hz = d.pop("cpu_frequency_max_hz", UNSET)

        cpu_l1d_cache_bytes = d.pop("cpu_l1d_cache_bytes", UNSET)

        cpu_l1i_cache_bytes = d.pop("cpu_l1i_cache_bytes", UNSET)

        cpu_l2_cache_bytes = d.pop("cpu_l2_cache_bytes", UNSET)

        cpu_l3_cache_bytes = d.pop("cpu_l3_cache_bytes", UNSET)

        cpu_model_name = d.pop("cpu_model_name", UNSET)

        cpu_thread_count = d.pop("cpu_thread_count", UNSET)

        gpu_count = d.pop("gpu_count", UNSET)

        def _parse_gpu_product_names(data: object) -> list[str] | None | Unset:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            try:
                if not isinstance(data, list):
                    raise TypeError()
                gpu_product_names_type_0 = cast(list[str], data)

                return gpu_product_names_type_0
            except (TypeError, ValueError, AttributeError, KeyError):
                pass
            return cast(list[str] | None | Unset, data)

        gpu_product_names = _parse_gpu_product_names(d.pop("gpu_product_names", UNSET))

        kernel_name = d.pop("kernel_name", UNSET)

        memory_bytes = d.pop("memory_bytes", UNSET)

        os_name = d.pop("os_name", UNSET)

        os_version = d.pop("os_version", UNSET)

        machine_info = cls(
            name=name,
            architecture_name=architecture_name,
            cpu_core_count=cpu_core_count,
            cpu_frequency_max_hz=cpu_frequency_max_hz,
            cpu_l1d_cache_bytes=cpu_l1d_cache_bytes,
            cpu_l1i_cache_bytes=cpu_l1i_cache_bytes,
            cpu_l2_cache_bytes=cpu_l2_cache_bytes,
            cpu_l3_cache_bytes=cpu_l3_cache_bytes,
            cpu_model_name=cpu_model_name,
            cpu_thread_count=cpu_thread_count,
            gpu_count=gpu_count,
            gpu_product_names=gpu_product_names,
            kernel_name=kernel_name,
            memory_bytes=memory_bytes,
            os_name=os_name,
            os_version=os_version,
        )

        return machine_info
