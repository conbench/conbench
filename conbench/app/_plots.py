import collections
import statistics

import bokeh.models
import bokeh.palettes
import bokeh.plotting
import dateutil.parser

from ..hacks import sorted_data


BLUE = "#1F77B4"

# from https://learnui.design/tools/data-color-picker.html
APP_PALETTE = {
    3: [
        "#003f5c",
        "#bc5090",
        "#ffa600",
    ],
    4: [
        "#003f5c",
        "#7a5195",
        "#ef5675",
        "#ffa600",
    ],
    5: [
        "#003f5c",
        "#58508d",
        "#bc5090",
        "#ff6361",
        "#ffa600",
    ],
    6: [
        "#003f5c",
        "#444e86",
        "#955196",
        "#dd5182",
        "#ff6e54",
        "#ffa600",
    ],
    7: [
        "#003f5c",
        "#374c80",
        "#7a5195",
        "#bc5090",
        "#ef5675",
        "#ff764a",
        "#ffa600",
    ],
    8: [
        "#003f5c",
        "#2f4b7c",
        "#665191",
        "#a05195",
        "#d45087",
        "#f95d6a",
        "#ff7c43",
        "#ffa600",
    ],
}

GRAPHS = {
    "default": {},
    "file-read": {
        "title": "Read speed ({dataset})",
        "p.yaxis.axis_label": "Time to read (seconds)",
        "fields": ["output_type", "file_type", "compression"],
        "case_format": "{file_type} ({compression}) - {output_type}",
        "factor_format": "{file_type} ({compression})",
        "factor_bucket": "output_type",
        "time_series_title": "{name}: {file_type} ({compression}) - {output_type}",
        "time_series_group_by": "dataset",
        "time_series_tooltip": [
            ("name", "@name"),
            ("os_name", "@os_name"),
            ("os_version", "@os_version"),
            ("language", "@benchmark_language_version"),
            ("arrow", "@arrow_version"),
        ],
    },
    "file-write": {
        "title": "Write speed ({dataset})",
        "p.yaxis.axis_label": "Time to write (seconds)",
        "fields": ["input_type", "file_type", "compression"],
        "case_format": "{file_type} ({compression}) - {input_type}",
        "factor_format": "{file_type} ({compression})",
        "factor_bucket": "input_type",
        "time_series_title": "{name}: {file_type} ({compression}) - {input_type}",
        "time_series_group_by": "dataset",
        "time_series_tooltip": [
            ("name", "@name"),
            ("os_name", "@os_name"),
            ("os_version", "@os_version"),
            ("language", "@benchmark_language_version"),
            ("arrow", "@arrow_version"),
        ],
    },
}


def get_default_palette(length):
    # slice the ends off this palette, I don't like that last yellow etc
    return list(bokeh.palettes.inferno(length + 5)[3:-2])


def get_display_unit(unit):
    if unit == "s":
        return "seconds"
    elif unit == "B/s":
        return "bytes/seconds"
    elif unit == "i/s":
        return "items/seconds"
    else:
        return unit


def get_graph_definition(name):
    return GRAPHS.get(name, GRAPHS.get("default"))


def get_date_format():
    date_format = "%Y-%m-%d"
    return bokeh.models.DatetimeTickFormatter(
        microseconds=[date_format],
        milliseconds=[date_format],
        seconds=[date_format],
        minsec=[date_format],
        minutes=[date_format],
        hourmin=[date_format],
        hours=[date_format],
        days=[date_format],
        months=[date_format],
        years=[date_format],
    )


def get_title(benchmarks, graph, name):
    title = f"{name}"
    tags = benchmarks[0]["tags"]
    if "title" in graph:
        title = graph["title"].format(**tags)
    elif "dataset" in tags:
        dataset = tags["dataset"]
        title = f"{name} ({dataset})"
    return title


def get_timeseries_title(benchmarks, graph, name):
    title = f"{name}"
    tags = benchmarks[0]["tags"]
    if "time_series_title" in graph:
        title = graph["time_series_title"].format(**tags)
    elif "dataset" in tags:
        dataset = tags["dataset"]
        title = f"{name} ({dataset})"
    return title


