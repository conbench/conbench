import abc
import hashlib
import json

import flask as f
import marshmallow
import sqlalchemy as s
from sqlalchemy import CheckConstraint as check
from sqlalchemy.dialects import postgresql
from sqlalchemy.orm import Mapped

from ..entities._entity import (
    Base,
    EntityMixin,
    EntitySerializer,
    NotNull,
    Nullable,
    genprimkey,
)


class Hardware(Base, EntityMixin):
    __tablename__ = "hardware"
    id: Mapped[str] = NotNull(s.String(50), primary_key=True, default=genprimkey)
    name: Mapped[str] = NotNull(s.Text)
    type: Mapped[str] = NotNull(s.String(50))

    # Note(JP): hash seems to be what we want to use for checking if two
    # results are hardware-comparable.
    hash: Mapped[str] = NotNull(s.String(1000))

    __mapper_args__ = {"polymorphic_on": type, "polymorphic_identity": "hardware"}

    @abc.abstractmethod
    def generate_hash(self):
        pass

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.hash = self.generate_hash()


class Machine(Hardware):
    architecture_name = Nullable(s.Text)
    kernel_name = Nullable(s.Text)
    os_name = Nullable(s.Text)
    os_version = Nullable(s.Text)
    cpu_model_name = Nullable(s.Text)
    cpu_l1d_cache_bytes = Nullable(s.Integer, check("cpu_l1d_cache_bytes>=0"))
    cpu_l1i_cache_bytes = Nullable(s.Integer, check("cpu_l1i_cache_bytes>=0"))
    cpu_l2_cache_bytes = Nullable(s.Integer, check("cpu_l2_cache_bytes>=0"))
    cpu_l3_cache_bytes = Nullable(s.Integer, check("cpu_l3_cache_bytes>=0"))
    cpu_core_count = Nullable(s.Integer, check("cpu_core_count>=0"))
    cpu_thread_count = Nullable(s.Integer, check("cpu_thread_count>=0"))
    cpu_frequency_max_hz = Nullable(s.BigInteger, check("cpu_frequency_max_hz>=0"))
    memory_bytes = Nullable(s.BigInteger, check("memory_bytes>=0"))
    gpu_count = Nullable(s.Integer, check("gpu_count>=0"), default=0)
    gpu_product_names = Nullable(postgresql.ARRAY(s.Text), default=[])

    # Note(JP): I think this complexity should go away.
    # also see https://github.com/conbench/conbench/issues/1281
    __mapper_args__ = {"polymorphic_identity": "machine"}

    def generate_hash(self):
        # Note(JP): this should simply be the digest of a popular hash
        # function. With the custom scheme below it's difficult to use this
        # hash programmatically as it has unpredictable length, charset, etc
        # (user-given data is in it).
        return (
            self.name
            + "-"
            + str(self.gpu_count)
            + "-"
            + str(self.cpu_core_count)
            + "-"
            + str(self.cpu_thread_count)
            + "-"
            + str(self.memory_bytes)
        )

    def serialize(self):
        return {
            "id": self.id,
            "name": self.name,
            "type": self.type,
            "architecture_name": self.architecture_name,
            "kernel_name": self.kernel_name,
            "os_name": self.os_name,
            "os_version": self.os_version,
            "cpu_model_name": self.cpu_model_name,
            "cpu_l1d_cache_bytes": self.cpu_l1d_cache_bytes,
            "cpu_l1i_cache_bytes": self.cpu_l1i_cache_bytes,
            "cpu_l2_cache_bytes": self.cpu_l2_cache_bytes,
            "cpu_l3_cache_bytes": self.cpu_l3_cache_bytes,
            "cpu_core_count": self.cpu_core_count,
            "cpu_thread_count": self.cpu_thread_count,
            "cpu_frequency_max_hz": self.cpu_frequency_max_hz,
            "memory_bytes": self.memory_bytes,
            "gpu_count": self.gpu_count,
            "gpu_product_names": self.gpu_product_names,
            # Note(JP): adding this to the public-facing API is not what I
            # aimed for here, but I'd like to display that checksum in the
            # result-result compare view in the UI and that is currently fed
            # from the API (API layer indirection: see
            # https://github.com/conbench/conbench/issues/1394).
            # "checksum": self.hash,
            "links": {
                "list": f.url_for("api.hardwares", _external=True),
                "self": f.url_for("api.hardware", hardware_id=self.id, _external=True),
            },
        }


