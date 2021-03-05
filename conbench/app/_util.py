from ..hacks import set_display_batch, set_display_name
from ..units import formatter_for_unit


def augment(benchmark):
    set_display_name(benchmark)
    set_display_time(benchmark)
    set_display_batch(benchmark)
    set_display_mean(benchmark)
    tags = benchmark["tags"]
    if "dataset" in tags:
        tags["dataset"] = dataset_name(tags["dataset"])


def dataset_name(name):
    return name.replace("_", " ")


def display_time(t):
    return t.split(".")[0].replace("T", "  ").rsplit(":", 1)[0]


def set_display_time(benchmark):
    t = benchmark["stats"]["timestamp"]
    benchmark["display_timestamp"] = display_time(t)


def set_display_mean(benchmark):
    unit = benchmark["stats"]["unit"]
    mean = float(benchmark["stats"]["mean"])
    fmt = formatter_for_unit(unit)
    benchmark["display_mean"] = fmt(mean, unit)
