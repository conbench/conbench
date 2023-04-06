from ..hacks import set_display_benchmark_name, set_display_case_permutation
from ..units import formatter_for_unit


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
    if not benchmark["stats"]["mean"]:
        return ""

    unit = benchmark["stats"]["unit"]
    mean = float(benchmark["stats"]["mean"])
    fmt = formatter_for_unit(unit)
    benchmark["display_mean"] = fmt(mean, unit)


def set_display_error(benchmark):
    if not benchmark["error"]:
        benchmark["error"] = ""
