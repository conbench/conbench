from ..db import Session
from ..entities._entity import EntitySerializer
from ..entities.benchmark_result import BenchmarkResult
from ..entities.commit import Commit
from ..entities.distribution import Distribution
from ..entities.hardware import Hardware
from ..entities.run import Run


class _Serializer(EntitySerializer):
    def _dump(self, history):
        standard_deviation = history.mean_sd if history.mean_sd else 0
        return {
            "benchmark_id": history.id,
            "case_id": history.case_id,
            "context_id": history.context_id,
            "mean": float(history.mean),
            "unit": history.unit,
            "hardware_hash": history.hash,
            "sha": history.sha,
            "repository": history.repository,
            "message": history.message,
            "timestamp": history.timestamp.isoformat(),
            "run_name": history.name,
            "distribution_mean": float(history.mean_mean),
            "distribution_stdev": float(standard_deviation),
        }


class HistorySerializer:
    one = _Serializer()
    many = _Serializer(many=True)


def get_history(case_id, context_id, hardware_hash):
    return (
        Session.query(
            BenchmarkResult.id,
            BenchmarkResult.case_id,
            BenchmarkResult.context_id,
            BenchmarkResult.mean,
            BenchmarkResult.unit,
            Hardware.hash,
            Commit.sha,
            Commit.repository,
            Commit.message,
            Commit.timestamp,
            Distribution.mean_mean,
            Distribution.mean_sd,
            Run.name,
        )
        .join(Run, Run.id == BenchmarkResult.run_id)
        .join(Hardware, Hardware.id == Run.hardware_id)
        .join(Commit, Commit.id == Run.commit_id)
        .join(Distribution, Distribution.commit_id == Commit.id)
        .filter(
            BenchmarkResult.case_id == case_id,
            BenchmarkResult.context_id == context_id,
            BenchmarkResult.error.is_(None),
            Run.name.like("commit: %"),
            Hardware.hash == hardware_hash,
            Distribution.case_id == case_id,
            Distribution.context_id == context_id,
            Distribution.hardware_hash == hardware_hash,
        )
        .order_by(Commit.timestamp.asc())
        .all()
    )
