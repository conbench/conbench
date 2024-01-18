import collections
import json
import logging
import math
from typing import Dict, List, Literal, Optional, Tuple, no_type_check

import bokeh.events
import bokeh.models
import bokeh.plotting

import conbench.units
from conbench import util
from conbench.api.history import get_history_for_benchmark
from conbench.entities.benchmark_result import BenchmarkResult
from conbench.entities.history import HistorySample, HistorySampleZscoreStats
from conbench.numstr import numstr
from conbench.types import TBenchmarkName

from ..hacks import sorted_data
from .types import BokehPlotJSONOrError, HighlightInHistPlot

log = logging.getLogger(__name__)


class HistoryUserFacingError(Exception):
    """
    Raise this while building a benchmark result history. The resulting error
    is meant to be user-facing and shown to the user in the UI or in the HTTP
    API.

    There are a number of aspects that may look 'wrong' while building history.
    I believe that, fundamentally, not all aspects can be caught during
    benchmark result submission. Quite a bit of validation can (should) be
    performed during assembly of history.

    It's an interesting question whether bad-looking items in the history
    should silently be left out (e.g., a mismatching unit) or if the history
    assembly should then fail. With the ability to mutate and delete individual
    benchmark results, I think we should err towards strictness and generate
    nice and precise errors.
    """


class TimeSeriesPlotMixin:
    def get_biggest_changes(self, benchmarks):
        benchmarks_by_id = {b["id"]: b for b in benchmarks}

        # top 3 regressions or improvements
        biggest_changes = sorted(
            [
                (abs(float(b["stats"]["z_score"])), b["id"])
                for b in benchmarks
                if b["stats"].get("z_regression") or b["stats"].get("z_improvement")
            ],
            reverse=True,
        )[:3]

        biggest_changes = [benchmarks_by_id[o[1]] for o in biggest_changes]
        biggest_changes_ids = [b["id"] for b in biggest_changes]
        # Note(JP): TODO: it appears that this is not covered by the test suite
        biggest_changes_names = [
            f'{b["display_bmname"]}, {b["display_case_perm"]}' for b in biggest_changes
        ]
        return biggest_changes, biggest_changes_ids, biggest_changes_names

    def get_history_plot(
        self,
        current_benchmark_result: BenchmarkResult,
        run,
        plot_index_for_html=0,
        highlight_other_result: Optional[HighlightInHistPlot] = None,
    ) -> BokehPlotJSONOrError:
        """
        Generate JSON string for inclusion in HTML doc or a reason for why the
        plot-describing JSON doc was not generated.

        `current_benchmark_result`: the result to generate the history plot
        for. If there is history and if after all a plot is generated, then
        _this_ result will be labeled as "current result" in the plot, and it
        will be the newest one in the plot (right-most on time axis).

        `run`: TODO
        """
        samples = get_history_for_benchmark(
            benchmark_result_id=current_benchmark_result.id
        )

        # Does `samples` include the current benchmark result? Interesting: the
        # current benchmark result may be failed, but I think all items in
        # samples (historical benchmark results are guaranteed to not be
        # failed.

        # The number (1, 2, 3?) maybe needs to be tuned further. Also see
        # https://github.com/conbench/conbench/issues/867
        if len(samples) < 3:
            # This reason/error will be shown verbatim in HTML, so this should be
            # a nice message.
            return BokehPlotJSONOrError(
                None,
                f"not enough history items yet ({len(samples)}). Keep submitting "
                "results for this specific benchmark scenario (case permutation, "
                "and context)!",
            )

        highlight_other: Optional[Tuple[HistorySample, str]] = None

        if highlight_other_result is not None:
            s_by_id: Dict[str, HistorySample] = {
                s.benchmark_result_id: s for s in samples
            }

            if highlight_other_result.bmrid not in s_by_id:
                return BokehPlotJSONOrError(
                    None,
                    "you asked to highlight the benchmark result with ID "
                    f"<kbd>{highlight_other_result.bmrid}</kbd> in this view. "
                    "However, that result is not part of the history of the "
                    f"result <kbd>{current_benchmark_result.id}</kbd>. The "
                    "two results are not directly comparable.",
                )
            highlight_other = (
                s_by_id[highlight_other_result.bmrid],
                highlight_other_result.highlight_name,
            )

        assert isinstance(samples[0], HistorySample)
        jsondoc = json.dumps(
            bokeh.embed.json_item(
                time_series_plot(
                    samples=samples,
                    current_benchmark_result=current_benchmark_result,
                    run=run,
                    highlight_result_in_hist=highlight_other,
                ),
                f"plot-history-{plot_index_for_html}",  # type: ignore
            )
        )
        return BokehPlotJSONOrError(jsondoc, None)


