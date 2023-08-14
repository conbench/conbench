"""
Pragmatic job management. A job runs in a thread (which is not an HTTP-handling
thread).

Currently managed jobs:

- long-running thread for periodic BMRT cache population/refresh
- long-running thread for periodic prometheus gauge re-init/set()
"""

import logging
import signal

import conbench.bmrt
import conbench.metrics
import conbench.util
from conbench.config import Config


original_sigint_handler = signal.getsignal(signal.SIGINT)
original_sigquit_handler = signal.getsignal(signal.SIGQUIT)

log = logging.getLogger(__name__)


SHUTDOWN = False
_STARTED = False
_THREADS = []


def start_jobs():
    if not Config.CREATE_ALL_TABLES:
        # This needs to be done more cleanly -- when running the DB migration,
        # the app should not even initialize so far.
        log.info(
            "BMRT cache: CREATE_ALL_TABLES is false, assume migration; do not start job"
        )
    else:
        log.info("start job: periodic BMRT cache population")
        _THREADS.append(conbench.bmrt.periodically_fetch_last_n_benchmark_results())

    log.info("start job: metrics.periodically_set_q_rem()")
    _THREADS.append(conbench.metrics.periodically_set_q_rem())

    # This state-keeping var is so far only used for logging.
    global _STARTED
    _STARTED = True


def stop_jobs_join():
    """
    For clean shutdown, explicitly waits for threads to terminate.

    I've added this for the test suite where we may go through multiple
    start/stop cycles. This is not really great because this mode of operation
    deviates from "prod".
    """
    log.info("stop_jobs_join(): set shutdown flag")
    global SHUTDOWN
    SHUTDOWN = True
    for t in _THREADS:
        log.info("join %s", t)
        t.join()

    log.info("all threads joined")


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
