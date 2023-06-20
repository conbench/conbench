import flask as f

from conbench.numstr import numstr

from ..config import Config
from ..hacks import set_display_benchmark_name, set_display_case_permutation


def error_page(msg="", alert_level="danger", subtitle="") -> str:
    """
    Generate HTML text which shows an error page, presenting an error message.

    This is OK to be delivered in a status-200 HTTP response for now.

    When msg is not provided (empty string) then this serves as a tool to
    expose current flash messages via a simple template (this will leave the
    app_content block empty).
    """
    # add more as desired
    assert alert_level in ("info", "danger", "primary", "warning")
    return f.render_template(
        "error.html",
        error_message=msg,
        application=Config.APPLICATION_NAME,
        # The (sub)title of the page (legacy, what's that for?)
        title=subtitle,
        alert_level=alert_level,
    )


def augment(benchmark, contexts=None):
    set_display_benchmark_name(benchmark)
    set_display_time(benchmark)
    set_display_case_permutation(benchmark)
    set_display_mean(benchmark)
    set_display_language(benchmark, contexts)
    set_display_error(benchmark)
    tags = benchmark["tags"]
    if "dataset" in tags:
        tags["dataset"] = dataset_name(tags["dataset"])


def dataset_name(name):
    return name.replace("_", " ")


def display_time(t: str):
    """
    Expect `t` to be an ISO 8601 compliant string
    - that encodes the UTC timezone with a Z suffix
    - that does not contain fractions of seconds

    Input example:  "2023-01-31Z05:36:45Z"
    Output example: "2023-01-31 05:36:45 UTC"
    """
    return t.replace("T", " ").replace("Z", " UTC")


def set_display_language(benchmark, contexts):
    if contexts is not None and benchmark["links"]["context"] in contexts:
        url = benchmark["links"]["context"]
        benchmark["display_language"] = contexts[url]["benchmark_language"]
    else:
        benchmark["display_language"] = "unknown"


def set_display_time(benchmark):
    benchmark["display_timestamp"] = display_time(benchmark["timestamp"])


def set_display_mean(benchmark):
    """
    Unclear in which context this is being consumed: where is this displayed?
    Does it make sense to limit this to a certain number of significant digits?

    This probably should be transitioned to SVS (not just mean). And depending
    on the context we may want to show/reveal raw data (with needless
    precision) _or_ limit precision (via sigfigs count) meaningfully.

    Update: seems to be shown in a tabular view where a per-result value
    is shown. 4 sigfigs are enough then.
    """
    if not benchmark["stats"]["mean"]:
        return ""

    unit = benchmark["stats"]["unit"]
    mean = float(benchmark["stats"]["mean"])
    benchmark["display_mean"] = f"{numstr(mean, sigfigs=4)} {unit}"


def set_display_error(benchmark):
    if not benchmark["error"]:
        benchmark["error"] = ""