def simple_bar_plot(benchmarks, height=400, width=400):
    if len(benchmarks) > 20:
        return None
    if len(benchmarks) == 1:
        return None

    name = benchmarks[0]["tags"]["name"]
    unit = get_display_unit(benchmarks[0]["stats"]["unit"])
    graph = get_graph_definition(name)

    fields = graph.get("fields", [])
    data = sorted_data(benchmarks, fields)

    cases, times = [], []
    for *values, timing in data:
        if fields:
            lookup = dict(zip(fields, values))
            case_format = graph.get("case_format", "")
            cases.append(case_format.format(**lookup, name=name))
        else:
            cases.append("-".join(values))
        times.append(timing)

    p = bokeh.plotting.figure(
        x_range=cases,
        title=get_title(benchmarks, graph, name),
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
    p.yaxis.axis_label = graph.get("p.yaxis.axis_label", unit)

    return p


def factor_bar_plot(benchmarks, height=400):
    name = benchmarks[0]["tags"]["name"]

    if len(benchmarks) > 40:
        print(f"Skipping factor_bar_plot {name}: {len(benchmarks)}")
        return None
    if len(benchmarks) == 1:
        print(f"Skipping factor_bar_plot {name}: {len(benchmarks)}")
        return None

    unit = get_display_unit(benchmarks[0]["stats"]["unit"])
    graph = get_graph_definition(name)

    fields = graph.get("fields", [])
    data, default_factor_bucket = sorted_data(benchmarks, fields, factor=True)
    factor_bucket = graph.get("factor_bucket", default_factor_bucket)

    factors, x, counts = [], [], []
    for *values, timing in data:
        lookup = dict(zip(fields, values))

        factor = "-".join(values[:-1])
        if "factor_format" in graph:
            factor = graph["factor_format"].format(**lookup)

        if factor not in factors:
            factors.append(factor)

        if fields:
            x.append((lookup[factor_bucket], factor))
        else:
            x.append((values[-1], factor))

        counts.append(timing)

    sorted_factors = list(zip(x, counts))
    x = [item[0] for item in sorted_factors]
    counts = [item[1] for item in sorted_factors]

    length = len(factors)
    default_palette = get_default_palette(length)
    palette = APP_PALETTE[length] if length in APP_PALETTE else default_palette

    source = bokeh.models.ColumnDataSource(data=dict(x=x, counts=counts))
    p = bokeh.plotting.figure(
        x_range=bokeh.models.FactorRange(*x),
        plot_height=height,
        title=get_title(benchmarks, graph, name),
        toolbar_location=None,
        tools="",
    )
    p.vbar(
        x="x",
        top="counts",
        width=0.9,
        source=source,
        line_color="white",
        fill_color=bokeh.transform.factor_cmap(
            "x",
            palette=palette,
            factors=list(factors),
            start=1,
            end=2,
        ),
    )
    p.y_range.start = 0
    p.x_range.range_padding = 0.1
    p.xgrid.grid_line_color = None
    p.xaxis.major_label_orientation = 1
    p.yaxis.axis_label = graph.get("p.yaxis.axis_label", unit)

    return p


def time_series_plot(by_machine_context, graph):
    # grab any benchmark from this group to get the graph definition
    key = list(by_machine_context.keys())[0]
    benchmarks = list(by_machine_context[key].values())
    name = benchmarks[0]["tags"]["name"]
    title = get_timeseries_title(benchmarks, graph, name)
    unit = get_display_unit(benchmarks[0]["stats"]["unit"])

    palette = get_default_palette(len(by_machine_context))
    tooltip = graph.get("time_series_tooltip", [])
    tooltips = [("date", "$x{%F}"), ("mean", "$y{0.000}")] + tooltip
    hover = bokeh.models.HoverTool(
        tooltips=tooltips,
        formatters={"$x": "datetime"},
    )

    p = bokeh.plotting.figure(
        x_axis_type="datetime",
        plot_height=250,
        plot_width=400,
        title=title,
        toolbar_location=None,
        tools=[hover],
    )
    p.ygrid.grid_line_alpha = 0.5
    p.yaxis.axis_label = unit
    p.xaxis.major_label_orientation = 1
    p.xaxis.axis_label = "Date"
    p.xaxis.formatter = get_date_format()
    all_times = []
    palette_copy = palette[::]
    machine_keys = list(by_machine_context.keys())
    for machine_key in sorted(machine_keys):
        by_id = by_machine_context[machine_key]
        data = []
        for benchmark in by_id.values():
            data.append(
                [
                    dateutil.parser.isoparse(benchmark["stats"]["timestamp"]),
                    float(benchmark["stats"]["mean"]),
                    benchmark["machine_info"],
                    benchmark["context"],
                ]
            )

        dates, times = [], []
        info = collections.defaultdict(list)
        for x in sorted(data):
            dates.append(x[0])
            times.append(x[1])
            for k, v in x[2].items():
                info[k].append(v)
            for k, v in x[3].items():
                info[k].append(v)
        all_times.extend(times)
        source_data = dict(x=dates, y=times)
        info.pop("id", None)
        source_data.update(**info)

        color = palette_copy.pop() if palette_copy else BLUE
        source = bokeh.models.ColumnDataSource(data=source_data)
        p.circle(color=color, source=source)
        p.line(color=color, source=source)

    end = statistics.stdev(all_times) if len(all_times) > 2 else 1
    p.y_range = bokeh.models.Range1d(start=0, end=max(all_times) + end)

    return p


def summary_scatter_plot(by_group, graph):
    palette = get_default_palette(len(by_group))
    group_by_key = graph.get("time_series_group_by", "")

    tooltips = [("date", "$x{%F}"), ("mean", "$y{0.000}")]
    if group_by_key:
        tooltips.append((group_by_key, "@group"))
    hover = bokeh.models.HoverTool(
        tooltips=tooltips,
        formatters={"$x": "datetime"},
    )
    p = bokeh.plotting.figure(
        x_axis_type="datetime",
        plot_height=250,
        plot_width=400,
        toolbar_location=None,
        tools=[hover],
    )
    p.ygrid.grid_line_alpha = 0.5
    p.xaxis.axis_label = "Date"
    p.xaxis.major_label_orientation = 1
    p.xaxis.formatter = get_date_format()

    all_times = []
    palette_copy = palette[::]
    for group_by in sorted(by_group.keys()):
        benchmarks = by_group[group_by]
        dates, times, groups = [], [], []
        for benchmark in benchmarks:
            dates.append(dateutil.parser.parse(benchmark["stats"]["timestamp"]))
            times.append(float(benchmark["stats"]["mean"]))
            if group_by_key:
                groups.append(benchmark["tags"][group_by_key])
            else:
                groups.append(None)
        all_times.extend(times)
        source_data = dict(x=dates, y=times, group=groups)
        source = bokeh.models.ColumnDataSource(data=source_data)
        color = palette_copy.pop() if palette_copy else BLUE
        p.circle(color=color, source=source)

    p.yaxis.axis_label = get_display_unit(benchmark["stats"]["unit"])
    end = statistics.stdev(all_times) if len(all_times) > 2 else 1
    p.y_range = bokeh.models.Range1d(start=0, end=max(all_times) + end)

    return p
