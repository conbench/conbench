"""
Relevant docs:

- https://github.com/rycus86/prometheus_flask_exporter#wsgi
- https://github.com/prometheus/client_python#multiprocess-mode-eg-gunicorn

prometheus_flask_exporter provides a useful quickstart, exposing relevant
metrics around HTTP request handlers. It is however potentially a little too
opinionated. I have not yet looked into adding custom metrics (like a custom
gauge, or counter).

I'd also like to add that the 'multiprocess complication' is not great to have
in the system. I think that generally these limitations are fine:
https://github.com/prometheus/client_python#multiprocess-mode-eg-gunicorn

But the added complexity compared to a more canonical setup is maybe hurtful in
the future.

Yet, I believe this is a great starting point. Within the 'multiprocess
complication' there is a choice to make: expose the /metrics HTTP endpoint in
the same HTTP server that handles regular HTTP requests, or spawn a separate
HTTP server for that? The latter has the advantage of separation of concerns
(metrics can still be obtained in case of a dead-locked main HTTP server).
Maybe the access log is a relevant criterion, too. I'd love to see an access
log showing the requests to the /metrics endpoint.
"""

# What's outcommented is a method that can be used when running a separate
# gunicorn HTTP server for serving the metrics endpoing.
#
# from prometheus_flask_exporter.multiprocess import GunicornPrometheusMetrics
# def when_ready(server):
#     GunicornPrometheusMetrics.start_http_server_when_ready(8000, "0.0.0.0")
#     print(
#         'done with: GunicornPrometheusMetrics.start_http_server_when_ready(8000, "0.0.0.0")'
#     )
# def child_exit(server, worker):
#     GunicornPrometheusMetrics.mark_process_dead_on_child_exit(worker.pid)
#

from prometheus_flask_exporter.multiprocess import GunicornInternalPrometheusMetrics


def child_exit(server, worker):
    GunicornInternalPrometheusMetrics.mark_process_dead_on_child_exit(worker.pid)


# Canonical gunicorn config below this line.
# https://docs.gunicorn.org/en/stable/settings.html#config-file


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
