import bokeh.plotting

from ..hacks import sorted_data


def get_display_unit(unit):
    if unit == "s":
        return "seconds"
    elif unit == "B/s":
        return "bytes/seconds"
    elif unit == "i/s":
        return "items/seconds"
    else:
        return unit


def get_title(benchmarks, name):
    title = f"{name}"
    tags = benchmarks[0]["tags"]
    if "dataset" in tags:
        dataset = tags["dataset"]
        title = f"{name} ({dataset})"
    return title


def simple_bar_plot(benchmarks, height=400, width=400):
    if len(benchmarks) > 30:
        return None
    if len(benchmarks) == 1:
        return None

    name = benchmarks[0]["tags"]["name"]
    unit = get_display_unit(benchmarks[0]["stats"]["unit"])

    cases, times = [], []
    data = sorted_data(benchmarks)
    for *values, timing in data:
        cases.append("-".join(values))
        times.append(timing)

    p = bokeh.plotting.figure(
        x_range=cases,
        title=get_title(benchmarks, name),
        toolbar_location=None,
        plot_height=height,
        plot_width=width,
        tools="",
    )
    p.vbar(x=cases, top=times, width=0.9, line_color="white", color="silver")
    p.y_range.start = 0
    p.x_range.range_padding = 0.1
    p.xgrid.grid_line_color = None
    p.xaxis.major_label_orientation = 1
    p.yaxis.axis_label = unit

    return p
