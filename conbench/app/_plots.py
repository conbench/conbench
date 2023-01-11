import collections
import datetime
import json
import logging

import bokeh.plotting
import dateutil

from ..hacks import sorted_data
from ..units import formatter_for_unit

log = logging.getLogger(__name__)


class TimeSeriesPlotMixin:
    def get_outliers(self, benchmarks):
        benchmarks_by_id = {b["id"]: b for b in benchmarks}

        # top 3 outliers
        outliers = sorted(
            [
                (abs(float(b["stats"]["z_score"])), b["id"])
                for b in benchmarks
                if b["stats"]["z_regression"] or b["stats"]["z_improvement"]
            ],
            reverse=True,
        )[:3]

        outliers = [benchmarks_by_id[o[1]] for o in outliers]
        outlier_ids = [b["id"] for b in outliers]
        outlier_names = [f'{b["display_batch"]}, {b["display_name"]}' for b in outliers]
        return outliers, outlier_ids, outlier_names

    def get_history_plot(self, benchmark, run, i=0):
        history = self._get_history(benchmark)
        if history:
            return json.dumps(
                bokeh.embed.json_item(
                    time_series_plot(history, benchmark, run),
                    f"plot-history-{i}",
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
        return "bytes/second"
    elif unit == "i/s":
        return "items/second"
    else:
        return unit


def get_date_format():
    date_format = "%Y-%m-%d"
    return bokeh.models.DatetimeTickFormatter(
        microseconds=date_format,
        milliseconds=date_format,
        seconds=date_format,
        minsec=date_format,
        minutes=date_format,
        hourmin=date_format,
        hours=date_format,
        days=date_format,
        months=date_format,
        years=date_format,
    )


def _simple_source(data, unit):
    unit_fmt = formatter_for_unit(unit)
    cases, points, means = [], [], []
    points_formated, units_formatted = [], set()

    for *values, point in data:
        cases.append(values)
        points.append(point)
        formatted = unit_fmt(float(point), unit)
        means.append(formatted)
        formated_point, formatted_unit = formatted.split(" ", 1)
        points_formated.append(formated_point)
        units_formatted.add(formatted_unit)

    unit_formatted = units_formatted.pop() if len(units_formatted) == 1 else None
    if unit_formatted:
        points = points_formated

    axis_unit = unit_formatted if unit_formatted is not None else unit
    if axis_unit == unit:
        axis_unit = get_display_unit(unit)

    # remove redundant tags from labels
    len_cases = len(cases)
    counts = collections.Counter([tag for case in cases for tag in case])
    stripped = [[tag for tag in case if counts[tag] != len_cases] for case in cases]
    cases = ["-".join(tags) for tags in stripped]

    source_data = dict(x=cases, y=points, means=means)
    return bokeh.models.ColumnDataSource(data=source_data), axis_unit


def simple_bar_plot(benchmarks, height=400, width=400, vbar_width=0.7):
    if len(benchmarks) > 30:
        return None
    if len(benchmarks) == 1:
        return None

    unit = benchmarks[0]["stats"]["unit"]
    data = sorted_data(benchmarks)
    source, axis_unit = _simple_source(data, unit)

    tooltips = [("mean", "@means")]
    hover = bokeh.models.HoverTool(tooltips=tooltips)

    p = bokeh.plotting.figure(
        x_range=source.data["x"],
        toolbar_location=None,
        height=height,
        width=width,
        tools=[hover],
    )
    p.vbar(
        x="x",
        top="y",
        source=source,
        width=vbar_width,
        line_color="white",
        color="silver",
    )

    p.y_range.start = 0
    p.x_range.range_padding = 0.1
    p.xgrid.grid_line_color = None
    p.xaxis.major_label_orientation = 1
    p.yaxis.axis_label = axis_unit

    return p


def _should_format(data, unit):
    unit_fmt = formatter_for_unit(unit)

    units_formatted = set()
    for x in data:
        units_formatted.add(unit_fmt(float(x["mean"]), unit).split(" ", 1)[1])

    unit_formatted = units_formatted.pop() if len(units_formatted) == 1 else None

    should = unit_formatted is not None
    axis_unit = unit_formatted if unit_formatted is not None else unit
    if axis_unit == unit:
        axis_unit = get_display_unit(unit)

    return should, axis_unit


def _source(
    data,
    unit,
    formatted=False,
    distribution_mean=False,
    alert_min=False,
    alert_max=False,
):
    # Note(JP): important magic: if not specified otherwise, this extracts
    # the mean-over-time.
    key = "distribution_mean" if distribution_mean else "mean"

    unit_fmt = formatter_for_unit(unit)

    # TODO: These commit message prefixes end up in the on-hover tooltip.
    # Change this to use short commit hashes. The long commit message prefix
    # does not unambiguously specify the commit. Ideally link to the commit, in
    # the tooltip?
    commits = [x["message"] for x in data]
    dates = [dateutil.parser.isoparse(x["timestamp"]) for x in data]

    points, means = [], []
    if alert_min:
        for x in data:
            alert = 5 * float(x["distribution_stdev"])
            points.append(float(x["distribution_mean"]) - alert)
            means.append(unit_fmt(points[-1], unit))
    elif alert_max:
        for x in data:
            alert = 5 * float(x["distribution_stdev"])
            points.append(float(x["distribution_mean"]) + alert)
            means.append(unit_fmt(points[-1], unit))
    else:
        points = [x[key] for x in data]
        # Note(JP): If `means` is just string-formatted `points` then this is
        # kind of acknowledging that `points` is always a collection of mean
        # values. It seems that this is a string value field that is only
        # ever used for tooltip generation?
        means = [unit_fmt(float(x[key]), unit) for x in data if x[key]]

    if formatted:
        # Note(JP): why would we want to calculate the raw numeric data from
        # the tooltip string labels?
        points = [x.split(" ")[0] for x in means]

    source_data = dict(x=dates, y=points, commits=commits, means=means)
    return bokeh.models.ColumnDataSource(data=source_data)


def time_series_plot(history, benchmark, run, height=380, width=1100):

    # log.info("Time series plot for:\n%s", json.dumps(history, indent=2))

    unit = history[0]["unit"]
    with_dist = [h for h in history if h["distribution_mean"]]
    formatted, axis_unit = _should_format(history, unit)

    # Note(JP): `history` is an ordered list of dicts, each dict has a `mean`
    # key which is extracted here by default.
    source_mean_over_time = _source(history, unit, formatted=formatted)
    source_min_over_time = bokeh.models.ColumnDataSource(
        data=dict(
            x=[dateutil.parser.isoparse(x["timestamp"]) for x in history],
            y=[min(x["data"]) for x in history],
            # commits=commits,
            # means=means,
        )
    )

    source_current_bm_mean = _source(
        [
            {
                "mean": benchmark["stats"]["mean"],
                "message": run["commit"]["message"],
                "timestamp": run["commit"]["timestamp"],
            }
        ],
        unit,
        formatted=formatted,
    )

    source_current_bm_min = _source(
        [
            {
                "mean": benchmark["stats"]["min"],
                "message": run["commit"]["message"],
                "timestamp": run["commit"]["timestamp"],
            }
        ],
        unit,
        formatted=formatted,
    )

    source_mean = _source(with_dist, unit, formatted=formatted, distribution_mean=True)
    source_alert_min = _source(with_dist, unit, formatted=formatted, alert_min=True)
    source_alert_max = _source(with_dist, unit, formatted=formatted, alert_max=True)

    t_start = source_mean_over_time.data["x"][0]
    t_end = source_mean_over_time.data["x"][-1]

    t_range: datetime.timedelta = t_end - t_start

    # Add padding/buffer to left and right so that newest data point does not
    # disappear under right plot boundary, and so that the oldest data point
    # has space from legend.
    t_start = t_start - (0.4 * t_range)
    t_end = t_end + (0.07 * t_range)

    p = bokeh.plotting.figure(
        x_axis_type="datetime",
        height=height,
        width=width,
        tools=["pan", "zoom_in", "zoom_out", "reset"],
        x_range=(t_start, t_end),
    )
    p.toolbar.logo = None

    p.xaxis.formatter = get_date_format()
    p.xaxis.major_label_orientation = 1
    p.yaxis.axis_label = axis_unit

    scatter_mean_over_time = p.circle(
        source=source_mean_over_time,
        legend_label="individual benchmark (mean)",
        name="history",
        size=4,
        color="#ccc",
    )

    p.line(
        source=source_min_over_time,
        legend_label="individual benchmark (min)",
        name="min-over-time",
        color="#222",
    )
    p.circle(
        source=source_min_over_time,
        legend_label="individual benchmark (min)",
        name="min-over-time",
        size=2,
        color="#222",
    )

    p.line(source=source_mean, color="#ffa600", legend_label="rolling window mean")
    p.line(
        source=source_alert_min,
        color="Silver",
        legend_label="rolling window mean +/- 5 σ",
        line_join="round",
        width=1,
    )
    p.line(source=source_alert_max, color="Silver")

    cur_bench_mean_circle = p.circle(
        source=source_current_bm_mean,
        size=8,
        color="#ff6361",
        legend_label="current benchmark (mean)",
        name="benchmark",
    )

    cur_bench_min_circle = p.circle(
        source=source_current_bm_min,
        size=8,
        color="#000",
        legend_label="current benchmark (min)",
        name="benchmark",
    )

    p.add_tools(
        bokeh.models.HoverTool(
            tooltips=[
                ("date", "$x{%F}"),
                # Note(JP): this is where the `means` name becomes special,
                # I think.
                ("mean", "@means"),
                ("commit", "@commits"),
            ],
            formatters={"$x": "datetime"},
            renderers=[
                scatter_mean_over_time,
                cur_bench_mean_circle,
                cur_bench_min_circle,
            ],
        )
    )

    p.legend.title_text_color = "darkgray"
    p.legend.title = f"benchmark results: {len(history)}"
    p.legend.location = "top_left"

    # Change the number of expected/desired date x ticks. There is otherwise
    # only very few of them (like 4). Also see
    # https://github.com/bokeh/bokeh/issues/665 and
    # https://github.com/bokeh/bokeh/pull/2186
    p.xaxis.ticker.desired_num_ticks = 9

    range_tool = bokeh.models.RangeTool(x_range=p.x_range)
    range_tool.overlay.fill_color = "gainsboro"
    range_tool.overlay.fill_alpha = 0.2

    select = bokeh.plotting.figure(
        title="drag the middle and edges of the selection box to change the range above",
        height=80,
        width=width,
        y_range=p.y_range,
        x_axis_type="datetime",
        y_axis_type=None,
        tools="",
        toolbar_location=None,
    )

    select.line("x", "y", source=source_mean_over_time)
    select.ygrid.grid_line_color = None
    select.add_tools(range_tool)
    select.toolbar.active_multi = range_tool
    select.axis.visible = False
    select.title.text_font_style = "italic"

    spacers = []
    for _ in range(2):
        spacer = bokeh.plotting.figure(
            toolbar_location=None,
            height=20,
        )
        spacer.outline_line_color = None
        spacers.append(spacer)
        # Note(JP): I cannot make sense of this warning. I think the printed
        # text is not acted on by anyone. Outcommeting for now.
        # print(f"Ignore any MISSING_RENDERERS warning for id={spacer.id}")

    return bokeh.layouts.column(p, spacers[0], select, spacers[1])
