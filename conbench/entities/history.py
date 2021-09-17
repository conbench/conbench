from ..db import Session
from ..entities._entity import EntitySerializer
from ..entities.commit import Commit
from ..entities.distribution import Distribution
from ..entities.machine import Machine
from ..entities.run import Run
from ..entities.summary import Summary


class _Serializer(EntitySerializer):
    decimal_fmt = "{:.6f}"

    def _dump(self, history):
        standard_deviation = history.mean_sd if history.mean_sd else 0
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
            "distribution_mean": self.decimal_fmt.format(history.mean_mean),
            "distribution_stdev": self.decimal_fmt.format(standard_deviation),
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
            Distribution.mean_mean,
            Distribution.mean_sd,
            Run.name,
        )
        .join(Run, Run.id == Summary.run_id)
        .join(Machine, Machine.id == Run.machine_id)
        .join(Commit, Commit.id == Run.commit_id)
        .join(Distribution, Distribution.commit_id == Commit.id)
        .filter(
            Summary.case_id == case_id,
            Summary.context_id == context_id,
            Run.name.like("commit: %"),
            Machine.hash == machine_hash,
            Distribution.case_id == case_id,
            Distribution.context_id == context_id,
            Distribution.machine_hash == machine_hash,
        )
        .order_by(Commit.timestamp.asc())
        .all()
    )
