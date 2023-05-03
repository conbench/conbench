import logging
import time
from collections import defaultdict
from typing import Dict, List, Tuple, TypedDict

import flask
import orjson

from conbench.app import app
from conbench.app._endpoint import authorize_or_terminate
from conbench.config import Config

# from conbench.entities.benchmark_result import BenchmarkResult
from conbench.job import BMRTBenchmarkResult, _cache_bmrs

log = logging.getLogger(__name__)


@app.route("/c-benchmarks/", methods=["GET"])  # type: ignore
@authorize_or_terminate
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


@app.route("/c-benchmarks/<bname>", methods=["GET"])  # type: ignore
@authorize_or_terminate
def show_benchmark_cases(bname: str) -> str:
    try:
        matching_results = _cache_bmrs["by_benchmark_name"][bname]
    except KeyError:
        return f"benchmark name not known: `{bname}`"

    # cases = set(bmr.case for bmr in results)

    results_by_case_id: Dict[str, List[BMRTBenchmarkResult]] = defaultdict(list)
    for r in matching_results:
        results_by_case_id[r.case_id].append(r)

    t0 = time.monotonic()

    hardware_count_per_case_id = {}
    for case_id, results in results_by_case_id.items():
        # The indirection through `.run` here is an architecture / DB schema
        # smell I think. This might fetch run dynamically from the DB>
        hardware_count_per_case_id[case_id] = len(set([r.hardware_id for r in results]))

    log.info("building hardware_count_per_case took %.3f s", time.monotonic() - t0)

    last_result_per_case_id: Dict[str, BMRTBenchmarkResult] = {}
    context_count_per_case_id = {}
    for case_id, results in results_by_case_id.items():
        context_count_per_case_id[case_id] = len(set([r.context_id for r in results]))
        last_result_per_case_id[case_id] = max(results, key=lambda r: r.started_at)

    return flask.render_template(
        "c-benchmark-cases.html",
        # benchmarks_by_name=benchmarks_by_name,
        # benchmarks_results=results,
        benchmark_name=bname,
        bmr_cache_meta=_cache_bmrs["meta"],
        results_by_case_id=results_by_case_id,
        hardware_count_per_case_id=hardware_count_per_case_id,
        last_result_per_case_id=last_result_per_case_id,
        context_count_per_case_id=context_count_per_case_id,
        benchmark_result_count=len(matching_results),
        application=Config.APPLICATION_NAME,
        title=Config.APPLICATION_NAME,  # type: ignore
    )


class TypeUIPlotInfo(TypedDict):
    title: str
    data_for_uplot: List[List]


@app.route("/c-benchmarks/<bname>/<caseid>", methods=["GET"])  # type: ignore
@authorize_or_terminate
def show_benchmark_results(bname: str, caseid: str) -> str:
    # First, filter by benchmark name.
    try:
        results_all_with_bname = _cache_bmrs["by_benchmark_name"][bname]
    except KeyError:
        return f"benchmark name not known: `{bname}`"

    # Now, filter those that have the required case ID set.
    matching_results = []
    for r in results_all_with_bname:
        if r.case_id == caseid:
            matching_results.append(r)

    log.info(
        "results_all_with_bname: %s, results with caseid and bname: %s",
        len(results_all_with_bname),
        len(matching_results),
    )
    # Be explicit that this is now of no use.
    del results_all_with_bname

    if not matching_results:
        return f"no results found for benchmark `{bname}` and case `{caseid}`"

    results_by_hardware_and_context: Dict[
        Tuple, List[BMRTBenchmarkResult]
    ] = defaultdict(list)

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
    # most busy plots first.
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
    infos_for_uplots = {}

    for (hwid, ctxid, _), results in results_by_hardware_and_context_sorted.items():
        # Only include those cases where there are at least three results.
        # (this structure is used for plotting only).
        if len(results) < 3:
            continue

        infos_for_uplots[f"{hwid}_{ctxid}"] = {
            "data_for_uplot": [
                [r.started_at for r in results],
                # rely on mean to be correct? use all data for
                # error vis
                [float(r.mean) for r in results if r.mean is not None],
            ],
            # Rely on at least one result being in the list.
            "title": "hardware: %s, context: %s, %s results"
            % (results[0].ui_hardware_short, ctxid[:7], len(results)),
        }

    # Need to find a way to put bytes straight into jinja template.
    # still is still a tiny bit faster than using stdlib json.dumps()
    infos_for_uplots_json = orjson.dumps(infos_for_uplots).decode("utf-8")

    return flask.render_template(
        "c-benchmark-results-for-case.html",
        matching_benchmark_result_count=len(matching_results),
        benchmark_results_for_table=results_for_table,
        benchmark_name=bname,
        bmr_cache_meta=_cache_bmrs["meta"],
        infos_for_uplots=infos_for_uplots,
        infos_for_uplots_json=infos_for_uplots_json,
        this_case_id=matching_results[0].case_id,
        this_case_text_id=matching_results[0].case_text_id,
        application=Config.APPLICATION_NAME,
        title=Config.APPLICATION_NAME,  # type: ignore
    )
