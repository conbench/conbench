# # https://github.com/prometheus/client_python#multiprocess-mode-eg-gunicorn
# from prometheus_client import multiprocess


# def worker_exit(server, worker):
#     multiprocess.mark_process_dead(worker.pid)

# then in the Gunicorn config file:
# from prometheus_flask_exporter.multiprocess import GunicornPrometheusMetrics


# def when_ready(server):
#     GunicornPrometheusMetrics.start_http_server_when_ready(8000, "0.0.0.0")
#     print(
#         'done with: GunicornPrometheusMetrics.start_http_server_when_ready(8000, "0.0.0.0")'
#     )


# def child_exit(server, worker):
#     GunicornPrometheusMetrics.mark_process_dead_on_child_exit(worker.pid)

from prometheus_flask_exporter.multiprocess import GunicornInternalPrometheusMetrics


def child_exit(server, worker):
    GunicornInternalPrometheusMetrics.mark_process_dead_on_child_exit(worker.pid)
