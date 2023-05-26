import collections
import functools
import logging
import math
import time
from typing import Dict, List, Tuple, TypedDict, TypeVar

import flask
import numpy as np
import numpy.polynomial
import orjson
import pandas as pd

import conbench.numstr
from conbench.app import app
from conbench.app._endpoint import authorize_or_terminate
from conbench.config import Config
from conbench.job import BMRTBenchmarkResult, TBenchmarkName, bmrt_cache
from conbench.outlier import remove_outliers_by_iqrdist

"""
Experimental: UX around 'conceptual benchmarks'

Most UI routes should contain the repo specifier, and not just the benchmark
name (scenario: same benchmark name, but two different benchmarked repositories
-- yeah, multi-repo support is costly. maybe drop it again.)
"""

numstr8 = functools.partial(conbench.numstr.numstr, sigfigs=8)


log = logging.getLogger(__name__)


def newest_of_many_results(results: List[BMRTBenchmarkResult]) -> BMRTBenchmarkResult:
    return max(results, key=lambda r: r.started_at)


def time_of_newest_of_many_results(results: List[BMRTBenchmarkResult]) -> float:
    return max(r.started_at for r in results)


# Make this function's return type precisely be the type of input `d`, which is
# often more specific than just Dict.
GenDict = TypeVar("GenDict")  # the variable name must coincide with the string


def get_first_n_dict_subset(d: GenDict, n: int) -> GenDict:
    # A bit of discussion here:
    # https://stackoverflow.com/a/12980510/145400
    assert isinstance(d, dict)
    return {k: d[k] for k in list(d)[:n]}  # type: ignore


@app.route("/c-benchmarks/", methods=["GET"])  # type: ignore
@authorize_or_terminate
def list_benchmarks() -> str:
    # Sort alphabetically by string key
    benchmarks_by_name_sorted_alphabetically = dict(
        sorted(
            bmrt_cache["by_benchmark_name"].items(), key=lambda item: item[0].lower()
        )
    )

    newest_result_by_bname: Dict[str, BMRTBenchmarkResult] = {
        bname: newest_of_many_results(bmrlist)
        for bname, bmrlist in bmrt_cache["by_benchmark_name"].items()
    }

    newest_result_for_each_benchmark_name_sorted = [
        bmr
        for _, bmr in sorted(
            newest_result_by_bname.items(),
            key=lambda item: item[1].started_at,
            reverse=True,
        )
    ]

    benchmarks_by_name_sorted_by_resultcount = dict(
        sorted(
            bmrt_cache["by_benchmark_name"].items(),
            key=lambda item: len(item[1]),
            reverse=True,
        ),
    )

    # Note(JP): build an average "results per case and recency" metric that
    # favors those benchmarks that have have more results per case permutation
    # and that have most of their results reported in the recent past. As we
    # frequently find us saying in discussions, the individual case permutation
    # is what we look at as the individual benchmark.
    # See https://github.com/conbench/conbench/issues/1264 for definition of
    # rpcr.
    now = time.time()
    benchmark_names_by_rpcr: Dict[str, str] = {}
    for bname, results in bmrt_cache["by_benchmark_name"].items():
        # Generally, there are C case permutations for this benchmark. Group
        # the results by case permutation.
        results_per_case: Dict[
            str, List[BMRTBenchmarkResult]
        ] = collections.defaultdict(list)
        for r in results:
            results_per_case[r.case_id].append(r)

        # Now, build the RPCR metric for each conceptual benchmark.
        rpcr = 0.0
        for _, cresults in results_per_case.items():
            # mean age in seconds of the last 10 % of the results
            a_i_seconds = now - avg_starttime_of_newest_n_percent_of_results(
                cresults, 10
            )
            a_i_days = a_i_seconds / (24.0 * 60 * 60)
            rpcr += 1 / a_i_days * len(cresults)

        # ratio = len(results) / float(case_permutation_count)
        # Sort order is not too important when there is a clash here as of
        # loss in precision.
        benchmark_names_by_rpcr[bname] = f"{rpcr:.1f}"

    benchmark_names_by_rpcr_sorted = dict(
        sorted(
            benchmark_names_by_rpcr.items(),
            key=lambda item: float(item[1]),
            reverse=True,
        )
    )

    return flask.render_template(
        "c-benchmarks.html",
        benchmarks_by_name=bmrt_cache["by_benchmark_name"],
        benchmark_result_count=len(bmrt_cache["by_id"]),
        benchmarks_by_name_sorted_alphabetically=benchmarks_by_name_sorted_alphabetically,
        benchmarks_by_name_sorted_by_resultcount=benchmarks_by_name_sorted_by_resultcount,
        benchmark_names_by_rpcr_sorted=benchmark_names_by_rpcr_sorted,
        newest_result_for_each_benchmark_name_topN=newest_result_for_each_benchmark_name_sorted[
            :20
        ],
        bmr_cache_meta=bmrt_cache["meta"],
        application=Config.APPLICATION_NAME,
        title=Config.APPLICATION_NAME,  # type: ignore
    )


