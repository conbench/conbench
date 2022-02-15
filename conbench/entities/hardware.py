import hashlib
import json

import flask as f
import marshmallow
import sqlalchemy as s
from sqlalchemy import CheckConstraint as check
from sqlalchemy.dialects import postgresql

from ..entities._entity import (
    Base,
    EntityMixin,
    EntitySerializer,
    NotNull,
    Nullable,
    generate_uuid,
)


class Hardware(Base, EntityMixin):
    __tablename__ = "machine"
    id = NotNull(s.String(50), primary_key=True, default=generate_uuid)
    name = NotNull(s.Text)
    type = NotNull(s.String(50))
    hash = NotNull(s.String(1000))

    __mapper_args__ = {"polymorphic_on": type, "polymorphic_identity": "hardware"}

    @classmethod
    def create(cls, data):
        hardware = cls(**data)
        hardware.hash = hardware.generate_hash()
        hardware.save()
        return hardware


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

    __mapper_args__ = {"polymorphic_identity": "machine"}

    @classmethod
    def upsert(cls, **kwargs):
        machine = cls.first(**kwargs)
        if not machine:
            machine = cls.create(kwargs)
        return machine

    def generate_hash(self):
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
            "links": {
                "list": f.url_for("api.hardwares", _external=True),
                "self": f.url_for("api.hardware", hardware_id=self.id, _external=True),
            },
        }


class Cluster(Hardware):
    info = Nullable(postgresql.JSONB)
    optional_info = Nullable(postgresql.JSONB)

    __mapper_args__ = {"polymorphic_identity": "cluster"}

    @classmethod
    def upsert(cls, **kwargs):
        cluster = cls.first(name=kwargs["name"], info=kwargs["info"])
        if cluster:
            cluster.update(dict(optional_info=kwargs["optional_info"]))
        else:
            cluster = cls.create(kwargs)
        return cluster

    def generate_hash(self):
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
        }


s.Index(
    "machine_index",
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
    name = marshmallow.fields.String(required=True)
    info = marshmallow.fields.Dict(required=True)
    optional_info = marshmallow.fields.Dict(required=True)


class MachineSchema:
    create = MachineCreate()


class ClusterSchema:
    create = ClusterCreate()
