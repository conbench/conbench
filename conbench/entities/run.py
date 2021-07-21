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
        from ..entities.summary import Summary

        parent = self.commit.parent
        runs = Run.search(
            filters=[Run.machine_id == self.machine_id, Commit.sha == parent],
            joins=[Commit],
        )
        run_contexts = Summary.distinct(
            Summary.context_id, filters=[Summary.run_id == self.id]
        )

        # TODO: What if there are multiple matches? Pick by date?
        # TODO: Should be using machine hash?
        for run in runs:
            baseline_contexts = Summary.distinct(
                Summary.context_id, filters=[Summary.run_id == run.id]
            )
            if set(run_contexts) == set(baseline_contexts):
                return run.id

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
                "list": f.url_for("api.runs", _external=True),
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
