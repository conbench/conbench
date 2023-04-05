"""
This module documents and initializes Prometheus metrics (Counters, Gauges,
Histograms, Summaries). It also defines functions for integration with the
Flask web application.

Helpful resources about naming metrics, as well as metric types:

- https://prometheus.io/docs/concepts/metric_types/
- https://github.com/prometheus/docs/blob/main/content/docs/practices/naming.md
- https://www.robustperception.io/on-the-naming-of-things/
- https://prometheus.io/docs/practices/naming/

A thread about using normal Python prometheus_client metrics at the same time
as prometheus_flask_exporter metrics ("just works!"):
https://github.com/rycus86/prometheus_flask_exporter/issues/147
"""

import logging
import os
import threading
import time

import flask
import prometheus_client
from prometheus_flask_exporter import NO_PREFIX
from prometheus_flask_exporter.multiprocess import GunicornInternalPrometheusMetrics

log = logging.getLogger(__name__)


COUNTER_GITHUB_HTTP_API_REQUESTS = prometheus_client.Counter(
    "conbench_github_httpapi_requests_total",
    "The total number of HTTP requests (attempted) to make to the GitHub HTTP API",
)


COUNTER_GITHUB_HTTP_API_REQUEST_FAILURES = prometheus_client.Counter(
    "conbench_github_httpapi_requests_failed_total",
    "The total number of HTTP requests to the GitHub HTTP API that failed "
    "eventually (either immediately or after retrying).",
)


COUNTER_GITHUB_HTTP_API_RETRYABLE_ERRORS = prometheus_client.Counter(
    "conbench_github_httpapi_retryable_errors_total",
    "The total number of retryable errors observed while interacting with the "
    "GitHub HTTP API (regardless of whether a retry was performed or not).",
)


COUNTER_GITHUB_HTTP_API_403RESPONSES = prometheus_client.Counter(
    "conbench_github_httpapi_403responses_total",
    "The total number of HTTP requests to the GitHub HTTP API that were "
    "responded to with a 403 response. Often rate-limiting/quota related.",
)


GAUGE_GITHUB_HTTP_API_QUOTA_REMAINING = prometheus_client.Gauge(
    "conbench_github_httpapi_quota_remaining",
    "A gauge that shows the last-observed x-ratelimit-remaining response "
    "header value.",
    # multiprocess mode gauges are tricky!
    # https://github.com/prometheus/client_python#multiprocess-mode-eg-gunicorn
    multiprocess_mode="liveall",
)

gauge_gh_api_rem_set = {"set": False}

# The topic of Gauge initiatlization in the Prometheus ecosystem is confusing.
# The spec says "Gauges MUST start at 0"
# (https://prometheus.io/docs/instrumenting/writing_clientlibs/). There are
# client libs that thought about NaN:
# https://github.com/micrometer-metrics/micrometer/issues/1343. With the very
# specific setup we have (Python's client lib in multiprocessing mode) it seems
# to report (from the start) the value 0. The value 0 however in this context
# has a special meaning: quota exhausted. So, once this gauge reports as 0 we
# want to know that this value came from an HTTP response. For now, set a
# special value -1 that by convention in this case here shall mean 'not
# initialized'. That is, if this ever shows a positive value or 0 then the
# value was communciated within an HTTP Response.
GAUGE_GITHUB_HTTP_API_QUOTA_REMAINING.set(-1)