def fmt_number_and_unit(value: float, unit: str):
    """
    Use this for on-hover data point display, so that it shows with unit.
    """
    return f"{numstr(value, sigfigs=5)} {unit}"


def fmt_number_for_bokeh_plot(value: float):
    """
    Use this for the Bokeh data source, cut unnecessary precision.
    """
    return numstr(value, sigfigs=8)


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


def simple_bar_plot(benchmarks, height=400, width=400, vbar_width=0.7):
    def _simple_source(data, unit):
        """
        We really need to rebuild this function. It's so cryptic. Moving this
        into simple_bar_plot() because that seems to be the only consumer.
        """
        cases, points, means = [], [], []
        points_formated, units_formatted = [], set()

        for *values, point in data:
            cases.append(values)
            points.append(point)
            formatted = fmt_number_and_unit(float(point), unit)
            means.append(formatted)
            formated_point, formatted_unit = formatted.split(" ", 1)
            points_formated.append(formated_point)
            units_formatted.add(formatted_unit)

        unit_formatted = units_formatted.pop() if len(units_formatted) == 1 else None
        if unit_formatted:
            points = points_formated

        axis_unit = unit_formatted if unit_formatted is not None else unit
        # if axis_unit == unit:
        #     axis_unit = get_display_unit(unit)

        # remove redundant tags from labels
        len_cases = len(cases)
        counts = collections.Counter([tag for case in cases for tag in case])
        stripped = [[tag for tag in case if counts[tag] != len_cases] for case in cases]
        cases = ["-".join(tags) for tags in stripped]

        source_data = dict(x=cases, y=points, means=means)
        return bokeh.models.ColumnDataSource(data=source_data), axis_unit

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


def _insert_nans(some_list: list, indexes: List[int]):
    """Insert nans into a list before the given indexes."""
    for ix in sorted(indexes, reverse=True):
        some_list.insert(ix, float("nan"))
    return some_list


def _truncate_commit_msg(msg: str) -> str:
    """
    Conditionally truncate commit msg.

    Note: I think we might have similar code elsewhere, ideally reconcile.
    """
    if len(msg) > 77:
        return msg[:75] + ".."

    return msg


