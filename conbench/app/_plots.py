import collections
import datetime
import json
import logging
from typing import Optional

import bokeh.plotting
import dateutil
import bokeh.events
from bokeh.models import Spacer, Span, OpenURL, TapTool, CustomJS

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
    commit_messages = [d["message"] for d in data]

    # Note(JP): isoparse() returns a `datetime.datetime` object. And I think
    # that the `timestamp` property corresponds to the invocation (or finish)
    # time of the corresponding benchmark case run (the `timestamp` property on
    # the `BenchmarkCreate` schema in the Conbench API). Are these tz-aware or
    # tz-naive but in UTC?
    datetimes = [dateutil.parser.isoparse(x["timestamp"]) for x in data]
    date_strings = [d.strftime("%Y-%m-%d %H-%M %Z") for d in datetimes]

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

    return bokeh.models.ColumnDataSource(
        data={
            "x": datetimes,
            "y": points,
            "date_strings": date_strings,
            "commit_messages": commit_messages,
            "commit_hashes_short": ["#" + d["sha"][:7] for d in data],
            "relative_benchmark_urls": [
                f'/benchmarks/{d["benchmark_id"]}' for d in data
            ],
            "means": means,
        }
    )


def _inspect_for_multisample(items) -> tuple[bool, Optional[int]]:
    """
    `items`: list of benchmark results as encoded by the history variant of the
    `_Serializer(EntitySerializer)`.

    Detect and handle special case where each data point (benchmark) comes with
    at most one data point (only one benchmark iteration's result). If all
    benchmarks report exactly one sample, or only zero samples, or a mixture of
    either one sample or zero samples: then this is not multisample in the
    sense of "(usually) more than one sample per benchmark".
    """

    # Get number of samples for each benchmark.
    samplecounts = [len(i["data"]) for i in items]

    multisample = True
    multisample_count = None
    scset = set(samplecounts)
    if scset in (set((0, 1)), set((1,))):
        multisample = False

    # For the special case where each benchmark in `items` reports exactly N
    # samples with N>1: extract the number N. There are ambiguous cases where
    # there (usually) are more than one sample per benchmark, but the exact
    # number of samples is not the same for each benchmark. Do not return a
    # simple/single (wrong) number in that case, but let return
    # `multisample_count` as `None`, meaning: ambiguous
    if len(scset) == 1:
        count = scset.pop()
        if count > 1:
            multisample_count = count

    return multisample, multisample_count


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
            # TODO: best-case is not always min, e.g. when data has a unit like
            # bandwidth.
            y=[min(x["data"]) for x in history],
        )
    )

    # source_mean_over_time.callback = CustomJS(
    #     args=dict(src=source_mean_over_time),
    #     code="""

    #     var rundiv = querySelectorAll('div.conbench-histplot-rundetails');
    #     rundiv.innerHTMK = "YES I GOT YA!"

    #     console.log(cb_obj)
    # """,
    # )

    # source_mean_over_time.selected.js_on_change(
    #     "indices",
    #     CustomJS(
    #         args=dict(src=source_mean_over_time),
    #         code="""

    #     console.log(cb_obj)

    #     // `cb_obj.indices` contains indices of selected data points in
    #     // source object.

    #     // make sure just one is selected?

    #     console.log(src.data[indices[0]])

    #     var rundiv = querySelectorAll('div.conbench-histplot-rundetails');
    #     rundiv.innerHTMK = "YES I GOT YA!"

    #     // console.log(cb_obj)
    # """,
    #     ),
    # )

    click_on_glyph_callback_show_run_details = CustomJS(
        code="""
        // did not work: document.querySelectorAll();
        const rundiv = document.getElementsByClassName("conbench-histplot-rundetails")[0];

        const i = cb_data.source.selected.indices[0];
        const selected_glyph_run_relurl = cb_data.source.data['relative_benchmark_urls'][i];
        const selected_glyph_run_date = cb_data.source.data['date_strings'][i];

        rundiv.innerHTML = "Selected benchmark: <br />" +

            '<ul><li>Report: <a href="' + selected_glyph_run_relurl + '">here</a></li>' +
            "<li>Time when benchmark was run: " + selected_glyph_run_date + "</li></ul><br />"
    """,
    )

    tap_callback_detect_unselect = CustomJS(
        # Note(JP): When not using `args`, I thought, one can use
        # `cb_data.source.selected.indices` to detect the situation where
        # nothing was selected. However, for such events `cb_data` is an empty
        # object. When using `args={"s1": source_mean_over_time}` then
        # `s1.selected.indices` seems to always be available no matter where
        # one clicks, and in case no glyph was licked the array is zero length.
        args={"s1": source_mean_over_time},
        code="""
        // console.log("cb_data:", cb_data);
        // console.log("cb_obj:", cb_obj);
        console.log("s1.selected.indices: ", s1.selected.indices);

        // if (cb_data && cb_data == {}
        // if (Object.keys(cb_data).length === 0) {
        //    console.log('cb_data is empty, assume nothing was clicked');
        // }

        if (s1.selected.indices.length == 0){
            console.log("nothing selected, remove detail");
            const rundiv = document.getElementsByClassName("conbench-histplot-rundetails")[0];
            rundiv.innerHTML = "";
        }
    """,
    )

    source_current_bm_mean = _source(
        [
            {
                "mean": benchmark["stats"]["mean"],
                "message": run["commit"]["message"],
                "timestamp": run["commit"]["timestamp"],
                "sha": run["commit"]["sha"],
                "benchmark_id": benchmark["id"],
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
                "sha": run["commit"]["sha"],
                "benchmark_id": benchmark["id"],
            }
        ],
        unit,
        formatted=formatted,
    )

    # Note(JP). The `source_rolling_*` data is based on the "distribution"
    # analysis in conbench which I believe is a rolling window analysis where
    # the time width of the window is variable, as of a fixed commit-count
    # width.
    source_rolling_mean_over_time = _source(
        with_dist, unit, formatted=formatted, distribution_mean=True
    )
    source_rolling_alert_min_over_time = _source(
        with_dist, unit, formatted=formatted, alert_min=True
    )
    source_rolling_alert_max_over_time = _source(
        with_dist, unit, formatted=formatted, alert_max=True
    )

    t_start = source_mean_over_time.data["x"][0]
    t_end = source_mean_over_time.data["x"][-1]

    t_range: datetime.timedelta = t_end - t_start

    # Add padding/buffer to left and right so that newest data point does not
    # disappear under right plot boundary, and so that the oldest data point
    # has space from legend.
    t_start = t_start - (0.4 * t_range)
    t_end = t_end + (0.07 * t_range)

    # taptool = TapTool(callback=display_run_callback)

    # url = "http://rofl.com/@run-id"
    # taptool = scatter_mean_over_time.select(type=TapTool)
    # taptool = p.select(type=TapTool)
    # taptool.callback = OpenURL(url=url)

    p = bokeh.plotting.figure(
        x_axis_type="datetime",
        height=height,
        width=width,
        tools=["pan", "zoom_in", "zoom_out", "reset", "tap"],
        x_range=(t_start, t_end),
    )
    p.toolbar.logo = None

    taptool = p.select(type=TapTool)
    taptool.callback = click_on_glyph_callback_show_run_details
    p.js_on_event("tap", tap_callback_detect_unselect)

    # p.js_on_event(
    #     # Not publicly document but seemingly established: 'tap' is not
    #     # just any click event in the plot, but only triggers when clicking
    #     # a glyph:
    #     # https://discourse.bokeh.org/t/how-to-trigger-callbacks-on-mouse-click-for-tap-tool/1630
    #     bokeh.events.Tap,
    #     display_run_callback,
    # )

    p.xaxis.formatter = get_date_format()
    p.xaxis.major_label_orientation = 1
    p.yaxis.axis_label = axis_unit

    multisample, multisample_count = _inspect_for_multisample(history)
    label = "benchmark (n=1)"
    if multisample:
        label = "benchmark mean"
        if multisample_count:
            label += f" (n={multisample_count})"

    scatter_mean_over_time = p.circle(
        source=source_mean_over_time,
        legend_label=label,
        name="history",
        size=4,
        color="#ccc",
    )

    if multisample:
        # Do not show min-over-time when each benchmark reports at most one
        # sample, i.e. when mean and min are the same.

        label = "benchmark min"
        if multisample_count:
            label += f" (n={multisample_count})"

        p.line(
            source=source_min_over_time,
            legend_label=label,
            name="min-over-time",
            color="#222",
        )
        p.circle(
            source=source_min_over_time,
            legend_label=label,
            name="min-over-time",
            size=2,
            color="#222",
        )

    p.line(
        source=source_rolling_mean_over_time,
        color="#ffa600",
        legend_label="rolling window mean",
    )
    p.line(
        source=source_rolling_alert_min_over_time,
        color="Silver",
        legend_label="rolling window mean +/- 5 σ",
        line_join="round",
        width=1,
    )
    p.line(source=source_rolling_alert_max_over_time, color="Silver")

    cur_bench_mean_circle = p.x(
        source=source_current_bm_mean,
        size=18,
        line_width=2.5,
        color="#A65DE7",
        legend_label="current benchmark (mean)" if multisample else "current benchmark",
        name="benchmark",
    )

    if multisample:
        # do not show this for n=1 (then min equals to mean).
        cur_bench_min_circle = p.circle(
            source=source_current_bm_min,
            size=6,
            color="#000",
            legend_label="current benchmark (min)",
            name="benchmark",
        )

    # visually separate out distribution changes
    dist_change_in_legend = False
    for result in history:
        if result["change_annotations"].get("begins_distribution_change", False):
            p.add_layout(
                Span(
                    location=dateutil.parser.isoparse(result["timestamp"]),
                    dimension="height",
                    line_color="purple",
                    line_dash="dashed",
                    line_alpha=0.5,
                )
            )

            if not dist_change_in_legend:
                # hack: add a dummy line so it appears on the legend
                p.line(
                    [dateutil.parser.isoparse(result["timestamp"])] * 2,
                    [result["mean"]] * 2,
                    legend_label="distribution change",
                    line_color="purple",
                    line_dash="dashed",
                    line_alpha=0.5,
                )
                dist_change_in_legend = True

    hover_renderers = [
        scatter_mean_over_time,
        cur_bench_mean_circle,
    ]

    if multisample:
        hover_renderers.append(cur_bench_min_circle)

    p.add_tools(
        bokeh.models.HoverTool(
            tooltips=[
                ("date", "$x{%F}"),
                # Note(JP): this is where the `means` name becomes special,
                # I think.
                ("mean", "@means"),
                ("commit", "@commit_hashes_short"),
                ("commit msg", "@commit_messages"),
            ],
            formatters={"$x": "datetime"},
            renderers=hover_renderers,
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

    return bokeh.layouts.column(p, Spacer(height=20), select, Spacer(height=20))