@app.route("/c-benchmarks/<bname>/trends", methods=["GET"])  # type: ignore
@authorize_or_terminate
def show_trends_for_benchmark(bname: TBenchmarkName) -> str:
    # Narrow down relevant dataframes.
    dfs_by_t3: Dict[Tuple[str, str, str], pd.DataFrame] = {}
    for (ibname, case_id, context_id, hardware_id), df in bmrt_cache[
        "by_4t_df"
    ].items():
        if ibname == bname:
            dfs_by_t3[(case_id, context_id, hardware_id)] = df

    log.info("built dfs_by_t3")

    # Do this trend analysis only for those timeseries that are recent.
    # Criterion here for now: simple cutoff relative to _now_. TODO:
    # relative to newest result for this conceptual benchmark.

    now = time.time()
    relchange_by_t3: Dict[Tuple[str, str, str], float] = {}
    for t3, df in dfs_by_t3.items():
        # Note(JP): make a linear regression: derive a slope value. this is
        # mainly about the sign of the slope. that means: we can work with the
        # absolute t/time values we have. for the y values the goal is to make
        # change comparable across different scenarios. Not across different
        # units, though.
        #
        # Interesting: benchmark result time distribution vs. commit
        # distribution over time. assume that code evolution is highly
        # correlated with benchmark start time evolution.

        # Ignore df rows in here where results reported SVS being NAN.
        # Update: do this later below where we have to dropna anyway.
        # df = df[df["svs"].notna()]

        # count(): number of non-NaN values
        if df["svs"].count() < 10:
            # Skip if there's little history anyway.
            continue

        # Recency criterion.
        newest_timestamp = df.index[-1].timestamp()
        if now - newest_timestamp > 86400 * 30:
            continue

        # TODO: basic outlier detection before the fit.
        # Either rolling window median based, or maybe
        # huber loss https://stackoverflow.com/a/61144766

        # Did some of that before here:
        # https://github.com/jgehrcke/covid-19-analysis/blob/4950649a27c51c2bf36baba258757249385f2808/process.py#L227
        # it's a bit of a seemingly complex(?) converstion from pd
        # datetimeindex back to float values. Remove 10^15 from these
        # nanoseconds-since-epoch to make the numeric values a little less
        # extreme for printing/debugging.

        # Do not modify dataframe objects in BMRT cache.
        df = df.copy()
        remove_outliers_by_iqrdist(df, "svs")

        # Now it's important to drop nans again because the outliers have been
        # marked with NaN, and any NaN will nannify the linear fit. We do not
        # want to mutate the DF in the BMRT cache. drop nans, create explicit
        # copy (otherwise this might be a view)
        df = df.dropna()  # drop all rows that have any NaN
        if len(df.index) < 10:
            # Skip if after outlier removal there's not enough history left.
            continue

        tfloats = (
            np.array(df.index.to_pydatetime(), dtype=np.datetime64).astype("float")
            / 10**15
        )
        yfloats = df["svs"].values

        # Note that this is a least squares fit.
        fitted_series = numpy.polynomial.Polynomial.fit(tfloats, yfloats, 1)

        # print(fitted_series)
        # https://numpy.org/doc/stable/reference/generated/numpy.polynomial.polynomial.Polynomial.fit.html#numpy.polynomial.polynomial.Polynomial.fit
        slope, ordinate = fitted_series.coef[1], fitted_series.coef[0]
        # print(slope, ordinate)

        # these values might be nan if the fit failed. if the input has a
        # nan then the fit fails: clean the input! But even then maybe the
        # fit might fail? Looks like nan has high sort order.
        # check for this value upon data emission? No.
        if math.isnan(slope):
            continue

        # Do a 'normalization' here to find _relative change_. For the offset
        # use data from the linear fit (the constant part of the linearity).
        # Think: the smaller most of the values are, the _more_ does the _same_
        # slope reflect relative change.
        relchange = slope / ordinate
        #  print(f"slope: {slope}")
        relchange_by_t3[t3] = relchange

    # sort by relative change, largest first.
    relchange_by_t3_sorted: Dict[Tuple[str, str, str], float] = dict(
        sorted(
            relchange_by_t3.items(),
            key=lambda item: item[1],
            reverse=True,
        )
    )

    log.info("made %s linear regressions", len(relchange_by_t3))

    # for t3, relchange in relchange_by_t3_sorted.items():
    #     print(t3, ": ", relchange)

    context_json_by_context_id: Dict[str, str] = {}
    infos_for_uplots: Dict[str, TypeUIPlotInfo] = {}

    # Input type equals output type, yeah
    topn_t3_dict = get_first_n_dict_subset(relchange_by_t3_sorted, 12)
    # topn_t3 = list(relchange_by_t3_sorted.keys())[:6]
    # log.info("topn for plot: %s", topn_t3_dict)

    for t3, relchange in topn_t3_dict.items():
        # for (hwid, ctxid, _), results in results_by_hardware_and_context_sorted.items():
        # Only include those cases where there are at least three results.
        # (this structure is used for plotting only).
        caseid, ctxid, hwid = t3
        results = bmrt_cache["by_4t_list"][(bname, caseid, ctxid, hwid)]

        # dfts = bmrt_cache["by_4t_df"][(bname, caseid, ctxid, hwid)]
        # print()
        # print()
        # print((bname, caseid, ctxid, hwid))
        # print(dfts.to_csv(na_rep="NaN", float_format=numstr8))

        # sanity check. there must be a considerable number of results in this
        # list because this is a top N case based on linear fit on a dataframe
        # with a minimum number of data points.
        assert len(results) > 7

        # context_dicts_by_context_id[ctxid] = results[0].context_dict
        # Maybe we don't need to pass the Python dict into the temmplate,
        # but a pre-formatted JSON doc for copy/pasting might result
        # in better UX.
        context_json_by_context_id[ctxid] = orjson.dumps(
            results[0].context_dict, option=orjson.OPT_INDENT_2
        ).decode("utf-8")

        units_seen = set()
        newest_result = newest_of_many_results(results)
        for r in results:
            units_seen.add(r.unit)

        # todo: need to add case id
        infos_for_uplots[f"{caseid}_{hwid}_{ctxid}"] = {
            # deduplicate with code below
            "data_for_uplot": [
                [int(r.started_at) for r in results],
                [
                    conbench.numstr.numstr(r.svs, 7) if not math.isnan(r.svs) else None
                    for r in results
                ],
            ],
            # Rely on at least one result being in the list.
            "hwid": hwid,
            "ctxid": ctxid,
            "caseid": caseid,
            "hwname": results[0].hardware_name,
            "aux_title": f"relchange: {conbench.numstr.numstr(relchange, 3)}",
            "n_results": len(results),
            "url_to_newest_result": flask.url_for(
                "app.benchmark-result",
                benchmark_result_id=newest_result.id,
            ),
            "unit": maybe_longer_unit(newest_result.unit),
        }

    log.info("generated uplot structs")
    # Need to find a way to put bytes straight into jinja template.
    # still is still a tiny bit faster than using stdlib json.dumps()
    infos_for_uplots_json = orjson.dumps(
        infos_for_uplots, option=orjson.OPT_INDENT_2
    ).decode("utf-8")

    log.info("built plot info JSON")

    return flask.render_template(
        "c-benchmark-trends.html",
        benchmark_name=bname,
        bmr_cache_meta=bmrt_cache["meta"],
        context_json_by_context_id=context_json_by_context_id,
        # y_unit_for_all_plots="foo",
        infos_for_uplots=infos_for_uplots,
        infos_for_uplots_json=infos_for_uplots_json,
        application=Config.APPLICATION_NAME,
        title=Config.APPLICATION_NAME,  # type: ignore
    )


