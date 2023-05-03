import dataclasses
import logging
import signal
import threading
import time
from collections import defaultdict
from typing import Dict, List, TypedDict

from sqlalchemy import select

import conbench.metrics
from conbench.config import Config
from conbench.db import Session
from conbench.entities.benchmark_result import BenchmarkResult
from conbench.entities.run import Run
from conbench.hacks import get_case_kvpair_strings

"""
This module implements a job which populates and provides a cache for the N
most recent benchmark results, the tail end. Benchmark result tail-end cache:
BMRT cache.

Central cache data structure are Python dictionaries (with thread-safe(atomic)
set/get operations).
"""

original_sigint_handler = signal.getsignal(signal.SIGINT)
original_sigquit_handler = signal.getsignal(signal.SIGQUIT)

log = logging.getLogger(__name__)


# https://goshippo.com/blog/measure-real-size-any-python-object/
# https://stackoverflow.com/a/40880923
# And then brute force to get this to count at least something.
# the special cases happen rarely, i.e. this counts the majority of what
# matters.
def get_size(obj, seen=None):
    """Recursively finds size of objects"""

    if obj is None:
        return 0

    if isinstance(obj, werkzeug.local.ContextVar):
        return 0

    size = sys.getsizeof(obj)

    if seen is None:
        seen = set()

    obj_id = id(obj)
    if obj_id in seen:
        return 0
    # Important mark as seen *before* entering recursion to gracefully handle
    # self-referential objects
    seen.add(obj_id)

    if isinstance(obj, dict):
        size += sum([get_size(v, seen) for v in obj.values()])
        size += sum([get_size(k, seen) for k in obj.keys()])

    elif hasattr(obj, "__dict__"):
        try:
            size += get_size(obj.__dict__, seen)
        except RuntimeError:
            # handle werkzeug.local special context var protection:
            # https://github.com/pallets/werkzeug/blob/2.2.3/src/werkzeug/local.py
            log.info("ignore werkzeug RuntimeErr")
            return 0

    elif hasattr(obj, "__iter__") and not isinstance(obj, (str, bytes, bytearray)):
        if obj is None:
            return 0

        if isinstance(obj, _SpecialForm):
            # Ignore this obj: TypeError: '_SpecialForm' object is not iterable
            return 0

        try:
            size += sum([get_size(i, seen) for i in obj])
        except TypeError:
            # Might still fail with
            # TypeError: 'NoneType' object is not iterable
            log.info("ignore not-yet-understood TypeError")
            seen.add(id(obj))
            return 0
    return size


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

SHUTDOWN = False
_STARTED = False


# Fetching one million items from a sample DB takes ~1 minute on my machine
# (the `results = Session.scalars(....all())` call takes that long.
def _fetch_and_cache_most_recent_results(n=0.06 * 10**6) -> None:
    log.debug(
        "BMRT cache: keys in cache: %s",
        len(_cache_bmrs["by_id"]),
    )
    t0 = time.monotonic()

    # Also fetch hardware from associated Run, so that result.run is in cache,
    # too, and so that result.run.hardware is a quick lookup.
    results = Session.scalars(
        select(BenchmarkResult)
        .join(Run)
        .order_by(BenchmarkResult.timestamp.desc())
        .limit(n)
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
        # Add property _hardware on result obj, from Run.
        result._hardware = result.run.hardware
        # point of confusion: `result.case.name` is the benchmark name
        # result._bmrt_benchmark_name = str(result.case.name)
        # result._bmrt_hardware_id = str(result.run.hardware.id)
        # result._bmrt_hardware_name = str(result.run.hardware.name)

        by_name_dict[result.case.name].append(result)
        # Add a property on the Case object, on the fly.
        # Build the textual representation of this case which should also
        # uniquely / unambiguously define/identify this specific case.
        result.case.text_id = " ".join(get_case_kvpair_strings(result.case.tags))
        by_case_dict[result.case.id].append(result)
        # case_text_by_id[case_id] = case_text_id
        # result._bmrt_case_text_id = case_text_id
        # result._bmrt_context_id = str(result.context_id)
        # result._bmrt_context_dict = result.context.to_dict()
        # result._bmrt_ui_hardware_short = str(result.ui_hardware_short)
        # result._bmrt_is_failed = result.is_failed()

        # for obj in (result,):
        #     Session.expunge(obj)
        #     sqlalchemy.orm.make_transient(obj)

        # Alternatively, take an approach with
        # @dataclasses.dataclass(slots=True)
        # del result.run
        # del result.case
        # del result.info
        # del result.context
        # del result.optional_benchmark_info
        # del result.change_annotations
        # del result.error
        # del result.times
        # del result.q1
        # del result.q3
        # del result.iqr
        # del result.validation
        # del result._sa_instance_state

    # last_result = results[-1]
    # for key, value in vars(last_result).items():
    #     log.info("prop %s size: %s", key, get_size(value))

    first_bmr = next(iter(by_id_dict))
    # for key, value in vars(first_bmr).items():
    #     log.info("prop %s size: %s", key, get_size(value))


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

    dsize = get_size(_cache_bmrs)
    log.info("_cache_bmrs size: %s", dsize)


def _periodically_fetch_last_n_benchmark_results() -> None:
    """
    Immediately return after having spawned a thread triggers periodic action.
    """
    first_sleep_seconds = 10
    min_delay_between_runs_seconds = 120

    if Config.TESTING:
        first_sleep_seconds = 2
        min_delay_between_runs_seconds = 20

    def _run_forever():
        global SHUTDOWN
        global _STARTED
        _STARTED = True

        delay_s = first_sleep_seconds

        while True:
            # Build responsive sleep loop that inspects SHUTDOWN often.
            deadline = time.monotonic() + delay_s
            while time.monotonic() < deadline:
                if SHUTDOWN:
                    log.debug("_run_forever: shut down")
                    return

                time.sleep(0.1)

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

    if not Config.CREATE_ALL_TABLES:
        # This needs to be done more cleanly -- when running the DB migration,
        # the app should not even initialize so far.
        log.info(
            "BMRT cache: CREATE_ALL_TABLES is false, assume migration; disable cache job"
        )
        return

    threading.Thread(target=_run_forever).start()
    # Do not attempt to explicitly join thread. Terminate thread cleanly as
    # part of gunicorn's worker process shutdown -- therefore the signal
    # handler-based logic below which injects a shutdown signal into the
    # thread.


def start_jobs():
    log.info("start job: periodic BMRT cache population")
    _periodically_fetch_last_n_benchmark_results()
    log.info("start job: metrics.periodically_set_q_rem()")
    conbench.metrics.periodically_set_q_rem()


def shutdown_handler(sig, frame):
    log.info(
        "BMRT cache job (started: %s): saw signal %s, set shutdown flag", _STARTED, sig
    )
    global SHUTDOWN
    SHUTDOWN = True
    if sig == signal.SIGINT:
        original_sigint_handler(sig, frame)


# Handle the common signals that instruct us to gracefully shut down. We have
# installed custom logic in the gunicorn worker_interrupt hook where we send
# ourselves a SIGTERM sinal. Don't worry, I don't generally hurt myself.
signal.signal(signal.SIGTERM, shutdown_handler)

# For interactive sessions (such as when running make run-app-dev)
signal.signal(signal.SIGINT, shutdown_handler)

# There is no clear purpose for this yet; I wonder which mechanism docker
# compose really uses to signal its containers a graceful shutdown -- so far I
# need to send SIGINT twice, and I think then it immediately sends SIGKILL to
# containerized processes.
signal.signal(signal.SIGQUIT, shutdown_handler)