@no_type_check
def _source(
    samples: List[HistorySample],
    unit,
    y_value_strategy: Literal[
        "svs", "all_data", "rolling_mean", "alert_min", "alert_max"
    ],
    break_line_indexes: Optional[List[int]] = None,
    reference_benchmark_result: Optional[BenchmarkResult] = None,
):
    """
    data_strategy: The way to extract the y-axis value(s) from each HistorySample.
        svs: Plot the sample's single-value summary.
        all_data: Plot all raw data points from the sample.
        rolling_mean: Plot the mean of the baseline distribution ending with the parent
            commit.
        alert_min: Plot the value that's 5 z-scores below the rolling_mean.
        alert_max: Plot the value that's 5 z-scores above the rolling_mean.
    """

    def x_axis_generator():
        """Yield a HistorySample for each intended data point."""
        if y_value_strategy == "all_data":
            # This strategy returns multiple points per sample.
            for s in samples:
                for _ in s.data:
                    yield s
        else:
            for s in samples:
                yield s

    # These commit message prefixes end up (among others) in the on-hover
    # tooltip in the history plot.
    commit_messages = [_truncate_commit_msg(s.commit_msg) for s in x_axis_generator()]

    # The `timestamp` property corresponds to the UTC-local commit time
    # (example value: 2022-03-03T19:48:06). That is, each string is ISO 8601
    # notation w/o timezone information. Transform those into tz-aware datetime
    # objects.
    #
    # Note that we do too much forth and back here; define `commit_timestamp`
    # properly on `HistorySample`  (to be tzaware and in UTC), then we can
    # simplify.
    datetimes = util.tznaive_iso8601_to_tzaware_dt(
        [s.commit_timestamp.isoformat() for s in x_axis_generator()]
    )

    # Get stringified versions of those datetimes for UI display purposes.
    # Include timezone information. This shows UTC for the %Z.
    date_strings = [d.strftime("%Y-%m-%d %H:%M %Z") for d in datetimes]

    values_to_plot: List[float] = []

    if y_value_strategy == "alert_min":
        # for 'lower boundary' vis, has its own problems. also see
        # https://github.com/conbench/conbench/issues/1252
        for s in samples:
            alert = 5 * float(s.zscorestats.rolling_stddev)
            values_to_plot.append(float(s.zscorestats.rolling_mean) - alert)

    elif y_value_strategy == "alert_max":
        for s in samples:
            alert = 5 * float(s.zscorestats.rolling_stddev)
            values_to_plot.append(float(s.zscorestats.rolling_mean) + alert)

    elif y_value_strategy == "rolling_mean":
        values_to_plot = [s.zscorestats.rolling_mean for s in samples]

    elif y_value_strategy == "svs":
        values_to_plot = [s.svs for s in samples]

    elif y_value_strategy == "all_data":
        values_to_plot = [d for s in samples for d in s.data]

    else:
        raise ValueError(f"bad {y_value_strategy=}")

    values_with_unit: List[str] = [fmt_number_and_unit(x, unit) for x in values_to_plot]

    # This structure is after all available in a JavaScript hook, search for
    # cb_data.source.data.
    dsdict = {
        "x": datetimes,
        # Note(JP): maybe rename `points` into `y_values_for_plotting`
        "y": values_to_plot,
        # List of human-readable date strings, corresponding to
        # the `datetimes` objects for the time axis
        "date_strings": date_strings,
        # List of (truncated) commit messages.
        "commit_messages": commit_messages,
        # List of short commit hashes with hashtag prefix
        "commit_hashes_short": ["#" + s.commit_hash[:8] for s in x_axis_generator()],
        "relative_benchmark_urls": [
            f"/benchmark-results/{s.benchmark_result_id}" for s in x_axis_generator()
        ],
        # Stringified values (truncated, with unit, for on-hover)
        "values_with_unit": values_with_unit,
        # Explicit structure for hover
        "commit_msgs_for_hover": commit_messages,
    }

    if reference_benchmark_result:
        dsdict["rel_resresrmp_urls"] = [
            f"/compare/benchmark-results/{reference_benchmark_result.id}...{s.benchmark_result_id}"
            for s in x_axis_generator()
        ]

    multisample, _ = _inspect_for_multisample(samples)
    if multisample:
        # multisample means: more than data point/iteration. Add a column to
        # the ColumnarDataSource: stringified individual samples (with units).
        strings = []
        # Note(JP): here it becomes obvious that we may need better naming to
        # distinguish samples from samples :-). In the next line, `samples` is
        # a list of entities that each may contain more than one per-iteration
        # sample.
        for s in x_axis_generator():
            # Terminology: subsample? itersample? rawsample?
            subsamples = s.data
            strings.append(
                ", ".join(fmt_number_and_unit(ss, unit) for ss in subsamples)
            )

        dsdict["multisample_strings_with_unit"] = strings

    if break_line_indexes:
        # This source will be used for a line, and we want to "break" the line between
        # the given indexes and the immediately previous data points. Do this by
        # inserting nans.
        # https://docs.bokeh.org/en/3.0.3/docs/user_guide/basic/lines.html#missing-points
        for key in dsdict:
            dsdict[key] = _insert_nans(dsdict[key], break_line_indexes)

    return bokeh.models.ColumnDataSource(data=dsdict)


