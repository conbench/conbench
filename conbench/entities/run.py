import flask as f
import sqlalchemy as s
from sqlalchemy.orm import relationship

from ..entities._entity import Base, EntityMixin, EntitySerializer, NotNull, Nullable
from ..entities.commit import Commit, CommitSerializer
from ..entities.machine import MachineSerializer


class Run(Base, EntityMixin):
    __tablename__ = "run"
    id = NotNull(s.String(50), primary_key=True)
    name = Nullable(s.String(250))
    timestamp = NotNull(s.DateTime(timezone=False), server_default=s.sql.func.now())
    commit_id = NotNull(s.String(50), s.ForeignKey("commit.id"))
    commit = relationship("Commit", lazy="joined")
    machine_id = NotNull(s.String(50), s.ForeignKey("machine.id"))
    machine = relationship("Machine", lazy="joined")

    def get_baseline_id(self):
        parent = self.commit.parent
        runs = Run.search(
            filters=[Run.machine_id == self.machine_id, Commit.sha == parent],
            joins=[Commit],
        )
        if runs:
            return runs[0].id
        return None


class _Serializer(EntitySerializer):
    def _dump(self, run):
        commit = CommitSerializer().one.dump(run.commit)
        machine = MachineSerializer().one.dump(run.machine)
        commit.pop("links", None)
        machine.pop("links", None)
        result = {
            "id": run.id,
            "name": run.name,
            "timestamp": run.timestamp.isoformat(),
            "commit": commit,
            "machine": machine,
            "links": {
                "self": f.url_for("api.run", run_id=run.id, _external=True),
            },
        }
        if not self.many:
            baseline_id, baseline_url = run.get_baseline_id(), None
            if baseline_id:
                baseline_url = f.url_for("api.run", run_id=baseline_id, _external=True)
            result["links"]["baseline"] = baseline_url
        return result


class RunSerializer:
    one = _Serializer()
    many = _Serializer(many=True)
