import flask as f
import sqlalchemy as s
from sqlalchemy.orm import relationship

from ..db import Session
from ..entities._entity import Base, EntityMixin, EntitySerializer, NotNull, Nullable
from ..entities.commit import Commit, CommitSerializer
from ..entities.machine import Machine, MachineSerializer


class Run(Base, EntityMixin):
    __tablename__ = "run"
    id = NotNull(s.String(50), primary_key=True)
    name = Nullable(s.String(250))
    timestamp = NotNull(s.DateTime(timezone=False), server_default=s.sql.func.now())
    commit_id = NotNull(s.String(50), s.ForeignKey("commit.id"))
    commit = relationship("Commit", lazy="joined")
    machine_id = NotNull(s.String(50), s.ForeignKey("machine.id"))
    machine = relationship("Machine", lazy="joined")

    def get_baseline_run(self):
        from ..entities.distribution import get_closest_parent
        from ..entities.summary import Summary

        result = (
            Session.query(
                Summary.case_id,
                Summary.context_id,
            )
            .filter(Summary.run_id == self.id)
            .all()
        )
        run_items = [(row[0], row[1]) for row in result]
        machines = Machine.all(hash=self.machine.hash)
        machine_ids = set([m.id for m in machines])

        parent = get_closest_parent(self)
        if not parent:
            return None

        # possible parent runs
        parent_runs = Run.search(
            filters=[
                Commit.sha == parent.sha,
                Machine.id.in_(machine_ids),
                Run.name.like("commit: %"),
            ],
            joins=[Commit, Machine],
            order_by=Run.timestamp.desc(),
        )

        # get run items for all possible parent runs
        parent_run_items = {run.id: [] for run in parent_runs}
        result = (
            Session.query(
                Summary.run_id,
                Summary.case_id,
                Summary.context_id,
            )
            .filter(Summary.run_id.in_(parent_run_items.keys()))
            .all()
        )
        for row in result:
            parent_run_items[row[0]].append((row[1], row[2]))

        # return run with matching contexts & cases
        # TODO:
        #   - what if all the contexts/cases just aren't yet in?
        #   - what if one of N benchmark cases failed?
        for parent_run in parent_runs:
            if set(run_items) == set(parent_run_items[parent_run.id]):
                return parent_run

        return None

    def get_baseline_id(self):
        run = self.get_baseline_run()
        return run.id if run else None


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
                "commit": f.url_for(
                    "api.commit", commit_id=commit["id"], _external=True
                ),
                "machine": f.url_for(
                    "api.machine", machine_id=machine["id"], _external=True
                ),
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