def _inspect_for_multisample(items: List[HistorySample]) -> Tuple[bool, Optional[int]]:
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
        samplecounts = [len(i.data) for i in items]
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


def gen_js_callback_click_on_glyph_show_run_details(repo_url):
    """
    Dynamically manipulate Bootstrap panel conbench-histplot-run-details`.

    Show run details if a corresponding glyph was clicked in the plot.

    Warning: requires manual testing, not covered by tests/CI.

    `repo_url` really is expected to be a URL.
    """
    return bokeh.models.CustomJS(
        code=f"""

        const i = cb_data.source.selected.indices[0];
        const url_bmr = cb_data.source.data['relative_benchmark_urls'][i];

        var url_resrescmp = "#";
        var url_resrescmp_title = "n/a";

        if (cb_data.source.data['rel_resresrmp_urls'] !== undefined) {{
            url_resrescmp = cb_data.source.data['rel_resresrmp_urls'][i];
            url_resrescmp_title = "compare"
        }}

        //const url_resrescmp =
        //const url_resrescmp = "foo";
        console.log(url_resrescmp);

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

        var commit_repo_url =  run_commit_hash_short + ' in {repo_url}';

        const repo = '{repo_url}';
        if (repo.startsWith('https://github.com/')) {{
            // for github at least this is known to work with a truncated hash
            const url_to_commit = repo + '/commit/' + run_commit_hash_short;
            commit_repo_url = '<a href="' + url_to_commit + '">' + url_to_commit + '</a>';
        }}

        // TODO? show run timestamp, not only commit timestamp.
        var newHtml = \
            '<li>Result view: <a href="' + url_bmr + '">' + url_bmr + '</a></li>' +
            '<li>Compare view (current and selected result):  <a href="' + url_resrescmp + '">' + url_resrescmp_title + '</a>' + "</li>" +
            '<li>Commit: ' + commit_repo_url + '</li>' +
            '<li>Commit message (truncated): ' + run_commit_msg_pfx + '</li>' +
            "<li>Commit timestamp: " + run_date_string + "</li>" +
            "<li>Result mean: " + run_result_value_with_unit + "</li>";


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


def time_series_plot(
    samples: List[HistorySample],
    current_benchmark_result: BenchmarkResult,
    run,
    height=420,
    width=800,
    highlight_result_in_hist: Optional[Tuple[HistorySample, str]] = None,
):
    """
    The `run` argument's purpose is unclear, document or remove.
    """
    # log.info(
    #     "Time series plot for:\n%s",
    #     json.dumps([s._dict_for_api_json() for s in samples], indent=2, default=str),
    # )

    units = set([s.unit for s in samples])
    if len(units) != 1:
        raise HistoryUserFacingError(f"heterogenous set of units: {units}")

    # The unit string for the axis label may be different (longer, for example)
    unit_symbol = conbench.units.legacy_convert(units.pop())
    unit_str_for_plot_axis_label = conbench.units.longform(unit_symbol)

    samples_with_z_score_analysis = [s for s in samples if s.zscorestats.rolling_mean]
    inliers = [s for s in samples if not s.zscorestats.is_outlier]
    outliers = [s for s in samples if s.zscorestats.is_outlier]

    has_outliers = len(outliers) > 0

    # formatted,  = _should_format([s.svs for s in samples], unit)
    # log.info("formatted: %s, axis_unit: %s", formatted, axis_unit)

    dist_change_indexes = [
        ix
        for ix, sample in enumerate(samples_with_z_score_analysis)
        if sample.zscorestats.begins_distribution_change
    ]

    # Note(JP): `samples` is an ordered list of dicts, each dict has a `mean`
    # key which is extracted here by default.
    source_raw_data = _source(samples, unit_symbol, "all_data")
    source_svs_inliers = _source(inliers, unit_symbol, "svs")
    source_svs_outliers = _source(outliers, unit_symbol, "svs")
    source_svs_all = _source(
        samples, unit_symbol, "svs", reference_benchmark_result=current_benchmark_result
    )

    # Note(JP). The `source_rolling_*` data is based on the "distribution"
    # analysis in conbench which I believe is a rolling window analysis where
    # the time width of the window is variable, as of a fixed commit-count
    # width.
    source_rolling_mean_over_time = _source(
        samples_with_z_score_analysis,
        unit_symbol,
        "rolling_mean",
        break_line_indexes=dist_change_indexes,
    )
    source_rolling_alert_min_over_time = _source(
        samples_with_z_score_analysis,
        unit_symbol,
        "alert_min",
        break_line_indexes=dist_change_indexes,
    )
    source_rolling_alert_max_over_time = _source(
        samples_with_z_score_analysis,
        unit_symbol,
        "alert_max",
        break_line_indexes=dist_change_indexes,
    )

    t_start = source_svs_all.data["x"][0]
    t_end = source_svs_all.data["x"][-1]

    t_range = t_end - t_start

    # Add explicit padding/buffer to left and right so that newest data point
    # does not disappear under right plot boundary, and so that the oldest data
    # point has space from legend.
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

    # Use a built-in method for taking influence on the y-axis/ordinate range,
    # just don't zoom in as much as bokeh usually would. For now, we don't show
    # the zero, and that might be fine so that one can focus on the acutal
    # change happening (losing perspective if that change matters or not :-)
    # but yeah that's what stock markets also do ¯\_(ツ)_/¯).
    p.y_range.range_padding = 0.5  # type: ignore[attr-defined]
    p.toolbar.logo = None  # type: ignore[attr-defined]

    # TapTool is not responding to each click event, but but only triggers when
    # clicking a glyph:
    # https://discourse.bokeh.org/t/how-to-trigger-callbacks-on-mouse-click-for-tap-tool/1630
    taptool = p.select(type=bokeh.models.TapTool)
    taptool.callback = gen_js_callback_click_on_glyph_show_run_details(
        # The repository is constant across all data points in this plot.
        repo_url=current_benchmark_result.commit_repo_url
    )

    # `tap` event triggers for each click. Whether or not this was on a glyph
    # of a specific data source this can be decided in the callback when
    # passing a data source to the callback and then inspecting
    # `s1.selected.indices`.
    p.js_on_event("tap", gen_js_callback_tap_detect_unselect(source_svs_all))

    p.xaxis.formatter = get_date_format()
    p.xaxis.major_label_orientation = 1
    p.yaxis.axis_label = unit_str_for_plot_axis_label
    p.xaxis.axis_label = ""

    multisample, multisample_count = _inspect_for_multisample(samples)
    if not multisample:
        n_label = "(n=1)"
        svs_type = ""
    elif multisample_count:
        n_label = f"(n={multisample_count})"
        svs_type = f"({current_benchmark_result.svs_type})"
    else:
        # mixed number of repetitions per result
        n_label = ""
        svs_type = f"({current_benchmark_result.svs_type})"

    # Raw results, only if multisample
    if multisample:
        p.circle(
            source=source_raw_data,
            legend_label=f"result repetitions {n_label}",
            name="raw",
            size=3,
            color="#ccc",
        )

    # Inlier SVS
    scatter_inliers = p.circle(
        source=source_svs_inliers,
        legend_label=f"result {svs_type}",
        name="inliers",
        size=3,
        color="#222",
        line_width=1,
        selection_color="#76bf5a",  # like bootstrap panel dff0d8, but darker
        selection_line_color="#5da540",  # same green, again darker
        # Cannot change the size upon selection
        # selection_size=10,
        nonselection_fill_alpha=1.0,
        nonselection_line_alpha=1.0,
    )

    # Outlier SVS
    if has_outliers:
        scatter_outliers = p.circle(
            source=source_svs_outliers,
            legend_label=f"outlier result {svs_type}",
            name="outliers",
            size=3,
            line_color="#ccc",
            fill_color="white",
            line_width=1,
            selection_color="#76bf5a",  # like bootstrap panel dff0d8, but darker
            selection_line_color="#5da540",  # same green, again darker
            # Cannot change the size upon selection
            # selection_size=10,
            nonselection_fill_alpha=1.0,
            nonselection_line_alpha=1.0,
        )

    p.line(
        source=source_rolling_mean_over_time,
        color="#ffa600",
        line_width=2,
        legend_label="lookback z-score (mean)",
    )
    p.line(
        source=source_rolling_alert_min_over_time,
        color="Silver",
        legend_label="lookback z-score leeway",
        line_join="round",
        width=1,
    )
    p.line(source=source_rolling_alert_max_over_time, color="Silver")

    (
        source_current_bm_svs,
        source_current_bm_raw,
    ) = get_source_for_single_benchmark_result(
        current_benchmark_result, run, unit_symbol
    )

    if highlight_result_in_hist is not None:
        hs = highlight_result_in_hist[0]
        description = highlight_result_in_hist[1]
        bokeh_ds_highlight_result = bokeh.models.ColumnDataSource(
            data={
                "x": [hs.commit_timestamp],
                "y": [hs.svs],
            }
        )

        p.x(
            source=bokeh_ds_highlight_result,
            size=19,
            line_width=2.5,
            color="#005050",  # VD magenta
            legend_label=f"highlighted result:\n{description} {svs_type}",
            name="additionally highlighted benchmark result",
        )

    cur_bench_mean_circle = None
    cur_bench_min_circle = None
    if source_current_bm_svs is not None:
        cur_bench_mean_circle = p.x(
            source=source_current_bm_svs,
            size=20,
            line_width=2.7,
            color="#C440C3",  # VD dark magenta
            legend_label=f"current result {svs_type}",
            name="result",
        )

        if multisample:
            # do not show this for n=1 (then min equals to mean).
            cur_bench_min_circle = p.circle(
                source=source_current_bm_raw,
                size=4,
                color="#C440C3",
                legend_label=f"current result repetitions {n_label}",
                name="result",
            )

    # further visually separate out distribution changes with a vertical line
    dist_change_in_legend = False
    for ix in dist_change_indexes:
        p.add_layout(
            bokeh.models.Span(  # type: ignore[attr-defined]
                location=util.tznaive_iso8601_to_tzaware_dt(
                    # transforming from datetime to string back to datetime is
                    # weird; done as part of refactoring to not change too much
                    # at the same time.
                    samples[ix].commit_timestamp.isoformat()
                ),
                dimension="height",
                line_color="purple",
                line_dash="dashed",
                line_alpha=0.5,
            )
        )

        if not dist_change_in_legend:
            # hack: add a dummy line so it appears on the legend
            p.line(
                [
                    util.tznaive_iso8601_to_tzaware_dt(
                        samples[ix].commit_timestamp.isoformat()
                    )
                ]
                * 2,
                [samples[ix].mean] * 2,
                legend_label="distribution change",
                line_color="purple",
                line_dash="dashed",
                line_alpha=0.5,
            )
            dist_change_in_legend = True

    hover_renderers = [scatter_inliers]

    if cur_bench_mean_circle is not None:
        hover_renderers.append(cur_bench_mean_circle)

    if cur_bench_min_circle is not None:
        hover_renderers.append(cur_bench_min_circle)

    if has_outliers:
        hover_renderers.append(scatter_outliers)

    p.add_tools(
        bokeh.models.HoverTool(
            tooltips=[
                ("commit date", "$x{%F}"),
                ("value", "@values_with_unit"),
                ("commit msg", "@commit_msgs_for_hover"),
            ],
            formatters={"$x": "datetime"},
            renderers=hover_renderers,
        )
    )

    p.legend.title_text_color = "darkgray"
    p.legend.title = f"number of results: {len(samples)}"
    p.legend.location = "top_left"
    p.legend.label_text_font_size = "12px"

    # y range should not go into the negative, but it should also not
    # always start at 0. Inspect `source_rolling_alert_min_over_time` which
    # should conceptually hold the minimal value across all sources.
    if min(source_rolling_alert_min_over_time.data["y"]) < 0:
        p.y_range.start = 0  # type: ignore

    # Change the number of expected/desired date x ticks. There is otherwise
    # only very few of them (like 4). Also see
    # https://github.com/bokeh/bokeh/issues/665 and
    # https://github.com/bokeh/bokeh/pull/2186
    p.xaxis.ticker.desired_num_ticks = 9

    return bokeh.layouts.column(p, bokeh.models.Spacer(height=5))

    # The _source() function requires as first arg a list of HistorySample
    # objects. Comply with this, but most of the info is ignored. We may want
    # to add a new type for stream-lining this.


def get_source_for_single_benchmark_result(current_benchmark_result, cur_run, unit):
    # Use the commit timestamp for the x-axis, unless it doesn't exist, in which case
    # use the benchmark result timestamp.

    # Edge case: the result may be failed, in which case we do not show a data point
    # (for now).

    # TODO: `cur_run` is an untyped dict. `cur_run` I think is here only to
    # communicate commit information. Once commit information is stores more
    # clearly on the benchmark result object we can remove the `cur_run`
    # argument and have type checking find potential bugs.

    if current_benchmark_result.is_failed:
        return None, None

    if cur_run["commit"]:
        commit_msg = cur_run["commit"]["message"]
        commit_hash = cur_run["commit"]["sha"]
        if cur_run["commit"]["timestamp"]:
            cur_benchmark_time = util.tznaive_iso8601_to_tzaware_dt(
                cur_run["commit"]["timestamp"]
            )
        else:
            cur_benchmark_time = current_benchmark_result.timestamp
    else:
        commit_msg = "no commit"
        commit_hash = "no commit"
        cur_benchmark_time = current_benchmark_result.timestamp

    dummy_hs = HistorySample(
        mean=current_benchmark_result.mean,
        benchmark_name=TBenchmarkName("dummy"),
        history_fingerprint="dummy",
        case_text_id="dummy",
        svs=current_benchmark_result.svs,
        svs_type=current_benchmark_result.svs_type,
        commit_msg=commit_msg,
        commit_timestamp=cur_benchmark_time,
        commit_hash=commit_hash,
        benchmark_result_id=current_benchmark_result.id,
        repository=current_benchmark_result.commit_repo_url,
        data=[
            float(d) if d is not None else math.nan
            for d in current_benchmark_result.data
        ],
        case_id="dummy",  # not consumed
        context_id="dummy",  # not consumed
        # "Per PEP 484, int is a subtype of float"
        times=[0.0],  # not consumed
        unit="dummy",  # not consumed
        hardware_hash="dummy",  # not consumed
        run_name="dummy",  # not consumed
        zscorestats=HistorySampleZscoreStats(
            begins_distribution_change=False,  # not consumed
            segment_id="dummy",  # not consumed
            rolling_mean_excluding_this_commit=0.0,  # not consumed
            rolling_mean=0.0,  # not consumed
            residual=0.0,  # not consumed
            rolling_stddev=0.0,  # not consumed
            is_outlier=False,  # not consumed
        ),
    )

    source_current_bm_svs = _source([dummy_hs], unit, "svs")
    source_current_bm_raw = _source([dummy_hs], unit, "all_data")

    return source_current_bm_svs, source_current_bm_raw
