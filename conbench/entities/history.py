from typing import List

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

        # Note(JP): expose `times` or `data` or flatten them or expose both?
        # Unclear. `times` is specified as "A list of benchmark durations. If
        # data is a duration measure, this should be a duplicate of that
        # object." `data` is specified with "A list of benchmark results (e.g.
        # durations, throughput). This will be used as the main + only metric
        # for regression and improvement. The values should be ordered in the
        # order the iterations were executed (the first element is the first
        # iteration, the second element is the second iteration, etc.). If an
        # iteration did not complete but others did and you want to send
        # partial data, mark each iteration that didn't complete as null."
        # Expose both for now.
        #
        # In practice, I have only seen `data` being used so far and even when
        # `data` was representing durations then this vector was not duplicated
        # as `times`.

        # For both, history.data and history.times expect either None or a list
        # Make it so that in the output object they are always a list,
        # potentially empty. `data` contains more than one value if this was
        # a multi-sample benchmark.
        data = []
        if history.data is not None:
            data = [float(d) if d is not None else None for d in history.data]

        times = []
        if history.times is not None:
            times = [float(t) if t is not None else None for t in history.times]

        return {
            "benchmark_id": history.id,
            "case_id": history.case_id,
            "context_id": history.context_id,
            "mean": float(history.mean),
            "data": data,
            "times": times,
            "unit": history.unit,
            "change_annotations": history.change_annotations or {},
            "hardware_hash": history.hash,
            "sha": history.sha,
            "repository": history.repository,
            # Note(JP): this is the commit message
            "message": history.message,
            "timestamp": history.timestamp.isoformat(),
            "run_name": history.name,
            "distribution_mean": float(history.mean_mean),
            "distribution_stdev": float(standard_deviation),
        }


class HistorySerializer:
    one = _Serializer()
    many = _Serializer(many=True)


def get_history(case_id, context_id, hardware_hash, repo) -> List[tuple]:
    """Given a case/context/hardware/repo, return all non-errored BenchmarkResults
    (past, present, and future) on the default branch that match those criteria, along
    with information about the stats of the distribution as of each BenchmarkResult.
    Order is not guaranteed.

    Primarily used to power the blue line in the timeseries plots.
    """
    return (
        Session.query(
            BenchmarkResult.id,
            BenchmarkResult.case_id,
            BenchmarkResult.context_id,
            BenchmarkResult.mean,
            BenchmarkResult.unit,
            BenchmarkResult.data,
            BenchmarkResult.times,
            BenchmarkResult.change_annotations,
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
            Commit.sha == Commit.fork_point_sha,  # on default branch
            Commit.repository == repo,
            Hardware.hash == hardware_hash,
            Distribution.case_id == case_id,
            Distribution.context_id == context_id,
            Distribution.hardware_hash == hardware_hash,
        )
        .order_by(Commit.timestamp.asc())
        .all()
    )
