import flask as f
import sqlalchemy as s
from sqlalchemy.orm import relationship

from ..entities._entity import Base, EntityMixin, EntitySerializer, NotNull


class Run(Base, EntityMixin):
    __tablename__ = "run"
    id = NotNull(s.String(50), primary_key=True)
    timestamp = NotNull(s.DateTime(timezone=False), server_default=s.sql.func.now())
    github_id = NotNull(s.String(50), s.ForeignKey("github.id"))
    github = relationship("GitHub", lazy="select")
    machine_id = NotNull(s.String(50), s.ForeignKey("machine.id"))
    machine = relationship("Machine", lazy="select")


class _Serializer(EntitySerializer):
    def _dump(self, run):
        result = {
            "id": run.id,
            "links": {
                "self": f.url_for("api.run", run_id=run.id, _external=True),
                "machine": f.url_for(
                    "api.machine", machine_id=run.machine_id, _external=True
                ),
            },
        }
        return result


class RunSerializer:
    one = _Serializer()
    many = _Serializer(many=True)
