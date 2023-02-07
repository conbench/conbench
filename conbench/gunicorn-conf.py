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
