from ..db import Session
from ..entities._entity import EntitySerializer
from ..entities.commit import Commit
from ..entities.machine import Machine
from ..entities.run import Run
from ..entities.summary import Summary


class _Serializer(EntitySerializer):
    decimal_fmt = "{:.6f}"

    def _dump(self, history):
        return {
            "benchmark_id": history.id,
            "case_id": history.case_id,
            "context_id": history.context_id,
            "mean": self.decimal_fmt.format(history.mean),
            "unit": history.unit,
            "machine_hash": history.hash,
            "sha": history.sha,
            "repository": history.repository,
            "message": history.message,
            "timestamp": history.timestamp.isoformat(),
            "run_name": history.name,
        }


class HistorySerializer:
    one = _Serializer()
    many = _Serializer(many=True)


def get_history(case_id, context_id, machine_hash):
    return (
        Session.query(
            Summary.id,
            Summary.case_id,
            Summary.context_id,
            Summary.mean,
            Summary.unit,
            Machine.hash,
            Commit.sha,
            Commit.repository,
            Commit.message,
            Commit.timestamp,
            Run.name,
        )
        .join(Run, Run.id == Summary.run_id)
        .join(Machine, Machine.id == Run.machine_id)
        .join(Commit, Commit.id == Run.commit_id)
        .filter(
            Summary.case_id == case_id,
            Summary.context_id == context_id,
            Machine.hash == machine_hash,
        )
        .order_by(Commit.timestamp.asc())
        .all()
    )
