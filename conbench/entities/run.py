import flask as f
import sqlalchemy as s
from sqlalchemy import distinct
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

    def _items_match(self, items, other):
        from ..entities.summary import Summary

        # TODO:
        #   - what if all the contexts/cases just aren't yet in?
        #   - what if one of N benchmark cases failed?
        other_summaries = Summary.all(run_id=other.id)
        other_items = [(s.context_id, s.case_id) for s in other_summaries]
        return set(items) == set(other_items)

    def get_baseline_run(self):
        from ..entities.distribution import get_closest_parent
        from ..entities.summary import Summary

        machines = Machine.all(hash=self.machine.hash)
        machine_ids = set([m.id for m in machines])

        run_summaries = Summary.all(run_id=self.id)
        run_contexts = set([s.context_id for s in run_summaries])
        run_items = [(s.context_id, s.case_id) for s in run_summaries]

        parent = get_closest_parent(self.commit)
        if not parent:
            return None

        # possible parent runs
        parent_runs = Run.search(
            joins=[Commit, Machine],
            filters=[
                Commit.sha == parent.sha,
                Machine.id.in_(machine_ids),
                Run.name.like("commit: %"),
            ],
            order_by=Run.timestamp.desc(),
        )

        # return run with matching contexts & cases
        for parent_run in parent_runs:
            if self._items_match(run_items, parent_run):
                return parent_run

        # no matches found, try walking backwards, 10 runs
        # TODO: there must be a better way
        rows = (
            Session.query(distinct(Summary.run_id), Commit.timestamp)
            .join(Run, Run.id == Summary.run_id)
            .join(Commit, Commit.id == Run.commit_id)
            .join(Machine, Machine.id == Run.machine_id)
            .filter(
                Run.name.like("commit: %"),
                Machine.id.in_(machine_ids),
                Summary.context_id.in_(run_contexts),
                Commit.timestamp < self.commit.timestamp,
            )
            .order_by(Commit.timestamp.desc(), Summary.run_id.desc())
            .limit(10)
            .all()
        )
        run_ids = set([row[0] for row in rows])

        # possible parent runs
        parent_runs = Run.search(
            filters=[Run.id.in_(run_ids)],
            joins=[Commit],
            order_by=Commit.timestamp.desc(),
        )

        # return run with matching contexts & cases
        for parent_run in parent_runs:
            if self._items_match(run_items, parent_run):
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
