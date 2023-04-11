import dataclasses
import logging
import signal
import threading
import time
from collections import defaultdict
from typing import Dict, List, TypedDict

from sqlalchemy import select

from conbench.config import Config
import conbench.metrics
from conbench.db import Session
from conbench.entities.benchmark_result import BenchmarkResult
from conbench.hacks import get_case_kvpair_strings

"""
This module implements a job which populates and provides a cache for the N
most recent benchmark results, the tail end. Benchmark result tail-end cache:
BMRT cache.

Central cache data structure are Python dictionaries (with thread-safe(atomic)
set/get operations).
"""

log = logging.getLogger(__name__)


@dataclasses.dataclass
class CacheUpdateMetaInfo:
    newest_result_time_str: str
    oldest_result_time_str: str
    n_results: int


class CacheDict(TypedDict):
    by_id: Dict[str, BenchmarkResult]
    by_benchmark_name: Dict[str, List[BenchmarkResult]]
    by_case_id: Dict[str, List[BenchmarkResult]]
    meta: CacheUpdateMetaInfo


# Think: do work in a child process, provide dictionary via shared memory to
# parent, maybe via https://pypi.org/project/shared-memory-dict/ this is _not_
# as stdlib pickling dict
# https://github.com/luizalabs/shared-memory-dict/issues/10
_cache_bmrs: CacheDict = {
    "by_id": {},
    "by_benchmark_name": {},
    "by_case_id": {},
    "meta": CacheUpdateMetaInfo(
        newest_result_time_str="n/a", oldest_result_time_str="n/a", n_results=0
    ),
}

_shutdown = False


# Fetching one million items from a sample DB takes ~1 minute on my machine
# (the `results = Session.scalars(....all())` call takes that long.
def _fetch_and_cache_most_recent_results(n=0.2 * 10**6) -> None:
    log.debug(
        "BMRT cache: keys in cache: %s",
        len(_cache_bmrs["by_id"]),
    )
    t0 = time.monotonic()

    results = Session.scalars(
        select(BenchmarkResult).order_by(BenchmarkResult.timestamp.desc()).limit(n)
    ).all()

    t1 = time.monotonic()

    if len(results) == 0:
        log.debug("BMRT cache: no results (testing mode?)")
        return

    by_id_dict: Dict[str, BenchmarkResult] = {}
    by_name_dict: Dict[str, List[BenchmarkResult]] = defaultdict(list)
    by_case_dict: Dict[str, List[BenchmarkResult]] = defaultdict(list)
    for result in results:
        by_id_dict[result.id] = result
        # point of confusion: `result.case.name` is the benchmark name
        by_name_dict[result.case.name].append(result)
        # Add a property on the Case object, on the fly.
        # Build the textual representation of this case which should also
        # uniquely / unambiguously define/identify this specific case.
        result.case.text_id = " ".join(get_case_kvpair_strings(result.case.tags))
        by_case_dict[result.case.id].append(result)

    # Mutate the dictionary which is accessed by other threads, do this in a
    # quick fashion -- each of this assignments is atomic (thread-safe), but
    # between those two assignments a thread might perform read access. (minor
    # inconsistency is possible). Of course we can add another lookup
    # indirection layer by assembling a completely new dictionary here and then
    # re-defining the name _cache_bmrs.
    _cache_bmrs["by_id"] = by_id_dict
    _cache_bmrs["by_benchmark_name"] = by_name_dict
    _cache_bmrs["by_case_id"] = by_case_dict
    _cache_bmrs["meta"] = CacheUpdateMetaInfo(
        newest_result_time_str=results[0].ui_time_started_at,
        oldest_result_time_str=results[-1].ui_time_started_at,
        n_results=len(results),
    )

    t2 = time.monotonic()

    conbench.metrics.GAUGE_BMRT_CACHE_LAST_UPDATE_SECONDS.set(t2 - t0)

    log.info(
        (
            "BMRT cache: keys in cache: %s, "
            "query took %.5f s, dict population took %.5f s"
        ),
        len(_cache_bmrs["by_id"]),
        t1 - t0,
        t2 - t1,
    )


def _periodically_fetch_last_n_benchmark_results() -> None:
    """
    Immediately return after having spawned a thread triggers periodic action.
    """
    first_sleep_seconds = 10
    min_delay_between_runs_seconds = 120

    def _run_forever():
        global _shutdown

        delay_s = first_sleep_seconds

        while True:
            # Build responsive sleep loop that inspects _shutdown often.
            deadline = time.monotonic() + delay_s
            while time.monotonic() < deadline:
                if _shutdown:
                    log.debug("_run_forever: shut down")
                    return

                time.sleep(0.02)

            t0 = time.monotonic()

            try:
                _fetch_and_cache_most_recent_results()
            except Exception as exc:
                # For now, log all error detail. (but handle all exceptions; do
                # some careful log-reading after rolling this out).
                log.exception("BMRT cache: exception during update: %s", exc)

            last_call_duration_s = time.monotonic() - t0

            # Generally we want to spent the majority of the time _not_ doing
            # this thing here. So, if the last iteration lasted for e.g. ~60
            # seconds, then keep waiting for ~five minutes until triggering the
            # next run.
            delay_s = max(min_delay_between_runs_seconds, 5 * last_call_duration_s)
            log.info("BMRT cache: trigger next fetch in %.3f s", delay_s)

    # Do not attempt to explicitly join thread. Terminate thread cleanly as
    # part of gunicorn's worker process shutdown -- therefore the signal
    # handler-based logic below which injects a shutdown signal into the
    # thread.
    if Config.TESTING:
        log.info("BMRT cache: disabled in TESTING mode")
        return

    threading.Thread(target=_run_forever).start()


def start_jobs():
    _periodically_fetch_last_n_benchmark_results()


def shutdown_handler(sig, frame):
    log.info("BMRT cache: saw signal %s, shutdown", sig)
    global _shutdown
    _shutdown = True


# Handle the common signals that instruct us to racefully shut down. We have
# installed custom logic in the gunicorn worker_interrupt hook where we send
# ourselves a SIGTERM sinal. Don't worry, I don't generally hurt myself.
signal.signal(signal.SIGTERM, shutdown_handler)
signal.signal(signal.SIGINT, shutdown_handler)
