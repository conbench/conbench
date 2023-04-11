import logging
import json
from collections import defaultdict

from typing import Dict, List, Tuple, TypedDict


import flask

from conbench.app import app
from conbench.entities.benchmark_result import BenchmarkResult
from conbench.config import Config
from conbench.job import _cache_bmrs


log = logging.getLogger(__name__)


@app.route("/c-benchmarks/", methods=["GET"])
def list_benchmarks() -> str:
    return flask.render_template(
        "c-benchmarks.html",
        # benchmarks_by_name=benchmarks_by_name,
        benchmarks_by_name=_cache_bmrs["by_benchmark_name"],
        benchmark_result_count=len(_cache_bmrs["by_id"]),
        bmr_cache_meta=_cache_bmrs["meta"],
        application=Config.APPLICATION_NAME,
        title=Config.APPLICATION_NAME,  # type: ignore
    )


@app.route("/c-benchmarks/<bname>", methods=["GET"])
def show_benchmark_cases(bname: str) -> str:
    try:
        results = _cache_bmrs["by_benchmark_name"][bname]
    except KeyError:
        return f"benchmark name not known: `{bname}`"

    # cases = set(bmr.case for bmr in results)

    results_by_case = defaultdict(list)
    for r in results:
        results_by_case[r.case].append(r)

    hardware_count_per_case = {}
    for case in results_by_case.keys():
        # The indirection through `.run` here is an architecture / DB schema
        # smell I think. This might fetch run dynamically from the DB>
        hardware_count_per_case[case] = len(set([r.run.hardware for r in results]))

    context_count_per_case = {}
    for case, results in results_by_case.items():
        context_count_per_case[case] = len(set([r.context for r in results]))

    return flask.render_template(
        "c-benchmark-cases.html",
        # benchmarks_by_name=benchmarks_by_name,
        # benchmarks_results=results,
        benchmark_name=bname,
        bmr_cache_meta=_cache_bmrs["meta"],
        results_by_case=results_by_case,
        hardware_count_per_case=hardware_count_per_case,
        context_count_per_case=context_count_per_case,
        # cases=cases,
        benchmark_result_count=len(results),
        application=Config.APPLICATION_NAME,
        title=Config.APPLICATION_NAME,  # type: ignore
    )


class TypeUIPlotInfo(TypedDict):
    title: str
    data_for_uplot: List[List]


@app.route("/c-benchmarks/<bname>/<caseid>", methods=["GET"])
def show_benchmark_results(bname: str, caseid: str) -> str:
    # First, filter by benchmark name.
    try:
        results_all_with_bname = _cache_bmrs["by_benchmark_name"][bname]
    except KeyError:
        return f"benchmark name not known: `{bname}`"

    # Now, filter those that have the required case ID set.
    matching_results = []
    for r in results_all_with_bname:
        if r.case.id == caseid:
            matching_results.append(r)

    log.info(
        "results_all_with_bname: %s, results with caseid and bname: %s",
        len(results_all_with_bname),
        len(matching_results),
    )
    # Be explicit that this is now of no use.
    del results_all_with_bname

    if matching_results:
        case = matching_results[0].case
    else:
        return f"no results found for benchmark `{bname}` and case `{caseid}`"

    results_by_hardware_and_context: Dict[Tuple, List[BenchmarkResult]] = defaultdict(
        list
    )

    # Build up timeseries of results (group results, don't sort them yet)
    for result in matching_results:
        # The indirection through `.run` here is an architecture / DB schema
        # smell I think. This might fetch run dynamically from the DB.
        # Store hardware name in dictionary key, for convenience.
        h = result.run.hardware
        hwid, hwname, ctxid = h.id, h.name, result.context.id
        results_by_hardware_and_context[(hwid, ctxid, hwname)].append(result)

    # This is going to be accessed with JavaScript.
    infos_for_uplots = {}

    for (hwid, ctxid, _), results in results_by_hardware_and_context.items():
        infos_for_uplots[f"{hwid}_{ctxid}"] = {
            "data_for_uplot": [
                [r.timestamp.timestamp() for r in results],
                # rely on mean to be correct? use all data for
                # error vis
                [float(r.mean) for r in results],
            ],
            # Rely on at least one result being in the list.
            "title": "hardware: %s, context: %s"
            % (results[0].ui_hardware_short, ctxid[:7]),
        }

    infos_for_uplots_json = json.dumps(infos_for_uplots, indent=2)
    return flask.render_template(
        "c-benchmark-results-for-case.html",
        # benchmarks_by_name=benchmarks_by_name,
        benchmark_results=matching_results,
        benchmark_name=bname,
        bmr_cache_meta=_cache_bmrs["meta"],
        results_by_hardware_and_context=results_by_hardware_and_context,
        infos_for_uplots_json=infos_for_uplots_json,
        case=case,
        benchmark_result_count=len(results),
        application=Config.APPLICATION_NAME,
        title=Config.APPLICATION_NAME,  # type: ignore
    )