@app.route("/c-benchmarks/<bname>", methods=["GET"])  # type: ignore
@authorize_or_terminate
def show_benchmark_cases(bname: TBenchmarkName) -> str:
    # Do not catch KeyError upon lookup for checking for key, because this
    # would insert the key into the defaultdict(list) (as an empty list).
    if bname not in bmrt_cache["by_benchmark_name"]:
        return f"benchmark name not known: `{bname}`"

    matching_results = bmrt_cache["by_benchmark_name"][bname]
    results_by_case_id: Dict[str, List[BMRTBenchmarkResult]] = collections.defaultdict(
        list
    )

    # First, group results by case.
    for r in matching_results:
        results_by_case_id[r.case_id].append(r)

    # Observe each unique key/value pair, but also keep track of how often
    # particular value was set for a key.
    all_values_per_case_key: Dict[str, collections.Counter] = collections.defaultdict(
        collections.Counter
    )

    # Keep track of the last time when a particular key/value pair was set.
    # Within a key, we can then see how recently the value was actually varied
    # across results. That way, we can identify those key/value pairs that do
    # not seem to be recent anymore.
    time_of_last_result_with_casekey_set: Dict[str, float] = {}

    for r in matching_results:
        # Today, there might be any kind of type here for key and value in the
        # r.case_dict (coming straight from DB). Difficult. See
        # https://github.com/conbench/conbench/pull/948 and
        # https://github.com/conbench/conbench/issues/940. Change both to
        # string here. Might be error-prone and a nest of bees, but we will have to see
        for case_parm_key, case_parm_value in r.case_dict.items():
            # Note that this two-dim loop that we're in can get expensive,
            # maybe takes 0.5 s for 10^5 results? I suspect there is lots of
            # low-hanging fruit potential for speeding this up by 10 or 100 x
            # -- However, really let's not do premature optimization. First,
            # make this 'correct', then maybe later measure and optimize.
            k = str(case_parm_key)
            v = str(case_parm_value)

            # The Counter update with a single value seems stupid :shrug:.
            all_values_per_case_key[k].update([v])

            if r.started_at > time_of_last_result_with_casekey_set.get(k, 0):
                time_of_last_result_with_casekey_set[k] = r.started_at

    # Translate absolute time(stamp) into age (in seconds) relative to ... not
    # to _now_ but relative to the more-or-less average time that the most
    # recent benchmark results came in.
    reftime = avg_starttime_of_newest_n_percent_of_results(matching_results, 10)

    relative_age_of_last_result_with_casekey_set = {
        k: reftime - t for k, t in time_of_last_result_with_casekey_set.items()
    }

    # And now identify those case key/value pairs that are _old_ compared to
    # the more recent benchmark results we talk about here.
    # The string value in the following dict is a numeric string, indicating
    # the "relative age" in days, shown in the UI
    dead_stock_casekeys: Dict[str, str] = {}
    for (
        casekey,
        rel_age_seconds,
    ) in relative_age_of_last_result_with_casekey_set.items():
        # Now. This might be too simple and too arbitrary, but it's worth
        # trying. A day has 86400 seconds. Set threshold in terms of N weeks.
        if rel_age_seconds > 86400 * 7 * 3:
            dead_stock_casekeys[casekey] = f"{int(rel_age_seconds / 86400.0)} days"

    # Sort by parameter value count (uniquely different parameter values,
    # not by how often these individual values are used).
    all_values_per_case_key = dict(
        sorted(
            all_values_per_case_key.items(),
            key=lambda item: len(item[1]),
            reverse=True,
        )
    )

    # Each item's value is a set of observed values. Make it a list, sorted
    # alphabetically.
    all_values_per_case_key_sorted: Dict[str, Dict[str, int]] = {}
    for case_parm_key, value_counter in all_values_per_case_key.items():
        all_values_per_case_key_sorted[case_parm_key] = dict(
            value_counter.most_common(None)
        )

    # Now, the tricky part -- simply remove the dead stock? For now, yes! But
    # also show in UI which case key parameters are hidden from the filter
    # panels, and why.
    for dskey in dead_stock_casekeys:
        del all_values_per_case_key_sorted[dskey]

    hardware_count_per_case_id = {}
    for case_id, results in results_by_case_id.items():
        # The indirection through `.run` here is an architecture / DB schema
        # smell I think. This might fetch run dynamically from the DB>
        hardware_count_per_case_id[case_id] = len(set([r.hardware_id for r in results]))

    last_result_per_case_id: Dict[str, BMRTBenchmarkResult] = {}

    context_count_per_case_id: Dict[str, int] = {}
    for case_id, results in results_by_case_id.items():
        context_count_per_case_id[case_id] = len(set([r.context_id for r in results]))
        last_result_per_case_id[case_id] = newest_of_many_results(results)

    return flask.render_template(
        "c-benchmark-cases.html",
        benchmark_name=bname,
        bmr_cache_meta=bmrt_cache["meta"],
        results_by_case_id=results_by_case_id,
        hardware_count_per_case_id=hardware_count_per_case_id,
        last_result_per_case_id=last_result_per_case_id,
        context_count_per_case_id=context_count_per_case_id,
        benchmark_result_count=len(matching_results),
        all_values_per_case_key_sorted=all_values_per_case_key_sorted,
        dead_stock_casekeys=dead_stock_casekeys,
        application=Config.APPLICATION_NAME,
        title=Config.APPLICATION_NAME,  # type: ignore
    )