def decorate_flask_app_with_metrics(app) -> None:
    """
    Add flask-prometheus-exporter magic to `app`.

    This mutates `app` in-place.
    """
    # If the environment tells us something unique about us when we are
    # one replica of N replicas, then inject the uniqueness too all emitted
    # metrics -- see https://github.com/conbench/conbench/issues/1008
    default_labels = {}
    epn = os.environ.get("ENV_POD_NAME")
    if epn:
        default_labels["envpodname"] = epn

    # Use `GunicornPrometheusMetrics` when spawning a separate HTTP server for
    # the metrics scrape endpoint. This needs PROMETHEUS_MULTIPROC_DIR to be
    # set to a path to a directory.
    _inspect_prom_multiproc_dir()
    GunicornInternalPrometheusMetrics(
        app=app,
        # See https://github.com/conbench/conbench/issues/1006
        # We will have to maybe iterate on those endpoint names,
        # and maybe, just maybe, add _some_ URL paths back when we understand
        # that we need them.
        group_by=http_handler_name,
        # Set bucket boundaries (unit: seconds) for tracking the distribution
        # of HTTP request processing durations (Prometheus metric of type
        # histogram). The default histogram buckets are not so useful for
        # Conbench as of today, because they are optimized for low-latency
        # APIs. Set bucket boundaries so that we have some resolution on the
        # high latency tail end. Once we push request processing times more or
        # less reliably below 10 seconds we can change these again. Each value
        # defines the upper inclusive bound for the corresponding histogram
        # bucket. Note that there is an implicit last/upper end bucket here
        # catching all observations up to +inf.
        # Update(JP): removed two buckets compared to initial stab, to work on
        # cardinatlity.
        buckets=(0.05, 0.1, 0.2, 0.5, 1.0, 5.0, 10.0, 20.0, 40.0, 70.0),
        default_labels=default_labels,
        defaults_prefix=NO_PREFIX,  # Remove the default "flask" prefix
    )


def http_handler_name(r: flask.Request) -> str:
    """
    Return string that is then used as matric label _value_ for representing
    the specific API endpoint / route handler that the currently incoming HTTP
    Request (as represented by the object `r` ) triggers.

    `r.endpoint` as built by Flask for example is

        - "api.runs"
        - "app.login"
        - "api.ping"
        - "static"
        - ...

    https://flask.palletsprojects.com/en/2.2.x/api/?highlight=endpoint#flask.Request.endpoint

    We define this function here for two good reasons:
        - to make this behavior explicit.
        - to allow for manually setting the _name_ of the metric label -- by
          default it would be "endpoint" which is sadly in conflict with
          another label already set by other parts of our metrics machinery.
          Use a completely different, generic name that can be re-used
          meaningfully when using something other than Flask. I like
          http_handler_name, and that's how we call this function.

    Here is the code that looks up the name of _this_ callable:
    https://github.com/rycus86/prometheus_flask_exporter/blob/413d73b629d40833fa6d85b6141dece87f102573/prometheus_flask_exporter/__init__.py#L402

    See https://github.com/conbench/conbench/issues/1006 for reference.
    """
    ep = r.endpoint
    if ep is None:
        log.warning("should not happen: `endpoint` is none in http_handler_name()")
        return "none"

    return ep


def _periodically_set_q_rem() -> None:
    """
    GAUGE_GITHUB_HTTP_API_QUOTA_REMAINING is a thread-safe data structure.

    See https://github.com/conbench/conbench/issues/997. Keep setting this
    gauge explicitly to -1 to try to not have this appear as if it's 0 (which
    seemingly the receiving end might think when there hasn't been an update
    for a while? Prometheus gauges are weird, because their initialization
    state is not so well-defined. For us, 0 is a special allowed value and
    explicitly _not_ the initialization value.)
    """

    def func():
        while True:
            time.sleep(10)
            if gauge_gh_api_rem_set["set"] - 1:
                # This process set an actual, meaningful value.
                # Stop re-inforcing the init state.
                return
            GAUGE_GITHUB_HTTP_API_QUOTA_REMAINING.set(-1)

    # Create a threaddy zombie, no need to join it. It likely terminates
    # itself. If it doesn't that's OK, too.
    threading.Thread(target=func).start()

    # This function immediately returns after having spawned the thread.


def _inspect_prom_multiproc_dir():
    """
    Log information about the environment variable PROMETHEUS_MULTIPROC_DIR
    and about the path it points to. This is helpful for debugging bad state.
    """
    path = os.environ.get("PROMETHEUS_MULTIPROC_DIR")
    log.info("env PROMETHEUS_MULTIPROC_DIR: `%s`", path)

    if not path:
        return

    try:
        log.info("os.path.isdir('%s'): %s", path, os.path.isdir(path))
    except OSError as exc:
        log.info("os.path.isdir('%s') failed: %s", path, exc)


_periodically_set_q_rem()
