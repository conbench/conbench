import os
import signal
import sys


"""
Gunicorn configuration that applies in testing and prod environments.

https://docs.gunicorn.org/en/stable/settings.html#config-file
"""


bind = ["0.0.0.0:5000"]

wsgi_app = "conbench:application"

# Canonical format, plus response generation duration in seconds.
access_log_format = (
    '%(h)s %(l)s %(u)s %(t)s "%(r)s" %(s)s %(b)s "%(f)s" "%(a)s" (%(L)s s)'
)

errorlog = "-"  # emit to stderr
accesslog = "-"  # emit to stdout
loglevel = "info"  # d efault

# requires setprocname
# proc_name = 'conbench-gunicorn'

# Reduce connection backlog from default (2048)
backlog = 300

# Run gunicorn as a single-process N thread model (these are real threads,
# based on CPython threading.Thread, using Unix pthreads). Assume that C copies
# of this are created by higher-level orchestration (so that more than one CPU
# core is after all serving requests).
# https://github.com/conbench/conbench/issues/1018
workers = 1
threads = 10

# This is the worker timeout; an observer process will terminate the observed
# worker process if the observed process hasn't responded within that
# timeframe. This was more relevant at times when we ran more than one worker
# process per gunicorn, and a single HTTP request could render a single process
# occupied. Keep a large value for now, for the case where all threads in the
# process process genuine requests (which all take a while to respond to)
timeout = 120


def worker_int(worker):
    # Motivation to use this hook was to build a simple/robust mechanism for
    # graceful shutdown of the _run_forever function in the BMRT cache.
    # https://github.com/benoitc/gunicorn/blob/69c508ac6e4b301045d3ce21acce8b416415d4c5/gunicorn/workers/base.py#L126
    # https://github.com/benoitc/gunicorn/issues/2706
    # https://github.com/benoitc/gunicorn/issues/2646
    sys.stdout.write("\nworker_int hook: send myself SIGTERM\n")
    os.kill(os.getpid(), signal.SIGTERM)