class TypeUIPlotInfo(TypedDict):
    hwid: str
    ctxid: str
    caseid: str
    hwname: str
    aux_title: str
    n_results: int
    url_to_newest_result: str
    data_for_uplot: List[List]
    unit: str


@app.route("/c-benchmarks/<bname>/<caseid>", methods=["GET"])  # type: ignore
@authorize_or_terminate
def show_benchmark_results(bname: TBenchmarkName, caseid: str) -> str:
    # First, filter by benchmark name.
    try:
        results_all_with_bname = bmrt_cache["by_benchmark_name"][bname]
    except KeyError:
        return f"benchmark name not known: `{bname}`"

    # Now, filter those that have the required case ID set.
    matching_results = []
    for r in results_all_with_bname:
        if r.case_id == caseid:
            matching_results.append(r)

    # log.info(
    #     "results_all_with_bname: %s, results with caseid and bname: %s",
    #     len(results_all_with_bname),
    #     len(matching_results),
    # )

    # Be explicit that this is now of no use.
    del results_all_with_bname

    if not matching_results:
        return f"no results found for benchmark `{bname}` and case `{caseid}`"

    results_by_hardware_and_context: Dict[
        Tuple, List[BMRTBenchmarkResult]
    ] = collections.defaultdict(list)

    # Build up timeseries of results (group results, don't sort them yet).
    for result in matching_results:
        # The indirection through `result.run.hardware` here is an architecture
        # / DB schema smell I think. This might fetch run dynamically from the
        # DB. Store hardware name in dictionary key, for convenience.
        hwid, hwname, ctxid = (
            result.hardware_id,
            result.hardware_name,
            result.context_id,
        )
        results_by_hardware_and_context[(hwid, ctxid, hwname)].append(result)

    # Make it so that infos_for_uplots is sorted by result count, i.e. show
    # most busy plots first. Instead, it might make sense to sort by recency!
    results_by_hardware_and_context_sorted = dict(
        sorted(
            results_by_hardware_and_context.items(),
            key=lambda item: len(item[1]),
            reverse=True,
        )
    )

    # In the table show at most ~3000 results (for now, it's not really OK
    # to render it for 10000 results)
    results_for_table = []
    for _, results in results_by_hardware_and_context_sorted.items():
        results_for_table.extend(results[:3000])
        if len(results_for_table) >= 3000:
            break

    # This is going to be the data structure that the individual plots are
    # based on, also JSON-serialized and then accessed by JavaScript.
    infos_for_uplots: Dict[str, TypeUIPlotInfo] = {}

    units_seen = set()

    # context_dicts_by_context_id: Dict[str, Dict[str, str]] = {}
    context_json_by_context_id: Dict[str, str] = {}

    for (hwid, ctxid, _), results in results_by_hardware_and_context_sorted.items():
        # Only include those cases where there are at least three results.
        # (this structure is used for plotting only).
        if len(results) < 3:
            continue

        # context_dicts_by_context_id[ctxid] = results[0].context_dict

        # Maybe we don't need to pass the Python dict into the temmplate,
        # but a pre-formatted JSON doc for copy/pasting might result
        # in better UX.
        context_json_by_context_id[ctxid] = orjson.dumps(
            results[0].context_dict, option=orjson.OPT_INDENT_2
        ).decode("utf-8")

        newest_result = newest_of_many_results(results)

        for r in results:
            units_seen.add(r.unit)

        infos_for_uplots[f"{hwid}_{ctxid}"] = {
            "data_for_uplot": [
                # Send timestamp with 1 second resolution.
                [int(r.started_at) for r in results],
                # Use single value summary (right now: mean or NaN). Also:
                # there is no need to send an abstruse number of significant
                # digits here (64 bit floating point precision). Benchmark
                # results should not vary across many orders of magnitude
                # between invocations. If they do, it's a qualitative problem
                # and the _precise_ difference does not need to be readable
                # from these plots. I think sending detail across seven orders
                # of magnitude is fine. Careful: >>>
                # np.format_float_positional(float("NaN")) would return 'nan'
                # (string). But for orjson to emit a `null` ( which is what
                # uplot wants we should have a `None` in the list).
                [
                    conbench.numstr.numstr(r.svs, 7) if not math.isnan(r.svs) else None
                    for r in results
                ],
            ],
            # Rely on at least one result being in the list.
            "hwid": hwid,
            "ctxid": ctxid,
            "caseid": caseid,
            "aux_title": "",
            "hwname": results[0].hardware_name,
            "n_results": len(results),
            "url_to_newest_result": flask.url_for(
                "app.benchmark-result",
                benchmark_result_id=newest_result.id,
            ),
            "unit": newest_result.unit,
        }

    # For now, only emit a warning in the web application log.
    # TODO: show a user-facing warning on this page.

    if len(units_seen) != 1:
        log.warning(
            "/c-benchmarks/%s/%s: saw more than one unit: %s", bname, caseid, units_seen
        )

    # Proceed, show a potentially wrong unit.
    y_unit_for_all_plots = maybe_longer_unit(units_seen.pop())
    # log.info("unit: %s", y_unit_for_all_plots)

    # Need to find a way to put bytes straight into jinja template.
    # still is still a tiny bit faster than using stdlib json.dumps()
    infos_for_uplots_json = orjson.dumps(
        infos_for_uplots, option=orjson.OPT_INDENT_2
    ).decode("utf-8")

    return flask.render_template(
        "c-benchmark-results-for-case.html",
        matching_benchmark_result_count=len(matching_results),
        benchmark_results_for_table=results_for_table,
        y_unit_for_all_plots=y_unit_for_all_plots,
        benchmark_name=bname,
        bmr_cache_meta=bmrt_cache["meta"],
        infos_for_uplots=infos_for_uplots,
        infos_for_uplots_json=infos_for_uplots_json,
        this_case_id=matching_results[0].case_id,
        this_case_text_id=matching_results[0].case_text_id,
        context_json_by_context_id=context_json_by_context_id,
        application=Config.APPLICATION_NAME,
        title=Config.APPLICATION_NAME,  # type: ignore
    )


_UNIT_REPLACE_MAP = {"s": "seconds", "i/s": "iterations / second"}


def maybe_longer_unit(unit: str) -> str:
    """
    A longer unit reads better on the ordinate of a plot.
    """
    if unit in _UNIT_REPLACE_MAP:
        return _UNIT_REPLACE_MAP[unit]
    return unit


def avg_starttime_of_newest_n_percent_of_results(
    results: List[BMRTBenchmarkResult], npc: int
) -> float:
    """
    Return average start time of the newest N percent of those results in the
    input list.

    Return the average start time in the form of a unix timestamp.

    This is a helper that can provide an idea about the 'recency' of a
    collection of benchmark results.
    """
    # Sort by age: newer items last -> smaller  values first -> asc (default
    # sort direction).
    timestamps = list(sorted((r.started_at for r in results)))

    # Take a most recent fraction of this list and build the mean value
    # (example:mean age in seconds of the last 10 % of the results)
    return float(np.mean(timestamps[-math.ceil(len(timestamps) / npc) :]))  # noqa
