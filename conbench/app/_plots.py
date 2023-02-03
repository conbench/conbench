import collections
import json
import logging
from typing import List, Optional, no_type_check

import bokeh.events
import bokeh.models
import bokeh.plotting

from conbench import util

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


def _insert_nans(some_list: list, indexes: List[int]):
    """Insert nans into a list before the given indexes."""
    for ix in sorted(indexes, reverse=True):
        some_list.insert(ix, float("nan"))
    return some_list


@no_type_check
def _source(
    data,
    unit,
    formatted=False,
    distribution_mean=False,
    alert_min=False,
    alert_max=False,
    break_line_indexes: Optional[List[int]] = None,
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

    # The `timestamp` property corresponds to the UTC-local commit time
    # (example value: 2022-03-03T19:48:06). That is, each string is ISO 8601
    # notation w/o timezone information. Transform those into tz-aware datetime
    # objects.
    datetimes = util.tznaive_iso8601_to_tzaware_dt([x["timestamp"] for x in data])

    # Get stringified versions of those datetimes for UI display purposes.
    # Include timezone information. This shows UTC for the %Z.
    date_strings = [d.strftime("%Y-%m-%d %H:%M %Z") for d in datetimes]

    points, values_with_unit = [], []

    if alert_min:
        for x in data:
            alert = 5 * float(x["distribution_stdev"])
            points.append(float(x["distribution_mean"]) - alert)
            values_with_unit.append(unit_fmt(points[-1], unit))

    elif alert_max:
        for x in data:
            alert = 5 * float(x["distribution_stdev"])
            points.append(float(x["distribution_mean"]) + alert)
            values_with_unit.append(unit_fmt(points[-1], unit))

    else:
        points = [x[key] for x in data]

        # Note(JP): If `means` is just string-formatted `points` then this is
        # kind of acknowledging that `points` is always a collection of mean
        # values. It seems that this is a string value field that is only
        # ever used for tooltip generation?
        values_with_unit = [unit_fmt(float(x[key]), unit) for x in data if x[key]]

    if formatted:
        # Note(JP): why would we want to calculate the raw numeric data from
        # the tooltip string labels?
        points = [x.split(" ")[0] for x in values_with_unit]

    dsdict = {
        "x": datetimes,
        # Note(JP): maybe rename `points` into `y_values_for_plotting`
        "y": points,
        # List of human-readable date strings, corresponding to
        # the `datetimes` objects for the time axis
        "date_strings": date_strings,
        # List of (truncated) commit messages.
        "commit_messages": commit_messages,
        # List of short commit hashes with hashtag prefix
        "commit_hashes_short": ["#" + d["sha"][:8] for d in data],
        "relative_benchmark_urls": [f'/benchmarks/{d["benchmark_id"]}' for d in data],
        # Stringified values (truncated, with unit)
        "values_with_unit": values_with_unit,
    }

    multisample, multisample_count = _inspect_for_multisample(data)
    if multisample:
        # Add a column to the ColumnarDataSource: stringified individual
        # samples (with units).
        strings = []
        for d in data:
            samples = d["data"]
            strings.append(", ".join(unit_fmt(s, unit) for s in samples))

        dsdict["multisample_strings_with_unit"] = strings

    if break_line_indexes:
        # This source will be used for a line, and we want to "break" the line between
        # the given indexes and the immediately previous data points. Do this by
        # inserting nans.
        # https://docs.bokeh.org/en/3.0.3/docs/user_guide/basic/lines.html#missing-points
        for key in dsdict:
            dsdict[key] = _insert_nans(dsdict[key], break_line_indexes)

    return bokeh.models.ColumnDataSource(data=dsdict)


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
    try:
        samplecounts = [len(i["data"]) for i in items]
    except KeyError:
        # TODO: clean up once type checking is tight enough.
        # Likely, the provided `items` for testing here are not strictly of the
        # required shape. It's a programming bug, but do not crash in this
        # case. Return an answer: not multisample (at least not in the way as
        # expected).
        log.warning("_inspect_for_multisample: unexpected argument: %s", items)
        return False, None

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


def gen_js_callback_tap_detect_unselect(source: bokeh.models.ColumnDataSource):
    """
    Dynamically manipulate Bootstrap panel conbench-histplot-run-details`.

    Hide if empty space in plot was clicked.

    Warning: requires manual testing, not covered by tests/CI.
    """
    return bokeh.models.CustomJS(
        # Note(JP): When not using `args`, I thought, one can use
        # `cb_data.source.selected.indices` to detect the situation where
        # nothing was selected. However, for such events `cb_data` is an empty
        # object. When using `args={"s1": source_mean_over_time}` then
        # `s1.selected.indices` seems to always be available no matter where
        # one clicks, and in case no glyph was clicked the array is zero
        # length.
        args={"s1": source},
        code="""
        // console.log("cb_data:", cb_data);
        // console.log("cb_obj:", cb_obj);
        // console.log("s1.selected.indices: ", s1.selected.indices);

        if (s1.selected.indices.length == 0) {
            console.log("nothing selected, remove detail");
            // Make the panel invisible.
            const e = document.getElementsByClassName("conbench-histplot-run-details")[0];
            e.style.display = 'none';
        }
    """,
    )


def gen_js_callback_click_on_glyph_show_run_details(repo_string):
    """
    Dynamically manipulate Bootstrap panel conbench-histplot-run-details`.

    Show run details if a corresponding glyph was clicked in the plot.

    Warning: requires manual testing, not covered by tests/CI.
    """
    return bokeh.models.CustomJS(
        code=f"""

        const i = cb_data.source.selected.indices[0];
        const run_report_relurl = cb_data.source.data['relative_benchmark_urls'][i];
        const run_date_string = cb_data.source.data['date_strings'][i];
        // Remove first character, the hashtag
        const run_commit_hash_short = cb_data.source.data['commit_hashes_short'][i].substring(1);
        const run_commit_msg_pfx = cb_data.source.data['commit_messages'][i];
        // This is a stringified version of the value that determines the y
        // plot position of this glyph.
        const run_result_value_with_unit = cb_data.source.data['values_with_unit'][i];

        var run_samples_with_units = undefined;

        if (cb_data.source.data['multisample_strings_with_unit'] !== undefined) {{
            run_samples_with_units = cb_data.source.data['multisample_strings_with_unit'][i];
        }}

        // JavaScript code generated in a Python f string -- templating hell, yeah! :)
        // I don't know if repo string is always a URL, if it's always
        // pointing to GitHub. But if it does, we can do some UX sugar.
        // Austin says that repo string should as of today be either None or
        // a URL to the GitHub repo. We will see what future needs will bring.

        var commit_repo_string =  run_commit_hash_short + ' in {repo_string}';

        const repo = '{repo_string}';
        if (repo.startsWith('https://github.com/')) {{
            // for github at least this is known to work with a truncated hash
            const url_to_commit = repo + '/commit/' + run_commit_hash_short;
            commit_repo_string = '<a href="' + url_to_commit + '">' + url_to_commit + '</a>';
        }}

        // TODO? show run timestamp, not only commit timestamp.
        var newHtml = \
            '<li>Report: <a href="' + run_report_relurl + '">' + run_report_relurl + '</a></li>' +
            '<li>Commit: ' + commit_repo_string + '</li>' +
            '<li>Commit message (truncated): ' + run_commit_msg_pfx + '</li>' +
            "<li>Commit timestamp: " + run_date_string + "</li>" +
            "<li>Result value: " + run_result_value_with_unit + "</li>";


        if (run_samples_with_units) {{
            newHtml += "<li>Result samples: " + run_samples_with_units + "</li>";
        }}

        const ul = document.getElementsByClassName("ul-histplot-run-details")[0];
        ul.innerHTML = newHtml;

        // Make the panel visible.
        const e = document.getElementsByClassName("conbench-histplot-run-details")[0];
        e.style.display = 'block'
    """,
    )


def time_series_plot(history, benchmark, run, height=380, width=1100):
    # log.info("Time series plot for:\n%s", json.dumps(history, indent=2))

    unit = history[0]["unit"]
    with_dist = [h for h in history if h["distribution_mean"]]
    formatted, axis_unit = _should_format(history, unit)
    dist_change_indexes = [
        ix for ix, result in enumerate(history) if result["begins_distribution_change"]
    ]

    # Note(JP): `history` is an ordered list of dicts, each dict has a `mean`
    # key which is extracted here by default.
    source_mean_over_time = _source(history, unit, formatted=formatted)

    source_min_over_time = bokeh.models.ColumnDataSource(
        data=dict(
            # Insert NaNs to break the line at distribution changes
            x=_insert_nans(
                util.tznaive_iso8601_to_tzaware_dt([x["timestamp"] for x in history]),
                dist_change_indexes,
            ),
            # TODO: best-case is not always min, e.g. when data has a unit like
            # bandwidth.
            y=_insert_nans([min(x["data"]) for x in history], dist_change_indexes),
        )
    )

    source_current_bm_mean = _source(
        [
            {
                "mean": benchmark["stats"]["mean"],
                "message": run["commit"]["message"],
                "timestamp": run["commit"]["timestamp"],
                "sha": run["commit"]["sha"],
                "benchmark_id": benchmark["id"],
                "repository": run["commit"]["repository"],
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
                "repository": run["commit"]["repository"],
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
        with_dist,
        unit,
        formatted=formatted,
        distribution_mean=True,
        break_line_indexes=dist_change_indexes,
    )
    source_rolling_alert_min_over_time = _source(
        with_dist,
        unit,
        formatted=formatted,
        alert_min=True,
        break_line_indexes=dist_change_indexes,
    )
    source_rolling_alert_max_over_time = _source(
        with_dist,
        unit,
        formatted=formatted,
        alert_max=True,
        break_line_indexes=dist_change_indexes,
    )

    t_start = source_mean_over_time.data["x"][0]
    t_end = source_mean_over_time.data["x"][-1]

    t_range = t_end - t_start

    # Add padding/buffer to left and right so that newest data point does not
    # disappear under right plot boundary, and so that the oldest data point
    # has space from legend.
    t_start = t_start - (0.4 * t_range)
    t_end = t_end + (0.07 * t_range)

    p = bokeh.plotting.figure(
        x_axis_type="datetime",
        height=height,
        width=width,
        tools=[
            # Allows for dragging the field of view, default drag action.
            "pan",
            # Allow for resetting the plot to original view.
            "reset",
            # This allows for benchmark-details-on-datapoint-click
            "tap",
            # Zoom in and out with mouse wheel, default wheel action
            "wheel_zoom",
            # Allow for drawing a box for zooming.
            "box_zoom",
        ],
        # Bokeh toolbars can have at most one active tool from each kind of
        # gesture (drag, scroll, tap).
        # https://docs.bokeh.org/en/2.4.0/docs/user_guide/tools.html#setting-the-active-tools
        # Enable box zoom by default, disable the "pan" tool by default. Via
        # clicking icons on the toolbar one can toggle manually between pan and
        # box-zoom. As of today we believe that box_zoom&wheel_zoom is a good
        # default combo to have.
        active_drag="box_zoom",
        active_scroll="wheel_zoom",
        active_tap="tap",
        active_inspect="auto",  # this enables hover by default (tool added below)
        toolbar_location="right",
        x_range=(t_start, t_end),
    )
    p.toolbar.logo = None

    # TapTool is not responding to each click event, but but only triggers when
    # clicking a glyph:
    # https://discourse.bokeh.org/t/how-to-trigger-callbacks-on-mouse-click-for-tap-tool/1630
    taptool = p.select(type=bokeh.models.TapTool)
    taptool.callback = gen_js_callback_click_on_glyph_show_run_details(
        # The repository is constant across all data points in this plot. The
        # underlying database query filters by exactly that (Commit.repository
        # == repo).
        repo_string=run["commit"]["repository"]
    )

    # `tap` event triggers for each click. Whether or not this was on a glyph
    # of a specific data source this can be decided in the callback when
    # passing a data source to the callback and then inspecting
    # `s1.selected.indices`.
    p.js_on_event("tap", gen_js_callback_tap_detect_unselect(source_mean_over_time))

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
        size=6,
        color="#ccc",
        line_width=1,
        selection_color="#76bf5a",  # like bootstrap panel dff0d8, but darker
        selection_line_color="#5da540",  # same green, again darker
        # Cannot change the size upon selection
        # selection_size=10,
        nonselection_fill_alpha=1.0,
        nonselection_line_alpha=1.0,
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

    # further visually separate out distribution changes with a vertical line
    dist_change_in_legend = False
    for ix in dist_change_indexes:
        p.add_layout(
            bokeh.models.Span(
                location=util.tznaive_iso8601_to_tzaware_dt(history[ix]["timestamp"]),
                dimension="height",
                line_color="purple",
                line_dash="dashed",
                line_alpha=0.5,
            )
        )

        if not dist_change_in_legend:
            # hack: add a dummy line so it appears on the legend
            p.line(
                [util.tznaive_iso8601_to_tzaware_dt(history[ix]["timestamp"])] * 2,
                [history[ix]["mean"]] * 2,
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
                ("value", "@values_with_unit"),
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

    return bokeh.layouts.column(p, bokeh.models.Spacer(height=5))
