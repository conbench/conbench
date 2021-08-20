import json

import bokeh.plotting
import dateutil

from ..hacks import sorted_data


class TimeSeriesPlotMixin:
    def get_history_plot(self, benchmark):
        history = self._get_history(benchmark)
        if history:
            return json.dumps(
                bokeh.embed.json_item(
                    time_series_plot(history, benchmark["id"]),
                    "plot-history",
                )
            )
        return None

    def _get_history(self, benchmark):
        response = self.api_get("api.history", benchmark_id=benchmark["id"])
        if response.status_code != 200:
            self.flash("Error getting history.")
            return []
        return response.json


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


def time_series_plot(history, benchmark_id, height=250, width=1000):
    unit = get_display_unit(history[0]["unit"])
    current = [h for h in history if h["benchmark_id"] == benchmark_id]
    with_dist = [h for h in history if h["distribution_mean"]]

    times = [h["mean"] for h in history]
    commits = [h["message"] for h in history]
    dates = [dateutil.parser.isoparse(h["timestamp"]) for h in history]

    times_x = [c["mean"] for c in current]
    commits_x = [c["message"] for c in current]
    dates_x = [dateutil.parser.isoparse(c["timestamp"]) for c in current]

    times_mean = [w["distribution_mean"] for w in with_dist]
    commits_mean = [w["message"] for w in with_dist]
    dates_mean = [dateutil.parser.isoparse(w["timestamp"]) for w in with_dist]

    alert_min, alert_max = [], []
    for w in with_dist:
        alert = 5 * float(w["distribution_stdev"])
        alert_min.append(float(w["distribution_mean"]) - alert)
        alert_max.append(float(w["distribution_mean"]) + alert)

    source_data = dict(x=dates, y=times, commit=commits)
    source = bokeh.models.ColumnDataSource(data=source_data)

    source_data_x = dict(x=dates_x, y=times_x, commit=commits_x)
    source_x = bokeh.models.ColumnDataSource(data=source_data_x)

    source_data_mean = dict(x=dates_mean, y=times_mean, commit=commits_mean)
    source_mean = bokeh.models.ColumnDataSource(data=source_data_mean)

    source_data_alert_min = dict(x=dates_mean, y=alert_min, commit=commits_mean)
    source_alert_min = bokeh.models.ColumnDataSource(data=source_data_alert_min)

    source_data_alert_max = dict(x=dates_mean, y=alert_max, commit=commits_mean)
    source_alert_max = bokeh.models.ColumnDataSource(data=source_data_alert_max)

    tooltips = [
        ("date", "$x{%F}"),
        ("mean", "$y{0.000}"),
        ("unit", unit),
        ("commit", "@commit"),
    ]
    hover = bokeh.models.HoverTool(
        tooltips=tooltips,
        formatters={"$x": "datetime"},
    )
    p = bokeh.plotting.figure(
        x_axis_type="datetime",
        plot_height=height,
        plot_width=width,
        toolbar_location=None,
        tools=[hover],
    )

    p.xaxis.formatter = get_date_format()
    p.xaxis.major_label_orientation = 1
    p.yaxis.axis_label = unit

    p.line(source=source, legend_label="History")
    p.line(source=source_mean, color="#ffa600", legend_label="Mean")
    p.line(source=source_alert_min, color="Silver", legend_label="+/- 5 σ")
    p.line(source=source_alert_max, color="Silver")
    p.circle(source=source_x, size=8, color="#ff6361", legend_label="Benchmark")

    p.legend.location = "bottom_left"

    return p