class Cluster(Hardware):
    info = Nullable(postgresql.JSONB)
    optional_info = Nullable(postgresql.JSONB)

    __mapper_args__ = {"polymorphic_identity": "cluster"}

    def generate_hash(self):
        # Note(JP): this should simply be the digest of a popular hash
        # function. With the custom scheme below it's difficult to use this
        # hash programmatically as it has unpredictable length, charset, etc
        # (user-given data is in it).
        return (
            self.name
            + "-"
            + hashlib.md5(
                json.dumps(self.info, sort_keys=True).encode("utf-8")
            ).hexdigest()
        )

    def serialize(self):
        return {
            "id": self.id,
            "name": self.name,
            "type": self.type,
            "info": self.info,
            "optional_info": self.optional_info,
            # See above; https://github.com/conbench/conbench/issues/1394
            # "checksum": self.hash,
        }


s.Index(
    "hardware_index",
    Machine.name,
    Machine.architecture_name,
    Machine.kernel_name,
    Machine.os_name,
    Machine.os_version,
    Machine.cpu_model_name,
    Machine.cpu_l1d_cache_bytes,
    Machine.cpu_l1i_cache_bytes,
    Machine.cpu_l2_cache_bytes,
    Machine.cpu_l3_cache_bytes,
    Machine.cpu_core_count,
    Machine.cpu_thread_count,
    Machine.cpu_frequency_max_hz,
    Machine.memory_bytes,
    Machine.gpu_count,
    Machine.gpu_product_names,
    unique=True,
)


class _Serializer(EntitySerializer):
    def _dump(self, hardware):
        return hardware.serialize()


class HardwareSerializer:
    one = _Serializer()
    many = _Serializer(many=True)


class MachineCreate(marshmallow.Schema):
    name = marshmallow.fields.String(required=True)
    architecture_name = marshmallow.fields.String(required=True)
    kernel_name = marshmallow.fields.String(required=True)
    os_name = marshmallow.fields.String(required=True)
    os_version = marshmallow.fields.String(required=True)
    cpu_model_name = marshmallow.fields.String(required=True)
    cpu_l1d_cache_bytes = marshmallow.fields.Integer(required=True)
    cpu_l1i_cache_bytes = marshmallow.fields.Integer(required=True)
    cpu_l2_cache_bytes = marshmallow.fields.Integer(required=True)
    cpu_l3_cache_bytes = marshmallow.fields.Integer(required=True)
    cpu_core_count = marshmallow.fields.Integer(required=True)
    cpu_thread_count = marshmallow.fields.Integer(required=True)
    cpu_frequency_max_hz = marshmallow.fields.Integer(required=True)
    memory_bytes = marshmallow.fields.Integer(required=True)
    gpu_count = marshmallow.fields.Integer(required=True)
    gpu_product_names = marshmallow.fields.List(
        marshmallow.fields.String, required=True
    )


class ClusterCreate(marshmallow.Schema):
    name = marshmallow.fields.String(
        required=True,
        metadata={
            "description": "Distinct name of the cluster, to be displayed on the web UI."
        },
    )
    info = marshmallow.fields.Dict(
        required=True,
        metadata={
            "description": "Information related to cluster (e.g. `hosts`, `nodes` or `number of workers`) "
            "configured to run a set of benchmarks. Used to differentiate between similar "
            "benchmark runs performed on different sets of hardware"
        },
    )
    # Note(JP): `optional` in the name conflicts with `required=True`.
    # This is confusing for API users.
    optional_info = marshmallow.fields.Dict(
        required=True,
        metadata={
            "description": "Additional optional information about the cluster, which is not likely to impact the "
            "benchmark performance (e.g. region, settings like logging type, etc). "
            "Despite the name, this field is required. An empty dictionary can be passed."
        },
    )


class MachineSchema:
    create = MachineCreate()


class ClusterSchema:
    create = ClusterCreate()
