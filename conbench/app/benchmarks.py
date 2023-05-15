import collections
import itertools
import logging
import math
import time
from typing import Dict, List, Tuple, TypedDict

import flask
import numpy as np
import orjson

import conbench.numstr
from conbench.app import app
from conbench.app._endpoint import authorize_or_terminate
from conbench.config import Config
from conbench.job import BMRTBenchmarkResult, bmrt_cache

log = logging.getLogger(__name__)


def newest_of_many_results(results: List[BMRTBenchmarkResult]) -> BMRTBenchmarkResult:
    return max(results, key=lambda r: r.started_at)


def time_of_newest_of_many_results(results: List[BMRTBenchmarkResult]) -> float:
    return max(r.started_at for r in results)


def get_first_n_dict_subset(d: Dict, n: int) -> Dict:
    # A bit of discussion here:
    # https://stackoverflow.com/a/12980510/145400
    return {k: d[k] for k in list(d)[:n]}


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
    benchmark_names_by_rpcr: Dict[str, str] = {}
    now = time.time()
    for bname, results in bmrt_cache["by_benchmark_name"].items():
        # Generally, there are C case permutations for this benchmark. Group
        # the results by case permutation.
        results_per_case: Dict[
            str, List[BMRTBenchmarkResult]
        ] = collections.defaultdict(list)
        for r in results:
            results_per_case[r.case_id].append(r)

        # Now, build the RPCR metric for each benchmark.
        rpcr = 0.0
        for _, cresults in results_per_case.items():
            # Sort by age: newer items last -> smaller age values last ->
            # desc -> reverse=True
            ages_seconds = list(
                sorted((now - r.started_at for r in cresults), reverse=True)
            )

            # Take a most recent fraction of this list and build the mean value
            # (mean age in seconds of the last 10 % of the results)
            a_i_seconds = np.mean(
                ages_seconds[-math.ceil(len(ages_seconds) / 10) :]  # noqa
            )
            a_i_days = float(a_i_seconds / (24.0 * 60 * 60))
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


@app.route("/c-benchmarks/<bname>", methods=["GET"])  # type: ignore
@authorize_or_terminate
def show_benchmark_cases(bname: str) -> str:
    # Do not catch KeyError upon lookup for checking for key, because this
    # would insert the key into the defaultdict(list) (as an empty list).
    if bname not in bmrt_cache["by_benchmark_name"]:
        return f"benchmark name not known: `{bname}`"

    t0 = time.monotonic()

    matching_results = bmrt_cache["by_benchmark_name"][bname]
    results_by_case_id: Dict[str, List[BMRTBenchmarkResult]] = collections.defaultdict(
        list
    )

    # First, group results by case.
    for r in matching_results:
        results_by_case_id[r.case_id].append(r)

    log.info("after first loop: %.5f s", time.monotonic() - t0)

    # Go through all results for this benchmark and keep track of all case
    # parameter keys seen. This is useful because it is allowed for a result to
    # _not_ specify a case parameter key in its case dictionary, and that
    # counts as a special case for a value: "not set".
    # all_case_keys_seen = set(
    #     itertools.chain.from_iterable(r.case_dict.keys() for r in matching_results)
    # )

    log.info("after second loop: %.5f s", time.monotonic() - t0)

    all_values_per_case_key: Dict[str, collections.Counter] = collections.defaultdict(
        collections.Counter
    )

    for r in matching_results:
        # Detect when this result's case dict does not specify some keys, and
        # represent those as special value. This allows for correct
        # identification of "constant case parameters" across _all_ results
        # (value count :1); in that case the parameter can be removed / ignored
        # / treated specially in the UI> Today, there might be any kind of type
        # here for key and value in the r.case_dict (coming straight from DB).
        # Difficult. See https://github.com/conbench/conbench/pull/948 and
        # https://github.com/conbench/conbench/issues/940. Change both to
        # string here. For example, this might result in values to be `"None"`.
        # keys_not_specified = all_case_keys_seen - set(r.case_dict.keys())
        # for k in keys_not_specified:
        #     # Forcing the type conversion from various types to string: this
        #     # might be error-prone and a nest of bees, but we will have to see
        #     all_values_per_case_key[str(k)].update(["_NOT_SET_IN_DICT"])
        for case_parm_key, case_parm_value in r.case_dict.items():
            all_values_per_case_key[str(case_parm_key)].update([str(case_parm_value)])

    # log.info("all_values_per_case_key: %s", all_values_per_case_key)

    log.info("after third loop: %.5f s", time.monotonic() - t0)

    # Sort by parameter value count (uniquely different parameter values,
    # not by how often these individual values are used).
    all_values_per_case_key = dict(
        sorted(
            all_values_per_case_key.items(),
            key=lambda item: len(item[1]),
            reverse=True,
        )
    )

    # log.info("all_values_per_case_key: %s", all_values_per_case_key)

    log.info("after sort 1: %.5f s", time.monotonic() - t0)

    # Each item's value is a set of observed values. Make it a list, sorted
    # alphabetically.
    all_values_per_case_key_sorted: Dict[str, Dict[str, int]] = {}
    for case_parm_key, value_counter in all_values_per_case_key.items():
        all_values_per_case_key_sorted[case_parm_key] = dict(
            value_counter.most_common(None)
        )
    # log.info("all case parameters seen: %s", all_values_per_case_key)

    # log.info("all_values_per_case_key_sorted: %s", all_values_per_case_key_sorted)

    log.info("after most common: %.5f s", time.monotonic() - t0)

    t0 = time.monotonic()

    hardware_count_per_case_id = {}
    for case_id, results in results_by_case_id.items():
        # The indirection through `.run` here is an architecture / DB schema
        # smell I think. This might fetch run dynamically from the DB>
        hardware_count_per_case_id[case_id] = len(set([r.hardware_id for r in results]))

    log.info("after hw stuff: %.5f s", time.monotonic() - t0)

    # log.info("building hardware_count_per_case took %.3f s", time.monotonic() - t0)

    last_result_per_case_id: Dict[str, BMRTBenchmarkResult] = {}

    context_count_per_case_id: Dict[str, int] = {}
    for case_id, results in results_by_case_id.items():
        context_count_per_case_id[case_id] = len(set([r.context_id for r in results]))
        last_result_per_case_id[case_id] = newest_of_many_results(results)

    log.info("after case stuff: %.5f s", time.monotonic() - t0)

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
        application=Config.APPLICATION_NAME,
        title=Config.APPLICATION_NAME,  # type: ignore
    )


class TypeUIPlotInfo(TypedDict):
    hwid: str
    ctxid: str
    hwname: str
    n_results: int
    url_to_newest_result: str
    data_for_uplot: List[List]
    unit: str


@app.route("/c-benchmarks/<bname>/<caseid>", methods=["GET"])  # type: ignore
@authorize_or_terminate
def show_benchmark_results(bname: str, caseid: str) -> str:
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
                # of magnitude is fine.
                [conbench.numstr.numstr(r.svs, 7) for r in results],
            ],
            # Rely on at least one result being in the list.
            "hwid": hwid,
            "ctxid": ctxid,
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
