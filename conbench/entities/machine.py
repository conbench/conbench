import flask as f
import marshmallow
import sqlalchemy as s
from sqlalchemy import CheckConstraint as check
from sqlalchemy import func
from sqlalchemy.dialects import postgresql
from sqlalchemy.ext.hybrid import hybrid_property

from ..entities._entity import (
    Base,
    EntityMixin,
    EntitySerializer,
    NotNull,
    generate_uuid,
)


class Machine(Base, EntityMixin):
    __tablename__ = "machine"
    id = NotNull(s.String(50), primary_key=True, default=generate_uuid)
    name = NotNull(s.Text)
    architecture_name = NotNull(s.Text)
    kernel_name = NotNull(s.Text)
    os_name = NotNull(s.Text)
    os_version = NotNull(s.Text)
    cpu_model_name = NotNull(s.Text)
    cpu_l1d_cache_bytes = NotNull(s.Integer, check("cpu_l1d_cache_bytes>=0"))
    cpu_l1i_cache_bytes = NotNull(s.Integer, check("cpu_l1i_cache_bytes>=0"))
    cpu_l2_cache_bytes = NotNull(s.Integer, check("cpu_l2_cache_bytes>=0"))
    cpu_l3_cache_bytes = NotNull(s.Integer, check("cpu_l3_cache_bytes>=0"))
    cpu_core_count = NotNull(s.Integer, check("cpu_core_count>=0"))
    cpu_thread_count = NotNull(s.Integer, check("cpu_thread_count>=0"))
    cpu_frequency_max_hz = NotNull(s.BigInteger, check("cpu_frequency_max_hz>=0"))
    memory_bytes = NotNull(s.BigInteger, check("memory_bytes>=0"))
    gpu_count = NotNull(s.Integer, check("gpu_count>=0"), default=0)
    gpu_product_names = NotNull(postgresql.ARRAY(s.Text), default=[])

    # TODO: Does GPU count belong in the hash?

    @hybrid_property
    def hash(self):
        return (
            self.name
            + "-"
            + str(self.cpu_core_count)
            + "-"
            + str(self.cpu_thread_count)
            + "-"
            + str(self.memory_bytes)
        )

    @hash.expression
    def hash(cls):
        return func.concat(
            cls.name,
            "-",
            cls.cpu_core_count,
            "-",
            cls.cpu_thread_count,
            "-",
            cls.memory_bytes,
        ).label("hash")


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
    def _dump(self, machine):
        return {
            "id": machine.id,
            "name": machine.name,
            "architecture_name": machine.architecture_name,
            "kernel_name": machine.kernel_name,
            "os_name": machine.os_name,
            "os_version": machine.os_version,
            "cpu_model_name": machine.cpu_model_name,
            "cpu_l1d_cache_bytes": machine.cpu_l1d_cache_bytes,
            "cpu_l1i_cache_bytes": machine.cpu_l1i_cache_bytes,
            "cpu_l2_cache_bytes": machine.cpu_l2_cache_bytes,
            "cpu_l3_cache_bytes": machine.cpu_l3_cache_bytes,
            "cpu_core_count": machine.cpu_core_count,
            "cpu_thread_count": machine.cpu_thread_count,
            "cpu_frequency_max_hz": machine.cpu_frequency_max_hz,
            "memory_bytes": machine.memory_bytes,
            "gpu_count": machine.gpu_count,
            "gpu_product_names": machine.gpu_product_names,
            "links": {
                "list": f.url_for("api.machines", _external=True),
                "self": f.url_for("api.machine", machine_id=machine.id, _external=True),
            },
        }


class MachineSerializer:
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


class MachineSchema:
    create = MachineCreate()
